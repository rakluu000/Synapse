from __future__ import annotations
from pathlib import Path
from .types import VerifyStep

def detect_dotnet_steps(project_root: Path, *, timeout_seconds: int) -> list[VerifyStep]:
    if not (any(project_root.glob("*.sln")) or any(project_root.glob("*.csproj")) or any(project_root.glob("*.fsproj"))):
        return []
    return [VerifyStep(name="dotnet:test", argv=["dotnet", "test"], cwd=project_root, timeout_seconds=timeout_seconds, kind="test")]
