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

- Last updated: `2026-07-28T16:58:22+08:00`
- Repository: `[CONFIRMED] https://github.com/MattSureham/BoardGate`
- Visibility: `[CONFIRMED] PUBLIC`
- Branch: `[CONFIRMED] main`
- HEAD: `[CONFIRMED] 1494432 feat(cli): emit validated project manifests`
- Phase: `[CONFIRMED] Phase 3 in progress — parsing and normalization`
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
  - `[CONFIRMED] Restricted YAML/JSON loader and four checked-in Draft
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
- Supported inputs: `[CONFIRMED] Directories, ZIP archives, and one or more
  regular files; Gerber, Excellon, BOM/placement CSV, BOM XLSX, rule profiles,
  and unknown files receive evidence-backed manifest classifications.
  Excellon round hits and routed slots are normalized to millimetres.`
- Implemented rules: `[CONFIRMED] None yet.`
- Verification:
  - `[CONFIRMED] gh repo view reported PUBLIC visibility.`
  - `[CONFIRMED] uv lock --check resolved 50 packages.`
  - `[CONFIRMED] uv run ruff format --check . passed.`
  - `[CONFIRMED] uv run ruff check . passed.`
  - `[CONFIRMED] uv run mypy src tests passed (53 source files).`
  - `[CONFIRMED] uv run pytest --cov=boardgate --cov-branch
    --cov-fail-under=85 -q passed: 124 tests, 91.04% coverage.`
- Known limitations:
  - `[CONFIRMED] The current CLI slice still emits only manifest.json; Gerber,
    BOM/CPL, rule execution, complete diagnostics, rendering, and review
    orchestration remain unimplemented.`
  - `[CONFIRMED] Parser timeout isolation is not connected yet.`
- Working tree: `[CONFIRMED] Verified Excellon adapter slice is pending commit.`

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
- Remaining work: Reuse and specialize the scanner for Gerber.
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

## Next Action

Implement the Gerber adapter for analytic primitives and polarity.

Start with:

- `src/boardgate/parsers/gerber.py`
- `src/boardgate/parsers/gerber_scanner.py`
- `tests/fixtures/parser/gerber/`
- `tests/unit/parsers/test_gerber.py`

Acceptance criteria:

1. Gerbonara remains behind the adapter and no third-party object escapes.
2. Line, Arc, Flash, and Region plus apertures, units, and polarity normalize
   to BoardGate analytic primitives.
3. X2 FileFunction/SameCoordinates values remain source evidence and are not
   treated as an unquestionable final layer mapping.
4. Macro and unsupported geometry emit explicit limitations.
5. Command spans align where provable and remain `null` otherwise.
6. Golden polarity, macro-limitation, malformed-input, and round-trip tests
   pass before a separate commit.

## Recent Activity

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
- Commit: PENDING (this Excellon commit)
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
