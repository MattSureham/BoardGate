import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { buildViewer } from "./build.mjs";

const viewerDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outputPath = resolve(viewerDirectory, "boardgate-viewer.html");

const first = await buildViewer();
const second = await buildViewer();
if (first !== second) {
  throw new Error("two consecutive viewer builds did not produce identical bytes");
}

const tracked = await readFile(outputPath, "utf8");
if (tracked !== first) {
  throw new Error("boardgate-viewer.html is stale; run npm run build");
}

function requireSingleMatch(contents, expression, label) {
  const matches = [...contents.matchAll(expression)];
  if (matches.length !== 1 || matches[0]?.[1] === undefined) {
    throw new Error(`standalone HTML must contain exactly one ${label}`);
  }
  return matches[0][1];
}

if ((first.match(/<!doctype html>/giu) ?? []).length !== 1) {
  throw new Error("standalone HTML must contain exactly one document");
}
const inlineScript = requireSingleMatch(first, /<script>([\s\S]*?)<\/script>/giu, "inline script");
const inlineStyle = requireSingleMatch(first, /<style>([\s\S]*?)<\/style>/giu, "inline style");
const scriptHash = createHash("sha256").update(inlineScript, "utf8").digest("base64");
const styleHash = createHash("sha256").update(inlineStyle, "utf8").digest("base64");
if (
  !first.includes(`script-src 'sha256-${scriptHash}'`) ||
  !first.includes(`style-src 'sha256-${styleHash}'`)
) {
  throw new Error("standalone HTML CSP hashes do not match its inline assets");
}
