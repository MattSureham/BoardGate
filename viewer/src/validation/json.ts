import type { ViewerResourcePolicy } from "../policy";
import { reject } from "./errors";

export type JsonPrimitive = null | boolean | number | string;
export type JsonValue =
  | JsonPrimitive
  | readonly JsonValue[]
  | { readonly [key: string]: JsonValue };

export interface ParsedJson {
  readonly value: JsonValue;
  readonly numberLexemes: ReadonlyMap<string, string>;
}

type JsonFormat = "pretty" | "compact";

const NUMBER = /-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-][0-9]{2,})?/y;
const FLOAT_PROPERTY_NAMES = new Set([
  "actual",
  "approximation_error_mm",
  "arc_chord_error",
  "confidence",
  "diameter_mm",
  "error_bound",
  "geometry_epsilon",
  "gross_alignment",
  "height_mm",
  "hole_diameter_mm",
  "mapping_confidence",
  "measurement_error_mm",
  "min_annular_ring",
  "min_annular_ring_mm",
  "min_copper_spacing",
  "min_copper_spacing_mm",
  "min_copper_to_edge",
  "min_copper_to_edge_mm",
  "min_drill_diameter",
  "min_drill_diameter_mm",
  "min_solder_mask_dam",
  "min_solder_mask_dam_mm",
  "min_trace_width",
  "min_trace_width_mm",
  "outline_closure",
  "required",
  "rotation_degrees",
  "width_mm",
  "x",
  "y",
]);
const INTEGER_PROPERTY_NAMES = new Set([
  "applicable_object_count",
  "drill_count",
  "elapsed_ms",
  "end_byte",
  "end_line",
  "evaluated_object_count",
  "finding_count",
  "input_file_count",
  "limit",
  "max_component_pair_candidates",
  "max_derived_coordinates_per_layer",
  "max_intersection_candidates_per_layer",
  "max_primitives_per_connected_subset",
  "max_primitives_per_layer",
  "max_primitives_per_review",
  "max_union_inputs_per_batch",
  "observed",
  "outer_contour_count",
  "primitive_count",
  "quantity",
  "sequence",
  "size_bytes",
  "start_byte",
  "start_line",
  "vertices",
]);

function pointerPart(value: string | number): string {
  return String(value).replaceAll("~", "~0").replaceAll("/", "~1");
}

function childPath(path: string, value: string | number): string {
  return `${path}/${pointerPart(value)}`;
}

function propertyName(path: string): string {
  const part = path.slice(path.lastIndexOf("/") + 1);
  return part.replaceAll("~1", "/").replaceAll("~0", "~");
}

function normalizedDigits(value: number): {
  readonly digits: string;
  readonly exponent: number;
} {
  const rendered = Math.abs(value).toString();
  const [mantissa = "", exponentText] = rendered.split("e");
  const explicitExponent = exponentText === undefined ? 0 : Number.parseInt(exponentText, 10);
  const decimalIndex = mantissa.indexOf(".");
  const decimalPosition = decimalIndex === -1 ? mantissa.length : decimalIndex;
  const allDigits = mantissa.replace(".", "");
  const leadingZeros = /^0*/.exec(allDigits)?.[0].length ?? 0;
  let digits = allDigits.slice(leadingZeros).replace(/0+$/, "");
  if (digits.length === 0) {
    digits = "0";
  }
  return {
    digits,
    exponent: explicitExponent + decimalPosition - leadingZeros - 1,
  };
}

/**
 * Spell a finite IEEE-754 value as CPython's shortest float ``repr`` does.
 *
 * Modern JavaScript and CPython use the same shortest-round-trip digits; their
 * observable differences are the fixed/scientific thresholds, exponent
 * padding, and the mandatory decimal suffix for integral fixed-form floats.
 */
export function pythonFloatRepr(value: number): string {
  if (!Number.isFinite(value)) {
    reject("ARTIFACT_JSON_INVALID");
  }
  if (Object.is(value, -0)) {
    return "-0.0";
  }
  if (value === 0) {
    return "0.0";
  }
  const sign = value < 0 ? "-" : "";
  const { digits, exponent } = normalizedDigits(value);
  if (exponent < -4 || exponent >= 16) {
    const mantissa = digits.length === 1 ? digits : `${digits[0]}.${digits.slice(1)}`;
    const exponentSign = exponent < 0 ? "-" : "+";
    const exponentDigits = Math.abs(exponent).toString().padStart(2, "0");
    return `${sign}${mantissa}e${exponentSign}${exponentDigits}`;
  }
  const decimalPosition = exponent + 1;
  let fixed: string;
  if (decimalPosition <= 0) {
    fixed = `0.${"0".repeat(-decimalPosition)}${digits}`;
  } else if (decimalPosition >= digits.length) {
    fixed = `${digits}${"0".repeat(decimalPosition - digits.length)}.0`;
  } else {
    fixed = `${digits.slice(0, decimalPosition)}.${digits.slice(decimalPosition)}`;
  }
  return `${sign}${fixed}`;
}

function requireCanonicalNumber(raw: string, value: number, path: string): void {
  const name = propertyName(path);
  const floatSyntax = raw.includes(".") || raw.includes("e");
  if (INTEGER_PROPERTY_NAMES.has(name)) {
    if (!Number.isSafeInteger(value) || String(value) !== raw) {
      reject("ARTIFACT_JSON_NONDETERMINISTIC");
    }
    return;
  }
  if (FLOAT_PROPERTY_NAMES.has(name) || floatSyntax) {
    if (pythonFloatRepr(value) !== raw) {
      reject("ARTIFACT_JSON_NONDETERMINISTIC");
    }
    if ((name === "x" || name === "y") && Number(value.toFixed(6)) !== value) {
      reject("ARTIFACT_JSON_NONDETERMINISTIC");
    }
    return;
  }
}

export function compareUnicodeCodePoints(left: string, right: string): number {
  const leftPoints = Array.from(left, (value) => value.codePointAt(0) ?? 0);
  const rightPoints = Array.from(right, (value) => value.codePointAt(0) ?? 0);
  const length = Math.min(leftPoints.length, rightPoints.length);
  for (let index = 0; index < length; index += 1) {
    const difference = (leftPoints[index] ?? 0) - (rightPoints[index] ?? 0);
    if (difference !== 0) {
      return difference;
    }
  }
  return leftPoints.length - rightPoints.length;
}

function hasUnpairedSurrogate(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const following = value.charCodeAt(index + 1);
      if (following < 0xdc00 || following > 0xdfff) {
        return true;
      }
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      return true;
    }
  }
  return false;
}

class BoundedJsonParser {
  readonly #text: string;
  readonly #policy: ViewerResourcePolicy;
  readonly #format: JsonFormat;
  readonly #numbers = new Map<string, string>();
  #index = 0;
  #entries = 0;

  constructor(text: string, policy: ViewerResourcePolicy, format: JsonFormat) {
    this.#text = text;
    this.#policy = policy;
    this.#format = format;
  }

  parse(): ParsedJson {
    if (this.#text.length === 0 || this.#text.startsWith("\ufeff")) {
      reject("ARTIFACT_JSON_INVALID");
    }
    const value = this.#parseValue(0, "");
    if (this.#index !== this.#text.length) {
      reject("ARTIFACT_JSON_INVALID");
    }
    return { value, numberLexemes: this.#numbers };
  }

  #countEntry(): void {
    this.#entries += 1;
    if (this.#entries > this.#policy.maxJsonEntries) {
      reject("ARTIFACT_RESOURCE_LIMIT");
    }
  }

  #requireDepth(depth: number): void {
    if (depth > this.#policy.maxJsonDepth) {
      reject("ARTIFACT_RESOURCE_LIMIT");
    }
  }

  #consume(expected: string): void {
    if (!this.#text.startsWith(expected, this.#index)) {
      reject("ARTIFACT_JSON_NONDETERMINISTIC");
    }
    this.#index += expected.length;
  }

  #parseValue(depth: number, path: string): JsonValue {
    this.#requireDepth(depth);
    const first = this.#text[this.#index];
    if (first === "{") {
      return this.#parseObject(depth, path);
    }
    if (first === "[") {
      return this.#parseArray(depth, path);
    }
    if (first === '"') {
      return this.#parseString();
    }
    if (this.#text.startsWith("true", this.#index)) {
      this.#index += 4;
      return true;
    }
    if (this.#text.startsWith("false", this.#index)) {
      this.#index += 5;
      return false;
    }
    if (this.#text.startsWith("null", this.#index)) {
      this.#index += 4;
      return null;
    }
    return this.#parseNumber(path);
  }

  #parseObject(depth: number, path: string): JsonValue {
    this.#countEntry();
    this.#consume("{");
    if (this.#text[this.#index] === "}") {
      this.#index += 1;
      return {};
    }
    if (this.#format === "pretty") {
      this.#consume("\n");
    }
    const object: Record<string, JsonValue> = {};
    const keys = new Set<string>();
    let previousKey: string | undefined;
    let first = true;
    while (true) {
      if (!first) {
        this.#consume(",");
        if (this.#format === "pretty") {
          this.#consume("\n");
        }
      }
      if (this.#format === "pretty") {
        this.#consume(" ".repeat((depth + 1) * 2));
      }
      if (this.#text[this.#index] !== '"') {
        reject("ARTIFACT_JSON_INVALID");
      }
      const key = this.#parseString();
      if (keys.has(key)) {
        reject("ARTIFACT_JSON_INVALID");
      }
      if (previousKey !== undefined && compareUnicodeCodePoints(previousKey, key) >= 0) {
        reject("ARTIFACT_JSON_NONDETERMINISTIC");
      }
      keys.add(key);
      previousKey = key;
      this.#consume(this.#format === "pretty" ? ": " : ":");
      this.#countEntry();
      object[key] = this.#parseValue(depth + 1, childPath(path, key));
      first = false;
      if (this.#text[this.#index] === "}") {
        if (this.#format === "pretty") {
          reject("ARTIFACT_JSON_NONDETERMINISTIC");
        }
        this.#index += 1;
        break;
      }
      if (
        this.#format === "pretty" &&
        this.#text.startsWith(`\n${" ".repeat(depth * 2)}}`, this.#index)
      ) {
        this.#index += depth * 2 + 2;
        break;
      }
    }
    return object;
  }

  #parseArray(depth: number, path: string): JsonValue {
    this.#countEntry();
    this.#consume("[");
    if (this.#text[this.#index] === "]") {
      this.#index += 1;
      return [];
    }
    if (this.#format === "pretty") {
      this.#consume("\n");
    }
    const array: JsonValue[] = [];
    let index = 0;
    while (true) {
      if (index > 0) {
        this.#consume(",");
        if (this.#format === "pretty") {
          this.#consume("\n");
        }
      }
      if (this.#format === "pretty") {
        this.#consume(" ".repeat((depth + 1) * 2));
      }
      this.#countEntry();
      array.push(this.#parseValue(depth + 1, childPath(path, index)));
      index += 1;
      if (this.#text[this.#index] === "]") {
        if (this.#format === "pretty") {
          reject("ARTIFACT_JSON_NONDETERMINISTIC");
        }
        this.#index += 1;
        break;
      }
      if (
        this.#format === "pretty" &&
        this.#text.startsWith(`\n${" ".repeat(depth * 2)}]`, this.#index)
      ) {
        this.#index += depth * 2 + 2;
        break;
      }
    }
    return array;
  }

  #parseString(): string {
    const start = this.#index;
    this.#index += 1;
    let escaped = false;
    while (this.#index < this.#text.length) {
      const character = this.#text[this.#index];
      if (escaped) {
        escaped = false;
      } else if (character === "\\") {
        escaped = true;
      } else if (character === '"') {
        this.#index += 1;
        const raw = this.#text.slice(start, this.#index);
        try {
          const parsed = JSON.parse(raw) as unknown;
          if (
            typeof parsed !== "string" ||
            JSON.stringify(parsed) !== raw ||
            hasUnpairedSurrogate(parsed)
          ) {
            reject("ARTIFACT_JSON_NONDETERMINISTIC");
          }
          return parsed;
        } catch {
          reject("ARTIFACT_JSON_INVALID");
        }
      } else if (character === undefined || character.charCodeAt(0) <= 0x1f) {
        reject("ARTIFACT_JSON_INVALID");
      }
      this.#index += 1;
    }
    reject("ARTIFACT_JSON_INVALID");
  }

  #parseNumber(path: string): number {
    NUMBER.lastIndex = this.#index;
    const match = NUMBER.exec(this.#text);
    if (match === null) {
      reject("ARTIFACT_JSON_INVALID");
    }
    const raw = match[0];
    const following = this.#text[NUMBER.lastIndex];
    if (
      following !== undefined &&
      following !== "," &&
      following !== "]" &&
      following !== "}" &&
      following !== "\n"
    ) {
      reject("ARTIFACT_JSON_INVALID");
    }
    if (raw === "-0" || raw.includes("E")) {
      reject("ARTIFACT_JSON_NONDETERMINISTIC");
    }
    const value = Number(raw);
    if (!Number.isFinite(value)) {
      reject("ARTIFACT_JSON_INVALID");
    }
    requireCanonicalNumber(raw, value, path);
    this.#index = NUMBER.lastIndex;
    this.#numbers.set(path, raw);
    return value;
  }
}

export function parseCanonicalJson(payload: string, policy: ViewerResourcePolicy): ParsedJson {
  if (!payload.endsWith("\n")) {
    reject("ARTIFACT_JSON_NONDETERMINISTIC");
  }
  return new BoundedJsonParser(payload.slice(0, -1), policy, "pretty").parse();
}

export function parseCompactJson(payload: string, policy: ViewerResourcePolicy): ParsedJson {
  return new BoundedJsonParser(payload, policy, "compact").parse();
}

export function isRecord(value: unknown): value is Record<string, JsonValue> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function canonicalCompact(
  value: JsonValue,
  numberLexemes: ReadonlyMap<string, string>,
  path = "",
): string {
  if (value === null || typeof value === "boolean") {
    return String(value);
  }
  if (typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    const lexeme = numberLexemes.get(path);
    if (lexeme === undefined) {
      reject("ARTIFACT_JSON_INVALID");
    }
    return lexeme;
  }
  if (Array.isArray(value)) {
    return `[${value
      .map((item, index) => canonicalCompact(item, numberLexemes, childPath(path, index)))
      .join(",")}]`;
  }
  const record = value as Record<string, JsonValue>;
  return `{${Object.keys(record)
    .sort(compareUnicodeCodePoints)
    .map(
      (key) =>
        `${JSON.stringify(key)}:${canonicalCompact(
          record[key] as JsonValue,
          numberLexemes,
          childPath(path, key),
        )}`,
    )
    .join(",")}}`;
}

export async function sha256Prefix(value: string, prefix: "src" | "prj" | "fnd"): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  const hex = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
  return `${prefix}-${hex.slice(0, 16)}`;
}
