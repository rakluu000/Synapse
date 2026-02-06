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


def _infer_plan_path(paths) -> Optional[str]:
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

    task_type = getattr(args, "task_type", None) or "fullstack"
    if task_type not in ("frontend", "backend", "fullstack"):
        task_type = "fullstack"
    want_frontend = task_type in ("frontend", "fullstack")

    slug = slugify(request)
    plan_path = paths.plan_dir / f"{slug}.md"

    context_pack = build_context_pack(paths=paths, defaults=defaults, slug=slug, phase="plan", query=request)

    claude_prompt = textwrap.dedent(
        f"""
        You are an expert software architect and tech lead.

        Constraints:
        - Do NOT use any tools, MCP servers, file access, or external search.
        - Only use the provided context pack.
        - Output must be Markdown only.
        - Do NOT output any code patches in this step.

        Task:
        Produce an implementation plan focusing on:
        - architecture and boundaries
        - risks, edge cases, and rollback strategy
        - testing strategy (with concrete commands if possible)
        - the intended task_type routing hint: {task_type}

        Request:
        {request}

        Context pack:
        {context_pack.read_text(encoding="utf-8")}
        """
    ).strip()

    tasks: list[dict[str, Any]] = [
        {
            "model": "claude",
            "prompt": claude_prompt,
            "project_root": project_root,
            "resume": getattr(args, "resume_claude", None),
            "slug": slug,
            "phase": "plan",
        }
    ]
    if want_frontend:
        gemini_prompt = textwrap.dedent(
            f"""
            You are a UI/Frontend expert engineer.

            Constraints:
            - Do NOT use any tools, MCP servers, file access, or external search.
            - Only use the provided context pack.
            - Output must be Markdown only.
            - Do NOT output any code patches in this step.

            Task:
            Produce a frontend/UI implementation plan with:
            1) UX goals + non-goals
            2) UI states/edge cases
            3) Concrete steps with expected outputs
            4) Key files to touch (paths only; if unknown, say "TBD")
            5) Test strategy (unit/e2e) + accessibility checklist

            Request:
            {request}

            Context pack:
            {context_pack.read_text(encoding="utf-8")}
            """
        ).strip()
        tasks.append(
            {
                "model": "gemini",
                "prompt": gemini_prompt,
                "project_root": project_root,
                "resume": getattr(args, "resume_gemini", None),
                "slug": slug,
                "phase": "plan",
            }
        )

    runs = run_model_tasks_parallel(tasks, defaults=defaults)

    claude_run = next((r for r in runs if r.model == "claude"), None)
    if claude_run is None:
        raise SynapseError("internal error: missing claude run result")
    gemini_run = next((r for r in runs if r.model == "gemini"), None)

    sessions: dict[str, Any] = {"claude": claude_run.session_id or "TBD"}
    if want_frontend:
        sessions["gemini"] = (gemini_run.session_id if gemini_run else None) or "TBD"

    claude_text = claude_run.output_text.strip() or "(no output from Claude)"
    gemini_text = "(skipped: task_type=backend)" if not want_frontend else (gemini_run.output_text.strip() if gemini_run else "") or "(no output from Gemini)"

    plan_text = "\n".join(
        [
            "## Draft (Claude)",
            "",
            claude_text,
            "",
            "## Draft (Gemini)",
            "",
            gemini_text,
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
        extra={"task_type": task_type},
    )

    claude_out = unique_path(paths.patches_dir / f"{slug}-plan-claude.md")
    claude_out.write_text(claude_text + "\n", encoding="utf-8", newline="\n")
    gemini_out = None
    if want_frontend:
        gemini_out = unique_path(paths.patches_dir / f"{slug}-plan-gemini.md")
        gemini_out.write_text(gemini_text + "\n", encoding="utf-8", newline="\n")

    rebuild_index(paths)
    sessions_by_slug: dict[str, dict[str, str]] = {}
    if gemini_run and gemini_run.session_id:
        sessions_by_slug["gemini"] = {slug: gemini_run.session_id}
    if claude_run.session_id:
        sessions_by_slug["claude"] = {slug: claude_run.session_id}
    update_state(
        paths,
        last={
            "command": "plan",
            "slug": slug,
            "task_type": task_type,
            "plan_path": str(plan_path),
            "context_pack": str(context_pack),
            "gemini_session_id": gemini_run.session_id if gemini_run else None,
            "claude_session_id": claude_run.session_id,
            "gemini_output": str(gemini_out) if gemini_out else None,
            "claude_output": str(claude_out),
        },
        sessions_by_slug=sessions_by_slug or None,
    )

    print(f"plan: {plan_path}")
    print(f"context_pack: {context_pack}")
    if want_frontend:
        print(f"gemini_session_id: {gemini_run.session_id if gemini_run else None or 'TBD'}")
    print(f"claude_session_id: {claude_run.session_id or 'TBD'}")
    if want_frontend and gemini_run:
        print(f"gemini_log: {gemini_run.log_path}")
    print(f"claude_log: {claude_run.log_path}")
    return 0 if all(r.exit_code == 0 for r in runs) else 2


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
    task_type = str(meta.get("task_type") or "fullstack")
    if task_type not in ("frontend", "backend", "fullstack"):
        task_type = "fullstack"
    sessions = meta.get("sessions") if isinstance(meta.get("sessions"), dict) else {}

    want_frontend = task_type in ("frontend", "fullstack")
    want_backend = task_type in ("backend", "fullstack")

    gemini_session: Optional[str] = getattr(args, "resume_gemini", None)
    if want_frontend and not gemini_session:
        s = sessions.get("gemini")
        if isinstance(s, str) and s and s != "TBD":
            gemini_session = s

    claude_session: Optional[str] = getattr(args, "resume_claude", None)
    if want_backend and not claude_session:
        s = sessions.get("claude")
        if isinstance(s, str) and s and s != "TBD":
            claude_session = s

    context_pack = build_context_pack(paths=paths, defaults=defaults, slug=slug, phase="execute", query=request)

    tasks: list[dict[str, Any]] = []
    if want_frontend:
        gemini_prompt = textwrap.dedent(
            f"""
            You are a UI/Frontend expert engineer.

            Constraints:
            - Do NOT use any tools, MCP servers, file access, or external search.
            - Only use the provided plan + context pack.
            - Output MUST be a single Unified Diff patch ONLY.
            - Do not include commentary outside the diff.

            Task:
            Implement ONLY the frontend/UI parts of the plan. Produce a clean, minimal patch.

            Plan:
            {plan_doc}

            Context pack:
            {context_pack.read_text(encoding="utf-8")}
            """
        ).strip()
        tasks.append(
            {
                "model": "gemini",
                "prompt": gemini_prompt,
                "project_root": project_root,
                "resume": gemini_session,
                "slug": slug,
                "phase": "execute",
            }
        )

    if want_backend:
        claude_prompt = textwrap.dedent(
            f"""
            You are a backend/infra expert engineer.

            Constraints:
            - Do NOT use any tools, MCP servers, file access, or external search.
            - Only use the provided plan + context pack.
            - Output MUST be a single Unified Diff patch ONLY.
            - Do not include commentary outside the diff.

            Task:
            Implement ONLY the backend/logic parts of the plan. Produce a clean, minimal patch.

            Plan:
            {plan_doc}

            Context pack:
            {context_pack.read_text(encoding="utf-8")}
            """
        ).strip()
        tasks.append(
            {
                "model": "claude",
                "prompt": claude_prompt,
                "project_root": project_root,
                "resume": claude_session,
                "slug": slug,
                "phase": "execute",
            }
        )

    if not tasks:
        raise SynapseError(f"execute: unsupported task_type: {task_type}")

    runs = run_model_tasks_parallel(tasks, defaults=defaults)
    gemini_run = next((r for r in runs if r.model == "gemini"), None)
    claude_run = next((r for r in runs if r.model == "claude"), None)

    gemini_out_md = None
    gemini_out_diff = None
    if gemini_run:
        gemini_out_md = unique_path(paths.patches_dir / f"{slug}-execute-draft-gemini.md")
        gemini_out_md.write_text(gemini_run.output_text.strip() + "\n", encoding="utf-8", newline="\n")
        diff = extract_unified_diff(gemini_run.output_text or "")
        if diff:
            gemini_out_diff = unique_path(paths.patches_dir / f"{slug}-execute-draft-gemini.diff")
            gemini_out_diff.write_text(diff, encoding="utf-8", newline="\n")

    claude_out_md = None
    claude_out_diff = None
    if claude_run:
        claude_out_md = unique_path(paths.patches_dir / f"{slug}-execute-draft-claude.md")
        claude_out_md.write_text(claude_run.output_text.strip() + "\n", encoding="utf-8", newline="\n")
        diff = extract_unified_diff(claude_run.output_text or "")
        if diff:
            claude_out_diff = unique_path(paths.patches_dir / f"{slug}-execute-draft-claude.diff")
            claude_out_diff.write_text(diff, encoding="utf-8", newline="\n")

    rebuild_index(paths)
    sessions_by_slug: dict[str, dict[str, str]] = {}
    if gemini_run and gemini_run.session_id:
        sessions_by_slug["gemini"] = {slug: gemini_run.session_id}
    if claude_run and claude_run.session_id:
        sessions_by_slug["claude"] = {slug: claude_run.session_id}
    update_state(
        paths,
        last={
            "command": "execute",
            "slug": slug,
            "task_type": task_type,
            "plan_path": str(plan_path),
            "context_pack": str(context_pack),
            "gemini_session_id": gemini_run.session_id if gemini_run else None,
            "gemini_log": str(gemini_run.log_path) if gemini_run else None,
            "gemini_output_md": str(gemini_out_md) if gemini_out_md else None,
            "gemini_output_diff": str(gemini_out_diff) if gemini_out_diff else None,
            "claude_session_id": claude_run.session_id if claude_run else None,
            "claude_log": str(claude_run.log_path) if claude_run else None,
            "claude_output_md": str(claude_out_md) if claude_out_md else None,
            "claude_output_diff": str(claude_out_diff) if claude_out_diff else None,
        },
        sessions_by_slug=sessions_by_slug or None,
    )

    print(f"plan: {plan_path}")
    print(f"context_pack: {context_pack}")
    print(f"task_type: {task_type}")
    if gemini_run:
        print(f"gemini_session_id: {gemini_run.session_id or 'TBD'}")
        print(f"gemini_output: {gemini_out_md}")
        print(f"gemini_patch: {gemini_out_diff or '(not extracted)'}")
        print(f"gemini_log: {gemini_run.log_path}")
    if claude_run:
        print(f"claude_session_id: {claude_run.session_id or 'TBD'}")
        print(f"claude_output: {claude_out_md}")
        print(f"claude_patch: {claude_out_diff or '(not extracted)'}")
        print(f"claude_log: {claude_run.log_path}")
    return 0 if all(r.exit_code == 0 for r in runs) else 2


def cmd_review(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    plan_path: Optional[Path] = None
    if getattr(args, "plan_path", None):
        p = Path(args.plan_path)
        plan_path = p if p.is_absolute() else (project_root / p).resolve()
        if not plan_path.exists():
            raise SynapseError(f"Plan not found: {plan_path}")
    else:
        inferred = _infer_plan_path(paths)
        if inferred:
            p = Path(inferred)
            plan_path = p if p.is_absolute() else (project_root / p).resolve()
            if plan_path and not plan_path.exists():
                plan_path = None

    inferred_slug: Optional[str] = None
    inferred_task_type: Optional[str] = None
    if plan_path and plan_path.exists():
        plan_doc = plan_path.read_text(encoding="utf-8")
        meta = extract_json_meta(plan_doc)
        inferred_slug = str(meta.get("slug") or plan_path.stem)
        tt = meta.get("task_type")
        inferred_task_type = str(tt) if isinstance(tt, str) else None

    task_type = getattr(args, "task_type", None) or inferred_task_type or "fullstack"
    if task_type not in ("frontend", "backend", "fullstack"):
        task_type = "fullstack"
    want_frontend = task_type in ("frontend", "fullstack")

    slug = inferred_slug or _dt.datetime.now().strftime("review-%Y%m%d-%H%M%S")
    context_pack = build_context_pack(paths=paths, defaults=defaults, slug=slug, phase="review", query="git diff review")

    claude_prompt = textwrap.dedent(
        f"""
        You are a senior code auditor.

        Constraints:
        - Do NOT use any tools, MCP servers, file access, or external search.
        - Only use the provided context pack.

        Scope:
        Audit the current git diff for correctness, security, edge cases, and maintainability.

        Output:
        1) A prioritized issue list (severity, rationale)
        2) Concrete fixes. If code changes are needed, include a Unified Diff patch in a ```diff fenced block.

        Context pack:
        {context_pack.read_text(encoding="utf-8")}
        """
    ).strip()

    tasks: list[dict[str, Any]] = [
        {
            "model": "claude",
            "prompt": claude_prompt,
            "project_root": project_root,
            "resume": None,
            "slug": slug,
            "phase": "review",
        }
    ]

    if want_frontend:
        gemini_prompt = textwrap.dedent(
            f"""
            You are a UI/UX and accessibility reviewer.

            Constraints:
            - Do NOT use any tools, MCP servers, file access, or external search.
            - Only use the provided context pack.

            Scope:
            Review the current git diff focusing on UI/UX consistency, accessibility, and design quality.

            Output:
            - A prioritized issue list (severity, rationale)
            - Concrete fixes (no need to include full code unless necessary; if patch is needed, include a Unified Diff in a ```diff fenced block)

            Context pack:
            {context_pack.read_text(encoding="utf-8")}
            """
        ).strip()
        tasks.append(
            {
                "model": "gemini",
                "prompt": gemini_prompt,
                "project_root": project_root,
                "resume": None,
                "slug": slug,
                "phase": "review",
            }
        )

    runs = run_model_tasks_parallel(tasks, defaults=defaults)
    claude_run = next((r for r in runs if r.model == "claude"), None)
    gemini_run = next((r for r in runs if r.model == "gemini"), None)
    if claude_run is None:
        raise SynapseError("internal error: missing claude review result")

    claude_out = unique_path(paths.patches_dir / f"{slug}-review-audit-claude.md")
    claude_out.write_text(claude_run.output_text.strip() + "\n", encoding="utf-8", newline="\n")
    gemini_out = None
    if gemini_run:
        gemini_out = unique_path(paths.patches_dir / f"{slug}-review-audit-gemini.md")
        gemini_out.write_text(gemini_run.output_text.strip() + "\n", encoding="utf-8", newline="\n")

    rebuild_index(paths)
    sessions_by_slug: dict[str, dict[str, str]] = {}
    if claude_run.session_id:
        sessions_by_slug["claude"] = {slug: claude_run.session_id}
    if gemini_run and gemini_run.session_id:
        sessions_by_slug["gemini"] = {slug: gemini_run.session_id}
    update_state(
        paths,
        last={
            "command": "review",
            "slug": slug,
            "task_type": task_type,
            "plan_path": str(plan_path) if plan_path else None,
            "context_pack": str(context_pack),
            "claude_session_id": claude_run.session_id,
            "claude_log": str(claude_run.log_path),
            "claude_output_md": str(claude_out),
            "gemini_session_id": gemini_run.session_id if gemini_run else None,
            "gemini_log": str(gemini_run.log_path) if gemini_run else None,
            "gemini_output_md": str(gemini_out) if gemini_out else None,
            "at": utc_now_iso(),
        },
        sessions_by_slug=sessions_by_slug or None,
    )

    print(f"task_type: {task_type}")
    if plan_path:
        print(f"plan: {plan_path}")
    print(f"context_pack: {context_pack}")
    print(f"claude_audit: {claude_out}")
    print(f"claude_log: {claude_run.log_path}")
    if gemini_out and gemini_run:
        print(f"gemini_audit: {gemini_out}")
        print(f"gemini_log: {gemini_run.log_path}")

    return 0 if all(r.exit_code == 0 for r in runs) else 2


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
            task_type=getattr(args, "task_type", "fullstack"),
            resume_gemini=getattr(args, "resume_gemini", None),
            resume_claude=getattr(args, "resume_claude", None),
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
            resume_gemini=getattr(args, "resume_gemini", None),
            resume_claude=getattr(args, "resume_claude", None),
        )
    )
    if exec_rc != 0:
        return exec_rc

    print("")
    print("workflow: execute completed (draft patches generated).")
    print("next: apply changes in Codex, then run: synapse verify && synapse review")
    return 0


def cmd_feat(args: argparse.Namespace) -> int:
    return cmd_workflow(args)
