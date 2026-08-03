# BoardGate

[中文说明](README.zh-CN.md)

BoardGate is an evidence-first, deterministic PCB manufacturing review agent.
It is designed to ingest fabrication and assembly files, normalize them into a
versioned project model, run reproducible DFM checks, and produce structured
findings, a Markdown report, and an SVG preview.

The project follows one hard boundary: parsers, measurements, and rule
decisions are deterministic. Agent orchestration may organize and explain
those results, but it must not invent geometry, manufacturing intent, or a
production-readiness guarantee.

## Status

BoardGate is under active development toward the v0.1 CLI MVP described in
[`IMPLEMENT_PCB_AGENT.md`](IMPLEMENT_PCB_AGENT.md). Verified repository state
and the exact next action are maintained in [`HANDOFF.md`](HANDOFF.md).

## Development

Prerequisites:

- Python 3.12 or newer
- uv 0.11.x

```bash
uv sync --locked
uv run pcb-review --version
uv run pytest
```

The target review interface is:

```bash
pcb-review inspect INPUT... \
  --rules rules/default.yaml \
  --output artifacts/review
```

## User walkthrough

This walkthrough takes you from a clean checkout to acting on a completed
review. Every command is deterministic: the same inputs and rule profile
always produce the same `manifest.json`, `project.json`, `findings.json`,
`report.md`, and `preview.svg` bytes.

### 1. Install

You need Python 3.12+ and uv 0.11.x. Then:

```bash
uv sync --locked
uv run pcb-review --version
```

All examples below prefix the CLI with `uv run`. If you installed the package
into your own environment, plain `pcb-review` works the same way.

### 2. Prepare one project input

`inspect` reviews exactly one PCB project per invocation. The project can be
supplied in three equivalent forms:

- a directory containing the fabrication/assembly files,
- a single non-nested ZIP archive of those files, or
- several explicit file paths.

A typical two-layer project needs Gerber copper layers, a board outline, and
an Excellon drill file; BOM and placement CSV/XLSX files are optional and
enable the assembly rules. The repository ships two small original projects
you can use immediately:

```text
tests/fixtures/valid_minimal_board/       # clean board, expected zero findings
tests/fixtures/copper_too_close_to_edge/  # same board with an edge violation
```

Inputs are treated as untrusted: symlinks, encrypted or nested archives,
absolute/traversal paths, and oversized payloads are rejected before any
parser runs. Files are classified by content, X2 attributes, filename, and
extension evidence together; ambiguous files are reported as unknown instead
of being guessed.

### 3. Run your first review

```bash
uv run pcb-review inspect tests/fixtures/copper_too_close_to_edge \
  --rules rules/default.yaml \
  --output artifacts/demo
```

Console output:

```text
Review prj-6aa57e8aab4e330a: READY_FOR_REVIEW; artifacts written to artifacts/demo
```

The project ID (`prj-...`) is derived from the input content, so the same
project always receives the same ID.

`--output` is optional. The output directory is resolved in three tiers
(ADR 0004):

1. the `--output` CLI option, when given;
2. otherwise `boardgate.toml` in a single directory input, e.g.
   `[review]` `output = ".review-output"` (relative paths resolve against
   the input directory's parent);
3. otherwise the built-in default: a sibling `<INPUT>.review-output`
   directory (archives and files use their stem).

When several inputs are supplied, `--output` is required. In every tier the
output must be empty or absent (add `--overwrite` to atomically replace a
previous review), and it may never contain, or be contained by, any input
path — a config value that violates this is rejected with exit code 2.

### 4. What gets written

Every completed or failed-safe review publishes exactly six artifacts:

| Artifact | Content | Bytes |
| --- | --- | --- |
| `manifest.json` | Source inventory: SHA-256, sizes, classification evidence | Deterministic |
| `project.json` | Normalized project model: layers, outline, drills, BOM/CPL | Deterministic |
| `findings.json` | All rule results, findings, risk modes, review status | Deterministic |
| `report.md` | Engineer-facing Markdown report | Deterministic |
| `preview.svg` | Script-free board preview with finding markers | Deterministic |
| `logs/run.jsonl` | Sanitized per-run structured events | Varies per run |

All JSON artifacts validate against the checked-in Draft 2020-12 schemas in
`schemas/v1/`. Before anything is published, the bundle is validated as a
whole (cross-artifact project/profile IDs, finding references, safe SVG), and
publication is atomic: a failed run never leaves a half-written or
partially replaced output directory.

### 5. Read the report

`report.md` is the primary human interface. It contains, in order: an
executive summary, an evidence-confidence section, the input inventory, the
project interpretation (board size, layers, drills, assembly scope), findings
grouped by severity (blockers, high-risk, warnings), findings that require
human confirmation, optimization suggestions, rules executed and not executed
(with reasons), parser/analysis limitations, an evidence index, and the
non-guarantee disclaimer.

The overall status is one of:

| Status | Meaning |
| --- | --- |
| `READY_FOR_REVIEW` | Required checks completed with no readiness-affecting findings |
| `READY_WITH_CONFIRMATIONS` | Usable, but some findings or partial coverage need a human decision |
| `INSUFFICIENT_INFORMATION` | Too much of the project was unresolved to judge |
| `NOT_READY_FOR_FABRICATION` | Confirmed readiness-affecting findings exist |
| `ANALYSIS_FAILED` | The pipeline itself failed; rule results were not produced |

Every finding has a stable ID and carries its evidence: source file SHA,
object ID, line/byte span when available, and the geometric measurement with
its configured threshold. The same finding ID appears in `report.md` and as
`data-finding-id` in `preview.svg`, so you can locate each issue visually.

Important: findings marked "requires human confirmation" are not weak
results — they are cases where BoardGate refuses to guess (ambiguous layer
mapping, unsupported aperture geometry, approximation error bands). The
report never silently upgrades them to pass or fail.

### 6. Use it in CI

Exit codes follow a fixed precedence (`4 > 2 > 3 > 1 > 0`):

| Code | Meaning |
| --- | --- |
| 0 | Review completed; no `--fail-on` threshold reached |
| 1 | Review completed and a confirmed blocker finding exists (only with `--fail-on blocker`) |
| 2 | User/config error (bad input, bad profile, unsafe output path) — nothing published |
| 3 | Pipeline failure after safe ingestion — an `ANALYSIS_FAILED` diagnostic bundle was published |
| 4 | Unexpected internal error |

A typical CI gate:

```bash
uv run pcb-review inspect fab/ --rules rules/default.yaml \
  --output artifacts/review --fail-on blocker
```

Note that `--fail-on blocker` only changes the exit code; all six artifacts
are always published for completed reviews.

### 7. Tune the rule profile

Copy `rules/default.yaml` and edit it — the profile is where your
fabricator's real limits live:

```yaml
fabrication:
  min_trace_width: 0.10      # mm
  min_copper_spacing: 0.10
  min_copper_to_edge: 0.25
  min_drill_diameter: 0.20
  min_annular_ring: 0.10
  min_solder_mask_dam: 0.10
```

Each of the 16 rules can be enabled/disabled and assigned a severity
(`blocker`, `high`, `warning`, `info`) plus whether it affects readiness.
Profiles are validated strictly: unknown fields, YAML tags/aliases, and
missing thresholds are rejected with exit code 2 before any file is read.
The profile's SHA-256 is embedded in every artifact, so results are always
traceable to the exact configuration that produced them.

### 8. If something goes wrong

| Message | Cause | Fix |
| --- | --- | --- |
| `INPUT_NOT_FOUND` | An input path does not exist | Check the path |
| `PROFILE_VALIDATION_ERROR` | Profile failed strict validation | Compare against `rules/default.yaml` |
| `PROJECT_CONFIG_ERROR` | `boardgate.toml` failed strict validation | Fix or remove the config file |
| `OUTPUT_REQUIRED` | Several inputs but no `--output` | Pass `--output` explicitly |
| `OUTPUT_NOT_EMPTY` | Output directory has content | Choose a new directory or pass `--overwrite` |
| `OUTPUT_OVERLAPS_INPUT` | Output contains or is inside an input | Move the output outside the project |
| `FILE_COUNT_LIMIT` / `UNSAFE_PATH` | Input exceeded security budgets | Reduce/sanitize the input set |
| `... (diagnostic fallback)` in the summary | A post-ingestion stage failed (exit 3) | Read `findings.json` `analysis_diagnostics` and `logs/run.jsonl` |

For deeper inspection, `--log-level debug` increases console verbosity, and
`logs/run.jsonl` records each pipeline stage with timestamps, selected
parsers, executed/skipped rules, and finding counts.

For the exact supported input subsets and deliberate v0.1 boundaries (no
netlist inference, no pad-registration claims, no macro-aperture exact
checks, and so on), see [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md).

## Offline review viewer

The separately distributed
[`viewer/boardgate-viewer.html`](viewer/boardgate-viewer.html) opens directly
from `file://` in current Chromium, Firefox, and WebKit browsers. It is not a
seventh review artifact. Keep the viewer wherever you choose, open it, select
one completed review output directory with the browser's directory chooser,
and wait for **Bundle validation complete**.

The viewer admits only an exact six-artifact bundle with these case-sensitive
paths:

```text
manifest.json
project.json
findings.json
report.md
preview.svg
logs/run.jsonl
```

Admission is offline, read-only, resource-bounded, and fail closed. The viewer
checks the inventory, canonical JSON and schemas, semantic and cross-artifact
identities, report metadata, a namespace-correct passive SVG vocabulary, and
the run log before it shows any project conclusion. A missing, extra,
malformed, inconsistent, or active-content artifact leaves the UI in a
neutral **Review unavailable** state. The selected `File` objects live only
as an in-memory snapshot for the current page: the viewer performs no upload,
network request, storage write, review invocation, or bundle modification.

After admission, the viewer displays the validated project/profile identity,
the original overall status, evidence counts, risk modes, and safe diagnostics
for `ANALYSIS_FAILED`. It imports the validated `preview.svg` into a
presentation-only DOM copy, with per-layer visibility checkboxes and a Finding
list that focuses the matching spatial or legend marker. Finally, it renders
`report.md` through a small line-oriented tokenizer limited to the
deterministic BoardGate report subset (headings, paragraphs, nested lists, and
`**bold**` status/Finding lines), built exclusively with
createElement/textContent — no Markdown library, no innerHTML, and HTML
comment metadata is not displayed. Finding-ID headings in the report are
activatable: selecting a Finding from the report or from the preview Finding
list focuses the same preview marker and keeps both buttons' pressed state in
sync. These interactions change only trusted CSS visibility and class state
on that presentation copy: geometry-defining attributes and the selected
bundle bytes remain unchanged, and no review rule is re-run or reinterpreted.

Developers need Node.js 22.12 or newer (but earlier than 25) to rebuild and
test the tracked standalone file:

```bash
cd viewer
npm ci
npm run check
npm run typecheck
npm run test:coverage
npm run build:check
```

## Safety and scope

All input files are treated as untrusted. A BoardGate report is engineering
review evidence, not a fabrication warranty. The initial MVP intentionally
excludes native EDA projects, ODB++, IPC-2581, SI/PI analysis, automatic PCB
modification, a web API, and network-backed LLM providers.
The exact supported subsets and known v0.1 limits are listed in
[`docs/CAPABILITIES.md`](docs/CAPABILITIES.md).

## Collaboration

Every participant must read and follow [`HANDOFF.md`](HANDOFF.md) before
changing the repository. It is the canonical collaboration state; repository
evidence takes precedence over chat history or summaries.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
