"""Bounded and duplicate-safe modification-request admission."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import boardgate.authoring.request as request_module
from boardgate.authoring.models import ModificationRequest, SetExcellonToolDiameter
from boardgate.authoring.request import (
    ModificationRequestError,
    load_modification_request,
    load_modification_request_bytes,
)


def valid_payload() -> bytes:
    return json.dumps(
        {
            "schema_version": "1.0",
            "base_project_id": "prj-1111111111111111",
            "operation": {
                "schema_version": "1.0",
                "kind": "set_excellon_tool_diameter",
                "operation_version": "1.0",
                "source_logical_path": "board-plated.drl",
                "source_file_id": "src-2222222222222222",
                "source_sha256": "3" * 64,
                "tool_code": "T01",
                "expected_diameter_mm": 0.15,
                "new_diameter_mm": 0.3,
                "instruction": "Increase the selected round drill tool.",
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def test_valid_request_bytes_and_json_file_are_admitted(tmp_path: Path) -> None:
    payload = valid_payload()
    path = tmp_path / "change.json"
    path.write_bytes(payload)

    from_bytes = load_modification_request_bytes(payload, source="change.json")
    from_file = load_modification_request(path)

    assert isinstance(from_bytes, ModificationRequest)
    assert from_file == from_bytes
    assert isinstance(from_bytes.operation, SetExcellonToolDiameter)
    assert from_bytes.operation.tool_code == "T01"


def test_request_size_limit_is_inclusive_and_rejects_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = valid_payload()
    monkeypatch.setattr(request_module, "MAX_MODIFICATION_REQUEST_BYTES", len(payload))

    assert load_modification_request_bytes(payload, source="request.json")
    with pytest.raises(ModificationRequestError) as caught:
        load_modification_request_bytes(payload + b" ", source="request.json")

    assert caught.value.code == "MODIFICATION_REQUEST_TOO_LARGE"


@pytest.mark.parametrize(
    ("payload", "code"),
    (
        (b"\xef\xbb\xbf{}", "MODIFICATION_REQUEST_ENCODING_ERROR"),
        (b"\xff", "MODIFICATION_REQUEST_ENCODING_ERROR"),
        (b"[]", "MODIFICATION_REQUEST_ROOT_ERROR"),
        (
            b'{"base_project_id":"a","base_project_id":"b"}',
            "MODIFICATION_REQUEST_SYNTAX_ERROR",
        ),
        (b'{"value":NaN}', "MODIFICATION_REQUEST_SYNTAX_ERROR"),
        (b'{"unterminated":', "MODIFICATION_REQUEST_SYNTAX_ERROR"),
    ),
)
def test_encoding_syntax_duplicate_and_root_failures_are_typed(
    payload: bytes,
    code: str,
) -> None:
    with pytest.raises(ModificationRequestError) as caught:
        load_modification_request_bytes(payload, source="safe-name.json")

    assert caught.value.code == code
    assert caught.value.source == "safe-name.json"


def test_nested_duplicate_and_unknown_fields_fail_closed() -> None:
    nested_duplicate = valid_payload().replace(
        b'"tool_code":"T01"',
        b'"tool_code":"T01","tool_code":"T02"',
    )
    with pytest.raises(ModificationRequestError) as duplicate:
        load_modification_request_bytes(nested_duplicate, source="change.json")
    assert duplicate.value.code == "MODIFICATION_REQUEST_SYNTAX_ERROR"

    unknown = valid_payload().replace(
        b'"base_project_id"',
        b'"unexpected":true,"base_project_id"',
    )
    with pytest.raises(ModificationRequestError) as invalid:
        load_modification_request_bytes(unknown, source="change.json")
    assert invalid.value.code == "MODIFICATION_REQUEST_VALIDATION_ERROR"
    assert "unexpected" in invalid.value.detail


@pytest.mark.parametrize(
    ("location", "value"),
    (
        (("schema_version",), None),
        (("operation", "schema_version"), None),
        (("operation", "operation_version"), None),
        (("operation", "operation_version"), "2.0"),
    ),
)
def test_executable_request_requires_explicit_supported_versions(
    location: tuple[str, ...],
    value: str | None,
) -> None:
    decoded = json.loads(valid_payload())
    target = decoded
    for part in location[:-1]:
        target = target[part]
    field = location[-1]
    if value is None:
        del target[field]
    else:
        target[field] = value

    with pytest.raises(ModificationRequestError) as caught:
        load_modification_request_bytes(
            json.dumps(decoded, separators=(",", ":")).encode(),
            source="change.json",
        )

    assert caught.value.code == "MODIFICATION_REQUEST_VALIDATION_ERROR"


def test_path_loader_reads_only_the_bounded_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = valid_payload()
    monkeypatch.setattr(request_module, "MAX_MODIFICATION_REQUEST_BYTES", len(payload))
    path = tmp_path / "oversized.json"
    path.write_bytes(payload + b" ignored trailing bytes")

    with pytest.raises(ModificationRequestError) as caught:
        load_modification_request(path)

    assert caught.value.code == "MODIFICATION_REQUEST_TOO_LARGE"


def test_pathological_json_nesting_returns_a_typed_safe_error() -> None:
    depth = 2_000
    payload = b'{"value":' + (b"[" * depth) + b"0" + (b"]" * depth) + b"}"

    with pytest.raises(ModificationRequestError) as caught:
        load_modification_request_bytes(payload, source="deep.json")

    assert caught.value.code in {
        "MODIFICATION_REQUEST_SYNTAX_ERROR",
        "MODIFICATION_REQUEST_VALIDATION_ERROR",
    }
    assert any(
        marker in caught.value.detail for marker in ("too deep", "recursion limit")
    )


def test_file_loader_rejects_non_json_and_source_safe_read_errors(
    tmp_path: Path,
) -> None:
    yaml_path = tmp_path / "change.yaml"
    yaml_path.write_text("not: json\n", encoding="utf-8")
    with pytest.raises(ModificationRequestError) as wrong_format:
        load_modification_request(yaml_path)
    assert wrong_format.value.code == "MODIFICATION_REQUEST_FORMAT_ERROR"

    directory = tmp_path / "unreadable.json"
    directory.mkdir()
    with pytest.raises(ModificationRequestError) as unreadable:
        load_modification_request(directory)
    assert unreadable.value.code == "MODIFICATION_REQUEST_READ_ERROR"
    assert str(tmp_path) not in str(unreadable.value)
