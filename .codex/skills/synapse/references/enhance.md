# `synapse enhance`

Claude rewrites the raw request into an execution-ready task spec (no code changes).

## Usage

```bash
synapse enhance <raw-request...>
```

## Models

- Claude

## Writes

- `<project>/.synapse/logs/*-enhance-claude-stream.jsonl`
- `<project>/.synapse/patches/<slug>-enhance-claude.md`
- `<project>/.synapse/state.json`
