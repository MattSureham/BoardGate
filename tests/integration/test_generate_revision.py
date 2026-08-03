"""End-to-end evidence for one deterministic, independently reviewed generation."""

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
)
from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
)
from boardgate.authoring import GenerationRequest, GenerationResult
from boardgate.authoring.coupon import GENERATION_PAYLOAD_PATHS
from boardgate.cli import main
from boardgate.config import load_rule_profile
from boardgate.config.models import RuleProfile
from boardgate.domain.enums import ReviewStatus
from boardgate.domain.project import PCBProject
from boardgate.domain.serialization import canonical_json
from boardgate.domain.source import ProjectManifest
from boardgate.rules.models import ReviewResult

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "rules" / "default.yaml"
SCHEMAS = ROOT / "schemas" / "v1"


def _request() -> GenerationRequest:
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
                        {
                            "schema_version": "1.0",
                            "x_mm": 15.0,
                            "y_mm": 10.0,
                            "drill_diameter_mm": 0.5,
                            "pad_diameter_mm": 1.0,
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
                    "instruction": "Generate a two-layer coupon with two plated holes.",
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
                *(f"design/{item}" for item in GENERATION_PAYLOAD_PATHS),
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


def test_cli_and_service_publish_the_same_complete_validated_generation(
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
    assert generation.operation.hole_count == 2
    assert generation.operation.tool_count == 2
    assert generation.operation.trace_count == 2
    assert len(generation.operation.drill_ids) == 2
    assert [item.logical_path for item in generation.payload_files] == list(
        GENERATION_PAYLOAD_PATHS
    )

    validation_manifest = ProjectManifest.model_validate_json(
        (cli_workspace / "validation" / "manifest.json").read_text(encoding="utf-8")
    )
    validation_project = PCBProject.model_validate_json(
        (cli_workspace / "validation" / "project.json").read_text(encoding="utf-8")
    )
    validation_review = ReviewResult.model_validate_json(
        (cli_workspace / "validation" / "findings.json").read_text(encoding="utf-8")
    )
    assert validation_manifest.project_id == generation.output_project_id
    assert validation_project.project_id == generation.output_project_id
    assert len(validation_project.drills) == 2
    assert validation_review.overall_status is ReviewStatus.READY_FOR_REVIEW
    assert validation_review.findings == ()
    assert generation.validation.finding_ids == ()

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
        *(f"design/{item}" for item in GENERATION_PAYLOAD_PATHS),
        *(f"validation/{item}" for item in DETERMINISTIC_ARTIFACT_PATHS),
    )
    assert {path: (cli_workspace / path).read_bytes() for path in stable_paths} == {
        path: (service_workspace / path).read_bytes() for path in stable_paths
    }


def test_invalid_requirements_fail_closed_without_a_workspace(tmp_path: Path) -> None:
    invalid_payload = json.loads(canonical_json(_request()))
    invalid_payload["operation"]["holes"][1]["x_mm"] = 5.2
    invalid_payload["operation"]["holes"][1]["y_mm"] = 5.0
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(invalid_payload), encoding="utf-8")
    output = tmp_path / "generation"

    result = CliRunner().invoke(
        main,
        (
            "generate",
            "--request",
            str(invalid_path),
            "--rules",
            str(RULES),
            "--output",
            str(output),
        ),
    )

    assert result.exit_code == 2
    assert "GENERATION_REQUEST_VALIDATION_ERROR" in result.output
    assert not output.exists()


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


def test_completed_blocker_review_is_published_with_exit_one(tmp_path: Path) -> None:
    profile = load_rule_profile(RULES)
    blocker_profile = profile.model_copy(
        update={
            "fabrication": profile.fabrication.model_copy(
                update={"min_drill_diameter": 0.4}
            )
        }
    )
    profile_path = tmp_path / "blocker-profile.json"
    profile_path.write_text(
        f"{canonical_json(blocker_profile)}\n",
        encoding="utf-8",
    )
    request_path = tmp_path / "request.json"
    request_path.write_text(f"{canonical_json(_request())}\n", encoding="utf-8")
    output = tmp_path / "blocker-generation"

    result = CliRunner().invoke(
        main,
        (
            "generate",
            "--request",
            str(request_path),
            "--rules",
            str(profile_path),
            "--output",
            str(output),
        ),
    )

    assert result.exit_code == 1, result.output
    validate_generation_workspace(output)
    generation = GenerationResult.model_validate_json(
        (output / "evidence" / "result.json").read_text(encoding="utf-8")
    )
    assert generation.validation.overall_status is (
        ReviewStatus.NOT_READY_FOR_FABRICATION
    )
    assert generation.validation.finding_ids


def test_failed_validation_publishes_no_generation_and_preserves_prior(
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


def test_workspace_validator_rejects_tampered_evidence_symlinks_and_extra_dirs(
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
    result = GenerationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    tampered_result = result.model_copy(
        update={
            "operation": result.operation.model_copy(
                update={"trace_count": result.operation.trace_count + 1}
            )
        }
    )
    result_path.write_text(
        f"{canonical_json(tampered_result)}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="applied generation evidence"):
        validate_generation_workspace(evidence_workspace)

    symlink_workspace = tmp_path / "symlink-tampered"
    shutil.copytree(workspace, symlink_workspace)
    linked_payload = symlink_workspace / "design" / GENERATION_PAYLOAD_PATHS[0]
    linked_payload.unlink()
    linked_payload.symlink_to(workspace / "design" / GENERATION_PAYLOAD_PATHS[0])
    with pytest.raises(ValueError, match="symbolic links"):
        validate_generation_workspace(symlink_workspace)

    directory_workspace = tmp_path / "directory-tampered"
    shutil.copytree(workspace, directory_workspace)
    (directory_workspace / "unexpected-empty-directory").mkdir()
    with pytest.raises(ValueError, match="inventory"):
        validate_generation_workspace(directory_workspace)
