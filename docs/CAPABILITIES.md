# BoardGate capability and limitation matrix

BoardGate retains its v0.1 evidence-first review baseline and now includes one
initial deterministic authoring operation. Its Gerber interpretation
targets the RS-274X/X2 semantics documented by Ucamco's
[Gerber Layer Format Specification, revision 2026.05](https://www.ucamco.com/en/guest/downloads/gerber-format).
This target is not a claim of complete format conformance or fabrication
approval.

| Area | Supported in v0.1 | Deliberate boundary |
| --- | --- | --- |
| Inputs | Direct files, directories, and non-nested ZIP archives | No scripts, binaries, encrypted entries, symlinks, or nested archives |
| Gerber | Absolute metric/inch Line, Arc, Flash, Region, polarity, standard apertures, `.FileFunction`, `.SameCoordinates` | Includes and incremental notation are rejected/limited; macro geometry is retained by bounds and excluded from unsupported exact checks |
| Excellon | Absolute round hits and displayed linear/arc slots, tool/unit/format/plating evidence | Routed slots are not treated as round holes by diameter or annular-ring rules |
| Layer mapping | Independent X2, filename, and extension evidence | Conflicts remain `LAYER_MAPPING_UNCERTAIN`; `LayerStack` is not authoritative |
| Outline | Closed analytic Line/Arc topology with nested cutouts | Open, unsupported, or ambiguous topology reduces coverage instead of being repaired |
| Copper rules | Supported standard round-aperture traces; polarity-composed connected geometry | No netlist inference; spacing is between disconnected copper components, not claimed nets |
| Drill alignment | Gross drill-bounding-box versus board-bounding-box mismatch | No pad-to-drill registration claim |
| Annular ring | Confirmed plated round drill with one unique standard round pad flash | NPTH, slots, ambiguous plating, and nonstandard/ambiguous pads are not asserted |
| Mask and silk | Trusted same-side, trusted-polarity overlap/dam checks | Gang openings are not reported as zero-width dams |
| Assembly | BOM/CPL reference reconciliation, duplicates, and CPL anchor containment | No package-body, courtyard, rotation-envelope, or pick-and-place collision inference |
| Evidence | Source SHA, object ID, nullable scanner line/byte span, geometric witness | Scanner alignment can be partial; unavailable source lines remain `null` |
| Derived geometry | One deterministic review-scoped workspace caches geometry, spatial indexes, polarity composition, components, board material, and contributor queries | Versioned resource limits produce explicit coverage gaps; no Shapely object crosses a persistence or worker boundary |
| Rule execution | Built-in rules run in a fresh spawned worker under the remaining review deadline | A timed-out, crashed, invalid, or oversized worker result is discarded and produces the six-artifact `ANALYSIS_FAILED` fallback |
| Visualization | Static, script-free SVG with layers, outline, drills, and Finding IDs | Not a pixel-equivalent CAM renderer and never feeds rule evaluation |
| Offline viewer | Separately distributed, single-file `file://` loader validates an explicitly selected exact six-artifact bundle, displays its original identity, status, counts, risk modes, and safe failure diagnostics, imports a namespace-correct passive preview.svg into a presentation-only DOM copy with layer visibility toggles and Finding-ID focus, renders report.md through a deterministic-subset tokenizer built only with createElement/textContent, and keeps report Finding headings and the preview Finding list on one shared selection state | No upload, persistence, review trigger, evidence write-back, Markdown library/innerHTML rendering, or readiness reinterpretation; interactions change only trusted CSS visibility/classes on the presentation copy, never geometry-defining attributes, selected bundle bytes, or review evidence |
| Narrative | Offline deterministic provider protocol | No network LLM provider or API key support |
| Readiness | Conservative status and explicit partial/skipped/failed coverage | Never a manufacturability guarantee; actual fabricator limits require engineer confirmation |
| PCB modification | Exact `set_excellon_tool_diameter` 1.0 operation on one confirmed warning-free metric/absolute Excellon source; stale base/source identity, old diameter, target tool, and syntax are checked before one same-width token change; before/after parses prove the protected semantic delta; a separate atomic revision includes canonical evidence and a fresh six-artifact review | No in-place edits, raw/free-form patches, arbitrary Gerber/Excellon round trips, tools shared with slots, unsupported tool syntax, or inferred design intent; request/profile files and non-design siblings are rejected from v1 design inputs |
| PCB generation | Exact `generate_two_layer_coupon` 1.0 requirements contract: one bounded metric rectangular two-layer coupon with explicit plated round holes, explicit pad diameters, and explicit straight round-aperture traces; the single registered deterministic executor emits X2 top/bottom copper, a rectangular outline, and a plated Excellon drill payload, reparses every emitted file, and proves the exact requested semantics before a separate atomic revision publishes canonical evidence plus a fresh six-artifact review | No free-form writer path, schematic synthesis, arbitrary placement/routing, slots, vias, non-round apertures, or native EDA authoring; the pinned normative disclaimer states that generation does not guarantee manufacturability or replace fabricator and engineer approval |

## Bounded derived geometry policy

Policy version 1.0 is serialized in `findings.json` and fixes the following
inclusive limits:

| Resource | Limit |
| --- | ---: |
| Parsed primitives per layer | 50,000 |
| Parsed primitives per review | 150,000 |
| Derived coordinates per layer | 1,500,000 |
| Spatial-intersection candidates per layer | 1,000,000 |
| Primitives per connected subset | 4,096 |
| Inputs per union batch | 128 |
| Component-pair candidates per review query | 250,000 |

The 1,000,000 intersection-candidate limit is shared per layer. Policy 1.0
uses fixed named allocations: 32% for layer composition; 20% for trace
contributors; 12% for copper-spacing contributors; 8% each for copper-edge
and solder-mask-dam contributors; and 4% each for the three silkscreen
contributor scopes and the two annular-ring scopes. Deterministic
largest-remainder rounding makes the allocations sum exactly to the configured
per-layer maximum. A layer/scope permits one witness batch per review
(identical repeats use the cache); a distinct second batch is rejected before
querying, so rules cannot reset or acquire this budget according to execution
order.

Equality is allowed; only exceeding a limit reduces coverage. A rule that
evaluates some applicable scope reports `PASS` or `FINDINGS` with `PARTIAL`
coverage. If every applicable scope is limited, it reports `SKIPPED` with
`NONE` coverage and `COMPUTATION_LIMIT`. Each structured coverage gap records
the affected source or layer, observed value, limit, and policy version, and
adds the `ANALYSIS_LIMITATION` risk mode without inventing a hardware Finding.

A wall-clock timeout has different semantics: the spawned rule worker's normal
result is discarded in full, BoardGate publishes the validated six-artifact
`ANALYSIS_FAILED` fallback, and the CLI exits 3. No hardware-dependent partial
result is recovered from an unresponsive worker.

Parser and rule limitations are also emitted in each `report.md`, including
static v0.1 scope boundaries even when a particular input produces no dynamic
parser diagnostic.

## Deterministic authoring policy

Modification requests are strict JSON capped at an inclusive 1 MiB and must
explicitly declare request and operation version 1.0. The operation registry
has no version fallback. Stable revision identity uses only structured
operation evidence, base/output project IDs, and content hashes; free-form
instruction wording is retained in request evidence but cannot change the
revision ID.

The Excellon diameter adapter policy 1.0 admits at most 50 MiB, 1,000,000
lines, 4,096 bytes per line, and 1,024 tool definitions. Equality is allowed;
N+1 fails before emission. Only a plain `TnnC<fixed-width-decimal>` definition
is patched, without changing source length or downstream byte spans. The
changed file is reparsed and all non-target drill/slot facts are compared
before the unchanged project review pipeline runs.

The revision workspace contains exactly:

```text
design/                 confirmed fabrication/assembly payloads
evidence/request.json   canonical admitted request
evidence/result.json    before/after and validation evidence
validation/             exact existing six-artifact review bundle
```

Symlinks, non-regular nodes, extra files/directories, digest/ID/span
mismatches, `ANALYSIS_FAILED`, and invalid nested review evidence prevent
publication. A completed blocker result is retained truthfully and returns
exit 1; it is not called a repair or fabrication approval.

Generation requests are strict JSON capped at an inclusive 1 MiB and must
explicitly declare request and operation version 1.0; the generator registry
has no version fallback and no free-form writer path. Stable generation
identity uses only the structured operation digest (excluding instruction
prose) and the output project ID derived from the emitted payload hashes.

The two-layer coupon writer policy 1.0 admits board dimensions from 1.0 to
500.0 mm, feature coordinates and sizes up to 500 mm, at most 1,024 holes,
and at most 4,096 traces. Equality is allowed; N+1 fails before emission.
Every value must be an exact multiple of the 0.000001 mm emission quantum,
each pad must exceed its drill, pad circles must fit inside the outline,
drill circles must not overlap, and trace endpoints must lie inside the
outline. Each emitted payload is capped at an inclusive 1 MiB. Every emitted
file is reparsed by the unchanged bounded parsers and compared against the
requested holes, pads, traces, and rectangle before the unchanged project
review pipeline runs on the generated design; the revision workspace layout
and publication rules are identical to modification.

## Offline viewer admission policy

The Phase 11 loader is distributed separately as
`viewer/boardgate-viewer.html`; it never becomes a seventh review artifact.
Each directory selection is treated as a new immutable in-memory snapshot.
The previous summary and validation worker are discarded before admission
begins, and the viewer never requests a writable file-system handle, browser
storage, network access, or a review-service channel.

Admission requires exactly one each of `manifest.json`, `project.json`,
`findings.json`, `report.md`, `preview.svg`, and `logs/run.jsonl`, with their
case-sensitive safe POSIX paths intact. It validates canonical UTF-8 JSON,
Draft 2020-12 schemas, model semantics, stable and cross-artifact identities,
report/SVG Finding metadata, a namespace-correct passive SVG/XML vocabulary,
and one ordered run log. The SVG subset contains BoardGate's static renderer
elements plus bounded local gradient paint definitions; declarative animation,
authored CSS, foreign namespaces, unsupported elements or attributes, and
external or non-paint references are rejected. Any inventory, resource,
schema, semantic, identity, or active-content error fails closed before a
project summary is displayed.

Viewer resource policy 1.0 uses inclusive limits:

| Resource | Limit |
| --- | ---: |
| `manifest.json` | 4 MiB |
| `project.json` | 256 MiB |
| `findings.json` | 256 MiB |
| `report.md` | 32 MiB |
| `preview.svg` | 128 MiB |
| `logs/run.jsonl` | 16 MiB |
| Complete bundle | 384 MiB |
| JSON nesting depth | 64 |
| JSON containers plus members/elements | 8,000,000 |
| SVG elements | 250,000 |
| SVG attributes | 2,000,000 |
| One JSONL line | 1 MiB |
| JSONL events | 10,000 |
| report.md lines | 200,000 |
| Fresh validation-worker deadline | 60 seconds |

Equality is accepted; the first event beyond a discrete limit is rejected.
After admission the viewer imports the validated `preview.svg` into a
presentation-only DOM copy, offers per-layer visibility checkboxes, and
focuses the marker matching a selected Finding ID. It also renders `report.md`
through a small line-oriented tokenizer limited to the deterministic
BoardGate report subset (ATX headings up to level four, paragraphs, two-space
nested lists, and `**bold**` inline segments) with composer backslash escapes
reversed; unknown structures fall back to literal paragraphs and HTML comment
metadata is not displayed. All DOM is built with createElement/textContent —
no Markdown library, no innerHTML — so report content cannot execute,
navigate, or embed active content. Finding-ID headings in the rendered report
are activatable buttons: selecting a Finding from the report or from the
preview Finding list focuses the same preview marker and keeps the pressed
state of both button sets in sync. These controls change only trusted CSS
visibility and class state on the presentation copy; geometry-defining
attributes and selected bundle bytes remain unchanged, and no Finding or rule
result is recomputed.
