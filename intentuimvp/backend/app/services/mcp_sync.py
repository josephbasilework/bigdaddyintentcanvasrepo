"""Multi-MCP Task DAG synchronization helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.capability_registry import CapabilityRegistry, CapabilityType
from app.mcp.client import MCPClient
from app.mcp.manifest import SecurityCategory
from app.models.node import Node
from app.models.turn import TurnActor, TurnType
from app.services.turns import log_turn_with_session_id_async, resolve_session_id_async

TaskStatus = Literal["pending", "in_progress", "completed", "blocked"]
ConflictResolutionPolicy = Literal["prefer_local", "prefer_external", "newest"]

DAG_METADATA_KEYS = (
    "task_dag",
    "taskDag",
    "dag",
    "dag_data",
    "dagData",
)


@dataclass
class TaskStatusChange:
    task_id: str
    prev_status: TaskStatus | None
    next_status: TaskStatus
    task: dict[str, Any]


@dataclass
class SyncAdapterResult:
    adapter: str
    success: bool
    skipped: bool = False
    requires_confirmation: bool = False
    pending_actions: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    updated_task_ids: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "success": self.success,
            "skipped": self.skipped,
            "requires_confirmation": self.requires_confirmation,
            "pending_actions": self.pending_actions or None,
            "errors": self.errors or None,
            "updated_task_ids": self.updated_task_ids,
        }


@dataclass
class TaskDagSyncOutcome:
    updated_metadata: dict[str, Any] | None
    results: list[SyncAdapterResult] = field(default_factory=list)
    pending_actions: list[dict[str, Any]] = field(default_factory=list)
    requires_confirmation: bool = False
    next_task: dict[str, Any] | None = None
    conflicts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExternalTaskUpdate:
    task_id: str
    status: TaskStatus
    updated_at: datetime | None = None
    source: str | None = None
    title: str | None = None


class BaseSyncAdapter:
    name = "adapter"

    async def sync_task_completions(
        self,
        *,
        client: MCPClient,
        completed_tasks: list[TaskStatusChange],
        dag: dict[str, Any],
        metadata: dict[str, Any],
        initiated_by: str,
    ) -> SyncAdapterResult:
        raise NotImplementedError


class CalendarSyncAdapter(BaseSyncAdapter):
    name = "calendar"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def sync_task_completions(
        self,
        *,
        client: MCPClient,
        completed_tasks: list[TaskStatusChange],
        dag: dict[str, Any],
        metadata: dict[str, Any],
        initiated_by: str,
    ) -> SyncAdapterResult:
        config = _extract_adapter_config(metadata, "calendar")
        tool_name = _normalize_text(
            config.get("tool_name")
            or config.get("toolName")
            or config.get("calendar_tool")
        ) or "calendar_update"
        server_id = _normalize_text(config.get("server_id") or config.get("serverId"))

        tool_info = await client.get_tool_info(tool_name)
        if tool_info is None:
            return SyncAdapterResult(
                adapter=self.name,
                success=False,
                skipped=True,
                errors=[f"Calendar tool '{tool_name}' not available"],
            )

        pending_actions: list[dict[str, Any]] = []
        errors: list[str] = []
        updated_task_ids: list[str] = []

        for change in completed_tasks:
            task = change.task
            task_id = change.task_id
            event_id = _normalize_text(
                task.get("calendar_event_id")
                or task.get("calendarEventId")
                or task.get("event_id")
            )
            if not event_id:
                continue

            summary = _normalize_text(task.get("title") or task.get("summary"))
            if summary and not summary.lstrip().startswith(("✅", "✔", "[x]")):
                summary = f"✅ {summary}"
            description = _normalize_text(task.get("description"))
            calendar_id = _extract_calendar_id(task, config)

            args: dict[str, Any] = {"event_id": event_id}
            if calendar_id:
                args["calendar_id"] = calendar_id
            if summary:
                args["summary"] = summary
            if description:
                args["description"] = description

            result = await client.call_tool(
                tool_name=tool_name,
                arguments=args,
                initiated_by=initiated_by,
                server_id=server_id,
            )

            if result.required_confirmation:
                pending_actions.append(
                    {
                        "adapter": self.name,
                        "task_id": task_id,
                        "tool_name": tool_name,
                        "arguments": args,
                        "preview": result.preview,
                        "diff": result.diff,
                    }
                )
                continue

            if not result.success:
                errors.append(result.error or f"Calendar update failed for {task_id}")
                continue

            updated_task_ids.append(task_id)

        requires_confirmation = bool(pending_actions)
        success = not errors and not requires_confirmation

        return SyncAdapterResult(
            adapter=self.name,
            success=success,
            requires_confirmation=requires_confirmation,
            pending_actions=pending_actions,
            errors=errors,
            updated_task_ids=updated_task_ids,
        )


class DocumentSyncAdapter(BaseSyncAdapter):
    name = "document"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def sync_task_completions(
        self,
        *,
        client: MCPClient,
        completed_tasks: list[TaskStatusChange],
        dag: dict[str, Any],
        metadata: dict[str, Any],
        initiated_by: str,
    ) -> SyncAdapterResult:
        config = _extract_adapter_config(metadata, "document")
        tool_name, server_id = await _resolve_document_tool(self._session, config)

        if not tool_name:
            return SyncAdapterResult(
                adapter=self.name,
                success=False,
                skipped=True,
                errors=["No document tool available for checkbox updates"],
            )

        tool_info = await client.get_tool_info(tool_name)
        schema_props = None
        if tool_info and isinstance(tool_info.get("input_schema"), dict):
            schema_props = tool_info["input_schema"].get("properties")

        pending_actions: list[dict[str, Any]] = []
        errors: list[str] = []
        updated_task_ids: list[str] = []

        for change in completed_tasks:
            task = change.task
            task_id = change.task_id
            checkbox_id = _normalize_text(
                task.get("doc_checkbox_id")
                or task.get("docCheckboxId")
                or task.get("checkbox_id")
                or task.get("checkboxId")
            )
            if not checkbox_id:
                continue

            document_id = _normalize_text(
                task.get("document_id")
                or task.get("doc_document_id")
                or task.get("docDocumentId")
                or config.get("document_id")
                or config.get("documentId")
                or config.get("doc_id")
                or config.get("docId")
            )

            canonical_args = {
                "document_id": document_id,
                "checkbox_id": checkbox_id,
                "checked": True,
                "task_id": task_id,
                "title": _normalize_text(task.get("title")),
                "status": "completed",
            }
            args = _build_args_for_schema(schema_props, canonical_args)
            if not args:
                continue

            result = await client.call_tool(
                tool_name=tool_name,
                arguments=args,
                initiated_by=initiated_by,
                server_id=server_id,
            )

            if result.required_confirmation:
                pending_actions.append(
                    {
                        "adapter": self.name,
                        "task_id": task_id,
                        "tool_name": tool_name,
                        "arguments": args,
                        "preview": result.preview,
                        "diff": result.diff,
                    }
                )
                continue

            if not result.success:
                errors.append(result.error or f"Document update failed for {task_id}")
                continue

            updated_task_ids.append(task_id)

        requires_confirmation = bool(pending_actions)
        success = not errors and not requires_confirmation

        return SyncAdapterResult(
            adapter=self.name,
            success=success,
            requires_confirmation=requires_confirmation,
            pending_actions=pending_actions,
            errors=errors,
            updated_task_ids=updated_task_ids,
        )


class TaskDagSyncService:
    def __init__(self, session: AsyncSession, adapters: list[BaseSyncAdapter] | None = None) -> None:
        self._session = session
        self._adapters = adapters or [
            CalendarSyncAdapter(session),
            DocumentSyncAdapter(session),
        ]

    async def sync_task_dag_update(
        self,
        *,
        node: Node,
        prev_metadata: dict[str, Any] | None,
        next_metadata: dict[str, Any] | None,
        initiated_by: str,
    ) -> TaskDagSyncOutcome:
        if not next_metadata or node.type != "dag":
            return TaskDagSyncOutcome(updated_metadata=None)

        prev_metadata = prev_metadata or {}
        next_metadata = next_metadata or {}

        prev_dag = extract_task_dag(prev_metadata)
        next_dag = extract_task_dag(next_metadata)
        if not prev_dag or not next_dag:
            return TaskDagSyncOutcome(updated_metadata=None)

        prev_tasks = _extract_tasks(prev_dag)
        next_tasks = _extract_tasks(next_dag)
        changes = compute_task_status_changes(prev_tasks, next_tasks)
        if not changes:
            return TaskDagSyncOutcome(updated_metadata=None)

        completed_changes = [c for c in changes if c.next_status == "completed"]
        if not completed_changes:
            updated_dag = _apply_status_updates(next_dag, changes, source="local")
            updated_metadata = _apply_dag_to_metadata(next_metadata, updated_dag)
            return TaskDagSyncOutcome(updated_metadata=updated_metadata)

        updated_dag = _apply_status_updates(next_dag, changes, source="local")
        updated_metadata = _apply_dag_to_metadata(next_metadata, updated_dag)

        client = MCPClient(self._session)
        await client.initialize()
        try:
            results: list[SyncAdapterResult] = []
            pending_actions: list[dict[str, Any]] = []
            requires_confirmation = False

            for adapter in self._adapters:
                result = await adapter.sync_task_completions(
                    client=client,
                    completed_tasks=completed_changes,
                    dag=updated_dag,
                    metadata=updated_metadata,
                    initiated_by=initiated_by,
                )
                results.append(result)
                pending_actions.extend(result.pending_actions)
                requires_confirmation = requires_confirmation or result.requires_confirmation

            next_task = select_next_ready_task(updated_dag)
            sync_payload: dict[str, Any] = {
                "last_synced_at": datetime.now(UTC).isoformat(),
                "last_completed_task_ids": [c.task_id for c in completed_changes],
                "next_task": next_task,
                "pending_actions": pending_actions or None,
                "results": [r.to_payload() for r in results],
            }

            updated_metadata = _merge_sync_metadata(updated_metadata, sync_payload)

            return TaskDagSyncOutcome(
                updated_metadata=updated_metadata,
                results=results,
                pending_actions=pending_actions,
                requires_confirmation=requires_confirmation,
                next_task=next_task,
            )
        finally:
            await client.shutdown()

    async def apply_external_updates(
        self,
        *,
        node: Node,
        metadata: dict[str, Any] | None,
        updates: list[ExternalTaskUpdate],
        policy: ConflictResolutionPolicy = "newest",
        source: str | None = None,
    ) -> TaskDagSyncOutcome:
        if not metadata or node.type != "dag" or not updates:
            return TaskDagSyncOutcome(updated_metadata=None)

        dag = extract_task_dag(metadata)
        if not dag:
            return TaskDagSyncOutcome(updated_metadata=None)

        updated_dag, conflicts, changed = reconcile_external_task_updates(
            dag, updates, policy=policy, source=source
        )
        if not changed and not conflicts:
            return TaskDagSyncOutcome(updated_metadata=None, conflicts=conflicts)

        updated_metadata = _apply_dag_to_metadata(metadata, updated_dag)
        next_task = select_next_ready_task(updated_dag)
        sync_payload = {
            "last_external_update_at": datetime.now(UTC).isoformat(),
            "next_task": next_task,
            "conflicts": conflicts or None,
        }
        updated_metadata = _merge_sync_metadata(updated_metadata, sync_payload)

        return TaskDagSyncOutcome(
            updated_metadata=updated_metadata,
            next_task=next_task,
            conflicts=conflicts,
        )

    async def log_sync_turn(
        self,
        *,
        node: Node,
        user_id: str,
        outcome: TaskDagSyncOutcome,
        summary_prefix: str = "Task DAG sync",
    ) -> None:
        if not outcome or not (outcome.results or outcome.next_task or outcome.conflicts):
            return

        session_id = await resolve_session_id_async(
            self._session,
            user_id=user_id,
            workspace_id=node.canvas_id,
        )
        if not session_id:
            return

        summary_parts: list[str] = [summary_prefix]
        if outcome.next_task and isinstance(outcome.next_task, dict):
            title = _normalize_text(outcome.next_task.get("title"))
            if title:
                summary_parts.append(f"Next task: {title}")

        await log_turn_with_session_id_async(
            self._session,
            session_id=session_id,
            actor=TurnActor.SYSTEM,
            turn_type=TurnType.SYSTEM_MESSAGE,
            summary=" · ".join(summary_parts),
            payload={
                "results": [r.to_payload() for r in outcome.results],
                "pending_actions": outcome.pending_actions or None,
                "next_task": outcome.next_task,
                "conflicts": outcome.conflicts or None,
            },
            related_node_id=node.id,
        )


# -----------------------------------------------------------------------------
# Pure helper functions (unit-test friendly)
# -----------------------------------------------------------------------------

def extract_task_dag(metadata: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None

    for key in DAG_METADATA_KEYS:
        candidate = metadata.get(key)
        if isinstance(candidate, dict) and isinstance(candidate.get("tasks"), list):
            return candidate

    return None


def compute_task_status_changes(
    prev_tasks: Iterable[dict[str, Any]],
    next_tasks: Iterable[dict[str, Any]],
) -> list[TaskStatusChange]:
    prev_by_id: dict[str, dict[str, Any]] = {}
    for task in prev_tasks:
        task_id = _normalize_text(task.get("id") or task.get("task_id") or task.get("taskId"))
        if task_id:
            prev_by_id[task_id] = task

    changes: list[TaskStatusChange] = []
    for task in next_tasks:
        task_id = _normalize_text(task.get("id") or task.get("task_id") or task.get("taskId"))
        if not task_id:
            continue
        next_status = _normalize_status(task.get("status"))
        if not next_status:
            continue
        prev_task = prev_by_id.get(task_id, {})
        prev_status = _normalize_status(prev_task.get("status"))
        if prev_status != next_status:
            changes.append(
                TaskStatusChange(
                    task_id=task_id,
                    prev_status=prev_status,
                    next_status=next_status,
                    task=task,
                )
            )
    return changes


def select_next_ready_task(dag: dict[str, Any]) -> dict[str, Any] | None:
    tasks = _extract_tasks(dag)
    dependencies = _extract_dependencies(dag)
    if not dependencies:
        for task in tasks:
            deps = task.get("dependencies")
            if isinstance(deps, list):
                for dep_id in deps:
                    normalized = _normalize_text(dep_id)
                    if normalized:
                        dependencies.append(
                            {
                                "task_id": task.get("id"),
                                "depends_on_task_id": normalized,
                            }
                        )
    if not tasks:
        return None

    tasks_by_id = {task.get("id"): task for task in tasks if task.get("id")}
    blockers_by_task: dict[str, list[str]] = {}
    for dep in dependencies:
        task_id = dep.get("task_id")
        depends_on = dep.get("depends_on_task_id")
        if not task_id or not depends_on:
            continue
        blockers_by_task.setdefault(task_id, []).append(depends_on)

    for task in tasks:
        task_id = task.get("id")
        if not task_id:
            continue
        status = _normalize_status(task.get("status"))
        if status != "pending":
            continue
        blockers = blockers_by_task.get(task_id, [])
        if not blockers:
            return {
                "id": task_id,
                "title": task.get("title"),
                "status": status,
            }
        if all(
            _normalize_status(tasks_by_id.get(blocker_id, {}).get("status"))
            == "completed"
            for blocker_id in blockers
        ):
            return {
                "id": task_id,
                "title": task.get("title"),
                "status": status,
            }

    return None


def reconcile_external_task_updates(
    dag: dict[str, Any],
    updates: Iterable[ExternalTaskUpdate],
    *,
    policy: ConflictResolutionPolicy = "newest",
    source: str | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    tasks = _extract_tasks(dag)
    if not tasks:
        return dag, [], False

    now = now or datetime.now(UTC)
    updates_list = list(updates)
    updated_tasks: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    did_change = False

    for task in tasks:
        task_id = task.get("id")
        if not task_id:
            updated_tasks.append(task)
            continue
        update = next((u for u in updates_list if u.task_id == task_id), None)
        if update is None:
            updated_tasks.append(task)
            continue
        local_status = _normalize_status(task.get("status"))
        if local_status == update.status:
            updated_tasks.append(task)
            continue

        resolution = _resolve_conflict(
            policy,
            local_status,
            update.status,
            _parse_timestamp(task.get("status_updated_at") or task.get("statusUpdatedAt")),
            update.updated_at,
        )
        if resolution == "external":
            updated_task = dict(task)
            updated_task["status"] = update.status
            updated_task["status_updated_at"] = (
                update.updated_at or now
            ).isoformat()
            updated_task["status_updated_by"] = update.source or source or "external"
            updated_tasks.append(updated_task)
            did_change = True
        else:
            updated_tasks.append(task)
            conflicts.append(
                {
                    "task_id": task_id,
                    "local_status": local_status,
                    "external_status": update.status,
                    "resolution": resolution,
                }
            )

    updated_dag = dict(dag)
    updated_dag["tasks"] = updated_tasks
    return updated_dag, conflicts, did_change


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------

def _normalize_text(value: Any) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
    return None


def _normalize_status(value: Any) -> TaskStatus | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("-", "_")
    alias_map = {
        "done": "completed",
        "complete": "completed",
    }
    normalized = alias_map.get(normalized, normalized)
    if normalized in {"pending", "in_progress", "completed", "blocked"}:
        return normalized  # type: ignore[return-value]
    return None


def _extract_tasks(dag: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = dag.get("tasks")
    if isinstance(tasks, list):
        normalized: list[dict[str, Any]] = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = _normalize_text(task.get("id") or task.get("task_id") or task.get("taskId"))
            if not task_id:
                continue
            normalized_task = dict(task)
            normalized_task["id"] = task_id
            normalized.append(normalized_task)
        return normalized
    return []


def _extract_dependencies(dag: dict[str, Any]) -> list[dict[str, Any]]:
    dependencies = dag.get("dependencies")
    if not isinstance(dependencies, list):
        return []

    normalized: list[dict[str, Any]] = []
    for dep in dependencies:
        if not isinstance(dep, dict):
            continue
        task_id = _normalize_text(dep.get("task_id") or dep.get("taskId"))
        depends_on = _normalize_text(
            dep.get("depends_on_task_id")
            or dep.get("dependsOnTaskId")
            or dep.get("depends_on")
            or dep.get("dependsOn")
        )
        if not task_id or not depends_on:
            continue
        normalized.append(
            {
                "task_id": task_id,
                "depends_on_task_id": depends_on,
                "type": dep.get("type") or dep.get("dependency_type"),
            }
        )
    return normalized


def _apply_status_updates(
    dag: dict[str, Any],
    changes: list[TaskStatusChange],
    *,
    source: str,
) -> dict[str, Any]:
    if not changes:
        return dag

    now = datetime.now(UTC).isoformat()
    change_map = {change.task_id: change for change in changes}
    updated_tasks: list[dict[str, Any]] = []

    for task in _extract_tasks(dag):
        task_id = _normalize_text(task.get("id") or task.get("task_id") or task.get("taskId"))
        if not task_id or task_id not in change_map:
            updated_tasks.append(task)
            continue
        updated_task = dict(task)
        updated_task["status"] = change_map[task_id].next_status
        updated_task["status_updated_at"] = now
        updated_task["status_updated_by"] = source
        updated_tasks.append(updated_task)

    updated_dag = dict(dag)
    updated_dag["tasks"] = updated_tasks
    return updated_dag


def _apply_dag_to_metadata(metadata: dict[str, Any], dag: dict[str, Any]) -> dict[str, Any]:
    updated = dict(metadata)
    updated["task_dag"] = dag
    for key in ("dag", "dag_data", "dagData", "taskDag"):
        if key in updated:
            updated[key] = dag
    return updated


def _merge_sync_metadata(metadata: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    updated = dict(metadata)
    existing = updated.get("mcp_sync")
    if not isinstance(existing, dict):
        existing = {}
    merged = {**existing, **payload}
    updated["mcp_sync"] = merged
    return updated


def _extract_adapter_config(metadata: dict[str, Any], adapter: str) -> dict[str, Any]:
    for key in ("mcp_sync", "mcpSync", "sync", "sync_state"):
        candidate = metadata.get(key)
        if isinstance(candidate, dict) and isinstance(candidate.get(adapter), dict):
            return candidate.get(adapter, {})
    for key in (f"{adapter}_sync", f"{adapter}Sync"):
        candidate = metadata.get(key)
        if isinstance(candidate, dict):
            return candidate
    return {}


def _extract_calendar_id(task: dict[str, Any], config: dict[str, Any]) -> str | None:
    suggestion = task.get("calendar_suggestion") or task.get("calendarSuggestion")
    suggestion_id = None
    if isinstance(suggestion, dict):
        suggestion_id = _normalize_text(
            suggestion.get("calendar_id") or suggestion.get("calendarId")
        )
    return (
        suggestion_id
        or _normalize_text(task.get("calendar_id") or task.get("calendarId"))
        or _normalize_text(config.get("calendar_id") or config.get("calendarId"))
        or "primary"
    )


def _build_args_for_schema(
    schema_props: dict[str, Any] | None,
    canonical_args: dict[str, Any],
) -> dict[str, Any]:
    if not canonical_args:
        return {}

    alias_map = {
        "document_id": ["document_id", "documentId", "doc_id", "docId"],
        "checkbox_id": ["checkbox_id", "checkboxId", "check_id", "checkId"],
        "checked": ["checked", "is_checked", "isChecked", "completed", "done"],
        "task_id": ["task_id", "taskId"],
        "title": ["title", "task_title", "taskTitle"],
        "status": ["status", "state"],
    }

    args: dict[str, Any] = {}
    for key, value in canonical_args.items():
        if value is None:
            continue
        candidates = alias_map.get(key, [key])
        selected_key = None
        if schema_props:
            for candidate in candidates:
                if candidate in schema_props:
                    selected_key = candidate
                    break
            if not selected_key:
                continue
        else:
            selected_key = candidates[0]
        args[selected_key] = value

    return args


async def _resolve_document_tool(
    session: AsyncSession,
    config: dict[str, Any],
) -> tuple[str | None, str | None]:
    tool_name = _normalize_text(
        config.get("tool_name")
        or config.get("toolName")
        or config.get("document_tool")
    )
    server_id = _normalize_text(config.get("server_id") or config.get("serverId"))
    if tool_name:
        return tool_name, server_id

    registry = CapabilityRegistry(session)
    capabilities = await registry.get_all_capabilities(include_disabled=True)
    doc_tools = [
        cap
        for cap in capabilities
        if cap.type == CapabilityType.TOOL
        and cap.category == SecurityCategory.DOCUMENT
        and cap.name
    ]
    if not doc_tools:
        return None, None

    preferred = next(
        (
            cap
            for cap in doc_tools
            if "checkbox" in cap.name.lower() or "check" in cap.name.lower()
        ),
        None,
    )
    selected = preferred or doc_tools[0]
    return selected.name, selected.server_id


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    return None


def _resolve_conflict(
    policy: ConflictResolutionPolicy,
    local_status: TaskStatus | None,
    external_status: TaskStatus,
    local_updated: datetime | None,
    external_updated: datetime | None,
) -> Literal["local", "external"]:
    if policy == "prefer_external":
        return "external"
    if policy == "prefer_local":
        return "local"

    # newest
    if external_updated and local_updated:
        return "external" if external_updated > local_updated else "local"
    if external_updated and not local_updated:
        return "external"
    return "local"
