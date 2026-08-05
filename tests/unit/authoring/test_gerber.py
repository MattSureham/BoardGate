"""Constrained Gerber aperture-diameter patch and semantic postconditions."""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest

import boardgate.authoring.gerber as gerber_module
from boardgate.authoring.excellon import AuthoringOperationError
from boardgate.authoring.gerber import (
    GerberPatchCandidate,
    prepare_gerber_aperture_diameter_patch,
    require_gerber_file_type,
    scan_gerber_aperture_definitions,
    verify_gerber_aperture_diameter_patch,
)
from boardgate.authoring.models import SetGerberStandardApertureDiameter
from boardgate.domain.enums import ApertureShape, FileType
from boardgate.domain.geometry import Point
from boardgate.domain.identifiers import source_file_id
from boardgate.domain.layer import (
    ArcPrimitive,
    FlashPrimitive,
    LinePrimitive,
    RegionPrimitive,
)
from boardgate.parsers.gerber import GerberParseResult, parse_gerber

SUBJECT = "board-top-copper.gtl"
PAYLOAD = (
    b"G04 authoring test*\n"
    b"%FSLAX46Y46*%\n"
    b"%MOMM*%\n"
    b"%ADD10C,0.800*%\n"
    b"%ADD11C,0.050*%\n"
    b"D10*\n"
    b"X05000000Y05000000D03*\n"
    b"D11*\n"
    b"X10000000Y08000000D02*\n"
    b"X10000000Y12000000D01*\n"
    b"M02*\n"
)


def parse_payload(payload: bytes, *, logical_path: str = SUBJECT) -> GerberParseResult:
    digest = hashlib.sha256(payload).hexdigest()
    return parse_gerber(
        payload,
        logical_path=logical_path,
        source_file_id=source_file_id(logical_path, digest),
    )


def operation(
    payload: bytes = PAYLOAD,
    *,
    expected: float = 0.05,
    new: float = 0.3,
    aperture_code: str = "D11",
) -> SetGerberStandardApertureDiameter:
    digest = hashlib.sha256(payload).hexdigest()
    return SetGerberStandardApertureDiameter(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path=SUBJECT,
        source_file_id=source_file_id(SUBJECT, digest),
        source_sha256=digest,
        aperture_code=aperture_code,
        expected_diameter_mm=expected,
        new_diameter_mm=new,
        instruction="Increase the selected standard round aperture.",
    )


def prepared_patch(
    payload: bytes = PAYLOAD,
    *,
    request: SetGerberStandardApertureDiameter | None = None,
) -> tuple[GerberParseResult, GerberPatchCandidate, GerberParseResult]:
    selected = request or operation(payload)
    before = parse_payload(payload)
    candidate = prepare_gerber_aperture_diameter_patch(payload, before, selected)
    after = parse_gerber(
        candidate.payload,
        logical_path=SUBJECT,
        source_file_id=candidate.output_source_file_id,
    )
    return before, candidate, after


def target_primitives(
    parsed: GerberParseResult, *, aperture_code: str = "D11"
) -> tuple[LinePrimitive | ArcPrimitive | FlashPrimitive, ...]:
    return tuple(
        primitive
        for primitive in parsed.primitives
        if not isinstance(primitive, RegionPrimitive)
        and primitive.provenance.metadata.get("aperture_code") == aperture_code
    )


def test_scanner_returns_normalized_apertures_and_exact_byte_spans() -> None:
    witnesses = scan_gerber_aperture_definitions(PAYLOAD, subject=SUBJECT)

    assert [(item.aperture_code, item.diameter_lexeme) for item in witnesses] == [
        ("D10", "0.800"),
        ("D11", "0.050"),
    ]
    first = witnesses[0]
    assert first.value_span.start_line == first.value_span.end_line == 4
    start = PAYLOAD.index(b"0.800")
    assert (first.value_span.start_byte, first.value_span.end_byte) == (
        start,
        start + len(b"0.800"),
    )


def test_scanner_limits_are_inclusive_and_reject_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gerber_module, "MAX_GERBER_PATCH_BYTES", 8)
    assert scan_gerber_aperture_definitions(b";123456\n", subject=SUBJECT) == ()
    with pytest.raises(AuthoringOperationError) as source_limit:
        scan_gerber_aperture_definitions(b";1234567\n", subject=SUBJECT)
    assert source_limit.value.code == "AUTHORING_SOURCE_SIZE_LIMIT"

    monkeypatch.setattr(gerber_module, "MAX_GERBER_PATCH_BYTES", 1024)
    monkeypatch.setattr(gerber_module, "MAX_GERBER_LINE_BYTES", 8)
    assert scan_gerber_aperture_definitions(b";1234567\n", subject=SUBJECT) == ()
    with pytest.raises(AuthoringOperationError) as line_limit:
        scan_gerber_aperture_definitions(b";12345678\n", subject=SUBJECT)
    assert line_limit.value.code == "AUTHORING_GERBER_LINE_LIMIT"

    monkeypatch.setattr(gerber_module, "MAX_GERBER_LINE_BYTES", 4096)
    monkeypatch.setattr(gerber_module, "MAX_GERBER_LINES", 2)
    assert scan_gerber_aperture_definitions(b"; one\n; two\n", subject=SUBJECT) == ()
    with pytest.raises(AuthoringOperationError) as line_count_limit:
        scan_gerber_aperture_definitions(
            b"; one\n; two\n; three\n",
            subject=SUBJECT,
        )
    assert line_count_limit.value.code == "AUTHORING_GERBER_LINE_COUNT_LIMIT"

    monkeypatch.setattr(gerber_module, "MAX_GERBER_LINES", 1_000_000)
    monkeypatch.setattr(gerber_module, "MAX_GERBER_APERTURE_DEFINITIONS", 2)
    assert (
        len(
            scan_gerber_aperture_definitions(
                b"%ADD10C,0.100*%\n%ADD11C,0.200*%\n",
                subject=SUBJECT,
            )
        )
        == 2
    )
    with pytest.raises(AuthoringOperationError) as aperture_limit:
        scan_gerber_aperture_definitions(
            b"%ADD10C,0.100*%\n%ADD11C,0.200*%\n%ADD12C,0.300*%\n",
            subject=SUBJECT,
        )
    assert aperture_limit.value.code == "AUTHORING_GERBER_APERTURE_LIMIT"


def test_patch_changes_only_the_target_token_and_preserves_metadata() -> None:
    selected = operation()
    before, candidate, after = prepared_patch(request=selected)

    expected = PAYLOAD.replace(b"%ADD11C,0.050*%", b"%ADD11C,0.300*%")
    assert candidate.payload == expected
    assert len(candidate.payload) == len(PAYLOAD)
    assert candidate.input_sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert candidate.output_sha256 == hashlib.sha256(expected).hexdigest()
    before_targets = target_primitives(before)
    assert len(before_targets) == 1
    assert candidate.affected_input_primitive_ids == tuple(
        primitive.primitive_id for primitive in before_targets
    )
    after_targets = target_primitives(after)
    assert len(after_targets) == 1
    assert after_targets[0].aperture.width_mm == pytest.approx(0.3)
    assert after_targets[0].aperture.shape is ApertureShape.CIRCLE

    applied = verify_gerber_aperture_diameter_patch(
        before,
        after,
        selected,
        candidate,
    )
    assert applied.input_value_span == applied.output_value_span
    assert applied.output_sha256 == candidate.output_sha256
    assert (
        applied.affected_input_primitive_ids == candidate.affected_input_primitive_ids
    )
    assert applied.affected_output_primitive_ids == tuple(
        primitive.primitive_id for primitive in after_targets
    )


@pytest.mark.parametrize(
    ("payload", "code"),
    (
        (
            b" %ADD10C,0.050*%\n",
            "AUTHORING_GERBER_APERTURE_DEFINITION_UNSUPPORTED",
        ),
        (
            b"%ADD10C,0.050X0.010*%\n",
            "AUTHORING_GERBER_APERTURE_DEFINITION_UNSUPPORTED",
        ),
        (
            b"%ADD10C,.050*%\n",
            "AUTHORING_GERBER_APERTURE_DEFINITION_UNSUPPORTED",
        ),
        (
            b"%ADD10C,0.050*%\n%ADD010C,0.100*%\n",
            "AUTHORING_GERBER_APERTURE_DUPLICATE",
        ),
    ),
)
def test_scanner_rejects_unsupported_or_duplicate_aperture_definitions(
    payload: bytes,
    code: str,
) -> None:
    with pytest.raises(AuthoringOperationError) as caught:
        scan_gerber_aperture_definitions(payload, subject=SUBJECT)
    assert caught.value.code == code


def test_patch_rejects_stale_digest_source_id_and_old_value() -> None:
    parsed = parse_payload(PAYLOAD)
    stale_digest = operation().model_copy(update={"source_sha256": "f" * 64})
    with pytest.raises(AuthoringOperationError) as digest_error:
        prepare_gerber_aperture_diameter_patch(PAYLOAD, parsed, stale_digest)
    assert digest_error.value.code == "AUTHORING_SOURCE_SHA_MISMATCH"

    stale_id = operation().model_copy(update={"source_file_id": "src-ffffffffffffffff"})
    with pytest.raises(AuthoringOperationError) as id_error:
        prepare_gerber_aperture_diameter_patch(PAYLOAD, parsed, stale_id)
    assert id_error.value.code == "AUTHORING_SOURCE_ID_MISMATCH"

    wrong_old_value = operation(expected=0.2)
    with pytest.raises(AuthoringOperationError) as old_value_error:
        prepare_gerber_aperture_diameter_patch(PAYLOAD, parsed, wrong_old_value)
    assert old_value_error.value.code == "AUTHORING_PRECONDITION_MISMATCH"


def test_patch_rejects_missing_unused_and_unrepresentable_targets() -> None:
    parsed = parse_payload(PAYLOAD)
    missing = operation(aperture_code="D12")
    with pytest.raises(AuthoringOperationError) as missing_error:
        prepare_gerber_aperture_diameter_patch(PAYLOAD, parsed, missing)
    assert missing_error.value.code == "AUTHORING_GERBER_APERTURE_NOT_FOUND"

    unused_payload = (
        b"G04 unused test*\n"
        b"%FSLAX46Y46*%\n"
        b"%MOMM*%\n"
        b"%ADD10C,0.800*%\n"
        b"%ADD11C,0.050*%\n"
        b"D10*\n"
        b"X05000000Y05000000D03*\n"
        b"M02*\n"
    )
    with pytest.raises(AuthoringOperationError) as unused_error:
        prepare_gerber_aperture_diameter_patch(
            unused_payload,
            parse_payload(unused_payload),
            operation(unused_payload),
        )
    assert unused_error.value.code == "AUTHORING_GERBER_APERTURE_UNUSED"

    too_precise = operation(new=0.0555)
    with pytest.raises(AuthoringOperationError) as precision_error:
        prepare_gerber_aperture_diameter_patch(PAYLOAD, parsed, too_precise)
    assert precision_error.value.code == "AUTHORING_GERBER_NEW_DIAMETER_PRECISION"

    too_wide = operation(new=10.0)
    with pytest.raises(AuthoringOperationError) as width_error:
        prepare_gerber_aperture_diameter_patch(PAYLOAD, parsed, too_wide)
    assert width_error.value.code == "AUTHORING_GERBER_NEW_DIAMETER_WIDTH"


def test_patch_rejects_non_metric_and_diagnostic_sources() -> None:
    payload = Path("tests/fixtures/parser/gerber/inch.gbr").read_bytes()
    parsed = parse_payload(payload)
    selected = operation(payload, expected=0.01, new=0.02, aperture_code="D10")
    with pytest.raises(AuthoringOperationError) as unit_error:
        prepare_gerber_aperture_diameter_patch(payload, parsed, selected)
    assert unit_error.value.code == "AUTHORING_GERBER_UNIT_UNSUPPORTED"

    macro_payload = (
        b"G04 macro mix*\n"
        b"%FSLAX46Y46*%\n"
        b"%MOMM*%\n"
        b"%AMROUND*1,1,$1,0,0*%\n"
        b"%ADD10ROUND,0.500*%\n"
        b"%ADD11C,0.050*%\n"
        b"D10*\n"
        b"X1000000Y1000000D03*\n"
        b"D11*\n"
        b"X1000000Y2000000D03*\n"
        b"M02*\n"
    )
    macro_parsed = parse_payload(macro_payload)
    assert macro_parsed.limitations
    with pytest.raises(AuthoringOperationError) as diagnostic_error:
        prepare_gerber_aperture_diameter_patch(
            macro_payload,
            macro_parsed,
            operation(macro_payload),
        )
    assert diagnostic_error.value.code == "AUTHORING_GERBER_DIAGNOSTIC_UNSUPPORTED"


def test_patch_rejects_incremental_notation() -> None:
    parsed = parse_payload(PAYLOAD).model_copy(update={"notation": "incremental"})
    with pytest.raises(AuthoringOperationError) as caught:
        prepare_gerber_aperture_diameter_patch(PAYLOAD, parsed, operation())
    assert caught.value.code == "AUTHORING_GERBER_NOTATION_UNSUPPORTED"


def test_patch_rejects_holed_or_non_circle_target_apertures() -> None:
    before = parse_payload(PAYLOAD)
    line = target_primitives(before)[0]

    holed = line.model_copy(
        update={"aperture": line.aperture.model_copy(update={"hole_diameter_mm": 0.01})}
    )
    holed_parsed = before.model_copy(
        update={
            "primitives": tuple(
                holed if primitive is line else primitive
                for primitive in before.primitives
            )
        }
    )
    with pytest.raises(AuthoringOperationError) as hole_error:
        prepare_gerber_aperture_diameter_patch(PAYLOAD, holed_parsed, operation())
    assert hole_error.value.code == "AUTHORING_GERBER_APERTURE_SCOPE_UNSUPPORTED"

    rectangular = line.model_copy(
        update={
            "aperture": line.aperture.model_copy(
                update={"shape": ApertureShape.RECTANGLE}
            )
        }
    )
    rectangular_parsed = before.model_copy(
        update={
            "primitives": tuple(
                rectangular if primitive is line else primitive
                for primitive in before.primitives
            )
        }
    )
    with pytest.raises(AuthoringOperationError) as shape_error:
        prepare_gerber_aperture_diameter_patch(PAYLOAD, rectangular_parsed, operation())
    assert shape_error.value.code == "AUTHORING_GERBER_APERTURE_SCOPE_UNSUPPORTED"


def test_semantic_verification_rejects_unrelated_primitive_change() -> None:
    selected = operation()
    before, candidate, after = prepared_patch(request=selected)
    flash = target_primitives(after, aperture_code="D10")[0]
    moved = flash.model_copy(update={"position": Point(x=9.0, y=8.0)})
    tampered = after.model_copy(
        update={
            "primitives": tuple(
                moved if primitive is flash else primitive
                for primitive in after.primitives
            )
        }
    )

    with pytest.raises(AuthoringOperationError) as caught:
        verify_gerber_aperture_diameter_patch(before, tampered, selected, candidate)
    assert caught.value.code == "AUTHORING_POSTCONDITION_PRIMITIVE_CHANGED"


def test_semantic_verification_rejects_inconsistent_output_identity() -> None:
    selected = operation()
    before, candidate, after = prepared_patch(request=selected)
    tampered = dataclasses.replace(
        candidate,
        output_source_file_id="src-ffffffffffffffff",
    )

    with pytest.raises(AuthoringOperationError) as caught:
        verify_gerber_aperture_diameter_patch(before, after, selected, tampered)
    assert caught.value.code == "AUTHORING_POSTCONDITION_SOURCE_MISMATCH"


def test_semantic_verification_rejects_metadata_and_count_changes() -> None:
    selected = operation()
    before, candidate, after = prepared_patch(request=selected)

    metadata_tampered = after.model_copy(update={"layer_hints": ("tampered",)})
    with pytest.raises(AuthoringOperationError) as metadata_error:
        verify_gerber_aperture_diameter_patch(
            before,
            metadata_tampered,
            selected,
            candidate,
        )
    assert metadata_error.value.code == "AUTHORING_POSTCONDITION_METADATA_CHANGED"

    count_tampered = after.model_copy(update={"primitives": after.primitives[:1]})
    with pytest.raises(AuthoringOperationError) as count_error:
        verify_gerber_aperture_diameter_patch(
            before,
            count_tampered,
            selected,
            candidate,
        )
    assert count_error.value.code == "AUTHORING_POSTCONDITION_FEATURE_COUNT_CHANGED"


def test_semantic_verification_rejects_diameter_and_target_set_changes() -> None:
    selected = operation()
    before, candidate, after = prepared_patch(request=selected)

    line = target_primitives(after)[0]
    wrong_width = line.model_copy(
        update={"aperture": line.aperture.model_copy(update={"width_mm": 0.4})}
    )
    width_tampered = after.model_copy(
        update={
            "primitives": tuple(
                wrong_width if primitive is line else primitive
                for primitive in after.primitives
            )
        }
    )
    with pytest.raises(AuthoringOperationError) as diameter_error:
        verify_gerber_aperture_diameter_patch(
            before,
            width_tampered,
            selected,
            candidate,
        )
    assert diameter_error.value.code == "AUTHORING_POSTCONDITION_DIAMETER_MISMATCH"

    target_tampered = dataclasses.replace(
        candidate,
        affected_input_primitive_ids=(),
    )
    with pytest.raises(AuthoringOperationError) as target_error:
        verify_gerber_aperture_diameter_patch(
            before,
            after,
            selected,
            target_tampered,
        )
    assert target_error.value.code == "AUTHORING_POSTCONDITION_TARGET_COUNT_CHANGED"


def test_target_type_check_is_explicit() -> None:
    require_gerber_file_type(FileType.GERBER, subject=SUBJECT)
    with pytest.raises(AuthoringOperationError) as caught:
        require_gerber_file_type(FileType.EXCELLON, subject=SUBJECT)
    assert caught.value.code == "AUTHORING_TARGET_TYPE_MISMATCH"
