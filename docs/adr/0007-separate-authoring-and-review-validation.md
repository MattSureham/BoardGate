# ADR 0007: Separate deterministic PCB authoring and review validation

- Status: Accepted
- Date: 2026-08-03

## Context

BoardGate v0.1 deliberately prioritized trustworthy manufacturing review.
`IMPLEMENT_PCB_AGENT.md` and the public README therefore listed automatic PCB
modification and production Gerber generation as initial-MVP non-goals. That
was a sequencing decision rather than an accepted ADR forbidding authoring.

The product now needs modification and generation as soon as they can be
implemented with evidence comparable to the review system. The current review
architecture cannot simply be made mutable:

- `PCBProject` is a frozen, content-addressed review snapshot whose manifest,
  source IDs, object IDs, and provenance describe immutable input bytes.
- The normalized review IR intentionally omits authoring intent and some
  source syntax. For example, bounded aperture-macro evidence is sufficient
  for conservative review but not lossless Gerber round trips.
- ADR 0002 defines the exact six-artifact review bundle, ADR 0003 prevents an
  agent from altering deterministic facts, ADR 0004 separates all generated
  outputs from inputs, and ADR 0006 keeps the Viewer read-only.
- Gerbonara is verified as a reader adapter, not a lossless writer. In the
  first candidate slice, rewriting a plated Excellon fixture through
  Gerbonara 1.6.3 discarded its explicit plating hint and reparsed as unknown.

The new capability must preserve those guarantees while allowing real design
bytes to change and acquire new identities.

## Decision

### Product scope change

BoardGate will support three sibling capabilities: review, modification, and
generation. This decision supersedes only the previous product-scope deferral
of automatic PCB modification and generation in the initial MVP. ADRs
0001–0006 remain Accepted and normative for their existing boundaries.

`PROJECT_SPEC.md` becomes the forward-looking product specification.
`IMPLEMENT_PCB_AGENT.md` remains the completed v0.1 review implementation
protocol and historical acceptance baseline.

### Separate authoring subsystem

Modification and generation use a separate deterministic authoring subsystem
and application services. They do not add writer behavior to `ReviewService`,
mutate `PCBProject`, edit Findings, or write through the Viewer.

The conceptual flow is:

```text
explicit request / structured requirements / selected review evidence
  -> strict versioned plan
  -> deterministic precondition and authorization checks
  -> registered operation or generator
  -> bounded format-specific emitter
  -> immutable new design payload and new content identities
  -> unchanged ReviewService on the emitted bytes
  -> authoring evidence plus independent six-artifact validation
```

An agent may propose only a schema-valid plan. It cannot write files directly,
execute unregistered operations, reinterpret measurements, or suppress the
review of emitted bytes. Suggested-action prose is never executable input.

### Models and adapters

Authoring has its own strict models for requests, generation requirements,
plans, applied operations, design inventories, and revision evidence. A review
`PCBProject` may provide precondition evidence, but it is never the mutable
authoring state. Each emitted revision is re-ingested and obtains new source,
object, and project IDs.

Format-specific writers or patchers are isolated behind authoring adapters,
parallel to parser adapters under ADR 0001. Third-party objects and Shapely
objects cannot cross their boundary. An adapter advertises a narrow capability
and rejects unsupported syntax rather than approximating it.

The first operation is a versioned, constrained Excellon tool-diameter edit.
It accepts only a confirmed metric, absolute source and a unique tool
definition with an exact expected digest and diameter. The selected tool may
not be used by a routed slot. Because a general third-party rewrite loses
verified source semantics, this operation changes only the uniquely scanned
diameter token. It reparses both versions and proves that the target round-hole
diameter is the only normalized design fact that changed. This operation-
specific byte patch is not a general text-edit facility.

### Output and validation boundary

Authoring never changes input in place. One revision is staged and atomically
published as a separate workspace:

```text
revision/
  design/**
  evidence/request.json
  evidence/result.json
  validation/manifest.json
  validation/project.json
  validation/findings.json
  validation/report.md
  validation/preview.svg
  validation/logs/run.jsonl
```

`design/` contains only emitted project payload. `validation/` remains the
exact ADR 0002 bundle and receives no additional artifact. The two directories
are siblings, satisfying ADR 0004's overlap rule. The authoring evidence binds
the request, before/after identities and digests, operation/adapter version,
payload inventory, and validation project/profile/status.

The existing safe ingestion, logical-path policy, canonical serialization and
hashing, strict models, `OutputTransaction`, and `ReviewService` are shared as
stable infrastructure. Review-scoped Shapely/GEOS workspaces, presentation
models, Viewer state, and NarrativeProvider state are not shared.

### Safety and failure semantics

- Inputs and existing output are immutable unless a complete explicitly
  requested replacement validates and commits.
- A stale digest, mismatched expected value, non-unique target, unsupported
  syntax, parser limitation, operation failure, or semantic postcondition
  failure publishes no revision.
- Unchanged sources must be byte-identical. The emitted source is reparsed and
  compared against explicit operation postconditions before review.
- The emitted project is reviewed from scratch. In the initial contract,
  `ANALYSIS_FAILED` or an invalid nested bundle aborts revision publication.
- A completed review containing blockers may be published and returned as
  blocked evidence. It is not called repaired, ready, or manufacturable.
- Authoring receives independent resource policies before operations expand
  beyond small bounded syntax scans or before native geometry work is added.
- A network-backed plan provider remains outside this decision and still
  requires the security/privacy decision identified by ADR 0003 and ISSUE-005.

### Migration and phased delivery

No existing review model, artifact path, Schema version, CLI `inspect`
behavior, Viewer behavior, or accepted ADR is migrated. New authoring Schemas
and CLI/application entry points are additive.

Delivery proceeds incrementally:

1. strict authoring contracts and this boundary;
2. deterministic constrained operations, beginning with Excellon tool
   diameter;
3. fresh review validation and atomic revision evidence;
4. one constrained structured Gerber/Excellon generator; and
5. broader typed agent-proposed operations and native EDA adapters.

## Alternatives

- **Mutate `PCBProject` and serialize it back to manufacturing files.**
  Rejected because the model is an immutable review snapshot and is not
  lossless authoring state. Its identities and provenance would become false.
- **Add modification/generation stages inside `ReviewService`.** Rejected
  because review must remain an independent validator and its exact output and
  failure semantics are already public contracts.
- **Treat Finding suggestions or free-form agent output as edits.** Rejected
  because prose lacks deterministic targets, stale-value preconditions,
  authorization, and executable postconditions.
- **Perform unrestricted raw text substitutions.** Rejected because arbitrary
  patches cannot prove syntax or semantics. The accepted first operation uses
  one dedicated scanner, one typed token, strict preconditions, and full
  before/after parser comparison.
- **Use a complete Gerbonara rewrite for the first edit.** Rejected until
  round-trip evidence exists; the evaluated version loses explicit Excellon
  plating evidence.
- **Build a separate external product/package.** Considered but rejected for
  now because it would duplicate safe ingestion, units, hashing, transaction,
  and review validation. A sibling package boundary inside BoardGate provides
  separation without duplicating trusted infrastructure.
- **Start with unconstrained Gerber generation or native KiCad/Altium
  authoring.** Deferred because the current repository cannot prove those
  semantics or round trips. A narrow generated board/coupon follows after the
  modification and validation contracts are executable.

## Consequences

BoardGate can add useful authoring operations without weakening review
evidence or Viewer immutability. Each operation has a higher implementation
burden: it needs format-specific preconditions, deterministic emission,
semantic-delta proof, a strict evidence contract, and independent review.

The first revision workspace is larger than a bare project because it includes
request/result evidence and a nested review. That separation is intentional:
the emitted design remains directly usable as fresh review input, while an
engineer can audit exactly what changed and what the unchanged review system
concluded.

General PCB generation remains constrained until writer adapters, authoring
intent models, resource policies, and end-to-end fixtures justify broader
claims. Support will be stated operation by operation rather than inferred
from the existence of an authoring subsystem.
