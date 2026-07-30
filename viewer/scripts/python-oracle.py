"""Batch differential oracle for the browser bundle admission tests.

This development-only helper deliberately delegates semantic authority to the
existing Python ``validate_artifact_bundle`` boundary. It emits only stable
case labels, acceptance state, and BoardGate error codes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict

from boardgate.application.artifacts import (
    ArtifactContractError,
    CompleteArtifactBundle,
    validate_artifact_bundle,
)


class OracleCase(TypedDict):
    label: str
    directory: str


class OracleResult(TypedDict):
    label: str
    ok: bool
    code: str | None


def _logical_files(directory: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        logical_path = path.relative_to(directory).as_posix()
        try:
            files[logical_path] = path.read_bytes().decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ArtifactContractError(
                "ARTIFACT_UTF8_INVALID",
                "An artifact is not canonical UTF-8 text.",
            ) from error
    return files


def _validate(case: OracleCase) -> OracleResult:
    label = case["label"]
    try:
        bundle = CompleteArtifactBundle.from_files(
            _logical_files(Path(case["directory"]))
        )
        validate_artifact_bundle(bundle)
    except ArtifactContractError as error:
        return {"label": label, "ok": False, "code": error.code}
    except (OSError, TypeError, ValueError):
        return {"label": label, "ok": False, "code": "ORACLE_INPUT_INVALID"}
    return {"label": label, "ok": True, "code": None}


def main() -> int:
    try:
        request: object = json.load(sys.stdin)
        if not isinstance(request, list):
            raise TypeError
        cases: list[OracleCase] = []
        for raw_case in request:
            if (
                not isinstance(raw_case, dict)
                or not isinstance(raw_case.get("label"), str)
                or not isinstance(raw_case.get("directory"), str)
            ):
                raise TypeError
            cases.append(
                {
                    "label": raw_case["label"],
                    "directory": raw_case["directory"],
                }
            )
    except (json.JSONDecodeError, TypeError):
        sys.stdout.write(
            json.dumps(
                {"error": "ORACLE_REQUEST_INVALID"},
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
        return 2

    sys.stdout.write(
        json.dumps(
            [_validate(case) for case in cases],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
