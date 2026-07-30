import { describe, expect, it } from "vitest";

import { COMPLETE_ARTIFACT_PATHS } from "../../src/contracts";
import { normalizeSelectedFiles, SelectionError } from "../../src/selection";

function selectedFile(path: string, contents = path): File {
  const file = new File([contents], path.split("/").at(-1) ?? "artifact");
  Object.defineProperty(file, "webkitRelativePath", {
    configurable: false,
    enumerable: true,
    value: path,
  });
  return file;
}

function completeSelection(root = "review"): File[] {
  return COMPLETE_ARTIFACT_PATHS.map((path) => selectedFile(`${root}/${path}`));
}

describe("directory selection normalization", () => {
  it("strips exactly one common root and returns normative artifact order", () => {
    const selected = completeSelection().reverse();
    const normalized = normalizeSelectedFiles(selected);

    expect(normalized.map((entry) => entry.path)).toEqual(COMPLETE_ARTIFACT_PATHS);
    expect(normalized.map((entry) => entry.blob)).toEqual(
      COMPLETE_ARTIFACT_PATHS.map(
        (path) => selected.find((file) => file.webkitRelativePath === `review/${path}`) as File,
      ),
    );
    expect(Object.isFrozen(normalized)).toBe(true);
    expect(normalized.every(Object.isFrozen)).toBe(true);
  });

  it.each([
    ["empty selection", []],
    ["missing artifact", completeSelection().slice(1)],
    ["extra artifact", [...completeSelection(), selectedFile("review/.DS_Store")]],
    [
      "wrong case",
      completeSelection().map((file) =>
        file.webkitRelativePath.endsWith("/manifest.json")
          ? selectedFile("review/Manifest.json")
          : file,
      ),
    ],
    [
      "multiple roots",
      completeSelection().map((file, index) =>
        index === 0 ? selectedFile(file.webkitRelativePath.replace("review/", "other/")) : file,
      ),
    ],
    ["rootless path", [selectedFile("manifest.json"), ...completeSelection().slice(1)]],
    [
      "backslash",
      completeSelection().map((file, index) =>
        index === 0 ? selectedFile("review\\manifest.json") : file,
      ),
    ],
    [
      "absolute path",
      completeSelection().map((file, index) =>
        index === 0 ? selectedFile("/review/manifest.json") : file,
      ),
    ],
    [
      "empty segment",
      completeSelection().map((file, index) =>
        index === 0 ? selectedFile("review//manifest.json") : file,
      ),
    ],
    [
      "dot segment",
      completeSelection().map((file, index) =>
        index === 0 ? selectedFile("review/./manifest.json") : file,
      ),
    ],
    [
      "parent segment",
      completeSelection().map((file, index) =>
        index === 0 ? selectedFile("review/../manifest.json") : file,
      ),
    ],
    [
      "NUL segment",
      completeSelection().map((file, index) =>
        index === 0 ? selectedFile("review/\0manifest.json") : file,
      ),
    ],
    [
      "duplicate raw path",
      [...completeSelection(), selectedFile("review/manifest.json", "duplicate")],
    ],
  ])("rejects %s without producing a partial inventory", (_label, files) => {
    expect(() => normalizeSelectedFiles(files)).toThrow(SelectionError);
    try {
      normalizeSelectedFiles(files);
    } catch (error) {
      expect(error).toMatchObject({
        viewerError: {
          code: "ARTIFACT_INVENTORY_MISMATCH",
        },
      });
    }
  });
});
