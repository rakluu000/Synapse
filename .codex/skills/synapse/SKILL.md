---
name: synapse
description: Codex-led multi-model workflow (Codex + Claude + Gemini). Use when the user asks to run `synapse <cmd> ...` to generate draft diffs/audits and persist artifacts to `./.synapse/**`.
---

# Synapse (Codex Skill)

Synapse is a **project-local workflow runner** driven by **Codex (main controller)**.

## Models (roles)

- **Claude**: planning (architecture/risks) + backend draft diffs + general code audit
- **Gemini**: frontend/UI draft diffs + UI/UX audit (only when `task_type` includes frontend)
- **Codex**: merges drafts, writes final code, runs verification, and delivers

Artifacts are written under `./.synapse/**` in the *target project root*.

## Hard rules (must follow)

- Only handle requests that start with `synapse <cmd> ...` (no slash commands).
- Before running anything: open `references/<cmd>.md` and summarize (purpose, usage, models, writes/side effects, and any safety/confirmation requirements).
- If any CLI args are unclear, run `synapse.py <cmd> --help` (via `uv`) and follow the output.
- Run Synapse scripts via `uv`:

```powershell
uv run --no-project python <SKILL_DIR>/scripts/synapse.py --project-dir <PROJECT_DIR> <cmd> ...
```

- Treat any external diff as a **draft**. Do **not** apply verbatim; Codex rewrites to production quality.
- If code changes are needed (Codex side): require a clean git tree, work on a `synapse/<slug>` branch, confirm twice (after plan; before applying changes), then run `synapse verify` and `synapse review`.

## Global flags (common)

- `--project-dir <dir>`: directory inside the target project (default: `.`)
- `--resume-gemini <SESSION_ID>` / `--resume-claude <SESSION_ID>`
- `--resume <SESSION_ID>`: alias for `--resume-gemini` (back-compat)

## Command map

Run the Python entrypoint with the same subcommand:

- `init`, `plan`, `execute`, `verify`, `review`
- `workflow`, `feat`
- `frontend`, `backend`
- `analyze`, `debug`, `optimize`, `test`, `enhance`

## Script guarantees

- Project root detection: `git rev-parse --show-toplevel` (fallback: current directory).
- Artifacts always go under `./.synapse/**` (plans/context/logs/patches/state/index).
- `init` only writes: `AGENTS.md`, `.gitignore`, `./.synapse/**` (idempotent).
- `verify` may create **project-local toolchain artifacts** (lockfiles, `.venv/`, `node_modules/`, build outputs) as a side effect.
- External model calls use local `claude` + `gemini` CLIs in stream-json mode (`session_id` captured; resume supported).
