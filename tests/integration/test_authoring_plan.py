"""End-to-end evidence that an authorized plan only drives existing services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import jsonschema
import pytest

from boardgate.application import (
    GenerationService,
    ModificationService,
    validate_generation_workspace,
    validate_modification_workspace,
)
from boardgate.authoring import (
    AuthoringPlan,
    GenerationRequest,
    ModificationRequest,
    PlanAuthorization,
    SetExcellonToolDiameter,
    admit_authoring_plan,
    load_authoring_plan,
)
from boardgate.authoring.identifiers import (
    generation_operation_sha256,
    generation_request_sha256,
    operation_sha256,
    plan_authorization_sha256,
    request_sha256,
)
from boardgate.authoring.plan_models import PLAN_AUTHORIZATION_STATEMENT
from boardgate.config import load_rule_profile
from boardgate.domain.enums import FileType, ReviewStatus
from boardgate.domain.serialization import canonical_json
from boardgate.ingestion import build_manifest, discover_inputs

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "drill_too_small"
RULES = ROOT / "rules" / "default.yaml"
SCHEMAS = ROOT / "schemas" / "v1"
APPROVER = "engineer@example.com"


def _modification_request() -> ModificationRequest:
    with discover_inputs((FIXTURE,)) as discovered:
        manifest = build_manifest(discovered)
    source = next(
        item
        for item in manifest.source_files
        if item.logical_path == "board-plated.drl"
    )
    assert source.file_type is FileType.EXCELLON
    return ModificationRequest(
        schema_version="1.0",
        base_project_id=manifest.project_id,
        operation=SetExcellonToolDiameter(
            schema_version="1.0",
            operation_version="1.0",
            source_logical_path=source.logical_path,
            source_file_id=source.source_file_id,
            source_sha256=source.sha256,
            tool_code="T01",
            expected_diameter_mm=0.1,
            new_diameter_mm=0.3,
            instruction=(
                "Increase the confirmed T01 round-drill diameter to 0.300 mm."
            ),
        ),
    )


def _generation_request() -> GenerationRequest:
    return GenerationRequest.model_validate_json(
        json.dumps(
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
                    "instruction": "Generate a two-layer coupon with one plated hole.",
                },
            }
        )
    )


def _plan_for(request: ModificationRequest | GenerationRequest) -> AuthoringPlan:
    request_kind: Literal["modification", "generation"]
    if isinstance(request, ModificationRequest):
        request_kind = "modification"
        request_digest = request_sha256(request)
        operation_digest = operation_sha256(request.operation)
    else:
        request_kind = "generation"
        request_digest = generation_request_sha256(request)
        operation_digest = generation_operation_sha256(request.operation)
    operation = request.operation
    return AuthoringPlan(
        schema_version="1.0",
        plan_version="1.0",
        request_kind=request_kind,
        operation_kind=operation.kind,
        operation_version=operation.operation_version,
        request_sha256=request_digest,
        operation_sha256=operation_digest,
        authorization=PlanAuthorization(
            approver=APPROVER,
            statement=PLAN_AUTHORIZATION_STATEMENT,
            request_sha256=request_digest,
            authorization_sha256=plan_authorization_sha256(
                approver=APPROVER,
                statement=PLAN_AUTHORIZATION_STATEMENT,
                request_sha256=request_digest,
            ),
        ),
        rationale="Selected Finding minimum_drill_diameter.",
    )


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _validate_public_schema(payload: dict[str, Any], schema_name: str) -> None:
    schema = _read_object(SCHEMAS / schema_name)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(payload)


@pytest.mark.parametrize("request_kind", ("modification", "generation"))
def test_authorized_plan_drives_only_the_registered_service(
    tmp_path: Path,
    request_kind: str,
) -> None:
    if request_kind == "modification":
        request: ModificationRequest | GenerationRequest = _modification_request()
    else:
        request = _generation_request()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        f"{canonical_json(_plan_for(request))}\n",
        encoding="utf-8",
    )

    admitted_plan = load_authoring_plan(plan_path)
    assert isinstance(admitted_plan, AuthoringPlan)
    _validate_public_schema(
        _read_object(plan_path),
        "authoring-plan.schema.json",
    )
    admitted = admit_authoring_plan(admitted_plan, request)
    assert admitted.request == request
    assert tuple(item.name for item in tmp_path.iterdir()) == ("plan.json",)

    output = tmp_path / "revision"
    if isinstance(admitted.request, ModificationRequest):
        modification_run = ModificationService().modify(
            (FIXTURE,),
            admitted.request,
            load_rule_profile(RULES),
            output,
        )
        assert modification_run.overall_status is ReviewStatus.READY_FOR_REVIEW
        validate_modification_workspace(output)
    else:
        generation_run = GenerationService().generate(
            admitted.request,
            load_rule_profile(RULES),
            output,
        )
        assert generation_run.overall_status is ReviewStatus.READY_FOR_REVIEW
        validate_generation_workspace(output)
    assert not tuple(tmp_path.glob(".revision.staging-*"))
    assert not tuple(tmp_path.glob(".revision.backup-*"))
