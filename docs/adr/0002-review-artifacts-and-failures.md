# ADR 0002: Complete review artifacts and failure semantics

- Status: Accepted
- Date: 2026-07-28

## Context

Phase 9 must publish a review as one recoverable directory. A caller must be
able to distinguish an engineering finding from an unavailable analysis, and
must never need terminal output or an exception traceback to understand why a
run failed. Repeated review runs also need a precise byte-stability boundary.

Safe ingestion is the first point at which BoardGate has a validated,
content-addressed input inventory. Before that point there is not enough
evidence to construct truthful project artifacts.

## Decision

### Complete bundle

After safe ingestion succeeds, BoardGate publishes all or none of exactly these
six files:

| Logical path | Contract | Byte stability |
| --- | --- | --- |
| `manifest.json` | Strict `ProjectManifest` JSON | Deterministic |
| `project.json` | Strict `PCBProject` JSON | Deterministic |
| `findings.json` | Strict `ReviewResult` JSON | Deterministic |
| `report.md` | Deterministic engineer-facing projection | Deterministic |
| `preview.svg` | Safe standalone deterministic projection | Deterministic |
| `logs/run.jsonl` | Strict ordered `RunLogEvent` stream | Run-varying |

The first five files must be byte-identical for the same normalized inputs,
profile, implementation version, and deterministic narrative provider. Run
identifiers, timestamps, and elapsed durations occur only in
`logs/run.jsonl`. JSON model artifacts use sorted keys, UTF-8, finite numbers,
and one terminal newline. A run log may vary between executions, while each
individual event still uses deterministic JSON key ordering.

Before publication, BoardGate validates the exact inventory; strict model and
checked-in Draft 2020-12 Schema round trips; project and profile identities;
the flattened Finding identity set; report and SVG Finding references; safe
SVG XML; and a single run identifier with strictly increasing log sequence
numbers. The SVG may use internal fragment references, but it may not contain
scripts, event-handler attributes, external URLs, external styles, DTDs, or
entity declarations.

### Sanitized failure evidence

`AnalysisDiagnostic` is a strict versioned domain boundary embedded in
`findings.json`. It records only a stable category, pipeline stage, code, and
short summary. Summaries reject multiline traceback text, exception reprs,
memory addresses, file URIs, and absolute POSIX, Windows, or UNC host paths.
Raw exception messages remain in neither deterministic artifacts nor the run
log.

When ordinary analysis becomes unavailable after safe ingestion:

- `manifest.json` remains the validated source inventory.
- `project.json` is the last validated project snapshot, or a schema-valid
  evidence-only project envelope derived from the manifest and selected
  profile. An evidence-only envelope contains no invented parsed geometry,
  drills, components, or assembly records and must be described as
  unavailable.
- `findings.json` has `overall_status: ANALYSIS_FAILED`, one or more sanitized
  `analysis_diagnostics`, and no fabricated normal `RuleResult` or `Finding`.
- `report.md` renders the unavailable status and diagnostic codes without
  claiming that any rule passed.
- `preview.svg` is a safe standalone failure placeholder when no trustworthy
  geometry exists.
- `logs/run.jsonl` records the run-varying execution sequence.

The fallback bundle is built in the same staging directory and passes the same
complete-bundle validator before atomic publication. If safe ingestion never
succeeds, BoardGate publishes no partial review directory. If fallback
construction or publication itself cannot be validated, the prior output is
preserved.

### CLI exit precedence

Artifact availability does not turn a failed analysis into a successful one.
When more than one terminal condition could apply, the exit decision uses this
precedence:

1. Exit `4` for an unclassified internal failure, including an invalid fallback
   or failed atomic publication for which no trustworthy review can be exposed.
2. Exit `2` for a typed invocation, input-discovery, security-ingestion, or
   rule-profile error.
3. Exit `3` when safe ingestion succeeded but parsing, project construction,
   rule execution, report composition, SVG rendering, or artifact validation
   could not produce a trustworthy normal review. A validated
   `ANALYSIS_FAILED` fallback still exits `3`.
4. Exit `1` only after analysis completed and the selected `--fail-on blocker`
   gate is triggered by a deterministic blocker.
5. Exit `0` after completed analysis when no selected failure gate is
   triggered.

`--fail-on none` disables only exit `1`; it never suppresses exits `2`, `3`, or
`4`.

## Alternatives

- Publishing whichever artifacts existed at the point of failure was rejected
  because consumers could mistake a partial directory for a complete review.
- Converting parser or pipeline failures into ordinary blocker Findings was
  rejected because it fabricates design evidence and conflates tool
  availability with PCB quality.
- Putting timestamps into every artifact was rejected because it destroys
  useful reproducibility without improving evidence.
- Persisting exception strings was rejected because they are unstable and can
  disclose host paths or source details.

## Consequences

Report and SVG implementations must be pure projections of validated models.
The ReviewService must retain enough manifest/profile evidence to construct
the post-ingestion fallback, and it must write every output through the
recoverable staging transaction. Tests compare the five deterministic files
separately from the run log. Future diagnostic fields or artifact paths are
public contract changes and require a schema-version decision.
