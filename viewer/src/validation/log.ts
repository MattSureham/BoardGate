import type { ViewerResourcePolicy } from "../policy";
import { reject } from "./errors";
import type { JsonValue } from "./json";
import { isRecord, parseCompactJson } from "./json";
import { validateSafeDiagnosticSummary } from "./safe-text";
import { assertSchema } from "./schema";

type JsonRecord = Record<string, JsonValue>;

const OFFSET_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

function record(value: JsonValue): JsonRecord {
  if (!isRecord(value)) {
    reject("RUN_LOG_EVENT_INVALID");
  }
  return value;
}

function text(value: JsonValue | undefined): string {
  if (typeof value !== "string") {
    reject("RUN_LOG_EVENT_INVALID");
  }
  return value;
}

function integer(value: JsonValue | undefined): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) {
    reject("RUN_LOG_EVENT_INVALID");
  }
  return value;
}

function sortedUniqueStrings(value: JsonValue | undefined): boolean {
  if (!Array.isArray(value)) {
    return false;
  }
  const strings = value.filter((item): item is string => typeof item === "string");
  return (
    strings.length === value.length &&
    new Set(strings).size === strings.length &&
    strings.every((item, index) => index === 0 || (strings[index - 1] ?? "") < item)
  );
}

function validateSortedMap(value: JsonValue | undefined, numeric: boolean): void {
  const map = record(value as JsonValue);
  const keys = Object.keys(map);
  if (keys.some((key, index) => !key || (index > 0 && (keys[index - 1] ?? "") >= key))) {
    reject("RUN_LOG_EVENT_INVALID");
  }
  for (const value of Object.values(map)) {
    if (
      (numeric && (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0)) ||
      (!numeric && (typeof value !== "string" || value.length === 0))
    ) {
      reject("RUN_LOG_EVENT_INVALID");
    }
  }
}

export interface RunLogAdmission {
  readonly runId: string;
  readonly projectId: string;
  readonly eventCount: number;
}

export function validateRunLog(payload: string, policy: ViewerResourcePolicy): RunLogAdmission {
  if (!payload.endsWith("\n")) {
    reject("RUN_LOG_TERMINATOR_MISSING");
  }
  const lines = payload.slice(0, -1).split("\n");
  if (lines.length === 0 || lines.some((line) => line.length === 0)) {
    reject("RUN_LOG_LINE_INVALID");
  }
  if (lines.length > policy.maxJsonlEvents) {
    reject("ARTIFACT_RESOURCE_LIMIT");
  }
  let runId: string | undefined;
  let projectId: string | undefined;
  let previousSequence = 0;
  for (const line of lines) {
    if (new Blob([line]).size > policy.maxJsonlLineBytes) {
      reject("ARTIFACT_RESOURCE_LIMIT");
    }
    const parsed = parseCompactJson(line, policy);
    assertSchema("runLogEvent", parsed.value, "RUN_LOG_EVENT_INVALID");
    const event = record(parsed.value);
    const currentRunId = text(event.run_id);
    const currentProjectId = text(event.project_id);
    const sequence = integer(event.sequence);
    if (runId !== undefined && currentRunId !== runId) {
      reject("RUN_LOG_ID_MISMATCH");
    }
    if (projectId !== undefined && currentProjectId !== projectId) {
      reject("RUN_LOG_PROJECT_MISMATCH");
    }
    if (sequence <= previousSequence) {
      reject("RUN_LOG_SEQUENCE_INVALID");
    }
    const timestamp = text(event.occurred_at);
    if (!OFFSET_TIMESTAMP.test(timestamp) || Number.isNaN(Date.parse(timestamp))) {
      reject("RUN_LOG_EVENT_INVALID");
    }
    validateSafeDiagnosticSummary(text(event.summary), "RUN_LOG_EVENT_INVALID");
    if (
      !sortedUniqueStrings(event.selected_parsers) ||
      !sortedUniqueStrings(event.executed_rules)
    ) {
      reject("RUN_LOG_EVENT_INVALID");
    }
    validateSortedMap(event.file_classification_counts, true);
    validateSortedMap(event.skipped_rule_reasons, false);
    runId = currentRunId;
    projectId = currentProjectId;
    previousSequence = sequence;
  }
  if (runId === undefined || projectId === undefined) {
    reject("RUN_LOG_EMPTY");
  }
  return { runId, projectId, eventCount: lines.length };
}
