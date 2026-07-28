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

- Last updated: `2026-07-28T18:33:33+08:00`
- Repository: `[CONFIRMED] https://github.com/MattSureham/BoardGate`
- Visibility: `[CONFIRMED] PUBLIC`
- Branch: `[CONFIRMED] main`
- HEAD: `[CONFIRMED] ed56bdd feat(rule): measure supported annular rings`
- Remote sync: `[CONFIRMED] origin/main remains at d297635; later local
  commits are pending a normal push because the configured proxy aborts the
  GitHub CONNECT request.`
- Phase: `[CONFIRMED] Phase 6–8 in progress — deterministic rule
  implementation`
- Entry point: `[CONFIRMED] uv run pcb-review inspect INPUT... --rules
  rules/default.yaml --output OUTPUT`
- Implemented capabilities:
  - `[CONFIRMED] Installable Python package and versioned CLI entry point.`
  - `[CONFIRMED] Locked Python 3.12 development environment and CI gates.`
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
  - `[CONFIRMED] Strict findings.json root model aggregates ordered
    RuleResults, unique Findings, risk modes, profile identity, review status,
    and the non-guarantee disclaimer.`
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
  silkscreen_over_exposed_pad v1.`
- Verification:
  - `[CONFIRMED] gh repo view reported PUBLIC visibility.`
  - `[CONFIRMED] uv lock --check resolved 50 packages.`
  - `[CONFIRMED] uv run ruff format --check . passed.`
  - `[CONFIRMED] uv run ruff check . passed.`
  - `[CONFIRMED] uv run mypy src tests passed (105 source files).`
  - `[CONFIRMED] uv run pytest --cov=boardgate --cov-branch
    --cov-fail-under=85 passed: 320 tests, 90.06% coverage.`
- Known limitations:
  - `[CONFIRMED] The current CLI slice still emits only manifest.json;
    the project-assembly service is not yet invoked there, and rule execution,
    complete artifact diagnostics, rendering, and review orchestration remain
    unimplemented.`
- Working tree: `[CONFIRMED] Verified silkscreen_over_exposed_pad rule slice is
  pending commit.`

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

### ISSUE-003 — GitHub HTTPS push is temporarily blocked by proxy

- Status: OPEN
- Severity: medium
- Owner: unassigned
- State label: `[CONFIRMED]`
- Context: Local atomic commits after `d297635` must be published to
  `origin/main`.
- Evidence: Repeated normal `git push origin main` attempts return
  `Proxy CONNECT aborted`; the local remote-tracking ref remains `d297635`.
- Suspected cause: The execution environment's configured HTTPS proxy is
  intermittently refusing the GitHub tunnel.
- Attempted approaches: Retried normal non-force pushes after separate rule
  commits.
- Current resolution state: Preserve the linear local history and retry a
  normal push after subsequent verified commits; do not force, rebase, or
  rewrite either history.
- Remaining work: Push local `main`, then verify remote HEAD and Actions.
- Relevant files: `.git/config`
- Blocking: No for local implementation; yes for remote synchronization.

## Next Action

Implement `minimum_solder_mask_dam` v1.

Start with:

- `src/boardgate/rules/surface_rules.py`
- `src/boardgate/rules/derived_geometry.py`
- `src/boardgate/rules/builtin.py`
- `tests/unit/rules/test_minimum_solder_mask_dam.py`

Acceptance criteria:

1. On each trusted solder-mask layer, measure true distances only between
   distinct final opening components; never compare top openings to bottom.
2. Treat one connected/gang opening as one component so it is not reported as
   a fabricated zero-width dam.
3. Equality passes; compositing and approximation error distinguish confirmed
   violations from PARTIAL confirmations, while uncertain polarity or
   unsupported geometry cannot become a numeric claim.
4. Pass/violation/equality/error-band/gang-opening/polarity/same-side,
   evidence, STRtree equivalence, stability, and round-trip tests pass before
   the separate commit.

## Recent Activity

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
- Commit: PENDING (this silkscreen_over_exposed_pad commit)
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
