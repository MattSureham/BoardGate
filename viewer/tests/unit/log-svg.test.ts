import { describe, expect, it } from "vitest";

import { VIEWER_RESOURCE_POLICY } from "../../src/policy";
import { AdmissionError } from "../../src/validation/errors";
import { validateRunLog } from "../../src/validation/log";
import type { CrossArtifactEvidence } from "../../src/validation/semantics";
import { validateSvg } from "../../src/validation/svg";
import { validateReport } from "../../src/validation/text";

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

const evidence: CrossArtifactEvidence = {
  projectId: "prj-0000000000000000",
  profileId: "profile",
  profileSha256: "0".repeat(64),
  findingIds: new Set(),
  sourceIds: new Set(),
  layerIds: new Set(),
  layerDetails: [],
  findingDetails: [],
  summary: {
    projectId: "prj-0000000000000000",
    profileId: "profile",
    profileSha256: "0".repeat(64),
    overallStatus: "READY_FOR_REVIEW",
    sourceCount: 0,
    layerCount: 0,
    drillCount: 0,
    slotCount: 0,
    placementCount: 0,
    bomItemCount: 0,
    ruleCount: 0,
    findingCount: 0,
    coverageGapCount: 0,
    riskModes: [],
    diagnostics: [],
    disclaimer: "test",
    layers: [],
    findings: [],
  },
};

function svg(children = ""): string {
  return (
    '<svg xmlns="http://www.w3.org/2000/svg" ' +
    'data-project-id="prj-0000000000000000" ' +
    `data-profile-sha256="${"0".repeat(64)}">${children}</svg>\n`
  );
}

function svgErrorCode(payload: string): string | undefined {
  try {
    validateSvg(payload, evidence, VIEWER_RESOURCE_POLICY);
  } catch (error) {
    return error instanceof AdmissionError ? error.viewerError.code : "UNEXPECTED_ERROR";
  }
  return undefined;
}

describe("streaming SVG budgets", () => {
  it("allows exact element/attribute budgets", () => {
    expect(() =>
      validateSvg(svg("<g/>"), evidence, {
        ...VIEWER_RESOURCE_POLICY,
        maxSvgElements: 2,
        maxSvgAttributes: 3,
      }),
    ).not.toThrow();
  });

  it("rejects the next element and attribute", () => {
    expect(() =>
      validateSvg(svg("<g/>"), evidence, {
        ...VIEWER_RESOURCE_POLICY,
        maxSvgElements: 1,
      }),
    ).toThrow(/resource policy/i);
    expect(() =>
      validateSvg(svg(), evidence, {
        ...VIEWER_RESOURCE_POLICY,
        maxSvgAttributes: 2,
      }),
    ).toThrow(/resource policy/i);
  });

  it.each([
    ["SVG_SCRIPT_REJECTED", "<script/>"],
    ["SVG_ACTIVE_ELEMENT_REJECTED", '<animate attributeName="d"/>'],
    ["SVG_ACTIVE_ELEMENT_REJECTED", '<animateColor attributeName="fill"/>'],
    ["SVG_ACTIVE_ELEMENT_REJECTED", "<animateMotion/>"],
    ["SVG_ACTIVE_ELEMENT_REJECTED", '<animateTransform attributeName="transform"/>'],
    ["SVG_ACTIVE_ELEMENT_REJECTED", '<set attributeName="fill"/>'],
    ["SVG_ACTIVE_ELEMENT_REJECTED", "<discard/>"],
    ["SVG_ACTIVE_ELEMENT_REJECTED", "<mpath/>"],
    ["SVG_ACTIVE_ELEMENT_REJECTED", "<style>@keyframes pulse {}</style>"],
    ["SVG_ACTIVE_ELEMENT_REJECTED", '<g style="animation: pulse 1s"/>'],
    ["SVG_EXTERNAL_REFERENCE_REJECTED", "<style>@import 'theme.css';</style>"],
    ["SVG_EXTERNAL_REFERENCE_REJECTED", '<style>.x { fill: url("theme.svg#paint"); }</style>'],
    ["SVG_EXTERNAL_REFERENCE_REJECTED", '<a href="data:text/html,x"/>'],
    ["SVG_EVENT_HANDLER_REJECTED", '<g onclick="x"/>'],
  ])("rejects active content with %s", (code, content) => {
    expect(svgErrorCode(svg(content))).toBe(code);
  });

  it("accepts one uniquely resolved local gradient paint reference", () => {
    expect(() =>
      validateSvg(
        svg(
          '<defs><linearGradient id="paint"><stop offset="0" stop-color="#fff"/>' +
            '<stop offset="1" stop-color="#000"/></linearGradient></defs>' +
            '<rect x="0" y="0" width="1" height="1" fill="url(#paint)"/>',
        ),
        evidence,
        VIEWER_RESOURCE_POLICY,
      ),
    ).not.toThrow();
  });

  it.each([
    ["missing paint server", '<rect x="0" y="0" width="1" height="1" fill="url(#paint)"/>'],
    [
      "non-gradient target",
      '<g id="paint" fill="url(#paint)"><rect x="0" y="0" width="1" height="1"/></g>',
    ],
    [
      "duplicate paint server",
      '<defs><linearGradient id="paint"/><radialGradient id="paint"/></defs>' +
        '<rect x="0" y="0" width="1" height="1" fill="url(#paint)"/>',
    ],
    [
      "local URL in a non-paint attribute",
      '<g transform="url(#paint)"><defs><linearGradient id="paint"/></defs></g>',
    ],
    ["quoted local paint URL", '<g fill="url(&quot;#paint&quot;)"/>'],
    ["uppercase local paint URL", '<g fill="URL(#paint)"/>'],
    ["spaced local paint URL", '<g fill="url( #paint)"/>'],
    ["separated local paint URL", '<g fill="url (#paint)"/>'],
  ])("rejects %s outside the local paint-reference contract", (_label, content) => {
    expect(svgErrorCode(svg(content))).toBe("SVG_VOCABULARY_REJECTED");
  });

  it("rejects malformed roots, metadata, and Findings", () => {
    expect(() =>
      validateSvg(
        '<html data-project-id="prj-0000000000000000" ' +
          `data-profile-sha256="${"0".repeat(64)}"/>`,
        evidence,
        VIEWER_RESOURCE_POLICY,
      ),
    ).toThrow(/root/i);
    expect(() =>
      validateSvg(svg().replace("</svg>\n", ""), evidence, VIEWER_RESOURCE_POLICY),
    ).toThrow(/well-formed/i);
    expect(() =>
      validateSvg(`<svg xmlns="${SVG_NAMESPACE}"/>`, evidence, VIEWER_RESOURCE_POLICY),
    ).toThrow(/metadata/i);
    expect(() =>
      validateSvg(
        svg('<g data-finding-id="fnd-0000000000000000"/>'),
        evidence,
        VIEWER_RESOURCE_POLICY,
      ),
    ).toThrow(/Finding identifiers/i);
  });

  it.each([
    ["wrong root namespace", (payload: string) => payload.replace(SVG_NAMESPACE, "urn:not-svg")],
    [
      "foreign descendant namespace",
      (payload: string) => payload.replace("</svg>", '<g xmlns="urn:not-svg"/></svg>'),
    ],
    [
      "namespaced ordinary attribute",
      (payload: string) => payload.replace("<svg ", '<svg xmlns:e="urn:evidence" e:role="img" '),
    ],
  ])("rejects %s", (_label, mutate) => {
    expect(svgErrorCode(mutate(svg()))).toBe("SVG_NAMESPACE_INVALID");
  });

  it.each([
    ["unknown element", "<metadata/>"],
    ["source class", '<g class="finding-focus"/>'],
    ["source visibility", '<g visibility="hidden"/>'],
    ["local link", '<a href="#paint"/>'],
    ["local image", '<image href="#paint"/>'],
    ["local use", '<use href="#paint"/>'],
  ])("rejects %s outside the passive vocabulary", (_label, content) => {
    expect(svgErrorCode(svg(content))).toBe("SVG_VOCABULARY_REJECTED");
  });

  it("extracts well-formed layer groups and rejects malformed or duplicate groups", () => {
    const admission = validateSvg(
      svg(
        '<g id="pcb-layers">' +
          '<g id="pcb-layer-0001" data-layer-id="lyr-aaaaaaaaaaaaaaaa" ' +
          'data-layer-role="COPPER" data-layer-side="TOP"/>' +
          '<g id="pcb-layer-0002" data-layer-id="lyr-bbbbbbbbbbbbbbbb" ' +
          'data-layer-role="SOLDER_MASK" data-layer-side="BOTTOM"/>' +
          "</g>",
      ),
      evidence,
      VIEWER_RESOURCE_POLICY,
    );
    expect(admission.layerGroups).toEqual([
      {
        groupId: "pcb-layer-0001",
        layerId: "lyr-aaaaaaaaaaaaaaaa",
        role: "COPPER",
        side: "TOP",
      },
      {
        groupId: "pcb-layer-0002",
        layerId: "lyr-bbbbbbbbbbbbbbbb",
        role: "SOLDER_MASK",
        side: "BOTTOM",
      },
    ]);
    expect(() =>
      validateSvg(
        svg('<g id="pcb-layer-0001" data-layer-id="lyr-aaaaaaaaaaaaaaaa"/>'),
        evidence,
        VIEWER_RESOURCE_POLICY,
      ),
    ).toThrow(/layer groups/i);
    expect(() =>
      validateSvg(
        svg(
          '<g id="pcb-layer-0001" data-layer-id="lyr-aaaaaaaaaaaaaaaa" ' +
            'data-layer-role="COPPER" data-layer-side="TOP"/>' +
            '<g id="pcb-layer-0001" data-layer-id="lyr-bbbbbbbbbbbbbbbb" ' +
            'data-layer-role="COPPER" data-layer-side="BOTTOM"/>',
        ),
        evidence,
        VIEWER_RESOURCE_POLICY,
      ),
    ).toThrow(/layer groups/i);
    expect(() =>
      validateSvg(
        svg(
          '<g id="pcb-layer-0001" data-layer-id="lyr-aaaaaaaaaaaaaaaa" ' +
            'data-layer-role="COPPER" data-layer-side="TOP"/>' +
            '<g id="pcb-layer-0002" data-layer-id="lyr-aaaaaaaaaaaaaaaa" ' +
            'data-layer-role="COPPER" data-layer-side="BOTTOM"/>',
        ),
        evidence,
        VIEWER_RESOURCE_POLICY,
      ),
    ).toThrow(/layer groups/i);
  });

  it("classifies Finding markers by section and rejects duplicates or strays", () => {
    const withFindings: CrossArtifactEvidence = {
      ...evidence,
      findingIds: new Set(["fnd-0000000000000000", "fnd-1111111111111111"]),
    };
    const valid =
      '<g id="spatial-findings"><g data-finding-id="fnd-0000000000000000"/></g>' +
      '<g id="non-spatial-findings"><g data-finding-id="fnd-1111111111111111"/></g>';
    const admission = validateSvg(svg(valid), withFindings, VIEWER_RESOURCE_POLICY);
    expect([...admission.spatialFindingIds]).toEqual(["fnd-0000000000000000"]);
    expect([...admission.nonSpatialFindingIds]).toEqual(["fnd-1111111111111111"]);

    expect(() =>
      validateSvg(
        svg(
          '<g id="other"><g data-finding-id="fnd-0000000000000000"/></g>' +
            '<g id="non-spatial-findings"><g data-finding-id="fnd-1111111111111111"/></g>',
        ),
        withFindings,
        VIEWER_RESOURCE_POLICY,
      ),
    ).toThrow(/Finding identifiers/i);
    expect(() =>
      validateSvg(
        svg(
          '<g id="spatial-findings"><g data-finding-id="fnd-0000000000000000"/>' +
            '<g data-finding-id="fnd-0000000000000000"/></g>' +
            '<g id="non-spatial-findings"><g data-finding-id="fnd-1111111111111111"/></g>',
        ),
        withFindings,
        VIEWER_RESOURCE_POLICY,
      ),
    ).toThrow(/Finding identifiers/i);
    expect(() =>
      validateSvg(
        svg(
          '<g id="spatial-findings"><g data-finding-id="fnd-0000000000000000"/></g>' +
            '<g id="non-spatial-findings"><g data-finding-id="fnd-0000000000000000"/></g>' +
            '<g id="non-spatial-findings"><g data-finding-id="fnd-1111111111111111"/></g>',
        ),
        withFindings,
        VIEWER_RESOURCE_POLICY,
      ),
    ).toThrow(/Finding identifiers/i);
    expect(
      svgErrorCode(
        svg(
          '<circle data-finding-id="fnd-0000000000000000"/>' +
            '<g id="spatial-findings"><g data-finding-id="fnd-0000000000000000"/></g>' +
            '<g id="non-spatial-findings"><g data-finding-id="fnd-1111111111111111"/></g>',
        ),
      ),
    ).toBe("SVG_VOCABULARY_REJECTED");
  });
});

describe("JSONL budgets", () => {
  it("rejects event and line N+1 before accepting malformed content", () => {
    expect(() =>
      validateRunLog("{}\n{}\n", {
        ...VIEWER_RESOURCE_POLICY,
        maxJsonlEvents: 1,
      }),
    ).toThrow(/resource policy/i);
    expect(() =>
      validateRunLog(`${" ".repeat(5)}\n`, {
        ...VIEWER_RESOURCE_POLICY,
        maxJsonlLineBytes: 4,
      }),
    ).toThrow(/resource policy/i);
  });

  const event =
    '{"category":"INPUT","code":"INGESTION_COMPLETED","drill_count":null,' +
    '"elapsed_ms":0,"error_type":null,"executed_rules":[],' +
    '"file_classification_counts":{},"finding_count":null,' +
    '"input_file_count":0,"level":"INFO",' +
    '"occurred_at":"2026-07-30T12:00:00Z","primitive_count":null,' +
    '"project_id":"prj-0000000000000000",' +
    '"run_id":"run-0000000000000000","schema_version":"1.0",' +
    '"selected_parsers":[],"sequence":1,"skipped_rule_reasons":{},' +
    '"stage":"INGESTION","summary":"Safe ingestion completed."}';

  it("accepts an exact event budget and enforces run-level identity", () => {
    expect(
      validateRunLog(`${event}\n`, {
        ...VIEWER_RESOURCE_POLICY,
        maxJsonlEvents: 1,
        maxJsonlLineBytes: new Blob([event]).size,
      }),
    ).toMatchObject({
      eventCount: 1,
      projectId: "prj-0000000000000000",
      runId: "run-0000000000000000",
    });
    expect(() =>
      validateRunLog(
        `${event}\n${event
          .replace("prj-0000000000000000", "prj-1111111111111111")
          .replace('"sequence":1', '"sequence":2')}\n`,
        VIEWER_RESOURCE_POLICY,
      ),
    ).toThrow(/project/i);
  });

  it.each([
    ["timestamp", (value: string) => value.replace("2026-07-30T12:00:00Z", "2026-07-30T12:00:00")],
    [
      "summary",
      (value: string) =>
        value.replace("Safe ingestion completed.", "Failed at /private/tmp/a.gbr."),
    ],
    [
      "selected parsers",
      (value: string) => value.replace('"selected_parsers":[]', '"selected_parsers":["x","x"]'),
    ],
    [
      "empty skipped reason",
      (value: string) =>
        value.replace('"skipped_rule_reasons":{}', '"skipped_rule_reasons":{"rule":""}'),
    ],
  ])("rejects invalid event %s semantics", (_label, mutate) => {
    expect(() => validateRunLog(`${mutate(event)}\n`, VIEWER_RESOURCE_POLICY)).toThrow();
  });
});

describe("untrusted report checks", () => {
  it("requires exact metadata and Finding sets without rendering Markdown", () => {
    const withFinding: CrossArtifactEvidence = {
      ...evidence,
      findingIds: new Set(["fnd-0000000000000000"]),
    };
    const report =
      "<!-- boardgate-project-id: prj-0000000000000000 -->\n" +
      `<!-- boardgate-profile-sha256: ${"0".repeat(64)} -->\n` +
      "Finding fnd-0000000000000000\n";
    expect(() => validateReport(report, withFinding, VIEWER_RESOURCE_POLICY)).not.toThrow();
    expect(() =>
      validateReport(
        report.replace("fnd-0000000000000000", "omitted"),
        withFinding,
        VIEWER_RESOURCE_POLICY,
      ),
    ).toThrow(/Finding identifiers/i);
    expect(() => validateReport(`${report}\u0000`, withFinding, VIEWER_RESOURCE_POLICY)).toThrow(
      /metadata/i,
    );
  });

  it("allows the exact line budget and rejects line N+1 before content checks", () => {
    const budget = { ...VIEWER_RESOURCE_POLICY, maxReportLines: 3 };
    const report =
      "<!-- boardgate-project-id: prj-0000000000000000 -->\n" +
      `<!-- boardgate-profile-sha256: ${"0".repeat(64)} -->\n`;
    expect(() => validateReport(report, evidence, budget)).not.toThrow();
    expect(() => validateReport(`${report}extra\n`, evidence, budget)).toThrow(/resource policy/i);
    expect(() =>
      validateReport(`${report}extra\n`, evidence, VIEWER_RESOURCE_POLICY),
    ).not.toThrow();
  });
});
