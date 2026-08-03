"""Bounded and duplicate-safe authoring-plan admission."""

from __future__ import annotations

from pathlib import Path

import pytest

import boardgate.authoring.plan_request as plan_module
from boardgate.authoring.plan_models import AuthoringPlan
from boardgate.authoring.plan_request import (
    AuthoringPlanError,
    load_authoring_plan,
    load_authoring_plan_bytes,
)
from boardgate.domain.serialization import canonical_json

from .test_generation_models import request as generation_request
from .test_plan_models import plan_for


def valid_payload() -> bytes:
    return canonical_json(plan_for(generation_request())).encode()


def test_valid_plan_bytes_and_json_file_are_admitted(tmp_path: Path) -> None:
    payload = valid_payload()
    path = tmp_path / "plan.json"
    path.write_bytes(payload)

    from_bytes = load_authoring_plan_bytes(payload, source="plan.json")
    from_file = load_authoring_plan(path)

    assert isinstance(from_bytes, AuthoringPlan)
    assert from_file == from_bytes
    assert from_bytes.plan_version == "1.0"


def test_plan_size_limit_is_inclusive_and_rejects_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = valid_payload()
    monkeypatch.setattr(plan_module, "MAX_AUTHORING_PLAN_BYTES", len(payload))

    admitted = load_authoring_plan_bytes(payload, source="plan.json")
    assert isinstance(admitted, AuthoringPlan)

    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan_bytes(payload + b" ", source="plan.json")
    assert caught.value.code == "AUTHORING_PLAN_TOO_LARGE"


def test_byte_order_mark_is_rejected() -> None:
    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan_bytes(
            b"\xef\xbb\xbf" + valid_payload(),
            source="plan.json",
        )
    assert caught.value.code == "AUTHORING_PLAN_ENCODING_ERROR"


def test_invalid_utf8_is_rejected() -> None:
    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan_bytes(b"\xff\xfe{}", source="plan.json")
    assert caught.value.code == "AUTHORING_PLAN_ENCODING_ERROR"


def test_duplicate_json_keys_are_rejected() -> None:
    payload = valid_payload().replace(
        b'"plan_version":"1.0"',
        b'"plan_version":"1.0","plan_version":"1.0"',
        1,
    )

    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan_bytes(payload, source="plan.json")
    assert caught.value.code == "AUTHORING_PLAN_SYNTAX_ERROR"
    assert "duplicate JSON key" in caught.value.detail


def test_non_finite_numbers_are_rejected() -> None:
    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan_bytes(b'{"schema_version":NaN}', source="plan.json")
    assert caught.value.code == "AUTHORING_PLAN_SYNTAX_ERROR"
    assert "non-finite" in caught.value.detail


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan_bytes(b'{"schema_version":', source="plan.json")
    assert caught.value.code == "AUTHORING_PLAN_SYNTAX_ERROR"


def test_non_object_root_is_rejected() -> None:
    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan_bytes(b'["not", "an", "object"]', source="plan.json")
    assert caught.value.code == "AUTHORING_PLAN_ROOT_ERROR"


def test_contract_violations_are_rejected_without_input_echoes() -> None:
    payload = valid_payload().replace(b'"authoring_plan"', b'"free_form"', 1)

    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan_bytes(payload, source="plan.json")
    assert caught.value.code == "AUTHORING_PLAN_VALIDATION_ERROR"
    assert "free_form" not in caught.value.detail


def test_unregistered_operations_are_rejected() -> None:
    payload = valid_payload().replace(
        b'"operation_kind":"generate_two_layer_coupon"',
        b'"operation_kind":"free_form_writer"',
        1,
    )

    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan_bytes(payload, source="plan.json")
    assert caught.value.code == "AUTHORING_PLAN_VALIDATION_ERROR"
    assert "registered operation" in caught.value.detail


def test_non_json_extension_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "plan.txt"
    path.write_bytes(valid_payload())

    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan(path)
    assert caught.value.code == "AUTHORING_PLAN_FORMAT_ERROR"


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(AuthoringPlanError) as caught:
        load_authoring_plan(tmp_path / "missing.json")
    assert caught.value.code == "AUTHORING_PLAN_READ_ERROR"
