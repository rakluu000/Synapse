from __future__ import annotations

import argparse
import sys

from _synapse.cmd_git import cmd_clean_branches, cmd_commit, cmd_rollback, cmd_worktree
from _synapse.cmd_tasks import (
    cmd_analyze,
    cmd_backend,
    cmd_debug,
    cmd_enhance,
    cmd_frontend,
    cmd_optimize,
    cmd_test,
)
from _synapse.cmd_verify import cmd_verify
from _synapse.cmd_workflow import cmd_execute, cmd_feat, cmd_init, cmd_plan, cmd_review, cmd_workflow
from _synapse.common import SynapseError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="synapse.py")
    p.add_argument("--project-dir", default=".", help="Directory inside the target project (default: .)")
    # Back-compat: --resume is treated as --resume-gemini.
    p.add_argument("--resume", dest="resume_gemini", default=None, help="Gemini session id to resume")
    p.add_argument("--resume-gemini", dest="resume_gemini", default=None, help="Gemini session id to resume")
    p.add_argument("--resume-claude", dest="resume_claude", default=None, help="Claude session id to resume")

    sub = p.add_subparsers(dest="cmd", required=True)

    sub_init = sub.add_parser("init")
    sub_init.set_defaults(func=cmd_init)

    sub_plan = sub.add_parser("plan")
    sub_plan.add_argument(
        "--task-type",
        choices=["frontend", "backend", "fullstack"],
        default="fullstack",
        help="Routing hint for later stages (default: fullstack)",
    )
    sub_plan.add_argument("request", nargs=argparse.REMAINDER)
    sub_plan.set_defaults(func=cmd_plan)

    sub_exec = sub.add_parser("execute")
    sub_exec.add_argument("plan_path")
    sub_exec.set_defaults(func=cmd_execute)

    sub_review = sub.add_parser("review")
    sub_review.add_argument("--plan-path", default=None, help="Optional plan path (used to infer task_type/slug)")
    sub_review.add_argument(
        "--task-type",
        choices=["frontend", "backend", "fullstack"],
        default=None,
        help="Override inferred task_type (default: infer from plan/state)",
    )
    sub_review.set_defaults(func=cmd_review)

    sub_verify = sub.add_parser("verify")
    sub_verify.add_argument("--dry-run", action="store_true", help="Print planned commands only")
    sub_verify.add_argument("--no-install", action="store_true", help="Skip dependency installation steps")
    sub_verify.add_argument("--keep-going", action="store_true", help="Continue even if a step fails")
    sub_verify.set_defaults(func=cmd_verify)

    sub_workflow = sub.add_parser("workflow")
    sub_workflow.add_argument("--yes", action="store_true")
    sub_workflow.add_argument(
        "--task-type",
        choices=["frontend", "backend", "fullstack"],
        default="fullstack",
        help="Routing hint for later stages (default: fullstack)",
    )
    sub_workflow.add_argument("request", nargs=argparse.REMAINDER)
    sub_workflow.set_defaults(func=cmd_workflow)

    sub_feat = sub.add_parser("feat")
    sub_feat.add_argument("--yes", action="store_true")
    sub_feat.add_argument(
        "--task-type",
        choices=["frontend", "backend", "fullstack"],
        default="fullstack",
        help="Routing hint for later stages (default: fullstack)",
    )
    sub_feat.add_argument("request", nargs=argparse.REMAINDER)
    sub_feat.set_defaults(func=cmd_feat)

    sub_frontend = sub.add_parser("frontend")
    sub_frontend.add_argument("request", nargs=argparse.REMAINDER)
    sub_frontend.set_defaults(func=cmd_frontend)

    sub_backend = sub.add_parser("backend")
    sub_backend.add_argument("request", nargs=argparse.REMAINDER)
    sub_backend.set_defaults(func=cmd_backend)

    sub_analyze = sub.add_parser("analyze")
    sub_analyze.add_argument("request", nargs=argparse.REMAINDER)
    sub_analyze.set_defaults(func=cmd_analyze)

    sub_debug = sub.add_parser("debug")
    sub_debug.add_argument("request", nargs=argparse.REMAINDER)
    sub_debug.set_defaults(func=cmd_debug)

    sub_optimize = sub.add_parser("optimize")
    sub_optimize.add_argument("request", nargs=argparse.REMAINDER)
    sub_optimize.set_defaults(func=cmd_optimize)

    sub_test = sub.add_parser("test")
    sub_test.add_argument("request", nargs=argparse.REMAINDER)
    sub_test.set_defaults(func=cmd_test)

    sub_enhance = sub.add_parser("enhance")
    sub_enhance.add_argument("request", nargs=argparse.REMAINDER)
    sub_enhance.set_defaults(func=cmd_enhance)

    sub_commit = sub.add_parser("commit")
    sub_commit.add_argument("--no-verify", action="store_true")
    sub_commit.add_argument("--all", action="store_true")
    sub_commit.add_argument("--amend", action="store_true")
    sub_commit.add_argument("--signoff", action="store_true")
    sub_commit.add_argument("--emoji", action="store_true")
    sub_commit.add_argument("--scope", default=None)
    sub_commit.add_argument("--type", default=None)
    sub_commit.add_argument("--yes", action="store_true")
    sub_commit.set_defaults(func=cmd_commit)

    sub_rollback = sub.add_parser("rollback")
    sub_rollback.add_argument("--target", required=True)
    sub_rollback.add_argument("--mode", choices=["reset", "revert"], default="reset")
    sub_rollback.add_argument("--branch", default=None)
    sub_rollback.add_argument("--dry-run", action="store_true", default=True)
    sub_rollback.add_argument("--yes", action="store_true")
    sub_rollback.set_defaults(func=cmd_rollback)

    sub_clean = sub.add_parser("clean-branches")
    sub_clean.add_argument("--base", default=None)
    sub_clean.add_argument("--stale", type=int, default=None)
    sub_clean.add_argument("--remote", action="store_true")
    sub_clean.add_argument("--dry-run", action="store_true", default=True)
    sub_clean.add_argument("--yes", action="store_true")
    sub_clean.add_argument("--force", action="store_true")
    sub_clean.set_defaults(func=cmd_clean_branches)

    sub_wt = sub.add_parser("worktree")
    sub_wt.add_argument("subcmd", choices=["add", "list", "remove", "prune", "migrate"])
    sub_wt.add_argument("path", nargs="?", default=None)
    sub_wt.add_argument("-b", "--branch", dest="branch", default=None)
    sub_wt.add_argument("--detach", action="store_true")
    sub_wt.add_argument("--from", dest="from_path", default=None)
    sub_wt.add_argument("--force", action="store_true")
    sub_wt.add_argument("--yes", action="store_true")
    sub_wt.set_defaults(func=cmd_worktree)

    return p


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except SynapseError as e:
        print(f"synapse error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
