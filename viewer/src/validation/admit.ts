import {
  type ArtifactPath,
  COMPLETE_ARTIFACT_PATHS,
  type ValidationResult,
  type ViewerFinding,
  type ViewerLayer,
} from "../contracts";
import type { ViewerResourcePolicy } from "../policy";
import { failureFrom, reject } from "./errors";
import { compareUnicodeCodePoints, parseCanonicalJson } from "./json";
import { validateRunLog } from "./log";
import { assertSchema } from "./schema";
import { validateModels } from "./semantics";
import { validateSvg } from "./svg";
import { validateReport } from "./text";
import { decodeUtf8, decodeUtf8Bytes } from "./utf8";

const EXPECTED_PATHS = new Set<string>(COMPLETE_ARTIFACT_PATHS);
type ArtifactPayload = Blob | ArrayBuffer;

function assertPolicy(policy: ViewerResourcePolicy): void {
  if (
    policy.policyVersion !== "1.0" ||
    !Number.isSafeInteger(policy.maxBundleBytes) ||
    !Number.isSafeInteger(policy.maxJsonDepth) ||
    !Number.isSafeInteger(policy.maxJsonEntries) ||
    !Number.isSafeInteger(policy.maxSvgElements) ||
    !Number.isSafeInteger(policy.maxSvgAttributes) ||
    !Number.isSafeInteger(policy.maxJsonlLineBytes) ||
    !Number.isSafeInteger(policy.maxJsonlEvents) ||
    !Number.isSafeInteger(policy.maxReportLines) ||
    !Number.isSafeInteger(policy.workerDeadlineMs) ||
    Object.values(policy.maxArtifactBytes).some(
      (limit) => !Number.isSafeInteger(limit) || limit < 1,
    ) ||
    [
      policy.maxBundleBytes,
      policy.maxJsonDepth,
      policy.maxJsonEntries,
      policy.maxSvgElements,
      policy.maxSvgAttributes,
      policy.maxJsonlLineBytes,
      policy.maxJsonlEvents,
      policy.maxReportLines,
      policy.workerDeadlineMs,
    ].some((limit) => limit < 1)
  ) {
    reject("ARTIFACT_RESOURCE_LIMIT");
  }
}

function hasSafeLogicalPath(path: string): boolean {
  return (
    !path.startsWith("/") &&
    !path.includes("\\") &&
    path.split("/").every((part) => part !== "" && part !== "." && part !== "..")
  );
}

function assertInventory(files: ReadonlyMap<string, ArtifactPayload>): void {
  if (
    files.size !== COMPLETE_ARTIFACT_PATHS.length ||
    [...files.keys()].some((path) => !hasSafeLogicalPath(path) || !EXPECTED_PATHS.has(path)) ||
    COMPLETE_ARTIFACT_PATHS.some((path) => !files.has(path))
  ) {
    reject("ARTIFACT_INVENTORY_MISMATCH");
  }
}

function preflightSizes(
  files: ReadonlyMap<string, ArtifactPayload>,
  policy: ViewerResourcePolicy,
): void {
  let total = 0;
  for (const path of COMPLETE_ARTIFACT_PATHS) {
    const blob = files.get(path);
    if (blob === undefined) {
      reject("ARTIFACT_INVENTORY_MISMATCH");
    }
    const size = blob instanceof Blob ? blob.size : blob.byteLength;
    if (size > policy.maxArtifactBytes[path]) {
      reject("ARTIFACT_RESOURCE_LIMIT");
    }
    total += size;
    if (!Number.isSafeInteger(total) || total > policy.maxBundleBytes) {
      reject("ARTIFACT_RESOURCE_LIMIT");
    }
  }
}

async function readArtifacts(
  files: ReadonlyMap<string, ArtifactPayload>,
): Promise<ReadonlyMap<ArtifactPath, string>> {
  const decoded = new Map<ArtifactPath, string>();
  for (const path of COMPLETE_ARTIFACT_PATHS) {
    const blob = files.get(path);
    if (blob === undefined) {
      reject("ARTIFACT_INVENTORY_MISMATCH");
    }
    decoded.set(path, blob instanceof Blob ? await decodeUtf8(blob) : decodeUtf8Bytes(blob));
  }
  return decoded;
}

function artifact(files: ReadonlyMap<ArtifactPath, string>, path: ArtifactPath): string {
  const value = files.get(path);
  if (value === undefined) {
    reject("ARTIFACT_INVENTORY_MISMATCH");
  }
  return value;
}

async function admitPayloads(
  files: ReadonlyMap<string, ArtifactPayload>,
  policy: ViewerResourcePolicy,
): Promise<ValidationResult> {
  try {
    assertPolicy(policy);
    assertInventory(files);
    preflightSizes(files, policy);
    const payloads = await readArtifacts(files);

    const manifestPayload = artifact(payloads, "manifest.json");
    const projectPayload = artifact(payloads, "project.json");
    const findingsPayload = artifact(payloads, "findings.json");
    const reportPayload = artifact(payloads, "report.md");
    const svgPayload = artifact(payloads, "preview.svg");
    const logPayload = artifact(payloads, "logs/run.jsonl");

    const parsedManifest = parseCanonicalJson(manifestPayload, policy);
    assertSchema("manifest", parsedManifest.value, "MANIFEST_JSON_INVALID");
    const parsedProject = parseCanonicalJson(projectPayload, policy);
    assertSchema("project", parsedProject.value, "PROJECT_JSON_INVALID");
    const parsedReview = parseCanonicalJson(findingsPayload, policy);
    assertSchema("findings", parsedReview.value, "FINDINGS_JSON_INVALID");

    const evidence = await validateModels(parsedManifest, parsedProject, parsedReview);
    validateReport(reportPayload, evidence, policy);
    const svgAdmission = validateSvg(svgPayload, evidence, policy);
    const runLog = validateRunLog(logPayload, policy);
    if (runLog.projectId !== evidence.projectId) {
      reject("RUN_LOG_PROJECT_MISMATCH");
    }
    for (const payload of [
      manifestPayload,
      projectPayload,
      findingsPayload,
      reportPayload,
      svgPayload,
    ]) {
      if (payload.includes(runLog.runId)) {
        reject("RUN_VARIANCE_LEAKED");
      }
    }

    if (
      svgAdmission.layerGroups.length !== evidence.layerDetails.length ||
      evidence.layerDetails.some(
        (detail) =>
          !svgAdmission.layerGroups.some(
            (group) =>
              group.layerId === detail.layerId &&
              group.role === detail.role &&
              group.side === detail.side,
          ),
      )
    ) {
      reject("SVG_LAYER_MISMATCH");
    }
    const layers: ViewerLayer[] = svgAdmission.layerGroups
      .map((group) => ({
        groupId: group.groupId,
        layerId: group.layerId,
        role: group.role,
        side: group.side,
      }))
      .sort((left, right) => {
        const roleOrder = compareUnicodeCodePoints(left.role, right.role);
        if (roleOrder !== 0) {
          return roleOrder;
        }
        const sideOrder = compareUnicodeCodePoints(left.side, right.side);
        return sideOrder === 0 ? compareUnicodeCodePoints(left.layerId, right.layerId) : sideOrder;
      });
    const findings: ViewerFinding[] = evidence.findingDetails
      .map((detail) => ({
        ...detail,
        spatial: svgAdmission.spatialFindingIds.has(detail.findingId),
      }))
      .sort((left, right) => compareUnicodeCodePoints(left.findingId, right.findingId));
    return {
      ok: true,
      summary: { ...evidence.summary, layers, findings },
      previewSvg: svgPayload,
      reportMarkdown: reportPayload,
    };
  } catch (error) {
    return failureFrom(error);
  }
}

export function admitBundle(
  files: ReadonlyMap<string, Blob>,
  policy: ViewerResourcePolicy,
): Promise<ValidationResult> {
  return admitPayloads(files, policy);
}

export function admitTransferredBundle(
  files: ReadonlyMap<string, ArrayBuffer>,
  policy: ViewerResourcePolicy,
): Promise<ValidationResult> {
  return admitPayloads(files, policy);
}
