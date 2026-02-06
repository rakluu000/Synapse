# `synapse debug`

问题诊断：基于上下文包（包含 git 状态、rg 命中、关键文件片段），输出可执行的排查路径与可能修复建议（默认不改代码）。

## 用法

```bash
synapse debug <问题描述...>
```

## 主要产物

- `<project>/.synapse/context/<slug>-debug.md`
- `<project>/.synapse/patches/<slug>-debug-claude.md`
- `<project>/.synapse/logs/*`

## 失败与恢复

- 若缺少复现信息：补充日志/错误堆栈后重跑
- Claude 调用失败：不影响仓库；重跑即可

