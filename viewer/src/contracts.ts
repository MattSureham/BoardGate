export const VIEWER_PROTOCOL_VERSION = "1.0" as const;

export const COMPLETE_ARTIFACT_PATHS = [
  "manifest.json",
  "project.json",
  "findings.json",
  "report.md",
  "preview.svg",
  "logs/run.jsonl",
] as const;

export type ArtifactPath = (typeof COMPLETE_ARTIFACT_PATHS)[number];

export interface ViewerDiagnostic {
  readonly code: string;
  readonly summary: string;
}

export interface ViewerLayer {
  readonly groupId: string;
  readonly layerId: string;
  readonly role: string;
  readonly side: string;
}

export interface ViewerFinding {
  readonly findingId: string;
  readonly ruleId: string;
  readonly severity: string;
  readonly title: string;
  readonly spatial: boolean;
}

export interface ReviewSummary {
  readonly projectId: string;
  readonly profileId: string;
  readonly profileSha256: string;
  readonly overallStatus: string;
  readonly sourceCount: number;
  readonly layerCount: number;
  readonly drillCount: number;
  readonly slotCount: number;
  readonly placementCount: number;
  readonly bomItemCount: number;
  readonly ruleCount: number;
  readonly findingCount: number;
  readonly coverageGapCount: number;
  readonly riskModes: readonly string[];
  readonly diagnostics: readonly ViewerDiagnostic[];
  readonly disclaimer: string;
  readonly layers: readonly ViewerLayer[];
  readonly findings: readonly ViewerFinding[];
}

export interface ViewerError {
  readonly code: string;
  readonly summary: string;
}

export type ValidationResult =
  | {
      readonly ok: true;
      readonly summary: ReviewSummary;
      readonly previewSvg: string;
    }
  | {
      readonly ok: false;
      readonly error: ViewerError;
    };

export interface WorkerFile {
  readonly path: ArtifactPath;
  readonly blob: Blob;
}

export interface WorkerTransferFile {
  readonly path: ArtifactPath;
  readonly bytes: ArrayBuffer;
}

export interface ViewerWorkerRequest {
  readonly kind: "boardgate.viewer.validate";
  readonly protocolVersion: typeof VIEWER_PROTOCOL_VERSION;
  readonly requestId: string;
  readonly files: readonly WorkerTransferFile[];
  readonly policy: import("./policy").ViewerResourcePolicy;
}

export interface ViewerWorkerResponse {
  readonly kind: "boardgate.viewer.result";
  readonly protocolVersion: typeof VIEWER_PROTOCOL_VERSION;
  readonly requestId: string;
  readonly result: ValidationResult;
}
