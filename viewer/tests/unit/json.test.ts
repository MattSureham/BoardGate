import { describe, expect, it } from "vitest";

import { VIEWER_RESOURCE_POLICY } from "../../src/policy";
import {
  canonicalCompact,
  compareUnicodeCodePoints,
  parseCanonicalJson,
  parseCompactJson,
  pythonFloatRepr,
  sha256Prefix,
} from "../../src/validation";
import { pythonCasefold } from "../../src/validation/casefold";
import { failureFrom } from "../../src/validation/errors";

function policy(
  overrides: Partial<typeof VIEWER_RESOURCE_POLICY> = {},
): typeof VIEWER_RESOURCE_POLICY {
  return { ...VIEWER_RESOURCE_POLICY, ...overrides };
}

describe("bounded deterministic JSON", () => {
  it("parses canonical pretty and compact JSON while preserving number lexemes", () => {
    const pretty = parseCanonicalJson(
      '{\n  "array": [\n    1,\n    1.0,\n    1e-06\n  ],\n  "text": "é"\n}\n',
      VIEWER_RESOURCE_POLICY,
    );
    expect(pretty.value).toEqual({ array: [1, 1, 0.000001], text: "é" });
    expect(pretty.numberLexemes.get("/array/1")).toBe("1.0");
    expect(
      canonicalCompact((pretty.value as { array: never[] }).array, pretty.numberLexemes, "/array"),
    ).toBe("[1,1.0,1e-06]");

    expect(parseCompactJson('{"a":1,"b":[]}', VIEWER_RESOURCE_POLICY).value).toEqual({
      a: 1,
      b: [],
    });
  });

  it.each([
    ['{"b": 1, "a": 2}\n', "key order"],
    ['{"a":1}\n', "spacing"],
    ['{\n  "a": 1\n}', "terminator"],
    ['{\n  "a": 01\n}\n', "number"],
    ['{\n  "a": NaN\n}\n', "constant"],
    ['{\n  "a": 1,\n  "a": 2\n}\n', "duplicate"],
    ['{\n  "a": "\\u0061"\n}\n', "noncanonical string"],
  ])("rejects %s (%s)", (payload) => {
    expect(() => parseCanonicalJson(payload, VIEWER_RESOURCE_POLICY)).toThrow();
  });

  it("allows depth and entry equality but rejects N+1", () => {
    expect(() =>
      parseCanonicalJson('{\n  "a": {}\n}\n', policy({ maxJsonDepth: 1, maxJsonEntries: 3 })),
    ).not.toThrow();
    expect(() =>
      parseCanonicalJson('{\n  "a": {\n    "b": 1\n  }\n}\n', policy({ maxJsonDepth: 1 })),
    ).toThrow(/resource policy/i);
    expect(() => parseCanonicalJson('{\n  "a": {}\n}\n', policy({ maxJsonEntries: 2 }))).toThrow(
      /resource policy/i,
    );
  });

  it("sorts by Unicode code point and derives stable SHA-256 prefixes", async () => {
    expect(["z", "😀", "\uffff"].sort(compareUnicodeCodePoints)).toEqual(["z", "\uffff", "😀"]);
    expect(await sha256Prefix('{"a":1}', "src")).toMatch(/^src-[0-9a-f]{16}$/);
    expect(await sha256Prefix('{"a":1}', "src")).toBe(await sha256Prefix('{"a":1}', "src"));
  });

  it.each([
    [0, "0.0"],
    [-0, "-0.0"],
    [1, "1.0"],
    [0.1, "0.1"],
    [0.0001, "0.0001"],
    [0.00001, "1e-05"],
    [0.000001, "1e-06"],
    [1e15, "1000000000000000.0"],
    [1e16, "1e+16"],
    [1.2e20, "1.2e+20"],
    [5e-324, "5e-324"],
    [1.7976931348623157e308, "1.7976931348623157e+308"],
  ])("spells %s as the Python float repr %s", (value, expected) => {
    expect(pythonFloatRepr(value)).toBe(expected);
  });

  it.each(["0.10", "1e+00", "1.0e+00", "1"])(
    "rejects non-Python canonical float spelling %s for a float field",
    (lexeme) => {
      expect(() =>
        parseCanonicalJson(`{\n  "confidence": ${lexeme}\n}\n`, VIEWER_RESOURCE_POLICY),
      ).toThrow(/canonical serialized form/i);
    },
  );

  it.each([
    "arc_chord_error",
    "geometry_epsilon",
    "gross_alignment",
    "min_annular_ring",
    "min_copper_spacing",
    "min_copper_to_edge",
    "min_drill_diameter",
    "min_solder_mask_dam",
    "min_trace_width",
    "outline_closure",
  ])("requires Python float spelling for rule-profile field %s", (field) => {
    expect(() => parseCanonicalJson(`{\n  "${field}": 1\n}\n`, VIEWER_RESOURCE_POLICY)).toThrow(
      /canonical serialized form/i,
    );
  });

  it("accepts canonical negative zero and exponent spelling", () => {
    expect(
      parseCanonicalJson('{\n  "confidence": -0.0,\n  "x": 1e-06\n}\n', VIEWER_RESOURCE_POLICY)
        .numberLexemes,
    ).toEqual(
      new Map([
        ["/confidence", "-0.0"],
        ["/x", "1e-06"],
      ]),
    );
  });

  it("rejects a float lexeme for a strict integer field and unrounded coordinates", () => {
    expect(() => parseCanonicalJson('{\n  "sequence": 1.0\n}\n', VIEWER_RESOURCE_POLICY)).toThrow(
      /canonical serialized form/i,
    );
    expect(() => parseCanonicalJson('{\n  "x": 1.1234567\n}\n', VIEWER_RESOURCE_POLICY)).toThrow(
      /canonical serialized form/i,
    );
  });

  it("matches Python casefold exceptional mappings", () => {
    expect(pythonCasefold("Straße/Σς/ﬃ/Ꭰꭰ")).toBe("strasse/σσ/ffi/ᎠᎠ");
  });

  it("maps unknown exceptions to one stable non-leaking failure", () => {
    expect(failureFrom(new Error("private implementation detail"))).toEqual({
      ok: false,
      error: {
        code: "VIEWER_INTERNAL_ERROR",
        summary: "The viewer could not validate this bundle without exposing partial results.",
      },
    });
  });
});
