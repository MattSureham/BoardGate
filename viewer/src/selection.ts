import { COMPLETE_ARTIFACT_PATHS, type ViewerError, type WorkerFile } from "./contracts";

const INVENTORY_ERROR: ViewerError = Object.freeze({
  code: "ARTIFACT_INVENTORY_MISMATCH",
  summary: "The selected directory does not contain exactly one complete BoardGate review bundle.",
});

const EXPECTED_PATHS = new Set<string>(COMPLETE_ARTIFACT_PATHS);

export class SelectionError extends Error {
  readonly viewerError: ViewerError;

  constructor(viewerError: ViewerError = INVENTORY_ERROR) {
    super(viewerError.summary);
    this.name = "SelectionError";
    this.viewerError = viewerError;
  }
}

function requireSafePath(path: string): readonly string[] {
  if (path.length === 0 || path.includes("\\") || path.startsWith("/") || path.endsWith("/")) {
    throw new SelectionError();
  }
  const segments = path.split("/");
  if (
    segments.some(
      (segment) =>
        segment.length === 0 || segment === "." || segment === ".." || segment.includes("\0"),
    )
  ) {
    throw new SelectionError();
  }
  return segments;
}

/**
 * Normalize one browser directory selection to BoardGate's six logical paths.
 *
 * `webkitRelativePath` is the evidence used here; `File.name` is intentionally
 * insufficient because it loses the required `logs/run.jsonl` hierarchy.
 */
export function normalizeSelectedFiles(files: Iterable<File>): readonly WorkerFile[] {
  const selections = [...files];
  if (selections.length === 0) {
    throw new SelectionError();
  }

  let commonRoot: string | undefined;
  const byLogicalPath = new Map<string, Blob>();
  const rawPaths = new Set<string>();

  for (const file of selections) {
    const rawPath = file.webkitRelativePath;
    if (rawPaths.has(rawPath)) {
      throw new SelectionError();
    }
    rawPaths.add(rawPath);

    const segments = requireSafePath(rawPath);
    if (segments.length < 2) {
      throw new SelectionError();
    }
    const root = segments[0];
    if (commonRoot === undefined) {
      commonRoot = root;
    } else if (root !== commonRoot) {
      throw new SelectionError();
    }

    const logicalPath = segments.slice(1).join("/");
    requireSafePath(logicalPath);
    if (!EXPECTED_PATHS.has(logicalPath) || byLogicalPath.has(logicalPath)) {
      throw new SelectionError();
    }
    byLogicalPath.set(logicalPath, file);
  }

  if (
    byLogicalPath.size !== COMPLETE_ARTIFACT_PATHS.length ||
    COMPLETE_ARTIFACT_PATHS.some((path) => !byLogicalPath.has(path))
  ) {
    throw new SelectionError();
  }

  return Object.freeze(
    COMPLETE_ARTIFACT_PATHS.map((path) =>
      Object.freeze({ path, blob: byLogicalPath.get(path) as Blob }),
    ),
  );
}
