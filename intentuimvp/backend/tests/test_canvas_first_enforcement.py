"""Canvas-first enforcement tests.

Validates that chat-first UI tokens are detected in frontend sources.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_checker_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = (
        repo_root
        / "intentuimvp"
        / "frontend"
        / "scripts"
        / "check_canvas_first.py"
    )
    assert script_path.exists(), "Canvas-first check script missing"

    spec = importlib.util.spec_from_file_location("check_canvas_first", script_path)
    assert spec and spec.loader, "Failed to load canvas-first check module"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_canvas_first_check_allows_canvas_components(tmp_path):
    checker = _load_checker_module()
    frontend_dir = tmp_path / "frontend"
    src_dir = frontend_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "CanvasNode.tsx").write_text(
        "export const CanvasNode = () => <div>Canvas</div>;"
    )

    violations = checker.scan_canvas_first(frontend_dir, [src_dir])

    assert violations == []


def test_canvas_first_check_flags_chat_components(tmp_path):
    checker = _load_checker_module()
    frontend_dir = tmp_path / "frontend"
    src_dir = frontend_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "ChatThread.tsx").write_text(
        "export const ChatThread = () => <div>ChatThread</div>;"
    )

    violations = checker.scan_canvas_first(frontend_dir, [src_dir])

    assert len(violations) == 1
    assert violations[0].token == "ChatThread"
