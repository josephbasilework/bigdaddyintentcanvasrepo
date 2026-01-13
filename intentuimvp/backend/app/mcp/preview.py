"""Helpers for building preview/diff payloads for external write confirmations."""

from __future__ import annotations

import json
from difflib import unified_diff
from typing import Any

_SENSITIVE_KEYWORDS = (
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "credential",
)


def redact_sensitive(value: Any) -> Any:
    """Redact sensitive fields from nested payloads."""
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(keyword in key_text for keyword in _SENSITIVE_KEYWORDS):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted

    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]

    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]

    return value


def build_tool_preview(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Build a sanitized preview payload for an external write."""
    sanitized_arguments = redact_sensitive(arguments)
    return {"tool": tool_name, "arguments": sanitized_arguments}


def build_tool_diff(
    preview: dict[str, Any],
    before: dict[str, Any] | None = None,
) -> str:
    """Build a unified diff for a preview payload."""
    before_payload = redact_sensitive(before) if before is not None else {}
    before_json = _serialize_payload(before_payload)
    after_json = _serialize_payload(preview)

    diff_lines = unified_diff(
        before_json.splitlines(keepends=True),
        after_json.splitlines(keepends=True),
        fromfile="current",
        tofile="proposed",
        lineterm="\n",
    )
    return "".join(diff_lines)


def _serialize_payload(value: Any) -> str:
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
        default=str,
    )
