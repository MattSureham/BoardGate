# BoardGate v0.1 capability and limitation matrix

BoardGate v0.1 is an evidence-first review aid. Its Gerber interpretation
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
| Visualization | Static, script-free SVG with layers, outline, drills, and Finding IDs | Not a pixel-equivalent CAM renderer and never feeds rule evaluation |
| Narrative | Offline deterministic provider protocol | No network LLM provider or API key support |
| Readiness | Conservative status and explicit partial/skipped/failed coverage | Never a manufacturability guarantee; actual fabricator limits require engineer confirmation |

Parser and rule limitations are also emitted in each `report.md`, including
static v0.1 scope boundaries even when a particular input produces no dynamic
parser diagnostic.
