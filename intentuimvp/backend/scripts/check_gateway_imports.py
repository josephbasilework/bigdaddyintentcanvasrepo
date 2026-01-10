#!/usr/bin/env python3
"""Fail if banned LLM provider SDKs are imported outside GatewayClient."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ALLOWED_PROVIDER_IMPORT_FILES = {
    "app/gateway/client.py",
}

BANNED_PROVIDERS = {
    "openai",
    "anthropic",
    "google.generativeai",
    "cohere",
    "langchain",
}


def _is_banned(module: str) -> bool:
    for banned in BANNED_PROVIDERS:
        if module == banned or module.startswith(f"{banned}."):
            return True
    return False


def _scan_file(py_file: Path, base_dir: Path) -> list[dict[str, str | int]]:
    relative_path = py_file.relative_to(base_dir)
    relative_path_str = str(relative_path)

    if relative_path_str in ALLOWED_PROVIDER_IMPORT_FILES:
        return []

    try:
        source = py_file.read_text()
    except OSError:
        return []

    try:
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return []

    lines = source.splitlines()
    violations: list[dict[str, str | int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if _is_banned(module):
                    line = node.lineno or 0
                    violations.append(
                        {
                            "file": relative_path_str,
                            "line": line,
                            "import": module,
                            "text": lines[line - 1].strip() if 0 < line <= len(lines) else "",
                        }
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            if _is_banned(module):
                line = node.lineno or 0
                violations.append(
                    {
                        "file": relative_path_str,
                        "line": line,
                        "import": module,
                        "text": lines[line - 1].strip() if 0 < line <= len(lines) else "",
                    }
                )
    return violations


def main() -> int:
    base_dir = Path(__file__).resolve().parents[1]
    app_dir = base_dir / "app"

    if not app_dir.exists():
        print("Gateway import check failed: app/ directory not found.", file=sys.stderr)
        return 2

    violations: list[dict[str, str | int]] = []

    for py_file in app_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        violations.extend(_scan_file(py_file, base_dir))

    if not violations:
        print("Gateway import check passed.")
        return 0

    print(
        "\nDirect LLM provider SDK imports detected!",
        "All LLM calls must go through GatewayClient (app/gateway/client.py).",
        "\nViolations found:",
        sep="\n",
        file=sys.stderr,
    )
    for violation in violations:
        file_path = violation["file"]
        line = violation["line"]
        imp = violation["import"]
        text = violation["text"]
        detail = f"{file_path}:{line}: {imp}"
        if text:
            detail = f"{detail} -> {text}"
        print(f"  - {detail}", file=sys.stderr)

    allowed = ", ".join(sorted(ALLOWED_PROVIDER_IMPORT_FILES))
    print(f"\nAllowed files: {allowed}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
