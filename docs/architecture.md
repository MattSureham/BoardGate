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
  -> safe base-project reconstruction and identity checks
  -> exact operation registry lookup
  -> bounded deterministic executor/writer adapter
  -> immutable design/ payload
  -> fresh unchanged ReviewService validation
  -> canonical revision evidence and atomic publication
```

The first executor performs one same-width Excellon tool-diameter token
replacement. It independently parses before and after emission and proves the
protected drill/slot facts remained unchanged. Broader editing and structured
generation must add their own versioned executors/writers; they cannot fall
back to free-form source rewriting.

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
- the application-layer modification registry maps an exact operation kind
  and version to one deterministic executor; missing versions never fall back.
- `agent` organizes structured results but never replaces measurements.
- `rendering` consumes domain results and is never a rule data source.

Review still publishes exactly its established six artifacts. A modification
publishes a separate `design/`, `evidence/`, and nested `validation/`
workspace, never a seventh review artifact and never inside an input project.
The Viewer remains read-only. The core must run without a network connection,
an API key, or an LLM.
