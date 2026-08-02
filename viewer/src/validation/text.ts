import type { ViewerResourcePolicy } from "../policy";
import { reject } from "./errors";
import type { CrossArtifactEvidence } from "./semantics";

const FINDING_ID = /\bfnd-[0-9a-f]{16}\b/g;
const REPORT_PROJECT_ID = /^<!-- boardgate-project-id: (prj-[0-9a-f]{16}) -->$/gm;
const REPORT_PROFILE_SHA = /^<!-- boardgate-profile-sha256: ([0-9a-f]{64}) -->$/gm;

function matches(pattern: RegExp, value: string): string[] {
  pattern.lastIndex = 0;
  return Array.from(value.matchAll(pattern), (match) => match[1] as string);
}

function countLines(report: string): number {
  let lines = report.length === 0 ? 0 : 1;
  for (let index = 0; index < report.length; index += 1) {
    if (report.charCodeAt(index) === 10) {
      lines += 1;
    }
  }
  return lines;
}

export function validateReport(
  report: string,
  evidence: CrossArtifactEvidence,
  policy: ViewerResourcePolicy,
): void {
  if (countLines(report) > policy.maxReportLines) {
    reject("ARTIFACT_RESOURCE_LIMIT");
  }
  if (
    report.includes("\u0000") ||
    matches(REPORT_PROJECT_ID, report).length !== 1 ||
    matches(REPORT_PROJECT_ID, report)[0] !== evidence.projectId ||
    matches(REPORT_PROFILE_SHA, report).length !== 1 ||
    matches(REPORT_PROFILE_SHA, report)[0] !== evidence.profileSha256
  ) {
    reject("REPORT_REVIEW_ID_MISMATCH");
  }
  FINDING_ID.lastIndex = 0;
  const reportFindings = new Set(report.match(FINDING_ID) ?? []);
  if (
    reportFindings.size !== evidence.findingIds.size ||
    [...reportFindings].some((findingId) => !evidence.findingIds.has(findingId))
  ) {
    reject("REPORT_FINDING_ID_MISMATCH");
  }
}
