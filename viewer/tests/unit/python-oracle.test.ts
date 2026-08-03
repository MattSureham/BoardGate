import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import type { ValidationResult } from "../../src/contracts";
import { VIEWER_RESOURCE_POLICY } from "../../src/policy";
import { admitBundle } from "../../src/validation";
import { type GeneratedBundle, generateValidBundle, replaceText } from "./fixture";

interface MutationCase {
  readonly label: string;
  readonly files: ReadonlyMap<string, Blob>;
}

interface OracleResult {
  readonly label: string;
  readonly ok: boolean;
  readonly code: string | null;
}

const viewerDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const repositoryDirectory = resolve(viewerDirectory, "..");
const oracleScript = resolve(viewerDirectory, "scripts/python-oracle.py");

let fixture: GeneratedBundle;
let temporaryDirectory: string;

beforeAll(() => {
  fixture = generateValidBundle();
  temporaryDirectory = mkdtempSync(join(tmpdir(), "boardgate-viewer-oracle-"));
});

afterAll(() => {
  fixture.cleanup();
  rmSync(temporaryDirectory, { recursive: true, force: true });
});

async function writeCase(testCase: MutationCase): Promise<string> {
  const directory = join(temporaryDirectory, testCase.label);
  mkdirSync(directory, { recursive: true });
  for (const [path, blob] of testCase.files) {
    const output = join(directory, path);
    mkdirSync(dirname(output), { recursive: true });
    writeFileSync(output, Buffer.from(await blob.arrayBuffer()));
  }
  return directory;
}

function resultCode(result: ValidationResult): string | null {
  return result.ok ? null : result.error.code;
}

describe("Python artifact-admission parity", () => {
  it("matches validate_artifact_bundle across one shared mutation corpus", async () => {
    const cases: MutationCase[] = [
      { label: "valid", files: fixture.files },
      {
        label: "missing-preview",
        files: new Map([...fixture.files].filter(([path]) => path !== "preview.svg")),
      },
      {
        label: "extra-artifact",
        files: new Map([...fixture.files, ["unexpected.txt", new Blob(["unexpected"])]]),
      },
      {
        label: "invalid-utf8",
        files: new Map([
          ...fixture.files,
          ["manifest.json", new Blob([new Uint8Array([0xc3, 0x28])])],
        ]),
      },
      {
        label: "duplicate-json-key",
        files: await replaceText(fixture.files, "manifest.json", (payload) =>
          payload.replace(
            '  "project_id":',
            '  "project_id": "prj-0000000000000000",\n  "project_id":',
          ),
        ),
      },
      {
        label: "noncanonical-number",
        files: await replaceText(fixture.files, "project.json", (payload) =>
          payload.replace('"rotation_degrees": 0.0', '"rotation_degrees": 0.00'),
        ),
      },
      {
        label: "project-id-mismatch",
        files: await replaceText(fixture.files, "findings.json", (payload) =>
          payload.replace(
            /"project_id": "prj-[0-9a-f]{16}"/u,
            '"project_id": "prj-0000000000000000"',
          ),
        ),
      },
      {
        label: "profile-mismatch",
        files: await replaceText(fixture.files, "findings.json", (payload) =>
          payload.replace(/"profile_id": "[^"]+"/u, '"profile_id": "wrong-profile"'),
        ),
      },
      {
        label: "risk-mismatch",
        files: await replaceText(fixture.files, "findings.json", (payload) =>
          payload.replace('  "risk_modes": [],', '  "risk_modes": [\n    "FILE_INCOMPLETE"\n  ],'),
        ),
      },
      {
        label: "report-id-mismatch",
        files: await replaceText(fixture.files, "report.md", (payload) =>
          payload.replace(/prj-[0-9a-f]{16}/u, "prj-0000000000000000"),
        ),
      },
      {
        label: "active-svg",
        files: await replaceText(fixture.files, "preview.svg", (payload) =>
          payload.replace("</svg>", '<script src="https://invalid.example/x"/></svg>'),
        ),
      },
      {
        label: "svg-wrong-root-namespace",
        files: await replaceText(fixture.files, "preview.svg", (payload) =>
          payload.replace('xmlns="http://www.w3.org/2000/svg"', 'xmlns="urn:not-svg"'),
        ),
      },
      {
        label: "svg-foreign-descendant",
        files: await replaceText(fixture.files, "preview.svg", (payload) =>
          payload.replace("</svg>", '<g xmlns="urn:not-svg"/></svg>'),
        ),
      },
      {
        label: "svg-animation",
        files: await replaceText(fixture.files, "preview.svg", (payload) =>
          payload.replace("</svg>", '<animate attributeName="viewBox" dur="1s"/></svg>'),
        ),
      },
      {
        label: "svg-style-element",
        files: await replaceText(fixture.files, "preview.svg", (payload) =>
          payload.replace("</svg>", "<style>@keyframes pulse {}</style></svg>"),
        ),
      },
      {
        label: "svg-style-attribute",
        files: await replaceText(fixture.files, "preview.svg", (payload) =>
          payload.replace("<svg ", '<svg style="animation: pulse 1s" '),
        ),
      },
      {
        label: "svg-unknown-element",
        files: await replaceText(fixture.files, "preview.svg", (payload) =>
          payload.replace("</svg>", "<metadata/></svg>"),
        ),
      },
      {
        label: "svg-local-link",
        files: await replaceText(fixture.files, "preview.svg", (payload) =>
          payload.replace("</svg>", '<a href="#paint"/></svg>'),
        ),
      },
      {
        label: "svg-local-gradient",
        files: await replaceText(fixture.files, "preview.svg", (payload) =>
          payload
            .replace(
              "</desc>",
              '</desc><defs><linearGradient id="paint"><stop offset="0" stop-color="#fff"/>' +
                '<stop offset="1" stop-color="#000"/></linearGradient></defs>',
            )
            .replace('fill="#ffffff"', 'fill="url(#paint)"'),
        ),
      },
      {
        label: "svg-missing-gradient",
        files: await replaceText(fixture.files, "preview.svg", (payload) =>
          payload.replace('fill="#ffffff"', 'fill="url(#missing)"'),
        ),
      },
      {
        label: "run-sequence-mismatch",
        files: await replaceText(fixture.files, "logs/run.jsonl", (payload) => {
          const lines = payload.trimEnd().split("\n");
          lines[1] = (lines[1] as string).replace('"sequence":2', '"sequence":1');
          return `${lines.join("\n")}\n`;
        }),
      },
    ];

    const browserResults = new Map<string, string | null>();
    const oracleRequest: { label: string; directory: string }[] = [];
    for (const testCase of cases) {
      browserResults.set(
        testCase.label,
        resultCode(await admitBundle(testCase.files, VIEWER_RESOURCE_POLICY)),
      );
      oracleRequest.push({
        label: testCase.label,
        directory: await writeCase(testCase),
      });
    }

    const rawOracle = execFileSync("uv", ["run", "python", oracleScript], {
      cwd: repositoryDirectory,
      encoding: "utf8",
      input: JSON.stringify(oracleRequest),
    });
    const oracleResults = JSON.parse(rawOracle) as OracleResult[];

    expect(oracleResults).toHaveLength(cases.length);
    expect(oracleResults.find((result) => result.label === "valid")).toMatchObject({
      ok: true,
      code: null,
    });
    for (const result of oracleResults) {
      const browserCode = browserResults.get(result.label);
      expect(browserCode === null, result.label).toBe(result.ok);
      if (result.label === "active-svg" || result.label.startsWith("svg-")) {
        expect(browserCode, `${result.label} error code`).toBe(result.code);
      }
    }
  }, 60_000);
});
