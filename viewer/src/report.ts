const HEADING = /^(#{1,4}) (.*)$/u;
const LIST_ITEM = /^( *)- (.*)$/u;
const HTML_COMMENT = /^<!--.*?-->$/u;
const ESCAPED_PUNCTUATION = /\\([\\`*_{}[\]()<>#+\-.!|:])/gu;
const MAX_LIST_DEPTH = 4;

export interface ReportInline {
  readonly text: string;
  readonly bold: boolean;
}

export type ReportBlock =
  | { readonly kind: "heading"; readonly level: number; readonly inline: readonly ReportInline[] }
  | { readonly kind: "paragraph"; readonly inline: readonly ReportInline[] }
  | {
      readonly kind: "list";
      readonly items: readonly {
        readonly depth: number;
        readonly inline: readonly ReportInline[];
      }[];
    };

function unescapeComposer(value: string): string {
  return value.replace(ESCAPED_PUNCTUATION, "$1");
}

function parseInline(raw: string): readonly ReportInline[] {
  const parts = raw.split("**");
  if (parts.length % 2 === 0) {
    return [{ text: unescapeComposer(raw), bold: false }];
  }
  const segments: ReportInline[] = [];
  for (const [index, part] of parts.entries()) {
    if (part.length > 0) {
      segments.push({ text: unescapeComposer(part), bold: index % 2 === 1 });
    }
  }
  return segments;
}

export function tokenizeReport(report: string): ReportBlock[] {
  const blocks: ReportBlock[] = [];
  let list: { readonly depth: number; readonly inline: readonly ReportInline[] }[] | undefined;
  const flushList = (): void => {
    if (list !== undefined && list.length > 0) {
      blocks.push({ kind: "list", items: list });
    }
    list = undefined;
  };

  for (const line of report.split("\n")) {
    if (line.trim().length === 0 || HTML_COMMENT.test(line)) {
      flushList();
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading !== null) {
      flushList();
      blocks.push({
        kind: "heading",
        level: (heading[1] as string).length,
        inline: parseInline(heading[2] as string),
      });
      continue;
    }
    const item = LIST_ITEM.exec(line);
    if (item !== null && (item[1] as string).length % 2 === 0) {
      list ??= [];
      list.push({
        depth: Math.min((item[1] as string).length / 2, MAX_LIST_DEPTH),
        inline: parseInline(item[2] as string),
      });
      continue;
    }
    flushList();
    blocks.push({ kind: "paragraph", inline: parseInline(line) });
  }
  flushList();
  return blocks;
}
