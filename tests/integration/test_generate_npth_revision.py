"""End-to-end evidence for deterministic mixed plated/NPTH generation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from click.testing import CliRunner

from boardgate.application import (
    GenerationExecutionError,
    GenerationService,
    ReviewService,
    validate_generation_workspace,
)
from boardgate.application.artifacts import (
    COMPLETE_ARTIFACT_PATHS,
    DETERMINISTIC_ARTIFACT_PATHS,
    deterministic_model_json,
)
from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
)
from boardgate.authoring import (
    AppliedTwoLayerCouponWithNpthGeneration,
    GenerateTwoLayerCouponWithNpth,
    GenerationRequest,
    GenerationResult,
)
from boardgate.authoring.coupon import (
    NON_PLATED_DRILL_PATH,
    NPTH_GENERATION_PAYLOAD_PATHS,
    PLATED_DRILL_PATH,
)
from boardgate.authoring.identifiers import (
    generation_id,
    generation_operation_sha256,
    generation_request_sha256,
)
from boardgate.cli import main
from boardgate.config import load_rule_profile
from boardgate.config.models import RuleProfile
from boardgate.domain.drill import DrillSlot
from boardgate.domain.enums import Plating, ReviewStatus
from boardgate.domain.geometry import Point
from boardgate.domain.identifiers import source_file_id
from boardgate.domain.project import PCBProject
from boardgate.domain.serialization import canonical_json
from boardgate.domain.source import ProjectManifest
from boardgate.rules.models import ReviewResult, RuleCoverage, RuleOutcome, RuleResult

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "rules" / "default.yaml"
SCHEMAS = ROOT / "schemas" / "v1"


def _request(*, first_npth_diameter_mm: float = 0.6) -> GenerationRequest:
    return GenerationRequest.model_validate_json(
        json.dumps(
            {
                "schema_version": "1.0",
                "operation": {
                    "schema_version": "1.0",
                    "kind": "generate_two_layer_coupon_with_npth",
                    "operation_version": "1.0",
                    "board_width_mm": 20.0,
                    "board_height_mm": 15.0,
                    "plated_holes": [
                        {
                            "schema_version": "1.0",
                            "x_mm": 5.0,
                            "y_mm": 5.0,
                            "drill_diameter_mm": 0.4,
                            "pad_diameter_mm": 1.0,
                        },
                        {
                            "schema_version": "1.0",
                            "x_mm": 15.0,
                            "y_mm": 10.0,
                            "drill_diameter_mm": 0.5,
                            "pad_diameter_mm": 1.0,
                        },
                    ],
                    "non_plated_holes": [
                        {
                            "schema_version": "1.0",
                            "x_mm": 10.0,
                            "y_mm": 5.0,
                            "drill_diameter_mm": first_npth_diameter_mm,
                        },
                        {
                            "schema_version": "1.0",
                            "x_mm": 10.0,
                            "y_mm": 10.0,
                            "drill_diameter_mm": 0.8,
                        },
                    ],
                    "traces": [
                        {
                            "schema_version": "1.0",
                            "x1_mm": 5.0,
                            "y1_mm": 5.0,
                            "x2_mm": 15.0,
                            "y2_mm": 10.0,
                            "width_mm": 0.25,
                            "copper_layers": "both",
                        },
                        {
                            "schema_version": "1.0",
                            "x1_mm": 1.0,
                            "y1_mm": 1.0,
                            "x2_mm": 19.0,
                            "y2_mm": 1.0,
                            "width_mm": 0.5,
                            "copper_layers": "top",
                        },
                    ],
                    "instruction": (
                        "Generate a two-layer coupon with explicit plated and "
                        "non-plated drills."
                    ),
                },
            }
        )
    )


def _published_files(root: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            item.relative_to(root).as_posix()
            for item in root.rglob("*")
            if item.is_file()
        )
    )


def _expected_workspace_files() -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                "evidence/request.json",
                "evidence/result.json",
                *(f"design/{item}" for item in NPTH_GENERATION_PAYLOAD_PATHS),
                *(f"validation/{item}" for item in COMPLETE_ARTIFACT_PATHS),
            )
        )
    )


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _validate_public_schema(payload: dict[str, Any], schema_name: str) -> None:
    schema = _read_object(SCHEMAS / schema_name)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(payload)


def _rule(review: ReviewResult, rule_id: str) -> RuleResult:
    return next(result for result in review.rule_results if result.rule_id == rule_id)


def _source_id(result: GenerationResult, logical_path: str) -> str:
    evidence = next(
        item for item in result.payload_files if item.logical_path == logical_path
    )
    return source_file_id(evidence.logical_path, evidence.sha256)


def _assert_exact_drill_population(
    project: PCBProject,
    *,
    source_id: str,
    expected: tuple[tuple[float, float, float], ...],
    expected_ids: tuple[str, ...],
    plating: Plating,
) -> None:
    drills = tuple(
        drill
        for drill in project.drills
        if drill.provenance.source_file_id == source_id
    )
    assert tuple(sorted(drill.drill_id for drill in drills)) == expected_ids
    actual = tuple(
        sorted(
            (drill.position.x, drill.position.y, drill.diameter_mm) for drill in drills
        )
    )
    assert len(actual) == len(expected)
    for actual_geometry, expected_geometry in zip(
        actual,
        sorted(expected),
        strict=True,
    ):
        assert actual_geometry == pytest.approx(expected_geometry)
    assert {drill.plating for drill in drills} == {plating}


def test_cli_and_service_publish_the_same_complete_validated_npth_generation(  # noqa: PLR0915
    tmp_path: Path,
) -> None:
    request = _request()
    request_path = tmp_path / "request.json"
    request_path.write_text(f"{canonical_json(request)}\n", encoding="utf-8")
    cli_workspace = tmp_path / "cli-generation"

    cli_result = CliRunner().invoke(
        main,
        (
            "generate",
            "--request",
            str(request_path),
            "--rules",
            str(RULES),
            "--output",
            str(cli_workspace),
        ),
    )

    assert cli_result.exit_code == 0, cli_result.output
    assert "Generation gen-" in cli_result.output
    assert "validation READY_FOR_REVIEW" in cli_result.output
    assert _published_files(cli_workspace) == _expected_workspace_files()
    validate_generation_workspace(cli_workspace)

    request_payload = _read_object(cli_workspace / "evidence" / "request.json")
    result_payload = _read_object(cli_workspace / "evidence" / "result.json")
    _validate_public_schema(request_payload, "generation-request.schema.json")
    _validate_public_schema(result_payload, "generation-result.schema.json")
    admitted_request = GenerationRequest.model_validate_json(
        (cli_workspace / "evidence" / "request.json").read_text(encoding="utf-8")
    )
    generation = GenerationResult.model_validate_json(
        (cli_workspace / "evidence" / "result.json").read_text(encoding="utf-8")
    )
    assert admitted_request == request
    assert isinstance(request.operation, GenerateTwoLayerCouponWithNpth)
    assert generation.operation.kind == "generate_two_layer_coupon_with_npth"
    assert generation.operation.plated_hole_count == 2
    assert generation.operation.plated_tool_count == 2
    assert generation.operation.non_plated_hole_count == 2
    assert generation.operation.non_plated_tool_count == 2
    assert generation.operation.trace_count == 2
    assert [item.logical_path for item in generation.payload_files] == list(
        NPTH_GENERATION_PAYLOAD_PATHS
    )

    manifest = ProjectManifest.model_validate_json(
        (cli_workspace / "validation" / "manifest.json").read_text(encoding="utf-8")
    )
    project = PCBProject.model_validate_json(
        (cli_workspace / "validation" / "project.json").read_text(encoding="utf-8")
    )
    review = ReviewResult.model_validate_json(
        (cli_workspace / "validation" / "findings.json").read_text(encoding="utf-8")
    )
    assert manifest.project_id == generation.output_project_id
    assert project.project_id == generation.output_project_id
    assert tuple(source.logical_path for source in manifest.source_files) == (
        NPTH_GENERATION_PAYLOAD_PATHS
    )
    assert len(project.drills) == 4
    plated_source_id = _source_id(generation, PLATED_DRILL_PATH)
    non_plated_source_id = _source_id(generation, NON_PLATED_DRILL_PATH)
    _assert_exact_drill_population(
        project,
        source_id=plated_source_id,
        expected=tuple(
            (hole.x_mm, hole.y_mm, hole.drill_diameter_mm)
            for hole in request.operation.plated_holes
        ),
        expected_ids=generation.operation.plated_drill_ids,
        plating=Plating.PLATED,
    )
    _assert_exact_drill_population(
        project,
        source_id=non_plated_source_id,
        expected=tuple(
            (hole.x_mm, hole.y_mm, hole.drill_diameter_mm)
            for hole in request.operation.non_plated_holes
        ),
        expected_ids=generation.operation.non_plated_drill_ids,
        plating=Plating.NON_PLATED,
    )

    assert review.overall_status is ReviewStatus.READY_FOR_REVIEW
    assert review.findings == ()
    assert generation.validation.finding_ids == ()
    diameter = _rule(review, "minimum_drill_diameter")
    assert diameter.outcome is RuleOutcome.PASS
    assert diameter.coverage is RuleCoverage.FULL
    assert diameter.evaluated_object_count == 4
    assert diameter.applicable_object_count == 4
    annular = _rule(review, "minimum_annular_ring")
    assert annular.outcome is RuleOutcome.PASS
    assert annular.coverage is RuleCoverage.FULL
    assert annular.evaluated_object_count == 4
    assert annular.applicable_object_count == 4
    assert annular.findings == ()

    service_workspace = tmp_path / "service-generation"
    service_run = GenerationService().generate(
        request,
        load_rule_profile(RULES),
        service_workspace,
    )
    assert service_run.generation_id == generation.generation_id
    assert service_run.output_project_id == generation.output_project_id
    assert service_run.overall_status is ReviewStatus.READY_FOR_REVIEW
    assert _published_files(service_workspace) == _expected_workspace_files()
    validate_generation_workspace(service_workspace)

    stable_paths = (
        "evidence/request.json",
        "evidence/result.json",
        *(f"design/{item}" for item in NPTH_GENERATION_PAYLOAD_PATHS),
        *(f"validation/{item}" for item in DETERMINISTIC_ARTIFACT_PATHS),
    )
    assert {path: (cli_workspace / path).read_bytes() for path in stable_paths} == {
        path: (service_workspace / path).read_bytes() for path in stable_paths
    }


def test_undersized_npth_is_reviewed_and_published_as_a_blocker(
    tmp_path: Path,
) -> None:
    request = _request(first_npth_diameter_mm=0.1)
    request_path = tmp_path / "request.json"
    request_path.write_text(f"{canonical_json(request)}\n", encoding="utf-8")
    output = tmp_path / "generation"

    result = CliRunner().invoke(
        main,
        (
            "generate",
            "--request",
            str(request_path),
            "--rules",
            str(RULES),
            "--output",
            str(output),
        ),
    )

    assert result.exit_code == 1, result.output
    assert "validation NOT_READY_FOR_FABRICATION" in result.output
    validate_generation_workspace(output)
    generation = GenerationResult.model_validate_json(
        (output / "evidence" / "result.json").read_text(encoding="utf-8")
    )
    review = ReviewResult.model_validate_json(
        (output / "validation" / "findings.json").read_text(encoding="utf-8")
    )
    diameter = _rule(review, "minimum_drill_diameter")
    assert diameter.outcome is RuleOutcome.FINDINGS
    assert diameter.coverage is RuleCoverage.FULL
    assert diameter.evaluated_object_count == 4
    assert diameter.applicable_object_count == 4
    assert len(diameter.findings) == 1
    finding = diameter.findings[0]
    assert finding.measurement is not None
    assert finding.measurement.actual == pytest.approx(0.1)
    assert finding.measurement.required == pytest.approx(0.2)
    assert finding.evidence[0].provenance.source_file_id == _source_id(
        generation,
        NON_PLATED_DRILL_PATH,
    )
    assert review.overall_status is ReviewStatus.NOT_READY_FOR_FABRICATION
    assert generation.validation.finding_ids == (finding.finding_id,)

    annular = _rule(review, "minimum_annular_ring")
    assert annular.outcome is RuleOutcome.PASS
    assert annular.coverage is RuleCoverage.FULL
    assert annular.evaluated_object_count == 4
    assert annular.applicable_object_count == 4
    assert annular.findings == ()


def test_existing_workspace_is_preserved_without_overwrite(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(f"{canonical_json(_request())}\n", encoding="utf-8")
    output = tmp_path / "generation"
    output.mkdir()
    sentinel = output / "prior.txt"
    sentinel.write_text("preserve prior generation\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        (
            "generate",
            "--request",
            str(request_path),
            "--rules",
            str(RULES),
            "--output",
            str(output),
        ),
    )

    assert result.exit_code == 2
    assert sentinel.read_text(encoding="utf-8") == "preserve prior generation\n"
    assert _published_files(output) == ("prior.txt",)


def test_failed_review_publishes_no_generation_and_preserves_prior(
    tmp_path: Path,
) -> None:
    def unavailable_rules(
        project: PCBProject,
        profile: RuleProfile,
    ) -> ReviewResult:
        del project, profile
        raise RuntimeError("simulated unavailable rule stage")

    output = tmp_path / "existing-generation"
    output.mkdir()
    sentinel = output / "prior.txt"
    sentinel.write_text("preserve prior generation\n", encoding="utf-8")
    service = GenerationService(
        review_service=ReviewService(rule_evaluator=unavailable_rules)
    )

    with pytest.raises(GenerationExecutionError) as caught:
        service.generate(
            _request(),
            load_rule_profile(RULES),
            output,
            overwrite=True,
        )

    assert caught.value.code == "GENERATION_VALIDATION_FAILED"
    assert sentinel.read_text(encoding="utf-8") == "preserve prior generation\n"
    assert _published_files(output) == ("prior.txt",)
    assert not tuple(tmp_path.glob(".existing-generation.staging-*"))
    assert not tuple(tmp_path.glob(".existing-generation.backup-*"))


def test_parser_failure_publishes_no_generation_or_temporary_state(
    tmp_path: Path,
) -> None:
    def fail_parser(job: ParserJob) -> ParserExecution:
        return ParserExecution(
            file_type=job.file_type,
            source_file_id=job.source_file_id,
            failure=ParserFailure(
                code="PARSER_TEST_FAILURE",
                detail="simulated bounded parser failure",
            ),
        )

    output = tmp_path / "generation"
    service = GenerationService(parser_executor=fail_parser)

    with pytest.raises(GenerationExecutionError) as caught:
        service.generate(
            _request(),
            load_rule_profile(RULES),
            output,
        )

    assert caught.value.code == "GENERATION_REPARSE_FAILED"
    assert not output.exists()
    assert not tuple(tmp_path.glob(".generation.staging-*"))
    assert not tuple(tmp_path.glob(".generation.backup-*"))


def test_workspace_validator_rejects_tampered_npth_evidence_and_payloads(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "generation"
    GenerationService().generate(
        _request(),
        load_rule_profile(RULES),
        workspace,
    )

    evidence_workspace = tmp_path / "evidence-tampered"
    shutil.copytree(workspace, evidence_workspace)
    result_path = evidence_workspace / "evidence" / "result.json"
    generation = GenerationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    tampered_result = generation.model_copy(
        update={
            "operation": generation.operation.model_copy(
                update={"trace_count": generation.operation.trace_count + 1}
            )
        }
    )
    result_path.write_text(
        f"{canonical_json(tampered_result)}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="applied generation evidence"):
        validate_generation_workspace(evidence_workspace)

    marker_workspace = tmp_path / "marker-tampered"
    shutil.copytree(workspace, marker_workspace)
    npth_path = marker_workspace / "design" / NON_PLATED_DRILL_PATH
    payload = npth_path.read_bytes()
    assert payload.count(b";TYPE=NON_PLATED") == 1
    npth_path.write_bytes(payload.replace(b";TYPE=NON_PLATED", b";TYPE=NOT_PLATED"))
    with pytest.raises(ValueError, match="payload digest"):
        validate_generation_workspace(marker_workspace)

    inventory_workspace = tmp_path / "inventory-tampered"
    shutil.copytree(workspace, inventory_workspace)
    (inventory_workspace / "design" / "unexpected.txt").write_text(
        "not contracted\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="inventory"):
        validate_generation_workspace(inventory_workspace)

    symlink_workspace = tmp_path / "symlink-tampered"
    shutil.copytree(workspace, symlink_workspace)
    linked_payload = symlink_workspace / "design" / NON_PLATED_DRILL_PATH
    linked_payload.unlink()
    linked_payload.symlink_to(workspace / "design" / NON_PLATED_DRILL_PATH)
    with pytest.raises(ValueError, match="symbolic links"):
        validate_generation_workspace(symlink_workspace)


def test_workspace_validator_rejects_tampered_applied_tool_and_drill_ids(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "generation"
    GenerationService().generate(
        _request(),
        load_rule_profile(RULES),
        workspace,
    )

    tool_workspace = tmp_path / "tool-evidence-tampered"
    shutil.copytree(workspace, tool_workspace)
    result_path = tool_workspace / "evidence" / "result.json"
    generation = GenerationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    assert isinstance(
        generation.operation,
        AppliedTwoLayerCouponWithNpthGeneration,
    )
    tampered_result = generation.model_copy(
        update={
            "operation": generation.operation.model_copy(
                update={"non_plated_tool_count": 1}
            )
        }
    )
    result_path.write_text(
        f"{canonical_json(tampered_result)}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="applied generation evidence"):
        validate_generation_workspace(tool_workspace)

    id_workspace = tmp_path / "drill-id-tampered"
    shutil.copytree(workspace, id_workspace)
    result_path = id_workspace / "evidence" / "result.json"
    generation = GenerationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    assert isinstance(
        generation.operation,
        AppliedTwoLayerCouponWithNpthGeneration,
    )
    fake_ids = tuple(
        sorted(
            (
                "drill-0000000000000000",
                *generation.operation.non_plated_drill_ids[1:],
            )
        )
    )
    tampered_result = generation.model_copy(
        update={
            "operation": generation.operation.model_copy(
                update={"non_plated_drill_ids": fake_ids}
            )
        }
    )
    result_path.write_text(
        f"{canonical_json(tampered_result)}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="drill IDs"):
        validate_generation_workspace(id_workspace)


@pytest.mark.parametrize("geometry", ("trace", "plated_pad"))
def test_workspace_validator_binds_request_geometry_to_design_bytes(
    tmp_path: Path,
    geometry: str,
) -> None:
    workspace = tmp_path / "generation"
    GenerationService().generate(
        _request(),
        load_rule_profile(RULES),
        workspace,
    )
    request_path = workspace / "evidence" / "request.json"
    result_path = workspace / "evidence" / "result.json"
    request = GenerationRequest.model_validate_json(
        request_path.read_text(encoding="utf-8")
    )
    generation = GenerationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    assert isinstance(request.operation, GenerateTwoLayerCouponWithNpth)
    if geometry == "trace":
        traces = list(request.operation.traces)
        traces[0] = traces[0].model_copy(update={"x2_mm": 14.0})
        changed_operation = request.operation.model_copy(
            update={"traces": tuple(traces)}
        )
    else:
        plated_holes = list(request.operation.plated_holes)
        plated_holes[0] = plated_holes[0].model_copy(update={"pad_diameter_mm": 1.1})
        changed_operation = request.operation.model_copy(
            update={"plated_holes": tuple(plated_holes)}
        )
    changed_request = request.model_copy(update={"operation": changed_operation})
    operation_digest = generation_operation_sha256(changed_operation)
    changed_result = generation.model_copy(
        update={
            "request_sha256": generation_request_sha256(changed_request),
            "operation_sha256": operation_digest,
            "generation_id": generation_id(
                operation_digest=operation_digest,
                output_project_id=generation.output_project_id,
            ),
        }
    )
    request_path.write_text(
        f"{canonical_json(changed_request)}\n",
        encoding="utf-8",
    )
    result_path.write_text(
        f"{canonical_json(changed_result)}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="deterministic design payload evidence"):
        validate_generation_workspace(workspace)


def test_workspace_validator_rejects_tampered_project_drill_semantics(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "generation"
    GenerationService().generate(
        _request(),
        load_rule_profile(RULES),
        workspace,
    )

    plating_workspace = tmp_path / "plating-tampered"
    shutil.copytree(workspace, plating_workspace)
    project_path = plating_workspace / "validation" / "project.json"
    project = PCBProject.model_validate_json(project_path.read_text(encoding="utf-8"))
    generation = GenerationResult.model_validate_json(
        (plating_workspace / "evidence" / "result.json").read_text(encoding="utf-8")
    )
    npth_source_id = _source_id(generation, NON_PLATED_DRILL_PATH)
    tampered_drills = tuple(
        drill.model_copy(update={"plating": Plating.PLATED})
        if drill.provenance.source_file_id == npth_source_id
        else drill
        for drill in project.drills
    )
    project_path.write_text(
        deterministic_model_json(
            project.model_copy(update={"drills": tampered_drills})
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="plating evidence"):
        validate_generation_workspace(plating_workspace)

    slot_workspace = tmp_path / "slot-tampered"
    shutil.copytree(workspace, slot_workspace)
    project_path = slot_workspace / "validation" / "project.json"
    project = PCBProject.model_validate_json(project_path.read_text(encoding="utf-8"))
    drill = project.drills[0]
    slot = DrillSlot(
        slot_id="slot-generated-workspace-tamper",
        start=drill.position,
        end=Point(x=drill.position.x + 1.0, y=drill.position.y),
        width_mm=drill.diameter_mm,
        tool_code=drill.tool_code,
        plating=drill.plating,
        provenance=drill.provenance,
    )
    project_path.write_text(
        deterministic_model_json(project.model_copy(update={"drill_slots": (slot,)})),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="contains drill slots"):
        validate_generation_workspace(slot_workspace)
