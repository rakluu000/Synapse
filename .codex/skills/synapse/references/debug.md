# `synapse debug`

Claude produces a debugging plan and likely fixes from the context pack (no patch by default).

## Usage

```bash
synapse debug <problem...>
```

## Models

- Claude

## Writes

- `<project>/.synapse/context/<slug>-debug.md`
- `<project>/.synapse/logs/*-debug-claude-stream.jsonl`
- `<project>/.synapse/patches/<slug>-debug-claude.md`
- `<project>/.synapse/state.json`
