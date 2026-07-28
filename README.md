# BoardGate

[中文说明](README.zh-CN.md)

BoardGate is an evidence-first, deterministic PCB manufacturing review agent.
It is designed to ingest fabrication and assembly files, normalize them into a
versioned project model, run reproducible DFM checks, and produce structured
findings, a Markdown report, and an SVG preview.

The project follows one hard boundary: parsers, measurements, and rule
decisions are deterministic. Agent orchestration may organize and explain
those results, but it must not invent geometry, manufacturing intent, or a
production-readiness guarantee.

## Status

BoardGate is under active development toward the v0.1 CLI MVP described in
[`IMPLEMENT_PCB_AGENT.md`](IMPLEMENT_PCB_AGENT.md). Verified repository state
and the exact next action are maintained in [`HANDOFF.md`](HANDOFF.md).

## Development

Prerequisites:

- Python 3.12 or newer
- uv 0.11.x

```bash
uv sync --locked
uv run pcb-review --version
uv run pytest
```

The target review interface is:

```bash
pcb-review inspect INPUT... \
  --rules rules/default.yaml \
  --output artifacts/review
```

## Safety and scope

All input files are treated as untrusted. A BoardGate report is engineering
review evidence, not a fabrication warranty. The initial MVP intentionally
excludes native EDA projects, ODB++, IPC-2581, SI/PI analysis, automatic PCB
modification, a web API, and network-backed LLM providers.

## Collaboration

Every participant must read and follow [`HANDOFF.md`](HANDOFF.md) before
changing the repository. It is the canonical collaboration state; repository
evidence takes precedence over chat history or summaries.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
