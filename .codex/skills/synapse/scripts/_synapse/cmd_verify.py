from __future__ import annotations

import argparse
import datetime as _dt
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from .common import (
    SynapseError,
    find_project_root,
    load_defaults,
    run_cmd,
    slugify,
    synapse_paths,
    unique_path,
    utc_now_iso,
)
from .state import rebuild_index, update_state


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


def _ensure_layout(project_root: Path):
    from .common import ensure_synapse_layout

    paths = synapse_paths(project_root)
    ensure_synapse_layout(paths)
    return paths


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


def _detect_steps(project_root: Path, *, defaults: dict[str, Any], no_install: bool) -> list[VerifyStep]:
    runner = defaults.get("runner", {})
    timeout_seconds = int(runner.get("timeout_seconds", 3600))

    steps: list[VerifyStep] = []

    # Node
    if (project_root / "package.json").exists():
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

    # Python (uv only)
    has_pyproject = (project_root / "pyproject.toml").exists()
    has_reqs = (project_root / "requirements.txt").exists()
    if has_pyproject or has_reqs:
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

    # Rust
    if (project_root / "Cargo.toml").exists():
        steps.append(VerifyStep(name="rust:test", argv=["cargo", "test"], cwd=project_root, timeout_seconds=timeout_seconds, kind="test"))

    # Go
    if (project_root / "go.mod").exists():
        steps.append(VerifyStep(name="go:test", argv=["go", "test", "./..."], cwd=project_root, timeout_seconds=timeout_seconds, kind="test"))

    # .NET
    if list(project_root.glob("*.sln")) or list(project_root.glob("*.csproj")) or list(project_root.glob("*.fsproj")):
        steps.append(VerifyStep(name="dotnet:test", argv=["dotnet", "test"], cwd=project_root, timeout_seconds=timeout_seconds, kind="test"))

    return steps


def _write_verify_log(log_path: Path, *, step: VerifyStep, exit_code: Optional[int], stdout: str, stderr: str, error: Optional[str]) -> None:
    parts: list[str] = []
    parts.append(f"step: {step.name}")
    parts.append(f"kind: {step.kind}")
    parts.append(f"cwd: {step.cwd}")
    parts.append(f"argv: {' '.join(step.argv)}")
    if exit_code is not None:
        parts.append(f"exit_code: {exit_code}")
    if error:
        parts.append(f"error: {error}")
    parts.append("")
    if stdout:
        parts.append("### STDOUT")
        parts.append(stdout.rstrip())
        parts.append("")
    if stderr:
        parts.append("### STDERR")
        parts.append(stderr.rstrip())
        parts.append("")
    log_path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8", newline="\n")


def cmd_verify(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    dry_run = bool(getattr(args, "dry_run", False))
    no_install = bool(getattr(args, "no_install", False))
    keep_going = bool(getattr(args, "keep_going", False))

    steps = _detect_steps(project_root, defaults=defaults, no_install=no_install)
    if not steps:
        print("verify: no recognizable toolchain found (nothing to run).")
        update_state(paths, last={"command": "verify", "at": utc_now_iso(), "results": [], "note": "no steps"})
        return 0

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    results: list[VerifyStepResult] = []

    print("verify: planned_steps:")
    for s in steps:
        print(f"- {s.name}: {' '.join(s.argv)}")

    if dry_run:
        for s in steps:
            results.append(
                VerifyStepResult(
                    name=s.name,
                    argv=s.argv,
                    kind=s.kind,
                    log_path=None,
                    status="DRY_RUN",
                    exit_code=None,
                    duration_seconds=None,
                    error=None,
                )
            )
        rebuild_index(paths)
        update_state(paths, last={"command": "verify", "at": utc_now_iso(), "dry_run": True, "results": [asdict(r) for r in results]})
        return 0

    ok = True
    for step in steps:
        log_name = f"{ts}-verify-{slugify(step.name)}.log"
        log_path = unique_path(paths.logs_dir / log_name)

        start = time.time()
        exit_code: Optional[int] = None
        stdout = ""
        stderr = ""
        error: Optional[str] = None

        try:
            res = run_cmd(step.argv, cwd=step.cwd, timeout_seconds=step.timeout_seconds)
            exit_code = res.code
            stdout = res.stdout
            stderr = res.stderr
            status = "OK" if res.code == 0 else "FAILED"
            if res.code != 0:
                ok = False
        except SynapseError as e:
            ok = False
            status = "BLOCKED"
            error = str(e)

        duration = time.time() - start
        try:
            _write_verify_log(log_path, step=step, exit_code=exit_code, stdout=stdout, stderr=stderr, error=error)
        except Exception as e:
            # If logging fails, still report the primary error.
            error = (error + " | " if error else "") + f"log_error: {type(e).__name__}: {e}"

        results.append(
            VerifyStepResult(
                name=step.name,
                argv=step.argv,
                kind=step.kind,
                log_path=str(log_path),
                status=status,
                exit_code=exit_code,
                duration_seconds=duration,
                error=error,
            )
        )

        print(f"verify: {step.name}: {status} ({duration:.1f}s) -> {log_path}")

        if status != "OK" and not keep_going:
            break

    rebuild_index(paths)
    update_state(
        paths,
        last={
            "command": "verify",
            "at": utc_now_iso(),
            "results": [asdict(r) for r in results],
        },
    )

    return 0 if ok else 2

