from __future__ import annotations

import argparse
import datetime as _dt
import textwrap
from pathlib import Path
from typing import Any, Optional

from .agents_md import ensure_agents_md, ensure_gitignore
from .common import (
    SynapseError,
    find_project_root,
    load_defaults,
    slugify,
    synapse_paths,
    unique_path,
    utc_now_iso,
)
from .context_pack import build_context_pack
from .llm import extract_unified_diff, run_model_tasks_parallel, run_model_with_retries
from .state import extract_json_meta, rebuild_index, update_state, upsert_plan_file


def _ensure_layout(project_root: Path):
    from .common import ensure_synapse_layout

    paths = synapse_paths(project_root)
    ensure_synapse_layout(paths)
    return paths


def _last_plan_path(paths) -> Optional[str]:
    from .common import read_json

    try:
        state = read_json(paths.state_json)
    except Exception:
        return None
    if not isinstance(state, dict):
        return None
    last = state.get("last", {})
    if not isinstance(last, dict):
        return None
    if last.get("command") != "plan":
        return None
    plan_path = last.get("plan_path")
    return plan_path if isinstance(plan_path, str) and plan_path else None


def cmd_init(args: argparse.Namespace) -> int:
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    ensure_gitignore(project_root)
    ensure_agents_md(project_root)

    rebuild_index(paths)
    update_state(paths, last={"command": "init", "at": utc_now_iso()})

    print(f"project_root: {project_root}")
    print(f"synapse_dir: {paths.synapse_dir}")
    print(f"state: {paths.state_json}")
    print(f"index: {paths.index_json}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    request = " ".join(args.request).strip()
    if not request:
        raise SynapseError("plan requires a non-empty request")

    slug = slugify(request)
    plan_path = paths.plan_dir / f"{slug}.md"

    context_pack = build_context_pack(paths=paths, defaults=defaults, slug=slug, phase="plan", query=request)

    gemini_prompt = textwrap.dedent(
        f"""
        You are an expert software engineer.

        Constraints:
        - Do NOT use any tools, MCP servers, file access, or external search.
        - Only use the provided context pack.
        - Output must be Markdown only.
        - Do NOT output any code patches in this step.

        Task:
        Produce a step-by-step implementation plan with:
        1) Goals + non-goals
        2) Assumptions (explicit)
        3) Concrete steps with expected outputs
        4) Key files to touch (paths only; if unknown, say "TBD")
        5) Test strategy

        Request:
        {request}

        Context pack:
        {context_pack.read_text(encoding="utf-8")}
        """
    ).strip()

    claude_prompt = textwrap.dedent(
        f"""
        You are an expert software architect.

        Constraints:
        - Do NOT use any tools, MCP servers, file access, or external search.
        - Only use the provided context pack.
        - Output must be Markdown only.
        - Do NOT output any code patches in this step.

        Task:
        Produce an implementation plan focusing on:
        - architecture and boundaries
        - risks, edge cases, and rollback strategy
        - testing strategy

        Request:
        {request}

        Context pack:
        {context_pack.read_text(encoding="utf-8")}
        """
    ).strip()

    runs = run_model_tasks_parallel(
        [
            {
                "model": "gemini",
                "prompt": gemini_prompt,
                "project_root": project_root,
                "resume": args.resume,
                "slug": slug,
                "phase": "plan",
            },
            {
                "model": "claude",
                "prompt": claude_prompt,
                "project_root": project_root,
                "resume": None,
                "slug": slug,
                "phase": "plan",
            },
        ],
        defaults=defaults,
    )

    gemini_run = next((r for r in runs if r.model == "gemini"), None)
    claude_run = next((r for r in runs if r.model == "claude"), None)
    if gemini_run is None:
        raise SynapseError("internal error: missing gemini run result")
    if claude_run is None:
        raise SynapseError("internal error: missing claude run result")

    sessions: dict[str, Any] = {
        "gemini": gemini_run.session_id or "TBD",
        "claude": claude_run.session_id or "TBD",
    }

    gemini_text = gemini_run.output_text.strip() or "(no output from Gemini)"
    claude_text = claude_run.output_text.strip() or "(no output from Claude)"

    plan_text = "\n".join(
        [
            "## Draft (Gemini)",
            "",
            gemini_text,
            "",
            "## Draft (Claude)",
            "",
            claude_text,
            "",
            "## Reconciliation (Codex)",
            "",
            "- Compare the two drafts and reconcile conflicts before implementation.",
            "- Ensure key files list and tests are concrete.",
        ]
    ).strip()

    upsert_plan_file(
        plan_path=plan_path,
        slug=slug,
        request=request,
        context_pack_path=context_pack,
        plan_text=plan_text,
        sessions=sessions,
    )

    gemini_out = unique_path(paths.patches_dir / f"{slug}-plan-gemini.md")
    gemini_out.write_text(gemini_text + "\n", encoding="utf-8", newline="\n")
    claude_out = unique_path(paths.patches_dir / f"{slug}-plan-claude.md")
    claude_out.write_text(claude_text + "\n", encoding="utf-8", newline="\n")

    rebuild_index(paths)
    sessions_by_slug: dict[str, dict[str, str]] = {}
    if gemini_run.session_id:
        sessions_by_slug["gemini"] = {slug: gemini_run.session_id}
    if claude_run.session_id:
        sessions_by_slug["claude"] = {slug: claude_run.session_id}
    update_state(
        paths,
        last={
            "command": "plan",
            "slug": slug,
            "plan_path": str(plan_path),
            "context_pack": str(context_pack),
            "gemini_session_id": gemini_run.session_id,
            "claude_session_id": claude_run.session_id,
            "gemini_output": str(gemini_out),
            "claude_output": str(claude_out),
        },
        sessions_by_slug=sessions_by_slug or None,
    )

    print(f"plan: {plan_path}")
    print(f"context_pack: {context_pack}")
    print(f"gemini_session_id: {gemini_run.session_id or 'TBD'}")
    print(f"claude_session_id: {claude_run.session_id or 'TBD'}")
    print(f"gemini_log: {gemini_run.log_path}")
    print(f"claude_log: {claude_run.log_path}")
    return 0 if gemini_run.exit_code == 0 else 2


def cmd_execute(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    plan_path = Path(args.plan_path)
    if not plan_path.is_absolute():
        plan_path = (project_root / plan_path).resolve()
    if not plan_path.exists():
        raise SynapseError(f"Plan not found: {plan_path}")

    plan_doc = plan_path.read_text(encoding="utf-8")
    meta = extract_json_meta(plan_doc)
    slug = str(meta.get("slug") or plan_path.stem)
    request = str(meta.get("request") or "").strip() or "(request missing in plan meta)"
    sessions = meta.get("sessions") if isinstance(meta.get("sessions"), dict) else {}

    gemini_session: Optional[str] = args.resume
    if not gemini_session:
        s = sessions.get("gemini")
        if isinstance(s, str) and s and s != "TBD":
            gemini_session = s

    context_pack = build_context_pack(paths=paths, defaults=defaults, slug=slug, phase="execute", query=request)

    gemini_prompt = textwrap.dedent(
        f"""
        You are an expert software engineer.

        Constraints:
        - Do NOT use any tools, MCP servers, file access, or external search.
        - Only use the provided plan + context pack.
        - Output MUST be a single Unified Diff patch ONLY.
        - Do not include commentary outside the diff.

        Task:
        Implement the plan. Produce a clean, minimal patch.

        Plan:
        {plan_doc}

        Context pack:
        {context_pack.read_text(encoding="utf-8")}
        """
    ).strip()

    gemini_run = run_model_with_retries(
        model="gemini",
        prompt=gemini_prompt,
        project_root=project_root,
        resume=gemini_session,
        defaults=defaults,
        slug=slug,
        phase="execute",
    )

    gemini_out_md = unique_path(paths.patches_dir / f"{slug}-execute-gemini.md")
    gemini_out_md.write_text(gemini_run.output_text.strip() + "\n", encoding="utf-8", newline="\n")

    diff = extract_unified_diff(gemini_run.output_text or "")
    gemini_out_diff = None
    if diff:
        gemini_out_diff = unique_path(paths.patches_dir / f"{slug}-execute-gemini.diff")
        gemini_out_diff.write_text(diff, encoding="utf-8", newline="\n")

    claude_prompt = textwrap.dedent(
        f"""
        You are a senior code reviewer.

        Constraints:
        - Do NOT use any tools, MCP servers, file access, or external search.
        - Only use the provided context pack + patch.
        - Do NOT propose commands that assume filesystem access.

        Scope:
        Review the patch for correctness, security, edge cases, and maintainability.

        Output:
        1) A prioritized issue list (severity, rationale)
        2) Concrete fixes. If code changes are needed, include a Unified Diff patch in a ```diff fenced block.

        Context pack:
        {context_pack.read_text(encoding="utf-8")}

        Patch:
        {diff or '(no diff extracted; review the text output instead)'}
        """
    ).strip()

    claude_run = run_model_with_retries(
        model="claude",
        prompt=claude_prompt,
        project_root=project_root,
        resume=None,
        defaults=defaults,
        slug=slug,
        phase="audit",
    )

    claude_out_md = unique_path(paths.patches_dir / f"{slug}-execute-claude.md")
    claude_out_md.write_text(claude_run.output_text.strip() + "\n", encoding="utf-8", newline="\n")

    rebuild_index(paths)
    sessions_by_slug: dict[str, dict[str, str]] = {}
    if gemini_run.session_id:
        sessions_by_slug["gemini"] = {slug: gemini_run.session_id}
    if claude_run.session_id:
        sessions_by_slug["claude"] = {slug: claude_run.session_id}
    update_state(
        paths,
        last={
            "command": "execute",
            "slug": slug,
            "plan_path": str(plan_path),
            "context_pack": str(context_pack),
            "gemini_session_id": gemini_run.session_id,
            "gemini_log": str(gemini_run.log_path),
            "gemini_output_md": str(gemini_out_md),
            "gemini_output_diff": str(gemini_out_diff) if gemini_out_diff else None,
            "claude_log": str(claude_run.log_path),
            "claude_output_md": str(claude_out_md),
        },
        sessions_by_slug=sessions_by_slug or None,
    )

    print(f"plan: {plan_path}")
    print(f"context_pack: {context_pack}")
    print(f"gemini_session_id: {gemini_run.session_id or 'TBD'}")
    print(f"gemini_output: {gemini_out_md}")
    print(f"gemini_patch: {gemini_out_diff or '(not extracted)'}")
    print(f"gemini_log: {gemini_run.log_path}")
    print(f"claude_audit: {claude_out_md}")
    print(f"claude_log: {claude_run.log_path}")
    return 0 if gemini_run.exit_code == 0 else 2


def cmd_review(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    slug = _dt.datetime.now().strftime("review-%Y%m%d-%H%M%S")
    context_pack = build_context_pack(paths=paths, defaults=defaults, slug=slug, phase="review", query="git diff review")

    rebuild_index(paths)
    update_state(
        paths,
        last={"command": "review", "slug": slug, "context_pack": str(context_pack), "at": utc_now_iso()},
    )

    print(f"context_pack: {context_pack}")
    print("next: review this diff in Codex (review-only).")
    return 0


def cmd_workflow(args: argparse.Namespace) -> int:
    project_root = find_project_root(Path(args.project_dir))
    cmd_init(argparse.Namespace(project_dir=str(project_root)))

    request = " ".join(args.request).strip()
    if not request:
        raise SynapseError("workflow requires a non-empty request")

    plan_rc = cmd_plan(
        argparse.Namespace(
            project_dir=str(project_root),
            request=[request],
            resume=args.resume,
        )
    )
    if plan_rc != 0:
        return plan_rc

    paths = synapse_paths(project_root)
    plan_path = _last_plan_path(paths)
    if not plan_path:
        print("workflow: unable to locate plan_path from state; stop after plan.")
        return 2

    if not args.yes:
        print("")
        print("workflow: plan completed. Confirm before execute.")
        print(f"next: synapse execute {plan_path}")
        return 0

    exec_rc = cmd_execute(
        argparse.Namespace(
            project_dir=str(project_root),
            plan_path=plan_path,
            resume=args.resume,
        )
    )
    if exec_rc != 0:
        return exec_rc

    cmd_review(argparse.Namespace(project_dir=str(project_root)))
    return 0


def cmd_feat(args: argparse.Namespace) -> int:
    return cmd_workflow(args)
