# `synapse worktree`

Git worktree 管理（安全优先，避免误删/误覆盖）。

## 用法

```bash
synapse worktree <add|list|remove|prune|migrate> [args...]
```

## 默认目录策略

实现建议采用结构化目录（可配置）：

- `<repo-parent>/.synapse-worktrees/<repo-name>/<worktree-path>`

## 安全护栏

- `add/remove/migrate` 默认需要确认；`--yes` 可跳过
- 仅对 git 仓库生效；非 git 仓库直接拒绝
- `remove` 前必须验证 worktree 干净或明确 `--force`

## 失败与恢复

- worktree 被占用/锁定：提示解锁或手动处理
- 迁移失败：不应删除源 worktree；优先保持可回滚

