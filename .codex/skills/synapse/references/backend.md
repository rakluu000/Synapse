# `synapse backend`

Claude generates a backend draft diff (no code is applied automatically; Codex rewrites and applies final changes).

## Usage

```bash
synapse backend <request...>
```

## Models

- Claude

## Writes

- `<project>/.synapse/context/<slug>-backend.md`
- `<project>/.synapse/logs/*-backend-claude-stream.jsonl`
- `<project>/.synapse/patches/<slug>-backend-claude.md`
- `<project>/.synapse/patches/<slug>-backend-claude.diff` (optional)
- `<project>/.synapse/state.json`

## Resume

- Use global `--resume-claude <SESSION_ID>`.
