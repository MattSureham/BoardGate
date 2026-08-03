# BoardGate Project Specification

## Status and precedence

This document is the forward-looking product specification for BoardGate.
`BOOTSTRAP.md` remains the normative collaboration protocol. The accepted
architecture decision records remain normative for their respective
boundaries. `IMPLEMENT_PCB_AGENT.md` remains the implementation and acceptance
protocol for the completed v0.1 manufacturing-review foundation; where that
document deferred PCB modification or generation as an initial-MVP non-goal,
this specification and ADR 0007 supersede that scope deferral for subsequent
phases.

Safety, preservation of user work, explicit evidence, and accepted ADRs take
precedence over feature breadth. `HANDOFF.md` records the currently verified
implementation state and the one immediate next action; it does not silently
change this product scope.

## Product definition

BoardGate is an evidence-first PCB engineering system with three distinct
capabilities:

1. **Review** an existing PCB manufacturing or assembly project and publish
   deterministic, traceable findings.
2. **Modify** a new revision of an existing project from an explicit,
   validated change request or from explicitly selected review evidence.
3. **Generate** a new PCB design or manufacturing artifact set from structured
   requirements when the requested semantics are inside a declared,
   deterministic capability envelope.

Review, modification, and generation may share safe ingestion, normalized
units, provenance, hashing, parser/writer adapters, atomic output mechanics,
and review validation. They must not share mutable evidence or collapse into a
single pipeline. In particular, a review snapshot is not an editable design
document, a Finding suggestion is not an executable edit, and an agent's
narrative is not a fabrication writer.

## Cross-capability principles

- The deterministic core must run offline without an LLM or API key.
- All source files, requirements, plans, and provider responses are untrusted.
- Inputs are immutable. Modification and generation always publish to a
  separate output tree through validated staging and recoverable replacement.
- Persisted contracts are strict, versioned, finite, and reject unknown
  fields. Unknown facts remain explicit rather than being guessed.
- Third-party parser or writer objects and Shapely objects never cross a
  public model, persistence, or worker boundary.
- Every engineering claim identifies the input/revision, implementation and
  operation version, applicable configuration, and supporting evidence.
- Resource limits and timeouts describe tool coverage, not PCB quality.
- A completed BoardGate review is evidence for engineer review, not a
  fabrication guarantee.

## Capability 1: review

The existing review system remains the authoritative validation capability.
It safely ingests Gerber, Excellon, BOM, and placement sources; constructs a
content-addressed `PCBProject`; executes deterministic rules; and publishes
exactly the six artifacts defined by ADR 0002.

The review subsystem remains read-only and one-way:

```text
untrusted project files
  -> safe ingestion
  -> parser-independent review snapshot
  -> deterministic rules
  -> Findings and projections
  -> exact six-artifact review bundle
```

Modification and generation must invoke review on newly emitted bytes from
scratch. They may not mutate an existing `PCBProject`, adjust its identifiers,
edit a review bundle, or treat Viewer state as design input.

## Capability 2: modification

### Scope

Modification creates a new, content-addressed design revision from an existing
project. An operation is supported only when BoardGate can prove its target,
preconditions, deterministic byte or semantic transformation, and
postconditions. Operations are registered and versioned individually.

The first supported vertical slice is a constrained Excellon round-drill tool
diameter change. Later candidates include bounded placement-field edits,
explicit layer transformations, and edits through native EDA adapters. Each
candidate requires its own capability and round-trip evidence; support for one
operation does not imply general Gerber, Excellon, or EDA editing.

### Inputs

- one safely ingestible base project;
- a strict, versioned modification request;
- the expected base project identity and target source identity/digest;
- operation-specific expected old values and new values;
- an explicit manufacturing rule profile for validation; and
- when a review Finding is used as the basis, the exact admitted review
  identity and selected Finding identifiers.

Natural-language instructions or provider output must first be converted to a
strict plan and explicitly authorized. They are never executed directly.

### Interfaces

The application interface is a dedicated modification service. The CLI form is
initially:

```bash
pcb-review modify INPUT... \
  --request CHANGE_REQUEST.json \
  --rules RULE_PROFILE \
  --output REVISION_DIRECTORY \
  [--overwrite]
```

The service accepts typed request/profile objects and paths. It does not call
the Viewer, parse suggested-action prose, or enter `ReviewService` until a new
design payload has been deterministically emitted and reparsed.

### Outputs

A revision is a separate atomic workspace, not a seventh review artifact:

```text
REVISION_DIRECTORY/
  design/                    emitted manufacturing/assembly payload only
  evidence/request.json      canonical validated request
  evidence/result.json       before/after digests and operation evidence
  validation/                exact six-artifact review of design/
```

`design/` contains no BoardGate evidence files, and `validation/` contains no
design sources. Evidence records the base and output project IDs, request
digest, old/new source IDs and hashes, affected objects, operation version,
writer/patch adapter version, output inventory, and validation status.

### Validation requirements

Before a modification is applied, BoardGate must prove:

- the safely rebuilt base manifest matches the request;
- the target source and expected digest are exact and unique;
- all operation-specific syntax and semantic preconditions hold;
- the expected old value matches parsed evidence; and
- the requested value is finite, bounded, and different.

After emission, BoardGate must reparse the changed source and prove the
operation-specific semantic delta while all protected facts remain equal.
Unchanged sibling files must remain byte-identical. It then rebuilds the
manifest and invokes the unchanged review pipeline on `design/`. A revision is
published only after its own cross-file evidence and nested review bundle are
validated.

### Failure behavior

- Invalid request, stale identity, missing/ambiguous target, or precondition
  mismatch: reject without publishing a revision.
- Unsupported syntax, operation capability gap, parser/writer failure, or
  failed semantic postcondition: fail closed without publishing.
- Review `ANALYSIS_FAILED`, invalid nested artifacts, or revision publication
  failure: publish no revision in the initial implementation.
- A completed review with blockers may be published as truthful evidence and
  must return the blocker gate status; it must not be described as repaired or
  fabrication-ready.
- Existing output is preserved unless an explicitly requested atomic
  `--overwrite` transaction validates and commits completely.

## Capability 3: generation

### Scope

Generation creates a new design revision from structured requirements, without
pretending that unsupported electrical or mechanical intent was inferred. A
generator declares its exact requirement schema, design semantics, emitted
formats, resource policy, and validation coverage.

The first generator is implemented as a constrained metric, rectangular
two-layer fabrication project/coupon with explicit dimensions, supported
standard apertures, plated round holes, and straight traces. Exact operation
`generate_two_layer_coupon/1.0` emits deterministic Gerber/Excellon through
bounded writer adapters and is accepted as fresh input by the existing review
pipeline.

The exact registered extension
`generate_two_layer_coupon_with_npth/1.0` adds a separate non-plated round-hole
set. It requires at least one plated hole with an explicit copper-pad diameter
and at least one non-plated hole without a pad, permits at most 1,024 holes in
the two sets combined and at most 4,096 traces, and emits separate explicitly
`PLATED` and `NON_PLATED` Excellon payloads. The generator proves its declared
geometry and format semantics; manufacturing clearances and readiness remain
decisions of the explicitly selected review profile in the subsequent
unchanged `ReviewService` run.

### Expected inputs and outputs

Inputs are strict structured requirements such as board dimensions, supported
layer stack, explicit copper primitives, hole definitions, and the separate
manufacturing profile used for review. The NPTH operation accepts
`plated_holes` containing x/y position, drill diameter, and pad diameter, and
`non_plated_holes` containing only x/y position and drill diameter. It does not
infer or emit a copper pad for an NPTH hole.

Outputs use the same separated revision workspace shape as modification, with
canonical generation requirements/plan evidence in place of a base-project
change request. The NPTH operation emits five design files: X2 top and bottom
copper, a rectangular outline, a plated Excellon file, and
`coupon-non-plated.drl` with explicit non-plated semantics.

Every generated source and object receives new content-derived identity and
generation provenance. Generated files are never injected into or represented
as an existing review bundle.

### Non-goals until separately specified

- inferred schematic capture, circuit synthesis, or proof of electrical
  correctness;
- unconstrained autorouting, placement optimization, impedance, SI, or PI;
- lossless editing of arbitrary Gerber, Excellon, KiCad, or Altium projects;
- arbitrary aperture-macro synthesis, ODB++, or IPC-2581 authoring;
- slots, vias, non-round holes, or general-purpose EDA authoring;
- autonomous production release or fabricator submission; and
- direct file writes by an LLM or network provider.

## Agent and tool boundaries

An agent may organize evidence and propose a strict modification or generation
plan. A deterministic planner validates identity and preconditions; a
registered deterministic executor performs the operation; a bounded adapter
emits bytes; and review independently evaluates the emitted project.

```text
explicit instruction / structured requirements / selected Findings
  -> versioned proposed plan
  -> deterministic plan admission and authorization
  -> registered operation or generator
  -> immutable new design payload
  -> fresh existing review
  -> revision evidence and engineer decision
```

Provider output cannot introduce unregistered operation kinds, alter measured
values, suppress Findings, choose unstated defaults, or claim readiness.
Network-backed providers remain subject to a separate security/privacy ADR.

## Traceability requirements

Modification and generation evidence must be sufficient to reproduce and
audit a revision without chat history. At minimum it records:

- canonical request/requirements digest and operation/generator version;
- base project/source identities where applicable;
- exact target and precondition evidence;
- before/after source digests and changed-object correspondence;
- complete output design inventory and content hashes;
- deterministic adapter and BoardGate implementation versions;
- nested review project/profile identities and original overall status; and
- explicit limitations, confirmations, and any remaining/new Findings.

Stable revision/change IDs are derived from canonical evidence, not time,
filesystem location, agent wording, or run IDs. Run-varying diagnostics remain
separate from deterministic evidence.

## Incremental delivery phases

### Phase A — authoring architecture and contracts

- Accept ADR 0007 and this project specification.
- Add strict request/result, operation registry, revision ID, and workspace
  contracts without changing the review bundle.
- Reuse safe ingestion and atomic publication through explicit adapters.

### Phase B — deterministic modification operations

- Deliver one operation at a time with precise format/precondition scope.
- First slice: change one supported metric absolute Excellon tool diameter,
  preserve all unrelated bytes, and prove the parsed semantic delta.
- Add stale-input, ambiguity, unsupported-syntax, and rollback tests.

### Phase C — independent review validation

- Re-ingest each emitted `design/` from bytes and run `ReviewService` fresh.
- Bind the revision evidence to the new project/profile/status and exact nested
  six-artifact bundle.
- Prove a before-review Finding can be resolved without hiding new Findings.

### Phase D — constrained structured generation

- **Implemented:** one narrow requirements schema and deterministic
  Gerber/Excellon writer envelope.
- **Implemented:** generation of an original minimal two-layer rectangular
  project followed by validation through the existing review pipeline.
- **Implemented:** equality/boundary, reproducibility, and resource-limit
  evidence for `generate_two_layer_coupon/1.0`.

### Phase E — broader agent-driven authoring

- **Implemented:** the first exact registered extension,
  `generate_two_layer_coupon_with_npth/1.0`, adds separately emitted and
  validated plated and non-plated round-hole sets.
- **Implemented:** the typed authoring-plan admission boundary admits exactly
  one registered modification or generation kind/version through
  `AuthoringPlan`/`PlanAuthorization` 1.0 contracts, a checked-in Draft
  2020-12 Schema, bounded duplicate-safe plan JSON loading, and deterministic
  admission that recomputes the request and structured-operation digests plus
  a separate approver-bound authorization digest. Plan prose cannot execute,
  alter operation fields, select unknown versions, suppress fresh review, or
  write design bytes directly.
- Add more registered operations and native EDA adapters only with round-trip
  evidence.
- Permit agents to propose typed plans, with explicit approval and deterministic
  execution.
- Evaluate remote collaboration/providers only after authentication, privacy,
  data-egress, quota, and determinism decisions.

## Acceptance standard

A phase is complete only when the capability executes end to end, strict
contracts and failure paths are tested, emitted bytes and evidence are
traceable, validation is performed where required, documentation and HANDOFF
are current, and coherent commits exist. Interfaces or TODO-only scaffolding
do not constitute implementation.
