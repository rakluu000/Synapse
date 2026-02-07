# `synapse ui`

Open a local **read-only** web viewer for `./.synapse/**` (prompts/outputs/patches/logs/state).

## Usage

```bash
synapse ui [--host <host>] [--port <port>] [--no-open]
```

## Notes

- The viewer serves **only** `.synapse/**` files.
- Default view: **Timeline** grouped by `slug → phase → model`. Use **Browse** to see the raw folder lists.
- The process runs until interrupted (Ctrl+C).
