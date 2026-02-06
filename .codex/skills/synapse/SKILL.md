---
name: synapse
description: Multi-model (Gemini + Claude) workflow runner for Codex. Uses only `synapse <cmd> ...` (no slash commands). Persists all artifacts to `./.synapse/**`.
metadata:
  short-description: Workflow/plan/execute with resumable sessions
---

# Synapse (Codex Skill)

Synapse is a **project-local workflow system** driven by Codex, with **Gemini** generating implementation patches and **Claude** producing audit feedback. All state/logs/plans live under `./.synapse/**` in the *target project root*.

## Trigger & Routing (strict)

Only handle requests that start with:

`synapse <cmd> ...`

Do **not** accept any slash command variants.

### Router protocol (must follow)

1. Parse `<cmd>` (first token after `synapse`).
2. **Read and disclose** `references/<cmd>.md` (show a short, relevant excerpt + summarize constraints: inputs/outputs, files touched, confirmation points).
3. Execute the command by running the Python CLI via `uv`:

```powershell
uv run --no-project python <SKILL_DIR>/scripts/synapse.py <cmd> ...
```

> Note: When installed globally, `<SKILL_DIR>` is typically `~/.codex/skills/synapse`.

## Command map

- `synapse init` → `scripts/synapse.py init`
- `synapse plan <需求>` → `scripts/synapse.py plan <需求>`
- `synapse execute <plan_path>` → `scripts/synapse.py execute <plan_path>`
- `synapse review` → `scripts/synapse.py review`
- `synapse workflow [--yes] <需求>` → `scripts/synapse.py workflow [--yes] <需求>`
- `synapse feat <需求>` → `scripts/synapse.py feat <需求>`
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
- Persist outputs only to: `AGENTS.md`, `./.synapse/**`, `.gitignore` (idempotent).
- External model calls:
  - Gemini CLI + Claude CLI
  - `--output-format stream-json` parsing to capture `session_id`
  - support `--resume <SESSION_ID>`
  - timeout/retry/concurrency come from `assets/defaults.json` (models are not pinned here).
