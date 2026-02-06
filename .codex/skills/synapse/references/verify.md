# `synapse verify`

自动探测项目类型并运行验证命令（安装依赖 → lint/typecheck → tests，按可用性选择）。

> `verify` 的目标是“尽量自动化，但不瞎猜”。当探测不到明确的项目入口或命令缺失时，会记录为 `SKIPPED/FAILED` 并把线索落盘到日志，交由 Codex 主控侧决定下一步。

## 用法

```bash
synapse verify [--dry-run] [--no-install] [--keep-going]
```

## 默认行为（重要）

- **允许写入项目级副产物**：例如 lockfile、`.venv/`、`node_modules/`、构建输出等（取决于项目工具链）
- 完整 stdout/stderr 会落盘到 `.synapse/logs/**`；终端只打印摘要与关键路径
- 默认遇到第一个失败就停止（可用 `--keep-going` 尽量跑完）
- `--dry-run` 只打印“计划运行的命令”，不实际执行

## 写入哪些文件

- `<project>/.synapse/logs/*`：每条 verify 命令的完整输出
- `<project>/.synapse/state.json`：记录最近一次 verify 的命令列表、退出码、日志路径

## 失败与恢复

- 依赖工具缺失（如 `uv`/`node`/`cargo`/`dotnet` 不存在）：会记录为 blocker，但不会崩溃
- 某条命令失败：查看对应日志文件；修复后重跑 `synapse verify` 即可

