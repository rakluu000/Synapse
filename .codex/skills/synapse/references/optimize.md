# `synapse optimize`

Claude proposes optimizations (may include a diff; extracted to a `.diff` file when possible). No code is applied automatically.

## Usage

```bash
synapse optimize <goal...>
```

## Models

- Claude

## Writes

- `<project>/.synapse/context/<slug>-optimize.md`
- `<project>/.synapse/logs/*-optimize-claude-stream.jsonl`
- `<project>/.synapse/patches/<slug>-optimize-claude.md`
- `<project>/.synapse/patches/<slug>-optimize-claude.diff` (optional)
- `<project>/.synapse/state.json`
