from __future__ import annotations

from pathlib import Path

from .types import VerifyStep


def detect_go_steps(project_root: Path, *, timeout_seconds: int) -> list[VerifyStep]:
    if not (project_root / "go.mod").exists():
        return []
    return [VerifyStep(name="go:test", argv=["go", "test", "./..."], cwd=project_root, timeout_seconds=timeout_seconds, kind="test")]

