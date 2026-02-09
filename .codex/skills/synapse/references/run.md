# `synapse run`

Run an external model with a **Codex-provided prompt template**.

## Usage

```bash
synapse run --model <claude|gemini> --slug <slug> [--phase <phase>] --prompt-file <path> [--plan-path <plan_path>] [--var KEY=VALUE] [--var-file KEY=PATH]
```

## Template variables

- The prompt file may contain placeholders like `{{REQUEST}}`, `{{CONTEXT_PACK}}`, etc.
- `--var KEY=VALUE` replaces `{{KEY}}` with `VALUE`.
- `--var-file KEY=PATH` replaces `{{KEY}}` with the file contents at `PATH`.

## Writes

- `<project>/.synapse/prompts/<ts>-<slug>-<phase>-<model>.prompt.md` (rendered prompt)
- `<project>/.synapse/patches/<ts>-<slug>-<phase>-<model>.md` (model output)
- `<project>/.synapse/patches/<ts>-<slug>-<phase>-<model>.diff` (optional; only if a unified diff is extractable)
- `<project>/.synapse/logs/<ts>-<slug>-<phase>-<model>-stream(-attemptN).jsonl` (retries keep per-attempt logs)
- `<project>/.synapse/state.json`
- `<project>/.synapse/index.json`

## Notes

- Do not rely on model filesystem/tool access. Synapse runs models headlessly and never auto-approves actions (Claude is run with tools disabled; Gemini tool attempts may be denied by the model CLI policy). Pass all required context via the prompt/template vars.
- If `--plan-path` is provided and a `session_id` is captured, the plan meta `sessions.<model>` is updated.
- The rendered prompt is saved under `.synapse/prompts/**`. If you use `--var-file` for secrets, they will be persisted there in plain text.
