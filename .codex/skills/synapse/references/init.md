# `synapse init`

Initialize Synapse in the target project root (idempotent).

## Usage

```bash
synapse init
```

## Writes (hard limit)

- `<project>/AGENTS.md` (maintains the `<!-- SYNAPSE-BEGIN --> … <!-- SYNAPSE-END -->` block)
- `<project>/.gitignore` (appends `/.synapse/`)
- `<project>/.synapse/**` (plan/context/logs/patches/state/index)

## Notes

- If not a git repo, `--project-dir` is treated as the project root.
