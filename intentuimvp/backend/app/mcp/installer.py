"""Runtime MCP installation and configuration helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.catalog import get_mcp_catalog_entry
from app.mcp.manifest import MCPManifest, is_blocked_capability
from app.mcp.models import SecurityLevel
from app.mcp.preview import build_tool_diff, build_tool_preview, redact_sensitive
from app.mcp.registry import DEFAULT_SECURITY_RULES, MCPServerRegistry
from app.mcp.security import MCPSecurityValidator


class MCPInstallError(RuntimeError):
    """Raised when MCP installation validation fails."""


_BLOCKED_COMMANDS = {
    "bash",
    "sh",
    "zsh",
    "fish",
    "cmd",
    "powershell",
    "pwsh",
}

_BLOCKED_ENV_KEYS = {
    "LD_PRELOAD",
    "DYLD_INSERT_LIBRARIES",
    "PYTHONPATH",
    "PATH",
    "HOME",
    "SHELL",
}


def _merge_transport_config(
    base: dict[str, Any] | None, override: dict[str, Any] | None
) -> dict[str, Any]:
    merged = deepcopy(base or {})
    if not override:
        return merged

    for key, value in override.items():
        if key == "env" and isinstance(value, dict):
            env = dict(merged.get("env", {}))
            env.update(value)
            merged["env"] = env
        else:
            merged[key] = value
    return merged


def _apply_credentials(
    transport_config: dict[str, Any], credentials: dict[str, str] | None
) -> dict[str, Any]:
    updated = deepcopy(transport_config)
    if not credentials:
        return updated
    env = dict(updated.get("env", {}))
    env.update(credentials)
    updated["env"] = env
    return updated


def _normalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(manifest)
    if "protocol_version" in normalized and "protocolVersion" not in normalized:
        normalized["protocolVersion"] = normalized.pop("protocol_version")

    capabilities = normalized.get("capabilities")
    if isinstance(capabilities, dict) and "tools" in capabilities:
        tools = capabilities.get("tools", [])
        if isinstance(tools, list):
            normalized_tools: list[dict[str, Any]] = []
            for tool in tools:
                if not isinstance(tool, dict):
                    continue
                tool_copy = dict(tool)
                if "inputSchema" in tool_copy and "input_schema" not in tool_copy:
                    tool_copy["input_schema"] = tool_copy.pop("inputSchema")
                normalized_tools.append(tool_copy)
            capabilities["tools"] = normalized_tools
            normalized["capabilities"] = capabilities
    return normalized


def _serialize_manifest(manifest: MCPManifest) -> dict[str, Any]:
    data = manifest.model_dump(by_alias=True)
    capabilities = data.get("capabilities", {})
    tools = capabilities.get("tools", [])
    if isinstance(tools, list):
        serialized_tools: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tool_copy = dict(tool)
            if "input_schema" in tool_copy:
                tool_copy["inputSchema"] = tool_copy.pop("input_schema")
            serialized_tools.append(tool_copy)
        capabilities["tools"] = serialized_tools
        data["capabilities"] = capabilities
    return data


def _capabilities_from_manifest(manifest: MCPManifest) -> dict[str, Any]:
    capabilities: dict[str, Any] = {}
    if manifest.capabilities.tools:
        tools_payload: list[dict[str, Any]] = []
        for tool in manifest.capabilities.tools:
            tools_payload.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema.model_dump(),
                }
            )
        capabilities["tools"] = tools_payload

    if manifest.capabilities.resources:
        capabilities["resources"] = [
            resource.model_dump() for resource in manifest.capabilities.resources
        ]

    if manifest.capabilities.prompts:
        capabilities["prompts"] = [
            prompt.model_dump() for prompt in manifest.capabilities.prompts
        ]

    return capabilities


def _infer_security_level(tool_name: str) -> SecurityLevel:
    lowered = tool_name.lower()
    if is_blocked_capability(tool_name):
        return SecurityLevel.BLOCKED
    if any(word in lowered for word in ("delete", "drop", "destroy", "remove")):
        return SecurityLevel.BLOCKED
    if any(word in lowered for word in ("write", "create", "update", "send", "post", "add", "set")):
        return SecurityLevel.REQUIRES_CONFIRM
    if any(word in lowered for word in ("read", "list", "get", "query", "search", "fetch")):
        return SecurityLevel.ALLOWED
    return SecurityLevel.REQUIRES_CONFIRM


def _build_security_rules(
    server_id: str, tools: list[dict[str, Any]]
) -> dict[str, str]:
    rules: dict[str, str] = {}
    defaults = DEFAULT_SECURITY_RULES.get(server_id, {})
    for tool in tools:
        tool_name = tool.get("name")
        if not tool_name:
            continue
        if tool_name in defaults:
            rules[tool_name] = defaults[tool_name].value
        else:
            rules[tool_name] = _infer_security_level(tool_name).value
    return rules


def _validate_transport_config(
    transport_type: str, transport_config: dict[str, Any]
) -> list[str]:
    issues: list[str] = []
    if transport_type == "stdio":
        command = transport_config.get("command")
        if not isinstance(command, list) or not command:
            issues.append("stdio transport requires a non-empty command list")
        else:
            executable = str(command[0]).lower()
            if executable in _BLOCKED_COMMANDS:
                issues.append(f"blocked stdio executable: {command[0]}")
            for token in command:
                token_str = str(token)
                if any(op in token_str for op in (";", "&&", "|", "`", "$(")):
                    issues.append("stdio command contains shell operators")
                    break
    elif transport_type == "sse":
        url = transport_config.get("url")
        if not isinstance(url, str) or not url.strip():
            issues.append("sse transport requires a url string")
    else:
        issues.append(f"unknown transport type: {transport_type}")

    env = transport_config.get("env")
    if isinstance(env, dict):
        for key in env.keys():
            if key in _BLOCKED_ENV_KEYS:
                issues.append(f"blocked env key: {key}")

    return issues


def _resolve_missing_credentials(
    credential_fields: list[dict[str, Any]],
    transport_config: dict[str, Any],
    credentials: dict[str, str] | None,
) -> list[str]:
    env = transport_config.get("env", {})
    provided = set(credentials.keys()) if credentials else set()
    missing: list[str] = []
    for field in credential_fields:
        env_key = field.get("env_key")
        if not env_key:
            continue
        required = field.get("required", True)
        if not required:
            continue
        if env_key in env and env.get(env_key):
            continue
        if env_key in provided:
            continue
        missing.append(env_key)
    return missing


def _is_review_complete(approved_tools: list[str], tools: list[dict[str, Any]]) -> bool:
    tool_names = {tool.get("name") for tool in tools if tool.get("name")}
    return bool(tool_names) and tool_names.issubset(set(approved_tools))


def _build_preview_payload(resolved: dict[str, Any]) -> dict[str, Any]:
    return {
        "server_id": resolved["server_id"],
        "name": resolved["name"],
        "description": resolved.get("description"),
        "transport_type": resolved["transport_type"],
        "transport_config": redact_sensitive(resolved["transport_config"]),
        "manifest": _serialize_manifest(resolved["manifest_model"]),
        "tools": [
            {
                **tool,
                "security_level": resolved["security_rules"].get(tool.get("name")),
            }
            for tool in resolved["tools"]
        ],
        "security_rules": resolved["security_rules"],
        "oauth": resolved.get("oauth"),
        "credential_fields": resolved.get("credential_fields", []),
        "missing_credentials": resolved.get("missing_credentials", []),
        "sandbox_issues": resolved.get("sandbox_issues", []),
        "blocked_tools": resolved.get("blocked_tools", []),
    }


class MCPInstaller:
    """Install and configure MCP servers at runtime."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._registry = MCPServerRegistry(session)
        self._validator = MCPSecurityValidator(session)

    async def _resolve_install_spec(self, payload: Any) -> dict[str, Any]:
        catalog_id = getattr(payload, "catalog_id", None)
        catalog_entry = (
            get_mcp_catalog_entry(catalog_id) if catalog_id else None
        )

        server_id = getattr(payload, "server_id", None) or (
            catalog_entry.get("server_id") if catalog_entry else None
        )
        if not server_id:
            raise MCPInstallError("server_id is required for MCP install preview")

        name = getattr(payload, "name", None) or (
            catalog_entry.get("name") if catalog_entry else server_id
        )
        description = getattr(payload, "description", None) or (
            catalog_entry.get("description") if catalog_entry else None
        )

        transport_type = getattr(payload, "transport_type", None) or (
            catalog_entry.get("transport_type") if catalog_entry else None
        )
        if not transport_type:
            raise MCPInstallError("transport_type is required for MCP install preview")

        transport_config = _merge_transport_config(
            catalog_entry.get("transport_config") if catalog_entry else None,
            getattr(payload, "transport_config", None),
        )

        credentials = getattr(payload, "credentials", None)
        transport_config = _apply_credentials(transport_config, credentials)

        manifest_input = getattr(payload, "manifest", None) or (
            catalog_entry.get("manifest") if catalog_entry else None
        )
        if not manifest_input:
            raise MCPInstallError("manifest is required for MCP install preview")

        normalized_manifest = _normalize_manifest(manifest_input)
        try:
            manifest_model = MCPManifest.model_validate(normalized_manifest)
        except ValidationError as exc:
            raise MCPInstallError(f"Invalid MCP manifest: {exc}") from exc

        is_valid, error_message = await self._validator.validate_manifest(
            normalized_manifest, transport_type, transport_config
        )
        if not is_valid:
            raise MCPInstallError(error_message or "Manifest validation failed")

        capabilities = _capabilities_from_manifest(manifest_model)
        tools = capabilities.get("tools", [])
        security_rules = _build_security_rules(server_id, tools)
        blocked_tools = [
            tool["name"]
            for tool in tools
            if security_rules.get(tool.get("name")) == SecurityLevel.BLOCKED.value
        ]

        credential_fields = catalog_entry.get("credential_fields", []) if catalog_entry else []
        missing_credentials = _resolve_missing_credentials(
            credential_fields, transport_config, credentials
        )

        sandbox_issues = _validate_transport_config(transport_type, transport_config)

        return {
            "catalog_entry": catalog_entry,
            "server_id": server_id,
            "name": name,
            "description": description,
            "transport_type": transport_type,
            "transport_config": transport_config,
            "manifest_model": manifest_model,
            "capabilities": capabilities,
            "tools": tools,
            "security_rules": security_rules,
            "blocked_tools": blocked_tools,
            "credential_fields": credential_fields,
            "missing_credentials": missing_credentials,
            "sandbox_issues": sandbox_issues,
            "oauth": getattr(payload, "oauth", None)
            or (catalog_entry.get("oauth") if catalog_entry else None),
        }

    async def build_preview(self, payload: Any) -> dict[str, Any]:
        resolved = await self._resolve_install_spec(payload)
        preview_payload = _build_preview_payload(resolved)
        preview = build_tool_preview("install_mcp", preview_payload)
        diff = build_tool_diff(preview)

        return {
            "requires_confirmation": True,
            "preview": preview_payload,
            "diff": diff,
        }

    async def install(self, payload: Any) -> dict[str, Any]:
        try:
            resolved = await self._resolve_install_spec(payload)
        except MCPInstallError as exc:
            return {
                "success": False,
                "requires_confirmation": False,
                "error": str(exc),
            }

        preview_payload = _build_preview_payload(resolved)
        preview = build_tool_preview("install_mcp", preview_payload)
        diff = build_tool_diff(preview)

        if not getattr(payload, "confirmed", False):
            return {
                "success": False,
                "requires_confirmation": True,
                "preview": preview_payload,
                "diff": diff,
            }

        if preview_payload.get("sandbox_issues"):
            return {
                "success": False,
                "requires_confirmation": False,
                "error": "Sandbox policy violations detected",
                "preview": preview_payload,
            }

        if preview_payload.get("missing_credentials"):
            return {
                "success": False,
                "requires_confirmation": False,
                "error": "Missing required credentials",
                "preview": preview_payload,
            }

        approved_tools = getattr(payload, "approved_tools", None) or []
        review_complete = _is_review_complete(
            approved_tools, preview_payload.get("tools", [])
        )
        enabled = review_complete

        transport_config = resolved["transport_config"]

        server = await self._registry.register_server(
            server_id=resolved["server_id"],
            name=resolved["name"],
            description=resolved.get("description"),
            transport_type=resolved["transport_type"],
            transport_config=transport_config,
            version=resolved["manifest_model"].version,
            capabilities=resolved["capabilities"],
            security_rules=resolved.get("security_rules", {}),
            enabled=enabled,
            rate_limit=(
                payload.rate_limit if getattr(payload, "rate_limit", None) is not None else 60
            ),
        )

        return {
            "success": True,
            "requires_confirmation": False,
            "review_required": not review_complete,
            "server": server.to_dict(),
            "preview": preview_payload,
        }
