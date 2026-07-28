"""Cross-platform logical-path normalization and validation."""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath

from boardgate.ingestion.errors import IngestionError

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_WINDOWS_FORBIDDEN = frozenset('<>:"|?*')
_FIRST_PRINTABLE_CODEPOINT = 32


def normalize_logical_path(raw_path: str, *, subject: str) -> str:
    """Return one safe, normalized relative POSIX path."""
    if not raw_path or "\x00" in raw_path:
        raise IngestionError(
            "UNSAFE_PATH",
            subject,
            "input path is empty or contains a NUL byte",
        )
    normalized_unicode = unicodedata.normalize("NFC", raw_path)
    if (
        normalized_unicode.startswith(("/", "\\"))
        or _DRIVE_PREFIX.match(normalized_unicode)
        or "\\" in normalized_unicode
    ):
        raise IngestionError(
            "UNSAFE_PATH",
            subject,
            "absolute, drive-qualified, and backslash paths are rejected",
        )
    raw_parts = normalized_unicode.split("/")
    if ".." in raw_parts:
        raise IngestionError(
            "UNSAFE_PATH",
            subject,
            "parent-directory traversal is rejected",
        )
    path = PurePosixPath(normalized_unicode)
    parts = tuple(part for part in path.parts if part != ".")
    if not parts:
        raise IngestionError("UNSAFE_PATH", subject, "path has no file name")
    for part in parts:
        if any(ord(character) < _FIRST_PRINTABLE_CODEPOINT for character in part):
            raise IngestionError(
                "UNSAFE_PATH",
                subject,
                "control characters are rejected",
            )
        if any(character in _WINDOWS_FORBIDDEN for character in part):
            raise IngestionError(
                "UNSAFE_PATH",
                subject,
                "path contains a cross-platform forbidden character",
            )
        if part.endswith((" ", ".")):
            raise IngestionError(
                "UNSAFE_PATH",
                subject,
                "path components may not end in a space or dot",
            )
    return PurePosixPath(*parts).as_posix()


def path_collision_key(logical_path: str) -> str:
    """Return a conservative cross-platform collision key."""
    return unicodedata.normalize("NFC", logical_path).casefold()
