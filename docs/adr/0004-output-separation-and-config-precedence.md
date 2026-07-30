# ADR 0004: Output separation and configuration precedence

- Status: Accepted
- Date: 2026-07-30

## Context

Review artifacts must never mix with user input: anything published inside an
input directory is re-ingested as untrusted input on the next run, polluting
classification and Findings. At the same time, machine-specific absolute
paths (for example a developer's home directory) must not be hard-coded into
the tool or the repository, and every participant — human or AI — needs one
permanent rule instead of per-convention memory.

## Decision

**Strict separation between input artifacts and generated outputs.**

1. Input directories only ever contain user input.
2. All generated content (the six review artifacts, and any future HTML,
   screenshots, or narrative output) is written to a dedicated output
   directory.
3. The output directory must never contain, or be contained by, any input
   path; the existing overlap validation enforces this for every tier below.

**Three-tier output resolution** for `pcb-review inspect`:

```text
--output CLI option
      │ (wins when present)
      ▼
Project config: boardgate.toml in a single directory input
      │ ([review] output = "...", relative paths resolve
      │  against the input directory's parent)
      ▼
Built-in default: sibling <input-name>.review-output
      (archives and files use their stem)
```

- `--output` is no longer required. When several inputs are supplied and no
  `--output` is given, the command fails with exit code 2 instead of
  guessing a location.
- Project configuration uses `boardgate.toml` parsed with the Python
  standard-library `tomllib` (no new dependency). The file is size-bounded,
  strictly validated (unknown fields rejected), and only consulted for a
  single directory input when `--output` is absent. It is never read from
  inside archives.
- Every tier still passes `preflight_output` and
  `reject_output_input_overlap`; a config value that points inside the input
  is rejected with exit code 2.

## Alternatives

- Hard-coding a default absolute path was rejected: it leaks personal
  machine layout into a public tool.
- Defaulting the output inside the input directory was rejected: subsequent
  runs would ingest prior artifacts as inputs.
- YAML project configuration was considered (a restricted YAML loader
  already exists for rule profiles) but deferred: TOML needs no new
  dependency and one config format is easier to keep strict.
- Reading configuration from archives or the process working directory was
  rejected as ambiguous or untrusted.

## Consequences

Each project can carry its own default output location without code changes;
the CLI keeps full override power; future output-producing features must
follow the same separation principle and resolve through the same
precedence. New config keys require an explicit strict-model extension and
tests.
