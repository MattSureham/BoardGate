import type { ArtifactPath } from "./contracts";

export interface ViewerResourcePolicy {
  readonly policyVersion: "1.0";
  readonly maxArtifactBytes: Readonly<Record<ArtifactPath, number>>;
  readonly maxBundleBytes: number;
  readonly maxJsonDepth: number;
  readonly maxJsonEntries: number;
  readonly maxSvgElements: number;
  readonly maxSvgAttributes: number;
  readonly maxJsonlLineBytes: number;
  readonly maxJsonlEvents: number;
  readonly workerDeadlineMs: number;
}

const MEBIBYTE = 1024 * 1024;

export const VIEWER_RESOURCE_POLICY: ViewerResourcePolicy = Object.freeze({
  policyVersion: "1.0",
  maxArtifactBytes: Object.freeze({
    "manifest.json": 4 * MEBIBYTE,
    "project.json": 256 * MEBIBYTE,
    "findings.json": 256 * MEBIBYTE,
    "report.md": 32 * MEBIBYTE,
    "preview.svg": 128 * MEBIBYTE,
    "logs/run.jsonl": 16 * MEBIBYTE,
  }),
  maxBundleBytes: 384 * MEBIBYTE,
  maxJsonDepth: 64,
  maxJsonEntries: 8_000_000,
  maxSvgElements: 250_000,
  maxSvgAttributes: 2_000_000,
  maxJsonlLineBytes: 1 * MEBIBYTE,
  maxJsonlEvents: 10_000,
  workerDeadlineMs: 60_000,
});
