#!/usr/bin/env python3
"""Canvas-first enforcement check.

Fails if chat-first UI component tokens appear in frontend source files.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BANNED_TOKENS = {
    "MessageList": "Chat-first message list component",
    "ChatThread": "Chat-first thread component",
}

FILE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}
EXCLUDED_DIR_NAMES = {"node_modules", ".next", "dist", "build", ".turbo"}


@dataclass(frozen=True)
class Violation:
    file: Path
    line: int
    token: str
    reason: str
    text: str


def _compile_patterns(tokens: dict[str, str]) -> list[tuple[str, re.Pattern[str], str]]:
    compiled: list[tuple[str, re.Pattern[str], str]] = []
    for token, reason in tokens.items():
        compiled.append((token, re.compile(rf"\b{re.escape(token)}\b"), reason))
    return compiled


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def _scan_file(
    file_path: Path,
    compiled_patterns: list[tuple[str, re.Pattern[str], str]],
) -> list[Violation]:
    try:
        contents = file_path.read_text(encoding="utf-8")
    except OSError:
        return []

    violations: list[Violation] = []
    for line_number, line in enumerate(contents.splitlines(), start=1):
        for token, pattern, reason in compiled_patterns:
            if pattern.search(line):
                violations.append(
                    Violation(
                        file=file_path,
                        line=line_number,
                        token=token,
                        reason=reason,
                        text=line.strip(),
                    )
                )
    return violations


def scan_canvas_first(
    base_dir: Path,
    search_dirs: Iterable[Path] | None = None,
) -> list[Violation]:
    if search_dirs is None:
        search_dirs = [base_dir / "src"]

    compiled_patterns = _compile_patterns(BANNED_TOKENS)
    violations: list[Violation] = []

    for search_dir in search_dirs:
        if not search_dir.exists():
            raise FileNotFoundError(f"Search directory not found: {search_dir}")

        for file_path in search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if _is_excluded(file_path):
                continue
            if file_path.suffix not in FILE_EXTENSIONS:
                continue
            violations.extend(_scan_file(file_path, compiled_patterns))

    return violations


def _format_violation(base_dir: Path, violation: Violation) -> str:
    relative = violation.file.relative_to(base_dir)
    detail = f"{relative}:{violation.line}: {violation.token} ({violation.reason})"
    if violation.text:
        detail = f"{detail} -> {violation.text}"
    return detail


def main() -> int:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Canvas-first enforcement check.")
    parser.add_argument(
        "--root",
        default=str(default_root),
        help="Frontend root directory (default: script parent).",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=["src"],
        help="Relative directories to scan from root.",
    )
    args = parser.parse_args()

    base_dir = Path(args.root).resolve()
    search_dirs = [base_dir / path for path in args.paths]

    try:
        violations = scan_canvas_first(base_dir, search_dirs)
    except FileNotFoundError as exc:
        print(f"Canvas-first check failed: {exc}", file=sys.stderr)
        return 2

    if not violations:
        print("Canvas-first check passed.")
        return 0

    print(
        "\nCanvas-first enforcement failed.",
        "Chat-first UI patterns detected in frontend source.",
        "\nViolations found:",
        sep="\n",
        file=sys.stderr,
    )
    for violation in violations:
        print(f"  - {_format_violation(base_dir, violation)}", file=sys.stderr)

    banned = ", ".join(sorted(BANNED_TOKENS))
    print(f"\nBanned tokens: {banned}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
