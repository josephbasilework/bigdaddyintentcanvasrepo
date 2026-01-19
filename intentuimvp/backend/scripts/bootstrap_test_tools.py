#!/usr/bin/env python3
"""Bootstrap backend test tooling (venv, pip, pytest)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolingConfig:
    backend_dir: Path
    venv_path: Path
    python_bin: str
    requirements_path: Path
    install_deps: bool

    @property
    def venv_python(self) -> Path:
        return self.venv_path / "bin" / "python"


def resolve_paths(
    backend_dir: Path,
    venv_path: str,
    requirements_path: str,
    python_bin: str,
    install_deps: bool,
) -> ToolingConfig:
    backend_dir = backend_dir.resolve()
    resolved_venv = Path(venv_path)
    if not resolved_venv.is_absolute():
        resolved_venv = backend_dir / resolved_venv
    resolved_requirements = Path(requirements_path)
    if not resolved_requirements.is_absolute():
        resolved_requirements = backend_dir / resolved_requirements
    return ToolingConfig(
        backend_dir=backend_dir,
        venv_path=resolved_venv,
        python_bin=python_bin,
        requirements_path=resolved_requirements,
        install_deps=install_deps,
    )


def build_steps(config: ToolingConfig) -> list[list[str]]:
    steps: list[list[str]] = []
    if not config.venv_path.exists():
        steps.append([config.python_bin, "-m", "venv", str(config.venv_path)])

    venv_python = str(config.venv_python)
    steps.append([venv_python, "-m", "ensurepip", "--upgrade"])
    steps.append([venv_python, "-m", "pip", "install", "--upgrade", "pip"])

    if config.install_deps:
        steps.append(
            [
                venv_python,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "-r",
                str(config.requirements_path),
            ]
        )
    return steps


def validate_config(config: ToolingConfig) -> None:
    if shutil.which(config.python_bin) is None:
        raise SystemExit(f"Python interpreter not found: {config.python_bin}")
    if not config.requirements_path.exists():
        raise SystemExit(f"Requirements file not found: {config.requirements_path}")
    if config.venv_path.exists() and not config.venv_python.exists():
        raise SystemExit(f"Virtualenv missing python: {config.venv_python}")


def run_steps(steps: list[list[str]], dry_run: bool) -> None:
    for step in steps:
        if dry_run:
            print(" ".join(step))
            continue
        subprocess.run(step, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap backend python tooling (venv, pip, pytest)."
    )
    parser.add_argument(
        "--backend-dir",
        default=str(Path(__file__).resolve().parents[1]),
        help="Backend directory containing requirements.txt",
    )
    parser.add_argument(
        "--venv-path",
        default=".venv",
        help="Virtualenv path (relative to backend dir unless absolute)",
    )
    parser.add_argument(
        "--requirements",
        default="requirements.txt",
        help="Requirements file (relative to backend dir unless absolute)",
    )
    parser.add_argument(
        "--python-bin",
        default="python3",
        help="Python interpreter to create the virtualenv",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip installing requirements.txt into the virtualenv",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = resolve_paths(
        backend_dir=Path(args.backend_dir),
        venv_path=args.venv_path,
        requirements_path=args.requirements,
        python_bin=args.python_bin,
        install_deps=not args.skip_install,
    )
    validate_config(config)
    steps = build_steps(config)
    run_steps(steps, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
