# `synapse workflow`

Codex-led end-to-end workflow (user-level meta command):

`init → plan → (Gate) → run(drafts) → Codex applies final code → verify → run(audits) → deliver`

## Usage (in Codex chat)

```bash
synapse workflow [--task-type <frontend|backend|fullstack>] <request...>
```

## Defaults

- If `--task-type` is omitted: default to `fullstack` (info-complete; higher cost).

## What Codex runs

1) `synapse init`
2) `synapse plan ...` (writes plan stub + Gate checklist + optional context pack)
3) `synapse run ...` (Claude + Gemini drafts; prompts are written by Codex)
4) **Gate (single user confirmation)**: Codex presents options + recommendation, user confirms once
5) `synapse run ...` (draft diffs for implementation; routed by confirmed `task_type`)
6) Codex applies final code changes (rewrite drafts into production quality)
7) `synapse verify` (auto-detect; may install deps / create lockfiles)
8) `git add -N .` (make new files visible in `git diff`)
9) `synapse pack --phase review ...` + `synapse run ...` (Claude/Gemini audits of current `git diff`)

## Confirmation (Gate)

- The only required confirmation is after `plan`.
- Gate must explicitly confirm: scope, `task_type`, stack/toolchain, allowed writes/side effects (deps install + lockfiles), verify commands, and git/review setup.

## Writes / side effects

- Always: `AGENTS.md`, `.gitignore`, `./.synapse/**`
- `verify` may create project-local toolchain artifacts (lockfiles, `.venv/`, `node_modules/`, build outputs, etc.)

## Notes

- Prompts are **not** hardcoded in scripts; Codex must generate them and pass via `synapse run --prompt-file ...`.
- Use `synapse ui` to open a local web viewer for `.synapse/**` (prompts/outputs/patches/logs/state).
