import { reject, type ViewerErrorCode } from "./errors";

const ABSOLUTE_POSIX_PATH = /(?:^|[\s("'=:])\/(?!\/)[^/\s"'():]+(?:\/[^/\s"'():]+)*/;
const ABSOLUTE_WINDOWS_PATH = /(?:^|[\s("'=])(?:[a-z]:[\\/]|\\\\)/i;
const EXCEPTION_REPR =
  /(?:Traceback \(most recent call last\)|\b[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)\s*(?:\(|:)|<[^>\r\n]*\bobject at 0x[0-9a-fA-F]+>)/;
const MEMORY_ADDRESS = /\b0x[0-9a-fA-F]{6,}\b/;

export function validateSafeDiagnosticSummary(value: string, code: ViewerErrorCode): void {
  if (
    value.trim() !== value ||
    ["\r", "\n", "\t", "\u0000"].some((character) => value.includes(character)) ||
    value.toLowerCase().includes("file://") ||
    ABSOLUTE_POSIX_PATH.test(value) ||
    ABSOLUTE_WINDOWS_PATH.test(value) ||
    EXCEPTION_REPR.test(value) ||
    MEMORY_ADDRESS.test(value)
  ) {
    reject(code);
  }
}
