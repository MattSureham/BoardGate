"""Finding structure and stable identifier tests."""

import math

import pytest
from pydantic import ValidationError

from boardgate.domain.enums import RiskMode, Severity
from boardgate.domain.finding import Finding, FindingEvidence, Measurement
from boardgate.domain.geometry import Point, Unit
from boardgate.domain.identifiers import finding_id
from boardgate.domain.provenance import Provenance

PROFILE_SHA = "d" * 64


def make_provenance(object_id: str = "line-1") -> Provenance:
    return Provenance(
        source_file_id="src-0123456789abcdef",
        object_id=object_id,
        parser="test-adapter",
        parser_version="1.0",
    )


def make_measurement() -> Measurement:
    return Measurement(
        actual=0.08,
        required=0.1,
        operator=">=",
        unit=Unit.MILLIMETRE,
        error_bound=0.001,
        config_path="fabrication.min_trace_width",
    )


def test_finding_id_is_stable_across_evidence_order() -> None:
    location = Point(x=1.0, y=2.0)
    measurement = make_measurement()

    first = finding_id(
        rule_id="minimum_trace_width",
        rule_version="1.0.0",
        profile_sha256=PROFILE_SHA,
        evidence_ids=["line-2", "line-1"],
        location=location,
        measurement=measurement,
    )
    second = finding_id(
        rule_id="minimum_trace_width",
        rule_version="1.0.0",
        profile_sha256=PROFILE_SHA,
        evidence_ids=["line-1", "line-2"],
        location=location,
        measurement=measurement,
    )

    assert first == second
    assert first.startswith("fnd-")


def test_finding_json_round_trip_preserves_fact_boundaries() -> None:
    measurement = make_measurement()
    provenance = make_provenance()
    identifier = finding_id(
        rule_id="minimum_trace_width",
        rule_version="1.0.0",
        profile_sha256=PROFILE_SHA,
        evidence_ids=[provenance.object_id or ""],
        location=Point(x=1.0, y=2.0),
        measurement=measurement,
    )
    finding = Finding(
        finding_id=identifier,
        rule_id="minimum_trace_width",
        rule_version="1.0.0",
        category=RiskMode.GEOMETRY_VIOLATION,
        severity=Severity.BLOCKER,
        confidence=0.99,
        config_path="fabrication.min_trace_width",
        title="Trace width below requirement",
        summary="A supported trace is narrower than the configured minimum.",
        facts=("Measured width is 0.08 mm.",),
        inference=None,
        location=Point(x=1.0, y=2.0),
        measurement=measurement,
        evidence=(FindingEvidence(provenance=provenance),),
        suggested_action="Increase trace width to at least 0.10 mm.",
    )

    restored = Finding.model_validate_json(finding.model_dump_json())

    assert restored == finding
    assert restored.inference is None
    assert restored.requires_human_confirmation is False


def test_uncertain_finding_requires_confirmation() -> None:
    with pytest.raises(ValidationError, match="require human confirmation"):
        Finding(
            finding_id="fnd-0123456789abcdef",
            rule_id="outline",
            rule_version="1.0.0",
            category=RiskMode.OUTLINE_UNCERTAIN,
            severity=Severity.WARNING,
            confidence=0.5,
            config_path="required_layers",
            title="Outline uncertain",
            summary="The outline could not be confirmed.",
            facts=("Two candidate outline files exist.",),
            evidence=(FindingEvidence(provenance=make_provenance()),),
        )


def test_measurement_rejects_non_finite_values() -> None:
    with pytest.raises(ValidationError):
        Measurement(
            actual=math.nan,
            required=0.1,
            operator=">=",
            unit=Unit.MILLIMETRE,
            config_path="fabrication.min_trace_width",
        )
