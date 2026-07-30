# HANDOFF

> **Collaboration Protocol (normative)**
>
> - Read this file before starting any work.
> - Update only your own structured state and activity records.
> - Preserve prior evidence, authorship, and participant records.
> - Never silently rewrite or delete another participant's findings.
> - Record disagreement as new evidence instead of overwriting history.
> - Label claims as `[CONFIRMED]`, `[INFERRED]`, or `[UNKNOWN]`.
> - Repository evidence takes precedence over assumptions and summaries.
> - Leave exactly one bounded, immediately actionable Next Action.
> - Keep the history understandable without access to prior conversations.
> - Protocol changes require a recorded proposal, motivation, compatibility
>   analysis, and explicit approval before adoption.

## Current State

- Last updated: `2026-07-30T15:50:00+08:00`
- Repository: `[CONFIRMED] https://github.com/MattSureham/BoardGate`
- Visibility: `[CONFIRMED] PUBLIC`
- Branch: `[CONFIRMED] main`
- HEAD: `[CONFIRMED] The branch-tip documentation commit containing this
  state follows code/CI parent a677e5b docs(handoff): record bounded
  geometry recovery.`
- Remote sync: `[CONFIRMED] local main, origin/main, and origin/HEAD point to
  the same public-main branch tip after a normal, non-force push.`
- Phase: `[CONFIRMED] Phase 9 end-to-end review pipeline and Phase 10
  deterministic agent orchestration are complete; Phase 11 (optional API or
  minimal web viewer) is the only remaining spec phase.`
- Entry point: `[CONFIRMED] uv run pcb-review inspect INPUT... --rules
  rules/default.yaml --output OUTPUT`
- Implemented capabilities:
  - `[CONFIRMED] Installable Python package and versioned CLI entry point.`
  - `[CONFIRMED] Locked Python 3.12 development environment; Ubuntu CI
    asserts and tests the actual Python 3.12 and 3.14 interpreters, while
    Ubuntu, macOS, and Windows run a complete Python 3.12 CLI review smoke.`
  - `[CONFIRMED] Repository collaboration protocol and architecture boundary.`
  - `[CONFIRMED] Strict, versioned Unit, Point, BoundingBox,
    CoordinateSystem, SourceSpan, and Provenance models.`
  - `[CONFIRMED] Canonical JSON serialization with six-decimal persisted
    coordinates.`
  - `[CONFIRMED] Parser-independent source manifest, layer primitive, drill,
    component, board-outline, PCBProject, Finding, and risk-mode models.`
  - `[CONFIRMED] Stable source, project, object, and finding identifier
    helpers.`
  - `[CONFIRMED] Strict Rule Profile 1.0 covering all 16 rule settings,
    required layers, fabrication thresholds, tolerances, and review policy.`
  - `[CONFIRMED] Restricted YAML/JSON loader and five checked-in Draft
    2020-12 public JSON Schemas.`
  - `[CONFIRMED] Private, lifecycle-bounded staging for directories, ZIP
    archives, and explicit regular files.`
  - `[CONFIRMED] ZIP preflight, streaming expansion, shared security budgets,
    and cross-platform logical-path collision detection.`
  - `[CONFIRMED] SHA-256 inventory, conservative content/name/extension
    classification, explicit conflicts, and byte-stable manifest generation.`
  - `[CONFIRMED] Public inspect CLI contract and validated, recoverable
    manifest output transaction.`
  - `[CONFIRMED] Gerbonara-backed Excellon adapter for metric/inch hits,
    linear/arc slots, plating hints, units, formats, and diagnostics.`
  - `[CONFIRMED] Lightweight source-command scanner provides line/byte spans
    and raw-coordinate provenance without duplicating geometry parsing.`
  - `[CONFIRMED] Gerbonara-backed Gerber adapter retains analytic Line, Arc,
    Flash, and Region segments, standard/macro apertures, polarity, X2
    attributes, and diagnostics.`
  - `[CONFIRMED] Evidence-preserving X2/filename/extension layer mapping with
    explicit conflict uncertainty and SameCoordinates evidence.`
  - `[CONFIRMED] Analytic outline graph reconstruction with bounded endpoint
    snapping, arc chord error, nested cutout topology, and explicit ambiguity.`
  - `[CONFIRMED] Deterministic, bounded UTF-8 CSV parsing for normalized BOM
    and placement records with typed column, unit, numeric, and DNP errors.`
  - `[CONFIRMED] BOM and placement records retain source row/byte spans,
    unmapped metadata, raw coordinates, and stable object provenance.`
  - `[CONFIRMED] Placement DNP/Fitted/Populate columns normalize to an
    explicit placement DNP flag with typed invalid-value diagnostics.`
  - `[CONFIRMED] XLSX BOM preflight rejects active content and unsafe ZIP/XML
    structure before read-only calamine parsing.`
  - `[CONFIRMED] XLSX worksheet selection is explicit when ambiguous, and
    normalized BOM provenance records exact worksheet, row, and column map
    while keeping unavailable text spans null.`
  - `[CONFIRMED] Each confirmed source type runs in a fresh spawn-isolated
    parser process with a 30-second default timeout and bounded cleanup.`
  - `[CONFIRMED] Parser failures, warnings, and limitations become stable
    source diagnostics and explicit project uncertainty without discarding
    successful sibling sources.`
  - `[CONFIRMED] Deterministic project assembly produces normalized layers,
    outline topology, drills, BOM/CPL records, profile requirements, and
    strict PCBProject JSON with no third-party objects.`
  - `[CONFIRMED] Orthogonal RuleResult outcome/coverage contracts, complete
    v1 registry validation, deterministic dependency ordering, per-rule
    exception containment, threshold error-band semantics, and overall status
    precedence are implemented.`
  - `[CONFIRMED] A single review-scoped DerivedGeometryWorkspace shares
    primitive derivation, spatial indexes, polarity composition, components,
    board material, and contributor queries across rules while keeping all
    Shapely objects inside the workspace.`
  - `[CONFIRMED] Geometry resource policy 1.0 persists inclusive primitive,
    coordinate, spatial-candidate, connected-subset, union-batch, and
    component-pair limits; its fixed named spatial allocations sum exactly to
    the per-layer cap without first-come or per-query budget resets.`
  - `[CONFIRMED] Resource exclusions produce structured RuleCoverageGap
    evidence, COMPUTATION_LIMIT reasons, conservative mixed/all-limited
    coverage semantics, and ANALYSIS_LIMITATION risk aggregation without
    fabricating hardware violations.`
  - `[CONFIRMED] Strict findings.json root model aggregates ordered
    RuleResults, unique Findings, risk modes, profile identity, review status,
    analysis diagnostics, and the non-guarantee disclaimer.`
  - `[CONFIRMED] Phase 9 now has an accepted six-artifact/failure contract,
    canonical deterministic JSON, sanitized run diagnostics, structured JSONL
    logs, and cross-artifact validation including safe SVG and Finding IDs.`
  - `[CONFIRMED] The deterministic Markdown composer projects structured
    project/review evidence into the normative report sections with safe
    partial-coverage wording and escaped untrusted text.`
  - `[CONFIRMED] The deterministic standalone SVG renderer projects analytic
    layers, board topology, drills, and spatial/non-spatial Finding markers
    without scripts or external resources.`
  - `[CONFIRMED] Original minimal valid-board and copper-edge fixtures exercise
    the real Gerber/Excellon adapters, project builder, and all required rules
    without third-party sample licensing.`
  - `[CONFIRMED] Deterministic orchestrator creates a profile-bound ReviewPlan,
    RuleEngine records unselected enabled rules as
    SKIPPED/ORCHESTRATOR_FILTERED, and the presentation view carries only
    stable Finding IDs (ADR 0003).`
  - `[CONFIRMED] Typed NarrativeProvider protocol with index-only fact
    selection and exact deterministic-Markdown fallback; v0.1 provider is
    local and offline.`
  - `[CONFIRMED] ReviewService connects ingestion, planning, project
    construction, all 16 rules, report composition, SVG rendering, bundle
    validation, and atomic publication of exactly the six contracted
    artifacts, with schema-valid ANALYSIS_FAILED fallback and CLI exit
    precedence 4 > 2 > 3 > 1 > 0 including --fail-on blocker.`
  - `[CONFIRMED] Production built-in rule evaluation runs in a fresh spawn
    worker using bounded private canonical-JSON exchange; the parent enforces
    the remaining review deadline, validates the response, terminates/kills
    unresponsive workers, cleans temporary state, and discards partial
    hardware conclusions on timeout or crash.`
  - `[CONFIRMED] Structured sanitized logs/run.jsonl events with a sixth
    public Draft 2020-12 run-log-event schema; the first five artifacts are
    byte-deterministic across runs.`
  - `[CONFIRMED] Ingestion enforces directory-walk and ZIP file-count limits
    and rejects Windows reserved device-name path components.`
  - `[CONFIRMED] Eleven original failure-mode fixture projects, fabrication
    and assembly fixture-matrix integration tests, and Hypothesis property
    tests for geometry, units, paths, and spatial indexing.`
  - `[CONFIRMED] docs/CAPABILITIES.md records the v0.1 supported subsets and
    deliberate boundaries; jsonschema is now a runtime dependency.`
  - `[CONFIRMED] ADR 0004 output separation and three-tier output resolution:
    --output CLI option, then boardgate.toml [review].output for a single
    directory input, then the built-in sibling <INPUT>.review-output default;
    --output is now optional and multi-input runs without it exit 2.`
- Supported inputs: `[CONFIRMED] Directories, ZIP archives, and one or more
  regular files; Gerber, Excellon, BOM/placement CSV, BOM XLSX, rule profiles,
  and unknown files receive evidence-backed manifest classifications.
  Excellon round hits/routed slots and Gerber analytic primitives are
  normalized to millimetres.`
- Implemented rules: `[CONFIRMED] required_layers_present and
  drill_file_present, board_outline_present, board_outline_closed, and
  multiple_outline_regions, gerber_drill_coordinate_alignment, and
  minimum_trace_width, minimum_copper_spacing, minimum_copper_to_edge, and
  minimum_drill_diameter, minimum_annular_ring, and
  silkscreen_over_exposed_pad, minimum_solder_mask_dam, and
  bom_placement_reference_match, duplicate_reference_designator, and
  placement_outside_board_outline v1 (16/16 registered rules).`
- Verification:
  - `[CONFIRMED] gh repo view reported PUBLIC visibility.`
  - `[CONFIRMED] uv lock --check resolved 50 packages.`
  - `[CONFIRMED] uv run ruff format --check . passed (156 files).`
  - `[CONFIRMED] uv run ruff check . passed.`
  - `[CONFIRMED] uv run mypy src tests passed (142 source files).`
  - `[CONFIRMED] uv run pytest --cov=boardgate --cov-branch
    --cov-fail-under=85 passed: 559 tests, 89.69% branch coverage.`
  - `[CONFIRMED] UV_PYTHON=3.14 uv run --isolated --python 3.14 pytest -q
    passed all 559 tests under local CPython 3.14.4.`
  - `[CONFIRMED] The 126,054-primitive private reproduction completed twice
    after the final fixes in 109.01 s and 109.25 s; each run produced exactly
    six valid artifacts, did not report ANALYSIS_FAILED, left no worker/temp
    residue, and had byte-identical manifest.json, project.json,
    findings.json, report.md, and preview.svg. The private input and outputs
    were not added to the repository.`
  - `[CONFIRMED] GitHub Actions run 30511949778 succeeded for quality,
    Python 3.12 and 3.14 tests, and full Ubuntu/macOS/Windows CLI review
    smokes. Its 3.14 log records CPython 3.14.6 and pytest on Python 3.14.6.`
  - `[CONFIRMED] Independent Claude verification on 2026-07-30 re-ran every
    Codex-reported gate at a677e5b: 559 tests passed at 89.69% branch
    coverage, Ruff format/check and mypy (142 files) passed, checked-in
    schemas are current, and the working tree was clean. A fresh
    default-profile inspect of the renamed private reproduction completed
    in 105.9 s wall time, published six artifacts with policy 1.0 and zero
    coverage gaps, and reported NOT_READY_FOR_FABRICATION solely from the
    missing drill/outline/required-layer blockers in that input.`
  - `[CONFIRMED] Each recovery commit was gate-verified on its own staged
    tree: b0ff240 (444 tests, 90.40%), 9d1de3d (471 tests, 90.57%), ccfb1a0
    (495 tests, 90.63%); checked-in schemas regenerated current.`
- Known limitations:
  - `[CONFIRMED] The v0.1 supported subsets and deliberate boundaries are
    documented in docs/CAPABILITIES.md; no API or web viewer exists
    (Phase 11).`
- Working tree: `[CONFIRMED] Clean at a677e5b before this documentation-only
  HANDOFF update.`

Current State is the evidence-backed present snapshot. Recent Activity explains
how the repository reached that state and must not be required to understand
the current capabilities.

## Active Issues

### ISSUE-001 — Gerbonara provenance granularity

- Status: RESOLVED
- Severity: medium
- Owner: unassigned
- State label: `[CONFIRMED]`
- Context: Gerbonara graphical objects do not retain source line/byte spans.
- Evidence: Local 1.6.3 API probe and Excellon golden fixtures.
- Suspected cause: Parser output intentionally represents geometry, not syntax
  locations.
- Attempted approaches: Inspected object fields and parser warning behavior.
- Current resolution state: A lightweight command scanner aligns
  object-producing commands by order and retains raw command, coordinates,
  tool, line, and byte span. Count mismatch is an explicit limitation and
  leaves unmatched spans `null`.
- Remaining work: None for v0.1; retain mismatch limitations in future
  adapters.
- Relevant files: `src/boardgate/parsers/scanner.py`,
  `tests/unit/parsers/test_scanner.py`
- Blocking: No.

### ISSUE-002 — Gerbonara Excellon plating argument is ignored

- Status: OPEN
- Severity: low
- Owner: unassigned
- State label: `[CONFIRMED]`
- Context: Gerbonara 1.6.3 exposes `plated=` on `ExcellonFile.open` and
  `from_string`, but `from_string` does not apply it to undefined tool plating.
- Evidence: Local source inspection and plated-hint adapter test.
- Suspected cause: The parameter is accepted but unused in the implementation.
- Attempted approaches: Passed a confirmed plated hint through the documented
  API and inspected resulting object plating.
- Current resolution state: BoardGate applies a confirmed caller hint only
  when parser object plating remains `None`; explicit file plating wins.
- Remaining work: Re-evaluate on dependency upgrades.
- Relevant files: `src/boardgate/parsers/excellon.py`
- Blocking: No.

### ISSUE-004 — GEOS cascaded union degrades on real-scale Gerber input

- Status: RESOLVED
- Severity: high
- Owner: Codex
- State label: `[CONFIRMED]`
- Context: A real two-layer board (six extension-less Gerbers renamed to
  `.gbl/.gbo/.gbs/.gtl/.gto/.gts`, largest 1.3 MB with tens of thousands of
  primitives) reaches rule evaluation after layer mapping succeeds, and the
  copper/mask polarity compositing stalls inside a single GEOS
  `CascadedPolygonUnion` call.
- Evidence: The original process was sampled twice (~18 min and ~84 min
  elapsed, 100% CPU); both samples showed the identical `GEOSUnaryUnion_r` →
  `CascadedPolygonUnion::binaryUnion` stack and never reached report
  composition. After commits c1c97c6 and 3622527, the same private
  126,054-primitive reproduction completed twice in 109.01 s and 109.25 s,
  produced six schema-valid artifacts, remained outside ANALYSIS_FAILED, left
  no worker/temp residue, and produced byte-identical first-five artifacts.
  The final local gate passed 559 tests at 89.69% branch coverage; Actions run
  30511949778 passed all quality, interpreter, test, and cross-platform smoke
  jobs.
- Suspected cause: `unary_union` over tens of thousands of possibly
  overlapping primitive polygons degenerates; derived-geometry compositing
  in the original `src/boardgate/rules/derived_geometry.py` had no
  primitive-count budget and no incremental/spatial pre-grouping.
- Attempted approaches: Waited 84+ minutes with two stack samples; no
  progress beyond the same union call.
- Current resolution state: Resolved for v0.1. RuleEngine creates one
  review-scoped DerivedGeometryWorkspace with deterministic bounded
  composition and cached derived products. Policy 1.0 publishes structured
  coverage gaps instead of entering known-over-budget GEOS work. Production
  rule evaluation runs in a fresh spawn worker that the parent can
  terminate/kill at the remaining review deadline; timeout/crash results are
  discarded into the six-artifact ANALYSIS_FAILED fallback.
- Remaining work: None for ISSUE-004; future resource-policy changes require a
  new policy version, Schema/report updates, and equality/N+1 regressions.
- Relevant files: `src/boardgate/rules/derived_geometry.py`,
  `src/boardgate/rules/engine.py`,
  `src/boardgate/application/rule_runner.py`,
  `src/boardgate/application/review_service.py`,
  `docs/adr/0005-bounded-derived-geometry-and-rule-isolation.md`
- Blocking: No.

### ISSUE-005 — Network-backed NarrativeProvider has no formal support path

- Status: OPEN
- Severity: low
- Owner: unassigned
- State label: `[CONFIRMED]`
- Context: The user operates a local, untracked Kimi provider experiment
  (`experiments/`, git-excluded) that successfully passes the
  NarrativeProvider protocol validation against the Kimi coding endpoint.
  ADR 0003 requires a separate security/privacy decision before any
  network-backed provider enters the repository.
- Evidence: Local experiment runs on 2026-07-29/30 produced validated
  `Agent Evidence Narrative` sections and exact-baseline fallback on
  invalid responses.
- Suspected cause: Deliberate v0.1 boundary, not a defect.
- Attempted approaches: Local programmatic injection via
  `ReviewService(narrative_provider=...)`; the CLI has no provider option.
- Current resolution state: Unresolved. Formal support would need an ADR
  (data-egress scope, credential handling, determinism marker semantics),
  dependency-policy-compliant HTTP client isolation, fallback tests, and an
  explicit CLI opt-in.
- Remaining work: Draft and accept the network-provider ADR before any
  implementation; until then keep experiments untracked.
- Relevant files: `src/boardgate/agent/narrative.py`,
  `docs/adr/0003-deterministic-agent-and-projections.md`
- Blocking: No.

### ISSUE-006 — Python 3.14 CI job used Python 3.12

- Status: RESOLVED
- Severity: medium
- Owner: Codex
- State label: `[CONFIRMED]`
- Context: The Ubuntu test matrix declared Python 3.14, but uv selected the
  repository's default Python 3.12 interpreter after setup.
- Evidence: Actions run 30507555190 job 90760486771 was named
  `tests (3.14)`, while its log records `Using CPython 3.12.3` and
  `platform linux -- Python 3.12.3`. After commit 0c8c85f, run 30511949778
  job 90773711195 records `Using CPython 3.14.6`, passes the explicit runtime
  assertion, and runs pytest on Python 3.14.6.
- Suspected cause: The matrix configured actions/setup-python but did not bind
  uv's interpreter selection to `matrix.python-version`.
- Attempted approaches: Added matrix-scoped `UV_PYTHON`, an explicit
  major/minor assertion, and a local isolated CPython 3.14.4 full-suite run.
- Current resolution state: Resolved. Ubuntu tests now execute and assert both
  declared interpreters; all 559 tests pass locally and in CI on Python 3.14.
- Remaining work: None for this issue.
- Relevant files: `.github/workflows/ci.yml`
- Blocking: No.

### ISSUE-007 — GitHub Actions emit Node 20 deprecation annotations

- Status: OPEN
- Severity: low
- Owner: unassigned
- State label: `[CONFIRMED]`
- Context: GitHub-hosted runners report that the pinned checkout, setup-python,
  and setup-uv action releases target deprecated Node 20 and are being forced
  to run on Node 24.
- Evidence: Successful Actions run 30511949778 annotates
  `actions/checkout@v4`, `actions/setup-python@v5`, and
  `astral-sh/setup-uv@v6` with the Node 20 deprecation notice.
- Suspected cause: The currently pinned action majors have not moved their
  packaged runtime metadata to Node 24.
- Attempted approaches: None; the forced Node 24 execution completed
  successfully on every job.
- Current resolution state: Non-blocking external-tooling warning. No BoardGate
  test or artifact contract is affected.
- Remaining work: Re-evaluate supported newer action majors during the next
  dependency-maintenance pass, including release provenance and changelogs.
- Relevant files: `.github/workflows/ci.yml`
- Blocking: No.

### ISSUE-003 — GitHub HTTPS push is temporarily blocked by proxy

- Status: RESOLVED
- Severity: medium
- Owner: unassigned
- State label: `[CONFIRMED]`
- Context: Local atomic commits after `d297635` initially could not be
  published to `origin/main`.
- Evidence: Repeated normal `git push origin main` attempts return
  `Proxy CONNECT aborted`; the local remote-tracking ref remains `d297635`.
- Suspected cause: The execution environment's configured HTTPS proxy is
  intermittently refusing the GitHub tunnel.
- Attempted approaches: Retried normal non-force pushes after separate rule
  commits, then retried after the recovery commit.
- Current resolution state: A normal push published the complete linear
  history through c1b2407. `git ls-remote`, `gh repo view`, and GitHub Actions
  independently confirmed the public `main` state and a successful CI run.
- Remaining work: None; continue normal pushes without rewriting history.
- Relevant files: `.git/config`
- Blocking: No.

## Next Action

Draft ADR 0006 deciding the Phase 11 transport boundary (read-only HTTP API
versus static viewer consuming the existing six-artifact bundle), including
rejected alternatives and security consequences, before writing any
transport code. (ADR 0004 covers output separation; ADR 0005 covers bounded
derived geometry and rule isolation.)

Start with:

- `docs/adr/0006-review-transport.md` (new)
- Phase 11 scope in `IMPLEMENT_PCB_AGENT.md` lines 1549–1570

Acceptance criteria:

1. The ADR follows the format of ADR 0001–0005 and states why the chosen
   transport cannot mutate the deterministic review evidence.
2. HANDOFF Current State and Next Action are updated in the same commit.

## Recent Activity

### 2026-07-30T15:50:00+08:00 — Claude — post-Codex consistency review

- Role: verification and triage agent
- Task: Independently verify that the Codex ISSUE-004 recovery round
  (commits c1c97c6, 3622527, 0c8c85f, a677e5b) is consistent with the
  repository, then update HANDOFF per BOOTSTRAP.
- Actions performed:
  - Confirmed ADR 0005 exists and matches the four ISSUE-004 acceptance
    criteria (budgeted degradation, shared workspace, deadline-enforced
    spawn worker, bounded reproduction).
  - Confirmed `DerivedGeometryWorkspace` is created once per review in
    `src/boardgate/rules/engine.py` and shared with every rule context, and
    that `src/boardgate/application/rule_runner.py` enforces the remaining
    deadline with terminate/kill on a fresh spawn worker.
  - Confirmed `RuleCoverageGap`, `COMPUTATION_LIMIT`,
    `ANALYSIS_LIMITATION`, and the persisted policy version are wired
    through domain enums, rules, report, and artifact validation.
  - Confirmed `docs/CAPABILITIES.md` documents the workspace, worker, and
    policy-1.0 limits; README claims remain accurate.
  - Re-ran the full gate suite and the CI query, and re-executed the
    private real-scale reproduction independently (see Tests).
  - Found no discrepancies between the Codex HANDOFF claims and repository
    evidence.
- Files modified:
  - `HANDOFF.md`
- Commands run:
  - `uv run ruff format --check .` / `uv run ruff check .`
  - `uv run mypy src tests` (142 files)
  - `uv run python scripts/export_schemas.py` (schemas already current)
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
  - `gh run view 30511949778` (all six jobs success)
  - `uv run pcb-review inspect <renamed private reproduction> --rules
    rules/default.yaml --output <sibling verification output> --overwrite`
- Tests:
  - 559 passed, 89.69% branch coverage — exactly matching the Codex report.
  - Independent reproduction run: 105.9 s wall time (Codex reported
    109.01 s/109.25 s), six artifacts published, policy 1.0 recorded, zero
    coverage gaps, `NOT_READY_FOR_FABRICATION` from the input's missing
    drill/outline/required-layer blockers only; not ANALYSIS_FAILED.
- Evidence: Gate outputs above; verification bundle at
  `/Users/matthew/Projects/testruns/PCB/1-verify.review-output` (private,
  not committed).
- Commit: PENDING (this consistency-review commit)
- Issues created or updated: None. Open set remains ISSUE-002 (low),
  ISSUE-005 (low), ISSUE-007 (low); none blocking.
- Remaining uncertainty: ISSUE-007 action-runtime annotations depend on
  upstream action releases; the private reproduction still lacks drill and
  outline files, so its geometry rules legitimately SKIP.
- Recommended next action: Draft ADR 0006 for the Phase 11 transport
  boundary (see Next Action).

### 2026-07-30T11:46:11+08:00 — Codex — bounded geometry and rule-timeout recovery

- Role: primary recovery and implementation agent
- Task: Resolve ISSUE-004 without replacing completed architecture, correct
  the false Python 3.14 CI matrix, and preserve evidence-first result
  semantics at real-board scale.
- Actions performed:
  - Validated the repository baseline at 84d266d against BOOTSTRAP,
    IMPLEMENT_PCB_AGENT, HANDOFF, git history, the clean worktree, the public
    main branch, and successful pre-change Actions run 30507555190.
  - Added one review-scoped DerivedGeometryWorkspace with cached derivation,
    indexes, composition, components, board material, and contributor queries;
    replaced repeated whole-layer unions with deterministic spatial grouping
    and bounded stable union batches.
  - Added persisted geometry resource policy 1.0, fixed per-layer candidate
    allocations, RuleCoverageGap/COMPUTATION_LIMIT contracts,
    ANALYSIS_LIMITATION risk aggregation, report/Evidence Index projection,
    artifact cross-validation, and current public Schemas.
  - Added conservative regressions for unknown polarity, unsupported exact
    geometry, clear subtraction, trace slivers, equality/N+1 budgets, query
    order/cache isolation, mixed/all-limited semantics, and pre-GEOS extreme
    geometry rejection.
  - Added a fresh spawn-isolated default rule worker with private bounded
    canonical-JSON staging, small typed Pipe envelope, result size/hash/model
    validation, exact deadline polling, terminate/kill cleanup, and
    six-artifact ANALYSIS_FAILED fallback.
  - Bound CI uv selection to the declared matrix interpreter, asserted the
    actual version, and expanded Linux/macOS/Windows smoke jobs to run a
    complete valid fixture review through the spawn worker.
  - Accepted ADR 0005 and updated CAPABILITIES with the resource and worker
    boundaries. Two independent read-only adversarial audits reported no
    remaining geometry, false-hardware, worker, cleanup, or contract blocker.
- Files modified:
  - `src/boardgate/rules/`, `src/boardgate/application/rule_runner.py`,
    `src/boardgate/application/review_service.py`,
    `src/boardgate/application/artifacts.py`
  - `src/boardgate/reporting/markdown.py`,
    `src/boardgate/agent/risk_modes.py`,
    `src/boardgate/domain/enums.py`
  - `tests/unit/rules/`, `tests/unit/application/`,
    `tests/unit/reporting/test_markdown.py`
  - `schemas/v1/`, `.github/workflows/ci.yml`,
    `docs/adr/0005-bounded-derived-geometry-and-rule-isolation.md`,
    `docs/CAPABILITIES.md`, `HANDOFF.md`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run python scripts/export_schemas.py`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
  - `UV_PYTHON=3.14 uv run --isolated --python 3.14 pytest -q`
  - Two private `uv run pcb-review inspect` runs over the 126,054-primitive
    reproduction, followed by strict bundle validation and first-five
    artifact SHA-256 equality checks.
  - `git push origin main`, `gh run watch 30511949778 --exit-status`, and
    3.14 job-log inspection.
- Tests:
  - Python 3.12.13: 559 passed; 89.69% branch coverage.
  - Python 3.14.4: 559 passed.
  - Private real-scale runs: 109.01 s and 109.25 s; six valid artifacts per
    run; not ANALYSIS_FAILED; byte-identical first five; no worker/temp
    residue.
  - GitHub Actions 30511949778: all six jobs passed; the 3.14 job used
    CPython 3.14.6; all three OS smoke jobs completed a valid review.
- Commits:
  - `c1c97c6 feat(geometry): share bounded derived geometry`
  - `3622527 feat(review): isolate rule evaluation behind timeout`
  - `0c8c85f ci: enforce declared Python runtimes`
  - `docs(handoff): record bounded geometry recovery` (the commit containing
    this activity record)
- Generated artifacts: Two private six-artifact review bundles were validated
  and compared outside the repository; neither the input nor outputs were
  committed.
- Issues created or updated: ISSUE-004 resolved; ISSUE-006 created and
  resolved; ISSUE-007 opened as a non-blocking external Actions warning.
  ISSUE-002 and ISSUE-005 remain open and non-blocking.
- Remaining uncertainty: Future policy changes require a new policy version;
  network NarrativeProvider support still requires its own security/privacy
  ADR; supported Node 24 action majors require dependency review.

### 2026-07-30T13:10:00+08:00 — Claude — open-issue audit for Codex handoff

- Role: triage agent
- Task: Audit all currently unresolved issues beyond ISSUE-004 and prepare
  HANDOFF for a Codex implementation round.
- Actions performed:
  - Grepped `src/` for TODO/FIXME markers: none.
  - Confirmed the complete open-issue set: ISSUE-002 (low, Gerbonara
    plating hint ignored — re-evaluate on dependency upgrades), ISSUE-004
    (high, blocking real-scale inputs), and the newly recorded ISSUE-005
    (low, network NarrativeProvider needs its own ADR per ADR 0003).
  - Added ISSUE-005 with evidence from the user's working local Kimi
    experiment.
  - Replaced Next Action with a bounded ISSUE-004 fix including the local
    real-scale reproduction input path.
- Files modified:
  - `HANDOFF.md`
- Commands run:
  - `grep -rn "TODO|FIXME|XXX" src/`
- Tests: None; documentation-only triage.
- Evidence: Open issues above; resolved issues (ISSUE-001, ISSUE-003)
  remain listed until archival.
- Commit: `35f3ba6 docs(handoff): audit open issues and target ISSUE-004
  for Codex`
- Issues created or updated: ISSUE-005 created.
- Remaining uncertainty: ISSUE-002 depends on a future Gerbonara upgrade.
- Recommended next action: Resolve ISSUE-004 (see Next Action).

### 2026-07-30T12:40:00+08:00 — Claude — output separation and config precedence

- Role: primary implementation agent
- Task: Turn the user's output-separation principle into a permanent norm
  (ADR 0004) and implement three-tier output resolution.
- Actions performed:
  - Accepted ADR 0004: strict input/output separation; CLI option >
    boardgate.toml > built-in sibling default; TOML via stdlib tomllib
    (YAML deferred, no new dependency).
  - Added strict size-bounded ProjectConfig loader, output resolution and
    sibling-default helpers, and CLI wiring (--output now optional).
  - Added 27 unit/integration tests covering precedence, config validation,
    overlap rejection, multi-input requirements, and archive stem defaults.
  - Updated both README walkthroughs and the troubleshooting tables.
- Files modified:
  - `docs/adr/0004-output-separation-and-config-precedence.md`
  - `src/boardgate/config/project.py`, `src/boardgate/config/__init__.py`
  - `src/boardgate/application/output.py`, `src/boardgate/cli.py`
  - `tests/unit/config/test_project_config.py`
  - `tests/unit/application/test_output.py`
  - `tests/integration/test_output_precedence.py`
  - `README.md`, `README.zh-CN.md`
  - `HANDOFF.md`
- Commands run:
  - `uv run ruff format --check .` / `uv run ruff check .`
  - `uv run mypy src tests` (139 files)
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests: Full suite 515 passed, 90.75% branch coverage.
- Evidence: Gate outputs above; precedence integration tests run the real
  CLI against fixture copies.
- Commit: `35f8426 feat(cli): resolve output via CLI, project config, then
  default`
- Issues created or updated: None; ISSUE-004 remains open and blocking for
  real-scale geometry inputs.
- Remaining uncertainty: Phase 11 transport direction still undecided.
- Recommended next action: Draft ADR 0005 for the Phase 11 transport
  boundary (see Next Action).

### 2026-07-29T01:35:00+08:00 — Claude — bilingual walkthrough, push, and CI confirmation

- Role: documentation and release agent
- Task: Add the user-facing walkthrough and publish all recovered commits.
- Actions performed:
  - Added an eight-step user walkthrough (install, input preparation, first
    review, six artifacts, report reading, CI usage, profile tuning,
    troubleshooting) to `README.md` and mirrored it in `README.zh-CN.md`.
  - Verified every factual claim against the live CLI help, a real fixture
    run, `ReviewStatus`/`RuleSeverity` enums, and ADR 0002.
  - Pushed ten local commits to `origin/main` with a normal push.
- Files modified:
  - `README.md`
  - `README.zh-CN.md`
  - `HANDOFF.md` (this update)
- Commands run:
  - `uv run pcb-review --help` / `inspect --help`
  - `uv run pcb-review inspect tests/fixtures/copper_too_close_to_edge ...`
  - `git push origin main`
  - `git ls-remote origin main`
  - `gh run watch 30414220783 --exit-status`
- Tests: No new tests; documentation-only change. Full gates were last run
  at ccfb1a0 (495 passed, 90.63% coverage).
- Evidence: `git ls-remote` reports origin/main at a037220; GitHub Actions
  run 30414220783 completed successfully in 1m26s.
- Commit: `a037220 docs(readme): add bilingual user walkthrough`
- Issues created or updated: None.
- Remaining uncertainty: Phase 11 transport direction is undecided.
- Recommended next action: Draft ADR 0004 for the Phase 11 transport
  boundary (see Next Action).

### 2026-07-29T00:00:00+08:00 — Claude — recovery, gate repair, and atomic commits

- Role: primary recovery agent
- Task: Recover the network-interrupted session, verify the actual repository
  state, and land the completed Phase 9/10 working tree as atomic commits
  without reimplementing finished work.
- State labels:
  - `[CONFIRMED] Actual recovery HEAD was 1932282 (fixture commit already
    landed); HANDOFF was one commit stale and its fixture entry said
    PENDING — that PENDING marker objectively refers to 1932282.`
  - `[CONFIRMED] The interrupted working tree already contained the complete
    ReviewService, agent orchestration, run-log schema, ingestion hardening,
    fixture matrices, property tests, and CAPABILITIES doc.`
  - `[CONFIRMED] PROJECT_SPEC.md remains absent; IMPLEMENT_PCB_AGENT.md is
    the canonical specification.`
- Actions performed:
  - Read BOOTSTRAP.md, HANDOFF.md, IMPLEMENT_PCB_AGENT.md, ADR 0003, and the
    full uncommitted diff before editing.
  - Fixed one interrupted-session test bug (missing parent mkdir in
    test_output_ancestor_of_input_is_rejected_and_preserves_input) and three
    lint issues in test_inspect_review.py (unused imports, lambda
    assignment); no production code needed changes.
  - Split the working tree into three atomic commits and verified each on
    its own staged tree via `git stash push -u --keep-index` before
    committing.
- Files modified:
  - `tests/integration/test_inspect_manifest.py` (test fix, committed in
    9d1de3d)
  - `tests/integration/test_inspect_review.py` (lint fixes, committed in
    9d1de3d)
  - `HANDOFF.md` (this update, uncommitted)
- Commands run:
  - `uv run ruff format --check .` / `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
  - `uv run python scripts/export_schemas.py` (schemas already current)
  - `uv lock --check`
- Tests:
  - Commit b0ff240 staged tree: 444 passed, 90.40% branch coverage.
  - Commit 9d1de3d staged tree: 471 passed, 90.57% branch coverage.
  - Final HEAD ccfb1a0: 495 passed, 90.63% branch coverage; Ruff and mypy
    clean (136 source files).
- Evidence: Gate outputs above; clean `git status` at ccfb1a0.
- Commits:
  - `b0ff240 feat(agent): add deterministic orchestration boundary`
  - `9d1de3d feat(review): wire complete review pipeline through the CLI`
  - `ccfb1a0 test(review): harden ingestion and add fixture and property
    matrices`
- Issues created or updated: None; ISSUE-002 remains open and non-blocking.
- Remaining uncertainty: The seven local commits are unpublished; GitHub
  Actions has not run for them.
- Recommended next action: Push to origin/main and confirm CI (see Next
  Action).

### 2026-07-28T21:36:05+08:00 — Codex — original Phase 9 PCB fixtures

- Role: primary implementation agent
- Task: Add license-safe golden projects for complete-review integration.
- Actions performed:
  - Added original 20 x 15 mm X2 Gerber/Excellon fixtures with shared
    coordinates, closed profile, top/bottom copper, plated round drill, unique
    standard pads, and eligible standard traces.
  - Verified the valid fixture reaches `READY_FOR_REVIEW` with all required
    rules passing and no Findings.
  - Added an edge variant that changes only trace position and deterministically
    produces two confirmed 0.150 mm copper-to-edge Findings.
- Files modified:
  - `tests/fixtures/valid_minimal_board/*`
  - `tests/fixtures/copper_too_close_to_edge/*`
  - `tests/integration/test_review_fixtures.py`
  - `HANDOFF.md`
- Commands run:
  - `uv run pytest tests/integration/test_review_fixtures.py -q`
  - `uv run ruff format --check tests/integration/test_review_fixtures.py`
  - `uv run ruff check tests/integration/test_review_fixtures.py`
  - `uv run mypy src tests`
  - `git diff --check`
- Tests:
  - Focused fixture integration suite: 2 passed.
  - Shared-tree full suite: 427 passed, 91.02% branch coverage.
- Evidence: Manifest classification, X2 mapping, SameCoordinates, outline
  closure, plated drill, unique annular matches, supported traces, complete
  required-rule coverage, and exact edge measurements.
- Commit: PENDING (this original Phase 9 fixture commit)
- Issues created or updated: The example profile keeps copper-edge severity at
  WARNING, so confirmed edge Findings do not by themselves create a blocker.
- Recommended next action: Wire the complete Phase 9 ReviewService and CLI.

### 2026-07-28T21:35:04+08:00 — Codex — deterministic standalone SVG

- Role: primary implementation agent
- Task: Render Phase 9 PCB and Finding evidence as a safe static SVG.
- Actions performed:
  - Rendered board outer contours/cutouts, Line/Arc/Flash/Region primitives,
    round drills, and routed slots in stable groups.
  - Applied an automatic viewBox and explicit X-right/Y-up to SVG screen
    transform while retaining analytic arcs.
  - Added spatial Finding markers and a deterministic non-spatial legend, each
    carrying the exact `data-finding-id`.
  - Escaped XML text/attributes and emitted no scripts, event handlers, DTD,
    external URL, or external style.
- Files modified:
  - `src/boardgate/rendering/__init__.py`
  - `src/boardgate/rendering/svg.py`
  - `tests/unit/rendering/test_svg.py`
  - `HANDOFF.md`
- Commands run:
  - `uv run pytest tests/unit/rendering/test_svg.py -q`
  - `uv run ruff check src/boardgate/rendering tests/unit/rendering`
  - `uv run mypy src tests`
  - `git diff --check`
- Tests:
  - Focused SVG suite: 8 passed with 87% renderer branch coverage.
  - Shared-tree full suite: 427 passed, 91.02% branch coverage.
- Evidence: Stable rendering, automatic viewBox, board/cutout groups, every
  primitive type, round/slot drills, arc/full-circle paths, coordinate
  reflection, spatial/non-spatial Findings, mismatch rejection, XML escaping,
  and no active/external content.
- Commit: `650525b feat(rendering): generate deterministic review SVG`
- Issues created or updated: None.
- Recommended next action: Wire the complete Phase 9 ReviewService and CLI.

### 2026-07-28T21:35:02+08:00 — Codex — deterministic Markdown report

- Role: primary implementation agent
- Task: Compose the Phase 9 engineer-facing report solely from structured
  project and review evidence.
- Actions performed:
  - Added all normative report sections for assessment, confidence, inputs,
    project interpretation, severity-grouped Findings, rule execution,
    limitations, confirmations, actions, Evidence Index, and disclaimer.
  - Preserved every Finding ID and resolved source SHA/object/span and witness
    evidence without inferring missing facts.
  - Escaped source-controlled Markdown content and enforced bounded wording
    for `PASS + PARTIAL`.
  - Rendered sanitized analysis diagnostics for `ANALYSIS_FAILED` bundles.
- Files modified:
  - `src/boardgate/reporting/__init__.py`
  - `src/boardgate/reporting/markdown.py`
  - `tests/unit/reporting/test_markdown.py`
  - `HANDOFF.md`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests:
  - Focused report suite: 7 passed with 98% reporting branch coverage.
  - Shared-tree full suite: 427 passed, 91.02% branch coverage.
- Evidence: Exact section coverage, deterministic bytes, severity grouping,
  escaped Markdown, partial-pass wording, missing inputs, parser and analysis
  diagnostics, unresolved evidence, line/byte spans, and project-ID mismatch.
- Commit: `516279f feat(reporting): compose evidence-backed review report`
- Issues created or updated: None.
- Recommended next action: Commit the deterministic standalone SVG renderer.

### 2026-07-28T21:32:21+08:00 — Codex — complete review artifact contract

- Role: primary implementation agent
- Task: Define Phase 9 artifact completeness, diagnostics, and failure
  semantics before wiring the review service.
- Actions performed:
  - Accepted ADR 0002 defining the exact six-file bundle, deterministic versus
    run-varying bytes, post-ingestion fallback, and CLI exit precedence.
  - Added strict sanitized `AnalysisDiagnostic` values to `ReviewResult`
    without converting unavailable analysis into fabricated rule Findings.
  - Added canonical JSON, structured JSONL, exact inventory, cross-model
    identity, Finding-reference, safe SVG, and run-variance validation.
  - Added an `ANALYSIS_FAILED` review builder and regenerated the affected
    Draft 2020-12 findings Schema.
- Files modified:
  - `docs/adr/0002-review-artifacts-and-failures.md`
  - `src/boardgate/application/artifacts.py`
  - `src/boardgate/domain/diagnostic.py`
  - `src/boardgate/rules/models.py`
  - `schemas/v1/findings.schema.json`
  - `tests/unit/application/test_artifacts.py`
  - `tests/unit/domain/test_diagnostic.py`
  - `HANDOFF.md`
- Commands run:
  - `uv run pytest tests/unit/domain/test_diagnostic.py
    tests/unit/application/test_artifacts.py -q`
  - `uv run ruff check` on the changed Python files
  - `uv run mypy` on the changed Python files
  - `git diff --check`
- Tests:
  - Focused diagnostic and artifact-contract suite: 38 passed.
  - Extended agent verification: 261 passed; Ruff format/check and mypy
    passed over the then-current shared tree.
- Evidence: Exact inventory rejection, deterministic-byte comparison,
  public Schema round trips, cross-artifact ID mismatch rejection, unsafe SVG
  rejection, monotonic single-run JSONL, summary sanitization, and
  analysis-unavailable round trip.
- Commit: `bb282f4 feat(review): define complete artifact contract`
- Issues created or updated: ADR 0002 accepted; no blocking issue created.
- Recommended next action: Commit the deterministic Markdown report composer.

### 2026-07-28T21:15:02+08:00 — Codex — placement anchor containment

- Role: primary implementation agent
- Task: Complete Phase 8 with `placement_outside_board_outline` v1.
- Actions performed:
  - Evaluated populated, non-ignored CPL anchor points against derived board
    material while explicitly excluding body/courtyard/rotation inference.
  - Used outer contours minus nested cutouts and treated exact external and
    cutout boundaries as not outside, with PARTIAL coverage inside the
    propagated outline/geometry error band.
  - Distinguished missing, empty, failed, and DNP/ignored placement inputs and
    rejected missing/open/invalid outline topology.
  - Attached placement row, location, distance measurement, outline witness,
    and source-relevant uncertainty to stable Findings.
  - Registered the sixteenth and final Phase 8 built-in rule.
- Files modified:
  - `src/boardgate/rules/assembly_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_placement_outside_board_outline.py`
  - `HANDOFF.md`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests:
  - Focused placement-outline tests: 11 passed.
  - Full suite: 374 passed, 90.56% branch coverage.
- Evidence: Inactive/missing/empty/failed inputs, missing/open outline,
  inside/outside anchors, exact outer/cutout boundary behavior, cutout
  interior, top/bottom anchor parity, DNP/marker/ignore filtering, relevant
  uncertainty, row and outline witnesses, stable IDs, and ReviewResult JSON
  round-trip.
- Commit: `0ece4bb feat(rule): validate placement anchor containment`
- Issues created or updated: None.
- Recommended next action: Define the Phase 9 review artifact/failure
  contract and validation boundary.

### 2026-07-28T21:06:55+08:00 — Codex — duplicate reference designators

- Role: primary implementation agent
- Task: Detect duplicate references independently within BOM and placement
  datasets.
- Actions performed:
  - Reused normalized DNP/ignore filtering while keeping BOM and placement
    occurrence maps independent.
  - Aggregated all duplicate references for one dataset into one Finding so
    multi-reference rows retain complete provenance without colliding IDs.
  - Kept a reference that appears once in each dataset as a valid
    non-duplicate.
  - Limited confirmation downgrades to uncertainty tied to assembly sources;
    unrelated project uncertainty does not weaken a definite duplicate.
  - Registered the fifteenth deterministic built-in rule.
- Files modified:
  - `src/boardgate/rules/assembly_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_duplicate_reference_designator.py`
  - `HANDOFF.md`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests:
  - Focused duplicate-reference tests: 8 passed.
  - Full suite: 363 passed, 90.48% branch coverage.
- Evidence: Inactive scope, case-insensitive BOM and CPL duplicates,
  cross-dataset non-duplicate, DNP/marker/ignore filtering, multi-reference
  evidence aggregation, relevant and unrelated uncertainty, deterministic
  IDs, and ReviewResult JSON round-trip.
- Commit: `1640bcb feat(rule): detect duplicate reference designators`
- Issues created or updated: ISSUE-003 resolved after c1b2407 was pushed and
  its GitHub Actions run completed successfully.
- Recommended next action: Implement `placement_outside_board_outline` v1.

### 2026-07-28T20:58:57+08:00 — Codex — Recovery and BOM/CPL reference match

- Role: primary recovery and implementation agent
- Task: Recover the interrupted repository state and complete
  `bom_placement_reference_match` v1 without reimplementing committed work.
- State labels:
  - `[CONFIRMED] PROJECT_SPEC.md is absent from HEAD, all available refs, and
    repository history; IMPLEMENT_PCB_AGENT.md is the tracked canonical
    implementation specification referenced by both READMEs.`
  - `[CONFIRMED] Actual recovery HEAD was 8210f5d with 13 committed rules and
    an unfinished BOM/CPL working tree; HANDOFF was one commit stale.`
- Actions performed:
  - Read BOOTSTRAP.md, IMPLEMENT_PCB_AGENT.md, HANDOFF.md, repository
    architecture documents, test configuration, current diffs, and recent
    local/remote history before editing.
  - Re-ran the interrupted working tree before repair: 330 tests passed and
    the only failure was the stale PCBProject Schema; Ruff reported two
    assembly-rule issues and mypy reported the same missing return type.
  - Added explicit placement DNP/Fitted/Populate normalization and preserved
    the default-false JSON contract.
  - Compared case-folded populated BOM/CPL reference sets after symmetric DNP
    and ignored-reference filtering, with explicit missing, failed, and
    candidate dataset evidence.
  - Aggregated directional BOM-only and placement-only facts into one
    evidence-backed mismatch Finding. This follows the existing Finding ID
    contract and avoids fabricating provenance when several references share
    one BOM row.
  - Stopped treating a classified assembly source with an ERROR diagnostic as
    usable for readiness, while treating a successfully parsed empty dataset
    as usable.
  - Regenerated the PCBProject Draft 2020-12 Schema and added deterministic
    parser, rule, status, candidate-filtering, failure, provenance, and JSON
    round-trip tests.
- Files modified:
  - `schemas/v1/project.schema.json`
  - `src/boardgate/domain/component.py`
  - `src/boardgate/parsers/placement.py`
  - `src/boardgate/rules/assembly_data.py`
  - `src/boardgate/rules/assembly_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `src/boardgate/rules/engine.py`
  - `tests/unit/domain/test_component.py`
  - `tests/unit/parsers/test_placement.py`
  - `tests/unit/rules/test_bom_placement_reference_match.py`
  - `tests/unit/rules/test_engine.py`
  - `HANDOFF.md`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run python scripts/export_schemas.py`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests:
  - Focused recovery and assembly tests: 48 passed.
  - Full suite: 355 passed, 90.44% branch coverage.
- Evidence: Inactive scope, case/whitespace normalization, directional
  mismatch provenance, multi-reference stable ID, missing BOM/CPL, explicit
  and marker DNP, ignored references, relevant/unrelated classification
  candidates, parser failure, readiness precedence, determinism, checked-in
  Schema currency, and ReviewResult JSON round-trip.
- Commit: `c1b2407 feat(rule): reconcile BOM and placement references`
- Issues created or updated: ISSUE-003 retained pending a normal push.
- Recommended next action: Implement `duplicate_reference_designator` v1.

### 2026-07-28T18:37:16+08:00 — Codex — minimum_solder_mask_dam v1

- Role: primary implementation agent
- Task: Measure true solder-mask dams without inventing gang-opening defects.
- Actions performed:
  - Composited mask polarity per side and flattened final openings into stable
    connected components.
  - Used the shared STRtree distance query only within each mask layer and
    applied equality-safe approximation/error-band decisions.
  - Kept one connected/gang opening as one component, so it is never compared
    with itself or reported as a zero-width dam.
  - Rejected weak/mis-sided/unknown-polarity/macro input and downgraded
    source-limited results to PARTIAL confirmation.
- Files modified:
  - `src/boardgate/rules/surface_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_minimum_solder_mask_dam.py`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests:
  - Focused solder-mask-dam tests: 11 passed.
  - Full suite: 331 passed, 90.17% branch coverage.
- Evidence: Pass/violation/equality/error-band, gang-opening exclusion,
  same/opposite-side separation, clear-polarity split, mapping/polarity/macro
  and source uncertainty, direct witnesses, determinism, and JSON round-trip.
- Commit: `8210f5d feat(rule): measure solder mask dams`
- Issues created or updated: None.
- Recommended next action: Implement `bom_placement_reference_match` v1.

### 2026-07-28T18:33:33+08:00 — Codex — silkscreen_over_exposed_pad v1

- Role: primary implementation agent
- Task: Detect same-side silkscreen over copper exposed by mask openings.
- Actions performed:
  - Paired trusted copper, solder-mask, and silkscreen layers strictly by side
    and rejected weak, duplicated, mis-sided, or unknown-polarity mappings.
  - Intersected polarity-composited copper and mask-opening geometry, then
    measured real silkscreen overlap rather than bounding-box overlap.
  - Used eroded robust-overlap witnesses to distinguish confirmed overlap from
    approximation-band confirmation.
  - Added square-millimetre measurements and regenerated all affected Draft
    2020-12 public schemas.
- Files modified:
  - `src/boardgate/domain/geometry.py`
  - `src/boardgate/rules/common.py`
  - `src/boardgate/rules/derived_geometry.py`
  - `src/boardgate/rules/drill_rules.py`
  - `src/boardgate/rules/surface_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `schemas/v1/finding.schema.json`
  - `schemas/v1/findings.schema.json`
  - `schemas/v1/project.schema.json`
  - `tests/unit/domain/test_geometry.py`
  - `tests/unit/rules/test_silkscreen_over_exposed_pad.py`
- Commands run:
  - `uv run python scripts/export_schemas.py`
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests:
  - Focused surface/schema/geometry tests: 28 passed.
  - Full suite: 320 passed, 90.06% branch coverage.
- Evidence: Same/opposite-side, no-overlap/equality, robust/error-band overlap,
  missing optional input, mapping/polarity/macro/source uncertainty, bottom
  side, three-layer provenance, determinism, and JSON round-trip tests.
- Commit: `5bf2d15 feat(rule): detect silkscreen over exposed pads`
- Issues created or updated: None.
- Recommended next action: Implement `minimum_solder_mask_dam` v1.

### 2026-07-28T18:26:35+08:00 — Codex — minimum_annular_ring v1

- Role: primary implementation agent
- Task: Measure only provable plated-drill/standard-pad annular rings.
- Actions performed:
  - Matched confirmed plated round hits to exactly one same-location standard
    circular pad flash on each trusted copper layer.
  - Calculated minimum radial ring from pad diameter, drill diameter, and
    measured center eccentricity with equality-safe error-band semantics.
  - Excluded NPTH, unknown plating, slots, macro/non-round pads, and prevented
    clear/unknown-polarity interference from becoming numeric claims.
  - Emitted evidence-backed confirmation findings for unmatched or ambiguous
    pad intent and stable per-layer IDs.
- Files modified:
  - `src/boardgate/rules/drill_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_minimum_annular_ring.py`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests:
  - Focused annular-ring tests: 15 passed.
  - Full suite: 309 passed, 89.70% branch coverage.
- Evidence: Pass/violation/equality/negative-ring/eccentricity/error-band,
  plating exclusions, unmatched/ambiguous/clear-polarity evidence, unique IDs,
  source uncertainty, determinism, and JSON round-trip tests.
- Commit: `ed56bdd feat(rule): measure supported annular rings`
- Issues created or updated: None.
- Recommended next action: Implement `silkscreen_over_exposed_pad` v1.

### 2026-07-28T18:20:59+08:00 — Codex — minimum_drill_diameter v1

- Role: primary implementation agent
- Task: Measure known circular drill hits without misclassifying routed slots.
- Actions performed:
  - Added a drill-rule module and registered round-hit diameter evaluation.
  - Applied equality-safe minimum/error-band decisions using the configured
    geometry epsilon.
  - Excluded routed slots explicitly and made source limitations downgrade
    violations or passing scope to human-confirmed PARTIAL coverage.
  - Preserved hit/tool and uncertainty provenance while stating that plating
    is outside this rule's decision.
- Files modified:
  - `src/boardgate/rules/drill_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_minimum_drill_diameter.py`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests:
  - Focused drill-diameter tests: 9 passed.
  - Full suite: 294 passed, 89.53% branch coverage.
- Evidence: Pass/violation/equality/error-band/source-uncertainty/tool-code,
  slot exclusion, stability, and JSON round-trip tests.
- Commit: `e62c94d feat(rule): enforce minimum drill diameter`
- Issues created or updated: None.
- Recommended next action: Implement `minimum_annular_ring` v1.

### 2026-07-28T18:17:30+08:00 — Codex — minimum_copper_to_edge v1

- Role: primary implementation agent
- Task: Measure final copper containment and clearance to every board edge.
- Actions performed:
  - Derived board material from all outer contours minus nested cutouts.
  - Measured polarity-composited copper components against outer and cutout
    boundaries without exposing Shapely objects in public contracts.
  - Used signed clearance for out-of-material copper and propagated copper,
    outline, and geometry-epsilon error bounds.
  - Applied profile `confirm|strict` edge-touch policy and kept uncertainty
    orthogonal to configured severity.
- Files modified:
  - `src/boardgate/rules/derived_geometry.py`
  - `src/boardgate/rules/geometry_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_minimum_copper_to_edge.py`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests:
  - Focused copper-edge tests: 8 passed.
  - Full suite: 285 passed, 89.40% branch coverage.
- Evidence: Outer/cutout/pass/equality/touch-policy/outside/error-band,
  evidence, determinism, and JSON round-trip tests.
- Commit: `4cd2a11 feat(rule): measure copper to board edges`
- Issues created or updated: None.
- Recommended next action: Implement `minimum_drill_diameter` v1.

### 2026-07-28T18:11:36+08:00 — Codex — minimum_copper_spacing v1

- Role: primary implementation agent
- Task: Compare distinct connected final-copper components without net data.
- Actions performed:
  - Flattened polarity-composited copper into stable per-layer components.
  - Added STRtree distance candidate selection with unique same-layer pairs
    and a brute-force equivalence test.
  - Preserved both component witnesses and explicitly avoided net claims.
  - Applied geometry error to equality/confirmed/PARTIAL spacing outcomes.
- Files modified:
  - `src/boardgate/rules/derived_geometry.py`
  - `src/boardgate/rules/geometry_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_minimum_copper_spacing.py`
- Tests:
  - Focused spacing tests: 8 passed.
  - Full suite: 277 passed, 89.21% branch coverage.
- Evidence: Component/polarity/layer/STRtree/equality/error-band tests.
- Commit: `93bcf99 feat(rule): measure composite copper spacing`
- Issues created or updated: None.
- Recommended next action: Implement `minimum_copper_to_edge` v1.

### 2026-07-28T18:08:20+08:00 — Codex — minimum_trace_width v1

- Role: primary implementation agent
- Task: Measure only supported final-copper trace draws.
- Actions performed:
  - Added local Shapely derivation for analytic lines/arcs/flashes/regions and
    polarity composition without serializing third-party geometry.
  - Limited eligibility to trusted copper and dark circular-aperture draws.
  - Excluded traces fully widened by other copper and traces altered by clear
    polarity; unsupported aperture geometry downgraded coverage.
  - Applied equality-safe minimum/error-band semantics with stable witnesses.
- Files modified:
  - `src/boardgate/rules/derived_geometry.py`
  - `src/boardgate/rules/geometry_rules.py`
  - `src/boardgate/rules/models.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_minimum_trace_width.py`
- Tests:
  - Focused trace/engine tests: 21 passed.
  - Full suite: 269 passed, 88.71% branch coverage.
- Evidence: Width pass/fail/equality/widening/polarity/error-band tests.
- Commit: `7565483 feat(rule): measure eligible trace widths`
- Issues created or updated: None.
- Recommended next action: Implement `minimum_copper_spacing` v1.

### 2026-07-28T18:03:57+08:00 — Codex — gross coordinate alignment v1

- Role: primary implementation agent
- Task: Detect only aggregate Gerber/drill coordinate disjointness.
- Actions performed:
  - Built conservative physical bounds for round holes, line slots, and full
    arc-slot circles.
  - Compared aggregate drill and trusted board bboxes using gross tolerance
    plus propagated outline error.
  - Distinguished exact-boundary pass, confirmed disjointness, and PARTIAL
    error-band overlap.
  - Stated explicitly in PASS and Finding facts that pad registration is not
    evaluated.
- Files modified:
  - `src/boardgate/rules/geometry_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_coordinate_alignment.py`
- Tests:
  - Focused alignment tests: 6 passed.
  - Full suite: 262 passed, 89.63% branch coverage.
- Evidence: Overlap/equality/disjoint/error-band/no-feature/round-trip tests.
- Commit: `4139215 feat(rule): detect gross drill coordinate mismatch`
- Issues created or updated: None.
- Recommended next action: Implement `minimum_trace_width` v1.

### 2026-07-28T18:01:21+08:00 — Codex — multiple_outline_regions v1

- Role: primary implementation agent
- Task: Detect disjoint outer board regions without counting cutouts.
- Actions performed:
  - Counted reconstructed outer contours only and explicitly excluded cutouts.
  - Passed one outer region even with nested cutouts.
  - Emitted one stable design-intent confirmation with per-contour witness
    bounds for multiple outer regions.
  - Depended on closed outline topology and kept missing outlines
    NOT_APPLICABLE.
- Files modified:
  - `src/boardgate/rules/file_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_multiple_outline_regions.py`
- Tests:
  - Focused topology tests: 4 passed.
  - Full suite: 256 passed, 89.68% branch coverage.
- Evidence: Single/cutout/multiple/dependency/stability/round-trip tests.
- Commit: `99b4b1f feat(rule): detect multiple outer board regions`
- Issues created or updated: None.
- Recommended next action: Implement gross Gerber/drill coordinate alignment.

### 2026-07-28T17:59:22+08:00 — Codex — board_outline_closed v1

- Role: primary implementation agent
- Task: Evaluate analytic contour closure and reconstruction error.
- Actions performed:
  - Added equality-safe maximum-threshold/error-band semantics.
  - Verified contour flags, endpoint gaps, and propagated outline measurement
    error against `tolerances.outline_closure`.
  - Emitted confirmed geometry blockers versus PARTIAL outline confirmations.
  - Kept absent outlines NOT_APPLICABLE and depended on outline presence.
- Files modified:
  - `src/boardgate/rules/models.py`
  - `src/boardgate/rules/file_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_board_outline_closed.py`
- Tests:
  - Focused closure tests: 6 passed.
  - Full suite: 252 passed, 89.66% branch coverage.
- Evidence: Closed/equality/open/error-band/absence/dependency tests.
- Commit: `13c390d feat(rule): verify board outline closure`
- Issues created or updated: None.
- Recommended next action: Implement `multiple_outline_regions` v1.

### 2026-07-28T17:56:37+08:00 — Codex — board_outline_present v1

- Role: primary implementation agent
- Task: Require a trustworthy reconstructed board boundary.
- Actions performed:
  - Passed only a normalized BoardOutline, not a filename or layer alone.
  - Distinguished complete absence from mapped/candidate layers whose
    reconstruction remains uncertain.
  - Added stable full blocker and PARTIAL confirmation Findings with layer and
    inventory evidence.
- Files modified:
  - `src/boardgate/rules/file_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_board_outline_present.py`
- Tests:
  - Focused outline-presence tests: 5 passed.
  - Full suite: 246 passed, 89.60% branch coverage.
- Evidence: Reconstructed/candidate/missing/stability/round-trip tests.
- Commit: `7f93695 feat(rule): require reconstructed board outline`
- Issues created or updated: None.
- Recommended next action: Implement `board_outline_closed` v1.

### 2026-07-28T17:54:09+08:00 — Codex — drill_file_present v1

- Role: primary implementation agent
- Task: Distinguish usable drill input from absence and parser uncertainty.
- Actions performed:
  - Counted a successfully parsed Excellon source as present even with zero
    hits.
  - Converted confirmed absence into a stable full-coverage blocker Finding.
  - Converted unresolved classifications and parser failures into PARTIAL
    confirmation Findings instead of false absence.
  - Added diagnostic and inventory provenance plus the exact rule config path.
- Files modified:
  - `src/boardgate/rules/file_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `tests/unit/rules/test_drill_file_present.py`
- Tests:
  - Focused file-rule tests: 10 passed.
  - Full suite: 241 passed, 89.61% branch coverage.
- Evidence: Empty/present/missing/candidate/failure/stability/round-trip tests.
- Commit: `27bce17 feat(rule): require parsed drill input`
- Issues created or updated: None.
- Recommended next action: Implement `board_outline_present` v1.

### 2026-07-28T17:51:35+08:00 — Codex — required_layers_present v1

- Role: primary implementation agent
- Task: Implement the first evidence-backed file/layer rule.
- Actions performed:
  - Required only strong, uncertainty-free mappings to satisfy profile roles.
  - Distinguished confirmed inventory absence from unresolved file or layer
    candidates.
  - Emitted stable blocker Findings for confirmed absence and confirmation
    Findings with PARTIAL coverage for ambiguity.
  - Added direct Finding config paths and shared profile-bound Finding ID,
    severity, and evidence helpers.
  - Registered the rule in the incremental built-in registry.
- Files modified:
  - `src/boardgate/rules/common.py`
  - `src/boardgate/rules/file_rules.py`
  - `src/boardgate/rules/builtin.py`
  - `src/boardgate/domain/finding.py`
  - `tests/unit/rules/test_required_layers_present.py`
  - public Finding/findings schemas
- Commands run:
  - `uv run python scripts/export_schemas.py`
  - full lock, sync, Ruff, mypy, and pytest coverage gate
- Tests:
  - Rule/domain/engine focus: 23 passed.
  - Full suite: 236 passed, 89.58% branch coverage.
- Evidence: Present/missing/ambiguous/stability/round-trip tests.
- Commit: `a734d2f feat(rule): require configured PCB layers`
- Issues created or updated: None.
- Recommended next action: Implement `drill_file_present` v1.

### 2026-07-28T17:47:40+08:00 — Codex — Rule-engine contracts and registry

- Role: primary implementation agent
- Task: Establish the semantic boundary required by all 16 deterministic
  rules.
- Context inspected:
  - `HANDOFF.md`
  - Existing Finding, identifier, Rule Profile, PCBProject, and status models
  - Rule outcome/coverage, threshold, dependency, and overall-status
    requirements in the approved plan
- Actions performed:
  - Added orthogonal PASS/FINDINGS/SKIPPED/FAILED and FULL/PARTIAL/NONE
    contracts with typed skip/failure reasons.
  - Added atomic evaluator returns that forbid Findings on any non-FINDINGS
    outcome and forbid partial Findings leaking from exceptions.
  - Added a complete v1 registry invariant, unique binding/version checks,
    dependency existence/self/cycle checks, and stable topological ordering.
  - Added disabled/dependency/exception containment while allowing independent
    later rules to continue.
  - Added conservative minimum-threshold comparison with equality-safe
    floating semantics and explicit error-band confirmation disposition.
  - Added normative overall-status precedence and strict findings.json root
    aggregation with a fabrication non-guarantee disclaimer.
  - Exported and validated the fifth public Draft 2020-12 JSON Schema.
- Files modified:
  - `src/boardgate/rules/`
  - `tests/unit/rules/test_engine.py`
  - `src/boardgate/schemas.py`
  - `schemas/v1/findings.schema.json`
- Commands run:
  - `uv run python scripts/export_schemas.py`
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/rules/test_engine.py -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Focused engine/registry/status tests: 14 passed.
  - Full suite: 231 passed, 89.54% branch coverage.
  - Lock, sync, five schema-current checks, Ruff, and mypy gates passed.
- Findings:
  - Binary pass/fail cannot represent a rule that checked only a trustworthy
    subset; outcome and coverage are now independently constrained.
  - IEEE-754 addition around exact decimal thresholds requires an equality
    guard so `0.09 + 0.01` cannot become a false confirmed violation.
- Evidence: Commands and registry/error-band/status tests above.
- Commit: `c360738 feat(rules): establish deterministic review engine`
- Issues created or updated: None.
- Remaining uncertainty: The registry contract exists, but built-in rules are
  not yet registered.
- Recommended next action: Implement `required_layers_present` v1.

### 2026-07-28T17:40:58+08:00 — Codex — Isolated parser and PCBProject assembly

- Role: primary implementation agent
- Task: Turn safely staged sources into the complete parser-independent IR.
- Context inspected:
  - `HANDOFF.md`
  - Existing ingestion, manifest, parser, layer, outline, profile, and project
    boundaries
  - Parser timeout and deterministic assembly requirements in the approved
    plan
- Actions performed:
  - Added strict parser jobs for only confirmed Gerber, Excellon, BOM
    CSV/XLSX, and placement CSV types.
  - Added fresh spawn-process execution, source-safe failure envelopes,
    bounded worker messages, timeout/terminate/kill cleanup, and strict
    parent-side model revalidation.
  - Rechecked every staged payload size and SHA-256 against the manifest
    immediately before dispatch.
  - Added stable source diagnostics for warnings, limitations, timeouts, and
    failures, with parser limitations copied into project uncertainty.
  - Assembled layers, outline, holes/slots, BOM, CPL, requirements, coordinate
    system, diagnostics, and uncertainties in manifest order.
  - Added repeatability, partial parser failure, staging mutation, timeout,
    strict-invariant, and full project round-trip tests.
  - Regenerated the public PCBProject schema with source diagnostics.
- Files modified:
  - `src/boardgate/application/parser_runner.py`
  - `src/boardgate/application/project_builder.py`
  - `src/boardgate/domain/diagnostic.py`
  - `src/boardgate/domain/project.py`
  - `tests/unit/application/test_parser_runner.py`
  - `tests/unit/application/test_project_builder.py`
  - `tests/unit/domain/test_diagnostic.py`
  - `schemas/v1/project.schema.json`
- Commands run:
  - `uv run python scripts/export_schemas.py`
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/application/test_parser_runner.py
    tests/unit/application/test_project_builder.py
    tests/unit/domain/test_diagnostic.py tests/unit/domain/test_project.py -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Focused parser/project/domain tests: 12 passed.
  - Full suite: 216 passed, 89.30% branch coverage.
  - Lock, sync, schema-current, Ruff, and mypy gates passed.
- Findings:
  - Passing the strict ParserJob through multiprocessing avoids unsafe binary
    XLSX JSON encoding while still preventing third-party objects from crossing
    the worker boundary.
  - One parser failure can be represented truthfully as uncertainty while
    preserving all independently successful normalized evidence.
- Evidence: Commands and isolation/repeatability/error tests above.
- Commit: `d297635 feat(project): isolate parsers and assemble PCB IR`
- Issues created or updated: None.
- Remaining uncertainty: Rule outcomes and readiness status are not computed
  yet.
- Recommended next action: Establish the deterministic rule-engine contracts.

### 2026-07-28T17:32:11+08:00 — Codex — Restricted XLSX BOM adapter

- Role: primary implementation agent
- Task: Safely normalize BOM XLSX without active workbook behavior.
- Context inspected:
  - `HANDOFF.md`
  - XLSX, calamine, multi-sheet, and source-evidence requirements in the
    approved plan
  - Installed python-calamine 0.8.2 typed API
- Actions performed:
  - Added complete OOXML ZIP entry indexing before parser invocation with
    encrypted/symlink/special/path/duplicate/size/ratio checks.
  - Stream-read and CRC-validated every member before calamine access.
  - Parsed restricted XML after rejecting DTD/entity declarations and blocked
    macro content types/files, external relationships/parts, and formulas.
  - Required ordinary worksheets and exact caller selection when more than
    one exists.
  - Converted only finite scalar/date/time cells into bounded deterministic
    strings and kept calamine workbook/sheet objects adapter-local.
  - Shared tabular header/column validation with CSV and preserved XLSX
    worksheet, physical row, and Excel column-label evidence.
- Files modified:
  - `src/boardgate/parsers/xlsx.py`
  - `src/boardgate/parsers/bom.py`
  - `src/boardgate/parsers/tabular.py`
  - `src/boardgate/parsers/__init__.py`
  - `tests/unit/parsers/test_xlsx.py`
  - `tests/unit/parsers/test_tabular.py`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/parsers/test_xlsx.py -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Focused XLSX tests: 12 passed.
  - Full suite: 207 passed, 89.89% branch coverage.
  - Lock, sync, Ruff, and mypy gates passed.
- Findings:
  - XLSX text line/byte spans do not exist; worksheet, row, and column labels
    are retained as the truthful source locator.
  - Calamine accepts a file-like object and context-managed close, allowing
    its objects to remain wholly inside the adapter.
- Evidence: Commands and normal/forbidden/limit/round-trip tests above.
- Commit: `bce8a24 feat(assembly): safely parse BOM workbooks`
- Issues created or updated: None.
- Remaining uncertainty: Parser timeout isolation is not connected yet.
- Recommended next action: Build isolated parser dispatch and PCBProject
  assembly.

### 2026-07-28T17:22:11+08:00 — Codex — BOM and placement CSV adapters

- Role: primary implementation agent
- Task: Normalize bounded assembly CSV inputs with source provenance.
- Context inspected:
  - `HANDOFF.md`
  - BOM, CPL, ambiguity, DNP, unit, and provenance requirements in the
    approved plan
- Actions performed:
  - Added deterministic UTF-8 CSV delimiter and header discovery with bounded
    rows, columns, and cell sizes.
  - Added strict alias resolution that rejects duplicate and conflicting
    columns instead of selecting one silently.
  - Added BOM reference grouping/range expansion, quantity consistency,
    explicit DNP retention, optional fields, and unmapped metadata.
  - Added placement coordinate-unit evidence, finite-number validation,
    inch-to-millimetre normalization, side mapping, and raw coordinates.
  - Preserved logical source, line/byte span, source row, stable object IDs,
    and parser version on each normalized record.
  - Allowed zero-quantity BOM items only when explicitly marked DNP and
    regenerated the PCBProject schema.
- Files modified:
  - `src/boardgate/parsers/tabular.py`
  - `src/boardgate/parsers/bom.py`
  - `src/boardgate/parsers/placement.py`
  - `src/boardgate/domain/component.py`
  - `tests/unit/parsers/`
  - `tests/unit/domain/test_component.py`
  - `schemas/v1/project.schema.json`
- Commands run:
  - `uv run python scripts/export_schemas.py`
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/parsers/test_tabular.py
    tests/unit/parsers/test_bom.py tests/unit/parsers/test_placement.py
    tests/unit/domain/test_component.py -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Focused assembly/domain tests: 25 passed.
  - Full suite: 195 passed, 90.75% branch coverage.
  - Lock, sync, schema-current, Ruff, and mypy gates passed.
- Findings:
  - Placement coordinate units cannot be safely inferred from bare numeric
    values; the adapter requires header/unit-column evidence or caller config.
  - BOM quantity zero is useful for retained DNP rows but unsafe without an
    explicit DNP marker.
- Evidence: Commands and positive/error/round-trip tests above.
- Commit: `f697b22 feat(assembly): parse BOM and placement CSV`
- Issues created or updated: None.
- Remaining uncertainty: XLSX source positions cannot carry text line/byte
  spans and need worksheet/cell evidence instead.
- Recommended next action: Add bounded XLSX preflight and calamine adapter.

### 2026-07-28T17:15:19+08:00 — Codex — Analytic outline reconstruction

- Role: primary implementation agent
- Task: Reconstruct trusted board material topology for Phase 4.
- Context inspected:
  - `HANDOFF.md`
  - Closure, arc-error, cutout, and ambiguity requirements in the approved plan
- Actions performed:
  - Added deterministic analytic arc approximation with a proven maximum chord
    error.
  - Added bounded endpoint clustering and graph-cycle reconstruction for
    trusted dark Line/Arc outline geometry.
  - Preserved oriented analytic segments while deriving only local Shapely
    polygons for validity and nesting.
  - Classified nested loops as cutouts and disjoint material loops as multiple
    outer contours with explicit uncertainty.
  - Propagated snap, radial, and chord approximation errors into BoardOutline.
  - Rejected open, branching, touching, unsupported, clear-polarity, and
    multi-source outline ambiguity without guessing.
  - Updated and regenerated the public PCBProject schema.
- Files modified:
  - `src/boardgate/geometry/`
  - `src/boardgate/normalization/outline.py`
  - `src/boardgate/domain/layer.py`
  - `tests/unit/geometry/`
  - `tests/unit/normalization/test_outline.py`
  - `schemas/v1/project.schema.json`
  - `pyproject.toml`
- Commands run:
  - `uv run python scripts/export_schemas.py`
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/geometry/test_arcs.py
    tests/unit/normalization/test_outline.py -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Focused geometry/outline tests: 15 passed.
  - Full suite: 170 passed, 91.08% branch coverage.
  - Lock, sync, schema-current, Ruff, and mypy gates passed.
- Findings:
  - Nested loops can be deterministically classified without treating a
    cutout as a second board.
  - Endpoint snapping contributes a measured error bound rather than altering
    geometry invisibly.
- Evidence: Commands and property/golden topology tests above.
- Commit: `854496e feat(outline): reconstruct board contours and cutouts`
- Issues created or updated: None.
- Remaining uncertainty: Multiple trusted outline source files still require
  coordinate confirmation.
- Recommended next action: Parse BOM and placement CSV with provenance.

### 2026-07-28T17:08:59+08:00 — Codex — Evidence-backed layer mapping

- Role: primary implementation agent
- Task: Normalize parsed Gerber sources into trustworthy PCBLayer roles.
- Context inspected:
  - `HANDOFF.md`
  - X2, filename, and extension mapping requirements in the approved plan
- Actions performed:
  - Added independent X2 FileFunction, filename-token, extension, and parser
    hint mapping signals.
  - Aggregated agreeing signals while retaining each evidence string.
  - Kept strong conflicts and weak/absent evidence as UNKNOWN with explicit
    LAYER_MAPPING_UNCERTAIN records.
  - Preserved SameCoordinates separately for later alignment checks.
  - Added stable layer IDs and copied only BoardGate parser primitives/bounds.
  - Updated and regenerated the public PCBProject schema.
- Files modified:
  - `src/boardgate/normalization/`
  - `src/boardgate/domain/layer.py`
  - `tests/unit/normalization/`
  - `schemas/v1/project.schema.json`
- Commands run:
  - `uv run python scripts/export_schemas.py`
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/normalization/test_layers.py -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Layer normalization tests: 19 passed.
  - Full suite: 155 passed, 91.37% branch coverage.
  - Lock, sync, schema-current, Ruff, and mypy gates passed.
- Findings:
  - X2 and conventional filename evidence can disagree on renamed exports;
    BoardGate now refuses to pick either role in that case.
  - SameCoordinates is retained but intentionally does not determine role.
- Evidence: Commands and mapping tests above.
- Commit: `3ab4e9b feat(layers): preserve mapping evidence and conflicts`
- Issues created or updated: None.
- Remaining uncertainty: Board outline topology is not reconstructed yet.
- Recommended next action: Reconstruct analytic outlines and nested cutouts.

### 2026-07-28T17:05:40+08:00 — Codex — Gerber analytic adapter

- Role: primary implementation agent
- Task: Complete the Phase 3 Gerber adapter boundary.
- Context inspected:
  - `HANDOFF.md`
  - Gerbonara 1.6.3 parser, aperture, object, region, warning, and X2 behavior
  - Gerber scope in the approved plan
- Actions performed:
  - Added byte-accurate Gerber command tokenization and object/region spans.
  - Added metric/inch normalization for Line, Arc, Flash, and analytic Region
    segments.
  - Added circle, rectangle, obround, polygon, and bounded macro aperture
    normalization, including holes, rotation, and polygon vertex count.
  - Preserved dark/clear polarity, aperture numbers, X2 file attributes,
    source units, raw commands/coordinates, and generator/layer hints.
  - Rejected include commands and made ignored/unknown statements and macro
    rule exclusions explicit limitations.
  - Updated and regenerated the public PCBProject schema.
- Files modified:
  - `src/boardgate/parsers/gerber.py`
  - `src/boardgate/parsers/gerber_scanner.py`
  - `src/boardgate/domain/layer.py`
  - `tests/fixtures/parser/gerber/`
  - `tests/unit/parsers/`
  - `tests/unit/domain/test_region.py`
  - `schemas/v1/project.schema.json`
- Commands run:
  - Local Gerbonara API and fixture behavior probes.
  - `uv run python scripts/export_schemas.py`
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/parsers/test_gerber.py
    tests/unit/parsers/test_gerber_scanner.py
    tests/unit/domain/test_region.py -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Focused Gerber/domain tests: 12 passed.
  - Full suite: 136 passed, 91.30% branch coverage.
  - Lock, sync, schema-current, Ruff, and mypy gates passed.
- Findings:
  - Gerbonara preserves X2 file attributes separately from its optional
    filename-derived layer hints.
  - Macro aperture bounding geometry is available, but standard-aperture DFM
    coverage must remain excluded and explicit.
- Evidence: Commands, installed-source references, and original golden fixtures.
- Commit: `02899e2 feat(parser): normalize Gerber analytic primitives`
- Issues created or updated: ISSUE-001 Gerber scanner work completed.
- Remaining uncertainty: Step-repeat object expansion can make source mapping
  partial and will be reported as such.
- Recommended next action: Normalize evidence-backed PCB layer mappings.

### 2026-07-28T16:58:22+08:00 — Codex — Excellon adapter

- Role: primary implementation agent
- Task: Implement the first Phase 3 parser adapter and provenance scanner.
- Context inspected:
  - `HANDOFF.md`
  - Gerbonara 1.6.3 installed source and runtime object behavior
  - Excellon scope in the approved plan
- Actions performed:
  - Added strict parser diagnostics and source-safe parser errors.
  - Added Gerbonara-backed metric/inch normalization for round drill hits.
  - Added separate analytic linear and arc routed-slot models.
  - Preserved coordinate format, zero suppression, notation, generator hints,
    raw commands, raw coordinates, tool codes, and source spans.
  - Converted ignored CAM commands and incremental notation to explicit
    limitations; classified unknown commands separately from malformed data.
  - Updated and regenerated the public PCBProject schema.
- Files modified:
  - `src/boardgate/parsers/`
  - `src/boardgate/domain/drill.py`
  - `tests/fixtures/parser/excellon/`
  - `tests/unit/parsers/`
  - `tests/unit/domain/test_drill.py`
  - `schemas/v1/project.schema.json`
- Commands run:
  - Local Gerbonara API and fixture behavior probes.
  - `uv run python scripts/export_schemas.py`
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/parsers tests/unit/domain/test_drill.py -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Focused parser/domain tests: 13 passed.
  - Full suite: 124 passed, 91.04% branch coverage.
  - Lock, sync, schema-current, Ruff, and mypy gates passed.
- Findings:
  - Gerbonara objects do not expose source spans; scanner alignment is explicit.
  - Gerbonara 1.6.3 accepts but does not apply the documented Excellon
    `plated=` hint; the adapter handles confirmed hints conservatively.
- Evidence: Commands, installed-source references, and original golden fixtures.
- Commit: `d565c0b feat(parser): normalize Excellon drills and slots`
- Issues created or updated: ISSUE-001 resolved; ISSUE-002 created.
- Remaining uncertainty: Parser execution is not timeout-isolated.
- Recommended next action: Add the Gerber analytic-primitive adapter.

### 2026-07-28T16:51:15+08:00 — Codex — Atomic manifest CLI slice

- Role: primary implementation agent
- Task: Expose the first Phase 2 vertical slice through the public CLI.
- Context inspected:
  - `HANDOFF.md`
  - CLI, exit-code, and overwrite contract in the approved plan
- Actions performed:
  - Added the complete inspect command shape and explicit Rule Profile
    validation.
  - Added output/input overlap rejection and exit code 2 for safe user/config
    errors.
  - Added same-parent staging and backup replacement with restoration on
    publish failure.
  - Added required-artifact and canonical model round-trip validation before
    publishing `manifest.json`.
  - Added directory, ZIP, separate-file, overwrite, restoration, schema, and
    stable-byte integration tests.
- Files modified:
  - `src/boardgate/cli.py`
  - `src/boardgate/application/`
  - `tests/unit/application/`
  - `tests/integration/`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/application
    tests/integration/test_inspect_manifest.py tests/unit/test_cli.py -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Focused tests: 14 passed.
  - Full suite: 111 passed, 90.85% branch coverage.
  - Lock, sync, Ruff, and mypy gates passed.
- Findings:
  - Failed staged validation never moves the existing output.
  - A failure after backup creation restores the prior output directory.
- Evidence: Commands and results above.
- Commit: `1494432 feat(cli): emit validated project manifests`
- Issues created or updated: None.
- Remaining uncertainty: Only `manifest.json` is emitted until parsing and the
  complete review pipeline are connected.
- Recommended next action: Implement Excellon parsing and command spans.

### 2026-07-28T16:47:04+08:00 — Codex — Stable project manifest

- Role: primary implementation agent
- Task: Complete deterministic Phase 2 classification and manifest generation.
- Context inspected:
  - `HANDOFF.md`
  - Manifest and classification contracts in `IMPLEMENT_PCB_AGENT.md`
- Actions performed:
  - Added bounded streaming SHA-256 hashing and stable source/project IDs.
  - Added separate extension, filename, Gerber/X2, Excellon, CSV-header,
    OOXML-container, and rule-profile signals.
  - Preserved all candidate evidence and emitted FILE_TYPE_UNKNOWN uncertainty
    for conflict or insufficient evidence.
  - Added byte-stable manifest serialization and Draft 2020-12 validation.
  - Kept `.xlsx` inputs intact rather than treating their ZIP container as a
    project archive.
- Files modified:
  - `src/boardgate/domain/identifiers.py`
  - `src/boardgate/ingestion/`
  - `tests/unit/ingestion/`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/ingestion
    tests/unit/domain/test_identifiers.py -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Focused tests: 46 passed.
  - Full suite: 97 passed, 90.89% branch coverage.
  - Lock, sync, Ruff, and mypy gates passed.
- Findings:
  - Strong, conflicting type signals intentionally resolve to UNKNOWN.
  - Directory, ZIP, and reversed explicit-file inputs serialize identically.
- Evidence: Commands and results above.
- Commit: `d2198d3 feat(ingestion): classify files and build manifests`
- Issues created or updated: ISSUE-003 was not required; ambiguous `.txt`
  drill inputs are resolved only when Excellon content evidence is strong.
- Remaining uncertainty: The public inspect command does not yet emit a
  manifest.
- Recommended next action: Add atomic CLI manifest output.

### 2026-07-28T16:42:19+08:00 — Codex — Safe project input staging

- Role: primary implementation agent
- Task: Implement the bounded, common ingestion boundary for Phase 2.
- Context inspected:
  - `HANDOFF.md`
  - ZIP and input security requirements in the approved plan
- Actions performed:
  - Added shared file-count, archive-size, file-size, expanded-size, and
    compression-ratio limits.
  - Added conservative Unicode/POSIX normalization and cross-platform
    collision keys.
  - Added ZIP central-directory preflight and bounded streaming extraction.
  - Rejected traversal, absolute/drive/backslash paths, symlinks, special
    files, encrypted entries, nested ZIPs, duplicate paths, and file/directory
    tree conflicts.
  - Added context-bounded staging for directories, ZIPs, and explicit files
    with cleanup after success and failure.
- Files modified:
  - `src/boardgate/ingestion/`
  - `tests/unit/ingestion/`
  - `pyproject.toml`
- Commands run:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/ingestion -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Ingestion tests: 29 passed.
  - Full suite: 82 passed, 90.38% branch coverage.
  - Lock, sync, Ruff, and mypy gates passed.
- Findings:
  - Metadata quotas are checked before expansion and actual streamed bytes are
    compared with declared sizes.
  - Logical paths are collision-checked across every supplied input.
- Evidence: Commands and results above.
- Commit: `ab7050e feat(ingestion): safely stage PCB project inputs`
- Issues created or updated: None.
- Remaining uncertainty: Content classification has not been implemented.
- Recommended next action: Add stable hashing, classification, and manifests.

### 2026-07-28T16:37:18+08:00 — Codex — Manufacturing Rule Profile

- Role: primary implementation agent
- Task: Complete the Phase 1 manufacturing configuration boundary.
- Context inspected:
  - `HANDOFF.md`
  - Rule-profile and security requirements in `IMPLEMENT_PCB_AGENT.md`
- Actions performed:
  - Added a strict Rule Profile 1.0 model with all 16 registered rule settings.
  - Added generic two-layer defaults with explicit thresholds and tolerances.
  - Added bounded, duplicate-key-safe JSON and restricted YAML loading.
  - Rejected YAML references, tags, multiple documents, legacy implicit
    booleans, non-finite JSON, unknown fields, and oversized profiles.
  - Exported deterministic Draft 2020-12 schemas for RuleProfile, Manifest,
    PCBProject, and Finding.
- Files modified:
  - `src/boardgate/config/`
  - `src/boardgate/schemas.py`
  - `rules/default.yaml`
  - `schemas/v1/`
  - `scripts/export_schemas.py`
  - `tests/unit/config/`
  - `pyproject.toml`
- Commands run:
  - `uv run python scripts/export_schemas.py`
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Full suite: 53 passed, 91.03% branch coverage.
  - Lock, sync, Ruff, and mypy gates passed.
- Findings:
  - YAML `true`/`false` remain supported while YAML 1.1 words such as `yes`
    remain strings and therefore fail strict boolean validation.
  - Error messages use only the profile basename.
- Evidence: Commands and results above; four current schemas validate as Draft
  2020-12.
- Commit: `9a9e285 feat(config): validate manufacturing rule profiles`
- Issues created or updated: None.
- Remaining uncertainty: Safe archive expansion is not implemented.
- Recommended next action: Implement bounded discovery and ZIP extraction.

### 2026-07-28T16:32:11+08:00 — Codex — PCB project and finding contracts

- Role: primary implementation agent
- Task: Complete the parser-independent Phase 1 project and finding slice.
- Context inspected:
  - `HANDOFF.md`
  - Domain and identifier requirements in `IMPLEMENT_PCB_AGENT.md`
- Actions performed:
  - Added source-manifest and classification-evidence contracts.
  - Added typed PCB layer primitives, apertures, drill hits/slots, component
    placements, BOM entries, and board outlines.
  - Added PCBProject requirements, Findings, measurements, evidence, statuses,
    severities, and risk modes.
  - Added canonical stable source, project, object, and finding identifiers.
- Files modified:
  - `src/boardgate/domain/`
  - `tests/unit/domain/`
- Commands run:
  - `uv run ruff format .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/domain -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Domain tests: 31 passed.
  - Full suite: 32 passed, 90.31% branch coverage.
  - Ruff and mypy passed.
- Findings:
  - Third-party parser and Shapely objects cannot enter the serialized
    contracts.
  - Finding confirmation state is validated independently from severity.
- Evidence: Commands and results above.
- Commit: `ce6bf2b feat(domain): add PCB project and finding schemas`
- Issues created or updated: None.
- Remaining uncertainty: Rule Profile configuration is not yet represented.
- Recommended next action: Add the strict Rule Profile loader and schemas.

### 2026-07-28T16:26:58+08:00 — Codex — Geometry and provenance models

- Role: primary implementation agent
- Task: Implement the first Phase 1 domain-model slice.
- Context inspected:
  - `HANDOFF.md`
  - Phase 1 requirements in `IMPLEMENT_PCB_AGENT.md`
- Actions performed:
  - Added strict/frozen Pydantic base models and schema version `1.0`.
  - Added canonical millimetre geometry and coordinate-system models.
  - Added optional, range-validated source spans and provenance.
  - Added deterministic canonical JSON serialization.
- Files modified:
  - `src/boardgate/domain/`
  - `tests/unit/domain/`
- Commands run:
  - `uv run ruff format .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run pytest tests/unit/domain -q`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
- Tests:
  - Domain tests: 22 passed.
  - Full suite: 23 passed, 100% branch coverage.
  - Ruff and mypy passed.
- Findings:
  - Persisted coordinates round to six decimals while in-memory calculations
    retain their original double precision.
- Evidence: Commands and results above.
- Commit: `6e5907b feat(domain): add geometry and provenance models`
- Issues created or updated: None.
- Remaining uncertainty: PCB project and finding IDs are not implemented yet.
- Recommended next action: Add PCBProject, Finding, RiskMode, and stable IDs.

### 2026-07-28T16:24:03+08:00 — Codex — Initial repository baseline

- Role: primary implementation agent
- Task: Create the public repository and establish the collaboration baseline.
- Context inspected:
  - `BOOTSTRAP.md`
  - `IMPLEMENT_PCB_AGENT.md`
  - Local directory and Git/GitHub state
- Actions performed:
  - Created `MattSureham/BoardGate` as a public GitHub repository.
  - Initialized local `main`, repository-local commit identity, and `origin`.
  - Added the collaboration protocol, bilingual README, Apache-2.0 license,
    architecture/ADR, dependency notices, Python package, CI, and smoke test.
  - Installed Python 3.12.13 with Homebrew after uv's managed-Python download
    stalled, then resolved and installed the locked project dependencies.
- Files modified:
  - Existing specification files added unchanged to Git tracking.
  - Repository documentation and configuration.
  - `src/boardgate` CLI baseline.
  - `tests/unit/test_cli.py`.
- Commands run:
  - `gh repo create MattSureham/BoardGate --public ...`
  - `gh repo view MattSureham/BoardGate --json ...`
  - `git init -b main`
  - `brew install python@3.12`
  - `uv lock`
  - `uv sync --locked --all-groups`
- Tests:
  - `uv run ruff format --check .` — passed.
  - `uv run ruff check .` — passed.
  - `uv run mypy src tests` — passed.
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85 -q`
    — 1 passed, 100% coverage.
- Findings:
  - The source directory initially contained only the two specification files.
- Evidence:
  - GitHub returned `visibility: PUBLIC`.
  - Remote URL is `https://github.com/MattSureham/BoardGate`.
  - Python runtime is CPython 3.12.13.
  - `uv.lock` resolves 50 packages.
- Commit: `e5b9c63 docs: establish PCB agent implementation baseline`
- Issues created or updated: ISSUE-001
- Remaining uncertainty: Gerbonara source-span behavior remains unverified.
- Recommended next action: Implement strict geometry and provenance models.

## Archived Summary

No activity has been archived. When this document reaches roughly 800–1200
lines, compress closed older activity here while preserving architectural
decisions, unresolved issues, rejected approaches, failed attempts, and
evidence references. Unresolved issues must remain in Active Issues.
