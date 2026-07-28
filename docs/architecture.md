# Architecture

BoardGate is a CLI-first, offline-capable PCB manufacturing review pipeline.

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

## Boundaries

- `ingestion` owns archive safety, hashing, and file classification.
- `parsers` isolate Gerbonara, CSV, and XLSX implementation details.
- `domain` owns serializable, versioned models without third-party objects.
- `normalization` owns unit, coordinate, and layer-role evidence.
- `geometry` may use Shapely for derived geometry and spatial queries.
- `rules` makes deterministic decisions and reports explicit coverage.
- `application` coordinates the complete review transaction.
- `agent` organizes structured results but never replaces measurements.
- `rendering` consumes domain results and is never a rule data source.

The core must run without a network connection, an API key, or an LLM.
