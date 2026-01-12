"""ARQ worker configuration and job functions.

This module defines the async worker that processes background jobs.
Jobs are defined as async functions that receive job context and parameters.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.agents.judge_agent import JudgeSynthesis, get_judge_agent
from app.agents.research_agent import ResearchReport, get_research_agent
from app.gateway.client import GatewayClient, get_gateway_client
from app.jobs.base import JobResult, JobType, get_redis_settings
from app.jobs.progress import progress_tracker
from app.jobs.retry import (
    checkpoint_manager,
)
from app.models.audio_block import AudioBlockStatus

logger = logging.getLogger(__name__)


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


async def deep_research_job(ctx: dict[str, Any], query: str, depth: int = 3) -> JobResult:
    """Execute a deep research job across multiple perspectives.

    This job orchestrates multi-perspective research by:
    1. Gathering information from different analytical perspectives
    2. Synthesizing findings into a comprehensive report
    3. Using ResearchAgent for web search and information gathering

    Args:
        ctx: ARQ execution context (contains job_id, etc.)
        query: Research query to investigate
        depth: Depth of research (1-5, default 3)

    Returns:
        JobResult with research findings or error.
    """
    job_id = ctx.get("job_id", str(uuid.uuid4()))
    user_id = ctx.get("user_id")
    workspace_id = ctx.get("workspace_id")

    # Create job in progress tracker
    await progress_tracker.create_job(
        job_id=job_id,
        job_type=JobType.DEEP_RESEARCH,
        user_id=user_id,
        workspace_id=workspace_id,
        parameters={"query": query, "depth": depth},
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
                query, max_steps=depth
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
            "perspectives": perspective_results,
            "web_research": research_report.model_dump(),
            "judge_synthesis": judge_synthesis.model_dump(),
            "synthesis": judge_synthesis.model_dump(),
            "timestamp": datetime.now(UTC).isoformat(),
            "job_id": job_id,
        }

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
        synthesis_job,
        export_job,
        transcription_job,
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
