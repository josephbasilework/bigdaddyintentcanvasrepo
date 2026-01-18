"""Doc generation service for creating structured documentation from artifacts.

This module provides functionality to generate structured documentation from
job artifacts, including plan nodes, research reports, and synthesis outputs.

The service:
- Extracts and structures content from artifacts
- Generates well-formatted markdown documentation
- Stores generated docs as artifacts
- Computes diffs for update suggestions when source artifacts change
"""

import logging
import re
from datetime import UTC, datetime
from difflib import unified_diff
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.client import GatewayClient, get_gateway_client
from app.jobs.artifact_storage import (
    ArtifactMetadata,
    ArtifactStorageService,
    ArtifactType,
    StoredArtifact,
    get_artifact_storage,
)

logger = logging.getLogger(__name__)


class DocGenerationRequest(BaseModel):
    """Request model for doc generation."""

    job_id: str | None = Field(
        default=None,
        description="Job ID to generate docs from. If not provided, uses node_id.",
    )
    node_id: int | None = Field(
        default=None,
        description="Node ID to generate docs from. If not provided, uses job_id.",
    )
    workspace_id: str | None = Field(
        default=None,
        description="Workspace ID context for the doc.",
    )
    doc_format: str = Field(
        default="markdown",
        description="Output format for the documentation (markdown, html, text).",
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to include metadata (timestamps, job IDs, etc.).",
    )


class GeneratedDocument(BaseModel):
    """Result from doc generation."""

    content: str = Field(description="Generated documentation content")
    format: str = Field(description="Format of the documentation")
    artifact_id: int | None = Field(
        default=None, description="Artifact ID if stored"
    )
    source_job_id: str | None = Field(default=None, description="Source job ID")
    source_node_id: int | None = Field(default=None, description="Source node ID")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Timestamp when doc was generated",
    )
    success: bool = Field(default=True, description="Whether generation succeeded")


class DocUpdateSuggestion(BaseModel):
    """Suggestion for updating an existing document based on artifact changes.

    Represents a diff between an existing document and a newly generated version,
    allowing for HITL (Human-in-the-Loop) approval before applying changes.
    """

    existing_doc_artifact_id: int = Field(
        description="Artifact ID of the existing document"
    )
    source_artifact_id: int = Field(
        description="Artifact ID that the document was generated from"
    )
    new_content: str = Field(description="New document content")
    diff: str = Field(description="Unified diff between old and new content")
    has_changes: bool = Field(
        default=True, description="Whether there are any changes"
    )
    lines_added: int = Field(default=0, description="Number of lines added")
    lines_removed: int = Field(default=0, description="Number of lines removed")
    suggested_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Timestamp when suggestion was created",
    )


class DocGenerationService:
    """Service for generating structured documentation from artifacts.

    This service extracts content from job artifacts and generates
    well-formatted documentation in various formats.
    """

    def __init__(
        self,
        gateway: GatewayClient | None = None,
        storage: ArtifactStorageService | None = None,
    ) -> None:
        """Initialize the doc generation service.

        Args:
            gateway: Optional Gateway client instance.
            storage: Optional artifact storage service.
        """
        self.gateway = gateway or get_gateway_client()
        self.storage = storage or get_artifact_storage()

    async def generate_from_plan_result(
        self,
        plan_result: dict[str, Any],
        doc_format: str = "markdown",
        include_metadata: bool = True,
    ) -> GeneratedDocument:
        """Generate documentation from a planner job result.

        Args:
            plan_result: The result data from a planner job.
            doc_format: Output format (markdown, html, text).
            include_metadata: Whether to include timestamps and metadata.

        Returns:
            GeneratedDocument with the formatted documentation.
        """
        plan_metadata = plan_result.get("plan_metadata", {})
        task_dag = plan_result.get("task_dag", {})
        execution_order = plan_result.get("execution_order", [])
        source_job_id = plan_result.get("job_id")

        if doc_format == "markdown":
            content = self._format_plan_as_markdown(
                plan_metadata, task_dag, execution_order, include_metadata, source_job_id
            )
        elif doc_format == "html":
            content = self._format_plan_as_html(
                plan_metadata, task_dag, execution_order, include_metadata, source_job_id
            )
        else:
            # Plain text fallback
            content = self._format_plan_as_text(
                plan_metadata, task_dag, execution_order, include_metadata, source_job_id
            )

        return GeneratedDocument(
            content=content,
            format=doc_format,
            source_job_id=source_job_id,
        )

    async def generate_from_research_result(
        self,
        research_result: dict[str, Any],
        doc_format: str = "markdown",
        include_metadata: bool = True,
    ) -> GeneratedDocument:
        """Generate documentation from a research job result.

        Args:
            research_result: The result data from a research job.
            doc_format: Output format (markdown, html, text).
            include_metadata: Whether to include timestamps and metadata.

        Returns:
            GeneratedDocument with the formatted documentation.
        """
        query = research_result.get("query", "")
        perspectives = research_result.get("perspectives", [])
        judge_synthesis = research_result.get("judge_synthesis", {})
        source_job_id = research_result.get("job_id")

        if doc_format == "markdown":
            content = self._format_research_as_markdown(
                query, perspectives, judge_synthesis, include_metadata, source_job_id
            )
        elif doc_format == "html":
            content = self._format_research_as_html(
                query, perspectives, judge_synthesis, include_metadata, source_job_id
            )
        else:
            content = self._format_research_as_text(
                query, perspectives, judge_synthesis, include_metadata, source_job_id
            )

        return GeneratedDocument(
            content=content,
            format=doc_format,
            source_job_id=source_job_id,
        )

    async def generate_and_store(
        self,
        request: DocGenerationRequest,
        source_artifact: StoredArtifact,
        source_result_data: dict[str, Any],
        user_id: str | None = None,
    ) -> GeneratedDocument:
        """Generate documentation and store it as an artifact.

        Args:
            request: The doc generation request.
            source_artifact: The source artifact being documented.
            source_result_data: The raw result data from the source job.
            user_id: Optional user ID for ownership.

        Returns:
            GeneratedDocument with the artifact_id populated.
        """
        # Determine doc type from source artifact
        if source_artifact.artifact_type == ArtifactType.SYNTHESIS_OUTPUT:
            generated = await self.generate_from_research_result(
                source_result_data,
                doc_format=request.doc_format,
                include_metadata=request.include_metadata,
            )
        else:
            # Default to plan format
            generated = await self.generate_from_plan_result(
                source_result_data,
                doc_format=request.doc_format,
                include_metadata=request.include_metadata,
            )

        # Store as a new artifact
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
            metadata = ArtifactMetadata(
                artifact_type=ArtifactType.MARKDOWN_DOCUMENT,
                artifact_name=f"Documentation from {source_artifact.artifact_name}",
                description=f"Generated documentation from artifact {source_artifact.id}",
                filename=f"doc_{source_artifact.id}.md",
                mime_type="text/markdown",
            )

            stored = await self.storage.store_artifact(
                db=db,
                job_id=request.job_id or source_artifact.job_id,
                metadata=metadata,
                content=generated.content,
                user_id=user_id,
                workspace_id=request.workspace_id,
            )

            generated.artifact_id = stored.id

        return generated

    def compute_doc_diff(
        self,
        old_content: str,
        new_content: str,
        old_filename: str = "original.md",
        new_filename: str = "updated.md",
    ) -> tuple[str, int, int]:
        """Compute a unified diff between two document contents.

        Args:
            old_content: Original document content.
            new_content: New document content.
            old_filename: Filename for the original (for diff header).
            new_filename: Filename for the new version (for diff header).

        Returns:
            Tuple of (diff_string, lines_added, lines_removed).
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = list(
            unified_diff(
                old_lines,
                new_lines,
                fromfile=old_filename,
                tofile=new_filename,
                lineterm="\n",
            )
        )

        diff_str = "".join(diff_lines)

        # Count added and removed lines
        lines_added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        lines_removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

        return diff_str, lines_added, lines_removed

    def extract_source_artifact_id(self, doc_artifact: StoredArtifact) -> int | None:
        """Extract the source artifact ID from a doc artifact's description.

        Args:
            doc_artifact: The document artifact to parse.

        Returns:
            Source artifact ID if found, None otherwise.
        """
        if not doc_artifact.description:
            return None

        # Description format: "Generated documentation from artifact {id}"
        match = re.search(r"from artifact (\d+)", doc_artifact.description)
        if match:
            return int(match.group(1))

        return None

    async def suggest_doc_update(
        self,
        db: AsyncSession,
        existing_doc: StoredArtifact,
        updated_source_artifact: StoredArtifact,
        updated_result_data: dict[str, Any],
        doc_format: str = "markdown",
        include_metadata: bool = True,
    ) -> DocUpdateSuggestion | None:
        """Generate an update suggestion for an existing document.

        When a source artifact changes and a document was previously generated
        from it, this method generates a new version and creates a diff for
        HITL approval.

        Args:
            db: Database session for loading the existing doc content.
            existing_doc: The existing document artifact.
            updated_source_artifact: The updated source artifact.
            updated_result_data: The raw result data from the updated source.
            doc_format: Output format for the new doc.
            include_metadata: Whether to include metadata in the new doc.

        Returns:
            DocUpdateSuggestion if there are changes, None if content is identical.
        """
        # Load existing doc content
        existing_result = await self.storage.get_artifact_content(db, existing_doc.id)
        if not existing_result:
            logger.warning(f"Could not load content for doc artifact {existing_doc.id}")
            return None

        _, old_content = existing_result

        # Ensure old_content is a string (convert from bytes if needed)
        if isinstance(old_content, bytes):
            old_content = old_content.decode("utf-8")

        # Generate new document from updated source
        if updated_source_artifact.artifact_type == ArtifactType.SYNTHESIS_OUTPUT:
            new_doc = await self.generate_from_research_result(
                updated_result_data,
                doc_format=doc_format,
                include_metadata=include_metadata,
            )
        else:
            new_doc = await self.generate_from_plan_result(
                updated_result_data,
                doc_format=doc_format,
                include_metadata=include_metadata,
            )

        new_content = new_doc.content

        # Compute diff
        diff_str, lines_added, lines_removed = self.compute_doc_diff(
            old_content,
            new_content,
            old_filename=f"doc_{existing_doc.id}.md",
            new_filename=f"doc_{existing_doc.id}_updated.md",
        )

        # Check if there are actual changes
        has_changes = old_content != new_content

        if not has_changes:
            logger.info(f"No changes detected for doc artifact {existing_doc.id}")
            return None

        source_id = self.extract_source_artifact_id(existing_doc) or updated_source_artifact.id

        return DocUpdateSuggestion(
            existing_doc_artifact_id=existing_doc.id,
            source_artifact_id=source_id,
            new_content=new_content,
            diff=diff_str,
            has_changes=has_changes,
            lines_added=lines_added,
            lines_removed=lines_removed,
        )

    async def find_docs_for_source(
        self,
        db: AsyncSession,
        source_artifact_id: int,
    ) -> list[StoredArtifact]:
        """Find all document artifacts generated from a specific source artifact.

        Args:
            db: Database session.
            source_artifact_id: The source artifact ID to search for.

        Returns:
            List of document artifacts that were generated from the source.
        """
        from sqlalchemy import select

        from app.models.artifact import ArtifactType, JobArtifact

        # Search for docs with descriptions containing the source artifact ID
        result = await db.execute(
            select(JobArtifact)
            .where(
                JobArtifact.artifact_type == ArtifactType.MARKDOWN_DOCUMENT.value,
                JobArtifact.description.contains(f"from artifact {source_artifact_id}"),
            )
            .order_by(JobArtifact.created_at.desc())
        )

        artifacts = result.scalars().all()
        return [StoredArtifact.from_model(a) for a in artifacts]

    async def apply_doc_update(
        self,
        db: AsyncSession,
        suggestion: DocUpdateSuggestion,
        user_id: str | None = None,
    ) -> StoredArtifact:
        """Apply an approved document update suggestion.

        Args:
            db: Database session.
            suggestion: The approved update suggestion.
            user_id: Optional user ID for ownership.

        Returns:
            The updated stored artifact.
        """
        from sqlalchemy import select

        from app.models.artifact import JobArtifact

        # Get the existing artifact
        result = await db.execute(
            select(JobArtifact).where(JobArtifact.id == suggestion.existing_doc_artifact_id)
        )
        artifact = result.scalar_one_or_none()

        if not artifact:
            raise ValueError(f"Document artifact {suggestion.existing_doc_artifact_id} not found")

        # Update the artifact with new content
        size_bytes = len(suggestion.new_content.encode("utf-8"))

        # Decide storage strategy based on size
        if size_bytes <= self.storage.inline_threshold:
            artifact.inline_data = suggestion.new_content
            artifact.storage_path = None
        else:
            # Store as file
            temp_filename = artifact.filename or f"doc_{artifact.id}.md"
            storage_path = self.storage._get_storage_path(
                artifact.job_id, artifact.id, temp_filename
            )
            content_bytes = suggestion.new_content.encode("utf-8")
            storage_path = await self.storage._file_storage.store(
                user_id=user_id or "system",
                attachment_id=None,
                filename=temp_filename,
                content=content_bytes,
                mime_type="text/markdown",
            )
            artifact.storage_path = storage_path
            artifact.inline_data = None

        artifact.size_bytes = size_bytes
        artifact.updated_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(artifact)

        logger.info(
            f"Applied doc update to artifact {artifact.id}: "
            f"{suggestion.lines_added} additions, {suggestion.lines_removed} deletions"
        )

        return StoredArtifact.from_model(artifact)

    def _format_plan_as_markdown(
        self,
        plan_metadata: dict[str, Any],
        task_dag: dict[str, Any],
        execution_order: list[list[str]],
        include_metadata: bool,
        source_job_id: str | None,
    ) -> str:
        """Format a plan result as markdown."""
        lines = []

        # Title
        goal = plan_metadata.get("goal", "Untitled Plan")
        lines.append(f"# Plan: {goal}\n")

        # Metadata
        if include_metadata:
            lines.append("## Metadata\n")
            if source_job_id:
                lines.append(f"- **Job ID**: `{source_job_id}`\n")
            lines.append(f"- **Generated**: `{datetime.now(UTC).isoformat()}`\n")
            lines.append("")

        # Approach
        approach = plan_metadata.get("approach", "")
        if approach:
            lines.append("## Approach\n")
            lines.append(f"{approach}\n")
            lines.append("")

        # Estimated Effort
        estimated_effort = plan_metadata.get("estimated_total_effort")
        if estimated_effort:
            lines.append(f"**Estimated Effort**: {estimated_effort}\n")
            lines.append("")

        # Assumptions
        assumptions = plan_metadata.get("assumptions", [])
        if assumptions:
            lines.append("### Assumptions\n")
            for assumption in assumptions:
                lines.append(f"- {assumption}\n")
            lines.append("")

        # Risks
        risks = plan_metadata.get("risks", [])
        if risks:
            lines.append("### Risks\n")
            for risk in risks:
                lines.append(f"- {risk}\n")
            lines.append("")

        # Tasks
        tasks = task_dag.get("tasks", [])
        if tasks:
            lines.append("## Tasks\n")
            for task in tasks:
                title = task.get("title", "Untitled Task")
                description = task.get("description", "")
                priority = task.get("priority", "medium")
                effort = task.get("estimated_effort")
                task_id = task.get("id", "")

                lines.append(f"### {title}\n")
                if task_id:
                    lines.append(f"**ID**: `{task_id}`  \n")
                lines.append(f"**Priority**: {priority}  \n")
                if effort:
                    lines.append(f"**Estimated Effort**: {effort}  \n")
                if description:
                    lines.append(f"\n{description}\n")
                lines.append("")

            # Execution order
            if execution_order:
                lines.append("## Execution Order\n")
                lines.append("Tasks can be executed in the following parallel layers:\n")
                for i, layer in enumerate(execution_order, 1):
                    lines.append(f"### Layer {i}\n")
                    for task_id in layer:
                        # Find task title
                        task_title = next(
                            (t.get("title", task_id) for t in tasks if t.get("id") == task_id),
                            task_id,
                        )
                        lines.append(f"- `{task_id}`: {task_title}\n")
                    lines.append("")

        return "".join(lines)

    def _format_plan_as_html(
        self,
        plan_metadata: dict[str, Any],
        task_dag: dict[str, Any],
        execution_order: list[list[str]],
        include_metadata: bool,
        source_job_id: str | None,
    ) -> str:
        """Format a plan result as HTML."""
        # For simplicity, convert markdown to HTML-ish format
        # A production version might use a proper markdown library
        md_content = self._format_plan_as_markdown(
            plan_metadata, task_dag, execution_order, include_metadata, source_job_id
        )

        # Basic markdown to HTML conversion
        html = md_content.replace("## ", "</h2><h2>").replace("# ", "</h1><h1>")
        html = html.replace("### ", "</h3><h3>").replace("**", "<strong>").replace("**", "</strong>")
        html = html.replace("`", "<code>").replace("`", "</code>")
        html = f"<html><body><h1>{html}</body></html>"

        return html

    def _format_plan_as_text(
        self,
        plan_metadata: dict[str, Any],
        task_dag: dict[str, Any],
        execution_order: list[list[str]],
        include_metadata: bool,
        source_job_id: str | None,
    ) -> str:
        """Format a plan result as plain text."""
        lines = []

        goal = plan_metadata.get("goal", "Untitled Plan")
        lines.append(f"PLAN: {goal}")
        lines.append("=" * len(f"PLAN: {goal}"))
        lines.append("")

        if include_metadata:
            lines.append("METADATA")
            lines.append("-" * 8)
            if source_job_id:
                lines.append(f"Job ID: {source_job_id}")
            lines.append(f"Generated: {datetime.now(UTC).isoformat()}")
            lines.append("")

        approach = plan_metadata.get("approach", "")
        if approach:
            lines.append("APPROACH")
            lines.append("-" * 8)
            lines.append(approach)
            lines.append("")

        tasks = task_dag.get("tasks", [])
        if tasks:
            lines.append("TASKS")
            lines.append("-" * 5)
            for task in tasks:
                title = task.get("title", "Untitled Task")
                description = task.get("description", "")
                priority = task.get("priority", "medium")
                lines.append(f"[{priority.upper()}] {title}")
                if description:
                    lines.append(f"  {description}")
                lines.append("")

        return "\n".join(lines)

    def _format_research_as_markdown(
        self,
        query: str,
        perspectives: list[dict[str, Any]],
        judge_synthesis: dict[str, Any],
        include_metadata: bool,
        source_job_id: str | None,
    ) -> str:
        """Format a research result as markdown."""
        lines = []

        lines.append(f"# Research Report: {query}\n")

        if include_metadata:
            lines.append("## Metadata\n")
            if source_job_id:
                lines.append(f"- **Job ID**: `{source_job_id}`\n")
            lines.append(f"- **Generated**: `{datetime.now(UTC).isoformat()}`\n")
            lines.append("")

        # Perspectives
        if perspectives:
            lines.append("## Perspectives\n")
            for persp in perspectives:
                name = persp.get("name", persp.get("display_name", "Unknown"))
                analysis = persp.get("analysis", "")
                lines.append(f"### {name.capitalize()}\n")
                lines.append(f"{analysis}\n")
                lines.append("")

        # Judge Synthesis
        if judge_synthesis:
            lines.append("## Synthesis\n")
            overall_assessment = judge_synthesis.get("overall_assessment", "")
            if overall_assessment:
                lines.append(f"{overall_assessment}\n")
                lines.append("")

            recommendations = judge_synthesis.get("recommendations", [])
            if recommendations:
                lines.append("### Recommendations\n")
                for rec in recommendations:
                    lines.append(f"- {rec}\n")
                lines.append("")

        return "".join(lines)

    def _format_research_as_html(
        self,
        query: str,
        perspectives: list[dict[str, Any]],
        judge_synthesis: dict[str, Any],
        include_metadata: bool,
        source_job_id: str | None,
    ) -> str:
        """Format a research result as HTML."""
        md_content = self._format_research_as_markdown(
            query, perspectives, judge_synthesis, include_metadata, source_job_id
        )

        # Basic markdown to HTML conversion
        html = md_content.replace("## ", "</h2><h2>").replace("# ", "</h1><h1>")
        html = html.replace("### ", "</h3><h3>").replace("**", "<strong>").replace("**", "</strong>")
        html = html.replace("`", "<code>").replace("`", "</code>")
        html = f"<html><body><h1>{html}</body></html>"

        return html

    def _format_research_as_text(
        self,
        query: str,
        perspectives: list[dict[str, Any]],
        judge_synthesis: dict[str, Any],
        include_metadata: bool,
        source_job_id: str | None,
    ) -> str:
        """Format a research result as plain text."""
        lines = []

        lines.append(f"RESEARCH REPORT: {query}")
        lines.append("=" * (len(f"RESEARCH REPORT: {query}")))
        lines.append("")

        if perspectives:
            lines.append("PERSPECTIVES")
            lines.append("-" * 12)
            for persp in perspectives:
                name = persp.get("name", persp.get("display_name", "Unknown"))
                analysis = persp.get("analysis", "")
                lines.append(f"[{name.upper()}]")
                lines.append(analysis)
                lines.append("")

        return "\n".join(lines)


# Singleton instance
_doc_service: DocGenerationService | None = None


def get_doc_service() -> DocGenerationService:
    """Get the singleton doc generation service.

    Returns:
        DocGenerationService instance.
    """
    global _doc_service
    if _doc_service is None:
        _doc_service = DocGenerationService()
    return _doc_service
