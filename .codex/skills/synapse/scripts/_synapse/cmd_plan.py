from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .common import (
    SynapseError,
    find_project_root,
    load_defaults,
    slugify,
    synapse_paths,
    utc_now_iso,
)
from .context_pack import build_context_pack
from .state import rebuild_index, update_state, upsert_plan_file


def _gate_stub(*, request: str) -> str:
    return "\n".join(
        [
            "## Gate (Codex) — single confirmation point",
            "",
            "Confirm these once after reviewing the drafts (scope + decisions + side effects).",
            "",
            "### Required confirmations",
            "",
            "- [ ] Scope and acceptance criteria are correct (no missing requirements).",
            "- [ ] `task_type` selection is confirmed:",
            "  - Options: `frontend` / `backend` / `fullstack`",
            "  - Codex recommendation: (fill in)  |  User choice: (fill in)",
            "- [ ] Stack/toolchain choice is confirmed (or explicitly TBD).",
            "- [ ] Allowed side effects are confirmed:",
            "  - [ ] Install dependencies (project-local).",
            "  - [ ] Generate/update lockfiles (project-local).",
            "  - [ ] Create toolchain artifacts (e.g., `.venv/`, `node_modules/`, build outputs).",
            "- [ ] Git/review setup is confirmed:",
            "  - [ ] Ensure this is a git repo (`git init` if needed).",
            "  - [ ] Before review: run `git add -N .` so new files appear in `git diff`.",
            "- [ ] Verification plan is confirmed (what `synapse verify` will run after applying code).",
            "",
            "### Open questions (fill in; keep short)",
            "",
            "- Q1: (if any)",
            "",
            "### Next steps (after Gate is confirmed)",
            "",
            "- Generate draft diffs via `synapse run ...` (Claude/Gemini).",
            "- Codex applies final code changes (rewrite drafts into production quality).",
            "- Run: `synapse verify`",
            "- Build a review context pack via `synapse pack --phase review ...`, then run audits via `synapse run ...`.",
            "",
        ]
    ).strip()


def cmd_plan(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = synapse_paths(project_root)

    from .common import ensure_synapse_layout

    ensure_synapse_layout(paths)

    request = " ".join(args.request).strip()
    if not request:
        raise SynapseError("plan requires a non-empty request")

    task_type = getattr(args, "task_type", None) or "fullstack"
    if task_type not in ("frontend", "backend", "fullstack"):
        task_type = "fullstack"

    slug = getattr(args, "slug", None) or slugify(request)
    plan_path = paths.plan_dir / f"{slug}.md"

    rg_queries = list(getattr(args, "rg_query", []) or [])
    include_files_raw = list(getattr(args, "include_file", []) or [])
    include_files: list[Path] = []
    for p in include_files_raw:
        pp = Path(p)
        include_files.append(pp if pp.is_absolute() else (project_root / pp).resolve())

    context_pack: Optional[Path] = None
    if not bool(getattr(args, "no_pack", False)):
        context_pack = build_context_pack(
            paths=paths,
            defaults=defaults,
            slug=slug,
            phase="plan",
            query=request,
            rg_queries=rg_queries if rg_queries else None,
            include_files=include_files if include_files else None,
        )

    plan_text = "\n".join(
        [
            "## Draft (Claude)",
            "",
            "(TBD: run `synapse run --model claude ...` and paste/summarize here.)",
            "",
            "## Draft (Gemini)",
            "",
            "(TBD: run `synapse run --model gemini ...` and paste/summarize here; skip if backend-only.)",
            "",
            _gate_stub(request=request),
        ]
    ).strip()

    upsert_plan_file(
        plan_path=plan_path,
        slug=str(slug),
        request=request,
        context_pack_path=context_pack,
        plan_text=plan_text,
        sessions={},
        extra={"task_type": task_type},
    )

    rebuild_index(paths)
    update_state(
        paths,
        last={
            "command": "plan",
            "slug": slug,
            "task_type": task_type,
            "plan_path": str(plan_path),
            "context_pack": str(context_pack) if context_pack else None,
            "at": utc_now_iso(),
        },
    )

    print(f"slug: {slug}")
    print(f"task_type: {task_type}")
    print(f"plan: {plan_path}")
    if context_pack:
        print(f"context_pack: {context_pack}")
    return 0
