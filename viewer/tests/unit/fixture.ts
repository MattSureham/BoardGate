import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { COMPLETE_ARTIFACT_PATHS } from "../../src/contracts";

const viewerDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const repositoryDirectory = resolve(viewerDirectory, "..");

export interface GeneratedBundle {
  readonly directory: string;
  readonly files: ReadonlyMap<string, Blob>;
  cleanup(): void;
}

export function generateValidBundle(fixtureName = "valid_minimal_board"): GeneratedBundle {
  const temporaryDirectory = mkdtempSync(join(tmpdir(), "boardgate-viewer-unit-"));
  const output = join(temporaryDirectory, "valid-ready");
  execFileSync(
    "uv",
    [
      "run",
      "pcb-review",
      "inspect",
      `tests/fixtures/${fixtureName}`,
      "--rules",
      "rules/default.yaml",
      "--output",
      output,
      "--fail-on",
      "none",
    ],
    {
      cwd: repositoryDirectory,
      encoding: "utf8",
      stdio: "pipe",
    },
  );
  const files = new Map(
    COMPLETE_ARTIFACT_PATHS.map((path) => [path, new Blob([readFileSync(join(output, path))])]),
  );
  return {
    directory: output,
    files,
    cleanup: () => rmSync(temporaryDirectory, { recursive: true, force: true }),
  };
}

export async function replaceText(
  files: ReadonlyMap<string, Blob>,
  path: string,
  mutate: (payload: string) => string,
): Promise<ReadonlyMap<string, Blob>> {
  const replaced = new Map(files);
  const current = files.get(path);
  if (current === undefined) {
    throw new Error(`missing fixture ${path}`);
  }
  replaced.set(path, new Blob([mutate(await current.text())]));
  return replaced;
}
