# ADR 0003: Deterministic agent and evidence projections

- Status: Accepted
- Date: 2026-07-28

## Context

Phase 10 needs an agent-shaped orchestration boundary without allowing an LLM
or presentation layer to alter parser facts, geometry, rule outcomes, stable
Finding IDs, or readiness. Report and SVG projections must also be provably
bound to the structured review they display.

## Decision

`DeterministicOrchestrator` creates a profile-bound `ReviewPlan` from the
manifest and the complete built-in rule registry.

- Parser tasks contain exactly the safely classified sources supported by a
  BoardGate adapter. Project construction rejects a plan that omits or adds a
  supported source.
- Every registered rule has an explicit `EXECUTE` or `PROFILE_DISABLED`
  disposition. `RuleEngine` accepts the selected set, retains a `RuleResult`
  for every registry entry, and records an unselected enabled rule as
  `SKIPPED/ORCHESTRATOR_FILTERED`. Filtering therefore cannot make readiness
  appear stronger by deleting a required check.
- Rule applicability, dependency handling, measurements, Findings, and status
  remain responsibilities of deterministic rule code. The orchestrator does
  not duplicate them.

After rule execution, the orchestrator returns the same `ReviewResult` object
alongside a separate `PresentationView`. That view contains only stable Finding
IDs grouped into blocker, high-risk, confirmation, and optimization display
categories.

`NarrativeProvider` is a callable typed protocol. Its request contains existing
Finding IDs and immutable facts; its response may only select those facts by
index. The v0.1 provider is local and deterministic. An exception, malformed
response, unknown ID/fact, identity mismatch, or nondeterministic marker returns
the exact baseline deterministic Markdown bytes. v0.1 has no network provider,
API key, or credential path.

The report includes machine-readable project/profile markers, and the SVG root
includes equivalent attributes. Complete-bundle validation checks those
markers, every Finding ID, canonical risk aggregation, source/layer evidence,
and recomputed source/project/Finding IDs before atomic publication. SVG is a
script-free projection and is never an input to a rule.

## Alternatives

- Allowing a provider to author free-form findings was rejected because its
  output could not be traced to deterministic evidence.
- Treating the plan as advisory-only was rejected because it would not actually
  select parser and rule execution.
- Removing filtered rules from `findings.json` was rejected because missing
  results could falsely improve readiness.
- Rendering from third-party parser or Shapely objects was rejected because it
  would bypass the normalized domain boundary.

## Consequences

The production review path remains offline and reproducible. New parser or rule
types require an explicit plan mapping and tests. A future network-backed
provider must satisfy the same typed response validation and exact fallback
behavior, and would require a separate security and privacy decision.
