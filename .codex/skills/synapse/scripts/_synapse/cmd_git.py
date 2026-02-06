from __future__ import annotations

import argparse
import datetime as _dt
import textwrap
from pathlib import Path

from .common import (
    SynapseError,
    find_project_root,
    is_git_repo,
    load_defaults,
    run_cmd,
    synapse_paths,
    truncate_bytes,
    unique_path,
)
from .llm import run_model_with_retries


def _ensure_layout(project_root: Path):
    from .common import ensure_synapse_layout

    paths = synapse_paths(project_root)
    ensure_synapse_layout(paths)
    return paths


def cmd_commit(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = _ensure_layout(project_root)

    if not is_git_repo(project_root):
        raise SynapseError("commit requires a git repository")

    st = run_cmd(["git", "status", "--porcelain"], cwd=project_root, timeout_seconds=20)
    if not st.stdout.strip():
        print("No changes to commit.")
        return 0

    diff_stat = run_cmd(["git", "diff", "--stat"], cwd=project_root, timeout_seconds=30)
    diff = run_cmd(["git", "diff"], cwd=project_root, timeout_seconds=60)
    diff_text = truncate_bytes(diff.stdout, 120_000)

    prompt = textwrap.dedent(
        f"""
        You are an expert engineer generating a Conventional Commit message.

        Constraints:
        - Do NOT use any tools, MCP servers, file access, or external search.
        - Output must be ONLY the commit message (subject line + optional body).
        - Subject line <= 72 characters.
        - Use Conventional Commits: <type>(<scope>): <subject>

        Options:
        - emoji: {bool(args.emoji)}
        - type: {args.type or "auto"}
        - scope: {args.scope or "auto"}

        Diff stat:
        {diff_stat.stdout.strip()}

        Diff (truncated):
        {diff_text}
        """
    ).strip()

    run = run_model_with_retries(
        model="claude",
        prompt=prompt,
        project_root=project_root,
        resume=None,
        defaults=defaults,
        slug="commit",
        phase="commit",
    )

    message = run.output_text.strip()
    if not message:
        raise SynapseError("Failed to generate commit message (empty output)")

    out_path = unique_path(paths.patches_dir / f"commit-message-{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt")
    out_path.write_text(message + "\n", encoding="utf-8", newline="\n")

    print(f"commit_message_file: {out_path}")
    print("")
    print(message)
    print("")
    if not args.yes:
        print("dry-run: not running git commit (pass --yes to execute).")
        return 0

    if args.all:
        run_cmd(["git", "add", "-A"], cwd=project_root, timeout_seconds=60, check=True)

    commit_argv = ["git", "commit", "-F", str(out_path)]
    if args.no_verify:
        commit_argv.append("--no-verify")
    if args.signoff:
        commit_argv.append("--signoff")
    if args.amend:
        commit_argv.append("--amend")

    res = run_cmd(commit_argv, cwd=project_root, timeout_seconds=300)
    print(res.stdout)
    if res.code != 0:
        print(res.stderr)
        return res.code
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    project_root = find_project_root(Path(args.project_dir))
    if not is_git_repo(project_root):
        raise SynapseError("rollback requires a git repository")

    target = args.target
    mode = args.mode
    branch = args.branch or run_cmd(["git", "branch", "--show-current"], cwd=project_root, timeout_seconds=10).stdout.strip()
    branch = branch or "(detached)"

    head = run_cmd(["git", "rev-parse", "HEAD"], cwd=project_root, timeout_seconds=10).stdout.strip()
    print(f"current_branch: {branch}")
    print(f"current_head: {head}")
    print(f"target: {target}")
    print(f"mode: {mode}")

    cmds: list[list[str]] = []
    if branch != "(detached)":
        cmds.append(["git", "switch", branch])
    if mode == "reset":
        cmds.append(["git", "reset", "--hard", target])
    else:
        cmds.append(["git", "revert", "--no-edit", f"{target}..HEAD"])

    print("")
    print("planned_commands:")
    for c in cmds:
        print("  " + " ".join(c))

    if args.dry_run and not args.yes:
        print("")
        print("dry-run: not executing (pass --yes to execute).")
        return 0
    if not args.yes:
        print("")
        print("refusing to execute without --yes")
        return 2

    for c in cmds:
        res = run_cmd(c, cwd=project_root, timeout_seconds=600)
        print(res.stdout)
        if res.code != 0:
            print(res.stderr)
            return res.code
    return 0


def cmd_clean_branches(args: argparse.Namespace) -> int:
    project_root = find_project_root(Path(args.project_dir))
    if not is_git_repo(project_root):
        raise SynapseError("clean-branches requires a git repository")

    base = args.base
    if not base:
        for candidate in ("main", "master"):
            res = run_cmd(["git", "show-ref", "--verify", f"refs/heads/{candidate}"], cwd=project_root, timeout_seconds=10)
            if res.code == 0:
                base = candidate
                break
    if not base:
        raise SynapseError("Unable to determine base branch (pass --base)")

    protected = {base, "main", "master", "develop", "production"}

    merged = run_cmd(["git", "branch", "--merged", base], cwd=project_root, timeout_seconds=20)
    branches: list[str] = []
    for line in merged.stdout.splitlines():
        name = line.replace("*", "").strip()
        if not name or name in protected:
            continue
        branches.append(name)

    stale_days = args.stale
    if stale_days is not None:
        cutoff = _dt.datetime.now().timestamp() - int(stale_days) * 86400
        keep: list[str] = []
        for br in branches:
            ts = run_cmd(["git", "log", "-1", "--format=%ct", br], cwd=project_root, timeout_seconds=20)
            try:
                last_commit = int(ts.stdout.strip())
            except ValueError:
                continue
            if last_commit <= cutoff:
                keep.append(br)
        branches = keep

    if not branches:
        print("No branches to clean.")
        return 0

    print(f"base: {base}")
    print("branches:")
    for br in branches:
        print(f"- {br}")

    if args.dry_run and not args.yes:
        print("")
        print("dry-run: not deleting (pass --yes to execute).")
        return 0
    if not args.yes:
        print("")
        print("refusing to execute without --yes")
        return 2

    delete_flag = "-D" if args.force else "-d"
    for br in branches:
        res = run_cmd(["git", "branch", delete_flag, br], cwd=project_root, timeout_seconds=60)
        if res.code != 0:
            print(res.stderr)
            return res.code
        print(res.stdout.strip())
        if args.remote:
            run_cmd(["git", "push", "origin", "--delete", br], cwd=project_root, timeout_seconds=120)
    return 0


def cmd_worktree(args: argparse.Namespace) -> int:
    project_root = find_project_root(Path(args.project_dir))
    if not is_git_repo(project_root):
        raise SynapseError("worktree requires a git repository")

    root = project_root.parent / ".synapse-worktrees" / project_root.name
    sub = args.subcmd

    if sub == "list":
        res = run_cmd(["git", "worktree", "list", "--porcelain"], cwd=project_root, timeout_seconds=30)
        print(res.stdout.strip())
        return 0 if res.code == 0 else res.code

    if sub == "prune":
        if not args.yes:
            print("refusing to prune without --yes")
            return 2
        res = run_cmd(["git", "worktree", "prune"], cwd=project_root, timeout_seconds=60)
        print(res.stdout.strip())
        return 0 if res.code == 0 else res.code

    if sub == "add":
        if not args.path:
            raise SynapseError("worktree add requires <path>")
        target = (root / args.path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["git", "worktree", "add"]
        if args.branch:
            cmd += ["-b", args.branch]
        if args.detach:
            cmd += ["--detach"]
        cmd += [str(target)]
        print(f"target: {target}")
        print("command: " + " ".join(cmd))
        if not args.yes:
            print("dry-run: not creating (pass --yes to execute).")
            return 0
        res = run_cmd(cmd, cwd=project_root, timeout_seconds=600)
        print(res.stdout.strip())
        if res.code != 0:
            print(res.stderr)
        return 0 if res.code == 0 else res.code

    if sub == "remove":
        if not args.path:
            raise SynapseError("worktree remove requires <path>")
        target = (root / args.path).resolve()
        cmd = ["git", "worktree", "remove"]
        if args.force:
            cmd.append("--force")
        cmd += [str(target)]
        print("command: " + " ".join(cmd))
        if not args.yes:
            print("dry-run: not removing (pass --yes to execute).")
            return 0
        res = run_cmd(cmd, cwd=project_root, timeout_seconds=600)
        print(res.stdout.strip())
        if res.code != 0:
            print(res.stderr)
        return 0 if res.code == 0 else res.code

    if sub == "migrate":
        if not args.path:
            raise SynapseError("worktree migrate requires <target-path>")
        if not args.from_path:
            raise SynapseError("worktree migrate requires --from <source-path>")
        target = (root / args.path).resolve()
        source = Path(args.from_path).resolve()

        if find_project_root(source) != project_root:
            raise SynapseError("source must belong to the same git repository")
        if target.exists() and find_project_root(target) != project_root:
            raise SynapseError("target must belong to the same git repository")

        patch = run_cmd(["git", "-C", str(source), "diff", "HEAD"], cwd=project_root, timeout_seconds=120)
        untracked = run_cmd(["git", "-C", str(source), "ls-files", "--others", "--exclude-standard"], cwd=project_root, timeout_seconds=60)

        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        patch_path = synapse_paths(project_root).patches_dir / f"worktree-migrate-{ts}.diff"
        patch_path.write_text(patch.stdout, encoding="utf-8", newline="\n")

        print(f"source: {source}")
        print(f"target: {target}")
        print(f"patch_file: {patch_path}")
        if untracked.stdout.strip():
            print("")
            print("untracked_files (not migrated):")
            print(untracked.stdout.strip())

        if not args.yes:
            print("")
            print("dry-run: not applying patch (pass --yes to execute).")
            return 0

        if not target.exists():
            raise SynapseError(f"target worktree does not exist: {target} (create it first)")

        tgt_status = run_cmd(["git", "-C", str(target), "status", "--porcelain"], cwd=project_root, timeout_seconds=30)
        if tgt_status.stdout.strip() and not args.force:
            raise SynapseError("target worktree is not clean (pass --force to override)")

        apply_res = run_cmd(["git", "-C", str(target), "apply", "--index", str(patch_path)], cwd=project_root, timeout_seconds=120)
        if apply_res.code != 0:
            print(apply_res.stderr)
            return apply_res.code
        print("migrated: applied patch to target (staged in index).")
        return 0

    raise SynapseError(f"Unknown worktree subcommand: {sub}")

