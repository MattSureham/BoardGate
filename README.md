# BoardGate

[中文说明](README.zh-CN.md)

BoardGate is an evidence-first, deterministic PCB review and authoring agent.
It ingests fabrication and assembly files, runs reproducible DFM checks, and
produces structured review evidence. Its separate authoring subsystems can
apply one narrowly supported PCB-file modification and generate bounded
two-layer coupon designs from structured requirements, each validated through
a fresh run of the unchanged review pipeline.

The project follows one hard boundary: parsers, measurements, and rule
decisions are deterministic. Agent orchestration may organize and explain
those results, but it must not invent geometry, manufacturing intent, or a
production-readiness guarantee.

## Status

The v0.1 review baseline is complete. The forward-looking review,
modification, and generation contract is [`PROJECT_SPEC.md`](PROJECT_SPEC.md);
the initial deterministic modification slice and two exact registered coupon
generation operations are implemented. Verified repository state
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

The review, modification, and generation interfaces are:

```bash
pcb-review inspect INPUT... \
  --rules rules/default.yaml \
  --output artifacts/review

pcb-review modify INPUT... \
  --request change.json \
  [--plan plan.json] \
  --rules rules/default.yaml \
  --output artifacts/revision

pcb-review generate \
  --request coupon.json \
  [--plan plan.json] \
  --rules rules/default.yaml \
  --output artifacts/generation
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

## Constrained PCB modification

Modification is a separate deterministic capability, not a rule-engine side
effect. Two operations are registered: `set_excellon_tool_diameter/1.0` changes
one explicitly identified Excellon round drill tool from an expected diameter
to a new diameter, and `set_gerber_standard_aperture_diameter/1.0` changes one
explicitly identified Gerber standard round aperture the same way. Each accepts
only a confirmed, warning-free, metric/absolute source with a plain fixed-width
definition (`TnnC0.000` or `%ADDnnC,0.000*%`); tools shared with routed slots,
holed or non-circle apertures, and unsupported syntax fail closed.

First run `inspect` and take the base project/source IDs and SHA-256 from its
validated `manifest.json`. For the original `drill_too_small` fixture, a
request is:

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

Save it as `change.json`, outside the project input directory, then run:

```bash
uv run pcb-review modify tests/fixtures/drill_too_small \
  --request change.json \
  --rules rules/default.yaml \
  --output artifacts/drill-revision
```

The atomic revision workspace contains emitted design bytes under `design/`,
canonical request/result evidence under `evidence/`, and an independent exact
six-artifact review under `validation/`. The input is never changed. Stale or
invalid requests exit 2 without publication; unsupported parsing/emission or
failed validation exits 3 without publication. A completed review that still
has blockers is published truthfully and exits 1—it is never described as a
repair or fabrication approval.

## Deterministic PCB generation

Generation is the third separate deterministic capability: structured
requirements in, one bounded design out, then a fresh independent review. The
first registered operation, `generate_two_layer_coupon/1.0`, emits a metric
rectangular two-layer coupon with explicit
plated round holes (each with its explicit copper pad) and explicit straight
round-aperture traces. There is no free-form writer path: the requirements
are validated against inclusive bounds (1.0–500.0 mm boards, at most 1,024
holes and 4,096 traces, all values exact multiples of 0.000001 mm), and the
executor reparses every emitted file and proves it matches the request before
the unchanged review pipeline runs.

A request is one strict JSON document, for example:

```json
{
  "schema_version": "1.0",
  "operation": {
    "schema_version": "1.0",
    "kind": "generate_two_layer_coupon",
    "operation_version": "1.0",
    "board_width_mm": 20.0,
    "board_height_mm": 15.0,
    "holes": [
      {
        "schema_version": "1.0",
        "x_mm": 5.0,
        "y_mm": 5.0,
        "drill_diameter_mm": 0.3,
        "pad_diameter_mm": 0.8
      }
    ],
    "traces": [
      {
        "schema_version": "1.0",
        "x1_mm": 1.0,
        "y1_mm": 1.0,
        "x2_mm": 19.0,
        "y2_mm": 1.0,
        "width_mm": 0.25,
        "copper_layers": "both"
      }
    ],
    "instruction": "Generate a two-layer coupon with one plated hole."
  }
}
```

Save it as `coupon.json`, then run:

```bash
uv run pcb-review generate \
  --request coupon.json \
  --rules rules/default.yaml \
  --output artifacts/coupon-generation
```

The published workspace has the same layout and publication rules as a
modification revision: `design/` holds the emitted X2 top/bottom copper,
rectangular outline, and plated Excellon drill payloads; `evidence/` holds
the canonical request and result (including the content-derived
`gen-...` generation ID and the pinned disclaimer that generation does not
guarantee manufacturability); `validation/` holds the independent
six-artifact review. Invalid requirements exit 2 without publication;
emission, reparse, or validation failures exit 3 without publication; a
completed review with blockers is published truthfully and exits 1.

The second exact operation,
`generate_two_layer_coupon_with_npth/1.0`, adds a separately emitted NPTH drill
file without changing or weakening the first contract. It requires at least
one entry in each of `plated_holes` and `non_plated_holes`; plated entries have
`x_mm`, `y_mm`, `drill_diameter_mm`, and `pad_diameter_mm`, while NPTH entries
have no pad field and never create an implicit copper pad. The two lists may
contain at most 1,024 holes in total, and the request may contain at most 4,096
traces. Its `design/` inventory has five files: X2 top and bottom copper, the
rectangular outline, a plated drill file, and `coupon-non-plated.drl`. The two
drill payloads carry explicit `PLATED` and `NON_PLATED` semantics and are
reparsed independently before the unchanged `ReviewService` validates the
entire generated design.

The generator proves bounded emission, board containment, drill non-overlap,
and exact requested semantics. Manufacturing clearances are not inferred or
guaranteed by generation: the explicitly selected review profile evaluates
them and may truthfully publish blockers. Slots, vias, non-round holes,
arbitrary routing, and general-purpose EDA authoring remain outside both
coupon operations.

## Typed authoring plans

An agent or tool may bind either authoring capability to an `AuthoringPlan`
1.0 JSON document (checked-in Draft 2020-12 schema, inclusive 1 MiB cap). A
plan names exactly one registered operation kind/version, carries the
canonical request and structured-operation digests, and requires a separate
authorization digest derived from the approver, a pinned non-guarantee
statement, and the request digest. Deterministic admission recomputes every
digest without performing I/O: instruction or rationale prose cannot change
any admitted identity, unknown kind/version pairs are rejected without
fallback, and an admitted plan executes only through the unchanged services
above with their fresh independent review.

Both authoring commands accept an optional `--plan plan.json` alongside
`--request`: the CLI loads and admits the plan against the exact request and
drives only the registered service when every digest matches. A tampered,
rebound, or kind-mismatched plan fails with exit 2 and publishes nothing;
without `--plan`, behavior is unchanged.

Mint a plan for an exact request with explicit approval:

```bash
uv run pcb-review plan \
  --request coupon.json \
  --kind generation \
  --approver engineer@example.com \
  --output plan.json
```

The command only loads the admitted request and writes byte-deterministic
canonical plan JSON (add `--rationale` for bounded optional prose and
`--overwrite` to replace an existing file). It stages no design inputs,
executes no operation, and runs no review; a minted plan passed through
`--plan` runs the identical pipeline as the plan-less invocation.

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

All input files are treated as untrusted. BoardGate evidence is not a
fabrication warranty. The implemented authoring slices are not arbitrary or
lossless Gerber/Excellon editing, and the implemented generators emit only
the bounded two-layer coupon contracts—none guarantees manufacturability.
Native EDA authoring, ODB++, IPC-2581, SI/PI,
autorouting, a web API, autonomous production release, and network-backed LLM
providers remain out of scope. The exact supported subsets and limits are in
[`docs/CAPABILITIES.md`](docs/CAPABILITIES.md).

## Collaboration

Every participant must read and follow [`HANDOFF.md`](HANDOFF.md) before
changing the repository. It is the canonical collaboration state; repository
evidence takes precedence over chat history or summaries.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
