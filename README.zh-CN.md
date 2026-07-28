# BoardGate

[English](README.md)

BoardGate 是一个 Evidence-first、确定性的 PCB 投产审查 Agent。它将制造与
装配文件安全导入并转换为版本化的统一项目模型，执行可复现的 DFM 检查，
最终输出结构化 Findings、Markdown 报告和 SVG 预览。

项目遵守一条硬边界：文件解析、几何测量和规则判断必须由确定性代码完成。
Agent 只能组织和解释这些结果，不得编造几何数据、设计意图或投产保证。

## 当前状态

项目正在按照 [`IMPLEMENT_PCB_AGENT.md`](IMPLEMENT_PCB_AGENT.md) 实现 v0.1
CLI MVP。已经验证的仓库状态和唯一下一步维护在
[`HANDOFF.md`](HANDOFF.md) 中。

## 开发

前置条件：

- Python 3.12 或更高版本
- uv 0.11.x

```bash
uv sync --locked
uv run pcb-review --version
uv run pytest
```

目标审查接口：

```bash
pcb-review inspect INPUT... \
  --rules rules/default.yaml \
  --output artifacts/review
```

## 安全与范围

所有输入文件都按不可信数据处理。BoardGate 报告是工程审查证据，不是板厂
投产保证。初始 MVP 明确不实现原生 EDA 工程、ODB++、IPC-2581、SI/PI、
自动修改 PCB、Web API 或需要联网的 LLM Provider。

## 协作

任何参与者修改仓库前都必须阅读并遵守 [`HANDOFF.md`](HANDOFF.md)。它是
权威协作状态；仓库 Evidence 的优先级高于聊天记录或摘要。

## 许可证

Apache License 2.0，详见 [`LICENSE`](LICENSE)。
