import { SaxesParser, type SaxesTagNS } from "saxes";

import type { ViewerResourcePolicy } from "../policy";
import { AdmissionError, reject } from "./errors";
import type { CrossArtifactEvidence } from "./semantics";

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const XMLNS_NAMESPACE = "http://www.w3.org/2000/xmlns/";
const URL_SCHEME = /(?:https?|ftp|file|javascript|data):/i;
const CSS_URL = /url\(\s*([^)]+?)\s*\)/gi;
const LOCAL_PAINT_REFERENCE = /^url\(#([A-Za-z_][A-Za-z0-9_.-]*)\)$/u;
const ACTIVE_ELEMENTS = new Set([
  "animate",
  "animatecolor",
  "animatemotion",
  "animatetransform",
  "discard",
  "embed",
  "foreignobject",
  "iframe",
  "mpath",
  "object",
  "set",
]);

const ELEMENT_ATTRIBUTES: ReadonlyMap<string, ReadonlySet<string>> = new Map([
  [
    "svg",
    new Set([
      "aria-labelledby",
      "data-profile-sha256",
      "data-project-id",
      "role",
      "version",
      "viewBox",
    ]),
  ],
  ["title", new Set(["id"])],
  ["desc", new Set(["id"])],
  [
    "g",
    new Set([
      "color",
      "data-coordinate-system",
      "data-finding-id",
      "data-finding-severity",
      "data-layer-id",
      "data-layer-role",
      "data-layer-side",
      "fill",
      "id",
      "transform",
    ]),
  ],
  [
    "path",
    new Set([
      "d",
      "data-aperture-shape",
      "data-contour-id",
      "data-contour-kind",
      "data-kind",
      "data-plating",
      "data-polarity",
      "data-primitive-id",
      "data-slot-id",
      "data-slot-kind",
      "fill",
      "fill-rule",
      "opacity",
      "stroke",
      "stroke-dasharray",
      "stroke-linecap",
      "stroke-width",
    ]),
  ],
  [
    "line",
    new Set([
      "data-aperture-shape",
      "data-kind",
      "data-polarity",
      "data-primitive-id",
      "fill",
      "opacity",
      "stroke",
      "stroke-dasharray",
      "stroke-linecap",
      "stroke-width",
      "x1",
      "x2",
      "y1",
      "y2",
    ]),
  ],
  [
    "rect",
    new Set([
      "data-aperture-shape",
      "data-kind",
      "data-polarity",
      "data-primitive-id",
      "fill",
      "height",
      "id",
      "opacity",
      "rx",
      "transform",
      "width",
      "x",
      "y",
    ]),
  ],
  [
    "circle",
    new Set([
      "cx",
      "cy",
      "data-aperture-shape",
      "data-drill-id",
      "data-kind",
      "data-plating",
      "data-polarity",
      "data-primitive-id",
      "fill",
      "opacity",
      "r",
      "stroke",
      "stroke-width",
    ]),
  ],
  [
    "ellipse",
    new Set([
      "cx",
      "cy",
      "data-aperture-shape",
      "data-kind",
      "data-polarity",
      "data-primitive-id",
      "fill",
      "opacity",
      "rx",
      "ry",
      "stroke",
      "stroke-dasharray",
      "stroke-width",
      "transform",
    ]),
  ],
  [
    "polygon",
    new Set([
      "data-aperture-shape",
      "data-kind",
      "data-polarity",
      "data-primitive-id",
      "fill",
      "opacity",
      "points",
    ]),
  ],
  ["text", new Set(["fill", "font-family", "font-size", "font-weight", "x", "y"])],
  ["defs", new Set()],
  [
    "linearGradient",
    new Set(["gradientTransform", "gradientUnits", "id", "spreadMethod", "x1", "x2", "y1", "y2"]),
  ],
  [
    "radialGradient",
    new Set([
      "cx",
      "cy",
      "fr",
      "fx",
      "fy",
      "gradientTransform",
      "gradientUnits",
      "id",
      "r",
      "spreadMethod",
    ]),
  ],
  ["stop", new Set(["offset", "stop-color", "stop-opacity"])],
]);

const GRADIENT_ELEMENTS = new Set(["linearGradient", "radialGradient"]);

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

function attributeValue(tag: SaxesTagNS, name: string): string | undefined {
  const attribute = tag.attributes[name];
  return attribute?.value;
}

function isNamespaceDeclaration(attribute: SaxesTagNS["attributes"][string]): boolean {
  return attribute.uri === XMLNS_NAMESPACE;
}

function scanSvgHazards(svg: string, policy: ViewerResourcePolicy): void {
  let elementCount = 0;
  let attributeCount = 0;
  const styleText: string[] = [];
  const styleAttributes: Array<Array<SaxesTagNS["attributes"][string]>> = [];
  const scanAttributes = (attributes: Array<SaxesTagNS["attributes"][string]>): void => {
    for (const attribute of attributes) {
      if (isNamespaceDeclaration(attribute)) {
        continue;
      }
      const name = attribute.local;
      const value = attribute.value;
      if (name.toLowerCase().startsWith("on")) {
        reject("SVG_EVENT_HANDLER_REJECTED");
      }
      if (
        containsExternalReference(value) ||
        ((name === "href" || name === "src") && !value.trim().startsWith("#"))
      ) {
        reject("SVG_EXTERNAL_REFERENCE_REJECTED");
      }
      if (name === "style") {
        reject("SVG_ACTIVE_ELEMENT_REJECTED");
      }
    }
  };
  const parser = new SaxesParser({ xmlns: true });
  parser.on("opentag", (tag) => {
    elementCount += 1;
    if (elementCount > policy.maxSvgElements) {
      reject("ARTIFACT_RESOURCE_LIMIT");
    }
    const tagName = tag.local.toLowerCase();
    if (tagName === "script") {
      reject("SVG_SCRIPT_REJECTED");
    }
    if (ACTIVE_ELEMENTS.has(tagName)) {
      reject("SVG_ACTIVE_ELEMENT_REJECTED");
    }
    const attributes = Object.values(tag.attributes);
    attributeCount += attributes.length;
    if (attributeCount > policy.maxSvgAttributes) {
      reject("ARTIFACT_RESOURCE_LIMIT");
    }
    if (tagName === "style") {
      styleText.push("");
      styleAttributes.push(attributes);
      return;
    }
    scanAttributes(attributes);
  });
  const appendStyleText = (text: string): void => {
    if (styleText.length > 0) {
      styleText[styleText.length - 1] += text;
    }
  };
  parser.on("text", appendStyleText);
  parser.on("cdata", appendStyleText);
  parser.on("closetag", (tag) => {
    if (tag.local.toLowerCase() !== "style") {
      return;
    }
    const text = styleText.pop() ?? "";
    if (text.toLowerCase().includes("@import") || containsExternalReference(text)) {
      reject("SVG_EXTERNAL_REFERENCE_REJECTED");
    }
    scanAttributes(styleAttributes.pop() ?? []);
    reject("SVG_ACTIVE_ELEMENT_REJECTED");
  });
  try {
    parser.write(svg).close();
  } catch (error) {
    if (error instanceof AdmissionError) {
      throw error;
    }
    reject("SVG_XML_INVALID");
  }
}

export interface SvgLayerGroup {
  readonly groupId: string;
  readonly layerId: string;
  readonly role: string;
  readonly side: string;
}

export interface SvgAdmission {
  readonly findingIds: ReadonlySet<string>;
  readonly layerGroups: readonly SvgLayerGroup[];
  readonly spatialFindingIds: ReadonlySet<string>;
  readonly nonSpatialFindingIds: ReadonlySet<string>;
}

const LAYER_GROUP_ID = /^pcb-layer-\d{4}$/u;

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

  scanSvgHazards(svg, policy);

  let elementCount = 0;
  let rootSeen = false;
  const findingIds = new Set<string>();
  let findingMarkerCount = 0;
  const spatialFindingIds = new Set<string>();
  const nonSpatialFindingIds = new Set<string>();
  const layerGroups: SvgLayerGroup[] = [];
  const layerGroupIds = new Set<string>();
  const groupStack: string[] = [];
  const idCounts = new Map<string, number>();
  const gradientIds = new Set<string>();
  const paintReferences: string[] = [];
  const parser = new SaxesParser({ xmlns: true });
  parser.on("opentag", (tag) => {
    elementCount += 1;
    if (elementCount > policy.maxSvgElements) {
      reject("ARTIFACT_RESOURCE_LIMIT");
    }
    if (!rootSeen) {
      rootSeen = true;
      if (tag.local !== "svg") {
        reject("SVG_ROOT_INVALID");
      }
      if (tag.uri !== SVG_NAMESPACE) {
        reject("SVG_NAMESPACE_INVALID");
      }
    } else if (tag.uri !== SVG_NAMESPACE) {
      reject("SVG_NAMESPACE_INVALID");
    }

    const tagName = tag.local;
    const allowedAttributes = ELEMENT_ATTRIBUTES.get(tagName);
    const attributes = Object.values(tag.attributes);
    for (const attribute of attributes) {
      if (isNamespaceDeclaration(attribute)) {
        continue;
      }
      if (attribute.uri !== "" || attribute.prefix !== "") {
        reject("SVG_NAMESPACE_INVALID");
      }
      const name = attribute.local;
      const value = attribute.value;
      if (allowedAttributes === undefined || !allowedAttributes.has(name)) {
        reject("SVG_VOCABULARY_REJECTED");
      }
      if (/url\s*\(/iu.test(value)) {
        if (name !== "fill" && name !== "stroke") {
          reject("SVG_VOCABULARY_REJECTED");
        }
        const match = LOCAL_PAINT_REFERENCE.exec(value);
        if (match?.[1] === undefined) {
          reject("SVG_VOCABULARY_REJECTED");
        }
        paintReferences.push(match[1]);
      }
    }

    if (allowedAttributes === undefined) {
      reject("SVG_VOCABULARY_REJECTED");
    }

    const elementId = attributeValue(tag, "id");
    groupStack.push(elementId ?? "");
    if (elementId !== undefined) {
      idCounts.set(elementId, (idCounts.get(elementId) ?? 0) + 1);
      if (GRADIENT_ELEMENTS.has(tagName)) {
        gradientIds.add(elementId);
      }
    }
    if (
      elementCount === 1 &&
      (attributeValue(tag, "data-project-id") !== evidence.projectId ||
        attributeValue(tag, "data-profile-sha256") !== evidence.profileSha256)
    ) {
      reject("SVG_REVIEW_ID_MISMATCH");
    }
    if (typeof elementId === "string" && LAYER_GROUP_ID.test(elementId)) {
      if (tagName !== "g") {
        reject("SVG_LAYER_GROUP_INVALID");
      }
      const layerId = attributeValue(tag, "data-layer-id");
      const role = attributeValue(tag, "data-layer-role");
      const side = attributeValue(tag, "data-layer-side");
      if (
        layerId === undefined ||
        layerId.length === 0 ||
        role === undefined ||
        role.length === 0 ||
        side === undefined ||
        side.length === 0 ||
        layerGroupIds.has(elementId) ||
        layerGroups.some((group) => group.layerId === layerId)
      ) {
        reject("SVG_LAYER_GROUP_INVALID");
      }
      layerGroupIds.add(elementId);
      layerGroups.push({ groupId: elementId, layerId, role, side });
    }
    const findingId = attributeValue(tag, "data-finding-id");
    if (findingId !== undefined) {
      if (tagName !== "g" || findingId.length === 0) {
        reject("SVG_FINDING_ID_MISMATCH");
      }
      findingMarkerCount += 1;
      findingIds.add(findingId);
      if (groupStack.includes("spatial-findings")) {
        spatialFindingIds.add(findingId);
      } else if (groupStack.includes("non-spatial-findings")) {
        nonSpatialFindingIds.add(findingId);
      } else {
        reject("SVG_FINDING_ID_MISMATCH");
      }
    }
  });
  parser.on("closetag", (tag) => {
    void tag;
    groupStack.pop();
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
    paintReferences.some(
      (gradientId) => !gradientIds.has(gradientId) || idCounts.get(gradientId) !== 1,
    )
  ) {
    reject("SVG_VOCABULARY_REJECTED");
  }
  if (
    findingMarkerCount !== findingIds.size ||
    findingIds.size !== evidence.findingIds.size ||
    [...findingIds].some((findingId) => !evidence.findingIds.has(findingId))
  ) {
    reject("SVG_FINDING_ID_MISMATCH");
  }
  return { findingIds, layerGroups, spatialFindingIds, nonSpatialFindingIds };
}
