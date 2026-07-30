import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { build as viteBuild } from "vite";

const viewerDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const defaultOutput = resolve(viewerDirectory, "boardgate-viewer.html");

function sha256CspSource(contents) {
  return `'sha256-${createHash("sha256").update(contents, "utf8").digest("base64")}'`;
}

function singleChunk(buildResult, label) {
  const results = Array.isArray(buildResult) ? buildResult : [buildResult];
  const chunks = results.flatMap((result) =>
    result.output.filter((output) => output.type === "chunk"),
  );
  if (chunks.length !== 1) {
    throw new Error(`${label} build produced ${chunks.length} chunks; expected exactly one`);
  }
  const [chunk] = chunks;
  if (chunk === undefined) {
    throw new Error(`${label} build did not produce a JavaScript chunk`);
  }
  return chunk.code.trimEnd();
}

function emittedCss(buildResult) {
  const results = Array.isArray(buildResult) ? buildResult : [buildResult];
  return results
    .flatMap((result) => result.output)
    .filter((output) => output.type === "asset" && output.fileName.endsWith(".css"))
    .sort((left, right) => left.fileName.localeCompare(right.fileName, "en"))
    .map((output) => String(output.source).trimEnd())
    .join("\n");
}

async function bundleEntry(entry, format, define = {}) {
  return viteBuild({
    appType: "custom",
    configFile: false,
    define,
    logLevel: "silent",
    root: viewerDirectory,
    build: {
      assetsInlineLimit: Number.MAX_SAFE_INTEGER,
      cssCodeSplit: false,
      emptyOutDir: false,
      modulePreload: false,
      reportCompressedSize: false,
      rollupOptions: {
        input: resolve(viewerDirectory, entry),
        output: {
          assetFileNames: "assets/[name][extname]",
          entryFileNames: "[name].js",
          format,
        },
      },
      sourcemap: false,
      target: "es2023",
      write: false,
    },
  });
}

function replaceOnce(template, marker, replacement) {
  const first = template.indexOf(marker);
  if (first === -1 || template.indexOf(marker, first + marker.length) !== -1) {
    throw new Error(`template must contain exactly one ${marker} marker`);
  }
  // A function replacement is required because bundled dependency code can
  // legitimately contain `$&`, `$`` or `$'`; string replacement would
  // reinterpret those sequences and splice template fragments into the HTML.
  return template.replace(marker, () => replacement);
}

function inlineSafeScript(script) {
  // HTML parsers terminate a classic script element at this byte sequence even
  // when it occurs inside a JavaScript string literal.
  return script.replace(/<\/script/giu, "<\\/script");
}

export async function buildViewer() {
  const packageMetadata = JSON.parse(
    await readFile(resolve(viewerDirectory, "package.json"), "utf8"),
  );
  const workerResult = await bundleEntry("src/worker.ts", "iife");
  const workerSource = singleChunk(workerResult, "worker");

  const mainResult = await bundleEntry("src/main.ts", "iife", {
    __BOARDGATE_VIEWER_VERSION__: JSON.stringify(packageMetadata.version),
    __BOARDGATE_WORKER_SOURCE__: JSON.stringify(workerSource),
  });
  const script = inlineSafeScript(singleChunk(mainResult, "main"));
  const style = emittedCss(mainResult);

  const csp = [
    "default-src 'none'",
    `script-src ${sha256CspSource(script)}`,
    `style-src ${sha256CspSource(style)}`,
    "worker-src blob:",
    "child-src blob:",
    "connect-src 'none'",
    "img-src 'none'",
    "font-src 'none'",
    "media-src 'none'",
    "object-src 'none'",
    "frame-src 'none'",
    "form-action 'none'",
    "base-uri 'none'",
  ].join("; ");

  let html = await readFile(resolve(viewerDirectory, "template.html"), "utf8");
  html = replaceOnce(html, "{{BOARDGATE_CSP}}", csp);
  html = replaceOnce(html, "{{BOARDGATE_STYLE}}", style);
  html = replaceOnce(html, "{{BOARDGATE_SCRIPT}}", script);
  return `${html.trimEnd()}\n`;
}

async function main() {
  const outputArgument = process.argv.find((argument) => argument.startsWith("--output="));
  const outputPath =
    outputArgument === undefined
      ? defaultOutput
      : resolve(process.cwd(), outputArgument.slice("--output=".length));
  await writeFile(outputPath, await buildViewer(), "utf8");
}

if (process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main();
}
