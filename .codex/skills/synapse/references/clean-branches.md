# `synapse clean-branches`

安全清理分支：识别“已合并到基准分支”的本地分支，默认 **dry-run** 输出清单。

## 用法

```bash
synapse clean-branches [--base <branch>] [--stale <days>] [--remote] [--dry-run] [--yes] [--force]
```

## 默认安全护栏

- 默认 `--dry-run`
- 保护分支（至少包含 `main/master` 等）永不自动删除，除非显式 `--force` 且 `--yes`

## 失败与恢复

- 无法确定基准分支：提示用户显式传 `--base`
- 删除后需要恢复：可用 `git reflog` 或重新从远端拉取同名分支（如仍存在）

