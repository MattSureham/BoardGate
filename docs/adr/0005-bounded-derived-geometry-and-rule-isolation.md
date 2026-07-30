# ADR 0005: Bounded derived geometry and isolated rule execution

- Status: Accepted
- Date: 2026-07-30

## Context

PCB review rules derive polygonal geometry from analytic Gerber primitives.
Several rules need the same per-layer geometry, connected components, spatial
index, board material, and source-contributor queries. Rebuilding those
objects independently is expensive, while an unrestricted GEOS operation can
consume the whole review deadline without giving Python an opportunity to
cancel it.

BoardGate must remain deterministic and evidence-first at realistic board
scale. Resource exhaustion is an analysis limitation, not evidence that a PCB
violates a manufacturing requirement. Conversely, a wall-clock timeout cannot
publish partially evaluated hardware conclusions as if the rule set completed.

## Decision

### Review-scoped derived geometry

Each review creates one `DerivedGeometryWorkspace` and shares it across all
rule contexts. It owns every Shapely geometry and spatial index; no Shapely
object crosses the domain, persistence, or worker-process boundary.

The workspace caches primitive derivation, deterministic STRtree indexes,
polarity composition, connected components, board material, and contributor
queries. Connected subsets are discovered in stable primitive order, and
unions use stable, bounded batches instead of repeatedly unioning an entire
layer. Rules consume those cached products and retain analytic BoardGate
objects as their serialized evidence.

### Versioned resource policy

Derived geometry uses a fixed policy version recorded in `findings.json`.
Policy version 1.0 has these inclusive limits:

| Resource | Limit |
| --- | ---: |
| Parsed primitives per layer | 50,000 |
| Parsed primitives per review | 150,000 |
| Derived coordinates per layer | 1,500,000 |
| Spatial-intersection candidates per layer | 1,000,000 |
| Primitives per connected subset | 4,096 |
| Inputs per union batch | 128 |
| Component-pair candidates per review query | 250,000 |

An observed value equal to its limit is allowed. Only a value greater than the
limit causes a degradation.

The 1,000,000 spatial-intersection candidates are one per-layer inventory, not
a fresh allowance for every STRtree query. Policy 1.0 partitions that inventory
into stable named scopes: layer composition 32%, trace contributors 20%,
copper-spacing contributors 12%, copper-edge contributors 8%, solder-mask-dam
contributors 8%, and 4% each for silkscreen copper, mask, and silkscreen
contributors plus annular-ring drill candidates and pad interference. Integer
limits use deterministic largest-remainder allocation, so their sum is exactly
the configured per-layer maximum. Each layer/scope accepts one deterministic
witness batch per review; an identical call is cached, while a distinct second
batch is rejected before another spatial query. Rule order therefore cannot
claim unused budget on a first-come basis or reset the per-layer cap.

A bounded degradation is represented by a structured `RuleCoverageGap` with
the policy version, source or layer, observed value, and limit. If some
applicable scope is evaluated, the rule returns `PASS` or `FINDINGS` with
`PARTIAL` coverage. If no applicable scope can be evaluated, it returns
`SKIPPED` with `NONE` coverage and reason `COMPUTATION_LIMIT`. Any coverage gap
adds the `ANALYSIS_LIMITATION` risk mode. It does not create a fabricated
manufacturing Finding.

### Isolated default rule evaluation

The production `ReviewService` evaluates the built-in rule registry in a fresh
spawned worker. The parent and worker exchange BoardGate's canonical JSON
models through a private temporary directory and a small typed control
envelope. The parent enforces the remaining review deadline, validates a
bounded result, terminates and then kills an unresponsive worker if necessary,
and removes the private directory.

If the worker times out, crashes, or returns an invalid or oversized result,
the normal rule result is discarded. The service publishes the existing
six-artifact `ANALYSIS_FAILED` fallback and exits 3. It never publishes
hardware-dependent partial results from a timed-out worker. Ordinary
exceptions from one Python rule remain isolated by `RuleEngine`; explicitly
injected test evaluators retain the synchronous interface and do not claim
process isolation.

## Alternatives

- Recomputing full-layer unions in every rule was rejected because cost grows
  with both rule count and primitive count and prevents cache reuse.
- One unrestricted global union per layer was rejected because a pathological
  connected set can enter an uninterruptible GEOS call.
- Treating a resource limit as a blocker Finding was rejected because the
  limit describes BoardGate's computation, not the board.
- Returning completed rule prefixes after a wall-clock timeout was rejected
  because rule order would determine which hardware claims survived.
- Thread cancellation was rejected because it cannot reliably interrupt a
  native GEOS call in the same process.

## Consequences

Resource-policy changes are public deterministic-contract changes: they
require a new policy version, Schema and report updates, and boundary tests.
Rules that use derived geometry must use the shared workspace so budgets,
ordering, cache scope, and provenance remain consistent.

Spawn isolation adds serialization and process-start overhead, including on
Windows and macOS. CI therefore runs a complete fixture review on all three
operating systems and asserts the actual interpreter for each declared Python
test matrix entry. Temporary model exchange remains private and bounded, and
Shapely/GEOS state is always reconstructed inside the worker.
