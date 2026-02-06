# `synapse workflow`

分阶段工作流编排：`init → plan → execute → review`。

## 用法

```bash
synapse workflow [--yes] <需求文本...>
```

## 默认行为（重要）

- **默认每阶段都需要用户确认**再进入下一阶段。
- 若传 `--yes`：脚本将一路执行到底（适合 CI/沙盒/确定性任务）。

## 写入哪些文件

- 会调用 `init/plan/execute/review`，因此会写入：
  - `<project>/AGENTS.md`
  - `<project>/.gitignore`
  - `<project>/.synapse/**`（plan/context/logs/patches/state/index）

## 失败与恢复（关键）

- 任一阶段失败：
  - 已完成阶段的产物会保留在 `./.synapse/**`
  - 修复问题后可从失败阶段重跑：
    - plan 失败：重跑 `synapse plan ...`
    - execute 失败：重跑 `synapse execute <plan_path>`
    - review 失败：重跑 `synapse review`
- 若清空 Codex 对话：
  - 依赖 `.synapse/state.json`（最近 plan/execute 信息）
  - 以及 plan 文件里的 `session_id` 继续执行

