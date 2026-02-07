from __future__ import annotations

from pathlib import Path

from .types import VerifyStep


def _should_run_pytest(project_root: Path) -> bool:
    if (project_root / "pytest.ini").exists():
        return True
    if (project_root / "conftest.py").exists():
        return True
    if (project_root / "tests").exists():
        return True
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return False
        return "pytest" in text
    return False


def detect_python_steps(project_root: Path, *, timeout_seconds: int, no_install: bool) -> list[VerifyStep]:
    has_pyproject = (project_root / "pyproject.toml").exists()
    has_reqs = (project_root / "requirements.txt").exists()
    if not (has_pyproject or has_reqs):
        return []

    steps: list[VerifyStep] = []
    if not no_install:
        if has_pyproject:
            steps.append(VerifyStep(name="python:uv:sync", argv=["uv", "sync"], cwd=project_root, timeout_seconds=timeout_seconds, kind="install"))
        else:
            steps.append(VerifyStep(name="python:uv:venv", argv=["uv", "venv"], cwd=project_root, timeout_seconds=timeout_seconds, kind="install"))
            steps.append(
                VerifyStep(
                    name="python:uv:pip-install",
                    argv=["uv", "pip", "install", "-r", "requirements.txt"],
                    cwd=project_root,
                    timeout_seconds=timeout_seconds,
                    kind="install",
                )
            )

    if _should_run_pytest(project_root):
        steps.append(
            VerifyStep(
                name="python:test:pytest",
                argv=["uv", "run", "python", "-m", "pytest"],
                cwd=project_root,
                timeout_seconds=timeout_seconds,
                kind="test",
            )
        )
    else:
        steps.append(
            VerifyStep(
                name="python:test:unittest",
                argv=["uv", "run", "python", "-m", "unittest", "discover"],
                cwd=project_root,
                timeout_seconds=timeout_seconds,
                kind="test",
            )
        )

    return steps

