# `synapse verify`

Auto-detect the project toolchain and run verification steps (install → lint/typecheck → test, when available). Does not call external models.

## Usage

```bash
synapse verify [--dry-run] [--no-install] [--keep-going]
```

## Writes / side effects

- `<project>/.synapse/logs/*` (full output per step)
- `<project>/.synapse/state.json` (steps + results)
- `<project>/.synapse/index.json`
- May create project-local toolchain artifacts (lockfiles, `.venv/`, `node_modules/`, build outputs, etc.)

## Exit codes

- `0`: all OK (or nothing to run)
- `2`: at least one FAILED/BLOCKED
