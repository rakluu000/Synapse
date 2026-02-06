from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Optional

from .common import SynapseError, find_project_root, load_defaults, slugify, synapse_paths, unique_path
from .context_pack import build_context_pack
from .llm import extract_unified_diff, run_model_with_retries
from .state import rebuild_index, update_state


def _ensure_layout(project_root: Path):
    from .common import ensure_synapse_layout

    paths = synapse_paths(project_root)
    ensure_synapse_layout(paths)
    return paths


def cmd_frontend(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    request = " ".join(args.request).strip()
    if not request:
        raise SynapseError("frontend requires a non-empty request")
    slug = slugify(request)

    context_pack = build_context_pack(paths=paths, defaults=defaults, slug=slug, phase="frontend", query=request)

    prompt = textwrap.dedent(
        f"""
        You are a UI/Frontend expert engineer.

        Constraints:
        - Do NOT use any tools, MCP servers, file access, or external search.
        - Only use the provided context pack.
        - Output MUST be a single Unified Diff patch ONLY.
        - Do not include commentary outside the diff.

        Request:
        {request}

        Context pack:
        {context_pack.read_text(encoding="utf-8")}
        """
    ).strip()

    gemini_run = run_model_with_retries(
        model="gemini",
        prompt=prompt,
        project_root=project_root,
        resume=args.resume,
        defaults=defaults,
        slug=slug,
        phase="frontend",
    )

    out_md = unique_path(paths.patches_dir / f"{slug}-frontend-gemini.md")
    out_md.write_text(gemini_run.output_text.strip() + "\n", encoding="utf-8", newline="\n")

    diff = extract_unified_diff(gemini_run.output_text or "")
    out_diff = None
    if diff:
        out_diff = unique_path(paths.patches_dir / f"{slug}-frontend-gemini.diff")
        out_diff.write_text(diff, encoding="utf-8", newline="\n")

    rebuild_index(paths)
    sessions_by_slug = {"gemini": {slug: gemini_run.session_id}} if gemini_run.session_id else None
    update_state(
        paths,
        last={
            "command": "frontend",
            "slug": slug,
            "context_pack": str(context_pack),
            "gemini_session_id": gemini_run.session_id,
            "output_md": str(out_md),
            "output_diff": str(out_diff) if out_diff else None,
        },
        sessions_by_slug=sessions_by_slug,
    )

    print(f"context_pack: {context_pack}")
    print(f"gemini_session_id: {gemini_run.session_id or 'TBD'}")
    print(f"output: {out_md}")
    print(f"patch: {out_diff or '(not extracted)'}")
    return 0 if gemini_run.exit_code == 0 else 2


def cmd_backend(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    request = " ".join(args.request).strip()
    if not request:
        raise SynapseError("backend requires a non-empty request")
    slug = slugify(request)

    context_pack = build_context_pack(paths=paths, defaults=defaults, slug=slug, phase="backend", query=request)
    task_path = unique_path(paths.patches_dir / f"{slug}-backend-task.md")
    task = "\n".join(
        [
            f"# Backend task: `{slug}`",
            "",
            f"Request: {request}",
            "",
            "## Inputs",
            f"- Context pack: `{context_pack}`",
            "",
            "## Constraints",
            "- Prefer minimal, targeted changes.",
            "- Follow existing project conventions.",
            "",
        ]
    )
    task_path.write_text(task, encoding="utf-8", newline="\n")

    rebuild_index(paths)
    update_state(
        paths,
        last={
            "command": "backend",
            "slug": slug,
            "context_pack": str(context_pack),
            "task_path": str(task_path),
        },
    )

    print(f"context_pack: {context_pack}")
    print(f"task: {task_path}")
    return 0


def _claude_text_task(args: argparse.Namespace, *, phase: str, title: str, want_patch: bool) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    request = " ".join(args.request).strip()
    if not request:
        raise SynapseError(f"{phase} requires a non-empty request")
    slug = slugify(request)

    context_pack = build_context_pack(paths=paths, defaults=defaults, slug=slug, phase=phase, query=request)

    output_spec = (
        "If code changes are needed, include a Unified Diff patch in a ```diff fenced block."
        if want_patch
        else "Do NOT output code patches unless explicitly requested."
    )

    prompt = textwrap.dedent(
        f"""
        You are {title}.

        Constraints:
        - Do NOT use any tools, MCP servers, file access, or external search.
        - Only use the provided context pack.

        Request:
        {request}

        Output:
        - Provide a structured, actionable answer.
        - {output_spec}

        Context pack:
        {context_pack.read_text(encoding="utf-8")}
        """
    ).strip()

    run = run_model_with_retries(
        model="claude",
        prompt=prompt,
        project_root=project_root,
        resume=args.resume,
        defaults=defaults,
        slug=slug,
        phase=phase,
    )

    out_md = unique_path(paths.patches_dir / f"{slug}-{phase}-claude.md")
    out_md.write_text(run.output_text.strip() + "\n", encoding="utf-8", newline="\n")

    out_diff = None
    if want_patch:
        diff = extract_unified_diff(run.output_text or "")
        if diff:
            out_diff = unique_path(paths.patches_dir / f"{slug}-{phase}-claude.diff")
            out_diff.write_text(diff, encoding="utf-8", newline="\n")

    rebuild_index(paths)
    sessions_by_slug = {"claude": {slug: run.session_id}} if run.session_id else None
    update_state(
        paths,
        last={
            "command": phase,
            "slug": slug,
            "context_pack": str(context_pack),
            "claude_session_id": run.session_id,
            "output_md": str(out_md),
            "output_diff": str(out_diff) if out_diff else None,
        },
        sessions_by_slug=sessions_by_slug,
    )

    print(f"context_pack: {context_pack}")
    print(f"claude_session_id: {run.session_id or 'TBD'}")
    print(f"output: {out_md}")
    if want_patch:
        print(f"patch: {out_diff or '(not extracted)'}")
    return 0 if run.exit_code == 0 else 2


def cmd_analyze(args: argparse.Namespace) -> int:
    return _claude_text_task(args, phase="analyze", title="a technical architect and analyst", want_patch=False)


def cmd_debug(args: argparse.Namespace) -> int:
    return _claude_text_task(args, phase="debug", title="a debugging expert", want_patch=False)


def cmd_optimize(args: argparse.Namespace) -> int:
    return _claude_text_task(args, phase="optimize", title="a performance and quality optimization expert", want_patch=True)


def cmd_test(args: argparse.Namespace) -> int:
    return _claude_text_task(args, phase="test", title="a testing expert", want_patch=True)


def cmd_enhance(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    request = " ".join(args.request).strip()
    if not request:
        raise SynapseError("enhance requires a non-empty request")
    slug = slugify(request)

    prompt = textwrap.dedent(
        f"""
        You are a prompt engineer.

        Constraints:
        - Do NOT use any tools, MCP servers, file access, or external search.
        - Output must be Markdown.

        Task:
        Rewrite the user's request into an execution-ready task spec with:
        - Goal
        - Non-goals
        - Acceptance criteria
        - Constraints/assumptions
        - Suggested plan outline (high level)

        User request:
        {request}
        """
    ).strip()

    run = run_model_with_retries(
        model="claude",
        prompt=prompt,
        project_root=project_root,
        resume=args.resume,
        defaults=defaults,
        slug=slug,
        phase="enhance",
    )

    out_md = unique_path(paths.patches_dir / f"{slug}-enhance-claude.md")
    out_md.write_text(run.output_text.strip() + "\n", encoding="utf-8", newline="\n")

    rebuild_index(paths)
    sessions_by_slug = {"claude": {slug: run.session_id}} if run.session_id else None
    update_state(
        paths,
        last={"command": "enhance", "slug": slug, "output_md": str(out_md), "claude_session_id": run.session_id},
        sessions_by_slug=sessions_by_slug,
    )

    print(f"output: {out_md}")
    return 0 if run.exit_code == 0 else 2

