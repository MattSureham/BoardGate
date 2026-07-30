import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { VIEWER_RESOURCE_POLICY } from "../../src/policy";
import type { JsonValue, ParsedJson } from "../../src/validation";
import { parseCanonicalJson } from "../../src/validation";
import { AdmissionError } from "../../src/validation/errors";
import { validateModels } from "../../src/validation/semantics";
import { type GeneratedBundle, generateValidBundle } from "./fixture";

type JsonRecord = Record<string, JsonValue>;

let minimalBundle: GeneratedBundle;
let findingBundle: GeneratedBundle;
let manifest: ParsedJson;
let project: ParsedJson;
let review: ParsedJson;
let findingManifest: ParsedJson;
let findingProject: ParsedJson;
let findingReview: ParsedJson;

function asRecord(value: JsonValue): JsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("expected test object");
  }
  return value as JsonRecord;
}

function asArray(value: JsonValue | undefined): JsonValue[] {
  if (!Array.isArray(value)) {
    throw new Error("expected test array");
  }
  return value as JsonValue[];
}

function copy(parsed: ParsedJson): ParsedJson {
  return {
    value: structuredClone(parsed.value),
    numberLexemes: parsed.numberLexemes,
  };
}

function valueAt(parsed: ParsedJson, path: readonly (string | number)[]): JsonValue {
  let current = parsed.value;
  for (const part of path) {
    current = Array.isArray(current)
      ? (current[part as number] as JsonValue)
      : (asRecord(current)[part] as JsonValue);
  }
  return current;
}

function setAt(
  parsed: ParsedJson,
  path: readonly (string | number)[],
  value: JsonValue,
): ParsedJson {
  const changed = copy(parsed);
  const parent = valueAt(changed, path.slice(0, -1));
  const key = path[path.length - 1];
  if (key === undefined) {
    throw new Error("mutation path must not be empty");
  }
  if (Array.isArray(parent)) {
    parent[key as number] = value;
  } else {
    asRecord(parent)[key] = value;
  }
  return changed;
}

async function parsedArtifact(bundle: GeneratedBundle, path: string): Promise<ParsedJson> {
  const blob = bundle.files.get(path);
  if (blob === undefined) {
    throw new Error(`missing ${path}`);
  }
  return parseCanonicalJson(await blob.text(), VIEWER_RESOURCE_POLICY);
}

async function expectCode(operation: Promise<unknown>, code: string): Promise<void> {
  try {
    await operation;
    throw new Error(`expected ${code}`);
  } catch (error) {
    expect(error).toBeInstanceOf(AdmissionError);
    expect((error as AdmissionError).viewerError.code).toBe(code);
  }
}

beforeAll(async () => {
  minimalBundle = generateValidBundle();
  findingBundle = generateValidBundle("copper_too_close_to_edge");
  [manifest, project, review, findingManifest, findingProject, findingReview] = await Promise.all([
    parsedArtifact(minimalBundle, "manifest.json"),
    parsedArtifact(minimalBundle, "project.json"),
    parsedArtifact(minimalBundle, "findings.json"),
    parsedArtifact(findingBundle, "manifest.json"),
    parsedArtifact(findingBundle, "project.json"),
    parsedArtifact(findingBundle, "findings.json"),
  ]);
});

afterAll(() => {
  minimalBundle.cleanup();
  findingBundle.cleanup();
});

describe("project semantic parity", () => {
  it.each([
    ["unit", "inch"],
    ["x_axis", "left"],
    ["y_axis", "down"],
    ["rotation_degrees", 1],
  ])("rejects noncanonical coordinate-system %s", async (field, value) => {
    await expectCode(
      validateModels(manifest, setAt(project, ["coordinate_system", field], value), review),
      "PROJECT_JSON_INVALID",
    );
  });

  it("rejects unsafe and Python-casefold-colliding source paths", async () => {
    await expectCode(
      validateModels(
        setAt(manifest, ["source_files", 1, "logical_path"], "../escape.gbr"),
        project,
        review,
      ),
      "MANIFEST_JSON_INVALID",
    );
    const folded = copy(manifest);
    const sources = asArray(asRecord(folded.value).source_files);
    asRecord(sources[0] as JsonValue).logical_path = "Straße.gbr";
    asRecord(sources[1] as JsonValue).logical_path = "STRASSE.GBR";
    await expectCode(validateModels(folded, project, review), "MANIFEST_JSON_INVALID");
    await expectCode(
      validateModels(
        manifest,
        setAt(project, ["source_files", 0, "logical_path"], "bad\\path.gbr"),
        review,
      ),
      "PROJECT_JSON_INVALID",
    );
  });

  it.each([
    ["layers", "layer_id"],
    ["drills", "drill_id"],
  ])("rejects duplicate %s identifiers", async (collection, key) => {
    const changed = copy(project);
    const items = asArray(asRecord(changed.value)[collection]);
    if (items.length < 2) {
      items.push(structuredClone(items[0] as JsonValue));
    }
    asRecord(items[1] as JsonValue)[key] = asRecord(items[0] as JsonValue)[key] as JsonValue;
    await expectCode(validateModels(manifest, changed, review), "PROJECT_JSON_INVALID");
  });

  it("rejects duplicate primitive IDs and inverted bounds", async () => {
    const duplicate = copy(project);
    const primitives = asArray(
      asRecord(asArray(asRecord(duplicate.value).layers)[1] as JsonValue).primitives,
    );
    primitives.push(structuredClone(primitives[0] as JsonValue));
    await expectCode(validateModels(manifest, duplicate, review), "PROJECT_JSON_INVALID");

    await expectCode(
      validateModels(
        manifest,
        setAt(project, ["layers", 0, "bounding_box", "minimum", "x"], 99),
        review,
      ),
      "PROJECT_JSON_INVALID",
    );
  });

  it.each([
    ["circle height", ["layers", 0, "primitives", 0, "aperture", "height_mm"], 0.7],
    ["macro name", ["layers", 0, "primitives", 0, "aperture", "shape"], "macro"],
    ["polygon vertices", ["layers", 0, "primitives", 0, "aperture", "shape"], "polygon"],
    ["nonpolygon vertices", ["layers", 0, "primitives", 0, "aperture", "vertices"], 3],
  ] as const)("rejects inconsistent aperture %s", async (_label, path, value) => {
    await expectCode(
      validateModels(manifest, setAt(project, path, value), review),
      "PROJECT_JSON_INVALID",
    );
  });

  it("accepts analytic arcs and closed regions but rejects unknown/disconnected primitives", async () => {
    const arcProject = copy(project);
    const arc = asRecord(valueAt(arcProject, ["layers", 1, "primitives", 0]));
    arc.kind = "arc";
    arc.center = structuredClone(arc.start as JsonValue);
    arc.clockwise = false;
    await expect(validateModels(manifest, arcProject, review)).resolves.toBeDefined();

    const regionProject = copy(project);
    const region = asRecord(valueAt(regionProject, ["layers", 0, "primitives", 0]));
    region.kind = "region";
    region.contours = [
      structuredClone(valueAt(regionProject, ["board_outline", "contours", 0, "segments"])),
    ];
    await expect(validateModels(manifest, regionProject, review)).resolves.toBeDefined();

    await expectCode(
      validateModels(
        manifest,
        setAt(project, ["layers", 0, "primitives", 0, "kind"], "unknown"),
        review,
      ),
      "PROJECT_JSON_INVALID",
    );
    const disconnected = copy(regionProject);
    setAt(disconnected, ["layers", 0, "primitives", 0, "contours", 0, 0, "end", "x"], 123);
    const segment = asRecord(
      valueAt(disconnected, ["layers", 0, "primitives", 0, "contours", 0, 0, "end"]),
    );
    segment.x = 123;
    await expectCode(validateModels(manifest, disconnected, review), "PROJECT_JSON_INVALID");
  });

  it.each([
    ["first point", ["board_outline", "contours", 0, "points", 0, "x"], 1],
    ["segment connection", ["board_outline", "contours", 0, "segments", 1, "start", "x"], 1],
    ["closed endpoint", ["board_outline", "contours", 0, "points", 4, "x"], 1],
    ["source alignment", ["board_outline", "contours", 0, "source_primitive_ids"], ["one"]],
    ["outer count", ["board_outline", "outer_contour_count"], 2],
  ] as const)("rejects inconsistent outline %s", async (_label, path, value) => {
    await expectCode(
      validateModels(manifest, setAt(project, path, value), review),
      "PROJECT_JSON_INVALID",
    );
  });

  it("validates line/arc slots, placements, and zero-quantity BOM semantics", async () => {
    const enriched = copy(project);
    const drill = asRecord(valueAt(enriched, ["drills", 0]));
    const point = structuredClone(drill.position as JsonValue);
    const provenance = structuredClone(drill.provenance as JsonValue);
    asArray(asRecord(enriched.value).drill_slots).push({
      center: null,
      clockwise: null,
      end: point,
      kind: "line",
      plating: "unknown",
      provenance,
      schema_version: "1.0",
      slot_id: "slot-test",
      start: structuredClone(point),
      tool_code: null,
      width_mm: 0.2,
    });
    asArray(asRecord(enriched.value).components).push({
      dnp: false,
      footprint: null,
      metadata: {},
      position: structuredClone(point),
      provenance: structuredClone(provenance),
      reference: "R1",
      rotation_degrees: 0,
      schema_version: "1.0",
      side: "top",
      value: null,
    });
    asArray(asRecord(enriched.value).bom_items).push({
      dnp: true,
      footprint: null,
      metadata: {},
      part_number: null,
      provenance: structuredClone(provenance),
      quantity: 0,
      references: ["R1"],
      schema_version: "1.0",
      value: null,
    });
    await expect(validateModels(manifest, enriched, review)).resolves.toBeDefined();

    const lineWithCenter = setAt(enriched, ["drill_slots", 0, "center"], structuredClone(point));
    await expectCode(validateModels(manifest, lineWithCenter, review), "PROJECT_JSON_INVALID");
    const arcWithoutCenter = setAt(enriched, ["drill_slots", 0, "kind"], "arc");
    await expectCode(validateModels(manifest, arcWithoutCenter, review), "PROJECT_JSON_INVALID");
    await expectCode(
      validateModels(manifest, setAt(enriched, ["bom_items", 0, "dnp"], false), review),
      "PROJECT_JSON_INVALID",
    );
  });

  it("rejects manifest/project identity and stable-ID divergence", async () => {
    await expectCode(
      validateModels(
        manifest,
        setAt(project, ["manifest", "project_id"], "prj-0000000000000000"),
        review,
      ),
      "ARTIFACT_PROJECT_ID_MISMATCH",
    );
    await expectCode(
      validateModels(
        setAt(manifest, ["source_files", 0, "source_file_id"], "src-0000000000000000"),
        setAt(project, ["source_files", 0, "source_file_id"], "src-0000000000000000"),
        review,
      ),
      "ARTIFACT_PROJECT_ID_MISMATCH",
    );
    await expectCode(
      validateModels(
        manifest,
        setAt(project, ["fabrication_requirements", "profile_id"], "other"),
        review,
      ),
      "ARTIFACT_PROFILE_ID_MISMATCH",
    );
    await expectCode(
      validateModels(
        manifest,
        setAt(project, ["source_files", 1, "source_file_id"], "src-0000000000000000"),
        review,
      ),
      "PROJECT_JSON_INVALID",
    );
  });
});

describe("review semantic and cross-evidence parity", () => {
  it("accepts real Findings and validates stable evidence-derived IDs", async () => {
    const admitted = await validateModels(findingManifest, findingProject, findingReview);
    expect(admitted.summary.findingCount).toBeGreaterThan(0);
    expect(admitted.findingIds.size).toBe(admitted.summary.findingCount);
  });

  it.each([
    ["uncertain confirmation", ["findings", 0, "category"], "UNIT_AMBIGUITY"],
    ["measurement config", ["findings", 0, "measurement", "config_path"], "other.path"],
    ["location unit", ["findings", 0, "location", "unit"], "inch"],
    ["witness bounds", ["findings", 0, "evidence", 0, "witness_bounds", "minimum", "x"], 99],
  ] as const)("rejects invalid Finding %s", async (_label, path, value) => {
    const changed = setAt(findingReview, path, value);
    if (path[0] === "findings") {
      const resultFindings = asArray(
        asRecord(
          asArray(asRecord(changed.value).rule_results).find(
            (item) =>
              asRecord(item).rule_id ===
              asRecord(asArray(asRecord(changed.value).findings)[0] as JsonValue).rule_id,
          ) as JsonValue,
        ).findings,
      );
      resultFindings[0] = structuredClone(
        asArray(asRecord(changed.value).findings)[0] as JsonValue,
      );
    }
    await expectCode(
      validateModels(findingManifest, findingProject, changed),
      "FINDINGS_JSON_INVALID",
    );
  });

  it.each([
    ["outcome", "PASS"],
    ["reason", "NOT_APPLICABLE"],
  ])("rejects Finding rule-result %s inconsistency", async (field, value) => {
    const changed = copy(findingReview);
    const finding = asRecord(asArray(asRecord(changed.value).findings)[0] as JsonValue);
    const result = asRecord(
      asArray(asRecord(changed.value).rule_results).find(
        (item) => asRecord(item).rule_id === finding.rule_id,
      ) as JsonValue,
    );
    result[field] = value;
    await expectCode(
      validateModels(findingManifest, findingProject, changed),
      "FINDINGS_JSON_INVALID",
    );
  });

  it("rejects flattened, duplicate, sorted-risk, and analysis-status inconsistencies", async () => {
    await expectCode(
      validateModels(
        manifest,
        project,
        setAt(
          review,
          ["rule_results", 0, "findings"],
          [structuredClone(asArray(asRecord(findingReview.value).findings)[0] as JsonValue)],
        ),
      ),
      "FINDINGS_JSON_INVALID",
    );

    const duplicateRule = copy(review);
    const results = asArray(asRecord(duplicateRule.value).rule_results);
    results.push(structuredClone(results[0] as JsonValue));
    await expectCode(validateModels(manifest, project, duplicateRule), "FINDINGS_JSON_INVALID");

    await expectCode(
      validateModels(
        manifest,
        project,
        setAt(review, ["risk_modes"], ["GEOMETRY_VIOLATION", "FILE_INCOMPLETE"]),
      ),
      "FINDINGS_JSON_INVALID",
    );
    await expectCode(
      validateModels(manifest, project, setAt(review, ["risk_modes"], ["ANALYSIS_LIMITATION"])),
      "FINDINGS_JSON_INVALID",
    );
    await expectCode(
      validateModels(manifest, project, setAt(review, ["overall_status"], "ANALYSIS_FAILED")),
      "FINDINGS_JSON_INVALID",
    );
  });

  it("accepts ANALYSIS_FAILED diagnostics and rejects unsafe or contradictory diagnostics", async () => {
    const failed = copy(review);
    const root = asRecord(failed.value);
    root.overall_status = "ANALYSIS_FAILED";
    root.rule_results = [];
    root.findings = [];
    root.analysis_diagnostics = [
      {
        category: "ANALYSIS",
        code: "PROJECT_BUILD_UNAVAILABLE",
        schema_version: "1.0",
        stage: "PROJECT_CONSTRUCTION",
        summary: "The normalized project could not be constructed.",
      },
    ];
    const admitted = await validateModels(manifest, project, failed);
    expect(admitted.summary.diagnostics).toHaveLength(1);

    await expectCode(
      validateModels(
        manifest,
        project,
        setAt(failed, ["analysis_diagnostics", 0, "summary"], "Failure at /private/tmp/board.gbr."),
      ),
      "FINDINGS_JSON_INVALID",
    );
    await expectCode(
      validateModels(manifest, project, setAt(failed, ["overall_status"], "READY_FOR_REVIEW")),
      "FINDINGS_JSON_INVALID",
    );
  });

  it("rejects source, layer, stable Finding, and expected risk mismatches", async () => {
    const changedSource = copy(findingReview);
    const topFinding = asRecord(asArray(asRecord(changedSource.value).findings)[0] as JsonValue);
    asRecord(
      asRecord(asArray(topFinding.evidence)[0] as JsonValue).provenance as JsonValue,
    ).source_file_id = "src-0000000000000000";
    const enclosing = asRecord(
      asArray(asRecord(changedSource.value).rule_results).find(
        (item) => asRecord(item).rule_id === topFinding.rule_id,
      ) as JsonValue,
    );
    asArray(enclosing.findings)[0] = structuredClone(topFinding);
    await expectCode(
      validateModels(findingManifest, findingProject, changedSource),
      "FINDING_SOURCE_EVIDENCE_MISMATCH",
    );

    const badLayer = copy(findingReview);
    const layerFinding = asRecord(asArray(asRecord(badLayer.value).findings)[0] as JsonValue);
    layerFinding.layer_ids = ["layer-unknown"];
    const layerResult = asRecord(
      asArray(asRecord(badLayer.value).rule_results).find(
        (item) => asRecord(item).rule_id === layerFinding.rule_id,
      ) as JsonValue,
    );
    asArray(layerResult.findings)[0] = structuredClone(layerFinding);
    await expectCode(
      validateModels(findingManifest, findingProject, badLayer),
      "FINDING_LAYER_EVIDENCE_MISMATCH",
    );

    const badId = copy(findingReview);
    const idFinding = asRecord(asArray(asRecord(badId.value).findings)[0] as JsonValue);
    idFinding.finding_id = "fnd-0000000000000000";
    const idResult = asRecord(
      asArray(asRecord(badId.value).rule_results).find(
        (item) => asRecord(item).rule_id === idFinding.rule_id,
      ) as JsonValue,
    );
    asArray(idResult.findings)[0] = structuredClone(idFinding);
    await expectCode(
      validateModels(findingManifest, findingProject, badId),
      "FINDING_STABLE_ID_MISMATCH",
    );

    await expectCode(
      validateModels(findingManifest, findingProject, setAt(findingReview, ["risk_modes"], [])),
      "REVIEW_RISK_MODE_MISMATCH",
    );
  });

  it("accepts one coherent computation gap and rejects cross-evidence mismatches", async () => {
    const limited = copy(review);
    const root = asRecord(limited.value);
    const result = asRecord(asArray(root.rule_results)[0] as JsonValue);
    const layer = asRecord(asArray(asRecord(project.value).layers)[0] as JsonValue);
    const gap: JsonRecord = {
      code: "COMPUTATION_LIMIT",
      layer_id: layer.layer_id as JsonValue,
      limit: 1,
      metric: "primitive_count",
      observed: 2,
      policy_version: "1.0",
      schema_version: "1.0",
      source_file_id: layer.source_file_id as JsonValue,
      summary: "A deterministic geometry resource limit was exceeded.",
      unit: "primitives",
    };
    result.coverage = "NONE";
    result.coverage_gaps = [gap];
    result.evaluated_object_count = 0;
    result.outcome = "SKIPPED";
    result.reason = "COMPUTATION_LIMIT";
    root.coverage_gaps = [structuredClone(gap)];
    root.risk_modes = ["ANALYSIS_LIMITATION"];
    await expect(validateModels(manifest, project, limited)).resolves.toBeDefined();

    const sourceMismatch = setAt(
      limited,
      ["coverage_gaps", 0, "source_file_id"],
      "src-0000000000000000",
    );
    setAt(
      sourceMismatch,
      ["rule_results", 0, "coverage_gaps", 0, "source_file_id"],
      "src-0000000000000000",
    );
    asRecord(valueAt(sourceMismatch, ["rule_results", 0, "coverage_gaps", 0])).source_file_id =
      "src-0000000000000000";
    await expectCode(
      validateModels(manifest, project, sourceMismatch),
      "COVERAGE_GAP_SOURCE_EVIDENCE_MISMATCH",
    );

    const layerMismatch = copy(limited);
    asRecord(valueAt(layerMismatch, ["coverage_gaps", 0])).layer_id = "layer-unknown";
    asRecord(valueAt(layerMismatch, ["rule_results", 0, "coverage_gaps", 0])).layer_id =
      "layer-unknown";
    await expectCode(
      validateModels(manifest, project, layerMismatch),
      "COVERAGE_GAP_LAYER_EVIDENCE_MISMATCH",
    );

    const ownerMismatch = copy(limited);
    const otherSource = asRecord(asArray(asRecord(manifest.value).source_files)[1] as JsonValue)
      .source_file_id as JsonValue;
    asRecord(valueAt(ownerMismatch, ["coverage_gaps", 0])).source_file_id = otherSource;
    asRecord(valueAt(ownerMismatch, ["rule_results", 0, "coverage_gaps", 0])).source_file_id =
      otherSource;
    await expectCode(
      validateModels(manifest, project, ownerMismatch),
      "COVERAGE_GAP_SOURCE_LAYER_MISMATCH",
    );
  });
});
