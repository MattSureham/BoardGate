import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const viewerDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const repositoryDirectory = resolve(viewerDirectory, "..");

export default function globalSetup(): () => void {
  const temporaryDirectory = mkdtempSync(join(tmpdir(), "boardgate-viewer-e2e-"));
  const output = join(temporaryDirectory, "valid-ready");
  const invalidOutput = join(temporaryDirectory, "invalid-inventory");

  execFileSync(
    "uv",
    [
      "run",
      "pcb-review",
      "inspect",
      "tests/fixtures/valid_minimal_board",
      "--rules",
      "rules/default.yaml",
      "--output",
      output,
    ],
    {
      cwd: repositoryDirectory,
      encoding: "utf8",
      stdio: "pipe",
    },
  );

  process.env.BOARDGATE_VIEWER_E2E_BUNDLE = output;
  mkdirSync(invalidOutput);
  writeFileSync(join(invalidOutput, "manifest.json"), "{}\n", "utf8");
  process.env.BOARDGATE_VIEWER_E2E_INVALID_BUNDLE = invalidOutput;
  process.env.BOARDGATE_VIEWER_E2E_HTML = resolve(viewerDirectory, "boardgate-viewer.html");

  return () => {
    rmSync(temporaryDirectory, { recursive: true, force: true });
  };
}
