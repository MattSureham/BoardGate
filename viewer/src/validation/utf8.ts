import { reject } from "./errors";

const UTF8_BOM = [0xef, 0xbb, 0xbf] as const;

export function decodeUtf8Bytes(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  if (bytes.length >= UTF8_BOM.length && UTF8_BOM.every((value, index) => bytes[index] === value)) {
    reject("ARTIFACT_UTF8_INVALID");
  }
  try {
    const text = new TextDecoder("utf-8", {
      fatal: true,
      ignoreBOM: true,
    }).decode(bytes);
    if (text.startsWith("\ufeff")) {
      reject("ARTIFACT_UTF8_INVALID");
    }
    return text;
  } catch {
    reject("ARTIFACT_UTF8_INVALID");
  }
}

export async function decodeUtf8(blob: Blob): Promise<string> {
  return decodeUtf8Bytes(await blob.arrayBuffer());
}
