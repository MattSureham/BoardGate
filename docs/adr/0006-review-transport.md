# ADR 0006: Offline static review viewer transport boundary

- Status: Accepted
- Date: 2026-07-30

## Context

Phase 11 may expose BoardGate review evidence through an HTTP API or a minimal
viewer. The existing application boundary already publishes an atomic,
validated six-artifact bundle. Its first five files are deterministic, while
the run log is the only run-varying artifact. Parser facts, rule outcomes,
Finding identifiers, readiness, reports, and SVG projections are already
bound together by strict models, public Schemas, and cross-artifact
validation.

Adding a transport must not create a second source of truth, let presentation
code reinterpret engineering conclusions, or turn untrusted PCB content into
active browser content. BoardGate must also remain usable offline without a
server, account, credential, API key, or network-backed provider.

## Decision

### Transport selection

The first Phase 11 transport will be a separately distributed, offline static
viewer. The user explicitly selects one existing complete review bundle in
the browser. The viewer reads the selected files into browser memory; it does
not upload them, persist them, invoke `ReviewService`, trigger a new review,
or write into the selected directory.

The viewer is not part of the review bundle. In particular,
`viewer.html`, JavaScript, styles, caches, screenshots, and other presentation
assets must not be added to the exact six-artifact inventory:

```text
manifest.json
project.json
findings.json
report.md
preview.svg
logs/run.jsonl
```

Viewer assets are built and distributed separately. They must work with
network access disabled and must not load code, fonts, telemetry, analytics,
or other resources from a CDN or remote origin.

### Bundle admission

The viewer must fail closed before displaying engineering claims unless all
six logical paths are present exactly once and the complete bundle passes the
browser equivalent of BoardGate's public validation boundary.

That validation includes, where applicable:

- strict JSON and public Draft 2020-12 Schema validation;
- finite values, the exact current `schema_version: "1.0"` contracts, and
  forbidden unknown fields;
- project, profile, source, layer, Finding, and risk-mode consistency;
- exact Finding references in the report and SVG;
- ordered, single-run JSONL log invariants; and
- SVG rejection of scripts, event handlers, `foreignObject`, external
  resources, external URLs, DTDs, and entity declarations.

Missing, extra, malformed, mismatched, oversized, or unsafe inputs produce an
explicit unavailable state. The viewer must not partially render a bundle or
describe an unvalidated rule as passed. A valid `ANALYSIS_FAILED` fallback
bundle remains displayable as failed analysis evidence.

Unknown or newer Schema versions fail closed. The initial viewer performs no
browser-side migration or artifact rewriting; a future version adapter
requires an explicit compatibility decision and must retain the originally
selected bytes.

The implementation must impose explicit browser-side file, total-byte, and
parse-complexity limits before parsing untrusted content. Those limits and
their tests are part of the viewer implementation, not a change to the
canonical review artifact contract.

### Immutable presentation

The viewer may organize only facts already present in the validated bundle.
It may use stable project, profile, layer, and Finding identifiers to:

- present the manifest and review status;
- toggle existing SVG layer groups;
- connect a Finding to an existing `data-finding-id`; and
- offer the originally selected artifact bytes for download.

The viewer must not recompute rules, measurements, risk modes, Finding IDs,
or readiness. It must not modify SVG geometry or save presentation state into
the bundle. Downloads return the original selected bytes, not a reserialized
model or rewritten projection.

Markdown is untrusted text and must not be executed as raw HTML. SVG may enter
an interactive DOM only after the complete bundle and SVG safety checks
succeed. Untrusted strings must be inserted through text-safe DOM operations,
not `innerHTML`.

`project_id` and `profile_sha256` bind evidence; neither is an authorization
secret, tenant identifier, or mutable catalog key.

## Alternatives

- A single-bundle, loopback-only read-only HTTP adapter was considered. It
  could reuse the Python validator directly, but it would add a server,
  filesystem-serving rules, port and lifecycle management, request limits,
  response headers, and a new network attack surface. It is deferred until
  remote or same-origin transport provides enough value to justify those
  costs.
- The Phase 11 `POST /projects` and `POST /projects/{id}/review` sketch was
  rejected for the first slice. Uploads and remote execution require separate
  decisions for authentication, authorization, tenant isolation, CORS and
  CSRF, body and concurrency quotas, private staging, cleanup, persistence,
  TLS, and job status.
- Serving arbitrary host paths or a mutable "latest review" catalog was
  rejected. `project_id` does not include the selected profile, and mutable
  lookup semantics would weaken exact bundle identity.
- Adding generated HTML or viewer assets to the review output was rejected
  because ADR 0002 defines an exact six-file bundle and ADR 0004 requires
  generated output to remain separate from input and other output classes.
- Trusting raw Markdown or SVG, duplicating deterministic rules in
  JavaScript, or allowing presentation edits to flow back into evidence was
  rejected because each bypasses the established evidence boundary.
- A network-backed NarrativeProvider remains outside this decision and
  continues to require the separate security and privacy decision recorded by
  ADR 0003 and ISSUE-005.

## Consequences

The initial viewer has no remote upload, storage, authentication, review
execution, or service availability concern. Loading and viewing a bundle
cannot mutate deterministic evidence because the browser receives read-only
user-selected file objects, retains an immutable in-memory snapshot, and has
no write or analysis transport.

The static approach does require browser-side validation equivalent to the
Python artifact validator and must account for browser file-selection and
memory limits. Viewer implementation must therefore begin with the complete
bundle loader and fail-closed validation foundation before layer controls,
Finding navigation, or report presentation.

A future HTTP transport requires a new ADR. It may be reconsidered only when
remote collaboration or centralized distribution is required and
authentication, authorization, tenancy, CORS, quotas, storage, TLS, immutable
review identity, and exact-byte response semantics have been decided.
