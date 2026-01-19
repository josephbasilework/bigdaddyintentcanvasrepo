"""Deterministic hook matching and execution."""

from __future__ import annotations

import asyncio
import contextvars
import logging
import time
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from app.context.input_router import get_input_router
from app.context.models import ContextPayload
from app.database import AsyncSessionLocal, SessionLocal
from app.handlers import HandlerContext, get_handler_executor
from app.models.hook import Hook
from app.models.turn import Turn, TurnActor, TurnType
from app.repositories.hook_repo import AsyncHookRepository, HookRepository
from app.repositories.session_repo import AsyncSessionRepository
from app.services.events import resolve_event_type
from app.services.turns import log_turn_for_user_async, log_turn_for_user_sync

logger = logging.getLogger(__name__)

HOOK_TYPE_EVENT = "event"
HOOK_TYPE_SCHEDULE = "schedule"

SCHEDULE_TYPE_INTERVAL = "interval"
SCHEDULE_TYPE_CRON = "cron"
SCHEDULE_TYPE_DATE = "date"

SUPPORTED_SCHEDULE_TYPES = {SCHEDULE_TYPE_INTERVAL, SCHEDULE_TYPE_CRON, SCHEDULE_TYPE_DATE}

HOOK_TURN_TYPES = {TurnType.HOOK_FIRED, TurnType.HOOK_FAILED}

_HOOK_EXECUTION_STACK: contextvars.ContextVar[tuple[int, ...]] = contextvars.ContextVar(
    "hook_execution_stack", default=()
)


class _SafeFormatDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _normalize_action(action: dict[str, Any] | None) -> dict[str, Any]:
    return action or {}


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except ValueError:
            return None
    return None


def _parse_interval_trigger(trigger: Mapping[str, Any]) -> timedelta | None:
    fields = {
        "weeks": trigger.get("weeks"),
        "days": trigger.get("days"),
        "hours": trigger.get("hours"),
        "minutes": trigger.get("minutes"),
        "seconds": trigger.get("seconds"),
    }
    interval_seconds = trigger.get("interval_seconds") or trigger.get("intervalSeconds")
    if interval_seconds is not None:
        fields["seconds"] = interval_seconds

    clean: dict[str, float] = {}
    for key, value in fields.items():
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric <= 0:
            continue
        clean[key] = numeric

    if not clean:
        return None
    return timedelta(**clean)


def compute_next_run_at(
    *,
    schedule_type: str | None,
    trigger: Mapping[str, Any] | None,
    now: datetime,
    last_fired_at: datetime | None = None,
) -> datetime | None:
    if schedule_type not in SUPPORTED_SCHEDULE_TYPES or trigger is None:
        return None

    if schedule_type == SCHEDULE_TYPE_INTERVAL:
        delta = _parse_interval_trigger(trigger)
        if delta is None:
            return None
        start_at = _parse_datetime(trigger.get("start_at") or trigger.get("startAt"))
        base = last_fired_at or now
        if last_fired_at is None and start_at is not None and start_at > now:
            return start_at
        return base + delta

    if schedule_type == SCHEDULE_TYPE_DATE:
        run_at = _parse_datetime(trigger.get("run_at") or trigger.get("runAt"))
        if run_at is None:
            return None
        if last_fired_at is not None:
            return None
        return run_at

    cron_fields = {
        key: trigger.get(key)
        for key in [
            "year",
            "month",
            "day",
            "week",
            "day_of_week",
            "dayOfWeek",
            "hour",
            "minute",
            "second",
            "timezone",
        ]
        if trigger.get(key) is not None
    }
    if "dayOfWeek" in cron_fields and "day_of_week" not in cron_fields:
        cron_fields["day_of_week"] = cron_fields.pop("dayOfWeek")
    if not cron_fields:
        return None
    try:
        cron = CronTrigger(**cron_fields)
    except Exception:
        logger.warning("Invalid cron trigger fields", extra={"trigger": cron_fields})
        return None
    next_fire = cron.get_next_fire_time(last_fired_at, now)
    if next_fire is None:
        return None
    return next_fire.replace(tzinfo=None)


def _build_hook_context(
    *,
    hook: Hook,
    event_type: str | None,
    turn: Turn | None,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "hook_id": hook.id,
        "hookId": hook.id,
        "hook_name": hook.name,
        "hookName": hook.name,
    }
    if event_type:
        context["event_type"] = event_type
        context["eventType"] = event_type
    if turn is not None:
        context.update(
            {
                "turn_id": turn.id,
                "turnId": turn.id,
                "turn_type": getattr(turn.type, "value", str(turn.type)),
                "turnType": getattr(turn.type, "value", str(turn.type)),
                "actor": getattr(turn.actor, "value", str(turn.actor)),
                "session_id": turn.session_id,
                "sessionId": turn.session_id,
                "related_node_id": turn.related_node_id,
                "relatedNodeId": turn.related_node_id,
                "related_edge_id": turn.related_edge_id,
                "relatedEdgeId": turn.related_edge_id,
            }
        )
    if payload is not None:
        context["payload"] = payload
    return context


def _render_template(template: str, context: dict[str, Any]) -> str:
    try:
        return template.format_map(_SafeFormatDict(context))
    except Exception:
        return template


def _coerce_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value)
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return None


def _coerce_int_id(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _matches_trigger(
    hook: Hook,
    *,
    turn: Turn,
    payload: Mapping[str, Any],
) -> bool:
    trigger = hook.trigger or {}
    if not isinstance(trigger, Mapping):
        return True

    actor = trigger.get("actor")
    if actor and str(actor) != getattr(turn.actor, "value", str(turn.actor)):
        return False

    node_id = trigger.get("related_node_id") or trigger.get("relatedNodeId")
    if node_id is not None:
        expected = _coerce_id(node_id)
        actual = _coerce_id(turn.related_node_id) or _coerce_id(
            payload.get("node_id") or payload.get("nodeId")
        )
        if expected and expected != actual:
            return False

    edge_id = trigger.get("related_edge_id") or trigger.get("relatedEdgeId")
    if edge_id is not None:
        expected = _coerce_id(edge_id)
        actual = _coerce_id(turn.related_edge_id) or _coerce_id(
            payload.get("edge_id") or payload.get("edgeId")
        )
        if expected and expected != actual:
            return False

    for key, expected in trigger.items():
        if key in {
            "actor",
            "related_node_id",
            "relatedNodeId",
            "related_edge_id",
            "relatedEdgeId",
        }:
            continue
        if key not in payload:
            continue
        actual = payload.get(key)
        if actual != expected:
            return False

    return True


async def _execute_hook_action(
    hook: Hook,
    *,
    action: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    action = _normalize_action(action)
    action_type = (
        action.get("type")
        or action.get("action_type")
        or action.get("actionType")
        or "command"
    )

    if action_type == "command":
        command_template = (
            action.get("command")
            or action.get("text")
            or action.get("prompt")
            or ""
        )
        if not isinstance(command_template, str) or not command_template.strip():
            raise ValueError("Hook action missing command text")
        command_text = _render_template(command_template, context).strip()
        attachments = action.get("attachments")
        if attachments is None:
            attachments = []
        selection = action.get("selection")

        payload = ContextPayload(
            text=command_text,
            attachments=attachments,
            selection=selection,
        )
        router = get_input_router()
        decision = await router.route(
            payload,
            user_id=hook.user_id or "default_user",
            session_id=hook.session_id,
            workspace_id=hook.workspace_id,
        )
        executor = get_handler_executor()
        run_id = f"hook-{hook.id}-{int(time.time())}"
        result = await executor.execute(
            decision,
            correlation_id=run_id,
            context=HandlerContext(
                user_id=hook.user_id,
                session_id=hook.session_id,
                workspace_id=hook.workspace_id,
            ),
        )
        return {
            "handler": decision.handler,
            "command": command_text,
            "run_id": run_id,
            "result": result,
        }

    if action_type == "notification":
        title_template = action.get("title") or action.get("name") or "Notification"
        message_template = action.get("message") or action.get("text") or ""
        if not isinstance(message_template, str) or not message_template.strip():
            raise ValueError("Hook action missing notification message")
        title = (
            _render_template(title_template, context).strip()
            if isinstance(title_template, str)
            else "Notification"
        )
        message = _render_template(message_template, context).strip()
        level = action.get("level") if isinstance(action.get("level"), str) else "info"
        metadata = action.get("metadata") if isinstance(action.get("metadata"), dict) else {}
        if "duration" in action:
            metadata["duration"] = action.get("duration")
        if "actions" in action:
            metadata["actions"] = action.get("actions")
        if not metadata:
            metadata = None
        related_node = _coerce_int_id(
            action.get("related_node_id") or action.get("relatedNodeId")
        )
        if related_node is None:
            related_node = _coerce_int_id(
                context.get("related_node_id") or context.get("relatedNodeId")
            )
        related_edge = _coerce_int_id(
            action.get("related_edge_id") or action.get("relatedEdgeId")
        )
        if related_edge is None:
            related_edge = _coerce_int_id(
                context.get("related_edge_id") or context.get("relatedEdgeId")
            )
        workspace_id = _coerce_int_id(hook.workspace_id)

        from app.services.notifications import create_notification_async

        await create_notification_async(
            user_id=hook.user_id or "default_user",
            workspace_id=workspace_id,
            session_id=hook.session_id,
            level=level,
            title=title,
            message=message,
            source=action.get("source") if isinstance(action.get("source"), str) else "hook",
            related_node_id=related_node,
            related_edge_id=related_edge,
            metadata=metadata,
        )
        return {
            "title": title,
            "message": message,
            "level": level,
        }

    raise ValueError(f"Unsupported hook action type: {action_type}")


async def _log_hook_turn_async(
    *,
    hook: Hook,
    turn_type: TurnType,
    summary: str,
    payload: dict[str, Any],
) -> None:
    async with AsyncSessionLocal() as db:
        await log_turn_for_user_async(
            db,
            user_id=hook.user_id,
            workspace_id=hook.workspace_id,
            session_id=hook.session_id,
            actor=TurnActor.SYSTEM,
            turn_type=turn_type,
            summary=summary,
            payload=payload,
        )


def _log_hook_turn_sync(
    *,
    hook: Hook,
    turn_type: TurnType,
    summary: str,
    payload: dict[str, Any],
) -> None:
    db = SessionLocal()
    try:
        log_turn_for_user_sync(
            db,
            user_id=hook.user_id,
            workspace_id=hook.workspace_id,
            session_id=hook.session_id,
            actor=TurnActor.SYSTEM,
            turn_type=turn_type,
            summary=summary,
            payload=payload,
        )
    finally:
        db.close()


async def _fire_hook_async(
    hook: Hook,
    *,
    event_type: str | None,
    turn: Turn | None,
    payload: dict[str, Any] | None,
) -> None:
    context = _build_hook_context(
        hook=hook,
        event_type=event_type,
        turn=turn,
        payload=payload,
    )
    summary = f"Hook fired: {hook.name}"
    await _log_hook_turn_async(
        hook=hook,
        turn_type=TurnType.HOOK_FIRED,
        summary=summary,
        payload={
            "hook_id": hook.id,
            "hook_name": hook.name,
            "hook_type": hook.hook_type,
            "schedule_type": hook.schedule_type,
            "event_type": event_type,
            "trigger": hook.trigger or {},
            "action": hook.action or {},
            "context": context,
        },
    )

    error_message: str | None = None
    token = _HOOK_EXECUTION_STACK.set((*_HOOK_EXECUTION_STACK.get(), hook.id))
    try:
        await _execute_hook_action(
            hook,
            action=hook.action or {},
            context=context,
        )
    except Exception as exc:  # pragma: no cover - logs error
        error_message = str(exc)
        logger.warning(
            "Hook action failed",
            extra={"hook_id": hook.id, "hook_name": hook.name},
            exc_info=True,
        )
    finally:
        _HOOK_EXECUTION_STACK.reset(token)

    if error_message:
        await _log_hook_turn_async(
            hook=hook,
            turn_type=TurnType.HOOK_FAILED,
            summary=f"Hook failed: {hook.name}",
            payload={
                "hook_id": hook.id,
                "hook_name": hook.name,
                "hook_type": hook.hook_type,
                "schedule_type": hook.schedule_type,
                "error": error_message,
                "event_type": event_type,
            },
        )

    async with AsyncSessionLocal() as db:
        repo = AsyncHookRepository(db)
        refreshed = await repo.get_hook(hook.id)
        if refreshed:
            refreshed.last_fired_at = datetime.utcnow()
            if refreshed.hook_type == HOOK_TYPE_SCHEDULE:
                refreshed.next_run_at = compute_next_run_at(
                    schedule_type=refreshed.schedule_type,
                    trigger=refreshed.trigger or {},
                    now=refreshed.last_fired_at,
                    last_fired_at=refreshed.last_fired_at,
                )
            await repo.update_hook(refreshed)


def _fire_hook_sync(
    hook: Hook,
    *,
    event_type: str | None,
    turn: Turn | None,
    payload: dict[str, Any] | None,
) -> None:
    context = _build_hook_context(
        hook=hook,
        event_type=event_type,
        turn=turn,
        payload=payload,
    )
    summary = f"Hook fired: {hook.name}"
    _log_hook_turn_sync(
        hook=hook,
        turn_type=TurnType.HOOK_FIRED,
        summary=summary,
        payload={
            "hook_id": hook.id,
            "hook_name": hook.name,
            "hook_type": hook.hook_type,
            "schedule_type": hook.schedule_type,
            "event_type": event_type,
            "trigger": hook.trigger or {},
            "action": hook.action or {},
            "context": context,
        },
    )

    error_message: str | None = None
    token = _HOOK_EXECUTION_STACK.set((*_HOOK_EXECUTION_STACK.get(), hook.id))
    try:
        asyncio.run(
            _execute_hook_action(
                hook,
                action=hook.action or {},
                context=context,
            )
        )
    except RuntimeError:
        error_message = "Hook action failed to execute"
    except Exception as exc:  # pragma: no cover - logging
        error_message = str(exc)
        logger.warning(
            "Hook action failed",
            extra={"hook_id": hook.id, "hook_name": hook.name},
            exc_info=True,
        )
    finally:
        _HOOK_EXECUTION_STACK.reset(token)

    if error_message:
        _log_hook_turn_sync(
            hook=hook,
            turn_type=TurnType.HOOK_FAILED,
            summary=f"Hook failed: {hook.name}",
            payload={
                "hook_id": hook.id,
                "hook_name": hook.name,
                "hook_type": hook.hook_type,
                "schedule_type": hook.schedule_type,
                "error": error_message,
                "event_type": event_type,
            },
        )

    db = SessionLocal()
    try:
        repo = HookRepository(db)
        refreshed = repo.get_hook(hook.id)
        if refreshed:
            refreshed.last_fired_at = datetime.utcnow()
            if refreshed.hook_type == HOOK_TYPE_SCHEDULE:
                refreshed.next_run_at = compute_next_run_at(
                    schedule_type=refreshed.schedule_type,
                    trigger=refreshed.trigger or {},
                    now=refreshed.last_fired_at,
                    last_fired_at=refreshed.last_fired_at,
                )
            repo.update_hook(refreshed)
    finally:
        db.close()


async def dispatch_event_hooks_async(turn: Turn) -> None:
    """Dispatch event-based hooks for a persisted turn."""
    if turn.type in HOOK_TURN_TYPES:
        return
    if _HOOK_EXECUTION_STACK.get():
        return

    payload = turn.get_payload()
    event_type = resolve_event_type(turn.type, turn.actor, payload)

    async with AsyncSessionLocal() as db:
        session_repo = AsyncSessionRepository(db)
        session = await session_repo.get_by_session_id(turn.session_id)
        user_id = session.user_id if session else None
        workspace_id = str(session.workspace_id) if session else None
        repo = AsyncHookRepository(db)
        hooks = await repo.list_event_hooks(
            event_type=event_type,
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=turn.session_id,
        )

    for hook in hooks:
        if not _matches_trigger(hook, turn=turn, payload=payload):
            continue
        await _fire_hook_async(
            hook,
            event_type=event_type,
            turn=turn,
            payload=payload,
        )


def dispatch_event_hooks_sync(turn: Turn) -> None:
    """Dispatch event-based hooks for a persisted turn (sync wrapper)."""
    if turn.type in HOOK_TURN_TYPES:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(dispatch_event_hooks_async(turn))
        return

    loop.create_task(dispatch_event_hooks_async(turn))


def run_due_scheduled_hooks() -> None:
    """Run scheduled hooks that are due."""
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        repo = HookRepository(db)
        hooks = repo.list_due_scheduled_hooks(now)
    finally:
        db.close()

    for hook in hooks:
        _fire_hook_sync(
            hook,
            event_type="schedule.due",
            turn=None,
            payload={"scheduled_for": hook.next_run_at.isoformat() if hook.next_run_at else None},
        )


def ensure_next_run_at(hook: Hook) -> Hook:
    """Ensure next_run_at is set for scheduled hooks."""
    if hook.hook_type != HOOK_TYPE_SCHEDULE:
        hook.next_run_at = None
        return hook
    now = datetime.utcnow()
    next_run = compute_next_run_at(
        schedule_type=hook.schedule_type,
        trigger=hook.trigger or {},
        now=now,
        last_fired_at=hook.last_fired_at,
    )
    hook.next_run_at = next_run
    return hook
