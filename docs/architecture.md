# Architecture

BoardGate is a CLI-first, offline-capable PCB review and deterministic
authoring system. Review, modification, and generation are distinct
capabilities even when they share safe ingestion, canonical identities, and
atomic output infrastructure.

```text
untrusted inputs
  -> safe ingestion and manifest
  -> parser adapters
  -> versioned BoardGate domain model
  -> normalization and derived geometry
  -> deterministic rule engine
  -> evidence-backed findings
  -> deterministic orchestration, report, and SVG
```

Authoring never mutates that review flow or treats `PCBProject` as an editable
design document:

```text
explicit versioned request
  -> strict admission and applicable base-project identity checks
  -> exact operation registry lookup
  -> bounded deterministic executor/writer adapter
  -> immutable design/ payload
  -> fresh unchanged ReviewService validation
  -> canonical authoring evidence and atomic publication
```

The modification executor performs one same-width Excellon tool-diameter token
replacement. It independently parses before and after emission and proves the
protected drill/slot facts remained unchanged. The generation registry has two
exact operations: `generate_two_layer_coupon/1.0` emits a plated-hole coupon,
and `generate_two_layer_coupon_with_npth/1.0` emits distinct plated and
non-plated drill files without creating NPTH copper pads. Both use bounded
writers, prove operation-specific postconditions by reparsing their payloads,
and send the immutable emitted bytes to the unchanged `ReviewService`. Broader
editing or generation must add its own versioned executor/writer; no registry
falls back to free-form source rewriting.

## Boundaries

- `ingestion` owns archive safety, hashing, and file classification.
- `parsers` isolate Gerbonara, CSV, and XLSX implementation details.
- `domain` owns serializable, versioned models without third-party objects.
- `normalization` owns unit, coordinate, and layer-role evidence.
- `geometry` may use Shapely for derived geometry and spatial queries.
- `rules` makes deterministic decisions and reports explicit coverage.
- `application` coordinates the complete review transaction.
- `authoring` owns strict requests/results, operation-specific bounded
  transforms, semantic postconditions, and content-derived revision evidence.
- application-layer modification and generation registries map exact operation
  kinds and versions to deterministic executors; missing versions never fall
  back.
- `agent` organizes structured results but never replaces measurements.
- `rendering` consumes domain results and is never a rule data source.

Review still publishes exactly its established six artifacts. Modification and
generation publish separate `design/`, `evidence/`, and nested `validation/`
workspaces, never a seventh review artifact and never inside an input project.
Generation establishes only its declared structural and geometric
postconditions; clearances and readiness are evaluated by the explicit review
profile in that nested unchanged review. The Viewer remains read-only. The
core must run without a network connection, an API key, or an LLM.
