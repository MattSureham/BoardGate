import { SaxesParser } from "saxes";

import type { ViewerResourcePolicy } from "../policy";
import { AdmissionError, reject } from "./errors";
import type { CrossArtifactEvidence } from "./semantics";

const URL_SCHEME = /(?:https?|ftp|file|javascript|data):/i;
const CSS_URL = /url\(\s*([^)]+?)\s*\)/gi;
const ACTIVE_ELEMENTS = new Set(["embed", "foreignobject", "iframe", "object"]);

function localName(value: string): string {
  const withoutNamespace = value.split("}").at(-1) ?? value;
  return (withoutNamespace.split(":").at(-1) ?? withoutNamespace).toLowerCase();
}

function containsExternalReference(value: string): boolean {
  const stripped = value.trim().replace(/^["']|["']$/g, "");
  if (stripped.startsWith("//") || URL_SCHEME.test(stripped)) {
    return true;
  }
  CSS_URL.lastIndex = 0;
  for (const match of value.matchAll(CSS_URL)) {
    const reference = (match[1] ?? "").trim().replace(/^["']|["']$/g, "");
    if (!reference.startsWith("#")) {
      return true;
    }
  }
  return false;
}

export interface SvgAdmission {
  readonly findingIds: ReadonlySet<string>;
}

export function validateSvg(
  svg: string,
  evidence: CrossArtifactEvidence,
  policy: ViewerResourcePolicy,
): SvgAdmission {
  const lowered = svg.toLowerCase();
  const withoutDeclaration = svg.replace(/^\s*<\?xml[^?]*\?>/i, "");
  if (
    lowered.includes("<!doctype") ||
    lowered.includes("<!entity") ||
    withoutDeclaration.includes("<?")
  ) {
    reject("SVG_ACTIVE_XML_REJECTED");
  }

  let elementCount = 0;
  let attributeCount = 0;
  let rootSeen = false;
  let styleDepth = 0;
  const findingIds = new Set<string>();
  const parser = new SaxesParser({ xmlns: false });
  parser.on("opentag", (tag) => {
    elementCount += 1;
    if (elementCount > policy.maxSvgElements) {
      reject("ARTIFACT_RESOURCE_LIMIT");
    }
    const tagName = localName(tag.name);
    if (!rootSeen) {
      rootSeen = true;
      if (tagName !== "svg") {
        reject("SVG_ROOT_INVALID");
      }
    }
    if (tagName === "script") {
      reject("SVG_SCRIPT_REJECTED");
    }
    if (ACTIVE_ELEMENTS.has(tagName)) {
      reject("SVG_ACTIVE_ELEMENT_REJECTED");
    }
    if (tagName === "style") {
      styleDepth += 1;
    }
    for (const [rawName, rawValue] of Object.entries(tag.attributes)) {
      attributeCount += 1;
      if (attributeCount > policy.maxSvgAttributes) {
        reject("ARTIFACT_RESOURCE_LIMIT");
      }
      const name = localName(rawName);
      const value = rawValue;
      if (name === "xmlns" || rawName.toLowerCase().startsWith("xmlns:")) {
        continue;
      }
      if (name.startsWith("on")) {
        reject("SVG_EVENT_HANDLER_REJECTED");
      }
      if (
        containsExternalReference(value) ||
        ((name === "href" || name === "src") && !value.trim().startsWith("#"))
      ) {
        reject("SVG_EXTERNAL_REFERENCE_REJECTED");
      }
      if (name === "data-finding-id") {
        findingIds.add(value);
      }
      if (
        elementCount === 1 &&
        ((name === "data-project-id" && value !== evidence.projectId) ||
          (name === "data-profile-sha256" && value !== evidence.profileSha256))
      ) {
        reject("SVG_REVIEW_ID_MISMATCH");
      }
    }
    if (
      elementCount === 1 &&
      (tag.attributes["data-project-id"] === undefined ||
        tag.attributes["data-profile-sha256"] === undefined)
    ) {
      reject("SVG_REVIEW_ID_MISMATCH");
    }
  });
  parser.on("closetag", (tag) => {
    if (localName(tag.name) === "style") {
      styleDepth -= 1;
    }
  });
  parser.on("text", (text) => {
    if (
      styleDepth > 0 &&
      (text.toLowerCase().includes("@import") || containsExternalReference(text))
    ) {
      reject("SVG_EXTERNAL_REFERENCE_REJECTED");
    }
  });

  try {
    parser.write(svg).close();
  } catch (error) {
    if (error instanceof AdmissionError) {
      throw error;
    }
    reject("SVG_XML_INVALID");
  }
  if (!rootSeen) {
    reject("SVG_XML_INVALID");
  }
  if (
    findingIds.size !== evidence.findingIds.size ||
    [...findingIds].some((findingId) => !evidence.findingIds.has(findingId))
  ) {
    reject("SVG_FINDING_ID_MISMATCH");
  }
  return { findingIds };
}
