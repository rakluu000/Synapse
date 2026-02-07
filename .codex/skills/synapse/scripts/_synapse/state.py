from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from .common import SynapsePaths, WriteGuard, read_json, read_text, utc_now_iso, write_json_atomic, write_text


def extract_json_meta(markdown: str) -> dict[str, Any]:
    m = re.search(r"```json[ \t]*\r?\n(\{.*?\})[ \t]*\r?\n```", markdown, flags=re.DOTALL)
    if not m:
        return {}
    try:
        meta = json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}
    return meta if isinstance(meta, dict) else {}


def upsert_plan_file(
    *,
    plan_path: Path,
    slug: str,
    request: str,
    context_pack_path: Optional[Path],
    plan_text: str,
    sessions: dict[str, Any],
    extra: Optional[dict[str, Any]] = None,
    guard: WriteGuard | None = None,
) -> None:
    meta: dict[str, Any] = {
        "synapse_version": 1,
        "slug": slug,
        "created_at": utc_now_iso(),
        "request": request,
        "context_pack": str(context_pack_path) if context_pack_path else None,
        "sessions": sessions,
    }
    if extra:
        meta.update(extra)

    doc = "\n".join(
        [
            f"# Plan: `{slug}`",
            "",
            "## Synapse Meta",
            "",
            "```json",
            json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "## Request",
            "",
            request.strip(),
            "",
            "## Plan",
            "",
            plan_text.strip() or "(empty)",
            "",
        ]
    )
    write_text(plan_path, doc, guard=guard)


def _replace_json_meta(markdown: str, meta: dict[str, Any]) -> str:
    block = "\n".join(["```json", json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True), "```"])
    pattern = re.compile(r"```json[ \t]*\r?\n(\{.*?\})[ \t]*\r?\n```", flags=re.DOTALL)
    if not pattern.search(markdown):
        raise ValueError("plan file is missing json meta block")
    # Use a function replacement to avoid backslash escapes in replacement strings.
    return pattern.sub(lambda _m: block, markdown, count=1)


def update_plan_session(*, plan_path: Path, model: str, session_id: str, guard: WriteGuard | None = None) -> None:
    if model not in ("gemini", "claude"):
        return
    text = read_text(plan_path)
    meta = extract_json_meta(text)
    if not meta:
        raise ValueError("plan file json meta could not be parsed")
    sessions = meta.get("sessions")
    if not isinstance(sessions, dict):
        sessions = {}
    sessions[model] = session_id
    meta["sessions"] = sessions
    write_text(plan_path, _replace_json_meta(text, meta), guard=guard)


def update_state(
    paths: SynapsePaths,
    *,
    last: dict[str, Any],
    sessions_by_slug: Optional[dict[str, dict[str, str]]] = None,
    guard: WriteGuard | None = None,
) -> None:
    state = read_json(paths.state_json)
    if not isinstance(state, dict):
        state = {}
    state.setdefault("version", 1)
    state["project_root"] = str(paths.project_root)
    state["updated_at"] = utc_now_iso()
    state["last"] = last
    state.setdefault("sessions", {"gemini": {"by_slug": {}}, "claude": {"by_slug": {}}})
    for model in ("gemini", "claude"):
        state["sessions"].setdefault(model, {"by_slug": {}})

    if sessions_by_slug:
        for model, mapping in sessions_by_slug.items():
            state["sessions"].setdefault(model, {"by_slug": {}})
            by_slug = state["sessions"][model].setdefault("by_slug", {})
            if isinstance(by_slug, dict):
                by_slug.update(mapping)

    write_json_atomic(paths.state_json, state, guard=guard)


def rebuild_index(paths: SynapsePaths, *, guard: WriteGuard | None = None) -> None:
    plans: list[dict[str, Any]] = []
    for p in sorted(paths.plan_dir.glob("*.md")):
        try:
            meta = extract_json_meta(read_text(p))
        except Exception:
            meta = {}
        slug = meta.get("slug") or p.stem
        sessions = meta.get("sessions") if isinstance(meta.get("sessions"), dict) else {}
        plans.append(
            {
                "slug": slug,
                "path": str(p),
                "created_at": meta.get("created_at"),
                "sessions": sessions,
            }
        )
    write_json_atomic(paths.index_json, {"version": 1, "updated_at": utc_now_iso(), "plans": plans}, guard=guard)
