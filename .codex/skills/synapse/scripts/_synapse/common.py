from __future__ import annotations

import datetime as _dt
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


class SynapseError(RuntimeError):
    pass


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    safe_mkdir(path.parent)
    path.write_text(content, encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def write_json_atomic(path: Path, data: Any) -> None:
    safe_mkdir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp.write_text(content, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def defaults_path() -> Path:
    # .../scripts/_synapse/common.py -> .../scripts -> .../ (skill root)
    skill_dir = Path(__file__).resolve().parents[2]
    return skill_dir / "assets" / "defaults.json"


def load_defaults() -> dict[str, Any]:
    path = defaults_path()
    if not path.exists():
        raise SynapseError(f"defaults.json not found: {path}")
    data = read_json(path)
    if not isinstance(data, dict) or data.get("version") != 1:
        raise SynapseError(f"Unsupported defaults.json: {path}")
    return data


@dataclass(frozen=True)
class CmdResult:
    code: int
    stdout: str
    stderr: str


def run_cmd(
    argv: list[str],
    *,
    cwd: Optional[Path] = None,
    timeout_seconds: Optional[int] = None,
    check: bool = False,
) -> CmdResult:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=check,
        )
    except FileNotFoundError as e:
        raise SynapseError(f"Command not found: {argv[0]}") from e
    except subprocess.TimeoutExpired as e:
        raise SynapseError(f"Command timed out after {timeout_seconds}s: {' '.join(argv)}") from e
    return CmdResult(code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def find_project_root(project_dir: Path) -> Path:
    project_dir = project_dir.resolve()
    try:
        res = run_cmd(["git", "rev-parse", "--show-toplevel"], cwd=project_dir, timeout_seconds=10)
    except SynapseError:
        return project_dir
    if res.code != 0:
        return project_dir
    root = res.stdout.strip()
    return Path(root).resolve() if root else project_dir


def is_git_repo(project_root: Path) -> bool:
    try:
        res = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=project_root, timeout_seconds=10)
    except SynapseError:
        return False
    return res.code == 0 and res.stdout.strip() == "true"


@dataclass(frozen=True)
class SynapsePaths:
    project_root: Path
    synapse_dir: Path
    plan_dir: Path
    context_dir: Path
    logs_dir: Path
    patches_dir: Path
    prompts_dir: Path
    index_json: Path
    state_json: Path


def synapse_paths(project_root: Path) -> SynapsePaths:
    syn_dir = project_root / ".synapse"
    return SynapsePaths(
        project_root=project_root,
        synapse_dir=syn_dir,
        plan_dir=syn_dir / "plan",
        context_dir=syn_dir / "context",
        logs_dir=syn_dir / "logs",
        patches_dir=syn_dir / "patches",
        prompts_dir=syn_dir / "prompts",
        index_json=syn_dir / "index.json",
        state_json=syn_dir / "state.json",
    )


def ensure_synapse_layout(paths: SynapsePaths) -> None:
    safe_mkdir(paths.plan_dir)
    safe_mkdir(paths.context_dir)
    safe_mkdir(paths.logs_dir)
    safe_mkdir(paths.patches_dir)
    safe_mkdir(paths.prompts_dir)

    if not paths.index_json.exists():
        write_json_atomic(paths.index_json, {"version": 1, "plans": [], "updated_at": utc_now_iso()})

    if not paths.state_json.exists():
        write_json_atomic(
            paths.state_json,
            {
                "version": 1,
                "project_root": str(paths.project_root),
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "last": {},
                "sessions": {"gemini": {"by_slug": {}}, "claude": {"by_slug": {}}},
            },
        )
        return

    state = read_json(paths.state_json)
    if not isinstance(state, dict):
        raise SynapseError(f"Invalid state.json (not an object): {paths.state_json}")
    state.setdefault("version", 1)
    state.setdefault("project_root", str(paths.project_root))
    state.setdefault("created_at", utc_now_iso())
    state["updated_at"] = utc_now_iso()
    state.setdefault("last", {})
    state.setdefault("sessions", {})
    state["sessions"].setdefault("gemini", {"by_slug": {}})
    state["sessions"].setdefault("claude", {"by_slug": {}})
    write_json_atomic(paths.state_json, state)


def slugify(text: str, *, max_len: int = 48) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]+", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    if not text:
        text = "task"
    if len(text) > max_len:
        text = text[:max_len].rstrip("-")
    return text or "task"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for i in range(2, 1000):
        candidate = parent / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise SynapseError(f"Unable to allocate unique path for: {path}")


def truncate_bytes(text: str, max_bytes: int) -> str:
    b = text.encode("utf-8", errors="replace")
    if len(b) <= max_bytes:
        return text
    cut = b[: max_bytes - 10]
    return cut.decode("utf-8", errors="replace") + "\n…(truncated)\n"

