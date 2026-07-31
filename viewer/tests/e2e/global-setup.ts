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
  const spatialOutput = join(temporaryDirectory, "spatial-findings");
  const legendOutput = join(temporaryDirectory, "legend-findings");

  const inspect = (fixture: string, destination: string): void => {
    execFileSync(
      "uv",
      [
        "run",
        "pcb-review",
        "inspect",
        `tests/fixtures/${fixture}`,
        "--rules",
        "rules/default.yaml",
        "--output",
        destination,
      ],
      {
        cwd: repositoryDirectory,
        encoding: "utf8",
        stdio: "pipe",
      },
    );
  };

  inspect("valid_minimal_board", output);
  inspect("copper_too_close_to_edge", spatialOutput);
  inspect("missing_drill", legendOutput);

  process.env.BOARDGATE_VIEWER_E2E_BUNDLE = output;
  process.env.BOARDGATE_VIEWER_E2E_SPATIAL_BUNDLE = spatialOutput;
  process.env.BOARDGATE_VIEWER_E2E_LEGEND_BUNDLE = legendOutput;
  mkdirSync(invalidOutput);
  writeFileSync(join(invalidOutput, "manifest.json"), "{}\n", "utf8");
  process.env.BOARDGATE_VIEWER_E2E_INVALID_BUNDLE = invalidOutput;
  process.env.BOARDGATE_VIEWER_E2E_HTML = resolve(viewerDirectory, "boardgate-viewer.html");

  return () => {
    rmSync(temporaryDirectory, { recursive: true, force: true });
  };
}
