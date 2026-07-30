import type { ValidationResult, ViewerError } from "../contracts";

const ERROR_SUMMARIES = {
  ARTIFACT_INVENTORY_MISMATCH:
    "The selected directory does not contain exactly one complete BoardGate review bundle.",
  ARTIFACT_RESOURCE_LIMIT: "The selected bundle exceeds the offline viewer resource policy.",
  ARTIFACT_UTF8_INVALID: "An artifact is not canonical UTF-8 text.",
  ARTIFACT_JSON_INVALID:
    "A JSON artifact does not satisfy the bounded deterministic JSON contract.",
  ARTIFACT_JSON_NONDETERMINISTIC:
    "A deterministic JSON artifact is not in canonical serialized form.",
  MANIFEST_JSON_INVALID: "manifest.json does not satisfy its strict public contract.",
  PROJECT_JSON_INVALID: "project.json does not satisfy its strict public contract.",
  FINDINGS_JSON_INVALID: "findings.json does not satisfy its strict public contract.",
  ARTIFACT_PROJECT_ID_MISMATCH: "The selected artifacts do not describe one identical project.",
  ARTIFACT_PROFILE_ID_MISMATCH: "The selected artifacts do not use one identical rule profile.",
  ARTIFACT_STABLE_ID_MISMATCH:
    "A project or source identifier is not derived from canonical evidence.",
  FINDING_STABLE_ID_MISMATCH: "A Finding identifier is not derived from canonical evidence.",
  FINDING_SOURCE_EVIDENCE_MISMATCH:
    "Finding evidence references a source outside the selected manifest.",
  FINDING_LAYER_EVIDENCE_MISMATCH:
    "Finding evidence references a layer outside the selected project.",
  COVERAGE_GAP_SOURCE_EVIDENCE_MISMATCH:
    "Coverage-gap evidence references a source outside the selected manifest.",
  COVERAGE_GAP_LAYER_EVIDENCE_MISMATCH:
    "Coverage-gap evidence references a layer outside the selected project.",
  COVERAGE_GAP_SOURCE_LAYER_MISMATCH: "Coverage-gap source and layer evidence are inconsistent.",
  COVERAGE_GAP_POLICY_MISMATCH: "Coverage-gap evidence does not use the persisted resource policy.",
  COVERAGE_GAP_LIMIT_INVALID: "Coverage-gap evidence does not exceed its declared resource limit.",
  REVIEW_RISK_MODE_MISMATCH: "Review risk modes do not match the admitted evidence.",
  REPORT_REVIEW_ID_MISMATCH: "The report metadata does not match the selected project and profile.",
  REPORT_FINDING_ID_MISMATCH: "The report Finding identifiers do not match findings.json.",
  SVG_ACTIVE_XML_REJECTED:
    "The preview contains an active XML declaration that is not safe to load.",
  SVG_XML_INVALID: "The preview is not a well-formed SVG document.",
  SVG_ROOT_INVALID: "The preview document root is not an SVG element.",
  SVG_SCRIPT_REJECTED: "The preview contains a script element.",
  SVG_ACTIVE_ELEMENT_REJECTED: "The preview contains an embedded active document element.",
  SVG_EVENT_HANDLER_REJECTED: "The preview contains an event-handler attribute.",
  SVG_EXTERNAL_REFERENCE_REJECTED: "The preview attempts to load or link to an external resource.",
  SVG_REVIEW_ID_MISMATCH: "The preview metadata does not match the selected project and profile.",
  SVG_FINDING_ID_MISMATCH: "The preview Finding identifiers do not match findings.json.",
  RUN_LOG_TERMINATOR_MISSING: "The structured run log is missing its final newline.",
  RUN_LOG_LINE_INVALID: "The structured run log contains an invalid line.",
  RUN_LOG_EVENT_INVALID: "A structured run-log event does not satisfy its strict public contract.",
  RUN_LOG_EMPTY: "The structured run log does not contain an event.",
  RUN_LOG_ID_MISMATCH: "The structured run log contains more than one run identifier.",
  RUN_LOG_PROJECT_MISMATCH: "The structured run log does not match the selected project.",
  RUN_LOG_SEQUENCE_INVALID: "Structured run-log sequence values are not strictly increasing.",
  RUN_VARIANCE_LEAKED: "Run-varying data occurs outside the structured run log.",
  VIEWER_INTERNAL_ERROR:
    "The viewer could not validate this bundle without exposing partial results.",
} as const;

export type ViewerErrorCode = keyof typeof ERROR_SUMMARIES;

export class AdmissionError extends Error {
  readonly viewerError: ViewerError;

  constructor(code: ViewerErrorCode) {
    super(ERROR_SUMMARIES[code]);
    this.name = "AdmissionError";
    this.viewerError = Object.freeze({ code, summary: ERROR_SUMMARIES[code] });
  }
}

export function reject(code: ViewerErrorCode): never {
  throw new AdmissionError(code);
}

export function failureFrom(error: unknown): ValidationResult {
  if (error instanceof AdmissionError) {
    return { ok: false, error: error.viewerError };
  }
  return {
    ok: false,
    error: {
      code: "VIEWER_INTERNAL_ERROR",
      summary: ERROR_SUMMARIES.VIEWER_INTERNAL_ERROR,
    },
  };
}
