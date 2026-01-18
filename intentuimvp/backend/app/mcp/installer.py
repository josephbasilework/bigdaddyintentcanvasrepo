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


def _normalize_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _dedupe_str_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


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


def _filter_catalog_transport_override(
    override: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if not override:
        return None, []
    issues: list[str] = []
    filtered: dict[str, Any] | None = None
    env_override = override.get("env")
    if env_override is not None:
        filtered = {"env": env_override}
    disallowed_keys = set(override.keys()) - {"env"}
    if disallowed_keys:
        issue_keys = ", ".join(sorted(disallowed_keys))
        issues.append(
            f"Catalog installs only allow env overrides; override provided for: {issue_keys}"
        )
    return filtered, issues


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


def _extract_permission_scopes(
    manifest: MCPManifest, oauth: Any, catalog_entry: dict[str, Any] | None
) -> list[str]:
    scopes: list[str] = []
    if oauth is not None:
        scopes.extend(_normalize_str_list(getattr(oauth, "scopes", None)))
        if isinstance(oauth, dict):
            scopes.extend(_normalize_str_list(oauth.get("scopes")))

    if catalog_entry:
        catalog_oauth = catalog_entry.get("oauth")
        if isinstance(catalog_oauth, dict):
            scopes.extend(_normalize_str_list(catalog_oauth.get("scopes")))

    metadata = manifest.metadata or {}
    metadata_oauth = metadata.get("oauth")
    if isinstance(metadata_oauth, dict):
        scopes.extend(_normalize_str_list(metadata_oauth.get("scopes")))

    permissions = metadata.get("permissions")
    if isinstance(permissions, dict):
        scopes.extend(_normalize_str_list(permissions.get("scopes")))

    return _dedupe_str_list(scopes)


def _extract_required_env(
    manifest: MCPManifest, credential_fields: list[dict[str, Any]]
) -> list[str]:
    required_env: list[str] = []
    metadata = manifest.metadata or {}
    required_env.extend(_normalize_str_list(metadata.get("required_env")))
    permissions = metadata.get("permissions")
    if isinstance(permissions, dict):
        required_env.extend(_normalize_str_list(permissions.get("required_env")))

    credential_env = [
        field.get("env_key") for field in credential_fields if field.get("env_key")
    ]
    required_env.extend(_normalize_str_list(credential_env))
    return _dedupe_str_list(required_env)


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


def _validate_capabilities(
    manifest: MCPManifest, tools: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    has_capabilities = bool(
        manifest.capabilities.tools
        or manifest.capabilities.resources
        or manifest.capabilities.prompts
    )
    if not has_capabilities:
        issues.append(
            {
                "message": "Manifest declares no capabilities",
                "blocking": True,
            }
        )

    names = [tool.get("name") for tool in tools if tool.get("name")]
    seen: set[str] = set()
    duplicates: list[str] = []
    for name in names:
        if name in seen:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        issues.append(
            {
                "message": f"Duplicate tool names detected: {', '.join(sorted(set(duplicates)))}",
                "blocking": True,
            }
        )

    for tool in tools:
        tool_name = tool.get("name") or "Unnamed tool"
        if not tool.get("description"):
            issues.append(
                {
                    "message": f"Tool '{tool_name}' is missing a description",
                    "blocking": False,
                }
            )
    return issues


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
        elif not (
            url.startswith("https://")
            or url.startswith("http://localhost")
            or url.startswith("http://127.0.0.1")
        ):
            issues.append("sse transport must use https or localhost")
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
    required_env: list[str] | None = None,
) -> list[str]:
    env = transport_config.get("env", {})
    provided = set(credentials.keys()) if credentials else set()
    required_keys: set[str] = set()
    missing: list[str] = []
    for field in credential_fields:
        env_key = field.get("env_key")
        if not env_key:
            continue
        required = field.get("required", True)
        if not required:
            continue
        required_keys.add(env_key)
    if required_env:
        required_keys.update(required_env)

    for env_key in sorted(required_keys):
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
        "resources": resolved.get("resources", []),
        "prompts": resolved.get("prompts", []),
        "tools": [
            {
                **tool,
                "security_level": resolved["security_rules"].get(tool.get("name")),
            }
            for tool in resolved["tools"]
        ],
        "security_rules": resolved["security_rules"],
        "oauth": resolved.get("oauth"),
        "permission_scopes": resolved.get("permission_scopes", []),
        "required_env": resolved.get("required_env", []),
        "credential_fields": resolved.get("credential_fields", []),
        "missing_credentials": resolved.get("missing_credentials", []),
        "sandbox_issues": resolved.get("sandbox_issues", []),
        "blocked_tools": resolved.get("blocked_tools", []),
        "security_checks": resolved.get("security_checks", []),
        "blocking_issues": resolved.get("blocking_issues", []),
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

        source_issues: list[dict[str, Any]] = []
        if catalog_entry:
            if getattr(payload, "server_id", None) and (
                payload.server_id != catalog_entry.get("server_id")
            ):
                source_issues.append(
                    {
                        "message": "Catalog installs cannot override server_id",
                        "blocking": True,
                    }
                )
            if getattr(payload, "transport_type", None) and (
                payload.transport_type != catalog_entry.get("transport_type")
            ):
                source_issues.append(
                    {
                        "message": "Catalog installs cannot override transport_type",
                        "blocking": True,
                    }
                )
            if getattr(payload, "manifest", None) is not None:
                source_issues.append(
                    {
                        "message": "Catalog installs cannot override manifest",
                        "blocking": True,
                    }
                )

        server_id = (
            catalog_entry.get("server_id")
            if catalog_entry
            else getattr(payload, "server_id", None)
        )
        if not server_id:
            raise MCPInstallError("server_id is required for MCP install preview")

        name = getattr(payload, "name", None) or (
            catalog_entry.get("name") if catalog_entry else server_id
        )
        description = getattr(payload, "description", None) or (
            catalog_entry.get("description") if catalog_entry else None
        )

        transport_type = (
            catalog_entry.get("transport_type")
            if catalog_entry
            else getattr(payload, "transport_type", None)
        )
        if not transport_type:
            raise MCPInstallError("transport_type is required for MCP install preview")

        transport_override = getattr(payload, "transport_config", None)
        if catalog_entry:
            filtered_override, override_issues = _filter_catalog_transport_override(
                transport_override
            )
            for issue in override_issues:
                source_issues.append({"message": issue, "blocking": True})
            transport_override = filtered_override

        transport_config = _merge_transport_config(
            catalog_entry.get("transport_config") if catalog_entry else None,
            transport_override,
        )

        credentials = getattr(payload, "credentials", None)
        transport_config = _apply_credentials(transport_config, credentials)

        if catalog_entry:
            manifest_input = catalog_entry.get("manifest")
        else:
            manifest_input = getattr(payload, "manifest", None)
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
        required_env = _extract_required_env(manifest_model, credential_fields)
        missing_credentials = _resolve_missing_credentials(
            credential_fields, transport_config, credentials, required_env=required_env
        )

        sandbox_issues = _validate_transport_config(transport_type, transport_config)
        resources = capabilities.get("resources", [])
        prompts = capabilities.get("prompts", [])
        capability_issues = _validate_capabilities(manifest_model, tools)
        permission_scopes = _extract_permission_scopes(
            manifest_model, getattr(payload, "oauth", None), catalog_entry
        )

        def make_check(
            check_id: str,
            label: str,
            status: str,
            details: str | None = None,
            issues: list[str] | None = None,
            blocking: bool = False,
        ) -> dict[str, Any]:
            return {
                "id": check_id,
                "label": label,
                "status": status,
                "details": details,
                "issues": issues or [],
                "blocking": blocking,
            }

        blocking_issues: list[str] = []
        security_checks: list[dict[str, Any]] = []

        if catalog_entry:
            if source_issues:
                source_messages = [issue["message"] for issue in source_issues]
                security_checks.append(
                    make_check(
                        "source_verification",
                        "Source verification",
                        "failed",
                        "Catalog overrides detected",
                        issues=source_messages,
                        blocking=True,
                    )
                )
                blocking_issues.extend(source_messages)
            else:
                security_checks.append(
                    make_check(
                        "source_verification",
                        "Source verification",
                        "passed",
                        "Catalog entry verified",
                    )
                )
        else:
            security_checks.append(
                make_check(
                    "source_verification",
                    "Source verification",
                    "pending",
                    "Custom MCP source requires manual verification",
                )
            )

        security_checks.append(
            make_check(
                "manifest_validation",
                "Manifest validation",
                "passed",
                "Manifest schema validated",
            )
        )

        capability_blocking = [
            issue["message"] for issue in capability_issues if issue.get("blocking")
        ]
        capability_warnings = [
            issue["message"] for issue in capability_issues if not issue.get("blocking")
        ]
        if capability_blocking:
            security_checks.append(
                make_check(
                    "capability_validation",
                    "Capability validation",
                    "failed",
                    "Blocking capability issues detected",
                    issues=capability_blocking + capability_warnings,
                    blocking=True,
                )
            )
            blocking_issues.extend(capability_blocking)
        elif capability_warnings:
            security_checks.append(
                make_check(
                    "capability_validation",
                    "Capability validation",
                    "pending",
                    "Non-blocking capability warnings detected",
                    issues=capability_warnings,
                )
            )
        else:
            security_checks.append(
                make_check(
                    "capability_validation",
                    "Capability validation",
                    "passed",
                    "Capabilities validated",
                )
            )

        if permission_scopes or required_env:
            scope_details = []
            if permission_scopes:
                scope_details.append(f"{len(permission_scopes)} scope(s)")
            if required_env:
                scope_details.append(f"{len(required_env)} env var(s)")
            security_checks.append(
                make_check(
                    "permission_scopes",
                    "Permission scope review",
                    "pending",
                    ", ".join(scope_details) + " require review",
                )
            )
        else:
            security_checks.append(
                make_check(
                    "permission_scopes",
                    "Permission scope review",
                    "passed",
                    "No permission scopes declared",
                )
            )

        if sandbox_issues:
            sandbox_message = f"Sandbox policy violations: {', '.join(sandbox_issues)}"
            security_checks.append(
                make_check(
                    "sandbox_validation",
                    "Sandbox validation",
                    "failed",
                    sandbox_message,
                    issues=sandbox_issues,
                    blocking=True,
                )
            )
            blocking_issues.append(sandbox_message)
        else:
            security_checks.append(
                make_check(
                    "sandbox_validation",
                    "Sandbox validation",
                    "passed",
                    "Sandbox policy checks passed",
                )
            )

        scan_issues: list[str] = []
        if missing_credentials:
            credentials_message = (
                f"Missing credentials: {', '.join(missing_credentials)}"
            )
            scan_issues.append(credentials_message)
            blocking_issues.append(credentials_message)
        if blocked_tools:
            scan_issues.append(f"Blocked tools detected: {', '.join(blocked_tools)}")
        scan_issues.extend(capability_warnings)
        scan_issues.extend(capability_blocking)

        if scan_issues:
            security_checks.append(
                make_check(
                    "issue_scan",
                    "Issue scan",
                    "failed" if missing_credentials or capability_blocking else "pending",
                    "Review detected issues before enabling",
                    issues=scan_issues,
                    blocking=bool(missing_credentials or capability_blocking),
                )
            )
        else:
            security_checks.append(
                make_check(
                    "issue_scan",
                    "Issue scan",
                    "passed",
                    "No issues detected",
                )
            )

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
            "resources": resources,
            "prompts": prompts,
            "security_rules": security_rules,
            "blocked_tools": blocked_tools,
            "credential_fields": credential_fields,
            "missing_credentials": missing_credentials,
            "sandbox_issues": sandbox_issues,
            "oauth": getattr(payload, "oauth", None)
            or (catalog_entry.get("oauth") if catalog_entry else None),
            "permission_scopes": permission_scopes,
            "required_env": required_env,
            "security_checks": security_checks,
            "blocking_issues": blocking_issues,
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

        blocking_issues = preview_payload.get("blocking_issues", [])
        if blocking_issues:
            issue_text = "; ".join(blocking_issues)
            return {
                "success": False,
                "requires_confirmation": False,
                "error": f"Install blocked: {issue_text}",
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
