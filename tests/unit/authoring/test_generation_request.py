"""Bounded and duplicate-safe generation-request admission."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import boardgate.authoring.generation_request as request_module
from boardgate.authoring.generation_models import GenerationRequest
from boardgate.authoring.generation_request import (
    GenerationRequestError,
    load_generation_request,
    load_generation_request_bytes,
)


def valid_payload() -> bytes:
    return json.dumps(
        {
            "schema_version": "1.0",
            "operation": {
                "schema_version": "1.0",
                "kind": "generate_two_layer_coupon",
                "operation_version": "1.0",
                "board_width_mm": 20.0,
                "board_height_mm": 15.0,
                "holes": [
                    {
                        "schema_version": "1.0",
                        "x_mm": 5.0,
                        "y_mm": 5.0,
                        "drill_diameter_mm": 0.3,
                        "pad_diameter_mm": 0.8,
                    },
                ],
                "traces": [
                    {
                        "schema_version": "1.0",
                        "x1_mm": 1.0,
                        "y1_mm": 1.0,
                        "x2_mm": 19.0,
                        "y2_mm": 1.0,
                        "width_mm": 0.25,
                        "copper_layers": "both",
                    },
                ],
                "instruction": "Generate the bounded coupon.",
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def test_valid_request_bytes_and_json_file_are_admitted(tmp_path: Path) -> None:
    payload = valid_payload()
    path = tmp_path / "generate.json"
    path.write_bytes(payload)

    from_bytes = load_generation_request_bytes(payload, source="generate.json")
    from_file = load_generation_request(path)

    assert isinstance(from_bytes, GenerationRequest)
    assert from_file == from_bytes
    assert from_bytes.operation.operation_version == "1.0"


def test_request_size_limit_is_inclusive_and_rejects_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = valid_payload()
    monkeypatch.setattr(request_module, "MAX_GENERATION_REQUEST_BYTES", len(payload))

    admitted = load_generation_request_bytes(payload, source="generate.json")
    assert isinstance(admitted, GenerationRequest)

    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request_bytes(payload + b" ", source="generate.json")
    assert caught.value.code == "GENERATION_REQUEST_TOO_LARGE"


def test_byte_order_mark_is_rejected() -> None:
    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request_bytes(
            b"\xef\xbb\xbf" + valid_payload(),
            source="generate.json",
        )
    assert caught.value.code == "GENERATION_REQUEST_ENCODING_ERROR"


def test_invalid_utf8_is_rejected() -> None:
    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request_bytes(b"\xff\xfe{}", source="generate.json")
    assert caught.value.code == "GENERATION_REQUEST_ENCODING_ERROR"


def test_duplicate_json_keys_are_rejected() -> None:
    payload = valid_payload().replace(
        b'"schema_version":"1.0",',
        b'"schema_version":"1.0","schema_version":"1.0",',
        1,
    )

    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request_bytes(payload, source="generate.json")
    assert caught.value.code == "GENERATION_REQUEST_SYNTAX_ERROR"
    assert "duplicate JSON key" in caught.value.detail


def test_non_finite_numbers_are_rejected() -> None:
    payload = valid_payload().replace(b"20.0", b"Infinity", 1)

    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request_bytes(payload, source="generate.json")
    assert caught.value.code == "GENERATION_REQUEST_SYNTAX_ERROR"
    assert "non-finite" in caught.value.detail


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request_bytes(b'{"schema_version":', source="generate.json")
    assert caught.value.code == "GENERATION_REQUEST_SYNTAX_ERROR"


def test_non_object_root_is_rejected() -> None:
    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request_bytes(b'["not", "an", "object"]', source="g.json")
    assert caught.value.code == "GENERATION_REQUEST_ROOT_ERROR"


def test_contract_violations_are_rejected_without_input_echoes() -> None:
    payload = valid_payload().replace(b"0.3", b"0.3000001", 1)

    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request_bytes(payload, source="generate.json")
    assert caught.value.code == "GENERATION_REQUEST_VALIDATION_ERROR"
    assert "0.3000001" not in caught.value.detail


def test_unknown_operation_versions_are_rejected() -> None:
    payload = valid_payload().replace(
        b'"operation_version":"1.0"',
        b'"operation_version":"2.0"',
        1,
    )

    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request_bytes(payload, source="generate.json")
    assert caught.value.code == "GENERATION_REQUEST_VALIDATION_ERROR"


def test_non_json_extension_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "generate.txt"
    path.write_bytes(valid_payload())

    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request(path)
    assert caught.value.code == "GENERATION_REQUEST_FORMAT_ERROR"


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request(tmp_path / "missing.json")
    assert caught.value.code == "GENERATION_REQUEST_READ_ERROR"
