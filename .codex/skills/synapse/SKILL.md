---
name: synapse
description: Codex-led multi-model workflow (Codex + Claude + Gemini). External models produce drafts/audits; Codex writes final code. Artifacts persist to `./.synapse/**`.
---

# Synapse (Codex Skill)

Synapse is a **project-local workflow system** driven by **Codex (main controller)**:

- **Claude**: architecture/risk planning + code audit (and backend draft patches when needed)
- **Gemini**: frontend/UI draft patches + UI/UX audit (only when `task_type` includes frontend)
- **Codex**: reconciles drafts, writes final production code, runs verification, and delivers

All plans/state/logs/patches live under `./.synapse/**` in the *target project root*.

## Trigger & Routing (strict)

Only handle requests that start with:

`synapse <cmd> ...`

Do **not** accept any slash command variants.

### Router protocol (must follow)

1. Parse `<cmd>` (first token after `synapse`).
2. **Read and disclose** `references/<cmd>.md` (show a short excerpt + summarize: inputs/outputs, files touched, confirmation points, model allocation).
3. Execute Synapse scripts via `uv`:

```powershell
uv run --no-project python <SKILL_DIR>/scripts/synapse.py <cmd> ...
```

> Note: When installed globally, `<SKILL_DIR>` is typically `~/.codex/skills/synapse`.

4. For commands that **modify product code** (`execute`, `workflow`, `feat`, `frontend`, `backend`):
   - Refuse to proceed if the git working tree is dirty (unless the user explicitly wants that).
   - Create/switch to a safe branch: `synapse/<slug>` (derived from plan/request).
   - Ask for confirmation at least twice:
     1) after `plan` is produced (before any code change),
     2) right before applying changes (show touched files + verification plan).
   - **Do not “apply” external diffs verbatim** as final output; treat them as drafts and have Codex rewrite to production quality.

## Command map

- `synapse init` → `scripts/synapse.py init`
- `synapse plan [--task-type <frontend|backend|fullstack>] <需求>` → `scripts/synapse.py plan ...`
- `synapse execute <plan_path>` → `scripts/synapse.py execute <plan_path>` (draft diffs + artifacts; Codex performs final code changes)
- `synapse verify` → `scripts/synapse.py verify` (auto-detect install/lint/test; logs to `.synapse/**`)
- `synapse review` → `scripts/synapse.py review`
- `synapse workflow [--task-type <frontend|backend|fullstack>] [--yes] <需求>` → `scripts/synapse.py workflow ...`
- `synapse feat [--task-type <frontend|backend|fullstack>] <需求>` → `scripts/synapse.py feat ...`
- `synapse frontend <需求>` → `scripts/synapse.py frontend <需求>`
- `synapse backend <需求>` → `scripts/synapse.py backend <需求>`
- `synapse analyze <问题>` → `scripts/synapse.py analyze <问题>`
- `synapse debug <问题>` → `scripts/synapse.py debug <问题>`
- `synapse optimize <目标>` → `scripts/synapse.py optimize <目标>`
- `synapse test <目标>` → `scripts/synapse.py test <目标>`
- `synapse enhance <原始需求>` → `scripts/synapse.py enhance <原始需求>`
- `synapse commit [options]` → `scripts/synapse.py commit [options]`
- `synapse rollback [options]` → `scripts/synapse.py rollback [options]`
- `synapse clean-branches [options]` → `scripts/synapse.py clean-branches [options]`
- `synapse worktree <subcmd> ...` → `scripts/synapse.py worktree <subcmd> ...`

## Hard constraints (enforced by scripts)

- Project root detection: `git rev-parse --show-toplevel` (fallback: current directory).
- Artifact outputs always go under: `./.synapse/**` (plans/context/logs/patches/state/index).
- `init` only writes: `AGENTS.md`, `.gitignore`, `./.synapse/**` (idempotent).
- `verify` may also create **project-local** dependency artifacts (e.g. lockfiles, `.venv/`, `node_modules/`, build outputs) as a result of running project commands.
- External model calls:
  - Gemini CLI + Claude CLI
  - `--output-format stream-json` parsing to capture `session_id`
  - support `--resume <SESSION_ID>` (CLI); Synapse script exposes `--resume-gemini/--resume-claude` (and `--resume` as alias for Gemini)
  - timeout/retry/concurrency come from `assets/defaults.json` (models are not pinned here).
