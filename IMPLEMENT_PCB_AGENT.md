## Instruction Precedence

Before starting work, read the following files in order:

1. `BOOTSTRAP.md`
2. `IMPLEMENT_PCB_AGENT.md`
3. `HANDOFF.md`
4. Existing repository documentation

Their responsibilities are:

- `BOOTSTRAP.md` defines the repository-wide collaboration, evidence, commit,
  interruption-recovery, and HANDOFF maintenance protocol.
- `IMPLEMENT_PCB_AGENT.md` defines the PCB Manufacturing Review Agent's
  product scope, architecture, implementation phases, and acceptance criteria.
- `HANDOFF.md` records the current verified repository state, active issues,
  recent activity, and the exact next action.

When instructions conflict:

1. Safety and preservation of existing user work take highest priority.
2. Explicit project requirements in `IMPLEMENT_PCB_AGENT.md` override generic
   workflow guidance in `BOOTSTRAP.md`.
3. `HANDOFF.md` may refine the immediate next action, but it must not silently
   override product requirements or architectural decisions.
4. If a conflict cannot be resolved safely, record it as an Active Issue in
   `HANDOFF.md` and choose the smallest reversible action.

# PCB Manufacturing Review Agent — Implementation Protocol

你现在需要在当前代码仓库中实现一个面向 PCB 投产审查的垂域 Agent。

本任务可能无法在单次 Codex 使用额度内完成。因此，你必须采用：

* 增量实现
* 小步验证
* 原子 Git 提交
* 持续维护 `HANDOFF.md`
* 任意阶段可中断、可恢复
* Evidence-first
* 不以“看起来完成”为完成标准

你的首要目标不是一次性实现所有功能，而是建立一个能够持续演进、可验证、可由下一位参与者无缝接手的工程基础。

---

# 1. Product Definition

实现一个 PCB 投产前审查 Agent。

用户上传 PCB 制造与装配文件后，系统应能够：

1. 自动识别并归类工程文件。
2. 解析 Gerber RS-274X 文件。
3. 解析 Excellon Drill 文件。
4. 重建 PCB 的基础层结构和板框。
5. 将 PCB 数据转换为统一的项目中间表示。
6. 执行确定性的 DFM 检查。
7. 将检查结果保存为结构化 Findings。
8. 在 PCB 查看器中定位和高亮问题。
9. 由 Agent 对确定性结果进行归并、解释和生成修改建议。
10. 生成可供工程师审查的 Markdown 或 JSON 报告。

产品的核心原则是：

> Agent 负责组织工程验证流程、解释结果和管理不确定性；几何测量、文件解析和规则判断必须由确定性工具完成。

不得让 LLM 猜测：

* 图层含义
* 实际尺寸
* 几何距离
* 孔径
* 线宽线距
* 板框是否闭合
* 文件是否缺失
* BOM 与坐标文件是否一致

---

# 2. Initial MVP Scope

第一阶段只实现以下输入：

* Gerber RS-274X
* Excellon Drill
* ZIP 工程包
* BOM CSV/XLSX
* Pick and Place CSV
* YAML/JSON 格式的制造规则配置

暂时不要优先实现：

* 原理图语义理解
* Altium 原生工程解析
* KiCad 原生工程解析
* ODB++
* IPC-2581
* 信号完整性分析
* 电源完整性分析
* 自动修改 PCB
* 自动生成可生产 Gerber
* 复杂视觉模型
* 全自动器件封装识别
* 完整板厂报价系统

除非当前仓库已经可靠实现了其中部分功能，否则不要扩大 MVP 范围。

---

# 3. Required User Workflow

目标端到端工作流：

```text
上传 ZIP 或若干 PCB 文件
    ↓
识别文件类型
    ↓
生成 Project Manifest
    ↓
解析 Gerber / Drill / BOM / CPL
    ↓
构建统一 PCBProject
    ↓
校验坐标、单位、图层和文件完整性
    ↓
执行 DFM Rules
    ↓
生成结构化 Findings
    ↓
在 Viewer 中显示 PCB 与问题位置
    ↓
生成投产审查报告
```

最低可用的 CLI 工作流应类似：

```bash
pcb-review inspect ./examples/basic_board.zip \
  --rules ./rules/default.yaml \
  --output ./artifacts/basic_board
```

预期输出：

```text
artifacts/basic_board/
├── manifest.json
├── project.json
├── findings.json
├── report.md
├── preview.svg
└── logs/
```

如果仓库定位更适合 Web API，可以增加 API，但不得以 API 代替可测试的核心领域逻辑。

核心逻辑不得与 UI、HTTP 框架或 LLM Provider 强绑定。

---

# 4. Architecture Requirements

建议采用以下模块边界。你可以根据仓库现有结构调整目录，但必须保持职责分离。

```text
src/
├── ingestion/
│   ├── archive.py
│   ├── classifier.py
│   └── manifest.py
├── parsers/
│   ├── gerber/
│   ├── excellon/
│   ├── bom/
│   └── placement/
├── domain/
│   ├── project.py
│   ├── geometry.py
│   ├── layer.py
│   ├── component.py
│   ├── finding.py
│   └── rules.py
├── normalization/
│   ├── units.py
│   ├── coordinates.py
│   └── layer_mapping.py
├── geometry/
│   ├── spatial_index.py
│   ├── distance.py
│   ├── connectivity.py
│   └── outline.py
├── rules/
│   ├── engine.py
│   ├── registry.py
│   └── builtin/
├── agent/
│   ├── orchestrator.py
│   ├── risk_modes.py
│   ├── tools.py
│   └── reporting.py
├── rendering/
│   └── svg.py
├── application/
│   └── review_service.py
├── cli/
└── api/
```

不要为了匹配该示意结构而无意义地重构已有仓库。

先检查现有架构，再将这些职责映射到最合适的位置。

---

# 5. Unified Domain Model

必须建立与解析库解耦的统一中间表示。

最低应包含以下概念。

## 5.1 PCBProject

```python
class PCBProject:
    project_id: str
    source_files: list[SourceFile]
    manifest: ProjectManifest
    units: Unit
    coordinate_system: CoordinateSystem
    layers: list[PCBLayer]
    board_outline: BoardOutline | None
    drills: list[DrillHit]
    components: list[ComponentPlacement]
    bom_items: list[BOMItem]
    fabrication_requirements: FabricationRequirements
    assembly_requirements: AssemblyRequirements
    metadata: dict[str, object]
    uncertainties: list[Uncertainty]
```

字段可以根据语言和仓库技术栈调整，但中间表示必须：

* 可序列化
* 可版本化
* 可测试
* 不直接暴露第三方解析库对象
* 能记录信息来源
* 能表达未知值
* 能表达解析置信度或不确定性

禁止使用空字符串或魔法值伪装未知状态。

---

## 5.2 Source Provenance

所有重要对象都应能够追踪到来源，例如：

```json
{
  "source_file": "board.GTL",
  "source_type": "gerber",
  "object_id": "primitive-1831",
  "line_number": 248,
  "parser": "internal-gerber-parser",
  "parser_version": "0.1.0"
}
```

不是每个对象都必须包含文本行号，但必须尽可能保留：

* 来源文件
* 原始对象标识
* 解析器
* 原始坐标或相关元数据

---

## 5.3 Finding

所有审查结果必须使用结构化 Finding，而不是仅生成文本消息。

建议模型：

```json
{
  "finding_id": "DFM-017",
  "rule_id": "copper_to_edge",
  "category": "GEOMETRY_VIOLATION",
  "severity": "BLOCKER",
  "confidence": 0.99,
  "status": "OPEN",
  "title": "Copper too close to board edge",
  "summary": "Top copper is 0.18 mm from the board edge.",
  "location": {
    "x": 42.315,
    "y": 18.640,
    "unit": "mm"
  },
  "layers": ["top_copper"],
  "measurement": {
    "actual": 0.18,
    "required": 0.25,
    "operator": ">=",
    "unit": "mm"
  },
  "evidence": [
    {
      "source_file": "board.GTL",
      "object_id": "track-1831"
    },
    {
      "source_file": "board.GKO",
      "object_id": "outline-42"
    }
  ],
  "suggested_action": "Increase copper-to-edge clearance to at least 0.25 mm.",
  "requires_human_confirmation": false,
  "related_findings": []
}
```

Finding ID 必须稳定或至少在同一次运行中唯一。

Finding 中应区分：

* 事实测量
* 规则要求
* 推断
* 修改建议
* 人工确认需求

---

# 6. Risk Modes

Agent 在执行或解释任务前，应显式识别风险模式。

第一版至少支持：

```text
FILE_INCOMPLETE
FILE_TYPE_UNKNOWN
UNIT_AMBIGUITY
COORDINATE_MISMATCH
LAYER_MAPPING_UNCERTAIN
OUTLINE_UNCERTAIN
GEOMETRY_VIOLATION
CROSS_FILE_INCONSISTENCY
DESIGN_INTENT_UNKNOWN
MANUFACTURER_RULE_MISMATCH
PARSER_LIMITATION
```

每个风险模式必须对应明确行为。

例如：

## FILE_INCOMPLETE

* 列出缺失文件或缺失能力。
* 不得输出无条件的“可以投产”结论。
* 可以继续执行不依赖缺失文件的检查。
* 在最终报告中降低结论置信度。

## UNIT_AMBIGUITY

* 不得默认猜测单位。
* 尝试根据文件声明、尺寸合理性和跨文件一致性消歧。
* 如果仍然无法消歧，生成待确认 Finding。
* 不得继续执行会产生误导的精确距离判断。

## LAYER_MAPPING_UNCERTAIN

* 保存候选映射及证据。
* 请求人工确认或标记为待确认项。
* 不得将不确定层直接认定为铜层、阻焊层或板框层。

## DESIGN_INTENT_UNKNOWN

* 只报告可测量事实。
* 不得编造设计意图。
* 可以提出需要工程师确认的问题。

---

# 7. Initial Deterministic Rules

优先实现高确定性规则。

第一阶段目标规则：

1. `required_layers_present`
2. `drill_file_present`
3. `board_outline_present`
4. `board_outline_closed`
5. `multiple_outline_regions`
6. `gerber_drill_coordinate_alignment`
7. `minimum_trace_width`
8. `minimum_copper_spacing`
9. `minimum_copper_to_edge`
10. `minimum_drill_diameter`
11. `minimum_annular_ring`
12. `silkscreen_over_exposed_pad`
13. `minimum_solder_mask_dam`
14. `bom_placement_reference_match`
15. `duplicate_reference_designator`
16. `placement_outside_board_outline`

不要同时粗糙实现全部规则。

按照后面的阶段计划逐步实现，每条规则都必须有：

* 唯一 `rule_id`
* 配置 Schema
* 明确输入
* 明确输出
* 单元测试
* 正例
* 反例
* 边界测试
* Finding Evidence
* 文档说明
* 已知限制

如果当前阶段只能可靠实现其中部分规则，应优先保证正确性，而不是用近似算法假装覆盖全部范围。

---

# 8. Manufacturing Rule Configuration

实现可版本化的规则配置。

示例：

```yaml
schema_version: "1.0"

profile:
  id: default-prototype-2layer
  name: Default Prototype 2-Layer
  manufacturer: generic
  revision: 1

units: mm

fabrication:
  min_trace_width: 0.10
  min_copper_spacing: 0.10
  min_copper_to_edge: 0.25
  min_drill_diameter: 0.20
  min_annular_ring: 0.10
  min_solder_mask_dam: 0.10

severity:
  minimum_trace_width: blocker
  minimum_copper_spacing: blocker
  minimum_copper_to_edge: warning
```

规则配置必须经过 Schema 校验。

错误配置必须快速失败，并提供可理解的错误信息。

不得在业务代码中散落硬编码工艺阈值。

---

# 9. Agent Responsibilities

Agent 只能基于工具提供的结构化数据进行推理。

Agent 的职责：

* 规划审查步骤
* 根据已有文件决定调用哪些工具
* 识别风险模式
* 汇总解析结果
* 归并重复 Findings
* 区分阻断项、高风险项、待确认项和优化建议
* 解释制造风险
* 生成修改建议
* 生成最终报告
* 明确表达不确定性

Agent 不得：

* 自行计算精确几何距离
* 从截图猜测线宽
* 在缺少证据时判断设计意图
* 将解析失败描述为设计错误
* 隐藏工具错误
* 将“未检查”描述为“检查通过”
* 因为没有发现问题就宣称一定可制造

第一版允许使用确定性的 Report Composer 代替真实 LLM。

核心架构必须支持后续接入 LLM Provider，但测试不得依赖外部模型服务。

---

# 10. Report Structure

生成的 `report.md` 至少包含：

```text
# PCB Manufacturing Review

## Executive Summary
- Overall status
- Confidence
- Blocker count
- Warning count
- Confirmation-required count

## Input Files
- Recognized files
- Unknown files
- Missing expected files

## Project Interpretation
- Units
- Coordinate system
- Layer mapping
- Board dimensions
- Drill summary
- BOM/CPL summary

## Blockers

## High-Risk Findings

## Requires Human Confirmation

## Optimization Suggestions

## Rules Executed

## Rules Not Executed
- Rule
- Reason
- Missing dependency

## Parser and Analysis Limitations

## Evidence Index
```

最终状态不得只使用 `PASS/FAIL`。

建议使用：

```text
READY_FOR_REVIEW
NOT_READY_FOR_FABRICATION
READY_WITH_CONFIRMATIONS
INSUFFICIENT_INFORMATION
ANALYSIS_FAILED
```

---

# 11. Visualization

MVP 优先实现 SVG 预览，而不是复杂 WebGL。

SVG 至少支持：

* 板框
* 铜层基础图元
* 钻孔
* 可配置图层可见性
* Finding 标记
* Finding ID 标签
* 基础坐标变换
* 自动适配 ViewBox

暂不追求：

* 完整 CAM 渲染精度
* 复杂阴影或 3D
* 高性能超大板实时交互
* 像素级复刻商业 Gerber Viewer

渲染层不得成为规则引擎的数据来源。

---

# 12. Security Requirements

所有上传文件都视为不可信输入。

至少处理：

* ZIP 路径穿越
* ZIP Bomb 基础限制
* 单文件尺寸限制
* 总解压尺寸限制
* 文件数量限制
* 异常文件名
* 重复文件名
* 不支持格式
* 解析超时或复杂度限制
* 临时目录清理
* 错误信息中避免泄露本机敏感路径

不得执行工程包中的任何脚本或二进制文件。

---

# 13. Testing Strategy

必须建立分层测试。

## Unit Tests

覆盖：

* 文件分类
* 单位转换
* 坐标转换
* 图层映射
* Domain Model 序列化
* 配置 Schema
* Finding 生成
* 每条规则
* ZIP 安全处理

## Golden Fixture Tests

在 `tests/fixtures/` 或等效目录维护最小工程样本：

```text
valid_minimal_board/
missing_drill/
open_outline/
copper_too_close_to_edge/
coordinate_mismatch/
bom_cpl_mismatch/
ambiguous_layer_names/
malformed_gerber/
```

每个 Fixture 应尽量小且可读。

为关键结果保存 Golden JSON，但避免因无关字段导致测试脆弱。

## Integration Tests

至少验证：

```text
输入工程包
→ 解析
→ 构建 PCBProject
→ 执行规则
→ 输出 Findings
→ 生成报告和 SVG
```

## Regression Tests

每修复一个实际 Bug，都增加对应回归测试。

---

# 14. Logging and Diagnostics

采用结构化日志。

关键阶段至少记录：

* run ID
* project ID
* 输入文件数量
* 文件分类结果
* 解析器选择
* 解析耗时
* 图元数量
* Drill 数量
* 执行规则
* 跳过规则及原因
* Finding 数量
* 错误类型

错误必须区分：

```text
UserInputError
UnsupportedFormatError
ParseError
NormalizationError
RuleConfigurationError
RuleExecutionError
RenderingError
AgentError
InternalError
```

不得捕获所有异常后只输出“处理失败”。

---

# 15. Implementation Principles

必须遵守以下原则：

## 15.1 Evidence First

任何审查结论都必须能追溯到：

* 输入文件
* 解析对象
* 测量结果
* 规则配置
* 检查版本

## 15.2 Deterministic Core

无 LLM、无网络时，核心审查流程仍然可运行。

## 15.3 Explicit Uncertainty

未知和未支持状态必须显式保存。

## 15.4 Fail Closed for Production Conclusions

当关键输入不完整或单位不确定时，不得给出“可直接投产”结论。

## 15.5 No Narrative Completion

不得根据常见 PCB 习惯补全缺失事实。

## 15.6 Small Vertical Slices

优先完成可运行的纵向切片，而不是一次铺开所有目录和空接口。

## 15.7 No Hollow Scaffolding

不要创建大量只有 `TODO`、`pass` 或抛出 `NotImplementedError` 的文件，并将其称为架构完成。

允许创建必要接口，但每个阶段必须产生可运行价值。

---

# 16. Mandatory Git and Continuity Protocol

这是本任务最重要的执行要求之一。

任务可能因为额度耗尽而随时中断。你必须保证任意时刻仓库都尽可能处于可恢复状态。

## 16.1 Before Editing

开始前必须：

1. 阅读整个仓库结构。
2. 阅读已有 README、设计文档、测试配置和贡献规范。
3. 检查当前 Git 状态。
4. 检查是否有未提交改动。
5. 不得覆盖或删除不属于你的已有改动。
6. 运行现有测试或最小健康检查。
7. 阅读仓库根目录的：

   * `HANDOFF.md`
   * `BOOTSTRAP.md`
   * `IMPLEMENT_PCB_AGENT.md`

   如果存在。

如果 `HANDOFF.md` 不存在，创建它。

如果已有未提交改动：

* 首先识别改动来源和作用。
* 不要直接 reset、checkout 或删除。
* 尽量在其基础上继续。
* 如果无法安全区分，应在 `HANDOFF.md` 中记录，并避免修改相关文件。

---

## 16.2 Commit Rules

必须采用小步原子提交。

推荐每个提交只完成一种明确变化，例如：

```text
chore: establish project quality gates
feat(domain): add versioned PCB project model
feat(ingestion): classify Gerber and drill files
feat(parser): parse Excellon drill coordinates
feat(rules): detect missing drill files
feat(rendering): generate SVG board outline preview
test(integration): add minimal review pipeline fixture
docs: document current parser limitations
```

禁止：

* 一个提交同时包含大量无关重构和新功能
* 几千行改动后才第一次提交
* 将失败测试留在普通阶段提交中
* 使用 `wip` 作为常态提交信息
* 修改代码后长期不提交
* 在未验证的情况下声称功能完成

每个提交前必须：

1. 检查 diff。
2. 运行与改动相关的测试。
3. 运行 lint/type-check，若项目已配置。
4. 确认没有意外生成文件。
5. 更新必要文档。
6. 更新 `HANDOFF.md`。
7. 记录测试 Evidence。
8. 然后提交。

每个逻辑阶段至少产生一个提交。

推荐每完成 30–90 分钟粒度的独立工作单元就提交；不要等待整个 Phase 完成。

---

## 16.3 Never Leave Large Uncommitted Work

在开始一个较大工作单元前，先确保：

```bash
git status
```

处于已知状态。

如果预计一个功能无法在剩余额度内完成，应先进一步切小。

例如不要直接开始：

```text
完整 Gerber 解析器
```

而应拆成：

```text
1. Gerber lexer and command model
2. Format/unit declarations
3. Aperture definitions
4. Linear interpolation
5. Flash primitives
6. Region support
7. Arc interpolation
8. Polarity handling
9. Fixture coverage
```

每一步都应尽量：

* 可测试
* 可提交
* 不破坏已有功能
* 能在下一次继续

---

# 17. HANDOFF.md Protocol

`HANDOFF.md` 是跨 Codex Session 的权威接力文档。

它不是普通开发日志，而是下一位参与者恢复工作所需的最小充分上下文。

必须保持以下结构：

```markdown
# HANDOFF

## Current State

## Active Issues

## Next Action

## Recent Activity

## Archived Summary
```

---

## 17.1 Current State

记录当前真实状态：

* 当前分支
* 最新提交
* 当前已完成 Phase
* 可运行入口
* 当前支持的输入格式
* 当前已实现规则
* 测试状态
* 已知限制

示例：

```markdown
## Current State

- Branch: `feature/pcb-review-agent`
- HEAD: `abc1234 feat(ingestion): add project manifest`
- Existing tests: 84 passed
- CLI:
  `pcb-review inspect <path> --rules <profile>`
- Supported:
  - ZIP ingestion
  - Gerber file classification
  - Excellon drill parsing
- Not yet supported:
  - Gerber regions
  - Arc interpolation
  - Copper-spacing rule
```

只记录已经由 Evidence 验证的能力。

---

## 17.2 Active Issues

每个未闭环事项使用稳定 ID：

```markdown
### ISSUE-007 — Gerber arc interpolation unsupported

- Status: OPEN
- Severity: medium
- Context:
- Evidence:
- Suspected cause:
- Attempted approaches:
- Remaining work:
- Relevant files:
- Blocking:
```

Issue 状态至少包括：

```text
OPEN
IN_PROGRESS
BLOCKED
RESOLVED
SUPERSEDED
```

不得因为暂时不处理就删除 Issue。

---

## 17.3 Next Action

必须写成下一位参与者可以直接执行的动作。

错误示例：

```text
继续做 Gerber。
```

正确示例：

```markdown
## Next Action

Implement linear interpolation for D01 draw commands.

Start with:
- `src/parsers/gerber/commands.py`
- `src/parsers/gerber/parser.py`
- `tests/fixtures/gerber/simple_trace.gbr`

Acceptance criteria:
1. Parse one horizontal and one vertical D01 segment.
2. Preserve source provenance.
3. Normalize coordinates to millimeters.
4. Add unit tests and one golden fixture.
5. Run `pytest tests/parsers/gerber`.
6. Commit separately before starting aperture flashes.
```

`Next Action` 一次只指定一个最合理的下一工作单元。

---

## 17.4 Recent Activity

记录最近若干轮完整活动：

```markdown
### 2026-07-28 — Session N

Goal:
Changes:
Files:
Commands run:
Tests:
Evidence:
Commit:
Remaining uncertainty:
```

不得只写“implemented parser”。

必须包含实际执行过的命令和结果摘要。

---

## 17.5 Archived Summary

当 `HANDOFF.md` 超过约 800–1200 行时：

1. 不要无限追加。
2. 将已闭环的旧活动压缩到 `Archived Summary`。
3. 保留所有未解决 Issue。
4. 保留关键架构决策。
5. 保留未验证假设。
6. 保留重要失败尝试。
7. 保留仍然影响当前实现的历史兼容信息。
8. 不得压缩掉下一位参与者继续工作所需的信息。

---

# 18. Evidence Requirements

任何“完成”声明必须附带 Evidence。

Evidence 可以包括：

* 测试命令与结果
* CLI 实际运行结果
* 生成的文件路径
* JSON 片段
* SVG 预览
* Fixture 名称
* Git commit hash
* Benchmark 数据
* 静态检查结果

例如：

```markdown
Evidence:

- `pytest tests/rules/test_missing_drill.py -q`
  - Result: `5 passed`
- `pcb-review inspect tests/fixtures/missing_drill`
  - Result: generated `FILE-001`
  - Severity: `BLOCKER`
  - Risk mode: `FILE_INCOMPLETE`
- Commit: `38ad91c`
```

不得将以下内容视为 Evidence：

* “代码看起来合理”
* “应该可以运行”
* “理论上已支持”
* “接口已经留好”
* “大部分完成”
* 未执行的测试命令
* 仅由 LLM 自己阅读代码得出的判断

如果没有验证，明确写：

```text
IMPLEMENTED BUT NOT VERIFIED
```

或：

```text
UNVERIFIED
```

---

# 19. Implementation Phases

按照以下顺序推进。

如果仓库已有部分能力，先验证再调整阶段，不要重复实现。

---

## Phase 0 — Repository Audit and Quality Baseline

目标：

* 理解现有代码
* 确立开发基线
* 避免破坏已有功能

任务：

1. 检查仓库架构。
2. 识别语言、包管理器和运行入口。
3. 运行现有测试。
4. 识别现有 PCB、Gerber 或 Agent 相关实现。
5. 记录技术债和冲突。
6. 创建或更新 `HANDOFF.md`。
7. 创建简短架构说明。
8. 确保 `.gitignore` 合理。
9. 确保基础 lint/test 命令明确。

交付：

* Repository audit 记录
* 测试基线
* 第一条 HANDOFF 记录
* 独立提交

验收：

* 下一位参与者无需重新猜测仓库如何运行。
* 当前失败测试被准确记录。
* 未擅自修复无关问题。

推荐提交：

```text
docs: record PCB agent implementation baseline
```

---

## Phase 1 — Domain Model and Configuration

目标：

* 建立统一 PCBProject
* 建立 Finding
* 建立规则配置 Schema

任务：

1. 建立单位模型。
2. 建立坐标和 Bounding Box。
3. 建立 Source Provenance。
4. 建立 PCBProject。
5. 建立 Layer、DrillHit、BoardOutline。
6. 建立 Finding。
7. 建立 RiskMode。
8. 建立规则 Profile Schema。
9. 支持 JSON 序列化和反序列化。
10. 添加单元测试。

验收：

* Domain Model 不依赖具体 Parser。
* 未知值可显式表达。
* 配置错误会快速失败。
* Round-trip 序列化测试通过。

拆分提交建议：

```text
feat(domain): add geometry and provenance models
feat(domain): add PCB project and finding schemas
feat(config): validate manufacturing rule profiles
```

---

## Phase 2 — Safe Ingestion and Project Manifest

目标：

* 安全接收文件和 ZIP
* 自动生成 Manifest

任务：

1. 安全解压。
2. 文件大小和数量限制。
3. 文件哈希。
4. 文件类型初步识别。
5. Gerber、Drill、BOM、CPL 候选分类。
6. 未知文件记录。
7. 重复和冲突检测。
8. Project Manifest 输出。
9. CLI 最小入口。

验收：

* ZIP 路径穿越测试通过。
* 能对 Fixture 生成稳定 Manifest。
* 不支持文件不会导致整个进程无信息崩溃。
* CLI 能输出 `manifest.json`。

拆分提交建议：

```text
feat(ingestion): safely extract PCB project archives
feat(ingestion): classify project files and build manifest
feat(cli): add project inspection entry point
```

---

## Phase 3 — Excellon Drill Vertical Slice

优先做 Drill，是因为范围比完整 Gerber 更容易控制。

目标：

* 解析基础 Excellon 文件
* 输出 DrillHit
* 支持基本可视化和统计

首批支持：

* 单位声明
* Tool 定义
* Tool 选择
* 绝对坐标
* Drill Hit
* 常见零抑制格式

暂不支持的语法必须显式报告。

验收：

* 至少三个 Excellon Fixtures。
* 坐标转换正确。
* Tool 与 DrillHit 关联正确。
* 解析错误包含来源位置。
* `project.json` 中可见 Drill 数据。
* SVG 可显示钻孔点。

拆分提交建议：

```text
feat(excellon): parse units and drill tools
feat(excellon): parse drill hit coordinates
feat(rendering): render drill hits in SVG
```

---

## Phase 4 — Gerber Foundation

不要一次实现完整 Gerber。

按照以下顺序小步实现：

### 4A

* 文件头
* 单位
* Format Specification
* Aperture Definition
* D02 Move
* D01 Linear Draw
* D03 Flash

### 4B

* Region
* Polarity
* Step and Repeat，如果需要
* 基础 Arc

### 4C

* 更复杂 Aperture
* Macro 的有限支持
* Parser Limitation Diagnostics

每个语法能力单独添加 Fixture。

验收：

* 能解析最小板框 Gerber。
* 能解析简单铜线和 Flash。
* 保留来源 Provenance。
* 所有坐标统一规范化。
* 不支持命令不会被静默忽略。
* SVG 能显示解析结果。

拆分提交应非常细，不要等完整 Gerber 支持后一次提交。

---

## Phase 5 — Layer Mapping and Board Outline

目标：

* 建立候选图层映射
* 提取板框
* 表达映射不确定性

任务：

1. 基于扩展名识别。
2. 基于文件名识别。
3. 基于 Gerber 属性识别。
4. 多证据冲突检测。
5. 候选层映射。
6. 板框轮廓提取。
7. 闭合检查。
8. 多轮廓检查。
9. 计算板尺寸。

验收：

* 不确定映射不会被强制确定。
* 能生成 `LAYER_MAPPING_UNCERTAIN`。
* 简单矩形板框可正确闭合。
* 开放轮廓 Fixture 可生成 Finding。
* 多轮廓 Fixture 可生成 Finding。

拆分提交建议：

```text
feat(layers): infer layer roles with evidence
feat(outline): reconstruct board outline
feat(rules): detect missing and open board outlines
```

---

## Phase 6 — Rule Engine Foundation

目标：

* 建立可扩展规则注册和执行系统

规则接口至少表达：

```text
rule_id
rule_version
requirements
configuration
execute(project, context)
findings
skip_reason
```

规则必须能够区分：

* PASS
* FINDINGS
* SKIPPED
* FAILED

`SKIPPED` 不等于 `PASS`。

验收：

* 规则注册稳定。
* 单条规则异常不应隐藏。
* 报告中列出已执行、跳过和失败规则。
* 支持按 Rule ID 过滤。
* 支持 Rule Profile。

拆分提交建议：

```text
feat(rules): add deterministic rule engine
feat(rules): report skipped and failed checks explicitly
```

---

## Phase 7 — File Completeness and Cross-File Rules

优先实现：

1. `required_layers_present`
2. `drill_file_present`
3. `board_outline_present`
4. `board_outline_closed`
5. `duplicate_reference_designator`
6. `bom_placement_reference_match`
7. `placement_outside_board_outline`

这需要先实现 BOM 和 CPL 的基础解析。

验收：

* 每条规则独立测试。
* Finding 包含 Evidence。
* BOM/CPL 差异区分：

  * BOM only
  * CPL only
  * duplicate
  * ignored reference
* 支持 DNP/Do Not Populate 的基础表达。

拆分提交建议：

```text
feat(bom): parse normalized BOM records
feat(placement): parse component placements
feat(rules): detect BOM and placement inconsistencies
```

---

## Phase 8 — Geometry Rules

只在几何模型可靠后开始。

推荐顺序：

1. `minimum_drill_diameter`
2. `minimum_copper_to_edge`
3. `minimum_trace_width`
4. `minimum_copper_spacing`
5. `minimum_annular_ring`
6. `minimum_solder_mask_dam`
7. `silkscreen_over_exposed_pad`

每个规则先实现一个受限但精确定义的版本。

例如：

```text
minimum_trace_width v1:
只检查由简单线性 Draw 形成、宽度直接来自圆形 Aperture 的 Trace。
不检查复杂 Region、Macro 或经过布尔运算的图形。
```

必须在报告中明确版本限制。

不得使用一个粗糙 Bounding Box 距离代替真实几何距离，却将结果描述为精确 DFM 判断。

验收：

* 几何单位一致。
* 空间索引结果与暴力基准在小 Fixture 上一致。
* 每条 Finding 包含 actual 和 required。
* 支持问题坐标定位。
* SVG 可高亮对应 Finding。

每条规则建议独立提交。

---

## Phase 9 — End-to-End Review Pipeline

目标：

实现完整纵向流程：

```text
input
→ ingestion
→ parsing
→ normalization
→ project model
→ rule engine
→ findings
→ report
→ SVG
```

验收命令：

```bash
pcb-review inspect tests/fixtures/valid_minimal_board \
  --rules rules/default.yaml \
  --output /tmp/pcb-review-valid
```

以及：

```bash
pcb-review inspect tests/fixtures/copper_too_close_to_edge \
  --rules rules/default.yaml \
  --output /tmp/pcb-review-edge
```

必须验证：

* 输出目录完整。
* JSON Schema 合法。
* 报告状态正确。
* Findings 数量符合 Golden。
* SVG 包含 Finding ID。
* 同一输入重复运行时，除时间戳等字段外输出稳定。

推荐提交：

```text
feat(review): integrate end-to-end PCB review pipeline
test(review): add golden end-to-end project fixtures
```

---

## Phase 10 — Agent Orchestration

只有确定性管线完成后再实现 Agent。

第一版可以使用本地、确定性的 Orchestrator：

1. 检查 Manifest。
2. 识别风险模式。
3. 判断哪些 Parser 可运行。
4. 判断哪些 Rule 可运行。
5. 收集 Finding。
6. 归并同源 Finding。
7. 生成分层报告。

然后再提供可选 LLM Adapter。

LLM Adapter 必须：

* 使用结构化输入
* 使用结构化输出
* 不覆盖测量值
* 不修改 Evidence
* 不将不确定结论升级为事实
* 保留原始 Findings
* 可完全禁用
* 在测试中使用 Fake Provider

验收：

* 无 API Key 时系统仍可运行。
* Agent 不会将 skipped rule 描述为 passed。
* Agent 不会在缺 Drill 时给出 READY 状态。
* LLM 输出非法时回退到确定性报告。
* LLM Provider 错误不会破坏核心结果。

拆分提交建议：

```text
feat(agent): orchestrate review steps using risk modes
feat(agent): compose evidence-backed review summaries
feat(agent): add optional structured LLM adapter
```

---

## Phase 11 — API or Minimal Web Viewer

只有核心流程稳定后再做。

API 可包含：

```text
POST /projects
POST /projects/{id}/review
GET  /projects/{id}
GET  /projects/{id}/findings
GET  /projects/{id}/report
GET  /projects/{id}/preview.svg
```

如果实现前端，第一版只需：

* 上传项目
* 查看文件 Manifest
* 查看 PCB SVG
* 切换基础图层
* 查看 Findings
* 点击 Finding 定位
* 下载报告

不要在核心能力不完整时优先投入 UI 美化。

---

# 20. Decision Records

重要设计选择必须记录 ADR 或等效文档，例如：

```text
docs/adr/
├── 0001-unified-project-model.md
├── 0002-deterministic-rule-engine.md
├── 0003-source-provenance.md
└── 0004-gerber-parser-strategy.md
```

至少记录：

* 为什么选择该方案
* 替代方案
* 已知代价
* 未来迁移条件

尤其需要记录：

* 使用第三方 Gerber 解析库还是自研
* 几何库选择
* 数据模型版本策略
* Finding 稳定 ID 策略
* SVG 渲染方案
* LLM Provider 边界

不要为每个小决定写 ADR。

---

# 21. Dependency Policy

添加依赖前必须：

1. 检查仓库已有依赖。
2. 确认许可证可接受。
3. 确认项目仍然维护。
4. 评估是否真的需要。
5. 将第三方对象隔离在 Adapter 后。
6. 添加最小使用说明。
7. 记录版本约束。

不得仅因为第三方库声称支持 Gerber 就假定其结果正确。

必须使用 Fixtures 验证实际行为。

如果库无法提供来源追踪或稳定几何模型，应通过 Adapter 转换到内部 Domain Model。

---

# 22. Performance Guidance

MVP 优先正确性，但避免明显不可扩展设计。

基础目标可设为：

* 小型工程包可在合理时间内完成。
* 空间查询使用索引，而不是所有规则都做全量 O(n²)。
* Parser 尽量流式处理。
* 不在日志中输出所有几何对象。
* 不在 Finding 中复制巨大几何数据。
* 大文件限制可配置。

如果进行性能优化，先添加 Benchmark，再修改实现。

不要提前做复杂并行化。

---

# 23. What To Do When Context or Quota Is Running Low

当你判断当前 Session 的上下文、时间或额度可能不足时：

1. 立即停止开启新的大功能。
2. 完成当前最小可闭环单元。
3. 删除无效临时代码。
4. 运行相关测试。
5. 更新文档。
6. 更新 `HANDOFF.md`。
7. 提交当前已验证成果。
8. 检查 `git status`。
9. 将剩余工作拆为明确的 `Next Action`。
10. 输出最终接力摘要。

禁止：

* 在额度即将耗尽时开始大型重构
* 留下数百行未提交改动
* 仅在聊天回复中描述状态而不写入仓库
* 声称“下次可以继续”却不留下明确入口
* 将失败实现提交为完成状态
* 为了赶进度跳过验证

如果存在无法安全提交的部分：

* 保存最小 Patch 或 Draft 文件。
* 在 `HANDOFF.md` 明确标记 `UNCOMMITTED / UNVERIFIED`。
* 说明涉及文件。
* 说明为什么不能提交。
* 说明恢复方法。
* 不得将其与已验证实现混在同一个完成声明里。

---

# 24. Required Final Response for Every Session

每次 Session 结束时，回复必须包含：

```text
Session goal:
Completed:
Commits:
Tests executed:
Generated artifacts:
Known limitations:
Active issues:
Exact next action:
Working tree status:
```

示例：

```text
Session goal:
Implement safe ZIP ingestion and project manifest.

Completed:
- Added ZIP traversal protection.
- Added file count and extracted-size limits.
- Added SHA-256 source file records.
- Added initial Gerber/Excellon classification.

Commits:
- a83f019 feat(ingestion): safely extract PCB project archives
- f21e74a feat(ingestion): build project manifest

Tests executed:
- pytest tests/ingestion -q
- 24 passed

Generated artifacts:
- tests/output/minimal_manifest.json

Known limitations:
- Content-based Gerber detection is not implemented.
- Nested archives are rejected.

Active issues:
- ISSUE-003: ambiguous `.txt` drill files.

Exact next action:
Implement content-based Excellon detection using the fixtures listed in HANDOFF.md.

Working tree status:
Clean.
```

不得只回复“完成了”。

---

# 25. First Session Instructions

现在开始执行，但第一轮不要直接大规模编码。

按照以下顺序行动：

1. 检查当前工作目录和 Git 状态。
2. 阅读仓库结构和所有现有文档。
3. 查找已有 PCB、Gerber、CAM、DFM、Agent、Memory 或 Handoff 相关实现。
4. 运行现有测试、lint 和 type-check，记录真实结果。
5. 判断这是：

   * 新项目
   * 已有项目扩展
   * 已有半成品实现
6. 将上面的目标架构映射到当前仓库，不要机械复制目录。
7. 创建或更新 `HANDOFF.md`。
8. 创建第一版实施计划，但只把最近 2–3 个可提交工作单元写得详细。
9. 选择一个最小纵向切片开始实现。
10. 完成测试后立即提交。
11. 更新 `HANDOFF.md`。
12. 如果额度允许，再进入下一个小工作单元。

首个纵向切片优先级：

```text
Domain Model
→ Rule Profile Schema
→ Safe File Manifest
→ CLI 输出 manifest.json
```

不要在第一步就尝试完成完整 Gerber Parser。

---

# 26. Definition of Done

一个 Phase 只有满足以下条件才算完成：

* 功能实现
* 单元测试通过
* 必要集成测试通过
* 错误路径经过测试
* Evidence 可追踪
* 文档更新
* HANDOFF 更新
* Git 提交完成
* Working Tree 状态已知
* 已知限制明确记录
* 下一阶段入口清晰

以下情况不算完成：

* 仅创建接口
* 仅创建目录
* 仅写设计文档
* 仅实现 Happy Path
* 测试未运行
* 依赖真实 LLM 才能运行
* 输出无法追踪到输入证据
* 修改尚未提交
* HANDOFF 未更新

---

# 27. Non-Goals and Guardrails

不要做以下事情：

* 不要重写整个仓库，除非已有架构完全不可用并有充分证据。
* 不要删除现有功能来简化实现。
* 不要修改无关代码风格。
* 不要将大规模格式化与功能提交混在一起。
* 不要伪造测试结果。
* 不要伪造 Commit。
* 不要假装支持未实现的 Gerber 命令。
* 不要吞掉 Parser Warning。
* 不要自动将未知层映射成最可能的层后隐藏不确定性。
* 不要让 LLM 直接读取任意文件并生成“检查通过”。
* 不要把截图视觉判断作为精密 DFM 测量。
* 不要为了展示 Agent 而绕开确定性 Rule Engine。
* 不要在没有 Evidence 的情况下输出生产安全保证。
* 不要自动 push、force push、rebase 或修改远程历史。
* 不要使用 `git reset --hard` 或清除用户工作，除非用户明确要求。

---

# 28. Desired End State

长期目标是形成以下可靠系统：

```text
PCB Project Files
        ↓
Safe Ingestion
        ↓
Normalized PCB Intermediate Representation
        ↓
Deterministic Geometry and Cross-File Checks
        ↓
Evidence-Backed Findings Graph
        ↓
Risk-Aware Agent Orchestration
        ↓
Human-Reviewable Manufacturing Decision
        ↓
Revision and Issue Closure Loop
```

最终系统最重要的品质不是“回答得像资深工程师”，而是：

* 每个结论有证据
* 每个测量可复现
* 每个未知被明确表达
* 每个问题可定位
* 每个版本可比较
* 每次中断可恢复
* 每位参与者可接力
* 每个完成声明经过验证

现在从仓库审计、测试基线和最小可提交纵向切片开始。
