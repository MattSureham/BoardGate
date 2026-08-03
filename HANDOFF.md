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

- Last updated: `2026-08-03T13:30:00+08:00`
- Repository: `[CONFIRMED] https://github.com/MattSureham/BoardGate`
- Visibility: `[CONFIRMED] PUBLIC`
- Branch: `[CONFIRMED] main`
- HEAD: `[CONFIRMED] The branch-tip HANDOFF commit containing this state
  follows local generation contracts/implementation/documentation commits
  4bd39bb, ec9ff16, and d8aa07a, which follow authoring commits a935d58,
  dea742d, f3ddd6e, 61ea33a, and 85d1599.`
- Remote sync: `[CONFIRMED] origin/main and origin/HEAD remain at recovery
  baseline fec6795. The branch-tip HANDOFF commit is local and follows eight
  unpushed atomic commits; no force push, rebase, or remote-history rewrite
  occurred.`
- Phase: `[CONFIRMED] Phase 9 end-to-end review pipeline and Phase 10
  deterministic agent orchestration are complete; the Phase 11 offline
  static Viewer is complete through bundle admission, project/status
  summary, validated SVG exploration, validated Markdown report rendering,
  and cross-panel Finding navigation. Authoring Phases A-D now have an
  accepted separate-subsystem architecture, strict public contracts, one
  deterministic Excellon modification operation, one bounded deterministic
  two-layer coupon generator, and independent review validation for both.`
- Entry points: `[CONFIRMED] uv run pcb-review inspect INPUT... --rules
  rules/default.yaml --output REVIEW_OUTPUT; uv run pcb-review modify
  INPUT... --request CHANGE.json --rules rules/default.yaml --output
  REVISION_OUTPUT; uv run pcb-review generate --request COUPON.json --rules
  rules/default.yaml --output GENERATION_OUTPUT`
- Implemented capabilities:
  - `[CONFIRMED] Installable Python package and versioned CLI entry point.`
  - `[CONFIRMED] Locked Python 3.12 development environment; Ubuntu CI
    asserts and tests the actual Python 3.12 and 3.14 interpreters, while
    Ubuntu, macOS, and Windows run a complete Python 3.12 CLI review smoke.`
  - `[CONFIRMED] Repository collaboration protocol and architecture boundary.`
  - `[CONFIRMED] PROJECT_SPEC.md now defines review, modification, and
    generation as separate capabilities; accepted ADR 0007 keeps the
    immutable review pipeline and read-only Viewer unchanged while placing
    deterministic authoring in a sibling subsystem.`
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
  - `[CONFIRMED] Restricted YAML/JSON loader and eight checked-in Draft
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
  - `[CONFIRMED] ADR 0006 selects a separately distributed, offline,
    read-only static Viewer as the Phase 11 transport boundary. It consumes
    only an explicitly user-selected, validated six-artifact bundle in browser
    memory and cannot upload, persist, trigger review, or mutate Evidence.`
  - `[CONFIRMED] viewer/boardgate-viewer.html is a separately distributed,
    deterministic single-file application that opens through file:// in
    Chromium, Firefox, and WebKit; it is not a seventh review artifact.`
  - `[CONFIRMED] Viewer resource policy 1.0 applies inclusive per-artifact,
    384 MiB total, JSON depth/entry, SVG element/attribute, JSONL, and
    60-second fresh-worker limits before displaying any engineering summary.`
  - `[CONFIRMED] Viewer admission requires the exact case-sensitive six-path
    inventory and validates fatal UTF-8, Python-compatible canonical JSON,
    strict standalone Draft 2020-12 Schemas, model semantics, stable IDs,
    cross-artifact identities, report metadata, namespace-correct passive
    SVG/XML, and the ordered run log. SVG admission permits only the static
    BoardGate renderer vocabulary plus unique local gradient paint servers;
    animation, authored style, foreign namespaces, unsupported vocabulary,
    and external or non-paint references fail closed with stable safe codes
    and no partial project conclusion.`
  - `[CONFIRMED] Each directory selection clears prior evidence, snapshots
    read-only bytes, terminates any prior Worker, and transfers bytes to a
    fresh validation Worker. Timeout, replacement, crash, and malformed
    responses terminate/revoke the Worker transport without storage, network,
    review execution, or bundle writes.`
  - `[CONFIRMED] The Phase 11 UI uses createElement/textContent to display
    the admitted project/profile identity, original overall status, evidence
    counts, risk modes, disclaimer, and safe ANALYSIS_FAILED diagnostics.`
  - `[CONFIRMED] Admission additionally extracts pcb-layer-%04d layer groups
    and classifies Finding markers by spatial/non-spatial section, rejects
    malformed or duplicate groups (SVG_LAYER_GROUP_INVALID), and cross-checks
    group layer ID/role/side against project.json layers
    (SVG_LAYER_MISMATCH).`
  - `[CONFIRMED] After admission the viewer imports preview.svg into a
    presentation-only DOM copy via DOMParser/importNode, with a main-thread
    defense that rejects parser errors, a non-SVG root, the wrong SVG
    namespace, or project-ID mismatch. Layer and Finding interactions change
    only trusted CSS visibility/class state on that copy; geometry-defining
    attributes and selected Bundle bytes remain unchanged, and review
    evidence is never re-evaluated.`
  - `[CONFIRMED] Viewer resource policy 1.0 additionally bounds report.md at
    an inclusive 200,000 lines (ARTIFACT_RESOURCE_LIMIT on N+1) before
    rendering.`
  - `[CONFIRMED] After admission the viewer renders report.md through a
    line-oriented tokenizer limited to the deterministic BoardGate report
    subset (ATX headings up to level four, paragraphs, two-space nested
    lists, **bold** inline segments, composer backslash escapes reversed);
    unknown structures degrade to literal paragraphs, HTML comment metadata
    is not displayed, and all DOM is built with createElement/textContent —
    no Markdown library and no innerHTML — so report content cannot execute
    active content.`
  - `[CONFIRMED] Finding-ID headings in the rendered report are activatable
    buttons; one shared controller selection state focuses the same preview
    marker whether a Finding is activated from the report or the preview
    Finding list, keeps aria-pressed in sync across both button sets, and
    scrolls the counterpart into view. Selection remains CSS-only on the
    validated in-memory copy.`
  - `[CONFIRMED] ModificationRequest/ModificationResult 1.0 are strict,
    explicit-version public contracts with checked-in Draft 2020-12 Schemas,
    complete ingestion-equivalent logical-path safety, full request and
    structured-operation digests, stable wording-independent revision IDs,
    fixed non-guarantee text, and cross-evidence validators.`
  - `[CONFIRMED] The complete authoring operation registry resolves exact
    kind/version pairs without fallback. Its first executor implements only
    set_excellon_tool_diameter 1.0 for a confirmed metric/absolute,
    warning-free Excellon source, using one same-width decimal-token patch,
    isolated before/after parsing, protected drill/slot comparison, and
    exact token-span evidence.`
  - `[CONFIRMED] ModificationService safely rebuilds and binds the base
    project, rejects control/non-design inputs and stale or unsupported
    requests, emits a separate design/evidence/validation workspace, invokes
    the unchanged ReviewService on emitted bytes, validates the exact outer
    inventory and nested six-artifact bundle, and publishes atomically.
    ANALYSIS_FAILED publishes no revision; completed blocker evidence is
    retained with exit 1 and no readiness reinterpretation.`
  - `[CONFIRMED] The original drill_too_small fixture proves the base review
    has exactly one minimum_drill_diameter blocker at 0.100 mm; the explicit
    T01 0.100 -> 0.300 mm revision changes only the intended token, produces
    stable request/result/design/first-five validation bytes, and receives a
    fresh READY_FOR_REVIEW result with that rule PASS/FULL and no new
    Findings.`
  - `[CONFIRMED] GenerationRequest/GenerationResult 1.0 are strict,
    explicit-version public contracts with checked-in Draft 2020-12 Schemas,
    bounded duplicate-safe JSON admission, full request and prose-independent
    operation digests, stable gen- IDs, sorted unique payload evidence,
    pinned non-guarantee disclaimer text, and cross-evidence validators. The
    generate_two_layer_coupon 1.0 operation bounds one metric rectangular
    two-layer coupon to 1.0-500.0 mm dimensions, explicit plated round holes
    with explicit pads, and explicit straight round-aperture traces at the
    exact 0.000001 mm emission quantum with inclusive 1,024-hole and
    4,096-trace limits; pad containment, pairwise drill overlap, and trace
    containment are proved in exact integer nanometres.`
  - `[CONFIRMED] The complete generation registry resolves exact kind/version
    pairs without fallback. Its sole executor emits X2 top/bottom copper, a
    rectangular outline, and a plated Excellon drill payload (each capped at
    an inclusive 1 MiB), reparses all four with the unchanged bounded
    parsers, and proves the exact requested rectangle, pads, traces, drills,
    and plating before returning applied-generation evidence.`
  - `[CONFIRMED] GenerationService shares the extracted revision-workspace
    helpers with ModificationService, runs the unchanged ReviewService on the
    emitted design/ bytes, binds canonical request/result evidence to the
    nested exact six-artifact validation bundle, and publishes atomically
    after full workspace validation. pcb-review generate maps request and
    admission failures to exit 2, capability/parser/validation failures to
    exit 3 with no publication, and completed blocker reviews to truthful
    publication with exit 1. CLI and service produce byte-identical
    design/evidence bytes and identical deterministic validation artifacts.`
- Supported inputs: `[CONFIRMED] Directories, ZIP archives, and one or more
  regular files; Gerber, Excellon, BOM/placement CSV, BOM XLSX, rule profiles,
  and unknown files receive evidence-backed manifest classifications.
  Excellon round hits/routed slots and Gerber analytic primitives are
  normalized to millimetres. The v1 modification path is deliberately
  narrower: every project member must be a confirmed fabrication/assembly
  payload, and request/profile control files must remain outside inputs.`
- Implemented rules: `[CONFIRMED] required_layers_present and
  drill_file_present, board_outline_present, board_outline_closed, and
  multiple_outline_regions, gerber_drill_coordinate_alignment, and
  minimum_trace_width, minimum_copper_spacing, minimum_copper_to_edge, and
  minimum_drill_diameter, minimum_annular_ring, and
  silkscreen_over_exposed_pad, minimum_solder_mask_dam, and
  bom_placement_reference_match, duplicate_reference_designator, and
  placement_outside_board_outline v1 (16/16 registered rules).`
- Verification:
  - `[CONFIRMED] Generation implementation gates on 2026-08-03 passed on the
    full tree: Ruff format/check (167 files), mypy (167 source files), and
    the complete Python 3.12 suite with 726 tests at 89.56% branch coverage
    including checked-in Schema currency. A two-run CLI smoke of the
    documented two-hole/two-trace coupon produced the same gen-/prj- IDs,
    READY_FOR_REVIEW validation, and byte-identical design/evidence
    artifacts; only the nested validation logs/run.jsonl differed by
    run ID, timestamps, and elapsed milliseconds, as contracted.`
  - `[CONFIRMED] Authoring implementation gates on 2026-08-03 passed:
    uv lock --check; locked all-group sync; checked-in Schema export/diff;
    Ruff format/check (174 files); mypy (156 source files); and the complete
    Python 3.12 suite with 655 tests at 89.59% branch coverage. The same 655
    tests passed under local CPython 3.14.4; the default environment was then
    restored to Python 3.12.13.`
  - `[CONFIRMED] A clean Viewer npm install reported zero vulnerabilities;
    Biome, TypeScript, 165-test Vitest coverage with one opt-in skip (92.84%
    statements, 87.54% branches, 98.65% functions, 92.74% lines), and the
    deterministic standalone build check passed after the two authoring
    Schemas were added. The Viewer still consumes exactly the original six
    review artifacts.`
  - `[CONFIRMED] Local file:// Playwright regression passed all 36 tests in
    Chromium, Firefox, and WebKit. ISSUE-008 did not reproduce locally and
    no Viewer behavior or test deadline changed.`
  - `[CONFIRMED] The first Viewer coverage attempt was run accidentally
    against the temporary Python 3.14 environment and its Python-oracle setup
    crossed the existing 10-second hook at 10.428 s. Restoring the declared
    Python 3.12 environment made the unchanged suite pass in 3.96 s; this was
    treated as environment evidence, not a product or ISSUE-010 regression.`
  - `[CONFIRMED] gh repo view reported PUBLIC visibility.`
  - `[CONFIRMED] uv lock --check resolved 50 packages.`
  - `[CONFIRMED] uv run ruff format --check . passed (158 files).`
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
  - `[CONFIRMED] GitHub Actions run 30523736566 succeeded at baseline
    17445dd before ADR 0006; the public repository and default main branch
    were independently rechecked before this documentation-only change.`
  - `[CONFIRMED] Independent Claude verification on 2026-07-30 at 076c6ed:
    commit 076c6ed touches only HANDOFF.md and docs/adr/0006-review-transport.md
    (no source, dependency, workflow, or Schema changes); ADR 0006 follows the
    ADR 0001–0005 format and explains why the static viewer cannot mutate
    review evidence; Actions run 30527646931 passed all six jobs; HEAD ==
    origin/main == origin/HEAD; Ruff format/check passed, checked-in Schemas
    are current, and the full suite passed 559 tests.`
  - `[CONFIRMED] Viewer local gates at implementation parent 9fcf6b2 passed:
    npm ci reported zero vulnerabilities; Biome format/lint and TypeScript
    passed; Vitest passed 118 tests with one opt-in private-scale test skipped
    and 92.14% statements, 87.01% branches, 97.69% functions, and 92.02%
    lines; two consecutive standalone builds were byte-identical with
    matching CSP hashes.`
  - `[CONFIRMED] Playwright file:// E2E passed 12 tests across Chromium,
    Firefox, and WebKit, including zero network/storage/service-worker use,
    unchanged bundle bytes, neutral replacement failure, and Worker
    terminate/revoke behavior on replacement and deadline.`
  - `[CONFIRMED] The untracked approximately 225.6 MiB private Bundle was
    admitted sequentially by the final standalone build in Chromium,
    Firefox, and WebKit in 5.869 s, 7.483 s, and 4.894 s. All engines produced
    the same original status and summary SHA-256 prefix 77a1ca0ef67409a9
    without remote requests or console errors; neither input nor output was
    added to the repository.`
  - `[CONFIRMED] GitHub Actions run 30553112414 succeeded at implementation
    parent 9fcf6b2 for all eight jobs: Viewer quality/parity, three-engine
    file:// E2E, root quality, Python 3.12/3.14 tests, and Ubuntu/macOS/Windows
    complete CLI smokes.`
  - `[CONFIRMED] Independent Claude verification on 2026-07-31 at 9ab9d2a:
    Actions run 30553535887 passed all eight jobs and HEAD == origin/main ==
    origin/HEAD; Python gates passed (559 tests, 89.69% branch coverage,
    Ruff, schemas current); Vitest passed 118 tests with one opt-in
    private-scale skip at 87.01% branch coverage inside the configured
    thresholds; the deterministic build check passed; Playwright passed 12/12
    across Chromium, Firefox, and WebKit after installing the missing local
    chromium-headless-shell (environment gap, not a code failure); the
    tracked boardgate-viewer.html carries a strict hash-pinned CSP with
    connect-src 'none'; and a Claude-driven Chromium smoke admitted the real
    private review bundle at
    /Users/matthew/Projects/testruns/PCB/1-verify.review-output, displayed
    the correct project ID and NOT_READY_FOR_FABRICATION summary with zero
    remote requests and zero console errors.`
  - `[CONFIRMED] Claude implementation gates on 2026-07-31 for the validated
    SVG exploration slice (31ed334): Biome check and TypeScript passed;
    Vitest passed 124 tests with one opt-in private-scale skip at 92.33%
    statements, 87.15% branches, 98.55% functions, and 92.22% lines, inside
    the configured thresholds; the deterministic build check passed with
    matching CSP hashes; Playwright passed 24/24 across Chromium, Firefox,
    and WebKit including four new tests proving layer toggles leave every
    path geometry attribute and bundle digest unchanged with zero remote
    requests, spatial Finding focus moves between markers, legend Findings
    focus non-spatial markers, and clean reviews render an empty Finding
    list; Python gates passed (559 tests, 89.69% branch coverage, Ruff
    format/check, mypy).`
  - `[CONFIRMED] GitHub Actions run 30598805829 for commits 31ed334+a3a003b
    initially failed viewer-browsers on one WebKit test, then concluded
    success after a targeted re-run of the failed job; recorded as ISSUE-008.`
  - `[CONFIRMED] Claude implementation gates on 2026-08-03 for the validated
    Markdown report rendering slice (2149f2d): Biome check and TypeScript
    passed; Vitest passed 132 tests with one opt-in private-scale skip at
    92.66% statements, 87.43% branches, 98.60% functions, and 92.55% lines,
    inside the configured thresholds; the deterministic build check passed;
    Playwright passed 27/27 across Chromium, Firefox, and WebKit including a
    new test proving the rendered report carries Finding IDs and bold status
    text, contains no script/img/iframe/object/embed/a/form/input/video/audio
    elements, hides HTML comment metadata, and leaves bundle digests and
    remote-request counts unchanged; Python gates passed (559 tests, 89.69%
    branch coverage, Ruff check).`
  - `[CONFIRMED] GitHub Actions run 30759509309 succeeded at 1c80e61 for all
    jobs, including viewer-quality and the three-engine viewer-browsers E2E.`
  - `[CONFIRMED] GitHub Actions run 30759616576 succeeded at 01278d3
    (documentation-only tip).`
  - `[CONFIRMED] Claude implementation gates on 2026-08-03 for the
    cross-panel Finding navigation slice (eb4af61): Biome check and
    TypeScript passed; Vitest passed 132 tests with one opt-in private-scale
    skip at 92.66% statements, 87.43% branches, 98.60% functions, and 92.55%
    lines; the deterministic build check passed; Playwright passed 30/30
    across Chromium, Firefox, and WebKit including a new test proving that
    activating a Finding from a report heading focuses the same preview
    marker as the preview Finding list with aria-pressed synchronized across
    both button sets, and that bundle digests and remote-request counts stay
    unchanged; Python gates passed (559 tests, 89.69% branch coverage).`
  - `[CONFIRMED] Codex local gates on 2026-08-03 for fcf6be3+6360bb5 passed:
    uv lock/sync, Ruff format/check (159 files), mypy (143 source files),
    checked-in Schema currency, and 591 Python tests on both Python 3.12 and
    isolated Python 3.14; the Python 3.12 coverage run reported 89.81% branch
    coverage.`
  - `[CONFIRMED] The same Viewer tree passed clean npm ci with zero reported
    vulnerabilities, Biome format/lint, TypeScript, 165 Vitest tests with one
    opt-in private-scale skip (92.84% statements, 87.54% branches, 98.65%
    functions, 92.74% lines), deterministic standalone build comparison,
    and 36/36 file:// Playwright tests across Chromium, Firefox, and WebKit.
    The active-SVG E2E remained neutral, exposed no admitted summary/preview/
    report, made zero remote requests, and left Bundle digests unchanged.`
  - `[CONFIRMED] The untracked 225,636,102-byte private six-artifact Bundle
    passed opt-in admission in 8.18 s and a full UI smoke in Chromium,
    Firefox, and WebKit in 6.985 s, 10.327 s, and 7.074 s. Every engine
    displayed NOT_READY_FOR_FABRICATION with the same summary SHA-256 prefix
    77a1ca0ef67409a9, six layers, and five Findings; layer/Finding/report
    interactions completed with zero remote requests or console errors and
    unchanged input digests. No private input or output was committed.`
  - `[CONFIRMED] GitHub Actions run 30777119202 at baseline a6a7f58 failed
    only viewer-browsers: 29/30 tests passed, while WebKit test "terminates
    and revokes an in-flight worker before validating a replacement" timed
    out after 90 s waiting for Review unavailable. The other seven jobs
    passed; trace.zip and error-context.md were generated but the workflow
    retained zero artifacts.`
  - `[CONFIRMED] GitHub Actions run 30779478703 at implementation tip
    6360bb5 passed all eight jobs. The three-engine viewer-browsers job
    passed, its failure-evidence upload step concluded skipped, and the run
    retained zero artifacts as required on the success path.`
  - `[CONFIRMED] GitHub Actions run 30779724086 at documentation tip 77a9e38
    failed only viewer-browsers: WebKit's first complete-Bundle test timed out
    while Playwright's directory `setInputFiles` call remained pending, even
    though trace screenshots show the Viewer reached Bundle validation
    complete about 1.6 s after input delivery. All other 35 browser tests and
    seven sibling jobs passed. The new upload step succeeded and retained one
    231,316-byte minimal artifact through 2026-08-10; its trace and error
    context were downloaded and inspected before any further action.`
  - `[CONFIRMED] GitHub Actions run 30780036747 at documentation tip 21456e9
    passed 164/165 Viewer unit tests before the generated-fixture admission
    test hit Vitest's default 5-second timeout at 5.023 s; every assertion
    before/after it, deterministic build, 36/36 browser tests, Python gates,
    and cross-platform smokes passed. Repository evidence showed synchronous
    Python fixture generation occurred inside the timed test body.`
  - `[CONFIRMED] Commit 546aa99 moved both generated admission fixtures into
    a shared beforeAll hook with an explicit 60-second setup bound, matching
    the existing semantics fixture pattern; no product or Viewer resource
    deadline changed. Locally the affected test body fell to 1 ms, and the
    full 165-test coverage suite, Biome, TypeScript, and deterministic build
    passed.`
  - `[CONFIRMED] GitHub Actions run 30780184522 at test-fix tip 546aa99 passed
    all eight jobs, including Viewer coverage/deterministic build and 36/36
    Chromium/Firefox/WebKit E2E. The failure-upload step was skipped and the
    run retained zero artifacts.`
  - `[CONFIRMED] GitHub Actions run 30780349890 at recovery snapshot 26bb1e6
    passed all seven non-browser jobs and 34/36 browser tests, but two
    unrelated WebKit tests timed out inside directory `setInputFiles`: the
    active-SVG fail-closed test and the non-spatial Finding-focus test. The
    upload step succeeded and retained exactly four scoped files in one
    412,422-byte artifact through 2026-08-10. Both traces show input delivery
    without a normal `setInputFiles` completion; the legend Bundle reached
    `Bundle validation complete` within 0.44 s and its timeout snapshot shows
    the full admitted UI, while the active-SVG timeout snapshot shows the
    expected neutral `SVG_ACTIVE_ELEMENT_REJECTED` result. No failed-job
    re-run occurred.`
  - `[CONFIRMED] Each recovery commit was gate-verified on its own staged
    tree: b0ff240 (444 tests, 90.40%), 9d1de3d (471 tests, 90.57%), ccfb1a0
    (495 tests, 90.63%); checked-in schemas regenerated current.`
- Known limitations:
  - `[CONFIRMED] The v0.1 supported subsets and deliberate boundaries are
    documented in docs/CAPABILITIES.md. The Phase 11 Viewer renders the
    validated summary, preview.svg, and report.md with layer toggles,
    Finding-ID focus, and cross-panel Finding navigation, but provides no
    API/upload/review/persistence channel.`
  - `[CONFIRMED] Authoring currently supports exactly one Excellon
    tool-diameter operation and exactly one bounded two-layer coupon
    generator; neither is arbitrary or lossless source editing, and neither
    guarantees manufacturability. No native EDA writer, inferred circuit
    intent, autorouter, free-form generation path, or autonomous
    production-release path is implemented.`
- Working tree: `[CONFIRMED] The branch-tip HANDOFF commit is expected to
  leave a clean local main after generation contracts commit 4bd39bb,
  validated generation commit ec9ff16, and documentation commit d8aa07a. It
  remains ahead of origin/main=fec6795 until an explicitly authorized normal
  push is performed.`

Current State is the evidence-backed present snapshot. Recent Activity explains
how the repository reached that state and must not be required to understand
the current capabilities.

## Active Issues

### ISSUE-009 — SVG admission accepted animation and foreign namespaces

- Status: RESOLVED
- Severity: medium
- Owner: Codex
- State label: `[CONFIRMED]`
- Context: Python `_validate_safe_svg` and Viewer `validateSvg` previously
  treated element local names as sufficient and rejected a blacklist of
  scripts, embedded documents, event handlers, and external references.
  Declarative SVG mutation and elements outside the SVG namespace therefore
  remained admissible, contrary to ADR 0006's fail-closed transport boundary.
- Evidence: Repository inspection at a6a7f58 showed the Python validator
  accepted any namespace sharing an allowed local root name, while the
  Viewer parser ran with namespace processing disabled and its active-element
  set omitted SMIL animation. Adversarial probes admitted both a wrong-
  namespace SVG and `<animate attributeName="viewBox">`; the latter changed
  the imported presentation under Chromium. New Python/TypeScript parity,
  unit, and three-engine E2E regressions exercise wrong root/descendant/
  attribute namespaces, every SVG animation form in scope, authored style,
  unknown vocabulary, local/external references, and valid static gradients.
- Suspected cause: Namespace-insensitive local-name normalization combined
  with a blacklist cannot prove that an extensible XML vocabulary is passive.
- Attempted approaches: Compared the generated renderer vocabulary and ADR
  0002 gradient requirement with both admission implementations, then used
  adversarial Python, Vitest, oracle, and browser cases. No parser dependency,
  public Schema, artifact inventory, Viewer protocol, or ADR change was
  required.
- Current resolution state: Resolved by fcf6be3. Python and Viewer now require
  the exact SVG namespace for every element, reject foreign ordinary
  attributes, enforce per-element passive attribute allowlists, permit only
  unique local `fill|stroke="url(#gradient)"` references to static linear or
  radial gradients, and preserve specific active/external error precedence.
  The main thread independently checks the DOMParser root namespace before
  import. The deterministic standalone Viewer was rebuilt and all local and
  CI gates passed.
- Remaining work: None for ISSUE-009; future renderer-vocabulary additions
  must update Python and TypeScript admission together with parity evidence.
- Relevant files: `src/boardgate/application/artifacts.py`,
  `viewer/src/validation/svg.ts`, `viewer/src/main.ts`,
  `tests/unit/application/test_artifacts.py`, `viewer/tests/`
- Blocking: No.

### ISSUE-010 — Generated admission fixture exceeded Vitest's test-body timeout

- Status: RESOLVED
- Severity: low
- Owner: Codex
- State label: `[CONFIRMED]`
- Context: Documentation-tip Actions run 30780036747 failed only
  viewer-quality because `exposes validated layer groups and Finding markers
  for presentation` exceeded Vitest's default 5-second per-test timeout.
- Evidence: The failed log reports 164 passing tests, one opt-in skip, and the
  single test timing out at 5.023 s. That test synchronously invoked
  `generateValidBundle("copper_too_close_to_edge")`, which runs the complete
  Python review CLI, inside the timed test body. A sibling semantics suite
  already generates the same two fixtures in a 60-second beforeAll hook and
  took 10.581 s on that runner. The same run's browser suite, build-independent
  jobs, and all assertions outside the timed fixture generation passed.
- Suspected cause: CI scheduling/runner variance pushed an integration-heavy
  synchronous setup operation just beyond a unit test's generic 5-second
  body deadline; this was not an admission assertion or resource-policy
  failure.
- Attempted approaches: Did not re-run the failed job. Moved both generated
  fixtures and their admission into one explicitly 60-second-bounded
  beforeAll hook, retained cleanup in afterAll, and kept the actual assertion
  test synchronous and fast. No global timeout or product deadline was
  increased.
- Current resolution state: Resolved by 546aa99. The focused affected test
  passed with a 1 ms body, the full local Viewer suite passed 165 tests with
  configured coverage and deterministic build checks, and Actions run
  30780184522 passed all eight jobs including viewer-quality.
- Remaining work: None; keep external fixture/process setup outside generic
  unit-test body deadlines and bound it explicitly.
- Relevant files: `viewer/tests/unit/admit.test.ts`,
  `viewer/tests/unit/fixture.ts`, `viewer/tests/unit/semantics.test.ts`
- Blocking: No.

### ISSUE-008 — WebKit directory-input Playwright hang in CI

- Status: OPEN
- Severity: low
- Owner: unassigned
- State label: `[CONFIRMED]`
- Context: GitHub Actions run 30598805829 (validated SVG exploration push,
  commits 31ed334+a3a003b) initially failed the viewer-browsers job: the
  WebKit project of test "clears admitted evidence before rejecting a
  replacement selection" exceeded the 90-second timeout waiting for the
  "Review unavailable." status after a replacement directory selection, even
  though the first admission inside that test had succeeded. 23/24 E2E tests
  and all seven other jobs passed. The issue recurred at a6a7f58 in Actions
  run 30777119202 on the adjacent WebKit test "terminates and revokes an
  in-flight worker before validating a replacement": 29/30 E2E tests and all
  seven sibling jobs passed, but this test waited 90 seconds for the same
  neutral status. A third occurrence in run 30779724086 affected the first
  complete-Bundle admission test instead of either replacement test: 35/36
  E2E tests and all seven sibling jobs passed. A fourth occurrence in run
  30780349890 affected two unrelated tests: active-SVG fail-closed admission
  and non-spatial Finding focus. Both stalled inside their initial directory
  selection while 34/36 E2E tests and all seven sibling jobs passed.
- Evidence: Both failed-job logs show `toBeVisible()` on "Review unavailable."
  unresolved for the full 90 s. In the first test the SelectionError →
  `showError` path is synchronous and every error branch renders that status,
  which originally indicated that the change handler likely never executed.
  In the recurrence the replacement should first terminate and revoke a
  synthetic in-flight Worker, then take that same inventory-error path. Run
  30777119202 generated `trace.zip` and `error-context.md`, but the old
  workflow uploaded nothing and its artifact API reports zero retained files.
  Run 30779724086 retained the next trace: Playwright began directory
  `setInputFiles` at monotonic 23.836 s, delivered the input snapshot at
  23.870 s, and did not complete that API call until context teardown at
  113.235 s. In contrast, trace screenshots at 25.069 s and 25.440 s move
  from the neutral page to "Bundle validation complete" with the full
  summary, preview, and report; the timeout error-context snapshot also shows
  that completed UI. Thus the page handled the change and completed Worker
  validation about 1.6 s after input delivery while the Playwright driver
  command remained pending for the full test timeout. Run 30780349890
  retained both new failure traces in one 412,422-byte artifact. The
  active-SVG call began at monotonic 34.852 s and recorded input at 34.886 s;
  it had no normal completion before the 90-second teardown, while its final
  snapshot correctly shows neutral `SVG_ACTIVE_ELEMENT_REJECTED` with no
  admitted evidence. The legend-Finding call began at 130.585 s, recorded
  input at 130.626 s, and likewise had no normal completion; trace frames at
  130.801 s and 131.019 s show the page reaching `Bundle validation complete`
  in at most 0.44 s, and its timeout snapshot contains the full valid review
  UI. This broader recurrence is independent of Bundle outcome and post-
  admission interaction content.
- Suspected cause: `[INFERRED]` Playwright 1.62.0's WebKit directory
  `setInputFiles` command/acknowledgement intermittently hangs on the GitHub
  Linux runner after successfully delivering the files. The original
  suspected cause was a runner-load flake because that job's first WebKit test
  took 4.8 s versus 418 ms on Chromium and the defect did not reproduce
  locally. The retained trace rules out a Viewer change-event or validation-
  Worker stall for the third occurrence, but replacement-path behavior still
  needs a bounded Linux reproduction before generalizing the cause.
- Attempted approaches: The original identical WebKit test passed five local
  repeats in about 0.4 s each; `gh run rerun 30598805829 --failed` then made
  the original job/run succeed without a code change. After the recurrence,
  the expanded 36-test suite passed twice locally across all three engines,
  and the private large-Bundle full UI smoke passed sequentially in Chromium,
  Firefox, and WebKit. Commit 6360bb5 now retains only Playwright `trace.zip`
  and `error-context.md` on an E2E-step failure through a SHA-pinned upload
  action; a workflow contract test fixes the failure-only condition, minimal
  path scope, seven-day retention, and `continue-on-error` behavior. On run
  30779724086 that step succeeded; the retained 231,316-byte artifact was
  downloaded to a temporary directory, and its JSONL trace, network record,
  screenshots, and error context were inspected without re-running the job.
  Run 30780349890 exercised the same diagnostic path for two failures: the
  upload succeeded, retained only two trace/error-context pairs, and both
  were downloaded and inspected without a re-run.
- Current resolution state: Open and recurrent. Diagnostic retention is
  implemented and verified on the success path: Actions run 30779478703
  passed all jobs, skipped the upload step, and retained zero artifacts. It is
  also verified on the failure path: run 30779724086 preserved exactly the
  intended trace/error-context evidence without changing the failed job
  result. That evidence shows completed Viewer behavior behind a hung test-
  driver command. Run 30780349890 then reproduced the same pending driver
  command across both a fail-closed Bundle and a valid Bundle whose UI had
  completed, while the fixed Viewer-quality job and every non-browser job
  passed. No Viewer behavior change is justified by the available evidence.
- Remaining work: Reproduce only the two replacement-selection WebKit tests
  in a temporary Playwright 1.62.0 Linux environment with repeat-each 20,
  one worker, and retained traces; compare change-event delivery and Worker
  terminate/revoke evidence before changing Viewer behavior.
- Relevant files: `viewer/tests/e2e/viewer.spec.ts`,
  `viewer/src/main.ts`, `.github/workflows/ci.yml`
- Blocking: No.

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
- Authoring impact (2026-08-03): `[CONFIRMED]` The first modification
  operation deliberately avoids Gerbonara whole-file writing. It replaces one
  exact same-width tool token, reparses the result, and tests that explicit
  `;TYPE=PLATED` evidence and every protected drill/slot fact remain intact.
  This contains ISSUE-002 for the supported slice but does not resolve the
  upstream parser behavior or authorize broader Excellon rewriting.
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
  `astral-sh/setup-uv@v6` with the Node 20 deprecation notice. Successful
  Viewer Actions run 30553112414 confirms the warning remains and also
  annotates the newly used `actions/setup-node@v4`.
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

Implement Phase E's second registered deterministic operation as an explicit
new kind/version: add a non-plated (NPTH) drill variant to the coupon
generator (for example `generate_two_layer_coupon` 1.1 with an explicit
non-plated Excellon payload alongside the plated one), keeping the frozen 1.0
contract unchanged, and deliver the same evidence standard as the first
generator — strict contract, bounded executor, reparse postconditions, fresh
ReviewService validation, byte-stable evidence, inclusive bounds, and
fail-closed tests — proving multi-operation registry discipline without
widening the writer beyond round holes and round-aperture geometry.

## Recent Activity

### 2026-08-03T13:30:00+08:00 — Claude — Phase D bounded two-layer coupon generation

- Role: recovery, primary implementation, and verification agent
- Task: Recover repository state after a context reset, confirm HANDOFF
  matches the repository, then implement the recorded Next Action: Phase D's
  first constrained structured generator with fresh unchanged ReviewService
  validation, byte-stable evidence, inclusive bounds, and fail-closed
  requirements, without a free-form writer path.
- Context inspected:
  - `BOOTSTRAP.md`, `PROJECT_SPEC.md`, ADR 0007, the complete Current State
    and Next Action of `HANDOFF.md`, the authoring models/request/identifiers,
    modification registry/service, revision output and artifact validation,
    parser runner, rules engine status precedence, schemas exporter, and the
    modification integration test suite.
  - `[CONFIRMED]` Recovery found local main at 85d1599 exactly matching the
    recorded HANDOFF state: five unpushed commits ahead of origin/main
    fec6795, clean tree, and no conflicting specifications. A RECOVERY
    REPORT was issued before implementation began.
  - `[CONFIRMED]` Live Gerbonara probes before writing the writer confirmed
    the working emission formats: FSLAX46Y46 metric Gerber with X2
    FileFunction/SameCoordinates attributes, and `M48`/`METRIC,TZ` Excellon
    with six-decimal coordinates and `;TYPE=PLATED`.
  - `[CONFIRMED]` A hand-built coupon review de-risked review semantics:
    with no traces the required readiness-affecting minimum_trace_width rule
    reports SKIPPED and the overall status becomes INSUFFICIENT_INFORMATION,
    and padless plated holes produce annular-ring blockers. The contract
    therefore requires explicit traces and explicit per-hole pad diameters.
- Actions performed:
  - `[CONFIRMED]` Added GenerateTwoLayerCoupon/GenerationRequest/
    GenerationResult 1.0 contracts: inclusive 1.0-500.0 mm board bounds,
    feature bounds, 1,024-hole and 4,096-trace maxima, an exact 0.000001 mm
    emission quantum enforced through Decimal integrality, exact integer
    nanometre proofs for pad containment, pairwise drill non-overlap
    (tangent admitted), and trace containment, plus pinned normative
    disclaimer text and sorted unique payload evidence.
  - `[CONFIRMED]` Added bounded duplicate-safe generation-request JSON
    admission (inclusive 1 MiB, BOM/duplicate-key/non-finite rejection)
    mirroring the modification request boundary, and content-derived
    generation request/operation digests and gen- IDs that exclude
    instruction prose from operation identity.
  - `[CONFIRMED]` Added the bounded coupon writer: deterministic sorted
    emission of X2 top/bottom copper, rectangular outline, and plated
    Excellon payloads with an inclusive 1 MiB per-payload cap, plus reparse
    postconditions that prove source identity, metric/absolute metadata,
    zero warnings/limitations, and exact requested rectangle/pads/traces/
    drills/plating.
  - `[CONFIRMED]` Added the exact-version generation registry (no fallback,
    import-time completeness validation against the model-admitted key set)
    and GenerationService, which runs the unchanged ReviewService on the
    emitted design bytes and atomically publishes the shared
    design/evidence/validation workspace only after full revalidation.
    Shared workspace helpers were extracted into revision_workspace.py; the
    modification service refactor is import-only with unchanged behavior.
  - `[CONFIRMED]` Added `pcb-review generate` with control-file/output
    overlap rejection and exit mapping: admission/request failures 2,
    capability/parser/validation failures 3 without publication, completed
    blocker reviews published truthfully with 1.
  - `[CONFIRMED]` Exported the two checked-in generation Schemas; the
    existing currency test asserts they match the models.
  - `[CONFIRMED]` Added 62 unit tests (contracts, admission, registry,
    writer) and 7 integration tests proving CLI/service publish identical
    workspaces, byte-stable design/evidence/deterministic-validation
    artifacts, schema validity of published evidence, inclusive bounds at N
    and rejection at N+1, invalid requirements exit 2 with no workspace,
    overwrite preservation, blocker exit 1 with truthful publication,
    failed validation and parser failures publish nothing and preserve prior
    output, and the workspace validator rejects tampered evidence, symlinks,
    and extra directories.
  - `[CONFIRMED]` Updated docs/CAPABILITIES.md (generation row and
    deterministic authoring policy) and both READMEs (status, interfaces,
    bilingual generation walkthroughs, safety scope). No Viewer, review
    Schema, dependency, or network-provider change was made.
- Files added or materially changed:
  - Contracts: `src/boardgate/authoring/generation_models.py`,
    `src/boardgate/authoring/generation_request.py`,
    `src/boardgate/authoring/identifiers.py`, `src/boardgate/schemas.py`,
    `schemas/v1/generation-request.schema.json`,
    `schemas/v1/generation-result.schema.json`
  - Implementation: `src/boardgate/authoring/coupon.py`,
    `src/boardgate/application/generation_registry.py`,
    `src/boardgate/application/generation_service.py`,
    `src/boardgate/application/revision_workspace.py`,
    `src/boardgate/application/modification_service.py`,
    `src/boardgate/cli.py`, package `__init__.py` exports
  - Evidence/tests: `tests/unit/authoring/test_generation_models.py`,
    `tests/unit/authoring/test_generation_request.py`,
    `tests/unit/authoring/test_generation_registry.py`,
    `tests/unit/authoring/test_coupon.py`,
    `tests/integration/test_generate_revision.py`
  - Documentation: `docs/CAPABILITIES.md`, `README.md`, `README.zh-CN.md`
- Commands and verification:
  - `uv run ruff format --check src tests` (167 files), `uv run ruff check
    src tests`, and `uv run mypy src tests` (167 source files) all passed.
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85` passed
    the complete suite: 726 tests, 89.56% branch coverage; the checked-in
    Schema currency test passed.
  - Two consecutive `uv run pcb-review generate` runs of the documented
    two-hole/two-trace coupon produced identical gen-d7e5e84e3a261e50 /
    prj-617f50c90bf61324 IDs and READY_FOR_REVIEW validation; `diff -r`
    showed only validation/logs/run.jsonl differing (run ID, timestamps,
    elapsed ms), as contracted for the sixth artifact.
- Commits:
  - `4bd39bb feat(authoring): define deterministic generation contracts`
  - `ec9ff16 feat(authoring): validate two-layer coupon generations`
  - `d8aa07a docs(authoring): document deterministic coupon generation`
  - branch-tip `docs(handoff)` commit containing this collaboration state
- Issues created or updated:
  - No new defect issue. ISSUE-002, ISSUE-005, ISSUE-007, and ISSUE-008
    remain open, low, and unaffected; no Viewer code was touched, so
    ISSUE-008's browser CI behavior is unchanged.
- Remote/delivery state: `[CONFIRMED]` The three implementation/documentation
  commits and this branch-tip HANDOFF commit are local on main, now eight
  commits ahead of origin/main=fec6795 together with the earlier authoring
  commits. The standing request did not authorize a push; no remote mutation
  was made.
- Remaining uncertainty: `[CONFIRMED]` The generator proves only the bounded
  coupon envelope (round plated holes, round-aperture straight traces,
  rectangular outline); it is not evidence for slots, vias, NPTH, non-round
  apertures, or arbitrary geometry. Per-commit staged-tree gate runs were not
  performed; gates were run on the full tree containing all three commits.
- Recommended next action: Implement the Phase E second registered operation
  (NPTH coupon variant) stated in Next Action.

### 2026-08-03T12:00:00+08:00 — Codex — Separate PCB authoring foundation and first validated revision

- Role: recovery, architecture, primary implementation, security review, and
  verification agent
- Task: Reassess the completed review-only boundary, make PCB modification
  and generation explicit product capabilities without weakening review
  evidence, and deliver the smallest deterministic modification that emits a
  real PCB artifact and validates it through the existing pipeline.
- Context inspected:
  - `BOOTSTRAP.md` in full, the complete `HANDOFF.md`, the absent-at-baseline
    `PROJECT_SPEC.md`, `IMPLEMENT_PCB_AGENT.md`, every ADR 0001-0006, review
    application/worker/output paths, parser adapters and normalized domain,
    Gerber/Excellon capabilities and fixtures, CLI/config/schema boundaries,
    tests, CI, recent commits, branch/remotes, and open ISSUE-002/005/007/008.
  - `[CONFIRMED]` Recovery baseline was clean local/remote main at fec6795.
    No existing ADR prohibited authoring: the legacy specification deferred
    it only for the initial review MVP. `PCBProject` is a content-addressed
    review snapshot and lacks the lossless syntax/design intent needed to be
    an editable authoring model.
- Architectural decision:
  - `[CONFIRMED]` Added forward-looking `PROJECT_SPEC.md` and accepted ADR
    0007. Review, modification, and generation remain distinct. Authoring is
    a sibling deterministic subsystem; emitted bytes enter the unchanged
    ReviewService as fresh input. ADRs 0001-0006, the exact six-artifact
    review bundle, and the read-only Viewer remain valid.
  - `[CONFIRMED]` Rejected mutation of `PCBProject`, free-form LLM/source
    writes, a seventh review artifact, and arbitrary Gerbonara round-trip
    output. The first slice uses an operation-specific exact token adapter
    because general Excellon rewriting cannot yet prove syntax/plating
    preservation.
- Actions performed:
  - `[CONFIRMED]` Added explicit-version ModificationRequest/Result models,
    two checked-in public Schemas, strict bounded duplicate-safe JSON
    admission, full safe-path parity with ingestion, full request and
    prose-independent operation digests, stable revision IDs, exact payload
    inventory, normative disclaimer, and cross-evidence validation.
  - `[CONFIRMED]` Added a complete exact-version operation registry. The sole
    registered executor patches one plain fixed-width metric/absolute
    Excellon TnnC diameter token, rejects warnings/limitations, ambiguous or
    unsupported scope, slots sharing the tool, stale values, and resource
    N+1; it reparses before/after and proves all protected drill/slot facts.
  - `[CONFIRMED]` Added `pcb-review modify`. It rejects request/profile files
    inside project inputs and non-design siblings, preserves all admitted
    input bytes, emits `design/`, canonical `evidence/`, and a nested exact
    six-artifact `validation/`, then validates symlink-free exact inventory,
    hashes, IDs, token span, normalized output drills, and review identity
    before atomic publication.
  - `[CONFIRMED]` Fixed review findings during independent inspection:
    revision identity no longer depends on instruction prose; executable
    versions cannot default silently; public logical paths cannot express
    values ingestion would reject; disclaimer/span evidence cannot be
    fabricated; external symlinks/extra directories fail workspace
    admission; request/precondition errors map to exit 2 while unsupported
    parser/executor/postcondition failures map to exit 3.
  - `[CONFIRMED]` Added the original `drill_too_small` fixture. Its baseline
    review has exactly one drill-diameter blocker; the tested revision changes
    only T01C0.100 to T01C0.300, resolves that Finding with PASS/FULL, adds no
    Finding, and yields stable deterministic revision bytes. Tests also prove
    stale/precondition/control/capability/parser/ANALYSIS_FAILED failures do
    not publish, an existing output is preserved, and a completed blocker
    review is published truthfully with exit 1.
  - `[CONFIRMED]` Updated English/Chinese usage, architecture, capability
    matrix, package description, and ISSUE-002 authoring impact. No network
    provider, Viewer behavior, review Schema, dependency, API, native EDA
    writer, or generator was added.
- Files added or materially changed:
  - Specification/architecture: `PROJECT_SPEC.md`,
    `docs/adr/0007-separate-authoring-and-review-validation.md`,
    `IMPLEMENT_PCB_AGENT.md`, `docs/architecture.md`,
    `docs/CAPABILITIES.md`, `README.md`, `README.zh-CN.md`
  - Contracts/implementation: `src/boardgate/authoring/`,
    `src/boardgate/application/modification_registry.py`,
    `src/boardgate/application/modification_service.py`,
    `src/boardgate/cli.py`, `src/boardgate/schemas.py`,
    `schemas/v1/modification-*.schema.json`
  - Evidence/tests: `tests/unit/authoring/`,
    `tests/integration/test_modify_revision.py`,
    `tests/fixtures/drill_too_small/`
- Commands and verification:
  - `uv lock --check`; locked Python 3.12 all-group sync; Schema export and
    clean diff; Ruff format/check; mypy; focused authoring/integration/schema
    suite (70 passed); full Python 3.12 coverage suite (655 passed, 89.59%
    branch); full CPython 3.14.4 suite (655 passed); default environment
    restored to CPython 3.12.13.
  - Clean `npm ci` (zero vulnerabilities), Biome, TypeScript, Vitest coverage
    (165 passed, one opt-in skip, thresholds met), deterministic Viewer build,
    and file:// Playwright 36/36 across Chromium/Firefox/WebKit. Added
    authoring Schemas did not expand the Viewer's exact six-artifact protocol.
  - The first Viewer coverage attempt inherited the temporary 3.14 virtual
    environment and its Python-oracle hook took 10.428 s; after restoring the
    declared 3.12 environment, the unchanged suite passed in 3.96 s. No
    timeout or Viewer code was changed.
- Commits:
  - `a935d58 docs(architecture): define deterministic PCB authoring boundary`
  - `dea742d feat(authoring): define deterministic revision contracts`
  - `f3ddd6e feat(authoring): validate Excellon diameter revisions`
  - `61ea33a docs(authoring): document constrained revision workflow`
  - branch-tip `docs(handoff): record validated authoring foundation` commit
    containing this collaboration state
- Issues created or updated:
  - No new defect issue. ISSUE-002 remains open upstream, low, and
    non-blocking; the supported adapter avoids whole-file rewriting and proves
    explicit plating survives. ISSUE-005, ISSUE-007, and ISSUE-008 remain
    open, low, and unaffected. ISSUE-008 did not reproduce in the local 36/36
    browser regression.
- Remote/delivery state: `[CONFIRMED]` The four implementation/documentation
  commits and this branch-tip HANDOFF commit are local on main, ahead of
  origin/main=fec6795. The current request authorized repository changes and
  coherent commits but did not request a push; no remote mutation was made.
- Remaining uncertainty: `[CONFIRMED]` The current operation does not prove a
  general Gerber/Excellon writer or lossless arbitrary edit path. Structured
  generation still needs its own requirements model, bounded writer adapter,
  generation evidence, and end-to-end validation; it must not reuse review
  IR as mutable source truth.
- Recommended next action: Implement the bounded Phase D two-layer coupon
  generator stated in Next Action.

### 2026-08-03T11:00:00+08:00 — Codex — Passive SVG admission and CI diagnostics recovery

- Role: recovery, primary implementation, security review, and verification
  agent
- Task: Recover the a6a7f58 repository state, repair ISSUE-009's SVG
  evidence-integrity gap without changing the Viewer transport contract, then
  implement ISSUE-008 failure-evidence retention and leave one bounded Linux
  reproduction action.
- Context inspected:
  - `BOOTSTRAP.md` in full, `IMPLEMENT_PCB_AGENT.md`, ADR 0002/0003/0006,
    `docs/CAPABILITIES.md`, `HANDOFF.md`, the Viewer/Python SVG admission and
    rendering paths, test/build configuration, Git history/status/remotes,
    public repository metadata, and Actions runs 30777119202, 30779478703,
    30779724086, 30780036747, and 30780184522 plus the retained Playwright
    artifact from 30779724086; then Actions run 30780349890 and both of its
    retained Playwright failure traces.
  - `[CONFIRMED] PROJECT_SPEC.md is absent from the repository and history;
    the operative project specification is IMPLEMENT_PCB_AGENT.md plus the
    accepted ADRs. Baseline local HEAD, origin/main, and origin/HEAD were
    clean and identical at a6a7f58 before implementation.`
- Actions performed:
  - `[CONFIRMED] Replaced namespace-insensitive SVG blacklists in Python and
    TypeScript with exact SVG expanded-name checks and a renderer-derived,
    per-element passive vocabulary. Added stable namespace/vocabulary error
    codes and constrained internal URL use to one unique existing static
    gradient paint server.`
  - `[CONFIRMED] Preserved active/external error specificity, added the
    main-thread DOMParser namespace defense, rebuilt the hash-pinned single
    HTML Viewer deterministically, and documented the presentation-copy
    boundary in English, Chinese, and CAPABILITIES.`
  - `[CONFIRMED] Added Python/Viewer parity, unit, and E2E regressions for
    namespace resets, foreign attributes, SMIL/declarative mutation, CSS,
    unknown vocabulary, local/external references, static gradients, neutral
    failure UI, zero network, and unchanged Bundle digests.`
  - `[CONFIRMED] Gave the browser E2E step a stable ID and added a failure-only
    SHA-pinned upload-artifact v7.0.1 step limited to Playwright trace.zip and
    error-context.md, with seven-day retention, no overwrite/hidden files,
    compression level zero, and continue-on-error. Added a parsed workflow
    contract regression for every setting and step adjacency.`
  - `[CONFIRMED] Pushed the two atomic implementation commits normally to
    public main and waited for the complete implementation-tip CI result; no
    force push, rebase, dependency update, Schema change, ADR change, artifact
    protocol change, or private-file addition occurred.`
  - `[CONFIRMED] When documentation-tip run 30779724086 reproduced the WebKit
    failure, did not re-run it. Downloaded the newly retained minimal artifact
    to an isolated temporary directory and inspected its error context,
    JSONL trace timing, network record, and screenshots. The page completed
    admission within about 1.6 seconds of input delivery while Playwright's
    directory setInputFiles command stayed pending until the 90-second test
    timeout/context teardown; this is evidence against changing Viewer
    admission or Worker behavior.`
  - `[CONFIRMED] Diagnosed the only failure in run 30780036747 rather than
    re-running it: a test synchronously generated a full Python review fixture
    inside Vitest's 5-second test-body deadline and crossed it by 23 ms. Moved
    both generated admission fixtures into a shared, explicitly 60-second-
    bounded beforeAll hook, matching the existing semantics test pattern;
    kept assertions and product/resource deadlines unchanged.`
  - `[CONFIRMED] When recovery-snapshot run 30780349890 failed two unrelated
    WebKit tests, again did not re-run it. Downloaded and inspected both
    retained trace/error-context pairs. Each directory input reached the page
    but its Playwright call never returned normally; one page displayed the
    valid completion status within 0.44 s and had the full review in its
    timeout snapshot, while the other final snapshot displayed the exact
    neutral active-SVG rejection. This confirms the failure-evidence workflow
    and broadens ISSUE-008 without supporting a Viewer behavior change.`
- Files modified:
  - SVG implementation/tests: `src/boardgate/application/artifacts.py`,
    `tests/unit/application/test_artifacts.py`, `viewer/src/main.ts`,
    `viewer/src/validation/errors.ts`, `viewer/src/validation/svg.ts`,
    `viewer/tests/unit/admit.test.ts`, `viewer/tests/unit/log-svg.test.ts`,
    `viewer/tests/unit/python-oracle.test.ts`,
    `viewer/tests/e2e/global-setup.ts`, `viewer/tests/e2e/viewer.spec.ts`
  - Distribution/docs: `viewer/boardgate-viewer.html`, `README.md`,
    `README.zh-CN.md`, `docs/CAPABILITIES.md`
  - CI/state: `.github/workflows/ci.yml`,
    `tests/unit/test_ci_workflow.py`, `HANDOFF.md`
- Commands run:
  - `uv lock --check`; `uv sync --locked --all-groups`; Schema export/diff;
    `uv run ruff format --check .`; `uv run ruff check .`;
    `uv run mypy src tests`; Python 3.12 coverage suite; isolated Python 3.14
    full suite
  - clean `npm ci`; Biome format/lint; TypeScript; Vitest coverage;
    deterministic build/build-check; two complete three-engine Playwright
    file:// E2E runs
  - opt-in private-scale admission and a one-off full Viewer UI smoke against
    `/Users/matthew/Projects/testruns/PCB/1-verify.review-output`
  - `gh run view`, failed-job log inspection, artifact API checks, normal
    `git push origin main`, implementation/documentation-tip Actions
    monitoring, `gh run download`, bounded ZIP listing/extraction, JSONL trace
    queries, visual inspection of the retained trace screenshots, focused and
    full Viewer regression runs, test-fix-tip Actions monitoring, and final
    two-trace failure inspection without a re-run
- Verification performed:
  - `[CONFIRMED] Python 3.12: 591 tests passed with 89.81% branch coverage;
    Python 3.14: the same 591 tests passed. Ruff, mypy, lock/sync, and Schema
    currency passed.`
  - `[CONFIRMED] Viewer: 165 tests passed with one opt-in skip and coverage
    above every configured threshold; clean install, Biome, TypeScript, and
    deterministic build passed. Playwright passed 36/36 in Chromium, Firefox,
    and WebKit, twice locally.`
  - `[CONFIRMED] Private 225,636,102-byte Bundle admission and full UI smokes
    completed within the 60-second deadline in all engines with the same
    summary, zero network/console errors, exercised SVG/report/Finding
    navigation, and unchanged file digests; the Bundle remains untracked.`
  - `[CONFIRMED] Actions run 30779478703 passed all eight jobs at 6360bb5;
    Viewer E2E passed, the upload step was skipped, and the artifact API
    returned zero success-path artifacts.`
  - `[CONFIRMED] Actions run 30779724086 failed only one WebKit test at
    77a9e38; 35/36 browser tests and all seven sibling jobs passed. The upload
    step succeeded and retained exactly the scoped trace/error-context
    artifact. Inspection proved the Viewer was complete while Playwright's
    directory-input API call remained pending; no blind re-run occurred.`
  - `[CONFIRMED] Run 30780036747 isolated ISSUE-010 at 5.023 s while the other
    164 Viewer tests, deterministic build, 36/36 browser tests, and all seven
    sibling jobs passed. After 546aa99, the affected local test body took
    1 ms; the 165-test coverage suite, Biome, TypeScript, and deterministic
    build passed. Actions run 30780184522 then passed all eight jobs, skipped
    the failure upload, and retained zero artifacts.`
  - `[CONFIRMED] Actions run 30780349890 passed Viewer quality, root quality,
    Python 3.12/3.14, and all three CLI smokes; browser E2E passed 34/36 and
    failed only two WebKit directory-selection calls after delivering their
    inputs. The successful upload retained one 412,422-byte minimal artifact
    (SHA-256 20780d257b50e45ed214521bf24c345e608221e7162f19438867727322268f74)
    through 2026-08-10. Both traces and error contexts were inspected; no
    blind re-run occurred.`
- Commits:
  - `fcf6be3 fix(svg): enforce passive preview vocabulary`
  - `6360bb5 ci(viewer): retain Playwright failure evidence`
  - `77a9e38 docs(handoff): record passive SVG and CI recovery`
  - `21456e9 docs(handoff): record retained WebKit trace evidence`
  - `546aa99 test(viewer): prebuild generated admission fixtures`
  - `26bb1e6 docs(handoff): finalize passive SVG recovery evidence`
  - branch-tip `docs(handoff): record final WebKit trace evidence` commit
    containing this latest inspected state
- Issues created or updated:
  - ISSUE-009 created and resolved with adversarial, parity, browser, private-
    scale, and CI evidence; it no longer blocks Viewer evidence-integrity
    claims.
  - ISSUE-010 created and resolved by moving external fixture setup under its
    own explicit bound; no product timeout was relaxed.
  - ISSUE-008 remains open and low severity. Its recurrence in run
    30777119202, 30779724086, and twice in 30780349890 is confirmed; the
    diagnostic upload is proven on both success and multi-failure paths. The
    retained traces narrow the failure to pending Playwright WebKit directory-
    input commands after successful page delivery across both accepted and
    rejected Bundles. ISSUE-002, ISSUE-005, and ISSUE-007 remain open, low,
    and non-blocking.
- Remaining uncertainty: `[UNKNOWN]` Why Playwright 1.62.0 WebKit on GitHub's
  Linux runner sometimes fails to acknowledge a delivered directory
  setInputFiles command, and whether the two earlier replacement-test
  occurrences share precisely that driver behavior. The retained traces do
  not support a Viewer code change, so none was made speculatively.
- Recommended next action: Run the bounded Linux WebKit reproduction stated
  in Next Action and inspect retained traces before proposing a product fix.

### 2026-08-03T09:40:00+08:00 — Claude — Cross-panel Finding navigation

- Role: primary implementation and verification agent
- Task: Implement the standing Next Action: make Finding-ID headings in the
  rendered report focus the same preview marker as the preview Finding list
  with one shared selection state and synchronized aria-pressed, preserving
  read-only evidence with E2E proof.
- Context inspected:
  - `viewer/src/main.ts` (existing panel-only focus logic), the report
    section structure from the 2149f2d round, the composer heading shapes
    (`#### fnd-… — title` severity-group headings and `### fnd-…` Evidence
    Index headings), and the existing spatial/legend E2E focus tests.
- Actions performed:
  - Replaced the panel-local click logic with a controller-owned
    `#selectFinding(findingId, scrollReport)` that clears marker focus,
    synchronizes aria-pressed across both `.finding-button` and
    `.report-finding-button` sets, focuses and scrolls the preview marker,
    and scrolls the report heading into view when activated from the panel.
  - Threaded an `onFindingSelect` callback through `renderPreview`/
    `buildFindingList` and `renderReport`; report headings whose text begins
    with a stable Finding ID render as in-heading buttons carrying
    `data-finding-id` and aria-pressed.
  - Added `.report-finding-button` styles (inline heading-text appearance
    with pressed-state highlight) and a three-engine E2E test proving
    bidirectional selection sync with unchanged bundle digests and zero
    remote requests.
  - Updated viewer claims in `README.md`, `README.zh-CN.md`, and
    `docs/CAPABILITIES.md`.
- Files modified:
  - `viewer/src/main.ts`, `viewer/src/style.css`,
    `viewer/tests/e2e/viewer.spec.ts`,
    `viewer/boardgate-viewer.html` (rebuilt deterministic artifact),
    `README.md`, `README.zh-CN.md`, `docs/CAPABILITIES.md`, `HANDOFF.md`
- Commands run:
  - `npm run format` / `npm run check` / `npm run typecheck`
  - `npx vitest run` / `npm run test:coverage`
  - `npm run build` / `npm run build:check` / `npm run test:e2e`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
- Tests:
  - Viewer: 132 passed, 1 skipped (opt-in private-scale); 92.66% statements,
    87.43% branches, 98.60% functions, 92.55% lines — all thresholds met;
    deterministic build check passed.
  - E2E: 30/30 passed across Chromium, Firefox, and WebKit, including the
    new cross-panel selection synchronization test.
  - Python: 559 passed, 89.69% branch coverage.
- Commit: `eb4af61 feat(viewer): synchronize Finding selection across report
  and preview` plus the branch-tip HANDOFF documentation commit.
- Issues created or updated: None. Open set remains ISSUE-002, ISSUE-005,
  ISSUE-007, ISSUE-008 — all low, non-blocking; ISSUE-008's remaining work
  becomes the Next Action.
- Remaining uncertainty: The private-scale opt-in test still requires a large
  local bundle to run; the full viewer UI has not been re-smoked against the
  private real-scale bundle since the report and navigation rounds.
- Recommended next action: Address the ISSUE-008 CI failure-artifact upload
  (see Next Action).

### 2026-08-03T01:50:00+08:00 — Claude — Phase 11 validated report rendering

- Role: primary implementation and verification agent
- Task: Implement the standing Next Action: display report.md only after
  successful bundle admission without a Markdown parser or innerHTML, keep
  evidence read-only, and prove with E2E that rendering never executes active
  content, mutates bundle bytes, or re-evaluates review evidence.
- Context inspected:
  - `BOOTSTRAP.md`, `HANDOFF.md`, ADR 0006, `docs/CAPABILITIES.md`,
    `src/boardgate/reporting/markdown.py` and `src/boardgate/agent/narrative.py`
    (the complete deterministic Markdown subset: ATX headings levels 1–4, two-
    space nested lists, paragraphs, `**bold**` status/Finding lines, composer
    backslash escapes, HTML comment metadata), the existing viewer validation
    and UI stack, and a freshly generated copper_too_close_to_edge report
    (whose overall status is READY_FOR_REVIEW because its findings are HIGH,
    not BLOCKER).
- Actions performed:
  - Added `maxReportLines: 200_000` to viewer resource policy 1.0 (viewer-
    internal policy; never serialized into artifacts) and enforced it
    fail-closed in `validateReport` with ARTIFACT_RESOURCE_LIMIT on N+1,
    counted without splitting the payload.
  - Extended the validation success contract with `reportMarkdown` and wired
    it through `admit.ts`; the worker passes results through unchanged.
  - Added `viewer/src/report.ts`: a total, line-oriented tokenizer for the
    deterministic report subset (headings 1–4, paragraphs, nested lists with
    depth clamped to four, `**bold**` segments with balanced-marker
    fail-safe, composer punctuation unescape); HTML comment lines and blank
    lines produce no blocks; unknown structures become literal paragraphs.
  - Added `renderReport` to `main.ts` (createElement/textContent only;
    headings shifted one level under the section heading; bold as
    `<strong>`), a hidden `report` section cleared on load/error/dispose,
    and report styles in `style.css`.
  - Added unit tests for the tokenizer and the report line budget, extended
    admission tests for the `reportMarkdown` payload, and added a three-engine
    E2E test proving the rendered report shows Finding IDs and bold status,
    hides HTML comment metadata, contains zero
    script/img/iframe/object/embed/a/form/input/video/audio elements, and
    leaves bundle digests and remote-request counts unchanged.
  - Updated the viewer claims in `README.md`, `README.zh-CN.md`, and
    `docs/CAPABILITIES.md` (capability row, policy table, admission
    epilogue).
- Files modified:
  - `viewer/src/policy.ts`, `viewer/src/contracts.ts`, `viewer/src/report.ts`,
    `viewer/src/main.ts`, `viewer/src/style.css`,
    `viewer/src/validation/admit.ts`, `viewer/src/validation/text.ts`,
    `viewer/tests/unit/report.test.ts`, `viewer/tests/unit/log-svg.test.ts`,
    `viewer/tests/unit/admit.test.ts`, `viewer/tests/e2e/viewer.spec.ts`,
    `viewer/boardgate-viewer.html` (rebuilt deterministic artifact),
    `README.md`, `README.zh-CN.md`, `docs/CAPABILITIES.md`, `HANDOFF.md`
- Commands run:
  - `npm run format` / `npm run check` / `npm run typecheck`
  - `npm run test:coverage` / `npm run build` / `npm run build:check`
  - `npm run test:e2e`
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
  - `uv run ruff check .`
  - `uv run pcb-review inspect tests/fixtures/copper_too_close_to_edge ...`
    to verify real report markup before writing assertions
- Tests:
  - Viewer: 132 passed, 1 skipped (opt-in private-scale); 92.66% statements,
    87.43% branches, 98.60% functions, 92.55% lines — all thresholds met;
    deterministic build check passed with matching CSP hashes.
  - E2E: 27/27 passed across Chromium, Firefox, and WebKit.
  - Python: 559 passed, 89.69% branch coverage; Ruff check passed.
- Commit: `2149f2d feat(viewer): render validated report with
  deterministic-subset tokenizer` plus the branch-tip HANDOFF documentation
  commit `1c80e61`; GitHub Actions run 30759509309 succeeded for all jobs.
- Issues created or updated: None. Open set remains ISSUE-002, ISSUE-005,
  ISSUE-007, ISSUE-008 — all low, non-blocking.
- Remaining uncertainty: Two filtered `npx playwright test -g` invocations
  failed during collection with a spurious schema-validators require error
  while the full suite passed cleanly before and after; treated as a runner
  invocation fluke, not product code. The private-scale opt-in test still
  requires a large local bundle to run.
- Recommended next action: Implement cross-panel Finding navigation (see Next
  Action).

### 2026-07-31T11:05:00+08:00 — Claude — Recovery and CI flake triage

- Role: takeover implementation/review agent
- Task: Recover project state per BOOTSTRAP, cross-check HANDOFF against the
  repository, and resolve the CI signal from the previous round before new
  implementation.
- Actions performed:
  - Read BOOTSTRAP.md and HANDOFF.md; confirmed PROJECT_SPEC.md has never
    existed in this repository (`ls`, `git log --all -- PROJECT_SPEC.md`) and
    that ADRs 0001–0006 plus docs/CAPABILITIES.md carry the specification
    role.
  - Verified working tree clean at a3a003b with main == origin/main;
    spot-checked viewer source against HANDOFF Current State claims.
  - Investigated failed Actions run 30598805829 viewer-browsers job (one
    WebKit timeout on a pre-existing replacement-selection test): confirmed
    the failing path is synchronous in main.ts, reproduced nothing locally
    (5/5 WebKit passes against the same build), and re-ran the failed job —
    run now concludes success.
  - Recorded the flake as ISSUE-008 (low, non-blocking) with a remaining-work
    note to upload Playwright failure artifacts if it recurs.
- Files modified:
  - `HANDOFF.md`
- Commands run:
  - `gh run view 30598805829 --log-failed`
  - `npx playwright test --project=webkit -g "clears admitted evidence"
    --repeat-each=5` (5 passed)
  - `gh run rerun 30598805829 --failed` then `gh run watch` (success)
- Tests: No code changed; local WebKit re-run 5/5 and CI re-run success are
  the verification evidence.
- Commit: the branch-tip documentation commit containing this entry.
- Issues created or updated: ISSUE-008 created (OPEN, low).
- Remaining uncertainty: Root cause of the WebKit stall is unproven; treated
  as a runner flake pending recurrence.
- Recommended next action: Implement Phase 11 validated Markdown report
  rendering (see Next Action).

### 2026-07-31T10:30:00+08:00 — Claude — Phase 11 validated SVG exploration

- Role: primary implementation and verification agent
- Task: Implement the standing Next Action left after the viewer loader
  foundation round: render preview.svg only after successful bundle
  admission, add layer visibility toggles and Finding-ID focus, and prove
  that interactions neither mutate nor re-evaluate review evidence (Codex
  was rate-limited, so Claude implemented this slice).
- Context inspected:
  - `BOOTSTRAP.md`, `HANDOFF.md`, ADR 0006, `docs/CAPABILITIES.md`,
    `README.md`/`README.zh-CN.md`, `src/boardgate/rendering/svg.py` (layer
    group ID/sort scheme and Finding marker sections), the existing viewer
    validation/rendering stack, and real CLI output for the
    `valid_minimal_board`, `copper_too_close_to_edge`, and `missing_drill`
    fixtures.
- Actions performed:
  - Extended `viewer/src/contracts.ts` with `ViewerLayer`/`ViewerFinding`,
    summary `layers`/`findings`, and a `previewSvg` success payload.
  - Extended `viewer/src/validation/svg.ts` to extract well-formed
    `pcb-layer-%04d` groups (rejecting missing metadata and duplicate group
    or layer IDs with SVG_LAYER_GROUP_INVALID) and to classify Finding
    markers by spatial/non-spatial section (rejecting strays and
    duplicates); added both error codes to `errors.ts`.
  - Extended `viewer/src/validation/semantics.ts` with layer/finding detail
    projections and `admit.ts` to cross-check SVG layer groups against
    project.json layers (SVG_LAYER_MISMATCH) and return sorted layers,
    spatial-flagged findings, and the validated SVG payload.
  - Implemented `renderPreview` in `viewer/src/main.ts`: DOMParser
    `image/svg+xml` re-parse of the already validated payload with
    parsererror/root/project-ID guards, `importNode` insertion, per-layer
    visibility checkboxes (`style.visibility` only), and a Finding list that
    moves a `finding-focus` class with `aria-pressed` state and
    `scrollIntoView`; added matching styles in `style.css`.
  - Added unit tests for layer-group extraction/rejection, Finding marker
    classification, admission summary/preview exposure, and the three
    SVG_LAYER_MISMATCH mutation cases; added four Playwright E2E tests per
    engine covering toggle geometry immutability (path `d` attributes and
    bundle digests unchanged, zero remote requests), spatial Finding focus,
    legend Finding focus on `missing_drill`, and the empty Finding list.
  - Updated the stale viewer claims in `README.md`, `README.zh-CN.md`, and
    `docs/CAPABILITIES.md`, which previously stated the viewer never inserts
    preview.svg or offers Finding navigation/layer controls.
- Files modified:
  - `viewer/src/contracts.ts`, `viewer/src/main.ts`, `viewer/src/style.css`,
    `viewer/src/validation/admit.ts`, `viewer/src/validation/errors.ts`,
    `viewer/src/validation/semantics.ts`, `viewer/src/validation/svg.ts`,
    `viewer/tests/unit/admit.test.ts`, `viewer/tests/unit/log-svg.test.ts`,
    `viewer/tests/e2e/global-setup.ts`, `viewer/tests/e2e/viewer.spec.ts`,
    `viewer/boardgate-viewer.html` (rebuilt deterministic artifact),
    `README.md`, `README.zh-CN.md`, `docs/CAPABILITIES.md`, `HANDOFF.md`
- Commands run:
  - `npm run format` / `npm run check` / `npm run typecheck`
  - `npm run test:coverage` / `npm run build:check`
  - `npm run test:e2e` (after build)
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
  - `uv run ruff check .` / `uv run ruff format --check .` / `uv run mypy src`
- Tests:
  - Viewer: 124 passed, 1 skipped (opt-in private-scale); 92.33% statements,
    87.15% branches, 98.55% functions, 92.22% lines — all thresholds met;
    deterministic build check passed with matching CSP hashes.
  - E2E: 24/24 passed across Chromium, Firefox, and WebKit, including the
    four new interaction/immutability tests.
  - Python: 559 passed, 89.69% branch coverage; Ruff format/check and mypy
    passed.
- Commit: `31ed334 feat(viewer): render validated SVG with layer toggles and
  Finding focus` plus the branch-tip HANDOFF documentation commit.
- Issues created or updated: None. Open set remains ISSUE-002, ISSUE-005,
  ISSUE-007 — all low, non-blocking.
- Remaining uncertainty: The private-scale opt-in test still requires a large
  local bundle to run; report.md rendering and any richer Finding navigation
  remain unimplemented by design.
- Recommended next action: Implement Phase 11 validated Markdown report
  rendering (see Next Action).

### 2026-07-31T09:35:00+08:00 — Claude — Viewer loader consistency review

- Role: verification agent
- Task: Independently verify the Codex Phase 11 viewer loader round
  (commits 45f8f76..9ab9d2a) against repository evidence and update HANDOFF
  per BOOTSTRAP.
- Actions performed:
  - Confirmed the round adds only the separately distributed `viewer/`
    toolchain, CI jobs, and documentation — no Python source, Schema, or
    six-artifact contract change; `viewer/boardgate-viewer.html` is not a
    seventh artifact.
  - Reviewed ADR 0006 compliance in source: fail-closed admission
    (inventory → size preflight → UTF-8 → canonical JSON → Schema →
    semantics → report/SVG/log → run-variance leak check), resource policy
    1.0 budgets, fresh Worker per validation with a 60 s deadline and
    terminate/revoke, textContent/createElement-only DOM, no
    innerHTML/fetch/storage/network in hand-written source, and a strict
    hash-pinned CSP (`default-src 'none'`, `connect-src 'none'`).
  - Re-ran all gates locally (see Tests) and smoke-tested the tracked
    standalone viewer in Chromium against the real private review bundle
    from the 2026-07-30 reproduction run.
  - Corrected one objectively incorrect reference in the Codex activity
    entry below: it listed `PROJECT_SPEC.md` as inspected context, but the
    file has never existed in this repository (verified by `ls` and
    `git log --all -- PROJECT_SPEC.md`). Removed it per the protocol's
    incorrect-reference exception; no other Codex content was altered.
- Files modified:
  - `HANDOFF.md`
- Commands run:
  - `git pull --ff-only` / `git diff --stat 8d4a43d..HEAD`
  - `gh run view 30553535887` (all eight jobs success) and
    `gh run view 30553112414` (success)
  - `uv run pytest --cov=boardgate --cov-branch --cov-fail-under=85`
  - `npm run test:coverage` / `npx vitest run` / `npm run build:check`
  - `npx playwright install chromium` then `npm run test:e2e`
  - One-off Playwright script admitting
    `/Users/matthew/Projects/testruns/PCB/1-verify.review-output` via
    `file://` with request/console monitoring
- Tests:
  - Python: 559 passed, 89.69% branch coverage — matches the Codex report.
  - Viewer: 118 passed, 1 skipped (opt-in private-scale), 87.01% branch
    coverage — matches; deterministic build check passed.
  - E2E: 12/12 passed across Chromium, Firefox, and WebKit. An initial
    4-failure chromium run was a local environment gap (missing
    chromium-headless-shell-1234 binary), resolved by
    `npx playwright install chromium`; not a code defect.
  - Real-bundle smoke: admission succeeded with the correct
    `prj-1c56cfbaab10d74b` / NOT_READY_FOR_FABRICATION summary, zero remote
    requests, zero console errors.
- Commit: `4ef4916 docs(handoff): verify viewer loader foundation round`
- Issues created or updated: None. The Codex-reported 225.6 MiB
  three-engine admission timings could not be independently reproduced (the
  private bundle was not available to this reviewer) and are retained as
  Codex evidence only. Open set remains ISSUE-002, ISSUE-005, ISSUE-007 —
  all low, non-blocking.
- Remaining uncertainty: SVG rendering, layer toggles, and Finding-ID focus
  are intentionally unimplemented; the private-scale opt-in test requires a
  large local bundle to run.
- Recommended next action: Implement Phase 11 validated SVG exploration (see
  Next Action).

### 2026-07-30T22:45:40+08:00 — Codex — Phase 11 offline Viewer loader foundation

- Role: primary implementation and verification agent
- Task: Implement ADR 0006's first Phase 11 slice: exact six-artifact
  offline admission, bounded validation, and a read-only project/status
  summary, then update HANDOFF without expanding into SVG exploration.
- Context inspected:
  - `BOOTSTRAP.md`, `HANDOFF.md`,
    `IMPLEMENT_PCB_AGENT.md`, ADR 0006, the six public Schemas, Python
    `validate_artifact_bundle`, canonical serializers and identifier helpers,
    report/SVG/log validators, CI, dependency notices, the existing fixture
    corpus, git/remote state, and the untracked private real-scale Bundle.
- Actions performed:
  - Added the locked Node/TypeScript toolchain and deterministic build that
    compiles standalone Ajv validators, bundles a classic Worker and main
    application into one tracked HTML file, inlines license notices, and
    verifies exact CSP hashes and byte reproducibility.
  - Implemented exact directory-selection normalization, viewer-policy 1.0,
    fatal UTF-8 and bounded canonical JSON parsing, strict Schema and semantic
    validation, Python-compatible stable-ID reconstruction, report/SVG/log
    checks, and the public `admitBundle` contract.
  - Implemented fresh Worker lifecycle management, transferable immutable
    byte snapshots, stable non-leaking errors, neutral replacement behavior,
    and the text-only summary UI without `innerHTML`, network, browser
    storage, writable handles, review invocation, or bundle mutation.
  - Added a shared TS/Python mutation corpus, unit/resource-boundary tests,
    conditional private-scale admission, three-engine file:// E2E capability
    probes, and independent Viewer CI jobs.
  - Updated the English/Chinese README, capabilities matrix and resource
    policy, and third-party notices without changing Python source, public
    Schemas, `pyproject.toml`, or `uv.lock`.
- Files modified:
  - `.gitignore`, `.github/workflows/ci.yml`
  - `viewer/`
  - `README.md`, `README.zh-CN.md`, `docs/CAPABILITIES.md`,
    `THIRD_PARTY_NOTICES.md`, `HANDOFF.md`
- Findings:
  - `[CONFIRMED]` Vitest 5 was not published in the resolved registry
    (`npm` returned E404), so the lock uses exact Vitest 4.1.10 and matching
    coverage provider; all requested coverage thresholds remain enforced.
  - `[CONFIRMED]` WebKit file:// Workers cannot reliably read structured-cloned
    File/Blob objects (`NotReadableError`); the main thread now snapshots each
    already-size-checked File to ArrayBuffer and transfers ownership to the
    fresh Worker under the same 60-second deadline.
  - `[CONFIRMED]` String-form template replacement reinterpreted JavaScript
    replacement tokens embedded in dependency code and could duplicate HTML
    fragments. The build now uses callback replacement, escapes inline
    `</script`, and checks for exactly one document/script/style plus matching
    CSP hashes.
  - `[CONFIRMED]` Final canonical-number audit found ten Rule Profile float
    property names missing from the explicit Python-float spelling set; all
    were added with individual regression cases.
  - `[CONFIRMED]` Initial Actions run 30552876988 exposed Vitest's default
    10-second asynchronous hook timeout while CI generated two Python fixture
    bundles. Commit 9fcf6b2 gives that bounded setup an explicit 60-second
    hook limit; replacement run 30553112414 passed.
- Verification performed:
  - `uv lock --check`; `uv sync --locked --all-groups`; Ruff format/check;
    mypy; full pytest branch-coverage gate.
  - `npm ci`; Biome format/lint; TypeScript; Vitest coverage; deterministic
    build and CSP check; Playwright Chromium/Firefox/WebKit E2E.
  - Final private-Bundle sequential Chromium/Firefox/WebKit admission and
    summary comparison; `git diff --check`; public/default-branch and remote
    ref checks; Actions runs 30552876988 and 30553112414.
- Tests:
  - Python: 559 passed; 89.69% branch coverage.
  - Viewer unit/parity: 118 passed, one opt-in private-scale test skipped;
    statements 92.14%, branches 87.01%, functions 97.69%, lines 92.02%.
  - Viewer browser: 12 passed across Chromium, Firefox, and WebKit.
  - Private approximately 225.6 MiB Bundle: 5.869/7.483/4.894 seconds with
    identical summary hash and no remote request or console error.
  - CI: run 30553112414 passed all eight jobs after the bounded hook fix.
- Commits:
  - `45f8f76 build(viewer): add reproducible offline toolchain`
  - `7d4c5d7 feat(viewer): validate bounded review bundles`
  - `ad88c44 feat(viewer): render validated review summary`
  - `fd1fe8f ci(viewer): verify offline browsers and parity`
  - `9fcf6b2 test(viewer): bound semantic fixture setup`
  - Branch-tip documentation commit:
    `docs(handoff): record viewer loader foundation`
- Issues created or updated:
  - No new issue. ISSUE-002 and ISSUE-005 remain low/non-blocking and
    unaffected. ISSUE-007 remains open: run 30553112414 confirms the same
    Node 20 deprecation annotations, now also including setup-node@v4 in
    Viewer jobs.
- Remaining uncertainty:
  - SVG insertion, layer controls, Finding-ID focus, Markdown/Finding-list
    presentation, and any HTTP/API/upload/persistence path remain outside
    this slice. The private Bundle remains untracked.
- Recommended next action: Implement Phase 11 validated SVG exploration as
  the sole bounded Next Action above.

### 2026-07-30T16:55:00+08:00 — Claude — ADR 0006 consistency review

- Role: verification agent
- Task: Independently verify the Codex ADR 0006 round (commit 076c6ed)
  against repository evidence and update HANDOFF per BOOTSTRAP.
- Actions performed:
  - Confirmed 076c6ed modifies only `HANDOFF.md` and
    `docs/adr/0006-review-transport.md` — no source, dependency, workflow,
    or Schema changes, matching the Codex delivery report.
  - Read ADR 0006 in full: it follows the ADR 0001–0005 format, records
    rejected alternatives (loopback HTTP adapter, upload/review API,
    mutable catalog, seventh bundle artifact, raw Markdown/SVG trust), and
    states why the offline static viewer cannot mutate deterministic
    evidence (read-only user-selected files, immutable in-memory snapshot,
    no write or analysis transport).
  - Confirmed the Current State correction from five to six checked-in
    public Schemas matches `schemas/v1/`.
  - Re-ran gates and CI queries (see Tests); found no discrepancies with
    the Codex claims.
  - Kept the Codex Next Action (Phase 11 viewer bundle-loader foundation)
    unchanged as the sole bounded next action.
- Files modified:
  - `HANDOFF.md`
- Commands run:
  - `git pull --ff-only` / `git show --stat 076c6ed`
  - `gh run view 30527646931` (all six jobs success)
  - `git rev-parse HEAD origin/main origin/HEAD` (all 076c6ed)
  - `uv run ruff format --check .` / `uv run ruff check .`
  - `uv run python scripts/export_schemas.py` (schemas already current)
  - `uv run pytest -q`
- Tests: 559 passed; Ruff format/check passed; working tree clean.
- Commit: `04a9bbf docs(handoff): verify ADR 0006 transport decision round`
- Issues created or updated: None. Open set remains ISSUE-002, ISSUE-005,
  ISSUE-007 — all low, non-blocking.
- Remaining uncertainty: Viewer bundle-loader budgets and browser
  validation tooling are undecided implementation details of the Next
  Action; a future HTTP transport requires a separate ADR.
- Recommended next action: Implement the Phase 11 offline static viewer
  bundle-loader foundation (see Next Action).

### 2026-07-30T16:38:48+08:00 — Codex — Phase 11 static Viewer boundary

- Role: primary documentation and architecture agent
- Task: Accept ADR 0006 for the bounded Phase 11 transport decision and
  advance HANDOFF to the first implementation slice without writing transport
  code.
- Context inspected:
  - `BOOTSTRAP.md`, `HANDOFF.md`, the Phase 11 scope in
    `IMPLEMENT_PCB_AGENT.md`, ADR 0001 through ADR 0005, the artifact
    validator and review service boundaries, project configuration, public
    Schemas, git history/status/remotes, and the latest GitHub Actions
    evidence.
- Actions performed:
  - Reconciled Current State with repository evidence at baseline 17445dd,
    successful Actions run 30523736566, the public `main` branch, and the six
    checked-in public Schemas.
  - Accepted a separately distributed, offline, read-only static Viewer that
    consumes an explicitly selected exact six-artifact bundle in browser
    memory.
  - Defined fail-closed inventory, Schema, cross-artifact, run-log, and SVG
    admission; exact-byte downloads; untrusted Markdown handling; explicit
    resource budgets; Schema-version rejection without migration; and a
    prohibition on review execution, persistence, Evidence rewriting, remote
    resources, and a seventh bundle artifact.
  - Deferred HTTP transport until remote collaboration justifies a separate
    decision covering authentication, authorization, tenancy, CORS, quotas,
    storage, TLS, immutable review identity, and exact-byte responses.
- Files modified:
  - `docs/adr/0006-review-transport.md`
  - `HANDOFF.md`
- Verification performed:
  - Inspected the exact artifact inventory, public Schema inventory,
    cross-artifact and SVG validation boundary, Phase 11 scope, prior ADR
    constraints, and open issue set.
  - Confirmed the documentation diff contains no source, dependency,
    workflow, Schema, or prior Recent Activity modification.
  - Ran `git diff --check` and a separate read-only ADR/HANDOFF audit.
- Findings:
  - The existing six-artifact contract is sufficient as the Viewer source of
    truth; no seventh artifact or second rule/readiness implementation is
    required.
  - Open ISSUE-002, ISSUE-005, and ISSUE-007 remain low-priority,
    non-blocking, and unchanged.
- Issues created or updated: None.
- Remaining uncertainty: Browser file-selection compatibility, validation
  tooling, and concrete file/total/parse budgets remain implementation
  decisions for the bounded loader slice. Any future HTTP transport still
  requires a separate ADR.
- Recommended next action: Implement the offline static Viewer bundle-loader
  foundation described in the sole Next Action.

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
- Commit: `e2ce101 docs(handoff): verify Codex geometry recovery and
  retarget Phase 11`
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
