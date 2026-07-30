import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import Ajv2020 from "ajv/dist/2020.js";
import standaloneCode from "ajv/dist/standalone/index.js";

const viewerDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryDirectory = resolve(viewerDirectory, "..");
const schemaDirectory = resolve(repositoryDirectory, "schemas", "v1");
const generatedDirectory = resolve(viewerDirectory, "src", "generated");
const generatedJavaScript = resolve(generatedDirectory, "schema-validators.js");
const generatedDeclaration = resolve(generatedDirectory, "schema-validators.d.ts");

const schemas = {
  manifest: "manifest.schema.json",
  project: "project.schema.json",
  findings: "findings.schema.json",
  finding: "finding.schema.json",
  ruleProfile: "rule-profile.schema.json",
  runLogEvent: "run-log-event.schema.json",
};

function requireDeclaredProperties(value) {
  if (Array.isArray(value)) {
    for (const item of value) {
      requireDeclaredProperties(item);
    }
    return;
  }

  if (value === null || typeof value !== "object") {
    return;
  }

  // Pydantic emits OpenAPI discriminator annotations alongside oneOf. Draft
  // 2020-12 validation is fully expressed by oneOf, while Ajv's optional
  // discriminator extension rejects Pydantic's explicit mapping object.
  delete value.discriminator;

  if (
    value.type === "object" &&
    value.properties !== null &&
    typeof value.properties === "object" &&
    !Array.isArray(value.properties)
  ) {
    value.required = Object.keys(value.properties);
  }

  for (const nested of Object.values(value)) {
    requireDeclaredProperties(nested);
  }
}

async function loadAdmissionSchema(fileName, schemaId) {
  const source = await readFile(resolve(schemaDirectory, fileName), "utf8");
  const schema = JSON.parse(source);
  requireDeclaredProperties(schema);
  schema.$id = schemaId;
  return schema;
}

async function writeIfChanged(path, contents) {
  let current = null;
  try {
    current = await readFile(path, "utf8");
  } catch (error) {
    if (error === null || typeof error !== "object" || error.code !== "ENOENT") {
      throw error;
    }
  }
  if (current !== contents) {
    await writeFile(path, contents, "utf8");
  }
}

const ajv = new Ajv2020({
  allErrors: true,
  coerceTypes: false,
  code: {
    esm: true,
    lines: true,
    optimize: 1,
    source: true,
  },
  messages: false,
  removeAdditional: false,
  strict: true,
  useDefaults: false,
  validateFormats: false,
});

for (const [exportName, fileName] of Object.entries(schemas)) {
  const schemaId = `https://boardgate.dev/schemas/viewer-admission/1.0/${exportName}`;
  ajv.addSchema(await loadAdmissionSchema(fileName, schemaId), schemaId);
}

const validatorExports = Object.fromEntries(
  Object.keys(schemas).map((exportName) => [
    exportName,
    `https://boardgate.dev/schemas/viewer-admission/1.0/${exportName}`,
  ]),
);

const generated =
  "/* Generated from ../../schemas/v1 by scripts/generate-schema-validators.mjs. */\n" +
  "/* Do not edit. The public schemas remain the source of truth. */\n" +
  standaloneCode(ajv, validatorExports);

const declaration = `import type { ErrorObject } from "ajv";

export type StandaloneValidator = ((data: unknown) => boolean) & {
  errors?: ErrorObject[] | null;
};

export const manifest: StandaloneValidator;
export const project: StandaloneValidator;
export const findings: StandaloneValidator;
export const finding: StandaloneValidator;
export const ruleProfile: StandaloneValidator;
export const runLogEvent: StandaloneValidator;
`;

await mkdir(generatedDirectory, { recursive: true });
await writeIfChanged(generatedJavaScript, generated);
await writeIfChanged(generatedDeclaration, declaration);
