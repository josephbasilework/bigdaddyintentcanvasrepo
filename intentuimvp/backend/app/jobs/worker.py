"""ARQ worker configuration and job functions.

This module defines the async worker that processes background jobs.
Jobs are defined as async functions that receive job context and parameters.
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.judge_agent import JudgeSynthesis, get_judge_agent
from app.agents.research_agent import ResearchReport, get_research_agent
from app.database import AsyncSessionLocal
from app.gateway.client import GatewayClient, get_gateway_client
from app.jobs.artifact_storage import (
    ArtifactMetadata,
    ArtifactType,
    get_artifact_storage,
)
from app.jobs.base import JobResult, JobType, get_redis_settings
from app.jobs.doc_generation import get_doc_service
from app.jobs.progress import progress_tracker
from app.jobs.retry import (
    checkpoint_manager,
)
from app.models.audio_block import AudioBlockStatus
from app.models.canvas import Canvas
from app.models.edge import RelationType
from app.models.node import Node, NodeType
from app.repositories.canvas_repo import CanvasRepository
from app.repositories.edge_repo import EdgeRepository
from app.repositories.node_repo import NodeRepository
from app.schemas.node import (
    BiasAnalysisSchema,
    CriticNodeMetadata,
    PerspectiveSchema,
    SynthesisNodeMetadata,
)

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "default_user"
REPORT_LABEL_LIMIT = 80
REPORT_OFFSET_X = 240.0
REPORT_OFFSET_Y = 140.0
REPORT_OFFSET_Z = 1.0

# Perspective node offsets for FR-012 Multi-Judge Compute
PERSPECTIVE_OFFSET_X = 200.0
PERSPECTIVE_OFFSET_Y = 100.0
PERSPECTIVE_OFFSET_Z = 1.0
SYNTHESIS_OFFSET_X = 400.0


class JobCancelledError(Exception):
    """Exception raised when a job is cancelled during execution.

    This exception is used to signal cooperative cancellation from within
    worker functions. It's caught at the top level of job functions to
    ensure proper cleanup and status updates.
    """

    pass


async def check_job_cancelled(job_id: str) -> None:
    """Check if a job has been cancelled and raise an exception if so.

    This function polls the database for the current job status.
    If the status is "cancelled", it raises JobCancelledError to signal
    the worker function to stop processing.

    Args:
        job_id: The ARQ job ID to check

    Raises:
        JobCancelledError: If the job status is "cancelled"

    Example:
        ```python
        async def my_job(ctx: dict[str, Any], param: str) -> JobResult:
            job_id = ctx.get("job_id")
            for item in items:
                await check_job_cancelled(job_id)  # Raises if cancelled
                # Process item...
            return JobResult(success=True)
        ```
    """
    job = await progress_tracker.get_job(job_id)
    if job and job.status == "cancelled":
        logger.info(f"[{job_id}] Job cancellation detected, stopping execution")
        raise JobCancelledError(f"Job {job_id} was cancelled")


def _truncate_label(text: str, limit: int = REPORT_LABEL_LIMIT) -> str:
    trimmed = text.strip()
    if not trimmed:
        return ""
    if len(trimmed) <= limit:
        return trimmed
    suffix = "..."
    return f"{trimmed[: max(0, limit - len(suffix))].rstrip()}{suffix}"


def _build_report_label(query: str) -> str:
    truncated_query = _truncate_label(query)
    if truncated_query:
        return f"Research Report: {truncated_query}"
    return "Research Report"


def _coerce_canvas_id(workspace_id: str | None) -> int | None:
    if not workspace_id:
        return None
    try:
        return int(workspace_id)
    except (TypeError, ValueError):
        return None


async def _resolve_canvas(
    session: AsyncSession, user_id: str | None, workspace_id: str | None
) -> Canvas:
    canvas_repo = CanvasRepository(session)
    canvas = None
    canvas_id = _coerce_canvas_id(workspace_id)
    if canvas_id is not None:
        canvas = await canvas_repo.get_by_id(canvas_id)
        if canvas is None:
            logger.warning(
                "Workspace ID did not match a canvas; falling back to user canvas",
                extra={"workspace_id": workspace_id, "user_id": user_id},
            )

    effective_user_id = user_id or DEFAULT_USER_ID
    if canvas is None:
        canvases = await canvas_repo.get_by_user(effective_user_id, limit=1)
        canvas = (
            canvases[0]
            if canvases
            else await canvas_repo.create_canvas(
                user_id=effective_user_id, name="default"
            )
        )

    return canvas


def _coerce_input_ref(ref: Any) -> int | None:
    if isinstance(ref, bool):
        return None
    if isinstance(ref, int):
        return ref
    if isinstance(ref, float):
        if ref.is_integer():
            return int(ref)
        return None
    if isinstance(ref, str):
        trimmed = ref.strip()
        if not trimmed:
            return None
        try:
            return int(trimmed)
        except ValueError:
            return None
    return None


async def _load_input_nodes(
    session: AsyncSession,
    input_refs: list[int | str | float] | None,
    canvas_id: int,
) -> list[Node]:
    if not input_refs:
        return []

    seen: set[int] = set()
    unique_ids: list[int] = []
    for ref in input_refs:
        ref_id = _coerce_input_ref(ref)
        if ref_id is None or ref_id in seen:
            continue
        seen.add(ref_id)
        unique_ids.append(ref_id)

    if not unique_ids:
        return []

    stmt = select(Node).where(Node.id.in_(unique_ids), Node.canvas_id == canvas_id)
    result = await session.execute(stmt)
    nodes = list(result.scalars().all())
    nodes_by_id = {node.id: node for node in nodes}
    return [nodes_by_id[node_id] for node_id in unique_ids if node_id in nodes_by_id]


async def _store_perspective_nodes(
    *,
    job_id: str,
    user_id: str | None,
    workspace_id: str | None,
    topic: str,
    evaluation: dict[str, Any],
    input_refs: list[int | str | float] | None,
) -> tuple[int, list[int], list[int], int]:
    """Store perspective analysis results as critic + synthesis nodes (FR-012).

    FR-012: Creates critic nodes for each perspective (skeptic, advocate, synthesizer)
    and a synthesis node. Critic nodes link to target nodes via CRITIQUES edges;
    the synthesis node links to critics via SUPPORTS edges.

    Args:
        job_id: The job ID for this analysis
        user_id: User ID who requested the analysis
        workspace_id: Canvas/workspace ID
        topic: The topic being analyzed
        evaluation: PerspectiveEvaluation dictionary from PerspectiveAgent
        input_refs: Optional list of node IDs used as inputs/targets for linking

    Returns:
        Tuple of (synthesis_node_id, critic_node_ids, edge_ids, canvas_id)
    """
    async with AsyncSessionLocal() as session:
        canvas = await _resolve_canvas(session, user_id, workspace_id)

        # Load input/target nodes for linking
        input_nodes = await _load_input_nodes(session, input_refs, canvas.id)

        topic_text = evaluation.get("topic", topic) or topic
        raw_perspectives = evaluation.get("perspectives", [])

        perspective_schemas: list[PerspectiveSchema] = []
        for perspective in raw_perspectives:
            if isinstance(perspective, BaseModel):
                perspective = perspective.model_dump()

            perspective_id = perspective.get("id") or str(uuid.uuid4())
            try:
                confidence = float(perspective.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0

            perspective_schemas.append(
                PerspectiveSchema(
                    id=str(perspective_id),
                    name=perspective.get("name", "unknown"),
                    description=perspective.get("description", ""),
                    stance=perspective.get("stance", "neutral"),
                    arguments=perspective.get("arguments") or [],
                    evidence=perspective.get("evidence") or [],
                    confidence=confidence,
                    strengths=perspective.get("strengths") or [],
                    weaknesses=perspective.get("weaknesses") or [],
                    failed=bool(perspective.get("failed", False)),
                    failure_reason=perspective.get("failure_reason"),
                )
            )

        base_x = 0.0
        base_y = 0.0
        base_z = 0.0
        if input_nodes:
            positions = [node.get_position() for node in input_nodes]
            base_x = sum(pos.get("x", 0.0) for pos in positions) / len(positions)
            base_y = sum(pos.get("y", 0.0) for pos in positions) / len(positions)
            base_z = max(pos.get("z", 0.0) for pos in positions)

        start_y = base_y
        if perspective_schemas:
            start_y = base_y - ((len(perspective_schemas) - 1) * PERSPECTIVE_OFFSET_Y) / 2

        node_repo = NodeRepository(session)
        edge_repo = EdgeRepository(session)

        critic_node_ids: list[int] = []
        all_edge_ids: list[int] = []
        source_node_id = input_nodes[0].id if len(input_nodes) == 1 else None

        # Create a critic node for each perspective
        for idx, perspective in enumerate(perspective_schemas):
            label_suffix = " (failed)" if perspective.failed else ""
            label = _truncate_label(
                f"{perspective.name.title()} Critic{label_suffix}", limit=50
            )

            position = {
                "x": base_x + PERSPECTIVE_OFFSET_X,
                "y": start_y + idx * PERSPECTIVE_OFFSET_Y,
                "z": base_z + PERSPECTIVE_OFFSET_Z,
            }

            node_metadata = CriticNodeMetadata(
                topic=topic_text,
                perspective_type=perspective.name,
                perspective=perspective,
                source_node_id=source_node_id,
            )

            critic_node = await node_repo.create_node(
                canvas_id=canvas.id,
                label=label,
                type=NodeType.CRITIC,
                position=position,
                node_metadata=node_metadata.model_dump(),
            )
            critic_node_ids.append(critic_node.id)

            # Link critic node to input/target nodes with CRITIQUES edge
            if input_nodes:
                for input_node in input_nodes:
                    edge = await edge_repo.create_edge(
                        canvas_id=canvas.id,
                        from_node_id=critic_node.id,
                        to_node_id=input_node.id,
                        relation_type=RelationType.CRITIQUES,
                        label=f"{perspective.name} critique",
                        metadata={
                            "jobId": job_id,
                            "perspective": perspective.name,
                            "confidence": perspective.confidence,
                            "failed": perspective.failed,
                        },
                    )
                    all_edge_ids.append(edge.id)

            logger.info(
                f"[{job_id}] Created critic node for perspective '{perspective.name}'",
                extra={"node_id": critic_node.id, "stance": perspective.stance},
            )

        # Create synthesis node with combined analysis
        recommendation = evaluation.get("recommendation") or ""
        consensus_points = evaluation.get("consensus_points") or []
        disagreement_points = evaluation.get("disagreement_points") or []
        bias_analysis = evaluation.get("bias_analysis") or {}
        try:
            overall_confidence = float(evaluation.get("confidence", 0.0))
        except (TypeError, ValueError):
            overall_confidence = 0.0

        synthesis_label = _truncate_label(
            f"Synthesis: {topic_text}" if topic_text else "Synthesis", limit=50
        )

        synthesis_position = {
            "x": base_x + SYNTHESIS_OFFSET_X,
            "y": base_y,
            "z": base_z + PERSPECTIVE_OFFSET_Z + 1,
        }

        bias_schema = None
        if bias_analysis:
            bias_schema = BiasAnalysisSchema(
                detected_biases=bias_analysis.get("detected_biases") or [],
                bias_explanations=bias_analysis.get("bias_explanations") or [],
                mitigation_suggestions=bias_analysis.get("mitigation_suggestions") or [],
                overall_bias_rating=bias_analysis.get("overall_bias_rating", "unknown"),
            )

        synthesis_metadata = SynthesisNodeMetadata(
            topic=topic_text,
            perspectives=perspective_schemas,
            consensus_points=consensus_points,
            disagreement_points=disagreement_points,
            bias_analysis=bias_schema,
            recommendation=recommendation,
            confidence=overall_confidence,
            source_node_ids=critic_node_ids,
        )

        synthesis_node = await node_repo.create_node(
            canvas_id=canvas.id,
            label=synthesis_label,
            type=NodeType.SYNTHESIS,
            position=synthesis_position,
            node_metadata=synthesis_metadata.model_dump(),
        )

        # Link synthesis node to all critic nodes with SUPPORTS edges
        for critic_id in critic_node_ids:
            edge = await edge_repo.create_edge(
                canvas_id=canvas.id,
                from_node_id=synthesis_node.id,
                to_node_id=critic_id,
                relation_type=RelationType.SUPPORTS,
                label="synthesizes",
                metadata={"jobId": job_id, "synthesis": True},
            )
            all_edge_ids.append(edge.id)

        logger.info(
            f"[{job_id}] Created synthesis node linked to {len(critic_node_ids)} critic nodes",
            extra={"synthesis_node_id": synthesis_node.id},
        )

    return synthesis_node.id, critic_node_ids, all_edge_ids, canvas.id


def _compute_report_position(input_nodes: list[Node]) -> dict[str, float]:
    if not input_nodes:
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    positions = [node.get_position() for node in input_nodes]
    avg_x = sum(pos.get("x", 0.0) for pos in positions) / len(positions)
    avg_y = sum(pos.get("y", 0.0) for pos in positions) / len(positions)
    max_z = max(pos.get("z", 0.0) for pos in positions)
    return {
        "x": avg_x + REPORT_OFFSET_X,
        "y": avg_y + REPORT_OFFSET_Y,
        "z": max_z + REPORT_OFFSET_Z,
    }


async def _store_research_report(
    *,
    job_id: str,
    user_id: str | None,
    workspace_id: str | None,
    query: str,
    result_data: dict[str, Any],
    input_refs: list[int | str | float] | None,
    judge_synthesis: JudgeSynthesis,
) -> tuple[int, int, list[int], int]:
    async with AsyncSessionLocal() as session:
        canvas = await _resolve_canvas(session, user_id, workspace_id)
        effective_user_id = user_id or DEFAULT_USER_ID
        report_label = _build_report_label(query)

        metadata = ArtifactMetadata(
            artifact_type=ArtifactType.RESEARCH_REPORT,
            artifact_name=report_label,
            description=f"Deep research report for '{_truncate_label(query)}'",
            filename=f"research_report_{job_id}.json",
            mime_type="application/json",
        )
        storage = get_artifact_storage()
        stored = await storage.store_artifact(
            session,
            job_id=job_id,
            metadata=metadata,
            content=json.dumps(result_data, ensure_ascii=True, indent=2),
            user_id=effective_user_id,
            workspace_id=str(canvas.id),
        )

        input_nodes = await _load_input_nodes(session, input_refs, canvas.id)
        position = _compute_report_position(input_nodes)
        node_metadata = {
            "artifactId": stored.id,
            "artifactType": stored.artifact_type,
            "jobId": job_id,
            "jobType": JobType.DEEP_RESEARCH.value,
            "query": query,
            "summary": judge_synthesis.executive_summary,
            "workspaceId": str(canvas.id),
            "sourceNodeIds": [node.id for node in input_nodes],
            "reportGeneratedAt": datetime.now(UTC).isoformat(),
        }

        node_repo = NodeRepository(session)
        node = await node_repo.create_node(
            canvas_id=canvas.id,
            label=report_label,
            type=NodeType.DOCUMENT,
            position=position,
            node_metadata=node_metadata,
        )

        edge_ids: list[int] = []
        if input_nodes:
            edge_repo = EdgeRepository(session)
            for input_node in input_nodes:
                edge = await edge_repo.create_edge(
                    canvas_id=canvas.id,
                    from_node_id=node.id,
                    to_node_id=input_node.id,
                    relation_type=RelationType.DERIVED_FROM,
                    metadata={"jobId": job_id, "artifactId": stored.id},
                )
                edge_ids.append(edge.id)

    return stored.id, node.id, edge_ids, canvas.id


async def _stream_periodic_progress(
    job_id: str,
    current_step: str,
    step_number: int,
    steps_total: int,
    progress_percent: float,
    interval_seconds: float = 10.0,
) -> asyncio.Task:
    """Create a background task that streams progress updates periodically.

    This is used during long-running operations (LLM calls, web search) to ensure
    the UI receives progress updates at least every 10 seconds as required by FR-011.

    Args:
        job_id: The job ID to stream progress for
        current_step: Description of the current step
        step_number: Current step number
        steps_total: Total number of steps
        progress_percent: Current progress percentage (0-100)
        interval_seconds: Interval between progress updates (default 10.0 for FR-011)

    Returns:
        An asyncio Task that should be cancelled when the operation completes

    Example:
        ```python
        # Start periodic progress streaming
        progress_task = await _stream_periodic_progress(
            job_id="job-123",
            current_step="Conducting web research",
            step_number=2,
            steps_total=5,
            progress_percent=40.0,
        )
        try:
            # Do long operation here
            result = await long_operation()
        finally:
            # Always cancel the progress task
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
        ```
    """
    async def _periodic_update() -> None:
        """Internal coroutine that sends periodic progress updates."""
        try:
            while True:
                await asyncio.sleep(interval_seconds)
                await check_job_cancelled(job_id)
                # Send a "still working" progress update with same percent
                await progress_tracker.update_progress(
                    job_id=job_id,
                    progress_percent=progress_percent,
                    current_step=f"{current_step}...",
                    step_number=step_number,
                    steps_total=steps_total,
                )
                logger.debug(f"[{job_id}] Periodic progress update sent")
        except asyncio.CancelledError:
            # Task was cancelled - this is expected
            logger.debug(f"[{job_id}] Periodic progress task cancelled")
            raise
        except JobCancelledError:
            # Job was cancelled - propagate this
            raise

    # Create and return the background task
    return asyncio.create_task(_periodic_update())


async def _generate_with_gateway(
    gateway: GatewayClient,
    system_prompt: str,
    user_prompt: str,
    model: str = "openai/gpt-4o",
    temperature: float = 0.7,
) -> str:
    """Generate a completion using the Gateway client.

    Args:
        gateway: Gateway client instance
        system_prompt: System prompt for the LLM
        user_prompt: User prompt for the LLM
        model: Model identifier
        temperature: Sampling temperature

    Returns:
        Generated content as string
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = await gateway.generate(
        model=model, messages=messages, temperature=temperature
    )
    return response.get("choices", [{}])[0].get("message", {}).get("content", "")


# Perspective models for multi-agent research


class PerspectiveAgent(BaseModel):
    """Definition of a research perspective agent."""

    name: str = Field(description="Name of the perspective")
    system_prompt: str = Field(description="System prompt for this perspective")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Temperature for this agent")


# Predefined research perspectives
DEFAULT_PERSPECTIVES: dict[str, PerspectiveAgent] = {
    "technical": PerspectiveAgent(
        name="technical",
        system_prompt="""You are a Technical Research Analyst. Your role is to:
- Analyze technical feasibility, implementation details, and architectural considerations
- Identify key technologies, frameworks, and tools involved
- Assess technical risks, challenges, and dependencies
- Consider scalability, performance, and security implications
- Evaluate technical debt and maintenance considerations

Focus on the HOW and WHAT from a technical standpoint.""",
        temperature=0.5,
    ),
    "business": PerspectiveAgent(
        name="business",
        system_prompt="""You are a Business Strategy Analyst. Your role is to:
- Analyze business value, ROI, and market potential
- Identify target customers, use cases, and revenue models
- Assess competitive landscape and differentiation opportunities
- Consider regulatory, legal, and compliance implications
- Evaluate operational impact and resource requirements

Focus on the WHY and WHO from a business standpoint.""",
        temperature=0.6,
    ),
    "ethical": PerspectiveAgent(
        name="ethical",
        system_prompt="""You are an Ethics and Society Analyst. Your role is to:
- Identify ethical implications and moral considerations
- Assess societal impact, fairness, and equity concerns
- Consider privacy, consent, and data protection
- Evaluate environmental sustainability implications
- Identify potential misuse cases and mitigation strategies

Focus on the SHOULD and COULD from an ethical standpoint.""",
        temperature=0.7,
    ),
    "user": PerspectiveAgent(
        name="user",
        system_prompt="""You are a User Experience Advocate. Your role is to:
- Analyze user needs, pain points, and experience expectations
- Assess accessibility, usability, and learnability
- Consider user workflows and interaction patterns
- Identify potential friction points and delight opportunities
- Evaluate onboarding, documentation, and support needs

Focus on the USER from an experiential standpoint.""",
        temperature=0.6,
    ),
}


# Job functions
# These are the actual async functions that the worker will execute


async def deep_research_job(
    ctx: dict[str, Any],
    query: str,
    depth: int = 3,
    input_refs: list[int | str | float] | None = None,
) -> JobResult:
    """Execute a deep research job across multiple perspectives.

    This job orchestrates multi-perspective research by:
    1. Gathering information from different analytical perspectives
    2. Synthesizing findings into a comprehensive report
    3. Using ResearchAgent for web search and information gathering

    Args:
        ctx: ARQ execution context (contains job_id, etc.)
        query: Research query to investigate
        depth: Depth of research (1-5, default 3)
        input_refs: Optional list of node IDs used as inputs for linking

    Returns:
        JobResult with research findings or error.
    """
    job_id = ctx.get("job_id", str(uuid.uuid4()))
    user_id = ctx.get("user_id")
    workspace_id_raw = ctx.get("workspace_id")
    workspace_id = str(workspace_id_raw) if workspace_id_raw is not None else None

    # Create job in progress tracker
    await progress_tracker.create_job(
        job_id=job_id,
        job_type=JobType.DEEP_RESEARCH,
        user_id=user_id,
        workspace_id=workspace_id,
        parameters={"query": query, "depth": depth, "input_refs": input_refs},
    )

    logger.info(f"[{job_id}] Starting deep research job: query='{query}', depth={depth}")

    # Check for existing checkpoint (recovery scenario)
    checkpoint = await checkpoint_manager.load_checkpoint(job_id)
    if checkpoint:
        logger.info(
            f"[{job_id}] Resuming from checkpoint: {checkpoint.step_name} (step {checkpoint.step_number})"
        )
        # Could restore state from checkpoint.data here

    try:
        # Check for cancellation before starting work
        await check_job_cancelled(job_id)

        # Select perspectives based on depth
        perspective_names = list(DEFAULT_PERSPECTIVES.keys())
        selected_perspectives = perspective_names[: min(depth, len(perspective_names))]
        total_steps = len(selected_perspectives) + 2  # perspectives + web research + synthesis

        logger.info(f"[{job_id}] Gathering perspectives: {selected_perspectives}")

        # Step 1: Gather research from each perspective
        perspective_results = []
        gateway = get_gateway_client()

        for idx, persp_name in enumerate(selected_perspectives, start=1):
            # Check for cancellation before each perspective
            await check_job_cancelled(job_id)

            persp_agent = DEFAULT_PERSPECTIVES[persp_name]

            # Update progress
            await progress_tracker.update_progress(
                job_id=job_id,
                progress_percent=(idx / total_steps) * 100,
                current_step=f"Gathering {persp_agent.name} perspective",
                step_number=idx,
                steps_total=total_steps,
            )

            # Generate perspective-specific analysis using Gateway
            # Start periodic progress streaming for this long operation (FR-011: 10s interval)
            progress_task = await _stream_periodic_progress(
                job_id=job_id,
                current_step=f"Gathering {persp_agent.name} perspective",
                step_number=idx,
                steps_total=total_steps,
                progress_percent=(idx / total_steps) * 100,
            )
            try:
                content = await _generate_with_gateway(
                    gateway=gateway,
                    system_prompt=persp_agent.system_prompt,
                    user_prompt=f"Analyze the following research query from your perspective: {query}\n\nProvide a comprehensive analysis including key findings, concerns, and recommendations.",
                    model="openai/gpt-4o",
                    temperature=persp_agent.temperature,
                )
            finally:
                # Always cancel the periodic progress task
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass

            # Check for cancellation after LLM call (long operation)
            await check_job_cancelled(job_id)

            perspective_results.append(
                {
                    "perspective": persp_name,
                    "name": persp_agent.name,
                    "analysis": content,
                    "temperature": persp_agent.temperature,
                }
            )
            logger.info(f"[{job_id}] Completed {persp_name} perspective analysis")

            # Save checkpoint after each perspective
            await checkpoint_manager.save_checkpoint(
                job_id=job_id,
                step_name=f"perspective_{persp_name}",
                step_number=idx,
                data={
                    "perspective_results": perspective_results,
                    "current_perspective": persp_name,
                },
            )

        # Step 2: Conduct web research using ResearchAgent
        web_research_step = len(selected_perspectives) + 1

        # Check for cancellation before web research
        await check_job_cancelled(job_id)

        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=(web_research_step / total_steps) * 100,
            current_step="Conducting web research",
            step_number=web_research_step,
            steps_total=total_steps,
        )

        logger.info(f"[{job_id}] Conducting web research")
        research_agent = get_research_agent()

        # Create a progress callback that streams research progress to the UI
        async def research_progress_callback(
            step_number: int,
            steps_total: int,
            current_step: str,
            data: dict[str, Any] | None = None,
        ) -> None:
            """Callback for streaming research progress to the UI.

            This is called by ResearchAgent during each research step to provide
            granular progress updates (sub-queries, sources found, etc.) to the UI.
            """
            # Calculate overall progress percent including research steps
            base_percent = (web_research_step - 1) / total_steps * 100
            step_size = 1 / total_steps * 100
            research_percent = (step_number - 1) / steps_total * step_size
            overall_percent = base_percent + research_percent

            await progress_tracker.update_progress(
                job_id=job_id,
                progress_percent=overall_percent,
                current_step=current_step,
                step_number=web_research_step,
                steps_total=total_steps,
                data=data or {},
            )

        # Start periodic progress streaming for web research (FR-011: 10s interval)
        progress_task = await _stream_periodic_progress(
            job_id=job_id,
            current_step="Conducting web research",
            step_number=web_research_step,
            steps_total=total_steps,
            progress_percent=(web_research_step / total_steps) * 100,
        )
        try:
            research_report: ResearchReport = await research_agent.research(
                query,
                max_steps=depth,
                progress_callback=research_progress_callback,
            )
        finally:
            # Always cancel the periodic progress task
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass

        # Check for cancellation after web research (long operation)
        await check_job_cancelled(job_id)

        # Save checkpoint after web research
        await checkpoint_manager.save_checkpoint(
            job_id=job_id,
            step_name="web_research",
            step_number=web_research_step,
            data={"research_report": research_report.model_dump()},
        )

        # Step 3: Judge and synthesize using LLM-as-Judge workflow
        judge_step = total_steps

        # Check for cancellation before synthesis
        await check_job_cancelled(job_id)

        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=(judge_step / total_steps) * 100,
            current_step="Judging and synthesizing perspectives",
            step_number=judge_step,
            steps_total=total_steps,
        )

        logger.info(f"[{job_id}] Running LLM-as-Judge evaluation")

        # Get Judge Agent and evaluate perspectives
        judge_agent = get_judge_agent(gateway=gateway)

        # Start periodic progress streaming for judge synthesis (FR-011: 10s interval)
        progress_task = await _stream_periodic_progress(
            job_id=job_id,
            current_step="Judging and synthesizing perspectives",
            step_number=judge_step,
            steps_total=total_steps,
            progress_percent=(judge_step / total_steps) * 100,
        )
        try:
            judge_synthesis: JudgeSynthesis = await judge_agent.judge(
                query=query,
                perspective_results=perspective_results,
            )
        finally:
            # Always cancel the periodic progress task
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass

        # Compile final result with judge synthesis
        result_data = {
            "query": query,
            "depth": depth,
            "input_refs": input_refs,
            "perspectives": perspective_results,
            "web_research": research_report.model_dump(),
            "judge_synthesis": judge_synthesis.model_dump(),
            "synthesis": judge_synthesis.model_dump(),
            "timestamp": datetime.now(UTC).isoformat(),
            "job_id": job_id,
        }

        report_artifact_id, report_node_id, report_edge_ids, report_canvas_id = (
            await _store_research_report(
                job_id=job_id,
                user_id=user_id,
                workspace_id=workspace_id,
                query=query,
                result_data=result_data,
                input_refs=input_refs,
                judge_synthesis=judge_synthesis,
            )
        )

        result_data.update(
            {
                "report_artifact_id": report_artifact_id,
                "report_node_id": report_node_id,
                "report_edge_ids": report_edge_ids,
                "report_canvas_id": report_canvas_id,
            }
        )

        logger.info(f"[{job_id}] Deep research completed successfully")

        # Mark job as complete
        await progress_tracker.complete_job(job_id=job_id, result_data=result_data)

        return JobResult(success=True, data=result_data)

    except JobCancelledError:
        logger.info(f"[{job_id}] Deep research job was cancelled")
        # Status already set to cancelled by the API, just need to return
        return JobResult(
            success=False,
            error="Job was cancelled",
            metadata={"job_id": job_id, "cancelled": True},
        )
    except Exception as e:
        logger.error(f"[{job_id}] Deep research failed: {e}", exc_info=True)

        # Mark job as failed
        await progress_tracker.fail_job(job_id=job_id, error_message=str(e))

        return JobResult(
            success=False, error=f"Deep research failed: {str(e)}", metadata={"job_id": job_id}
        )


async def perspective_gather_job(
    ctx: dict[str, Any], query: str, perspectives: list[str]
) -> JobResult:
    """Gather information from multiple perspectives.

    This job conducts focused analysis from specified analytical perspectives
    using specialized agent personas for each viewpoint.

    Args:
        ctx: ARQ execution context
        query: Research query
        perspectives: List of perspective names to gather (e.g., ["technical", "business"])

    Returns:
        JobResult with gathered perspective data.
    """
    job_id = ctx.get("job_id", str(uuid.uuid4()))
    user_id = ctx.get("user_id")
    workspace_id = ctx.get("workspace_id")

    # Create job in progress tracker
    await progress_tracker.create_job(
        job_id=job_id,
        job_type=JobType.PERSPECTIVE_GATHER,
        user_id=user_id,
        workspace_id=workspace_id,
        parameters={"query": query, "perspectives": perspectives},
    )

    logger.info(f"[{job_id}] Gathering perspectives: {perspectives}")

    try:
        # Check for cancellation before starting work
        await check_job_cancelled(job_id)

        results = []
        gateway = get_gateway_client()
        total_steps = len(perspectives)

        for idx, persp_name in enumerate(perspectives, start=1):
            # Check for cancellation before each perspective
            await check_job_cancelled(job_id)

            # Get perspective configuration
            if persp_name not in DEFAULT_PERSPECTIVES:
                logger.warning(f"[{job_id}] Unknown perspective: {persp_name}, skipping")
                continue

            persp_agent = DEFAULT_PERSPECTIVES[persp_name]

            # Update progress
            await progress_tracker.update_progress(
                job_id=job_id,
                progress_percent=(idx / total_steps) * 100,
                current_step=f"Gathering {persp_agent.name} perspective",
                step_number=idx,
                steps_total=total_steps,
            )

            # Generate perspective-specific analysis using Gateway
            content = await _generate_with_gateway(
                gateway=gateway,
                system_prompt=persp_agent.system_prompt,
                user_prompt=f"Analyze the following research query from your perspective: {query}\n\nProvide a comprehensive analysis including:\n- Key findings relevant to your perspective\n- Concerns or risks\n- Recommendations\n- Related questions to consider",
                model="openai/gpt-4o",
                temperature=persp_agent.temperature,
            )

            # Check for cancellation after LLM call (long operation)
            await check_job_cancelled(job_id)

            results.append(
                {
                    "name": persp_name,
                    "display_name": persp_agent.name,
                    "analysis": content,
                    "temperature": persp_agent.temperature,
                }
            )
            logger.info(f"[{job_id}] Completed {persp_name} perspective")

        result_data = {
            "query": query,
            "perspectives": results,
            "timestamp": datetime.now(UTC).isoformat(),
            "job_id": job_id,
        }

        logger.info(f"[{job_id}] Perspective gathering completed successfully")

        # Mark job as complete
        await progress_tracker.complete_job(job_id=job_id, result_data=result_data)

        return JobResult(success=True, data=result_data)

    except JobCancelledError:
        logger.info(f"[{job_id}] Perspective gathering job was cancelled")
        return JobResult(
            success=False,
            error="Job was cancelled",
            metadata={"job_id": job_id, "cancelled": True},
        )
    except Exception as e:
        logger.error(f"[{job_id}] Perspective gathering failed: {e}", exc_info=True)

        # Mark job as failed
        await progress_tracker.fail_job(job_id=job_id, error_message=str(e))

        return JobResult(
            success=False, error=f"Perspective gathering failed: {str(e)}", metadata={"job_id": job_id}
        )


async def perspective_analysis_job(
    ctx: dict[str, Any],
    topic: str,
    perspectives: list[str] | None = None,
    input_refs: list[int | str | float] | None = None,
) -> JobResult:
    """Run perspective analysis using LLM-as-judge patterns (FR-012).

    This job analyzes a topic from multiple perspectives (skeptic, advocate, synthesizer)
    using the PerspectiveAgent and creates critic + synthesis nodes on the canvas.

    Args:
        ctx: ARQ execution context (contains job_id, user_id, workspace_id)
        topic: Topic to analyze
        perspectives: Optional list of perspective types (defaults to skeptic, advocate, synthesizer)
        input_refs: Optional list of node IDs to link critic nodes to

    Returns:
        JobResult with synthesis node ID and analysis results.
    """
    from app.agents.perspective_agent import get_perspective_agent

    job_id = ctx.get("job_id", str(uuid.uuid4()))
    user_id = ctx.get("user_id")
    workspace_id = ctx.get("workspace_id")

    # Create job in progress tracker
    await progress_tracker.create_job(
        job_id=job_id,
        job_type=JobType.PERSPECTIVE_ANALYSIS,
        user_id=user_id,
        workspace_id=workspace_id,
        parameters={"topic": topic, "perspectives": perspectives, "input_refs": input_refs},
    )

    logger.info(f"[{job_id}] Starting perspective analysis for topic: {topic}")

    try:
        await check_job_cancelled(job_id)

        # Use default perspectives if none provided (FR-012)
        if perspectives is None or len(perspectives) == 0:
            perspectives = ["skeptic", "advocate", "synthesizer"]

        # Update initial progress
        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=10,
            current_step="Initializing perspective analysis",
            step_number=1,
            steps_total=2,
        )

        await check_job_cancelled(job_id)

        # Get the perspective agent and run evaluation
        agent = get_perspective_agent()
        evaluation = await agent.evaluate(topic)

        await check_job_cancelled(job_id)

        # Update progress after evaluation
        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=70,
            current_step="Creating critic and synthesis nodes",
            step_number=2,
            steps_total=2,
        )

        # Store perspective nodes using _store_perspective_nodes (FR-012)
        synthesis_node_id, critic_node_ids, edge_ids, canvas_id = await _store_perspective_nodes(
            job_id=job_id,
            user_id=user_id,
            workspace_id=workspace_id,
            topic=topic,
            evaluation=evaluation.model_dump(),
            input_refs=input_refs,
        )

        result_data = {
            "topic": topic,
            "synthesis_node_id": synthesis_node_id,
            "critic_node_ids": critic_node_ids,
            "edge_ids": edge_ids,
            "canvas_id": canvas_id,
            "evaluation": evaluation.model_dump(),
            "timestamp": datetime.now(UTC).isoformat(),
            "job_id": job_id,
        }

        logger.info(
            f"[{job_id}] Perspective analysis completed: "
            f"{len(critic_node_ids)} critics, synthesis node {synthesis_node_id}"
        )

        # Mark job as complete
        await progress_tracker.complete_job(job_id=job_id, result_data=result_data)

        return JobResult(success=True, data=result_data)

    except JobCancelledError:
        logger.info(f"[{job_id}] Perspective analysis job was cancelled")
        return JobResult(
            success=False,
            error="Job was cancelled",
            metadata={"job_id": job_id, "cancelled": True},
        )
    except Exception as e:
        logger.error(f"[{job_id}] Perspective analysis failed: {e}", exc_info=True)

        # Mark job as failed
        await progress_tracker.fail_job(job_id=job_id, error_message=str(e))

        return JobResult(
            success=False,
            error=f"Perspective analysis failed: {str(e)}",
            metadata={"job_id": job_id},
        )


async def synthesis_job(
    ctx: dict[str, Any], query: str, perspective_results: list[dict[str, Any]]
) -> JobResult:
    """Synthesize results from multiple perspectives using LLM-as-Judge workflow.

    This job uses the Judge Agent to evaluate, score, and synthesize results
    from multiple perspective analyses into a comprehensive, actionable report.

    Args:
        ctx: ARQ execution context
        query: Original research query
        perspective_results: Results from perspective gathering jobs

    Returns:
        JobResult with synthesized findings.

    Raises:
        ValueError: If perspective_results is empty.
    """
    job_id = ctx.get("job_id", str(uuid.uuid4()))
    user_id = ctx.get("user_id")
    workspace_id = ctx.get("workspace_id")

    # Create job in progress tracker
    await progress_tracker.create_job(
        job_id=job_id,
        job_type=JobType.SYNTHESIS,
        user_id=user_id,
        workspace_id=workspace_id,
        parameters={"query": query, "perspective_count": len(perspective_results)},
    )

    logger.info(f"[{job_id}] Synthesizing {len(perspective_results)} perspective results using Judge Agent")

    # Validate input before try/catch to allow ValueError to propagate
    if not perspective_results:
        raise ValueError("No perspective results to synthesize")

    try:
        # Check for cancellation before starting work
        await check_job_cancelled(job_id)

        # Update progress - starting evaluation
        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=10,
            current_step="Evaluating perspectives with Judge Agent",
            step_number=1,
            steps_total=2,
        )

        # Use Judge Agent for evaluation and synthesis
        gateway = get_gateway_client()
        judge_agent = get_judge_agent(gateway=gateway)
        judge_synthesis: JudgeSynthesis = await judge_agent.judge(
            query=query,
            perspective_results=perspective_results,
        )

        # Check for cancellation after judge synthesis (long operation)
        await check_job_cancelled(job_id)

        # Update progress - synthesis complete
        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=90,
            current_step="Synthesis complete",
            step_number=2,
            steps_total=2,
        )

        result_data = {
            "query": query,
            "perspective_count": len(perspective_results),
            "judge_synthesis": judge_synthesis.model_dump(),
            "synthesis": judge_synthesis.model_dump(),
            "timestamp": datetime.now(UTC).isoformat(),
            "job_id": job_id,
        }

        logger.info(f"[{job_id}] Judge-based synthesis completed successfully")

        # Mark job as complete
        await progress_tracker.complete_job(job_id=job_id, result_data=result_data)

        return JobResult(success=True, data=result_data)

    except JobCancelledError:
        logger.info(f"[{job_id}] Synthesis job was cancelled")
        return JobResult(
            success=False,
            error="Job was cancelled",
            metadata={"job_id": job_id, "cancelled": True},
        )
    except Exception as e:
        logger.error(f"[{job_id}] Synthesis failed: {e}", exc_info=True)

        # Mark job as failed
        await progress_tracker.fail_job(job_id=job_id, error_message=str(e))

        return JobResult(
            success=False, error=f"Synthesis failed: {str(e)}", metadata={"job_id": job_id}
        )


async def export_job(
    ctx: dict[str, Any],
    workspace_id: str,
    export_format: str = "json",
) -> JobResult:
    """Export a workspace to a file.

    Args:
        ctx: ARQ execution context
        workspace_id: Workspace to export
        export_format: Export format (json, csv, etc.)

    Returns:
        JobResult with export file path or error.
    """
    job_id = ctx.get("job_id", str(uuid.uuid4()))
    user_id = ctx.get("user_id")

    # Create job in progress tracker
    await progress_tracker.create_job(
        job_id=job_id,
        job_type=JobType.EXPORT,
        user_id=user_id,
        workspace_id=workspace_id,
        parameters={"export_format": export_format},
    )

    logger.info(f"[{job_id}] Exporting workspace {workspace_id} as {export_format}")

    try:
        # Check for cancellation before starting work
        await check_job_cancelled(job_id)

        # Update progress - starting export
        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=50,
            current_step="Exporting workspace",
            step_number=1,
            steps_total=1,
        )

        # Simulate export (could be a long operation)
        await asyncio.sleep(1)

        # Check for cancellation after export operation
        await check_job_cancelled(job_id)

        result_data = {
            "workspace_id": workspace_id,
            "format": export_format,
            "file_path": f"/exports/{workspace_id}.{export_format}",
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info(f"[{job_id}] Export completed")

        # Mark job as complete
        await progress_tracker.complete_job(job_id=job_id, result_data=result_data)

        return JobResult(success=True, data=result_data)

    except JobCancelledError:
        logger.info(f"[{job_id}] Export job was cancelled")
        return JobResult(
            success=False,
            error="Job was cancelled",
            metadata={"job_id": job_id, "cancelled": True},
        )
    except Exception as e:
        logger.error(f"[{job_id}] Export failed: {e}")

        # Mark job as failed
        await progress_tracker.fail_job(job_id=job_id, error_message=str(e))

        return JobResult(success=False, error=str(e))


async def transcription_job(
    ctx: dict[str, Any],
    audio_block_id: int,
) -> JobResult:
    """Transcribe audio content from an audio block.

    This job processes an audio block and generates a transcription.
    For the MVP, this uses a mock transcription service via the Gateway.

    Args:
        ctx: ARQ execution context (contains job_id, user_id, workspace_id)
        audio_block_id: ID of the audio block to transcribe

    Returns:
        JobResult with transcription data or error.
    """
    job_id = ctx.get("job_id", str(uuid.uuid4()))
    user_id = ctx.get("user_id")
    workspace_id = ctx.get("workspace_id")

    # Create job in progress tracker
    await progress_tracker.create_job(
        job_id=job_id,
        job_type=JobType.TRANSCRIPTION,
        user_id=user_id,
        workspace_id=workspace_id,
        parameters={"audio_block_id": audio_block_id},
    )

    logger.info(f"[{job_id}] Starting transcription job for audio block {audio_block_id}")

    try:
        # Check for cancellation before starting work
        await check_job_cancelled(job_id)

        from app.database import SessionLocal
        from app.repositories.audio_block_repo import AudioBlockRepository

        # Get the audio block from database
        db = SessionLocal()
        try:
            repo = AudioBlockRepository(db)
            audio_block = await repo.get_by_id(audio_block_id)

            if audio_block is None:
                raise ValueError(f"Audio block {audio_block_id} not found")

            # Update progress - starting transcription
            await progress_tracker.update_progress(
                job_id=job_id,
                progress_percent=20,
                current_step="Preparing audio for transcription",
                step_number=1,
                steps_total=3,
            )

            # Check for cancellation
            await check_job_cancelled(job_id)

            # Update status to transcribing
            await repo.set_status(audio_block_id, AudioBlockStatus.TRANSCRIBING)
            logger.info(f"[{job_id}] Set audio block {audio_block_id} status to transcribing")

            # Update progress - processing audio
            await progress_tracker.update_progress(
                job_id=job_id,
                progress_percent=50,
                current_step="Processing audio content",
                step_number=2,
                steps_total=3,
            )

            # For MVP: Generate mock transcription
            # In production, this would call a real transcription service
            # For now, we'll use a placeholder that indicates transcription occurred
            mock_transcription = (
                f"[Transcription of audio block {audio_block_id}]\n"
                f"Audio URI: {audio_block.audio_uri}\n"
                f"Duration: {audio_block.duration or 'unknown'} seconds\n\n"
                f"Note: This is a mock transcription for the MVP. "
                f"In production, this would contain the actual transcribed text "
                f"from the audio recording using a service like OpenAI Whisper."
            )

            # Simulate processing time
            await asyncio.sleep(1)

            # Check for cancellation after processing
            await check_job_cancelled(job_id)

            # Update progress - completing
            await progress_tracker.update_progress(
                job_id=job_id,
                progress_percent=90,
                current_step="Finalizing transcription",
                step_number=3,
                steps_total=3,
            )

            # Update audio block with transcription
            await repo.update_transcription(audio_block_id, mock_transcription)
            logger.info(f"[{job_id}] Updated audio block {audio_block_id} with transcription")

            result_data = {
                "audio_block_id": audio_block_id,
                "transcription": mock_transcription,
                "status": "transcribed",
                "timestamp": datetime.now(UTC).isoformat(),
                "job_id": job_id,
            }

            logger.info(f"[{job_id}] Transcription job completed successfully")

            # Mark job as complete
            await progress_tracker.complete_job(job_id=job_id, result_data=result_data)

            return JobResult(success=True, data=result_data)

        finally:
            db.close()

    except JobCancelledError:
        logger.info(f"[{job_id}] Transcription job was cancelled")

        # Update audio block status back to ready if cancelled
        try:
            db = SessionLocal()
            repo = AudioBlockRepository(db)
            await repo.set_status(audio_block_id, AudioBlockStatus.READY)
            db.close()
        except Exception:
            pass  # Best effort cleanup

        return JobResult(
            success=False,
            error="Job was cancelled",
            metadata={"job_id": job_id, "cancelled": True},
        )
    except Exception as e:
        logger.error(f"[{job_id}] Transcription failed: {e}", exc_info=True)

        # Update audio block with error status
        try:
            db = SessionLocal()
            repo = AudioBlockRepository(db)
            await repo.set_status(
                audio_block_id, AudioBlockStatus.ERROR, error_message=str(e)
            )
            db.close()
        except Exception:
            pass  # Best effort cleanup

        # Mark job as failed
        await progress_tracker.fail_job(job_id=job_id, error_message=str(e))

        return JobResult(
            success=False,
            error=f"Transcription failed: {str(e)}",
            metadata={"job_id": job_id},
        )


async def planner_job(
    ctx: dict[str, Any],
    goal: str,
    context: str = "",
) -> JobResult:
    """Execute a planning job to generate a structured plan with task DAG.

    This job uses the PlannerAgent to decompose a user goal into:
    - Structured plan with objectives and approach
    - Task DAG (Directed Acyclic Graph) with dependencies
    - Execution order for parallelizable work

    Args:
        ctx: ARQ execution context (contains job_id, user_id, workspace_id)
        goal: The user's goal or objective to plan for
        context: Optional additional context (selected nodes, workspace state, etc.)

    Returns:
        JobResult with plan data or error.
    """
    job_id = ctx.get("job_id", str(uuid.uuid4()))
    user_id = ctx.get("user_id")
    workspace_id = ctx.get("workspace_id")

    await progress_tracker.create_job(
        job_id=job_id,
        job_type=JobType.PLANNER,
        user_id=user_id,
        workspace_id=workspace_id,
        parameters={"goal": goal, "context": context},
    )

    logger.info(f"[{job_id}] Starting planner job for goal: {goal[:50]}...")

    try:
        await check_job_cancelled(job_id)

        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=10,
            current_step="Analyzing goal and context",
            step_number=1,
            steps_total=3,
        )

        from app.agents.planner_agent import get_planner

        planner = get_planner()

        await check_job_cancelled(job_id)

        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=30,
            current_step="Generating structured plan",
            step_number=2,
            steps_total=3,
        )

        progress_task = await _stream_periodic_progress(
            job_id=job_id,
            current_step="Generating structured plan",
            step_number=2,
            steps_total=3,
            progress_percent=50,
        )

        try:
            planner_result = await planner.plan(goal, context)
        finally:
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass

        await check_job_cancelled(job_id)

        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=90,
            current_step="Finalizing plan and execution order",
            step_number=3,
            steps_total=3,
        )

        execution_order = planner_result.task_dag.get_execution_order()

        result_data = {
            "plan_metadata": planner_result.plan_metadata.model_dump(),
            "task_dag": planner_result.task_dag.model_dump(),
            "execution_order": execution_order,
            "source_references": planner_result.source_references,
            "reasoning": planner_result.reasoning,
            "success": planner_result.success,
            "job_id": job_id,
        }

        logger.info(
            f"[{job_id}] Planner job completed: "
            f"{len(planner_result.task_dag.tasks)} tasks, "
            f"{len(execution_order)} execution layers"
        )

        await progress_tracker.complete_job(job_id=job_id, result_data=result_data)

        return JobResult(success=planner_result.success, data=result_data)

    except JobCancelledError:
        logger.info(f"[{job_id}] Planner job was cancelled")
        return JobResult(
            success=False,
            error="Job was cancelled",
            metadata={"job_id": job_id, "cancelled": True},
        )
    except Exception as e:
        logger.error(f"[{job_id}] Planner job failed: {e}", exc_info=True)

        await progress_tracker.fail_job(job_id=job_id, error_message=str(e))

        return JobResult(
            success=False,
            error=f"Planning failed: {str(e)}",
            metadata={"job_id": job_id},
        )


async def doc_generation_job(
    ctx: dict[str, Any],
    source_job_id: str,
    doc_format: str = "markdown",
    include_metadata: bool = True,
) -> JobResult:
    """Generate structured documentation from job artifacts.

    This job processes completed job artifacts (especially plan and research jobs)
    and generates well-formatted documentation that can be exported or reviewed.

    Args:
        ctx: ARQ execution context (contains job_id, user_id, workspace_id)
        source_job_id: Job ID to generate documentation from
        doc_format: Output format (markdown, html, text)
        include_metadata: Whether to include timestamps and metadata

    Returns:
        JobResult with generated documentation or error.
    """
    job_id = ctx.get("job_id", str(uuid.uuid4()))
    user_id = ctx.get("user_id")
    workspace_id = ctx.get("workspace_id")

    await progress_tracker.create_job(
        job_id=job_id,
        job_type=JobType.DOC_GENERATION,
        user_id=user_id,
        workspace_id=workspace_id,
        parameters={
            "source_job_id": source_job_id,
            "doc_format": doc_format,
            "include_metadata": include_metadata,
        },
    )

    logger.info(
        f"[{job_id}] Starting doc generation job for source job {source_job_id}"
    )

    try:
        await check_job_cancelled(job_id)

        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=20,
            current_step="Retrieving source job",
            step_number=1,
            steps_total=4,
        )

        # Get source job to retrieve its result data
        source_job = await progress_tracker.get_job(source_job_id)
        if not source_job:
            raise ValueError(f"Source job {source_job_id} not found")

        # Parse source job result data
        source_result_data = {}
        if source_job.result_data:
            import json

            try:
                source_result_data = json.loads(source_job.result_data)
            except json.JSONDecodeError:
                logger.warning(
                    f"[{job_id}] Failed to parse source job result data, using empty dict"
                )

        await check_job_cancelled(job_id)

        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=50,
            current_step="Generating documentation",
            step_number=2,
            steps_total=4,
        )

        # Generate documentation
        doc_service = get_doc_service()

        source_job_type = source_job.job_type
        if source_job_type == JobType.PLANNER:
            generated = await doc_service.generate_from_plan_result(
                source_result_data,
                doc_format=doc_format,
                include_metadata=include_metadata,
            )
        elif source_job_type in (
            JobType.DEEP_RESEARCH,
            JobType.SYNTHESIS,
            JobType.PERSPECTIVE_GATHER,
        ):
            generated = await doc_service.generate_from_research_result(
                source_result_data,
                doc_format=doc_format,
                include_metadata=include_metadata,
            )
        else:
            # Generic format for other job types
            generated = await doc_service.generate_from_plan_result(
                source_result_data,
                doc_format=doc_format,
                include_metadata=include_metadata,
            )

        await check_job_cancelled(job_id)

        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=70,
            current_step="Storing documentation artifact",
            step_number=3,
            steps_total=4,
        )

        # Store the generated doc as an artifact
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.config import get_settings

        _settings = get_settings()
        _db_url = _settings.database_url
        if _db_url.startswith("sqlite://"):
            _db_url = _db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

        _async_engine = create_async_engine(_db_url)
        async_session_maker = async_sessionmaker(
            bind=_async_engine, expire_on_commit=False
        )

        async with async_session_maker() as db:
            from app.jobs.artifact_storage import (
                ArtifactMetadata,
                ArtifactType,
                get_artifact_storage,
            )

            storage = get_artifact_storage()

            metadata = ArtifactMetadata(
                artifact_type=ArtifactType.MARKDOWN_DOCUMENT,
                artifact_name=f"Documentation from job {source_job_id}",
                description=f"Generated documentation from {source_job_type} job",
                filename=f"doc_{source_job_id}.md",
                mime_type="text/markdown",
            )

            stored = await storage.store_artifact(
                db=db,
                job_id=source_job_id,
                metadata=metadata,
                content=generated.content,
                user_id=user_id,
                workspace_id=workspace_id,
            )

            generated.artifact_id = stored.id

        await check_job_cancelled(job_id)

        await progress_tracker.update_progress(
            job_id=job_id,
            progress_percent=90,
            current_step="Documentation complete",
            step_number=4,
            steps_total=4,
        )

        result_data = {
            "source_job_id": source_job_id,
            "source_job_type": source_job_type,
            "doc_format": doc_format,
            "content": generated.content,
            "artifact_id": generated.artifact_id,
            "generated_at": generated.generated_at,
            "job_id": job_id,
        }

        logger.info(
            f"[{job_id}] Doc generation completed: artifact_id={generated.artifact_id}"
        )

        await progress_tracker.complete_job(job_id=job_id, result_data=result_data)

        return JobResult(success=True, data=result_data)

    except JobCancelledError:
        logger.info(f"[{job_id}] Doc generation job was cancelled")
        return JobResult(
            success=False,
            error="Job was cancelled",
            metadata={"job_id": job_id, "cancelled": True},
        )
    except Exception as e:
        logger.error(f"[{job_id}] Doc generation failed: {e}", exc_info=True)

        await progress_tracker.fail_job(job_id=job_id, error_message=str(e))

        return JobResult(
            success=False,
            error=f"Doc generation failed: {str(e)}",
            metadata={"job_id": job_id},
        )


# ARQ Worker Configuration


class WorkerSettings:
    """ARQ worker settings.

    Defines job functions, retry behavior, and Redis connection.
    """

    # Redis connection
    redis_settings = get_redis_settings()

    # Job functions registry
    functions = [
        deep_research_job,
        perspective_gather_job,
        perspective_analysis_job,
        synthesis_job,
        export_job,
        transcription_job,
        planner_job,
        doc_generation_job,
    ]

    # Retry settings
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    retry_jobs = True
    max_tries = 3

    # Queue settings
    queue_read_limit = 100
    queue_name = "intentui:jobs"

    # Health check
    health_check_interval = 60

    # On startup
    async def on_startup(self) -> None:
        """Called when worker starts."""
        logger.info("ARQ worker starting up...")

    # On shutdown
    async def on_shutdown(self) -> None:
        """Called when worker shuts down."""
        logger.info("ARQ worker shutting down...")


# Scheduled jobs (cron)
# Example: health check job every hour
async def health_check_job(ctx: dict[str, Any]) -> None:
    """Periodic health check job."""
    logger.debug("Health check job executed")


# Note: Cron jobs can be added to WorkerSettings.cron_jobs list
# Example: WorkerSettings.cron_jobs = [cron(health_check_job, minute={0})]
# For now, cron jobs are configured separately
