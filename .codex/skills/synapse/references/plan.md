# `synapse plan`

Create a plan file (plan meta: `task_type` + `sessions`) and a context pack.

## Usage

```bash
synapse plan [--task-type <frontend|backend|fullstack>] <request...>
```

## Defaults

- `--task-type` defaults to `fullstack`

## Models

- Claude: always (architecture/risks/boundaries/tests)
- Gemini: only for `frontend|fullstack` (UI/UX/a11y plan)

## Writes

- `<project>/.synapse/plan/<slug>.md` (meta JSON: `task_type`, `sessions`, `request`, `context_pack`)
- `<project>/.synapse/context/<slug>-plan.md`
- `<project>/.synapse/patches/*-plan-claude.md`
- `<project>/.synapse/patches/*-plan-gemini.md` (optional)
- `<project>/.synapse/logs/*-plan-*-stream.jsonl`
- `<project>/.synapse/state.json`, `<project>/.synapse/index.json`

## Stdout

- `plan: <path>`
- `context_pack: <path>`
- `claude_session_id: <id|TBD>`
- `gemini_session_id: <id|TBD>` (optional)

## Notes

- This step produces draft plans; Codex consolidates/approves the final plan in chat.
- `execute` resumes via plan meta `sessions` by default; global `--resume-*` overrides.
