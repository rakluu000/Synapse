from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class VerifyStep:
    name: str
    argv: list[str]
    cwd: Path
    timeout_seconds: int
    kind: str  # install|lint|typecheck|test|build|other

@dataclass
class VerifyStepResult:
    name: str
    argv: list[str]
    kind: str
    log_path: Optional[str]
    status: str  # OK|FAILED|SKIPPED|BLOCKED|DRY_RUN
    exit_code: Optional[int]
    duration_seconds: Optional[float]
    error: Optional[str]
