# `synapse frontend`

前端/UI 专项：用 **Gemini** 产出 Unified Diff Patch（原型补丁），并落盘到 `./.synapse/patches/**`。

## 用法

```bash
synapse frontend <UI 需求文本...>
```

## 主要产物

- `<project>/.synapse/context/<slug>-frontend.md`：上下文包
- `<project>/.synapse/patches/<slug>-frontend-gemini.md`：模型原始文本
- `<project>/.synapse/patches/<slug>-frontend-gemini.diff`：提取出的 unified diff（如可提取）
- `<project>/.synapse/logs/*`：Gemini stream-json 原始输出

## 会话复用

- 若提供 `--resume <SESSION_ID>`（或从 `.synapse/state.json` / plan 文件读取到 session id），会优先复用会话，降低上下文重复投喂。

## 失败与恢复

- patch 提取失败：保留 `*.md` 原文；可手动复制 diff 或重跑
- 会话丢失：重跑不影响既有产物；会生成新日志与新 patch 文件

