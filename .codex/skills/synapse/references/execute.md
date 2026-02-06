# `synapse execute`

Read a plan and generate **draft diffs** based on plan meta `task_type` (does not apply code changes).

## Usage

```bash
synapse execute <plan_path>
```

## Routing

- `frontend` → Gemini (frontend draft diff)
- `backend` → Claude (backend draft diff)
- `fullstack` → both in parallel

## Writes

- `<project>/.synapse/context/<slug>-execute.md`
- `<project>/.synapse/logs/*-execute-*-stream.jsonl`
- `<project>/.synapse/patches/*-execute-draft-gemini.{md,diff}` (optional)
- `<project>/.synapse/patches/*-execute-draft-claude.{md,diff}` (optional)
- `<project>/.synapse/state.json`

## Resume

- Uses plan meta `sessions` by default; override via global `--resume-gemini/--resume-claude`.

## Notes

- If diff extraction fails, only the `.md` file is written.
- Codex should rewrite drafts into final code, then run `synapse verify` and `synapse review`.
