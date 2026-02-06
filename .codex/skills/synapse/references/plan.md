# `synapse plan`

生成**可复用会话**的实施计划文件，并为外部模型准备上下文包（context pack）。

## 用法

```bash
synapse plan <需求文本...>
```

## 写入哪些文件

- `<project>/.synapse/plan/<slug>.md`：计划文件（包含需求、关键步骤、会话信息）
- `<project>/.synapse/context/<slug>-plan.md`：上下文包（用于投喂外部模型）
- `<project>/.synapse/logs/*`：Gemini/Claude 的 `stream-json` 原始输出（如启用外部模型）
- `<project>/.synapse/state.json` / `<project>/.synapse/index.json`：更新索引与状态

> 计划文件的 `session_id` 允许先占位（`TBD`），但推荐在 plan 阶段就从 Gemini `stream-json` 中捕获并写入，便于后续 `synapse execute --resume`。

## 输出（对 Codex）

脚本会在 stdout 打印：

- 计划文件路径
- context pack 路径
- 捕获到的 `gemini_session_id`（如果本次调用了 Gemini）

## 失败与恢复（关键）

- **Gemini 调用失败/超时**：
  - 仍会生成 plan 文件（`session_id: TBD`）
  - 可直接重跑 `synapse plan ...`（会生成新 plan 或覆盖同 slug 的 plan，取决于实现策略）
- **需要续跑**：
  - 后续用 `synapse execute <plan_path>`，脚本会优先读取 plan 中的 `gemini_session_id` 并 `--resume`
  - 即使清空 Codex 对话，也可以依靠 `<project>/.synapse/state.json` + plan 文件继续

