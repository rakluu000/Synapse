# `synapse analyze`

Claude produces a structured analysis from the context pack (no patch by default).

## Usage

```bash
synapse analyze <question-or-goal...>
```

## Models

- Claude

## Writes

- `<project>/.synapse/context/<slug>-analyze.md`
- `<project>/.synapse/logs/*-analyze-claude-stream.jsonl`
- `<project>/.synapse/patches/<slug>-analyze-claude.md`
- `<project>/.synapse/state.json`
