import { findings, manifest, project, runLogEvent } from "../generated/schema-validators";
import { reject, type ViewerErrorCode } from "./errors";
import type { JsonValue } from "./json";

type StandaloneValidator = {
  (value: unknown): boolean;
  readonly errors?: unknown;
};

const VALIDATORS = {
  manifest: manifest as StandaloneValidator,
  project: project as StandaloneValidator,
  findings: findings as StandaloneValidator,
  runLogEvent: runLogEvent as StandaloneValidator,
} as const;

export type ViewerSchemaName = keyof typeof VALIDATORS;

export function assertSchema(
  name: ViewerSchemaName,
  value: JsonValue,
  code: ViewerErrorCode,
): void {
  if (!VALIDATORS[name](value)) {
    reject(code);
  }
}
