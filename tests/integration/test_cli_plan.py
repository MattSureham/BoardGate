"""CLI evidence that only an exactly matching authorized plan may execute."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from click.testing import CliRunner

from boardgate.authoring import (
    AuthoringPlan,
    GenerationRequest,
    ModificationRequest,
    PlanAuthorization,
    SetExcellonToolDiameter,
)
from boardgate.authoring.identifiers import (
    generation_operation_sha256,
    generation_request_sha256,
    operation_sha256,
    plan_authorization_sha256,
    request_sha256,
)
from boardgate.authoring.plan_models import PLAN_AUTHORIZATION_STATEMENT
from boardgate.cli import main
from boardgate.domain.enums import FileType
from boardgate.domain.serialization import canonical_json
from boardgate.ingestion import build_manifest, discover_inputs

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "drill_too_small"
RULES = ROOT / "rules" / "default.yaml"
APPROVER = "engineer@example.com"
WRONG_DIGEST = "0" * 64


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


def _plan_payload(
    request: ModificationRequest | GenerationRequest,
) -> dict[str, Any]:
    request_kind: Literal["modification", "generation"]
    if isinstance(request, ModificationRequest):
        request_kind = "modification"
        request_digest = request_sha256(request)
        operation_digest = operation_sha256(request.operation)
    else:
        request_kind = "generation"
        request_digest = generation_request_sha256(request)
        operation_digest = generation_operation_sha256(request.operation)
    plan = AuthoringPlan(
        schema_version="1.0",
        plan_version="1.0",
        request_kind=request_kind,
        operation_kind=request.operation.kind,
        operation_version=request.operation.operation_version,
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
    payload = json.loads(canonical_json(plan))
    assert isinstance(payload, dict)
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def _stable_bytes(root: Path) -> dict[str, bytes]:
    return {
        item.relative_to(root).as_posix(): item.read_bytes()
        for item in sorted(root.rglob("*"))
        if item.is_file()
        and item.relative_to(root).as_posix() != "validation/logs/run.jsonl"
    }


def _invoke_modify(
    request_path: Path,
    output: Path,
    plan_path: Path | None = None,
) -> Any:
    arguments = ["modify", str(FIXTURE), "--request", str(request_path)]
    if plan_path is not None:
        arguments.extend(("--plan", str(plan_path)))
    arguments.extend(("--rules", str(RULES), "--output", str(output)))
    return CliRunner().invoke(main, tuple(arguments))


def _invoke_generate(
    request_path: Path,
    output: Path,
    plan_path: Path | None = None,
) -> Any:
    arguments = ["generate", "--request", str(request_path)]
    if plan_path is not None:
        arguments.extend(("--plan", str(plan_path)))
    arguments.extend(("--rules", str(RULES), "--output", str(output)))
    return CliRunner().invoke(main, tuple(arguments))


def test_modify_with_matching_plan_publishes_planless_identical_revision(
    tmp_path: Path,
) -> None:
    request = _modification_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, _plan_payload(request))

    planned_output = tmp_path / "planned"
    planned = _invoke_modify(request_path, planned_output, plan_path)
    assert planned.exit_code == 0, planned.output
    assert "validation READY_FOR_REVIEW" in planned.output

    planless_output = tmp_path / "planless"
    planless = _invoke_modify(request_path, planless_output)
    assert planless.exit_code == 0, planless.output

    assert _stable_bytes(planned_output) == _stable_bytes(planless_output)


def test_generate_with_matching_plan_publishes_planless_identical_generation(
    tmp_path: Path,
) -> None:
    request = _generation_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, _plan_payload(request))

    planned_output = tmp_path / "planned"
    planned = _invoke_generate(request_path, planned_output, plan_path)
    assert planned.exit_code == 0, planned.output
    assert "validation READY_FOR_REVIEW" in planned.output

    planless_output = tmp_path / "planless"
    planless = _invoke_generate(request_path, planless_output)
    assert planless.exit_code == 0, planless.output

    assert _stable_bytes(planned_output) == _stable_bytes(planless_output)


def test_tampered_plan_request_digest_never_executes(tmp_path: Path) -> None:
    request = _modification_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))
    payload = _plan_payload(request)
    payload["request_sha256"] = WRONG_DIGEST
    payload["authorization"]["request_sha256"] = WRONG_DIGEST
    payload["authorization"]["authorization_sha256"] = plan_authorization_sha256(
        approver=APPROVER,
        statement=PLAN_AUTHORIZATION_STATEMENT,
        request_sha256=WRONG_DIGEST,
    )
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, payload)

    output = tmp_path / "out"
    result = _invoke_modify(request_path, output, plan_path)

    assert result.exit_code == 2, result.output
    assert "PLAN_REQUEST_DIGEST_MISMATCH" in result.output
    assert not output.exists()


def test_rebound_plan_authorization_never_executes(tmp_path: Path) -> None:
    request = _generation_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))
    payload = _plan_payload(request)
    payload["authorization"]["authorization_sha256"] = WRONG_DIGEST
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, payload)

    output = tmp_path / "out"
    result = _invoke_generate(request_path, output, plan_path)

    assert result.exit_code == 2, result.output
    assert "PLAN_AUTHORIZATION_MISMATCH" in result.output
    assert not output.exists()


def test_generation_plan_cannot_drive_modify(tmp_path: Path) -> None:
    request = _modification_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, _plan_payload(_generation_request()))

    output = tmp_path / "out"
    result = _invoke_modify(request_path, output, plan_path)

    assert result.exit_code == 2, result.output
    assert "PLAN_REQUEST_KIND_MISMATCH" in result.output
    assert not output.exists()


def test_reworded_request_instruction_invalidates_plan(tmp_path: Path) -> None:
    request = _modification_request()
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, _plan_payload(request))
    reworded = json.loads(canonical_json(request))
    reworded["operation"]["instruction"] = "Reworded prose attempting reuse."
    request_path = tmp_path / "request.json"
    _write_json(request_path, reworded)

    output = tmp_path / "out"
    result = _invoke_modify(request_path, output, plan_path)

    assert result.exit_code == 2, result.output
    assert "PLAN_REQUEST_DIGEST_MISMATCH" in result.output
    assert not output.exists()


def test_reworded_plan_rationale_remains_inert(tmp_path: Path) -> None:
    request = _generation_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))
    payload = _plan_payload(request)
    payload["rationale"] = "Different prose with no digest effect."
    plan_path = tmp_path / "plan.json"
    _write_json(plan_path, payload)

    output = tmp_path / "out"
    result = _invoke_generate(request_path, output, plan_path)

    assert result.exit_code == 0, result.output
    assert "validation READY_FOR_REVIEW" in result.output
    assert (output / "validation" / "findings.json").is_file()


def test_plan_inside_design_inputs_is_rejected(tmp_path: Path) -> None:
    request = _modification_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))

    output = tmp_path / "out"
    result = _invoke_modify(request_path, output, FIXTURE / "plan.json")

    assert result.exit_code == 2, result.output
    assert "MODIFICATION_CONTROL_INSIDE_INPUT" in result.output
    assert not output.exists()


def test_plan_must_be_a_json_file(tmp_path: Path) -> None:
    request = _generation_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))
    plan_path = tmp_path / "plan.txt"
    _write_json(plan_path, _plan_payload(request))

    output = tmp_path / "out"
    result = _invoke_generate(request_path, output, plan_path)

    assert result.exit_code == 2, result.output
    assert "AUTHORING_PLAN_FORMAT_ERROR" in result.output
    assert not output.exists()
