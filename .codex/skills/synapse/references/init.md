# `synapse init`

初始化/修复 Synapse 在**目标项目根目录**的落盘结构与基础约束文件。

## 用法

```bash
synapse init
```

## 读写范围（强约束）

只允许写入/更新以下路径（幂等）：

- `<project>/AGENTS.md`
- `<project>/.gitignore`
- `<project>/.synapse/**`

## 主要产物

- `<project>/.synapse/index.json`：Synapse 索引（版本号、计划列表等）
- `<project>/.synapse/state.json`：Synapse 状态（最近一次命令、session id、最近计划等）
- `<project>/.synapse/{plan,context,logs,patches}/`：计划/上下文包/日志/补丁目录
- `<project>/.gitignore`：追加 `/.synapse/`（不存在则创建；已存在则不重复追加）
- `<project>/AGENTS.md`：
  - 若不存在：生成基础内容
  - 若存在：仅维护文件末尾的 Synapse 区块（用 `<!-- SYNAPSE-BEGIN -->` / `<!-- SYNAPSE-END -->` 标记替换）

## 失败与恢复

- **非 git 仓库**：项目根目录退化为当前目录；仍会创建 `.synapse/` 等产物
- **`.gitignore` 只读/权限不足**：不会影响 `.synapse/` 与 `AGENTS.md` 的生成；修复权限后重试即可
- **`AGENTS.md` 合并异常**：脚本只替换标记区块；如标记缺失会自动追加一个新标记区块到文件末尾

