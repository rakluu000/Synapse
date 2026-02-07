# `synapse pack`

Build a context pack under `./.synapse/context/**`.

## Usage

```bash
synapse pack [--phase <label>] [--slug <slug>] [--query <text>] [--rg-query <q>...] [--include-file <path>...]
```

## Notes

- Use `--rg-query` to avoid query-derivation heuristics (Codex-controlled).
- Outputs are read-only inputs for `synapse run` prompts.

## Writes

- `<project>/.synapse/context/<unique>.md`
- `<project>/.synapse/state.json`
- `<project>/.synapse/index.json`
