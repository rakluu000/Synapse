# `synapse test`

Claude proposes test additions/changes (may include a diff; extracted to a `.diff` file when possible). No code is applied automatically.

## Usage

```bash
synapse test <target...>
```

## Models

- Claude

## Writes

- `<project>/.synapse/context/<slug>-test.md`
- `<project>/.synapse/logs/*-test-claude-stream.jsonl`
- `<project>/.synapse/patches/<slug>-test-claude.md`
- `<project>/.synapse/patches/<slug>-test-claude.diff` (optional)
- `<project>/.synapse/state.json`
