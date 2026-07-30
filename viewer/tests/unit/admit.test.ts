import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { COMPLETE_ARTIFACT_PATHS, type ValidationResult } from "../../src/contracts";
import { VIEWER_RESOURCE_POLICY, type ViewerResourcePolicy } from "../../src/policy";
import { admitBundle, admitTransferredBundle } from "../../src/validation";
import { type GeneratedBundle, generateValidBundle, replaceText } from "./fixture";

let bundle: GeneratedBundle;
let accepted: ValidationResult;

beforeAll(async () => {
  bundle = generateValidBundle();
  accepted = await admitBundle(bundle.files, VIEWER_RESOURCE_POLICY);
});

afterAll(() => {
  bundle.cleanup();
});

function errorCode(result: ValidationResult): string | undefined {
  return result.ok ? undefined : result.error.code;
}

function withLimits(
  maxArtifactBytes: ViewerResourcePolicy["maxArtifactBytes"],
  maxBundleBytes: number,
): ViewerResourcePolicy {
  return {
    ...VIEWER_RESOURCE_POLICY,
    maxArtifactBytes,
    maxBundleBytes,
  };
}

describe("bundle admission", () => {
  it("admits one exact six-artifact bundle and exposes only a summary", () => {
    expect(accepted.ok).toBe(true);
    if (!accepted.ok) {
      return;
    }
    expect(accepted.summary).toMatchObject({
      overallStatus: "READY_FOR_REVIEW",
      sourceCount: 4,
      layerCount: 3,
      drillCount: 1,
      slotCount: 0,
      placementCount: 0,
      bomItemCount: 0,
      findingCount: 0,
      coverageGapCount: 0,
    });
    expect(accepted.summary.projectId).toMatch(/^prj-[0-9a-f]{16}$/);
    expect(accepted.summary).not.toHaveProperty("manifest");
    expect(accepted.summary).not.toHaveProperty("project");
    expect(accepted.summary).not.toHaveProperty("review");
  });

  it("admits transferred ArrayBuffer snapshots without Blob reads", async () => {
    const snapshots = new Map<string, ArrayBuffer>();
    for (const [path, blob] of bundle.files) {
      snapshots.set(path, await blob.arrayBuffer());
    }

    expect(await admitTransferredBundle(snapshots, VIEWER_RESOURCE_POLICY)).toEqual(accepted);
  });

  it.each([
    ["missing", (files: Map<string, Blob>) => files.delete("preview.svg")],
    ["extra", (files: Map<string, Blob>) => files.set("unexpected.txt", new Blob(["x"]))],
    [
      "backslash",
      (files: Map<string, Blob>) =>
        files.set("logs\\run.jsonl", files.get("logs/run.jsonl") as Blob),
    ],
    [
      "dot segment",
      (files: Map<string, Blob>) => files.set("./preview.svg", files.get("preview.svg") as Blob),
    ],
  ])("rejects an inventory with a %s entry", async (_label, mutate) => {
    const files = new Map(bundle.files);
    mutate(files);
    const result = await admitBundle(files, VIEWER_RESOURCE_POLICY);
    expect(errorCode(result)).toBe("ARTIFACT_INVENTORY_MISMATCH");
    expect(result).not.toHaveProperty("summary");
  });

  it("allows file and bundle size equality and rejects N+1 before parsing", async () => {
    const limits = Object.fromEntries(
      COMPLETE_ARTIFACT_PATHS.map((path) => [path, (bundle.files.get(path) as Blob).size]),
    ) as unknown as ViewerResourcePolicy["maxArtifactBytes"];
    const total = [...bundle.files.values()].reduce((sum, blob) => sum + blob.size, 0);
    expect(await admitBundle(bundle.files, withLimits(limits, total))).toMatchObject({ ok: true });

    const tooSmall = {
      ...limits,
      "project.json": limits["project.json"] - 1,
    };
    expect(errorCode(await admitBundle(bundle.files, withLimits(tooSmall, total)))).toBe(
      "ARTIFACT_RESOURCE_LIMIT",
    );
    expect(errorCode(await admitBundle(bundle.files, withLimits(limits, total - 1)))).toBe(
      "ARTIFACT_RESOURCE_LIMIT",
    );
  });

  it("rejects a BOM and invalid UTF-8 without leaking decoder details", async () => {
    const bom = new Map(bundle.files);
    bom.set(
      "manifest.json",
      new Blob([
        new Uint8Array([0xef, 0xbb, 0xbf]),
        await (bundle.files.get("manifest.json") as Blob).arrayBuffer(),
      ]),
    );
    const bomResult = await admitBundle(bom, VIEWER_RESOURCE_POLICY);
    expect(errorCode(bomResult)).toBe("ARTIFACT_UTF8_INVALID");

    const invalid = new Map(bundle.files);
    invalid.set("manifest.json", new Blob([new Uint8Array([0xc3, 0x28])]));
    const invalidResult = await admitBundle(invalid, VIEWER_RESOURCE_POLICY);
    expect(errorCode(invalidResult)).toBe("ARTIFACT_UTF8_INVALID");
    if (!invalidResult.ok) {
      expect(invalidResult.error.summary).not.toMatch(/decoder|offset|byte 0x/i);
    }
  });

  it("rejects noncanonical deterministic JSON and missing default fields", async () => {
    const noncanonical = await replaceText(bundle.files, "manifest.json", (payload) =>
      JSON.stringify(JSON.parse(payload)),
    );
    expect(errorCode(await admitBundle(noncanonical, VIEWER_RESOURCE_POLICY))).toBe(
      "ARTIFACT_JSON_NONDETERMINISTIC",
    );

    const missingDefault = await replaceText(bundle.files, "manifest.json", (payload) => {
      const value = JSON.parse(payload) as {
        source_files: { candidates?: unknown }[];
      };
      delete value.source_files[0]?.candidates;
      return `${JSON.stringify(value, null, 2)}\n`;
    });
    expect(errorCode(await admitBundle(missingDefault, VIEWER_RESOURCE_POLICY))).toBe(
      "MANIFEST_JSON_INVALID",
    );
  });

  it("rejects cross-artifact project and profile mismatches", async () => {
    const wrongProject = await replaceText(bundle.files, "findings.json", (payload) =>
      payload.replace(/"project_id": "prj-[0-9a-f]{16}"/, '"project_id": "prj-0000000000000000"'),
    );
    expect(errorCode(await admitBundle(wrongProject, VIEWER_RESOURCE_POLICY))).toBe(
      "ARTIFACT_PROJECT_ID_MISMATCH",
    );

    const wrongProfile = await replaceText(bundle.files, "findings.json", (payload) =>
      payload.replace(/"profile_id": "[^"]+"/, '"profile_id": "other-profile"'),
    );
    expect(errorCode(await admitBundle(wrongProfile, VIEWER_RESOURCE_POLICY))).toBe(
      "ARTIFACT_PROFILE_ID_MISMATCH",
    );
  });

  it("rejects report and SVG identity mismatches", async () => {
    const report = await replaceText(bundle.files, "report.md", (payload) =>
      payload.replace(/prj-[0-9a-f]{16}/, "prj-0000000000000000"),
    );
    expect(errorCode(await admitBundle(report, VIEWER_RESOURCE_POLICY))).toBe(
      "REPORT_REVIEW_ID_MISMATCH",
    );

    const svg = await replaceText(bundle.files, "preview.svg", (payload) =>
      payload.replace(
        /data-project-id="prj-[0-9a-f]{16}"/,
        'data-project-id="prj-0000000000000000"',
      ),
    );
    expect(errorCode(await admitBundle(svg, VIEWER_RESOURCE_POLICY))).toBe(
      "SVG_REVIEW_ID_MISMATCH",
    );
  });

  it.each([
    ["SVG_SCRIPT_REJECTED", (svg: string) => svg.replace("</svg>", "<script/></svg>")],
    [
      "SVG_ACTIVE_ELEMENT_REJECTED",
      (svg: string) => svg.replace("</svg>", "<foreignObject/></svg>"),
    ],
    [
      "SVG_EVENT_HANDLER_REJECTED",
      (svg: string) => svg.replace("<svg ", '<svg onload="alert(1)" '),
    ],
    [
      "SVG_EXTERNAL_REFERENCE_REJECTED",
      (svg: string) => svg.replace("</svg>", '<image href="https://invalid.example/x"/></svg>'),
    ],
    ["SVG_ACTIVE_XML_REJECTED", (svg: string) => `<!DOCTYPE svg>${svg}`],
  ])("rejects active SVG content with %s", async (code, mutate) => {
    const files = await replaceText(bundle.files, "preview.svg", mutate);
    expect(errorCode(await admitBundle(files, VIEWER_RESOURCE_POLICY))).toBe(code);
  });

  it("rejects malformed, mixed-run, and non-monotonic JSONL", async () => {
    const noTerminator = await replaceText(bundle.files, "logs/run.jsonl", (payload) =>
      payload.slice(0, -1),
    );
    expect(errorCode(await admitBundle(noTerminator, VIEWER_RESOURCE_POLICY))).toBe(
      "RUN_LOG_TERMINATOR_MISSING",
    );

    const mixedRun = await replaceText(bundle.files, "logs/run.jsonl", (payload) => {
      const lines = payload.trimEnd().split("\n");
      lines[1] = (lines[1] as string).replace(
        /"run_id":"run-[0-9a-f]{16}"/,
        '"run_id":"run-0000000000000000"',
      );
      return `${lines.join("\n")}\n`;
    });
    expect(errorCode(await admitBundle(mixedRun, VIEWER_RESOURCE_POLICY))).toBe(
      "RUN_LOG_ID_MISMATCH",
    );

    const sequence = await replaceText(bundle.files, "logs/run.jsonl", (payload) => {
      const lines = payload.trimEnd().split("\n");
      lines[1] = (lines[1] as string).replace('"sequence":2', '"sequence":1');
      return `${lines.join("\n")}\n`;
    });
    expect(errorCode(await admitBundle(sequence, VIEWER_RESOURCE_POLICY))).toBe(
      "RUN_LOG_SEQUENCE_INVALID",
    );
  });

  it("rejects run identifiers leaked into deterministic evidence", async () => {
    const log = await (bundle.files.get("logs/run.jsonl") as Blob).text();
    const runId = /"run_id":"(run-[0-9a-f]{16})"/.exec(log)?.[1];
    expect(runId).toBeDefined();
    const files = await replaceText(
      bundle.files,
      "report.md",
      (payload) => `${payload}\nRun: ${runId}\n`,
    );
    expect(errorCode(await admitBundle(files, VIEWER_RESOURCE_POLICY))).toBe("RUN_VARIANCE_LEAKED");
  });
});
