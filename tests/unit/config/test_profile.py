"""Manufacturing profile model and loading tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardgate.config.loader import (
    MAX_PROFILE_BYTES,
    RuleProfileError,
    load_rule_profile,
    load_rule_profile_bytes,
)
from boardgate.config.models import RuleId, RuleProfile, profile_hash
from boardgate.domain.enums import LayerRole

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE = ROOT / "rules" / "default.yaml"


def default_payload() -> bytes:
    return DEFAULT_PROFILE.read_bytes()


def test_default_profile_loads_with_expected_limits() -> None:
    profile = load_rule_profile(DEFAULT_PROFILE)

    assert profile.schema_version == "1.0"
    assert profile.required_layers == (
        LayerRole.TOP_COPPER,
        LayerRole.BOTTOM_COPPER,
        LayerRole.BOARD_OUTLINE,
    )
    assert profile.fabrication.min_trace_width == 0.1
    assert profile.fabrication.min_copper_to_edge == 0.25
    assert profile.tolerances.outline_closure == 0.01
    assert profile.tolerances.geometry_epsilon == 0.001
    assert profile.tolerances.gross_alignment == 0.5
    assert profile.rules.by_id(RuleId.MINIMUM_TRACE_WIDTH).affects_readiness


def test_yaml_and_json_have_the_same_model_and_hash() -> None:
    profile = load_rule_profile(DEFAULT_PROFILE)
    json_payload = json.dumps(profile.model_dump(mode="json")).encode()
    parsed_json = load_rule_profile_bytes(
        json_payload,
        source="profile.json",
        format_hint=".json",
    )

    assert parsed_json == profile
    assert profile_hash(parsed_json) == profile_hash(profile)
    assert len(profile_hash(profile)) == 64


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"---\n{}\n---\n{}\n", "PROFILE_DOCUMENT_COUNT"),
        (b"value: &shared []\ncopy: *shared\n", "PROFILE_YAML_REFERENCE_REJECTED"),
        (b"value: !custom thing\n", "PROFILE_YAML_TAG_REJECTED"),
        (b"value: 1\nvalue: 2\n", "PROFILE_SYNTAX_ERROR"),
        (b"- not\n- a\n- mapping\n", "PROFILE_ROOT_ERROR"),
    ],
)
def test_yaml_restrictions(payload: bytes, code: str) -> None:
    with pytest.raises(RuleProfileError) as caught:
        load_rule_profile_bytes(
            payload,
            source="profile.yaml",
            format_hint=".yaml",
        )

    assert caught.value.code == code


def test_yaml_legacy_boolean_words_remain_strings() -> None:
    payload = default_payload().replace(
        b"assembly_auto_scope: true",
        b"assembly_auto_scope: yes",
    )

    with pytest.raises(
        RuleProfileError,
        match=r"PROFILE_VALIDATION_ERROR.*assembly_auto_scope",
    ):
        load_rule_profile_bytes(
            payload,
            source="profile.yaml",
            format_hint=".yaml",
        )


@pytest.mark.parametrize(
    ("payload", "format_hint", "code"),
    [
        (b"{", ".json", "PROFILE_SYNTAX_ERROR"),
        (b'{"profile": 1, "profile": 2}', ".json", "PROFILE_SYNTAX_ERROR"),
        (b'{"value": NaN}', ".json", "PROFILE_SYNTAX_ERROR"),
        (b"{}", ".toml", "PROFILE_FORMAT_ERROR"),
        (b"\xff", ".yaml", "PROFILE_ENCODING_ERROR"),
        (b"null", ".json", "PROFILE_ROOT_ERROR"),
    ],
)
def test_structural_errors_are_typed(
    payload: bytes,
    format_hint: str,
    code: str,
) -> None:
    with pytest.raises(RuleProfileError) as caught:
        load_rule_profile_bytes(
            payload,
            source="profile",
            format_hint=format_hint,
        )

    assert caught.value.code == code


def test_profile_size_limit_is_enforced_before_decode() -> None:
    with pytest.raises(RuleProfileError) as caught:
        load_rule_profile_bytes(
            b"x" * (MAX_PROFILE_BYTES + 1),
            source="large.yaml",
            format_hint=".yaml",
        )

    assert caught.value.code == "PROFILE_TOO_LARGE"


def test_invalid_profile_reports_field_without_absolute_path(tmp_path: Path) -> None:
    profile_path = tmp_path / "invalid.yaml"
    profile_path.write_text(
        default_payload()
        .decode()
        .replace("min_trace_width: 0.10", "min_trace_width: -1"),
        encoding="utf-8",
    )

    with pytest.raises(RuleProfileError) as caught:
        load_rule_profile(profile_path)

    assert caught.value.code == "PROFILE_VALIDATION_ERROR"
    assert "fabrication.min_trace_width" in caught.value.detail
    assert str(tmp_path) not in str(caught.value)


def test_profile_is_strict_and_forbids_unknown_fields() -> None:
    profile = load_rule_profile(DEFAULT_PROFILE)
    data = profile.model_dump(mode="json")
    data["unexpected"] = True

    with pytest.raises(RuleProfileError, match="Extra inputs are not permitted"):
        load_rule_profile_bytes(
            json.dumps(data).encode(),
            source="profile.json",
            format_hint=".json",
        )

    assert RuleProfile.model_validate_json(profile.model_dump_json()) == profile
