"""CLI evidence that only an exactly matching authorized plan may execute."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pytest
from click.testing import CliRunner

from boardgate.authoring import (
    AuthoringPlan,
    GenerationRequest,
    ModificationRequest,
    PlanAuthorization,
    SetExcellonToolDiameter,
    admit_authoring_plan,
    load_authoring_plan,
    mint_authoring_plan,
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


def _invoke_plan(  # noqa: PLR0913
    request_path: Path,
    output: Path,
    *,
    kind: str,
    approver: str = APPROVER,
    rationale: str | None = None,
    overwrite: bool = False,
) -> Any:
    arguments = [
        "plan",
        "--request",
        str(request_path),
        "--kind",
        kind,
        "--approver",
        approver,
        "--output",
        str(output),
    ]
    if rationale is not None:
        arguments.extend(("--rationale", rationale))
    if overwrite:
        arguments.append("--overwrite")
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


@pytest.mark.parametrize("kind", ("modification", "generation"))
def test_minted_plan_drives_services_identically_to_planless(
    tmp_path: Path,
    kind: str,
) -> None:
    if kind == "modification":
        request: ModificationRequest | GenerationRequest = _modification_request()
    else:
        request = _generation_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))
    plan_path = tmp_path / "plan.json"

    minted = _invoke_plan(request_path, plan_path, kind=kind)
    assert minted.exit_code == 0, minted.output
    expected = mint_authoring_plan(request, approver=APPROVER)
    assert plan_path.read_bytes() == f"{canonical_json(expected)}\n".encode()
    admitted = admit_authoring_plan(load_authoring_plan(plan_path), request)
    assert admitted.request == request

    planned_output = tmp_path / "planned"
    if kind == "modification":
        planned = _invoke_modify(request_path, planned_output, plan_path)
    else:
        planned = _invoke_generate(request_path, planned_output, plan_path)
    assert planned.exit_code == 0, planned.output
    assert "validation READY_FOR_REVIEW" in planned.output

    planless_output = tmp_path / "planless"
    if kind == "modification":
        planless = _invoke_modify(request_path, planless_output)
    else:
        planless = _invoke_generate(request_path, planless_output)
    assert planless.exit_code == 0, planless.output

    assert _stable_bytes(planned_output) == _stable_bytes(planless_output)


def test_plan_command_output_is_byte_deterministic(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(_generation_request())))
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    assert _invoke_plan(request_path, first, kind="generation").exit_code == 0
    assert _invoke_plan(request_path, second, kind="generation").exit_code == 0

    assert first.read_bytes() == second.read_bytes()


def test_plan_command_writes_only_the_plan_file(tmp_path: Path) -> None:
    request = _modification_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))
    plan_path = tmp_path / "plan.json"

    result = _invoke_plan(
        request_path,
        plan_path,
        kind="modification",
        rationale="Selected Finding minimum_drill_diameter.",
    )

    assert result.exit_code == 0, result.output
    assert sorted(item.name for item in tmp_path.iterdir()) == [
        "plan.json",
        "request.json",
    ]
    assert load_authoring_plan(plan_path).rationale == (
        "Selected Finding minimum_drill_diameter."
    )


def test_plan_command_rejects_the_wrong_request_kind(tmp_path: Path) -> None:
    modification_path = tmp_path / "change.json"
    _write_json(modification_path, json.loads(canonical_json(_modification_request())))
    generation_path = tmp_path / "coupon.json"
    _write_json(generation_path, json.loads(canonical_json(_generation_request())))
    plan_path = tmp_path / "plan.json"

    wrong_generation = _invoke_plan(modification_path, plan_path, kind="generation")
    assert wrong_generation.exit_code == 2, wrong_generation.output
    assert not plan_path.exists()

    wrong_modification = _invoke_plan(generation_path, plan_path, kind="modification")
    assert wrong_modification.exit_code == 2, wrong_modification.output
    assert not plan_path.exists()


def test_plan_command_rejects_a_missing_request(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"

    result = _invoke_plan(tmp_path / "missing.json", plan_path, kind="generation")

    assert result.exit_code == 2, result.output
    assert not plan_path.exists()


def test_plan_command_output_policy(tmp_path: Path) -> None:
    request = _generation_request()
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(request)))
    request_bytes = request_path.read_bytes()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("pre-existing content", encoding="utf-8")

    refused = _invoke_plan(request_path, plan_path, kind="generation")
    assert refused.exit_code == 2, refused.output
    assert "PLAN_OUTPUT_EXISTS" in refused.output
    assert plan_path.read_text(encoding="utf-8") == "pre-existing content"

    replaced = _invoke_plan(request_path, plan_path, kind="generation", overwrite=True)
    assert replaced.exit_code == 0, replaced.output
    expected = mint_authoring_plan(request, approver=APPROVER)
    assert plan_path.read_bytes() == f"{canonical_json(expected)}\n".encode()

    text_path = tmp_path / "plan.txt"
    wrong_suffix = _invoke_plan(request_path, text_path, kind="generation")
    assert wrong_suffix.exit_code == 2, wrong_suffix.output
    assert "AUTHORING_PLAN_FORMAT_ERROR" in wrong_suffix.output
    assert not text_path.exists()

    overlap = _invoke_plan(request_path, request_path, kind="generation")
    assert overlap.exit_code == 2, overlap.output
    assert "PLAN_OUTPUT_OVERLAPS_REQUEST" in overlap.output
    assert request_path.read_bytes() == request_bytes


def test_plan_command_rejects_contract_violating_approver_and_rationale(
    tmp_path: Path,
) -> None:
    request_path = tmp_path / "request.json"
    _write_json(request_path, json.loads(canonical_json(_generation_request())))
    plan_path = tmp_path / "plan.json"

    empty_approver = _invoke_plan(
        request_path, plan_path, kind="generation", approver=""
    )
    assert empty_approver.exit_code == 2, empty_approver.output
    assert "PLAN_MINT_CONTRACT_ERROR" in empty_approver.output
    assert not plan_path.exists()

    long_rationale = _invoke_plan(
        request_path,
        plan_path,
        kind="generation",
        rationale="x" * 501,
    )
    assert long_rationale.exit_code == 2, long_rationale.output
    assert "PLAN_MINT_CONTRACT_ERROR" in long_rationale.output
    assert not plan_path.exists()
