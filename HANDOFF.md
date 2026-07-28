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

- Last updated: `2026-07-28T16:24:03+08:00`
- Repository: `[CONFIRMED] https://github.com/MattSureham/BoardGate`
- Visibility: `[CONFIRMED] PUBLIC`
- Branch: `[CONFIRMED] main`
- HEAD: `[UNKNOWN] This baseline commit is pending; resolve it with
  git rev-parse HEAD after commit.`
- Phase: `[CONFIRMED] Phase 0 complete — repository and quality baseline`
- Entry point: `[CONFIRMED] uv run pcb-review --version`
- Implemented capabilities:
  - `[CONFIRMED] Installable Python package and versioned CLI entry point.`
  - `[CONFIRMED] Locked Python 3.12 development environment and CI gates.`
  - `[CONFIRMED] Repository collaboration protocol and architecture boundary.`
- Supported inputs: `[CONFIRMED] None yet.`
- Implemented rules: `[CONFIRMED] None yet.`
- Verification:
  - `[CONFIRMED] gh repo view reported PUBLIC visibility.`
  - `[CONFIRMED] uv lock --check resolved 50 packages.`
  - `[CONFIRMED] uv run ruff format --check . passed (12 files).`
  - `[CONFIRMED] uv run ruff check . passed.`
  - `[CONFIRMED] uv run mypy src tests passed (4 source files).`
  - `[CONFIRMED] uv run pytest --cov=boardgate --cov-branch
    --cov-fail-under=85 -q passed: 1 test, 100% coverage.`
- Known limitations:
  - `[CONFIRMED] Domain, ingestion, parsers, rules, rendering, and review
    orchestration remain unimplemented.`
- Working tree: `[CONFIRMED] Initial verified baseline is pending commit.`

Current State is the evidence-backed present snapshot. Recent Activity explains
how the repository reached that state and must not be required to understand
the current capabilities.

## Active Issues

### ISSUE-001 — Gerbonara provenance granularity is unverified

- Status: OPEN
- Severity: medium
- Owner: unassigned
- State label: `[CONFIRMED]`
- Context: The selected parser exposes graphical objects but source line/byte
  spans must be verified before they can be attached to findings.
- Evidence: Gerbonara adapter probe has not yet been implemented.
- Suspected cause: The third-party object API may not retain source spans.
- Attempted approaches: None.
- Current resolution state: Track source file and stable object IDs first;
  later add a lightweight command-span scanner without duplicating geometry
  parsing.
- Remaining work: Add frozen fixtures and verify span mapping.
- Relevant files: `IMPLEMENT_PCB_AGENT.md`
- Blocking: No; missing spans must remain explicit `null`.

## Next Action

Implement versioned `Unit`, `Point`, `BoundingBox`, `CoordinateSystem`, and
`Provenance` models with strict JSON round-trip tests.

Start with:

- `src/boardgate/domain/geometry.py`
- `src/boardgate/domain/provenance.py`
- `tests/unit/domain/`

Acceptance criteria:

1. Every public root model carries `schema_version: "1.0"`.
2. Unknown source locations are represented by `None`, never magic values.
3. NaN and infinity are rejected.
4. Coordinates serialize deterministically in millimeters.
5. `uv run pytest tests/unit/domain -q` passes.
6. Commit separately before adding `PCBProject` and `Finding`.

## Recent Activity

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
- Commit: PENDING (this baseline commit)
- Issues created or updated: ISSUE-001
- Remaining uncertainty: Gerbonara source-span behavior remains unverified.
- Recommended next action: Implement strict geometry and provenance models.

## Archived Summary

No activity has been archived. When this document reaches roughly 800–1200
lines, compress closed older activity here while preserving architectural
decisions, unresolved issues, rejected approaches, failed attempts, and
evidence references. Unresolved issues must remain in Active Issues.
