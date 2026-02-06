# `synapse frontend`

Gemini generates a frontend draft diff (no code is applied automatically; Codex rewrites and applies final changes).

## Usage

```bash
synapse frontend <request...>
```

## Models

- Gemini

## Writes

- `<project>/.synapse/context/<slug>-frontend.md`
- `<project>/.synapse/logs/*-frontend-gemini-stream.jsonl`
- `<project>/.synapse/patches/<slug>-frontend-gemini.md`
- `<project>/.synapse/patches/<slug>-frontend-gemini.diff` (optional)
- `<project>/.synapse/state.json`

## Resume

- Use global `--resume-gemini <SESSION_ID>` (or alias `--resume <SESSION_ID>`).
