from __future__ import annotations

import json
from pathlib import Path

from .types import VerifyStep


def _read_package_json_scripts(project_root: Path) -> dict[str, str]:
    p = project_root / "package.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    scripts = data.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def _pick_node_pm(project_root: Path) -> tuple[str, list[str]]:
    if (project_root / "pnpm-lock.yaml").exists():
        return ("pnpm", ["pnpm", "install", "--frozen-lockfile"])
    if (project_root / "yarn.lock").exists():
        return ("yarn", ["yarn", "install", "--frozen-lockfile"])
    if (project_root / "package-lock.json").exists():
        return ("npm", ["npm", "ci"])
    return ("npm", ["npm", "install"])


def _node_run_argv(pm: str, script: str) -> list[str]:
    if pm == "npm":
        return ["npm", "run", script]
    if pm == "pnpm":
        return ["pnpm", "run", script]
    if pm == "yarn":
        return ["yarn", "run", script]
    return [pm, "run", script]


def detect_node_steps(project_root: Path, *, timeout_seconds: int, no_install: bool) -> list[VerifyStep]:
    if not (project_root / "package.json").exists():
        return []

    steps: list[VerifyStep] = []
    pm, install_argv = _pick_node_pm(project_root)
    if not no_install:
        steps.append(VerifyStep(name=f"node:{pm}:install", argv=install_argv, cwd=project_root, timeout_seconds=timeout_seconds, kind="install"))

    scripts = _read_package_json_scripts(project_root)
    for s in ("lint", "typecheck", "test"):
        if s in scripts:
            steps.append(
                VerifyStep(
                    name=f"node:{pm}:{s}",
                    argv=_node_run_argv(pm, s),
                    cwd=project_root,
                    timeout_seconds=timeout_seconds,
                    kind="test" if s == "test" else s,
                )
            )
    return steps

