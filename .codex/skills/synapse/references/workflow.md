# `synapse workflow`

Convenience wrapper: `init → plan → execute` (drafts only; does not apply code changes).

## Usage

```bash
synapse workflow [--task-type <frontend|backend|fullstack>] [--yes] <request...>
```

## Defaults

- `--task-type` defaults to `fullstack`

## Behavior

- Always runs `init` and `plan`.
- Without `--yes`: stops after `plan` (prints the next `synapse execute <plan_path>`).
- With `--yes`: continues through `execute` (prints next steps: Codex applies final changes, then run `verify` + `review`).

## Writes

- Combined outputs of `init` + `plan` + `execute` (`AGENTS.md`, `.gitignore`, `./.synapse/**`).
