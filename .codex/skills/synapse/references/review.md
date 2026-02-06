# `synapse review`

External audit of the current `git diff` (writes audit reports; does not apply code changes).

## Usage

```bash
synapse review [--plan-path <plan_path>] [--task-type <frontend|backend|fullstack>]
```

## Models

- Claude: always (general audit)
- Gemini: only for `frontend|fullstack` (UI/UX + accessibility audit)

## Writes

- `<project>/.synapse/context/<slug>-review.md`
- `<project>/.synapse/logs/*-review-*-stream.jsonl`
- `<project>/.synapse/patches/*-review-audit-claude.md`
- `<project>/.synapse/patches/*-review-audit-gemini.md` (optional)
- `<project>/.synapse/state.json`

## Notes

- If `--plan-path/--task-type` is omitted, the script tries to infer from `.synapse/state.json`; otherwise defaults to `fullstack`.
- Starts new sessions (no auto-resume).
