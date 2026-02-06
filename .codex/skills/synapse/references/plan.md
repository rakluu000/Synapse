# `synapse plan`

生成**可复用会话**的实施计划文件（包含 `task_type` 路由信息），并为外部模型准备上下文包（context pack）。

## 用法

```bash
synapse plan --task-type <frontend|backend|fullstack> <需求文本...>
```

> 若不指定 `--task-type`：默认 `fullstack`（成本更高，但最不容易漏掉链路）。

## 模型分工（本阶段）

- **Claude**：架构/风险/边界/测试策略的主计划草案（默认总会调用）
- **Gemini**：仅当 `task_type` 包含 `frontend` 时，补充 UI/UX/可访问性相关计划草案
- **Codex（主控）**：对照两份草案，产出最终可执行计划并在后续阶段落地（脚本不自动合并）

## 写入哪些文件

- `<project>/.synapse/plan/<slug>.md`：计划文件（包含 `task_type`、需求、关键步骤、会话信息）
- `<project>/.synapse/context/<slug>-plan.md`：上下文包（用于投喂外部模型）
- `<project>/.synapse/patches/*`：
  - `*-plan-claude.md`：Claude 计划草案
  - `*-plan-gemini.md`：Gemini 计划草案（仅 frontend/fullstack）
- `<project>/.synapse/logs/*`：Gemini/Claude 的 `stream-json` 原始输出
- `<project>/.synapse/state.json` / `<project>/.synapse/index.json`：更新索引与状态

## 会话复用（关键）

- 脚本会从 `stream-json` 捕获并落盘 `session_id`（写入 plan meta）
- 后续 `synapse execute` 会优先从 plan meta 读取并 `--resume`，以降低重复上下文投喂

## 输出（stdout）

- `plan: <path>`
- `context_pack: <path>`
- `gemini_session_id: <id|TBD>`（仅 frontend/fullstack）
- `claude_session_id: <id|TBD>`

## 失败与恢复（关键）

- 外部模型调用失败/超时：
  - 仍会生成 plan 文件（`session_id: TBD`）
  - 修复环境后重跑 `synapse plan ...` 即可（会生成新日志；plan 可能覆盖同 slug 或产生同名后缀，取决于当前实现）
- 清空 Codex 对话后续跑：
  - 依靠 `<project>/.synapse/state.json` + plan 文件里的 `sessions` 继续执行
