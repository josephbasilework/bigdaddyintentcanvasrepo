"""External state observation manager for dashboard subscriptions."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
import websockets

from app.database import AsyncSessionLocal
from app.mcp.client import MCPClient
from app.models.dashboard_subscription import DashboardSubscriptionTarget
from app.services.dashboard_updates import publish_dashboard_update

ExternalSourceType = Literal["api", "websocket", "mcp"]
ExternalStatus = Literal["idle", "connecting", "connected", "error"]

DEFAULT_POLL_INTERVAL_MS = 15000
MIN_POLL_INTERVAL_MS = 1000
DEFAULT_RECONNECT_DELAY_S = 5.0
MAX_PAYLOAD_BYTES = 512 * 1024
MAX_PREVIEW_CHARS = 4000


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = int(value)
        return value if value > 0 else default
    return default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return None


def _sanitize_string(value: str, max_chars: int = 2000) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[: max_chars - 3]}..."


def _sanitize_payload(value: Any, depth: int = 0) -> Any:
    if depth >= 4:
        return "[truncated]"
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str):
            return _sanitize_string(value, 2000)
        return value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return value.hex()
    if isinstance(value, list):
        return [_sanitize_payload(item, depth + 1) for item in value[:50]]
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in list(value.items())[:50]:
            sanitized[str(key)] = _sanitize_payload(item, depth + 1)
        return sanitized
    return _sanitize_string(str(value), 2000)


def _normalize_endpoint(endpoint: str | None, allowed_protocols: set[str]) -> str | None:
    if not endpoint:
        return None
    trimmed = endpoint.strip()
    if not trimmed:
        return None
    try:
        parsed = urlparse(trimmed)
    except ValueError:
        return None
    if parsed.scheme and parsed.scheme not in allowed_protocols:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    return trimmed


def _sanitize_source_id(raw: str, max_length: int = 120) -> str:
    if len(raw) <= max_length:
        return raw
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    keep = max_length - len(digest) - 3
    return f"{raw[:keep]}...{digest}"


@dataclass
class ExternalSourceConfig:
    type: ExternalSourceType
    endpoint: str | None = None
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS
    mcp_server_id: str | None = None
    mcp_tool_name: str | None = None
    mcp_args: dict[str, Any] | None = None
    allow_write: bool = False
    write_method: Literal["POST", "PUT", "PATCH"] = "POST"
    write_payload: dict[str, Any] | None = None

    def signature(self) -> str:
        payload = {
            "type": self.type,
            "endpoint": self.endpoint,
            "poll_interval_ms": self.poll_interval_ms,
            "mcp_server_id": self.mcp_server_id,
            "mcp_tool_name": self.mcp_tool_name,
            "mcp_args": self.mcp_args,
        }
        return json.dumps(payload, sort_keys=True, default=str)


def coerce_external_source_config(config: dict[str, Any]) -> ExternalSourceConfig | None:
    if not _is_record(config):
        return None

    type_candidate = _coerce_str(config.get("type")) or _coerce_str(
        config.get("sourceType")
    )
    if type_candidate not in {"api", "websocket", "mcp"}:
        return None

    endpoint = _coerce_str(config.get("endpoint")) or _coerce_str(config.get("url"))
    endpoint = endpoint or _coerce_str(config.get("source"))

    poll_interval_ms = _coerce_int(
        config.get("pollIntervalMs") or config.get("poll_interval_ms"),
        DEFAULT_POLL_INTERVAL_MS,
    )
    poll_interval_ms = max(poll_interval_ms, MIN_POLL_INTERVAL_MS)

    mcp_config = config.get("mcp") if _is_record(config.get("mcp")) else {}
    mcp_server_id = (
        _coerce_str(config.get("mcpServerId"))
        or _coerce_str(config.get("mcp_server_id"))
        or _coerce_str(mcp_config.get("serverId"))
        or _coerce_str(mcp_config.get("server_id"))
    )
    mcp_tool_name = (
        _coerce_str(config.get("mcpToolName"))
        or _coerce_str(config.get("mcp_tool_name"))
        or _coerce_str(mcp_config.get("toolName"))
        or _coerce_str(mcp_config.get("tool_name"))
    )
    mcp_args = (
        config.get("mcpArgs")
        if _is_record(config.get("mcpArgs"))
        else config.get("mcp_args")
        if _is_record(config.get("mcp_args"))
        else mcp_config.get("args")
        if _is_record(mcp_config.get("args"))
        else None
    )

    allow_write = _coerce_bool(
        config.get("allowWrite")
        if isinstance(config.get("allowWrite"), bool)
        else config.get("allow_write")
    )
    write_method = _coerce_str(config.get("writeMethod")) or _coerce_str(
        config.get("write_method")
    )
    if write_method not in {"POST", "PUT", "PATCH"}:
        write_method = "POST"
    write_payload = (
        config.get("writePayload")
        if _is_record(config.get("writePayload"))
        else config.get("write_payload")
        if _is_record(config.get("write_payload"))
        else None
    )

    return ExternalSourceConfig(
        type=type_candidate,
        endpoint=endpoint,
        poll_interval_ms=poll_interval_ms,
        mcp_server_id=mcp_server_id,
        mcp_tool_name=mcp_tool_name,
        mcp_args=mcp_args,
        allow_write=allow_write,
        write_method=write_method,
        write_payload=write_payload,
    )


def build_external_source_id(config: ExternalSourceConfig) -> str:
    if config.type == "mcp":
        server_id = config.mcp_server_id or "default"
        tool = config.mcp_tool_name or "tool"
        return _sanitize_source_id(f"mcp:{server_id}:{tool}")
    endpoint = config.endpoint or "endpoint"
    parsed = urlparse(endpoint)
    if parsed.scheme and parsed.netloc:
        sanitized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    else:
        sanitized = endpoint
    return _sanitize_source_id(sanitized)


def build_external_update_payload(
    *,
    status: ExternalStatus,
    payload: Any | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "status": status,
        "observed_at": datetime.now(UTC).isoformat(),
    }
    if payload is not None:
        data["payload"] = _sanitize_payload(payload)
    if error:
        data["error"] = _sanitize_string(error, MAX_PREVIEW_CHARS)
    return data


class ExternalUpdateBuffer:
    def __init__(self, publish_callback) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1)
        self._task: asyncio.Task | None = None
        self._last_hash: str | None = None
        self._publish = publish_callback

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def enqueue(self, update: dict[str, Any]) -> None:
        try:
            update_hash = hashlib.sha1(
                json.dumps(update, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
        except (TypeError, ValueError):
            update_hash = hashlib.sha1(str(update).encode("utf-8")).hexdigest()
        if update_hash == self._last_hash:
            return
        self._last_hash = update_hash
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await self._queue.put(update)

    async def _run(self) -> None:
        while True:
            update = await self._queue.get()
            try:
                await self._publish(update)
            except Exception:
                # Preserve the buffer loop even if a publish fails.
                continue


class ExternalSourceSubscription:
    def __init__(
        self,
        *,
        source_id: str,
        config: ExternalSourceConfig,
    ) -> None:
        self.source_id = source_id
        self.config = config
        self._canvas_refs: dict[int, int] = {}
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._buffer = ExternalUpdateBuffer(self._publish_update)
        self._status: ExternalStatus = "idle"
        self._last_error: str | None = None
        self._signature = config.signature()

    def add_canvas(self, canvas_id: int) -> None:
        self._canvas_refs[canvas_id] = self._canvas_refs.get(canvas_id, 0) + 1

    def remove_canvas(self, canvas_id: int) -> None:
        if canvas_id not in self._canvas_refs:
            return
        if self._canvas_refs[canvas_id] <= 1:
            self._canvas_refs.pop(canvas_id, None)
        else:
            self._canvas_refs[canvas_id] -= 1

    @property
    def canvas_ids(self) -> list[int]:
        return list(self._canvas_refs.keys())

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._buffer.start()
        if self.config.type == "api":
            self._task = asyncio.create_task(self._poll_api())
        elif self.config.type == "websocket":
            self._task = asyncio.create_task(self._listen_websocket())
        else:
            self._task = asyncio.create_task(self._poll_mcp())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._buffer.stop()
        self._task = None
        self._status = "idle"

    async def refresh_config(self, config: ExternalSourceConfig) -> None:
        signature = config.signature()
        if signature == self._signature:
            self.config = config
            return
        await self.stop()
        self.config = config
        self._signature = signature
        await self.start()

    async def _publish_update(self, update: dict[str, Any]) -> None:
        if not self.canvas_ids:
            return
        for canvas_id in self.canvas_ids:
            await publish_dashboard_update(
                canvas_id=canvas_id,
                target=DashboardSubscriptionTarget.EXTERNAL_STATE,
                source_id=self.source_id,
                change_type="updated",
                data=update,
            )

    async def _emit_status(self, status: ExternalStatus, error: str | None = None) -> None:
        if status == self._status and error == self._last_error:
            return
        self._status = status
        self._last_error = error
        await self._buffer.enqueue(
            build_external_update_payload(status=status, payload=None, error=error)
        )

    async def _emit_payload(self, payload: Any) -> None:
        self._status = "connected"
        self._last_error = None
        await self._buffer.enqueue(
            build_external_update_payload(status="connected", payload=payload, error=None)
        )

    async def _poll_api(self) -> None:
        allowed = {"http", "https"}
        endpoint = _normalize_endpoint(self.config.endpoint, allowed)
        if not endpoint:
            await self._emit_status("error", "API endpoint must use http or https")
            return
        timeout = httpx.Timeout(10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            await self._emit_status("connecting")
            while not self._stop_event.is_set():
                try:
                    response = await client.get(
                        endpoint,
                        headers={"Accept": "application/json"},
                    )
                    if response.status_code >= 400:
                        await self._emit_status(
                            "error",
                            f"Request failed ({response.status_code})",
                        )
                    else:
                        payload = await _parse_response_payload(response)
                        await self._emit_payload(payload)
                except httpx.TimeoutException:
                    await self._emit_status("error", "API request timed out")
                except Exception as exc:
                    await self._emit_status("error", str(exc))

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.config.poll_interval_ms / 1000,
                    )
                except TimeoutError:
                    continue

    async def _listen_websocket(self) -> None:
        allowed = {"ws", "wss"}
        endpoint = _normalize_endpoint(self.config.endpoint, allowed)
        if not endpoint:
            await self._emit_status("error", "WebSocket endpoint must use ws or wss")
            return
        while not self._stop_event.is_set():
            await self._emit_status("connecting")
            try:
                async with websockets.connect(
                    endpoint,
                    max_size=MAX_PAYLOAD_BYTES,
                    ping_interval=20,
                ) as ws:
                    await self._emit_status("connected")
                    async for message in ws:
                        if self._stop_event.is_set():
                            break
                        payload = _parse_ws_message(message)
                        await self._emit_payload(payload)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                await self._emit_status("error", str(exc))
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=DEFAULT_RECONNECT_DELAY_S,
                    )
                except TimeoutError:
                    continue

    async def _poll_mcp(self) -> None:
        if not self.config.mcp_tool_name:
            await self._emit_status("error", "MCP tool name is required")
            return
        await self._emit_status("connecting")
        while not self._stop_event.is_set():
            try:
                async with AsyncSessionLocal() as session:
                    client = MCPClient(session)
                    await client.initialize()
                    try:
                        result = await client.call_tool(
                            tool_name=self.config.mcp_tool_name,
                            arguments=self.config.mcp_args or {},
                            initiated_by="system",
                            server_id=self.config.mcp_server_id,
                        )
                    finally:
                        await client.shutdown()
                if result.required_confirmation:
                    await self._emit_status(
                        "error",
                        "MCP tool requires confirmation before execution",
                    )
                elif not result.success:
                    await self._emit_status(
                        "error", result.error or "MCP tool execution failed"
                    )
                else:
                    await self._emit_payload(result.result)
            except Exception as exc:
                await self._emit_status("error", str(exc))

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.config.poll_interval_ms / 1000,
                )
            except TimeoutError:
                continue


async def _parse_response_payload(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    text = response.text
    if len(text) > MAX_PAYLOAD_BYTES:
        return text[:MAX_PAYLOAD_BYTES]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _parse_ws_message(message: Any) -> Any:
    if isinstance(message, bytes):
        if len(message) > MAX_PAYLOAD_BYTES:
            return message[:MAX_PAYLOAD_BYTES].decode("utf-8", errors="ignore")
        try:
            return json.loads(message)
        except json.JSONDecodeError:
            return message.decode("utf-8", errors="ignore")
    if isinstance(message, str):
        if len(message) > MAX_PAYLOAD_BYTES:
            message = message[:MAX_PAYLOAD_BYTES]
        try:
            return json.loads(message)
        except json.JSONDecodeError:
            return message
    return message


class ExternalStateSubscriptionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sources: dict[str, ExternalSourceSubscription] = {}
        self._dashboard_sources: dict[int, dict[str, ExternalSourceConfigWithId]] = {}

    async def attach_dashboard(
        self,
        dashboard_node_id: int,
        canvas_id: int,
        subscriptions: list[dict[str, Any]],
    ) -> None:
        external_configs = self._extract_external_configs(subscriptions)
        if not external_configs:
            await self.detach_dashboard(dashboard_node_id, canvas_id)
            return

        async with self._lock:
            prev = self._dashboard_sources.get(dashboard_node_id, {})
            next_sources = {item.source_id: item for item in external_configs}

            removed = set(prev.keys()) - set(next_sources.keys())
            added = set(next_sources.keys()) - set(prev.keys())
            updated = set(next_sources.keys()) & set(prev.keys())

            for source_id in removed:
                await self._remove_source_canvas(source_id, canvas_id)

            for source_id in added:
                await self._add_source_canvas(source_id, canvas_id, next_sources[source_id])

            for source_id in updated:
                await self._update_source_config(source_id, next_sources[source_id])
                subscription = self._sources.get(source_id)
                if subscription and canvas_id not in subscription.canvas_ids:
                    subscription.add_canvas(canvas_id)

            self._dashboard_sources[dashboard_node_id] = next_sources

    async def detach_dashboard(self, dashboard_node_id: int, canvas_id: int) -> None:
        async with self._lock:
            prev = self._dashboard_sources.pop(dashboard_node_id, {})
            for source_id in prev.keys():
                await self._remove_source_canvas(source_id, canvas_id)

    async def _add_source_canvas(
        self,
        source_id: str,
        canvas_id: int,
        source_config: ExternalSourceConfigWithId,
    ) -> None:
        subscription = self._sources.get(source_id)
        if not subscription:
            subscription = ExternalSourceSubscription(
                source_id=source_id,
                config=source_config.config,
            )
            self._sources[source_id] = subscription
            await subscription.start()
        else:
            await subscription.refresh_config(source_config.config)
        subscription.add_canvas(canvas_id)

    async def _update_source_config(
        self,
        source_id: str,
        source_config: ExternalSourceConfigWithId,
    ) -> None:
        subscription = self._sources.get(source_id)
        if not subscription:
            subscription = ExternalSourceSubscription(
                source_id=source_id,
                config=source_config.config,
            )
            self._sources[source_id] = subscription
            await subscription.start()
            return
        await subscription.refresh_config(source_config.config)

    async def _remove_source_canvas(self, source_id: str, canvas_id: int) -> None:
        subscription = self._sources.get(source_id)
        if not subscription:
            return
        subscription.remove_canvas(canvas_id)
        if subscription.canvas_ids:
            return
        await subscription.stop()
        self._sources.pop(source_id, None)

    def _extract_external_configs(
        self, subscriptions: list[dict[str, Any]]
    ) -> list[ExternalSourceConfigWithId]:
        configs: list[ExternalSourceConfigWithId] = []
        for subscription in subscriptions:
            target = (
                subscription.get("subscriptionTarget")
                or subscription.get("subscription_target")
                or subscription.get("target")
            )
            if target != DashboardSubscriptionTarget.EXTERNAL_STATE.value:
                continue
            config = subscription.get("config") or subscription.get("subscription_config")
            if not _is_record(config):
                continue
            parsed = coerce_external_source_config(config)
            if not parsed:
                continue
            source_id = (
                _coerce_str(subscription.get("sourceId"))
                or _coerce_str(subscription.get("source_id"))
                or build_external_source_id(parsed)
            )
            configs.append(ExternalSourceConfigWithId(source_id=source_id, config=parsed))
        return configs


@dataclass
class ExternalSourceConfigWithId:
    source_id: str
    config: ExternalSourceConfig


_external_state_manager: ExternalStateSubscriptionManager | None = None


def get_external_state_manager() -> ExternalStateSubscriptionManager:
    global _external_state_manager
    if _external_state_manager is None:
        _external_state_manager = ExternalStateSubscriptionManager()
    return _external_state_manager
