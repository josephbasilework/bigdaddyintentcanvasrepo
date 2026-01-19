from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_test_tools.py"
    spec = importlib.util.spec_from_file_location("bootstrap_test_tools", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_paths_relative(tmp_path):
    module = load_module()
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "requirements.txt").write_text("# test\n")

    config = module.resolve_paths(
        backend_dir=backend_dir,
        venv_path=".venv",
        requirements_path="requirements.txt",
        python_bin="python3",
        install_deps=True,
    )

    assert config.venv_path == backend_dir / ".venv"
    assert config.requirements_path == backend_dir / "requirements.txt"


def test_build_steps_includes_venv_creation_when_missing(tmp_path):
    module = load_module()
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "requirements.txt").write_text("# test\n")

    config = module.resolve_paths(
        backend_dir=backend_dir,
        venv_path=".venv",
        requirements_path="requirements.txt",
        python_bin="python3",
        install_deps=True,
    )
    steps = module.build_steps(config)

    assert steps[0][:3] == ["python3", "-m", "venv"]
    assert any("--no-deps" in step for step in steps)


def test_build_steps_skips_venv_creation_when_exists(tmp_path):
    module = load_module()
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "requirements.txt").write_text("# test\n")
    (backend_dir / ".venv").mkdir()

    config = module.resolve_paths(
        backend_dir=backend_dir,
        venv_path=".venv",
        requirements_path="requirements.txt",
        python_bin="python3",
        install_deps=False,
    )
    steps = module.build_steps(config)

    assert not any(step[:3] == ["python3", "-m", "venv"] for step in steps)
