# Third-party dependency notices

BoardGate is licensed under Apache-2.0. Its Python dependencies retain their
own licenses. The exact resolved dependency graph is recorded in `uv.lock`.

Direct runtime dependencies at the initial baseline:

- Click — BSD-3-Clause
- Gerbonara — Apache-2.0
- jsonschema — MIT
- Pydantic — MIT
- python-calamine — MIT
- PyYAML — MIT
- Shapely — BSD-3-Clause
- GEOS, used by Shapely — LGPL-2.1-or-later

This file is informational and does not replace the license texts distributed
by those projects. If BoardGate later distributes binaries, the release
process must generate and verify a complete notice/SBOM for all transitive
dependencies.
