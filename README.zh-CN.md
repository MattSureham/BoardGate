# BoardGate

[English](README.md)

BoardGate 是一个 Evidence-first、确定性的 PCB 审查与 authoring Agent。
它安全导入制造与装配文件，执行可复现的 DFM 检查并输出结构化审查证据。
独立的 authoring 子系统现在还能执行一种严格受限的 PCB 文件修改，并把
新设计交给未经改写的现有审查管线重新验证。

项目遵守一条硬边界：文件解析、几何测量和规则判断必须由确定性代码完成。
Agent 只能组织和解释这些结果，不得编造几何数据、设计意图或投产保证。

## 当前状态

v0.1 审查基线已经完成。面向未来的审查、修改与生成契约由
[`PROJECT_SPEC.md`](PROJECT_SPEC.md) 定义；首个确定性修改纵向切片已实现，
结构化 PCB 生成仍处于规划阶段。已经验证的仓库状态和唯一下一步维护在
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

审查与修改接口：

```bash
pcb-review inspect INPUT... \
  --rules rules/default.yaml \
  --output artifacts/review

pcb-review modify INPUT... \
  --request change.json \
  --rules rules/default.yaml \
  --output artifacts/revision
```

## 使用 walkthrough

本 walkthrough 带你从全新检出走到完成一次审查并处理结果。所有命令都是
确定性的：相同输入与相同规则 Profile 必然产生完全相同的
`manifest.json`、`project.json`、`findings.json`、`report.md` 和
`preview.svg` 字节。

### 1. 安装

需要 Python 3.12+ 和 uv 0.11.x，然后：

```bash
uv sync --locked
uv run pcb-review --version
```

下面示例都以 `uv run` 前缀调用 CLI；如果你把包装进了自己的环境，直接
使用 `pcb-review` 效果相同。

### 2. 准备一个项目输入

`inspect` 每次调用只审查一个 PCB 项目。项目可以用三种等价形式提供：

- 一个包含制造/装配文件的目录；
- 一个不含嵌套压缩包的 ZIP 归档；
- 多个明确的文件路径。

典型的两层板项目需要 Gerber 铜层、板框（outline）和 Excellon 钻孔文件；
BOM 与贴片坐标（CSV/XLSX）可选，提供后会启用装配类规则。仓库自带两个
原创小项目可直接使用：

```text
tests/fixtures/valid_minimal_board/       # 干净板，预期零 Findings
tests/fixtures/copper_too_close_to_edge/  # 同一块板，含铜到板边违规
```

所有输入按不可信数据处理：符号链接、加密或嵌套压缩包、绝对/穿越路径、
超限载荷都会在解析器运行前被拒绝。文件类型由内容、X2 属性、文件名和
扩展名证据共同判定；证据不足的文件会被标记为 unknown，而不是猜测。

### 3. 运行第一次审查

```bash
uv run pcb-review inspect tests/fixtures/copper_too_close_to_edge \
  --rules rules/default.yaml \
  --output artifacts/demo
```

控制台输出：

```text
Review prj-6aa57e8aab4e330a: READY_FOR_REVIEW; artifacts written to artifacts/demo
```

项目 ID（`prj-...`）由输入内容推导，同一项目永远得到同一 ID。

`--output` 是可选的。输出目录按三层优先级解析（ADR 0004）：

1. 命令行 `--output` 参数（给出时优先）；
2. 否则读取单个目录输入中的 `boardgate.toml`，例如
   `[review]` `output = ".review-output"`（相对路径相对输入目录的
   父目录解析）；
3. 否则使用内置默认值：输入目录的兄弟目录 `<输入名>.review-output`
   （压缩包和文件取其主名）。

提供多个输入时必须显式给出 `--output`。无论哪一层，输出目录必须为空
或不存在（加 `--overwrite` 可原子替换上一次结果），且不得包含任一
输入路径、也不得被任一输入路径包含——违反此规则的配置值会以退出码
2 拒绝。

### 4. 产出物

每次完成（或安全失败）的审查都恰好发布六个 Artifact：

| Artifact | 内容 | 字节稳定性 |
| --- | --- | --- |
| `manifest.json` | 源文件清单：SHA-256、大小、分类证据 | 确定性 |
| `project.json` | 归一化项目模型：层、板框、钻孔、BOM/CPL | 确定性 |
| `findings.json` | 全部规则结果、Findings、风险模式、审查状态 | 确定性 |
| `report.md` | 面向工程师的 Markdown 报告 | 确定性 |
| `preview.svg` | 无脚本的板子预览，带 Finding 标记 | 确定性 |
| `logs/run.jsonl` | 脱敏的单次运行结构化事件 | 每次运行不同 |

所有 JSON Artifact 都通过 `schemas/v1/` 中签入的 Draft 2020-12 Schema
校验。发布前会对整个产物包做交叉校验（跨文件的 project/profile ID、
Finding 引用、SVG 安全性），并且发布是原子的：失败的运行不会留下写
了一半的或被部分替换的输出目录。

### 5. 阅读报告

`report.md` 是主要的人工接口，依次包含：执行摘要、证据置信度、输入
清单、项目解读（板尺寸、层、钻孔、装配范围）、按严重度分组的
Findings（blocker、高风险、warning）、需要人工确认的 Findings、优化
建议、已执行与未执行的规则（含原因）、解析/分析限制、证据索引，以及
非投产保证声明。

总体状态为以下之一：

| 状态 | 含义 |
| --- | --- |
| `READY_FOR_REVIEW` | 必需检查完成，无影响投产的 Findings |
| `READY_WITH_CONFIRMATIONS` | 可用，但部分 Findings 或部分覆盖需要人工决定 |
| `INSUFFICIENT_INFORMATION` | 项目无法解析的部分过多，无法判断 |
| `NOT_READY_FOR_FABRICATION` | 存在已确认的影响投产的 Findings |
| `ANALYSIS_FAILED` | 流水线本身失败，未产生规则结果 |

每个 Finding 都有稳定 ID，并携带证据：源文件 SHA、对象 ID、可用的
行/字节区间，以及几何测量值和对应阈值。同一 Finding ID 同时出现在
`report.md` 和 `preview.svg` 的 `data-finding-id` 属性中，可以直观地
定位每个问题。

注意：标记为"需要人工确认"的 Finding 并不是弱结果，而是 BoardGate
拒绝猜测的情形（层映射歧义、不支持的光圈几何、近似误差带）。报告
绝不会把它们悄悄升级为通过或失败。

### 6. 在 CI 中使用

退出码遵循固定优先级（`4 > 2 > 3 > 1 > 0`）：

| 退出码 | 含义 |
| --- | --- |
| 0 | 审查完成，未达到 `--fail-on` 阈值 |
| 1 | 审查完成且存在已确认的 blocker Finding（仅在 `--fail-on blocker` 时） |
| 2 | 用户/配置错误（输入、Profile、输出路径不安全），不发布任何产物 |
| 3 | 安全导入之后流水线失败，发布 `ANALYSIS_FAILED` 诊断产物包 |
| 4 | 未预期的内部错误 |

典型的 CI 门禁：

```bash
uv run pcb-review inspect fab/ --rules rules/default.yaml \
  --output artifacts/review --fail-on blocker
```

注意 `--fail-on blocker` 只改变退出码；完成的审查始终发布全部六个
Artifact。

### 7. 调整规则 Profile

复制 `rules/default.yaml` 再修改——板厂的真实工艺极限就写在这里：

```yaml
fabrication:
  min_trace_width: 0.10      # mm
  min_copper_spacing: 0.10
  min_copper_to_edge: 0.25
  min_drill_diameter: 0.20
  min_annular_ring: 0.10
  min_solder_mask_dam: 0.10
```

16 条规则中的每一条都可以启用/禁用，并可设置严重度（`blocker`、
`high`、`warning`、`info`）以及是否影响投产就绪。Profile 采用严格
校验：未知字段、YAML tag/别名、缺失阈值都会在读取任何文件之前以
退出码 2 拒绝。Profile 的 SHA-256 嵌入每个 Artifact，因此结果永远
可以追溯到产生它的确切配置。

### 8. 出错时怎么办

| 信息 | 原因 | 处理 |
| --- | --- | --- |
| `INPUT_NOT_FOUND` | 输入路径不存在 | 检查路径 |
| `PROFILE_VALIDATION_ERROR` | Profile 未通过严格校验 | 对照 `rules/default.yaml` 修改 |
| `PROJECT_CONFIG_ERROR` | `boardgate.toml` 未通过严格校验 | 修正或删除该配置文件 |
| `OUTPUT_REQUIRED` | 多个输入但未给 `--output` | 显式传入 `--output` |
| `OUTPUT_NOT_EMPTY` | 输出目录非空 | 换新目录或加 `--overwrite` |
| `OUTPUT_OVERLAPS_INPUT` | 输出包含输入或被输入包含 | 把输出移到项目之外 |
| `FILE_COUNT_LIMIT` / `UNSAFE_PATH` | 输入超出安全预算 | 精简/清理输入集 |
| 摘要中出现 `... (diagnostic fallback)` | 导入后某阶段失败（退出码 3） | 查看 `findings.json` 的 `analysis_diagnostics` 和 `logs/run.jsonl` |

需要更深入排查时，`--log-level debug` 可提高控制台详细程度；
`logs/run.jsonl` 记录了每个流水线阶段的时间戳、选用的解析器、
执行/跳过的规则和 Finding 数量。

v0.1 精确的输入子集与刻意保留的边界（不做网络表推断、不声明焊盘
对位、不对宏光圈做精确检查等）见
[`docs/CAPABILITIES.md`](docs/CAPABILITIES.md)。

## 受限 PCB 修改

修改是独立的确定性能力，不是规则引擎的副作用。首个 operation 会把一个
明确指定的 Excellon 圆孔刀具从预期旧直径改为新直径。它只接受已确认、
无 warning/limitation、metric/absolute，且使用固定宽度普通
`TnnC0.000` 定义的源文件；与 routed slot 共用的刀具或不支持的语法会
fail closed。

先运行 `inspect`，从已验证的 `manifest.json` 取得 base project/source ID
与 SHA-256。仓库原创 `drill_too_small` fixture 对应的 request 为：

```json
{
  "schema_version": "1.0",
  "base_project_id": "prj-843b23c76e645c40",
  "operation": {
    "schema_version": "1.0",
    "kind": "set_excellon_tool_diameter",
    "operation_version": "1.0",
    "source_logical_path": "board-plated.drl",
    "source_file_id": "src-2e142b0470b42176",
    "source_sha256": "b0071583553477b42cad5a632756df8114e6e191d77ceef23568e6afceeaf76d",
    "tool_code": "T01",
    "expected_diameter_mm": 0.1,
    "new_diameter_mm": 0.3,
    "instruction": "Increase the explicitly selected T01 round-drill diameter."
  }
}
```

将其保存为项目输入目录之外的 `change.json`，然后运行：

```bash
uv run pcb-review modify tests/fixtures/drill_too_small \
  --request change.json \
  --rules rules/default.yaml \
  --output artifacts/drill-revision
```

原子 revision workspace 在 `design/` 保存输出设计字节，在 `evidence/`
保存 canonical request/result Evidence，并在 `validation/` 保存一次独立的
完整六产物审查。输入永不被修改。过期或非法 request 以退出码 2 拒绝且不
发布；不支持的解析/输出或失败的验证以退出码 3 拒绝且不发布。若审查完成
但仍有 blocker，则如实发布 revision 并返回 1，绝不会称其已修复或获准投产。

## 离线审查 Viewer

独立分发的
[`viewer/boardgate-viewer.html`](viewer/boardgate-viewer.html) 可以在当前
Chromium、Firefox 和 WebKit 浏览器中直接以 `file://` 打开。它不是第七个
审查 Artifact。把 Viewer 放在任意位置并打开，通过浏览器的目录选择器选择
一个已完成的审查输出目录，然后等待页面显示 **Bundle validation complete**。

Viewer 只接受包含以下大小写敏感路径的、恰好六个 Artifact 的 Bundle：

```text
manifest.json
project.json
findings.json
report.md
preview.svg
logs/run.jsonl
```

准入过程完全离线、只读、受资源上限约束，并且失败关闭。Viewer 会先检查
文件清单、规范 JSON 与 Schema、语义和跨 Artifact 身份、报告元数据、
namespace 正确的被动 SVG vocabulary 及运行日志，之后才显示任何工程结论。
缺失、额外、格式错误、相互不一致或包含主动内容的 Artifact 都只会让界面
进入中性的 **Review unavailable** 状态。所选 `File` 对象只作为当前页面
内存中的快照存在；Viewer 不上传、不发起网络请求、不写入存储、不触发审查，
也不修改 Bundle。

准入成功后，Viewer 会显示通过验证的项目/Profile 身份、原始总体状态、
证据计数、风险模式，以及 `ANALYSIS_FAILED` 的安全诊断。它会把通过验证的
`preview.svg` 导入一个仅用于展示的 DOM 副本，提供逐图层可见性开关和
Finding 列表，点击 Finding 可聚焦对应的空间或图例标记。最后，它会通过
一个面向行的轻量分词器渲染 `report.md`，该分词器只支持 BoardGate
确定性报告的子集（标题、段落、嵌套列表和 `**加粗**` 状态/Finding 行），
并完全使用 createElement/textContent 构建——不使用 Markdown 库，不使用
innerHTML，也不显示 HTML 注释元数据。报告中的 Finding-ID 标题可以激活：
从报告或预览 Finding 列表中选择 Finding 都会聚焦同一个预览标记，并保持
两处按钮的按下状态同步。这些交互只改变该展示副本上可信的 CSS 可见性和
类名状态：定义几何的属性和所选 Bundle 字节保持不变，也不会重新执行或
解释任何审查规则。

开发者需要 Node.js 22.12 或更高版本（且低于 25）来重建并测试已签入的
单文件 Viewer：

```bash
cd viewer
npm ci
npm run check
npm run typecheck
npm run test:coverage
npm run build:check
```

## 安全与范围

所有输入文件都按不可信数据处理。BoardGate Evidence 不是板厂投产保证。
当前 authoring 切片不是任意或无损的 Gerber/Excellon 编辑；从结构化需求
生成 PCB 也尚未实现。原生 EDA authoring、ODB++、IPC-2581、SI/PI、
autorouting、Web API、自动投产发布和需要联网的 LLM Provider 仍不在范围内。
精确支持范围与限制见
[`docs/CAPABILITIES.md`](docs/CAPABILITIES.md)。

## 协作

任何参与者修改仓库前都必须阅读并遵守 [`HANDOFF.md`](HANDOFF.md)。它是
权威协作状态；仓库 Evidence 的优先级高于聊天记录或摘要。

## 许可证

Apache License 2.0，详见 [`LICENSE`](LICENSE)。
