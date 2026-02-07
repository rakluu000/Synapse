# `synapse plan`

Create a **plan stub** (meta JSON + Gate checklist) and (by default) a **plan context pack**.

## Usage

```bash
synapse plan [--task-type <frontend|backend|fullstack>] [--slug <slug>] [--no-pack] [--rg-query <q>] [--include-file <path>] <request...>
```

## Defaults

- `--task-type` defaults to `fullstack`

## Models

- None. This command does **not** call external models.
- Codex generates prompts and uses `synapse run` to call Claude/Gemini.

## Writes

- `<project>/.synapse/plan/<slug>.md` (meta JSON: `task_type`, `sessions`, `request`, `context_pack`)
- `<project>/.synapse/context/<slug>-plan(-N).md` (unless `--no-pack`; unique-suffixed on collisions)
- `<project>/.synapse/state.json`, `<project>/.synapse/index.json`

## Stdout

- `backup: <path>` (only if an existing plan was backed up)
- `slug: <slug>`
- `task_type: <task_type>`
- `plan: <path>`
- `context_pack: <path>` (if created)

## Notes

- The plan file is the anchor for the **Gate** (single user confirmation point).
- If `<project>/.synapse/plan/<slug>.md` already exists, it is backed up to `<slug>.md.bak` (unique-suffixed) before being overwritten.
- `synapse run --plan-path <plan>` will update `sessions` in plan meta (when `session_id` is available).
