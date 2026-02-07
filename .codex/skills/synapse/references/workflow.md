# `synapse workflow`

Codex-led end-to-end workflow (user-level meta command):

`init → plan → run(gate_prep) → Gate → run(drafts) → Codex applies final code → verify → run(audits) → deliver`

## Usage (in Codex chat)

```bash
synapse workflow [--task-type <frontend|backend|fullstack>] <request...>
```

## Defaults

- If `--task-type` is omitted: default to `fullstack` (info-complete; higher cost).

## What Codex runs (high level)

1) `synapse init`
2) `synapse plan ...` (writes plan stub + Gate checklist + optional context pack)
3) `synapse run ...` (**gate_prep**, Claude; Gemini optional for frontend/fullstack)
4) **Gate (single-round user reply)** (see rules below)
5) `synapse run ...` (draft diffs for implementation; routed by confirmed `task_type`)
6) Codex applies final code changes (rewrite drafts into production quality)
7) `synapse verify` (auto-detect; may install deps / create lockfiles)
8) `git add -N .` (make new files visible in `git diff`)
9) `synapse pack --phase review ...` + `synapse run ...` (Claude/Gemini audits of current `git diff`)

## Gate rules (single-round)

- Codex asks the full clarification checklist **in one message** (often 5-10 questions if the request is ambiguous).
- User replies once (e.g. `A1..An`). Unanswered items imply: accept the recommended default.
- User can reply `Defaults` / `默认` to accept all recommended defaults.
- Gate must also confirm: scope + acceptance criteria, `task_type`, stack/toolchain, allowed side effects, verify plan, and git/review setup.

## `gate_prep` contract (Claude)

Goal: make the Gate high-signal, even when the request is vague.

Claude output must be **Markdown** (same language as the request) and include:

- Restated request (1-2 sentences)
- Draft acceptance criteria (bullet list)
- Clarification checklist (Q1..Qn):
  - Ask **5-10 questions** when ambiguous.
  - Each question includes: `Why this matters`, `Recommended default`, `Answer format`.
- Recommendations (short): likely `task_type`, stack/toolchain assumptions, and a verification approach.
- Constraints: no code changes; **no diffs/patches**.

## Writes / side effects

- Always: `AGENTS.md`, `.gitignore`, `./.synapse/**`
- `verify` may create project-local toolchain artifacts (lockfiles, `.venv/`, `node_modules/`, build outputs, etc.)

## Notes

- Prompts are **not** hardcoded in scripts; Codex must generate them and pass via `synapse run --prompt-file ...`.
- Use `synapse ui` to open a local web viewer for `.synapse/**` (prompts/outputs/patches/logs/state).
