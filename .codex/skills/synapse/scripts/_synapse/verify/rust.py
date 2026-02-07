from __future__ import annotations

from pathlib import Path

from .types import VerifyStep


def detect_rust_steps(project_root: Path, *, timeout_seconds: int) -> list[VerifyStep]:
    if not (project_root / "Cargo.toml").exists():
        return []
    return [VerifyStep(name="rust:test", argv=["cargo", "test"], cwd=project_root, timeout_seconds=timeout_seconds, kind="test")]

