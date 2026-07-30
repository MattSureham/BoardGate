# Third-party dependency notices

BoardGate is licensed under Apache-2.0. Its Python dependencies retain their
own licenses. The exact resolved Python dependency graph is recorded in
`uv.lock`.

Direct runtime dependencies at the initial baseline:

- Click — BSD-3-Clause
- Gerbonara — Apache-2.0
- jsonschema — MIT
- Pydantic — MIT
- python-calamine — MIT
- PyYAML — MIT
- Shapely — BSD-3-Clause
- GEOS, used by Shapely — LGPL-2.1-or-later

The separately distributed offline Viewer embeds code from these direct
runtime dependencies. Its exact resolved JavaScript dependency graph is
recorded in `viewer/package-lock.json`:

- Ajv — MIT
- saxes — ISC

Resolved transitive Viewer runtime dependencies:

- fast-deep-equal — MIT
- fast-uri — BSD-3-Clause
- json-schema-traverse — MIT
- require-from-string — MIT
- xmlchars — MIT

Direct Viewer development and verification dependencies (not loaded from the
network by the standalone Viewer at runtime):

- Biome — MIT OR Apache-2.0
- Playwright Test — Apache-2.0
- Node.js type definitions (`@types/node`) — MIT
- Vitest V8 coverage provider — MIT
- TypeScript — Apache-2.0
- Vite — MIT
- Vitest — MIT

This file is informational and does not replace the license texts distributed
by those projects. If BoardGate later distributes binaries, the release
process must generate and verify a complete notice/SBOM for all transitive
dependencies.
