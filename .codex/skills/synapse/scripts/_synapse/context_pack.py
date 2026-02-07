from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Any

from .common import (
    SynapsePaths,
    WriteGuard,
    is_git_repo,
    read_text,
    run_cmd,
    truncate_bytes,
    unique_path,
    write_text,
)


def derive_rg_queries(query: str, *, max_queries: int) -> list[str]:
    stop = {
        "the",
        "and",
        "or",
        "to",
        "a",
        "an",
        "of",
        "in",
        "on",
        "for",
        "with",
        "is",
        "are",
        "be",
        "as",
        "at",
        "by",
        "from",
        "this",
        "that",
        "these",
        "those",
        "it",
        "we",
        "you",
        "i",
        "our",
        "your",
        "实现",
        "功能",
        "支持",
        "增加",
        "优化",
        "修复",
        "问题",
    }
    tokens = re.findall(r"[A-Za-z0-9_][A-Za-z0-9_./:-]{1,}", query)
    seen: set[str] = set()
    out: list[str] = []
    for tok in tokens:
        t = tok.strip().lower()
        if len(t) < 3:
            continue
        if t in stop:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(tok)
        if len(out) >= max_queries:
            break
    if not out and query.strip():
        out.append(query.strip()[:32])
    return out


def select_key_files(project_root: Path, *, max_files: int, extra_files: list[Path] | None = None) -> list[Path]:
    candidates: list[Path] = []

    if extra_files:
        for p in extra_files:
            try:
                if p.exists() and p.is_file():
                    candidates.append(p)
            except Exception:
                continue

    preferred_names = [
        "AGENTS.md",
        ".gitignore",
        "README.md",
        "README.txt",
        "README",
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "Cargo.toml",
        "go.mod",
        "Makefile",
        "Dockerfile",
    ]
    for name in preferred_names:
        p = project_root / name
        if p.exists() and p.is_file():
            candidates.append(p)

    if is_git_repo(project_root):
        try:
            st = run_cmd(["git", "status", "--porcelain"], cwd=project_root, timeout_seconds=20)
            if st.code == 0:
                for line in st.stdout.splitlines():
                    if not line.strip():
                        continue
                    path_part = line[3:].strip()
                    if " -> " in path_part:
                        path_part = path_part.split(" -> ", 1)[1].strip()
                    p = project_root / path_part
                    if p.exists() and p.is_file():
                        candidates.append(p)
        except Exception:
            pass

    seen: set[Path] = set()
    unique: list[Path] = []
    for p in candidates:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        unique.append(p)
        if len(unique) >= max_files:
            break
    return unique


def snippet_for_file(path: Path, *, max_lines: int, max_bytes: int) -> str:
    try:
        size = path.stat().st_size
        if size > max(256_000, max_bytes * 4):
            return f"(skipped: file too large: {size} bytes)"
        text = read_text(path)
    except Exception as e:
        return f"(skipped: {type(e).__name__}: {e})"

    lines = text.splitlines()
    head = lines[:max_lines]
    out = "\n".join(head)
    out = truncate_bytes(out, max_bytes)
    if len(lines) > max_lines:
        out += "\n…(truncated)\n"
    return out


def build_context_pack(
    *,
    paths: SynapsePaths,
    defaults: dict[str, Any],
    slug: str,
    phase: str,
    query: str,
    rg_queries: list[str] | None = None,
    include_files: list[Path] | None = None,
    guard: WriteGuard | None = None,
) -> Path:
    cfg = defaults.get("context_pack", {})
    rg_cfg = cfg.get("rg", {})
    snip_cfg = cfg.get("snippets", {})
    git_cfg = cfg.get("git", {})

    rg_max_depth = int(rg_cfg.get("max_depth", 25))
    rg_max_queries = int(rg_cfg.get("max_queries", 10))
    rg_max_matches_per_query = int(rg_cfg.get("max_matches_per_query", 80))
    rg_max_total_matches = int(rg_cfg.get("max_total_matches", 200))
    rg_max_filesize = str(rg_cfg.get("max_filesize", "1M"))

    max_files = int(snip_cfg.get("max_files", 20))
    max_lines_per_file = int(snip_cfg.get("max_lines_per_file", 160))
    max_bytes_per_file = int(snip_cfg.get("max_bytes_per_file", 20000))

    diff_max_bytes = int(git_cfg.get("diff_max_bytes", 200000))
    diff_max_lines = int(git_cfg.get("diff_max_lines", 2000))
    status_max_lines = int(git_cfg.get("status_max_lines", 300))

    out_path = unique_path(paths.context_dir / f"{slug}-{phase}.md")
    project_root = paths.project_root
    git_ok = is_git_repo(project_root)

    parts: list[str] = []
    parts.append(f"# Synapse Context Pack: `{slug}` / `{phase}`")
    parts.append("")
    parts.append(f"- created_at: {_dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()}")
    parts.append(f"- project_root: {project_root}")
    parts.append(f"- git_repo: {git_ok}")
    parts.append(f"- query: {query}")
    parts.append("")

    if git_ok:
        parts.append("## Git")
        parts.append("")
        head = run_cmd(["git", "rev-parse", "HEAD"], cwd=project_root, timeout_seconds=10)
        branch = run_cmd(["git", "branch", "--show-current"], cwd=project_root, timeout_seconds=10)
        parts.append(f"- branch: {branch.stdout.strip() or '(detached)'}")
        parts.append(f"- head: {head.stdout.strip()}")
        parts.append("")

        status = run_cmd(["git", "status", "--porcelain", "-b"], cwd=project_root, timeout_seconds=20)
        status_lines = status.stdout.splitlines()[:status_max_lines]
        parts.append("### `git status --porcelain -b`")
        parts.append("")
        parts.append("```")
        parts.append("\n".join(status_lines) if status_lines else "(clean)")
        parts.append("```")
        parts.append("")

        diff_stat = run_cmd(["git", "diff", "--stat"], cwd=project_root, timeout_seconds=30)
        parts.append("### `git diff --stat`")
        parts.append("")
        parts.append("```")
        parts.append(diff_stat.stdout.strip() or "(no diff)")
        parts.append("```")
        parts.append("")

        diff = run_cmd(["git", "diff"], cwd=project_root, timeout_seconds=60)
        diff_text = "\n".join(diff.stdout.splitlines()[:diff_max_lines])
        diff_text = truncate_bytes(diff_text, diff_max_bytes).rstrip()
        parts.append("### `git diff` (truncated)")
        parts.append("")
        parts.append("```diff")
        parts.append(diff_text or "")
        parts.append("```")
        parts.append("")
    else:
        parts.append("## Git")
        parts.append("")
        parts.append("(not a git repository)")
        parts.append("")

    parts.append("## ripgrep (summary)")
    parts.append("")
    queries = rg_queries[:] if rg_queries else derive_rg_queries(query, max_queries=rg_max_queries)
    queries = [q for q in queries if isinstance(q, str) and q.strip()]
    if len(queries) > rg_max_queries:
        queries = queries[:rg_max_queries]
    total_hits = 0
    for q in queries:
        if total_hits >= rg_max_total_matches:
            break
        parts.append(f"### `rg -n {q!r}`")
        parts.append("")
        try:
            rg = run_cmd(
                [
                    "rg",
                    "-n",
                    "--max-depth",
                    str(rg_max_depth),
                    "--max-filesize",
                    rg_max_filesize,
                    "--max-count",
                    str(max(1, rg_max_matches_per_query // 10)),
                    "--glob",
                    "!**/.synapse/**",
                    q,
                ],
                cwd=project_root,
                timeout_seconds=60,
            )
            lines = [ln for ln in rg.stdout.splitlines() if ln.strip()]
            if not lines:
                parts.append("```")
                parts.append("(no matches)")
                parts.append("```")
                parts.append("")
                continue
            remaining = rg_max_total_matches - total_hits
            take = min(len(lines), min(rg_max_matches_per_query, remaining))
            total_hits += take
            parts.append("```")
            parts.append("\n".join(lines[:take]))
            if len(lines) > take:
                parts.append("…(truncated)")
            parts.append("```")
            parts.append("")
        except Exception as e:
            parts.append("```")
            parts.append(f"(rg failed: {type(e).__name__}: {e})")
            parts.append("```")
            parts.append("")

    parts.append("## Key files (snippets)")
    parts.append("")
    key_files = select_key_files(project_root, max_files=max_files, extra_files=include_files)
    if not key_files:
        parts.append("(none selected)")
    for p in key_files:
        rel = p.relative_to(project_root) if p.is_absolute() else p
        parts.append(f"### `{rel}`")
        parts.append("")
        parts.append("```")
        parts.append(snippet_for_file(p, max_lines=max_lines_per_file, max_bytes=max_bytes_per_file).rstrip())
        parts.append("```")
        parts.append("")

    write_text(out_path, "\n".join(parts).rstrip() + "\n", guard=guard)
    return out_path
