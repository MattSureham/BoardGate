import type { ReviewSummary, ViewerDiagnostic } from "../contracts";
import { pythonCasefold } from "./casefold";
import { reject, type ViewerErrorCode } from "./errors";
import type { JsonValue, ParsedJson } from "./json";
import { canonicalCompact, compareUnicodeCodePoints, isRecord, sha256Prefix } from "./json";
import { validateSafeDiagnosticSummary } from "./safe-text";

type JsonRecord = Record<string, JsonValue>;

const ANALYSIS_FAILED = "ANALYSIS_FAILED";
const UNCERTAIN_CATEGORIES = new Set([
  "DESIGN_INTENT_UNKNOWN",
  "LAYER_MAPPING_UNCERTAIN",
  "OUTLINE_UNCERTAIN",
  "UNIT_AMBIGUITY",
]);

function record(value: JsonValue, code: ViewerErrorCode): JsonRecord {
  if (!isRecord(value)) {
    reject(code);
  }
  return value;
}

function array(value: JsonValue | undefined, code: ViewerErrorCode): readonly JsonValue[] {
  if (!Array.isArray(value)) {
    reject(code);
  }
  return value;
}

function string(value: JsonValue | undefined, code: ViewerErrorCode): string {
  if (typeof value !== "string") {
    reject(code);
  }
  return value;
}

function number(value: JsonValue | undefined, code: ViewerErrorCode): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    reject(code);
  }
  return value;
}

function nullableString(value: JsonValue | undefined, code: ViewerErrorCode): string | null {
  if (value === null) {
    return null;
  }
  return string(value, code);
}

function sameJson(left: JsonValue, right: JsonValue): boolean {
  if (left === right) {
    return true;
  }
  if (Array.isArray(left) && Array.isArray(right)) {
    return (
      left.length === right.length &&
      left.every((item, index) => sameJson(item, right[index] as JsonValue))
    );
  }
  if (isRecord(left) && isRecord(right)) {
    const leftKeys = Object.keys(left);
    const rightKeys = Object.keys(right);
    return (
      leftKeys.length === rightKeys.length &&
      leftKeys.every(
        (key, index) =>
          key === rightKeys[index] && sameJson(left[key] as JsonValue, right[key] as JsonValue),
      )
    );
  }
  return false;
}

function unique(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

function sortedUnique(values: readonly string[]): boolean {
  return (
    unique(values) &&
    values.every(
      (value, index) =>
        index === 0 || compareUnicodeCodePoints(values[index - 1] as string, value) < 0,
    )
  );
}

function validateSafePath(path: string, code: ViewerErrorCode): void {
  if (
    path.startsWith("/") ||
    path.includes("\\") ||
    path.split("/").some((part) => part === "" || part === "." || part === "..")
  ) {
    reject(code);
  }
}

function validatePoint(value: JsonValue): void {
  const point = record(value, "PROJECT_JSON_INVALID");
  if (point.unit !== "mm") {
    reject("PROJECT_JSON_INVALID");
  }
  number(point.x, "PROJECT_JSON_INVALID");
  number(point.y, "PROJECT_JSON_INVALID");
}

function validateBounds(value: JsonValue): void {
  const bounds = record(value, "PROJECT_JSON_INVALID");
  validatePoint(bounds.minimum as JsonValue);
  validatePoint(bounds.maximum as JsonValue);
  const minimum = record(bounds.minimum as JsonValue, "PROJECT_JSON_INVALID");
  const maximum = record(bounds.maximum as JsonValue, "PROJECT_JSON_INVALID");
  if (
    number(minimum.x, "PROJECT_JSON_INVALID") > number(maximum.x, "PROJECT_JSON_INVALID") ||
    number(minimum.y, "PROJECT_JSON_INVALID") > number(maximum.y, "PROJECT_JSON_INVALID")
  ) {
    reject("PROJECT_JSON_INVALID");
  }
}

function validateSourceSpan(value: JsonValue | undefined, code: ViewerErrorCode): void {
  if (value === null) {
    return;
  }
  const span = record(value as JsonValue, code);
  for (const [startName, endName] of [
    ["start_line", "end_line"],
    ["start_byte", "end_byte"],
  ] as const) {
    const start = span[startName];
    const end = span[endName];
    if ((start === null) !== (end === null)) {
      reject(code);
    }
    if (typeof start === "number" && typeof end === "number" && start > end) {
      reject(code);
    }
  }
}

function validateProvenance(value: JsonValue, code: ViewerErrorCode): void {
  const provenance = record(value, code);
  validateSourceSpan(provenance.source_span, code);
}

function validateAperture(value: JsonValue): void {
  const aperture = record(value, "PROJECT_JSON_INVALID");
  const shape = string(aperture.shape, "PROJECT_JSON_INVALID");
  const width = number(aperture.width_mm, "PROJECT_JSON_INVALID");
  const height = aperture.height_mm;
  if (shape === "circle" && height !== null && number(height, "PROJECT_JSON_INVALID") !== width) {
    reject("PROJECT_JSON_INVALID");
  }
  if (shape === "macro" && aperture.macro_name === null) {
    reject("PROJECT_JSON_INVALID");
  }
  if ((shape === "polygon") !== (aperture.vertices !== null)) {
    reject("PROJECT_JSON_INVALID");
  }
}

function validateSegment(value: JsonValue): void {
  const segment = record(value, "PROJECT_JSON_INVALID");
  validatePoint(segment.start as JsonValue);
  validatePoint(segment.end as JsonValue);
  if (segment.kind === "arc") {
    validatePoint(segment.center as JsonValue);
  }
}

function samePoint(left: JsonValue, right: JsonValue): boolean {
  return sameJson(left, right);
}

function validateRegionContours(contoursValue: JsonValue): void {
  for (const contourValue of array(contoursValue, "PROJECT_JSON_INVALID")) {
    const contour = array(contourValue, "PROJECT_JSON_INVALID");
    if (contour.length === 0) {
      reject("PROJECT_JSON_INVALID");
    }
    contour.forEach(validateSegment);
    for (let index = 0; index < contour.length; index += 1) {
      const current = record(contour[index] as JsonValue, "PROJECT_JSON_INVALID");
      const following = record(
        contour[(index + 1) % contour.length] as JsonValue,
        "PROJECT_JSON_INVALID",
      );
      if (!samePoint(current.end as JsonValue, following.start as JsonValue)) {
        reject("PROJECT_JSON_INVALID");
      }
    }
  }
}

function validatePrimitive(value: JsonValue): void {
  const primitive = record(value, "PROJECT_JSON_INVALID");
  validateProvenance(primitive.provenance as JsonValue, "PROJECT_JSON_INVALID");
  switch (primitive.kind) {
    case "line":
      validatePoint(primitive.start as JsonValue);
      validatePoint(primitive.end as JsonValue);
      validateAperture(primitive.aperture as JsonValue);
      break;
    case "arc":
      validatePoint(primitive.start as JsonValue);
      validatePoint(primitive.end as JsonValue);
      validatePoint(primitive.center as JsonValue);
      validateAperture(primitive.aperture as JsonValue);
      break;
    case "flash":
      validatePoint(primitive.position as JsonValue);
      validateAperture(primitive.aperture as JsonValue);
      break;
    case "region":
      validateRegionContours(primitive.contours as JsonValue);
      break;
    default:
      reject("PROJECT_JSON_INVALID");
  }
}

function validateOutline(value: JsonValue): void {
  const outline = record(value, "PROJECT_JSON_INVALID");
  validateBounds(outline.bounding_box as JsonValue);
  const contours = array(outline.contours, "PROJECT_JSON_INVALID");
  let outerCount = 0;
  for (const contourValue of contours) {
    const contour = record(contourValue, "PROJECT_JSON_INVALID");
    if (contour.kind === "outer") {
      outerCount += 1;
    }
    const segments = array(contour.segments, "PROJECT_JSON_INVALID");
    const points = array(contour.points, "PROJECT_JSON_INVALID");
    if (segments.length === 0 || points.length < 2) {
      reject("PROJECT_JSON_INVALID");
    }
    segments.forEach(validateSegment);
    points.forEach(validatePoint);
    const firstSegment = record(segments[0] as JsonValue, "PROJECT_JSON_INVALID");
    const lastSegment = record(segments[segments.length - 1] as JsonValue, "PROJECT_JSON_INVALID");
    if (
      !samePoint(points[0] as JsonValue, firstSegment.start as JsonValue) ||
      !samePoint(points[points.length - 1] as JsonValue, lastSegment.end as JsonValue)
    ) {
      reject("PROJECT_JSON_INVALID");
    }
    for (let index = 1; index < segments.length; index += 1) {
      const previous = record(segments[index - 1] as JsonValue, "PROJECT_JSON_INVALID");
      const current = record(segments[index] as JsonValue, "PROJECT_JSON_INVALID");
      if (!samePoint(previous.end as JsonValue, current.start as JsonValue)) {
        reject("PROJECT_JSON_INVALID");
      }
    }
    if (
      contour.closed === true &&
      (!samePoint(points[0] as JsonValue, points[points.length - 1] as JsonValue) ||
        !samePoint(firstSegment.start as JsonValue, lastSegment.end as JsonValue))
    ) {
      reject("PROJECT_JSON_INVALID");
    }
    const sourceIds = array(contour.source_primitive_ids, "PROJECT_JSON_INVALID");
    if (sourceIds.length > 0 && sourceIds.length !== segments.length) {
      reject("PROJECT_JSON_INVALID");
    }
  }
  if (outerCount !== number(outline.outer_contour_count, "PROJECT_JSON_INVALID")) {
    reject("PROJECT_JSON_INVALID");
  }
}

function validateManifestSemantics(manifest: JsonRecord): void {
  const sources = array(manifest.source_files, "MANIFEST_JSON_INVALID");
  const sourceIds: string[] = [];
  const foldedPaths: string[] = [];
  for (const sourceValue of sources) {
    const source = record(sourceValue, "MANIFEST_JSON_INVALID");
    sourceIds.push(string(source.source_file_id, "MANIFEST_JSON_INVALID"));
    const path = string(source.logical_path, "MANIFEST_JSON_INVALID");
    validateSafePath(path, "MANIFEST_JSON_INVALID");
    foldedPaths.push(pythonCasefold(path));
  }
  if (!unique(sourceIds) || !unique(foldedPaths)) {
    reject("MANIFEST_JSON_INVALID");
  }
}

function validateProjectSemantics(project: JsonRecord): void {
  const coordinateSystem = record(project.coordinate_system as JsonValue, "PROJECT_JSON_INVALID");
  if (
    coordinateSystem.unit !== "mm" ||
    coordinateSystem.x_axis !== "right" ||
    coordinateSystem.y_axis !== "up" ||
    coordinateSystem.rotation_degrees !== 0
  ) {
    reject("PROJECT_JSON_INVALID");
  }
  validatePoint(coordinateSystem.origin as JsonValue);

  const projectSourceIds: string[] = [];
  const projectFoldedPaths: string[] = [];
  for (const sourceValue of array(project.source_files, "PROJECT_JSON_INVALID")) {
    const source = record(sourceValue, "PROJECT_JSON_INVALID");
    projectSourceIds.push(string(source.source_file_id, "PROJECT_JSON_INVALID"));
    const path = string(source.logical_path, "PROJECT_JSON_INVALID");
    validateSafePath(path, "PROJECT_JSON_INVALID");
    projectFoldedPaths.push(pythonCasefold(path));
  }
  if (!unique(projectSourceIds) || !unique(projectFoldedPaths)) {
    reject("PROJECT_JSON_INVALID");
  }

  const collections: readonly [string, readonly JsonValue[]][] = [
    ["layer_id", array(project.layers, "PROJECT_JSON_INVALID")],
    ["drill_id", array(project.drills, "PROJECT_JSON_INVALID")],
    ["slot_id", array(project.drill_slots, "PROJECT_JSON_INVALID")],
    ["diagnostic_id", array(project.source_diagnostics, "PROJECT_JSON_INVALID")],
  ];
  for (const [key, values] of collections) {
    const ids = values.map((value) =>
      string(record(value, "PROJECT_JSON_INVALID")[key], "PROJECT_JSON_INVALID"),
    );
    if (!unique(ids)) {
      reject("PROJECT_JSON_INVALID");
    }
  }

  for (const layerValue of array(project.layers, "PROJECT_JSON_INVALID")) {
    const layer = record(layerValue, "PROJECT_JSON_INVALID");
    const primitives = array(layer.primitives, "PROJECT_JSON_INVALID");
    const primitiveIds = primitives.map((value) =>
      string(record(value, "PROJECT_JSON_INVALID").primitive_id, "PROJECT_JSON_INVALID"),
    );
    if (!unique(primitiveIds)) {
      reject("PROJECT_JSON_INVALID");
    }
    primitives.forEach(validatePrimitive);
    if (layer.bounding_box !== null) {
      validateBounds(layer.bounding_box as JsonValue);
    }
  }

  if (project.board_outline !== null) {
    validateOutline(project.board_outline as JsonValue);
  }
  for (const drillValue of array(project.drills, "PROJECT_JSON_INVALID")) {
    const drill = record(drillValue, "PROJECT_JSON_INVALID");
    validatePoint(drill.position as JsonValue);
    validateProvenance(drill.provenance as JsonValue, "PROJECT_JSON_INVALID");
  }
  for (const slotValue of array(project.drill_slots, "PROJECT_JSON_INVALID")) {
    const slot = record(slotValue, "PROJECT_JSON_INVALID");
    validatePoint(slot.start as JsonValue);
    validatePoint(slot.end as JsonValue);
    validateProvenance(slot.provenance as JsonValue, "PROJECT_JSON_INVALID");
    if (
      (slot.kind === "arc" && (slot.center === null || slot.clockwise === null)) ||
      (slot.kind === "line" && (slot.center !== null || slot.clockwise !== null))
    ) {
      reject("PROJECT_JSON_INVALID");
    }
    if (slot.center !== null) {
      validatePoint(slot.center as JsonValue);
    }
  }
  for (const componentValue of array(project.components, "PROJECT_JSON_INVALID")) {
    const component = record(componentValue, "PROJECT_JSON_INVALID");
    validatePoint(component.position as JsonValue);
    validateProvenance(component.provenance as JsonValue, "PROJECT_JSON_INVALID");
  }
  for (const itemValue of array(project.bom_items, "PROJECT_JSON_INVALID")) {
    const item = record(itemValue, "PROJECT_JSON_INVALID");
    if (number(item.quantity, "PROJECT_JSON_INVALID") === 0 && item.dnp !== true) {
      reject("PROJECT_JSON_INVALID");
    }
    validateProvenance(item.provenance as JsonValue, "PROJECT_JSON_INVALID");
  }
}

function validateFinding(value: JsonValue): void {
  const finding = record(value, "FINDINGS_JSON_INVALID");
  if (
    UNCERTAIN_CATEGORIES.has(string(finding.category, "FINDINGS_JSON_INVALID")) &&
    finding.requires_human_confirmation !== true
  ) {
    reject("FINDINGS_JSON_INVALID");
  }
  if (finding.measurement !== null) {
    const measurement = record(finding.measurement as JsonValue, "FINDINGS_JSON_INVALID");
    if (measurement.config_path !== finding.config_path) {
      reject("FINDINGS_JSON_INVALID");
    }
  }
  if (finding.location !== null) {
    const point = record(finding.location as JsonValue, "FINDINGS_JSON_INVALID");
    if (point.unit !== "mm") {
      reject("FINDINGS_JSON_INVALID");
    }
  }
  for (const evidenceValue of array(finding.evidence, "FINDINGS_JSON_INVALID")) {
    const evidence = record(evidenceValue, "FINDINGS_JSON_INVALID");
    validateProvenance(evidence.provenance as JsonValue, "FINDINGS_JSON_INVALID");
    if (evidence.witness_bounds !== null) {
      const bounds = record(evidence.witness_bounds as JsonValue, "FINDINGS_JSON_INVALID");
      const minimum = record(bounds.minimum as JsonValue, "FINDINGS_JSON_INVALID");
      const maximum = record(bounds.maximum as JsonValue, "FINDINGS_JSON_INVALID");
      if (
        minimum.unit !== "mm" ||
        maximum.unit !== "mm" ||
        number(minimum.x, "FINDINGS_JSON_INVALID") > number(maximum.x, "FINDINGS_JSON_INVALID") ||
        number(minimum.y, "FINDINGS_JSON_INVALID") > number(maximum.y, "FINDINGS_JSON_INVALID")
      ) {
        reject("FINDINGS_JSON_INVALID");
      }
    }
  }
}

function validateGap(value: JsonValue, policyVersion: string): void {
  const gap = record(value, "FINDINGS_JSON_INVALID");
  if (gap.policy_version !== policyVersion) {
    reject("FINDINGS_JSON_INVALID");
  }
  if (number(gap.observed, "FINDINGS_JSON_INVALID") <= number(gap.limit, "FINDINGS_JSON_INVALID")) {
    reject("FINDINGS_JSON_INVALID");
  }
}

function validateRuleResult(value: JsonValue, policyVersion: string): void {
  const result = record(value, "FINDINGS_JSON_INVALID");
  const outcome = string(result.outcome, "FINDINGS_JSON_INVALID");
  const coverage = string(result.coverage, "FINDINGS_JSON_INVALID");
  const findings = array(result.findings, "FINDINGS_JSON_INVALID");
  const gaps = array(result.coverage_gaps, "FINDINGS_JSON_INVALID");
  const hasFindings = findings.length > 0;
  if ((outcome === "FINDINGS") !== hasFindings) {
    reject("FINDINGS_JSON_INVALID");
  }
  const needsReason = outcome === "SKIPPED" || outcome === "FAILED";
  if (needsReason !== (result.reason !== null)) {
    reject("FINDINGS_JSON_INVALID");
  }
  if (outcome === "SKIPPED" && coverage !== "NONE") {
    reject("FINDINGS_JSON_INVALID");
  }
  if (coverage === "FULL" && gaps.length > 0) {
    reject("FINDINGS_JSON_INVALID");
  }
  if (gaps.length > 0 && (outcome === "PASS" || outcome === "FINDINGS") && coverage !== "PARTIAL") {
    reject("FINDINGS_JSON_INVALID");
  }
  if (outcome === "FAILED" && gaps.length > 0) {
    reject("FINDINGS_JSON_INVALID");
  }
  if (gaps.length > 0 && outcome === "SKIPPED" && result.reason !== "COMPUTATION_LIMIT") {
    reject("FINDINGS_JSON_INVALID");
  }
  if (
    result.applicable_object_count !== null &&
    number(result.evaluated_object_count, "FINDINGS_JSON_INVALID") >
      number(result.applicable_object_count, "FINDINGS_JSON_INVALID")
  ) {
    reject("FINDINGS_JSON_INVALID");
  }
  for (const findingValue of findings) {
    validateFinding(findingValue);
    const finding = record(findingValue, "FINDINGS_JSON_INVALID");
    if (finding.rule_id !== result.rule_id || finding.rule_version !== result.rule_version) {
      reject("FINDINGS_JSON_INVALID");
    }
  }
  for (const gap of gaps) {
    validateGap(gap, policyVersion);
  }
}

function diagnosticKey(value: JsonValue): string {
  const diagnostic = record(value, "FINDINGS_JSON_INVALID");
  return [diagnostic.category, diagnostic.stage, diagnostic.code, diagnostic.summary].join(
    "\u0000",
  );
}

function validateReviewSemantics(review: JsonRecord): void {
  const policy = record(review.geometry_resource_policy as JsonValue, "FINDINGS_JSON_INVALID");
  const policyVersion = string(policy.policy_version, "FINDINGS_JSON_INVALID");
  const results = array(review.rule_results, "FINDINGS_JSON_INVALID");
  const resultIds = results.map((value) =>
    string(record(value, "FINDINGS_JSON_INVALID").rule_id, "FINDINGS_JSON_INVALID"),
  );
  if (!unique(resultIds)) {
    reject("FINDINGS_JSON_INVALID");
  }
  for (const value of results) {
    validateRuleResult(value, policyVersion);
  }

  const flattenedFindings = results.flatMap((value) =>
    array(record(value, "FINDINGS_JSON_INVALID").findings, "FINDINGS_JSON_INVALID"),
  );
  const findings = array(review.findings, "FINDINGS_JSON_INVALID");
  if (
    findings.length !== flattenedFindings.length ||
    findings.some((value, index) => !sameJson(value, flattenedFindings[index] as JsonValue))
  ) {
    reject("FINDINGS_JSON_INVALID");
  }
  const flattenedGaps = results.flatMap((value) =>
    array(record(value, "FINDINGS_JSON_INVALID").coverage_gaps, "FINDINGS_JSON_INVALID"),
  );
  const gaps = array(review.coverage_gaps, "FINDINGS_JSON_INVALID");
  if (
    gaps.length !== flattenedGaps.length ||
    gaps.some((value, index) => !sameJson(value, flattenedGaps[index] as JsonValue))
  ) {
    reject("FINDINGS_JSON_INVALID");
  }
  const findingIds = findings.map((value) =>
    string(record(value, "FINDINGS_JSON_INVALID").finding_id, "FINDINGS_JSON_INVALID"),
  );
  if (!unique(findingIds)) {
    reject("FINDINGS_JSON_INVALID");
  }
  const risks = array(review.risk_modes, "FINDINGS_JSON_INVALID").map((value) =>
    string(value, "FINDINGS_JSON_INVALID"),
  );
  if (!sortedUnique(risks)) {
    reject("FINDINGS_JSON_INVALID");
  }
  const hasLimitRisk = risks.includes("ANALYSIS_LIMITATION");
  if (hasLimitRisk !== gaps.length > 0) {
    reject("FINDINGS_JSON_INVALID");
  }
  for (const value of gaps) {
    validateGap(value, policyVersion);
  }

  const diagnostics = array(review.analysis_diagnostics, "FINDINGS_JSON_INVALID");
  for (const value of diagnostics) {
    const diagnostic = record(value, "FINDINGS_JSON_INVALID");
    validateSafeDiagnosticSummary(
      string(diagnostic.summary, "FINDINGS_JSON_INVALID"),
      "FINDINGS_JSON_INVALID",
    );
  }
  const keys = diagnostics.map(diagnosticKey);
  if (!sortedUnique(keys)) {
    reject("FINDINGS_JSON_INVALID");
  }
  const failed = review.overall_status === ANALYSIS_FAILED;
  if (failed !== diagnostics.length > 0) {
    reject("FINDINGS_JSON_INVALID");
  }
  if (failed && (results.length > 0 || findings.length > 0)) {
    reject("FINDINGS_JSON_INVALID");
  }
}

function sourceSpanLabel(provenance: JsonRecord): string {
  if (provenance.source_span === null) {
    return "none";
  }
  const span = record(provenance.source_span as JsonValue, "FINDINGS_JSON_INVALID");
  const display = (value: JsonValue | undefined): string =>
    value === null ? "None" : String(value);
  return `${display(span.start_line)}:${display(span.end_line)}:${display(
    span.start_byte,
  )}:${display(span.end_byte)}`;
}

async function expectedFindingId(
  finding: JsonRecord,
  profileSha256: string,
  parsedReview: ParsedJson,
  index: number,
): Promise<string> {
  const evidenceIds = [`profile-config:${string(finding.config_path, "FINDINGS_JSON_INVALID")}`];
  for (const evidenceValue of array(finding.evidence, "FINDINGS_JSON_INVALID")) {
    const provenance = record(
      record(evidenceValue, "FINDINGS_JSON_INVALID").provenance as JsonValue,
      "FINDINGS_JSON_INVALID",
    );
    evidenceIds.push(
      provenance.object_id === null
        ? `${string(
            provenance.source_file_id,
            "FINDINGS_JSON_INVALID",
          )}:${sourceSpanLabel(provenance)}`
        : string(provenance.object_id, "FINDINGS_JSON_INVALID"),
    );
  }
  evidenceIds.sort(compareUnicodeCodePoints);
  const root = `/findings/${index}`;
  const location =
    finding.location === null
      ? "null"
      : canonicalCompact(
          finding.location as JsonValue,
          parsedReview.numberLexemes,
          `${root}/location`,
        );
  const measurement =
    finding.measurement === null
      ? "null"
      : canonicalCompact(
          finding.measurement as JsonValue,
          parsedReview.numberLexemes,
          `${root}/measurement`,
        );
  const payload =
    `{"evidence_ids":${JSON.stringify(evidenceIds)},` +
    `"location":${location},"measurement":${measurement},` +
    `"profile_sha256":${JSON.stringify(profileSha256)},` +
    `"rule_id":${JSON.stringify(string(finding.rule_id, "FINDINGS_JSON_INVALID"))},` +
    `"rule_version":${JSON.stringify(string(finding.rule_version, "FINDINGS_JSON_INVALID"))}}`;
  return sha256Prefix(payload, "fnd");
}

export interface LayerDetail {
  readonly layerId: string;
  readonly role: string;
  readonly side: string;
}

export interface FindingDetail {
  readonly findingId: string;
  readonly ruleId: string;
  readonly severity: string;
  readonly title: string;
}

export interface CrossArtifactEvidence {
  readonly projectId: string;
  readonly profileId: string;
  readonly profileSha256: string;
  readonly findingIds: ReadonlySet<string>;
  readonly sourceIds: ReadonlySet<string>;
  readonly layerIds: ReadonlySet<string>;
  readonly layerDetails: readonly LayerDetail[];
  readonly findingDetails: readonly FindingDetail[];
  readonly summary: ReviewSummary;
}

export async function validateModels(
  parsedManifest: ParsedJson,
  parsedProject: ParsedJson,
  parsedReview: ParsedJson,
): Promise<CrossArtifactEvidence> {
  const manifest = record(parsedManifest.value, "MANIFEST_JSON_INVALID");
  const project = record(parsedProject.value, "PROJECT_JSON_INVALID");
  const review = record(parsedReview.value, "FINDINGS_JSON_INVALID");
  validateManifestSemantics(manifest);
  validateProjectSemantics(project);
  validateReviewSemantics(review);

  if (
    !sameJson(project.manifest as JsonValue, manifest) ||
    project.project_id !== manifest.project_id ||
    review.project_id !== project.project_id
  ) {
    reject("ARTIFACT_PROJECT_ID_MISMATCH");
  }
  const requirements = record(
    project.fabrication_requirements as JsonValue,
    "PROJECT_JSON_INVALID",
  );
  if (
    review.profile_id !== requirements.profile_id ||
    review.profile_sha256 !== requirements.profile_sha256
  ) {
    reject("ARTIFACT_PROFILE_ID_MISMATCH");
  }

  const sourceValues = array(manifest.source_files, "MANIFEST_JSON_INVALID");
  const sourcePairs: [string, string][] = [];
  const sourceIds = new Set<string>();
  for (const sourceValue of sourceValues) {
    const source = record(sourceValue, "MANIFEST_JSON_INVALID");
    const path = string(source.logical_path, "MANIFEST_JSON_INVALID");
    const digest = string(source.sha256, "MANIFEST_JSON_INVALID");
    const expectedSourceId = await sha256Prefix(
      `{"logical_path":${JSON.stringify(path)},"sha256":${JSON.stringify(digest)}}`,
      "src",
    );
    const sourceId = string(source.source_file_id, "MANIFEST_JSON_INVALID");
    if (sourceId !== expectedSourceId) {
      reject("ARTIFACT_STABLE_ID_MISMATCH");
    }
    sourceIds.add(sourceId);
    sourcePairs.push([path, digest]);
  }
  sourcePairs.sort((left, right) => {
    const pathOrder = compareUnicodeCodePoints(left[0], right[0]);
    return pathOrder === 0 ? compareUnicodeCodePoints(left[1], right[1]) : pathOrder;
  });
  const expectedProjectId = await sha256Prefix(JSON.stringify(sourcePairs), "prj");
  const projectId = string(project.project_id, "PROJECT_JSON_INVALID");
  if (projectId !== expectedProjectId) {
    reject("ARTIFACT_STABLE_ID_MISMATCH");
  }

  const projectSources = array(project.source_files, "PROJECT_JSON_INVALID");
  if (
    projectSources.length !== sourceValues.length ||
    projectSources.some(
      (value, index) =>
        string(record(value, "PROJECT_JSON_INVALID").source_file_id, "PROJECT_JSON_INVALID") !==
        string(
          record(sourceValues[index] as JsonValue, "MANIFEST_JSON_INVALID").source_file_id,
          "MANIFEST_JSON_INVALID",
        ),
    )
  ) {
    reject("PROJECT_JSON_INVALID");
  }

  const layerValues = array(project.layers, "PROJECT_JSON_INVALID");
  const layerIds = new Set(
    layerValues.map((value) =>
      string(record(value, "PROJECT_JSON_INVALID").layer_id, "PROJECT_JSON_INVALID"),
    ),
  );
  const layerDetails: LayerDetail[] = layerValues.map((value) => {
    const layer = record(value, "PROJECT_JSON_INVALID");
    return {
      layerId: string(layer.layer_id, "PROJECT_JSON_INVALID"),
      role: string(layer.role, "PROJECT_JSON_INVALID"),
      side: string(layer.side, "PROJECT_JSON_INVALID"),
    };
  });
  const layersById = new Map(
    layerValues.map((value) => {
      const layer = record(value, "PROJECT_JSON_INVALID");
      return [
        string(layer.layer_id, "PROJECT_JSON_INVALID"),
        string(layer.source_file_id, "PROJECT_JSON_INVALID"),
      ] as const;
    }),
  );
  const findings = array(review.findings, "FINDINGS_JSON_INVALID");
  const profileSha256 = string(review.profile_sha256, "FINDINGS_JSON_INVALID");
  const findingIds = new Set<string>();
  const findingDetails: FindingDetail[] = [];
  for (let index = 0; index < findings.length; index += 1) {
    const finding = record(findings[index] as JsonValue, "FINDINGS_JSON_INVALID");
    const referencedLayers = new Set(
      array(finding.layer_ids, "FINDINGS_JSON_INVALID").map((value) =>
        string(value, "FINDINGS_JSON_INVALID"),
      ),
    );
    for (const evidenceValue of array(finding.evidence, "FINDINGS_JSON_INVALID")) {
      const evidence = record(evidenceValue, "FINDINGS_JSON_INVALID");
      const provenance = record(evidence.provenance as JsonValue, "FINDINGS_JSON_INVALID");
      if (!sourceIds.has(string(provenance.source_file_id, "FINDINGS_JSON_INVALID"))) {
        reject("FINDING_SOURCE_EVIDENCE_MISMATCH");
      }
      if (evidence.layer_id !== null) {
        referencedLayers.add(string(evidence.layer_id, "FINDINGS_JSON_INVALID"));
      }
    }
    if ([...referencedLayers].some((layerId) => !layerIds.has(layerId))) {
      reject("FINDING_LAYER_EVIDENCE_MISMATCH");
    }
    const actualId = string(finding.finding_id, "FINDINGS_JSON_INVALID");
    if (actualId !== (await expectedFindingId(finding, profileSha256, parsedReview, index))) {
      reject("FINDING_STABLE_ID_MISMATCH");
    }
    findingIds.add(actualId);
    findingDetails.push({
      findingId: actualId,
      ruleId: string(finding.rule_id, "FINDINGS_JSON_INVALID"),
      severity: string(finding.severity, "FINDINGS_JSON_INVALID"),
      title: string(finding.title, "FINDINGS_JSON_INVALID"),
    });
  }

  const reviewPolicy = record(
    review.geometry_resource_policy as JsonValue,
    "FINDINGS_JSON_INVALID",
  );
  for (const gapValue of array(review.coverage_gaps, "FINDINGS_JSON_INVALID")) {
    const gap = record(gapValue, "FINDINGS_JSON_INVALID");
    const sourceId = nullableString(gap.source_file_id, "FINDINGS_JSON_INVALID");
    const layerId = nullableString(gap.layer_id, "FINDINGS_JSON_INVALID");
    if (sourceId !== null && !sourceIds.has(sourceId)) {
      reject("COVERAGE_GAP_SOURCE_EVIDENCE_MISMATCH");
    }
    if (layerId !== null && !layerIds.has(layerId)) {
      reject("COVERAGE_GAP_LAYER_EVIDENCE_MISMATCH");
    }
    if (layerId !== null && sourceId !== null && layersById.get(layerId) !== sourceId) {
      reject("COVERAGE_GAP_SOURCE_LAYER_MISMATCH");
    }
    if (gap.policy_version !== reviewPolicy.policy_version) {
      reject("COVERAGE_GAP_POLICY_MISMATCH");
    }
    if (
      number(gap.observed, "FINDINGS_JSON_INVALID") <= number(gap.limit, "FINDINGS_JSON_INVALID")
    ) {
      reject("COVERAGE_GAP_LIMIT_INVALID");
    }
  }

  if (review.overall_status !== ANALYSIS_FAILED) {
    const expectedRisks = new Set<string>();
    for (const findingValue of findings) {
      expectedRisks.add(
        string(record(findingValue, "FINDINGS_JSON_INVALID").category, "FINDINGS_JSON_INVALID"),
      );
    }
    for (const uncertaintyValue of array(project.uncertainties, "PROJECT_JSON_INVALID")) {
      expectedRisks.add(
        string(record(uncertaintyValue, "PROJECT_JSON_INVALID").risk_mode, "PROJECT_JSON_INVALID"),
      );
    }
    if (array(review.coverage_gaps, "FINDINGS_JSON_INVALID").length > 0) {
      expectedRisks.add("ANALYSIS_LIMITATION");
    }
    const actual = array(review.risk_modes, "FINDINGS_JSON_INVALID").map((value) =>
      string(value, "FINDINGS_JSON_INVALID"),
    );
    const expected = [...expectedRisks].sort(compareUnicodeCodePoints);
    if (
      actual.length !== expected.length ||
      actual.some((value, index) => value !== expected[index])
    ) {
      reject("REVIEW_RISK_MODE_MISMATCH");
    }
  }

  const diagnostics = array(review.analysis_diagnostics, "FINDINGS_JSON_INVALID").map(
    (value): ViewerDiagnostic => {
      const diagnostic = record(value, "FINDINGS_JSON_INVALID");
      return {
        code: string(diagnostic.code, "FINDINGS_JSON_INVALID"),
        summary: string(diagnostic.summary, "FINDINGS_JSON_INVALID"),
      };
    },
  );
  const summary: ReviewSummary = {
    projectId,
    profileId: string(review.profile_id, "FINDINGS_JSON_INVALID"),
    profileSha256,
    overallStatus: string(review.overall_status, "FINDINGS_JSON_INVALID"),
    sourceCount: sourceValues.length,
    layerCount: layerValues.length,
    drillCount: array(project.drills, "PROJECT_JSON_INVALID").length,
    slotCount: array(project.drill_slots, "PROJECT_JSON_INVALID").length,
    placementCount: array(project.components, "PROJECT_JSON_INVALID").length,
    bomItemCount: array(project.bom_items, "PROJECT_JSON_INVALID").length,
    ruleCount: array(review.rule_results, "FINDINGS_JSON_INVALID").length,
    findingCount: findings.length,
    coverageGapCount: array(review.coverage_gaps, "FINDINGS_JSON_INVALID").length,
    riskModes: array(review.risk_modes, "FINDINGS_JSON_INVALID").map((value) =>
      string(value, "FINDINGS_JSON_INVALID"),
    ),
    diagnostics,
    disclaimer: string(review.disclaimer, "FINDINGS_JSON_INVALID"),
    layers: [],
    findings: [],
  };
  return {
    projectId,
    profileId: summary.profileId,
    profileSha256,
    findingIds,
    sourceIds,
    layerIds,
    layerDetails,
    findingDetails,
    summary,
  };
}
