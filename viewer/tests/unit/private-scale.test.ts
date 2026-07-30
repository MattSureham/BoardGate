import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { COMPLETE_ARTIFACT_PATHS } from "../../src/contracts";
import { VIEWER_RESOURCE_POLICY } from "../../src/policy";
import { admitBundle } from "../../src/validation";

const privateBundle = process.env.BOARDGATE_VIEWER_PRIVATE_BUNDLE;

describe.runIf(privateBundle !== undefined)("private scale evidence", () => {
  it(
    "admits the caller-provided bundle inside the fixed worker deadline",
    async () => {
      const started = performance.now();
      const files = new Map(
        COMPLETE_ARTIFACT_PATHS.map((path) => [
          path,
          new Blob([readFileSync(join(privateBundle as string, path))]),
        ]),
      );
      const result = await admitBundle(files, VIEWER_RESOURCE_POLICY);
      expect(result).toMatchObject({ ok: true });
      expect(performance.now() - started).toBeLessThan(VIEWER_RESOURCE_POLICY.workerDeadlineMs);
    },
    VIEWER_RESOURCE_POLICY.workerDeadlineMs + 5_000,
  );
});
