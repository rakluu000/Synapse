# `synapse test`

测试生成/补强：基于上下文包输出测试策略，并可生成测试补丁（Unified Diff）落盘到 `.synapse/patches/`。

## 用法

```bash
synapse test <目标或模块...>
```

## 主要产物

- `<project>/.synapse/context/<slug>-test.md`
- `<project>/.synapse/patches/<slug>-test-claude.md`
- `<project>/.synapse/patches/<slug>-test-claude.diff`（若能提取）
- `<project>/.synapse/logs/*`

## 注意

脚本只产出补丁文件；是否应用由 Codex 主控侧决定。

