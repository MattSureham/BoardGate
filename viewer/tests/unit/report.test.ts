import { describe, expect, it } from "vitest";

import { tokenizeReport } from "../../src/report";

describe("report tokenizer", () => {
  it("returns no blocks for empty or metadata-only input", () => {
    expect(tokenizeReport("")).toEqual([]);
    expect(tokenizeReport("\n\n")).toEqual([]);
    expect(
      tokenizeReport(
        "<!-- boardgate-project-id: prj-0000000000000000 -->\n" +
          `<!-- boardgate-profile-sha256: ${"0".repeat(64)} -->\n`,
      ),
    ).toEqual([]);
  });

  it("tokenizes headings, paragraphs, and nested lists", () => {
    const blocks = tokenizeReport(
      "# Title\n\n## Section\n\nIntro line\n\n- first\n  - nested\n- second\n\n#### Detail\n",
    );
    expect(blocks).toEqual([
      { kind: "heading", level: 1, inline: [{ text: "Title", bold: false }] },
      { kind: "heading", level: 2, inline: [{ text: "Section", bold: false }] },
      { kind: "paragraph", inline: [{ text: "Intro line", bold: false }] },
      {
        kind: "list",
        items: [
          { depth: 0, inline: [{ text: "first", bold: false }] },
          { depth: 1, inline: [{ text: "nested", bold: false }] },
          { depth: 0, inline: [{ text: "second", bold: false }] },
        ],
      },
      { kind: "heading", level: 4, inline: [{ text: "Detail", bold: false }] },
    ]);
  });

  it("splits bold segments and unescapes composer punctuation", () => {
    const blocks = tokenizeReport(
      "- Overall status: **READY_FOR_REVIEW**\n" +
        "- Escaped \\*\\*not bold\\*\\* and \\#hash\\# and \\\\ backslash\n",
    );
    expect(blocks).toEqual([
      {
        kind: "list",
        items: [
          {
            depth: 0,
            inline: [
              { text: "Overall status: ", bold: false },
              { text: "READY_FOR_REVIEW", bold: true },
            ],
          },
          {
            depth: 0,
            inline: [{ text: "Escaped **not bold** and #hash# and \\ backslash", bold: false }],
          },
        ],
      },
    ]);
  });

  it("treats unbalanced bold markers as literal text", () => {
    expect(tokenizeReport("has **unbalanced bold\n")).toEqual([
      { kind: "paragraph", inline: [{ text: "has **unbalanced bold", bold: false }] },
    ]);
  });

  it("falls back to paragraphs for unknown structures", () => {
    expect(tokenizeReport("##### too deep\n- \n   - odd indent\n| table |\n")).toEqual([
      { kind: "paragraph", inline: [{ text: "##### too deep", bold: false }] },
      { kind: "list", items: [{ depth: 0, inline: [] }] },
      { kind: "paragraph", inline: [{ text: "   - odd indent", bold: false }] },
      { kind: "paragraph", inline: [{ text: "| table |", bold: false }] },
    ]);
  });

  it("keeps unknown backslash sequences literal", () => {
    expect(tokenizeReport("path C:\\temp\\file\n")).toEqual([
      { kind: "paragraph", inline: [{ text: "path C:\\temp\\file", bold: false }] },
    ]);
  });

  it("clamps deep nesting to the maximum rendered depth", () => {
    const blocks = tokenizeReport("          - deep\n");
    expect(blocks).toEqual([
      { kind: "list", items: [{ depth: 4, inline: [{ text: "deep", bold: false }] }] },
    ]);
  });
});
