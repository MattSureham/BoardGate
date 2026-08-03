"""Bounded, duplicate-safe JSON admission for modification requests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from boardgate.authoring.models import ModificationRequest

MAX_MODIFICATION_REQUEST_BYTES = 1024 * 1024


class ModificationRequestError(ValueError):
    """Typed, source-safe request admission failure."""

    def __init__(self, code: str, source: str, detail: str) -> None:
        self.code = code
        self.source = source
        self.detail = detail
        super().__init__(f"{code}: {detail} [{source}]")


def _reject_json_constant(value: str) -> None:
    msg = f"non-finite JSON number {value!r} is not allowed"
    raise ValueError(msg)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            msg = "request contains a duplicate JSON key"
            raise ValueError(msg)
        result[key] = value
    return result


def load_modification_request_bytes(
    payload: bytes,
    *,
    source: str,
) -> ModificationRequest:
    """Admit one bounded strict JSON request without path-derived semantics."""
    if len(payload) > MAX_MODIFICATION_REQUEST_BYTES:
        raise ModificationRequestError(
            "MODIFICATION_REQUEST_TOO_LARGE",
            source,
            f"request exceeds {MAX_MODIFICATION_REQUEST_BYTES} bytes",
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise ModificationRequestError(
            "MODIFICATION_REQUEST_ENCODING_ERROR",
            source,
            "request must be UTF-8 without a byte-order mark",
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ModificationRequestError(
            "MODIFICATION_REQUEST_ENCODING_ERROR",
            source,
            "request must be UTF-8",
        ) from error
    try:
        raw = json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        if isinstance(error, json.JSONDecodeError):
            detail = f"invalid JSON at line {error.lineno}, column {error.colno}"
        elif isinstance(error, RecursionError):
            detail = "request JSON nesting is too deep"
        else:
            detail = str(error)
        raise ModificationRequestError(
            "MODIFICATION_REQUEST_SYNTAX_ERROR",
            source,
            detail,
        ) from error
    if not isinstance(raw, Mapping):
        raise ModificationRequestError(
            "MODIFICATION_REQUEST_ROOT_ERROR",
            source,
            "request root must be an object",
        )
    try:
        normalized = json.dumps(
            raw,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return ModificationRequest.model_validate_json(normalized)
    except (RecursionError, TypeError, ValueError, ValidationError) as error:
        if isinstance(error, ValidationError):
            first = error.errors(include_url=False, include_input=False)[0]
            location = ".".join(str(part) for part in first["loc"]) or "<root>"
            safe_location = location.encode("unicode_escape").decode("ascii")[:200]
            detail = f"{safe_location}: {first['msg']}"
        elif isinstance(error, RecursionError):
            detail = "request JSON nesting is too deep"
        else:
            detail = "request contains an invalid JSON value"
        raise ModificationRequestError(
            "MODIFICATION_REQUEST_VALIDATION_ERROR",
            source,
            detail,
        ) from error


def load_modification_request(path: Path) -> ModificationRequest:
    """Read and admit one `.json` modification request."""
    source = path.name or "<request>"
    if path.suffix.casefold() != ".json":
        raise ModificationRequestError(
            "MODIFICATION_REQUEST_FORMAT_ERROR",
            source,
            "request extension must be .json",
        )
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_MODIFICATION_REQUEST_BYTES + 1)
    except OSError as error:
        raise ModificationRequestError(
            "MODIFICATION_REQUEST_READ_ERROR",
            source,
            "request could not be read",
        ) from error
    return load_modification_request_bytes(payload, source=source)
