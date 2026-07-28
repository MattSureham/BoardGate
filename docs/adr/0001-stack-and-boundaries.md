# ADR 0001: Python stack and deterministic boundaries

- Status: Accepted
- Date: 2026-07-28

## Context

BoardGate needs robust Gerber/Excellon ingestion, planar geometry operations,
strict versioned JSON contracts, and a testable command-line workflow.

## Decision

- Use Python 3.12+, uv, a `src/boardgate` package, and Click.
- Use strict Pydantic models at persistence and configuration boundaries.
- Isolate Gerbonara behind adapters; domain and rules must not import it.
- Retain analytic domain primitives and use Shapely only for derived geometry.
- Keep orchestration deterministic and offline in v0.1.

## Alternatives

- A complete in-house CAM parser was rejected for the MVP because its
  compatibility and fixture burden would delay the review pipeline.
- Binding rules directly to Gerbonara or Shapely was rejected because it would
  make provenance, serialization, and future parser replacement fragile.

## Consequences

Gerbonara behavior must be verified with frozen fixtures. Unsupported syntax or
unavailable provenance remains explicit rather than being guessed. Shapely/GEOS
and Gerbonara transitive dependencies must be recorded in dependency notices.
