"""End-to-end evidence for one reviewed placement anchor-coordinate revision."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from click.testing import CliRunner

from boardgate.application import (
    ModificationExecutionError,
    ModificationInputError,
    ModificationService,
    ReviewService,
    validate_modification_workspace,
)
from boardgate.application.artifacts import (
    COMPLETE_ARTIFACT_PATHS,
    DETERMINISTIC_ARTIFACT_PATHS,
)
from boardgate.authoring import (
    AppliedPlacementAnchorCoordinateChange,
    ModificationRequest,
    ModificationResult,
    SetPlacementAnchorCoordinate,
)
from boardgate.cli import main
from boardgate.config import load_rule_profile
from boardgate.config.models import RuleProfile
from boardgate.domain.enums import FileType, ReviewStatus
from boardgate.domain.project import PCBProject
from boardgate.domain.serialization import canonical_json
from boardgate.domain.source import ProjectManifest
from boardgate.ingestion import build_manifest, discover_inputs
from boardgate.rules.models import ReviewResult

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "placement_outside_outline"
RULES = ROOT / "rules" / "default.yaml"
SCHEMAS = ROOT / "schemas" / "v1"
TARGET_PATH = "component-placement.csv"


def _project_request(
    project: Path = FIXTURE,
    *,
    target_path: str = TARGET_PATH,
    reference: str = "C1",
    expected_position_mm: float = 25.0,
    new_position_mm: float = 10.0,
) -> ModificationRequest:
    with discover_inputs((project,)) as discovered:
        manifest = build_manifest(discovered)
    source = next(
        item for item in manifest.source_files if item.logical_path == target_path
    )
    assert source.file_type is FileType.PLACEMENT_CSV
    return ModificationRequest(
        schema_version="1.0",
        base_project_id=manifest.project_id,
        operation=SetPlacementAnchorCoordinate(
            schema_version="1.0",
            operation_version="1.0",
            source_logical_path=source.logical_path,
            source_file_id=source.source_file_id,
            source_sha256=source.sha256,
            reference=reference,
            coordinate="x",
            expected_position_mm=expected_position_mm,
            new_position_mm=new_position_mm,
            instruction="Move the confirmed C1 anchor inside the board outline.",
        ),
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
    design_files = tuple(
        f"design/{item.name}" for item in FIXTURE.iterdir() if item.is_file()
    )
    return tuple(
        sorted(
            (
                "evidence/request.json",
                "evidence/result.json",
                *design_files,
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


def _assert_only_requested_payload_changed(workspace: Path) -> None:
    for original in sorted(FIXTURE.iterdir()):
        if not original.is_file():
            continue
        before = original.read_bytes()
        after = (workspace / "design" / original.name).read_bytes()
        if original.name == TARGET_PATH:
            assert after == before.replace(b"C1,25,5,90", b"C1,10,5,90")
        else:
            assert after == before


def _assert_coordinate_rule_resolved(validation_review: ReviewResult) -> None:
    outline_result = next(
        item
        for item in validation_review.rule_results
        if item.rule_id.value == "placement_outside_board_outline"
    )
    assert outline_result.outcome.value == "PASS"
    assert outline_result.coverage.value == "FULL"
    assert validation_review.overall_status is ReviewStatus.READY_FOR_REVIEW
    assert validation_review.findings == ()


def _run_baseline_review(project: Path, output: Path) -> ReviewResult:
    ReviewService().inspect(
        (project,),
        load_rule_profile(RULES),
        output,
    )
    return ReviewResult.model_validate_json(
        (output / "findings.json").read_text(encoding="utf-8")
    )


def _assert_revision_evidence(
    workspace: Path,
    request: ModificationRequest,
) -> ModificationResult:
    request_payload = _read_object(workspace / "evidence" / "request.json")
    result_payload = _read_object(workspace / "evidence" / "result.json")
    _validate_public_schema(request_payload, "modification-request.schema.json")
    _validate_public_schema(result_payload, "modification-result.schema.json")
    admitted_request = ModificationRequest.model_validate_json(
        (workspace / "evidence" / "request.json").read_text(encoding="utf-8")
    )
    modification = ModificationResult.model_validate_json(
        (workspace / "evidence" / "result.json").read_text(encoding="utf-8")
    )
    assert admitted_request == request
    assert modification.base_project_id == request.base_project_id
    assert modification.output_project_id != modification.base_project_id
    assert [
        item.logical_path for item in modification.payload_files if item.changed
    ] == [TARGET_PATH]
    assert modification.operation.input_value_span.start_line == 3
    assert modification.operation.input_value_span == (
        modification.operation.output_value_span
    )
    assert isinstance(
        modification.operation,
        AppliedPlacementAnchorCoordinateChange,
    )
    assert modification.operation.reference == "C1"
    assert modification.operation.coordinate == "x"
    assert modification.operation.old_position_mm == 25.0
    assert modification.operation.new_position_mm == 10.0
    assert len(modification.operation.affected_input_placement_ids) == 1
    assert len(modification.operation.affected_output_placement_ids) == 1
    return modification


def test_base_fixture_has_the_exact_target_review_finding(tmp_path: Path) -> None:
    request = _project_request()
    baseline_review = _run_baseline_review(FIXTURE, tmp_path / "baseline-review")

    assert baseline_review.overall_status is ReviewStatus.NOT_READY_FOR_FABRICATION
    assert len(baseline_review.findings) == 1
    baseline_finding = baseline_review.findings[0]
    assert baseline_finding.rule_id == "placement_outside_board_outline"
    assert any(
        evidence.provenance.source_file_id == request.operation.source_file_id
        for evidence in baseline_finding.evidence
    )


def test_cli_and_service_publish_the_same_complete_validated_revision(
    tmp_path: Path,
) -> None:
    request = _project_request()
    request_path = tmp_path / "request.json"
    request_path.write_text(f"{canonical_json(request)}\n", encoding="utf-8")
    cli_workspace = tmp_path / "cli-revision"

    cli_result = CliRunner().invoke(
        main,
        (
            "modify",
            str(FIXTURE),
            "--request",
            str(request_path),
            "--rules",
            str(RULES),
            "--output",
            str(cli_workspace),
        ),
    )

    assert cli_result.exit_code == 0, cli_result.output
    assert "Revision rev-" in cli_result.output
    assert "validation READY_FOR_REVIEW" in cli_result.output
    assert _published_files(cli_workspace) == _expected_workspace_files()
    validate_modification_workspace(cli_workspace)
    _assert_only_requested_payload_changed(cli_workspace)
    modification = _assert_revision_evidence(cli_workspace, request)

    validation_manifest = ProjectManifest.model_validate_json(
        (cli_workspace / "validation" / "manifest.json").read_text(encoding="utf-8")
    )
    validation_project = PCBProject.model_validate_json(
        (cli_workspace / "validation" / "project.json").read_text(encoding="utf-8")
    )
    validation_review = ReviewResult.model_validate_json(
        (cli_workspace / "validation" / "findings.json").read_text(encoding="utf-8")
    )
    assert validation_manifest.project_id == modification.output_project_id
    assert validation_project.project_id == modification.output_project_id
    target_placements = tuple(
        placement
        for placement in validation_project.components
        if placement.provenance.source_file_id
        == modification.operation.output_source_file_id
    )
    assert tuple(sorted(placement.reference for placement in target_placements)) == (
        "C1",
        "R1",
    )
    moved = next(
        placement for placement in target_placements if placement.reference == "C1"
    )
    assert moved.position.x == 10.0
    assert moved.position.y == 5.0
    _assert_coordinate_rule_resolved(validation_review)
    assert modification.validation.finding_ids == ()

    service_workspace = tmp_path / "service-revision"
    service_run = ModificationService().modify(
        (FIXTURE,),
        request,
        load_rule_profile(RULES),
        service_workspace,
    )
    assert service_run.revision_id == modification.revision_id
    assert service_run.base_project_id == modification.base_project_id
    assert service_run.output_project_id == modification.output_project_id
    assert service_run.overall_status is ReviewStatus.READY_FOR_REVIEW
    assert _published_files(service_workspace) == _expected_workspace_files()
    validate_modification_workspace(service_workspace)
    _assert_only_requested_payload_changed(service_workspace)

    stable_paths = (
        "evidence/request.json",
        "evidence/result.json",
        *(
            f"design/{item.name}"
            for item in sorted(FIXTURE.iterdir())
            if item.is_file()
        ),
        *(f"validation/{item}" for item in DETERMINISTIC_ARTIFACT_PATHS),
    )
    assert {path: (cli_workspace / path).read_bytes() for path in stable_paths} == {
        path: (service_workspace / path).read_bytes() for path in stable_paths
    }


def test_stale_source_request_fails_closed_and_preserves_existing_workspace(
    tmp_path: Path,
) -> None:
    request = _project_request()
    stale_operation = request.operation.model_copy(update={"source_sha256": "0" * 64})
    stale_request = request.model_copy(update={"operation": stale_operation})
    workspace = tmp_path / "existing-revision"
    workspace.mkdir()
    sentinel = workspace / "prior.txt"
    sentinel.write_bytes(b"preserve this prior revision\n")

    with pytest.raises(ModificationInputError) as caught:
        ModificationService().modify(
            (FIXTURE,),
            stale_request,
            load_rule_profile(RULES),
            workspace,
            overwrite=True,
        )

    assert caught.value.code == "MODIFICATION_SOURCE_IDENTITY_MISMATCH"
    assert sentinel.read_bytes() == b"preserve this prior revision\n"
    assert _published_files(workspace) == ("prior.txt",)
    assert not tuple(tmp_path.glob(".existing-revision.staging-*"))
    assert not tuple(tmp_path.glob(".existing-revision.backup-*"))


@pytest.mark.parametrize(
    ("overrides", "code"),
    (
        ({"reference": "R7"}, "AUTHORING_PLACEMENT_REFERENCE_NOT_FOUND"),
        ({"expected_position_mm": 24.0}, "AUTHORING_PRECONDITION_MISMATCH"),
        (
            {"new_position_mm": 10.5},
            "AUTHORING_PLACEMENT_NEW_COORDINATE_PRECISION",
        ),
        ({"new_position_mm": 100.0}, "AUTHORING_PLACEMENT_NEW_COORDINATE_WIDTH"),
    ),
)
def test_cli_rejects_invalid_requests_without_publication(
    tmp_path: Path,
    overrides: dict[str, object],
    code: str,
) -> None:
    invalid_request = _project_request().model_copy(
        update={"operation": _project_request().operation.model_copy(update=overrides)}
    )
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(f"{canonical_json(invalid_request)}\n", encoding="utf-8")
    output = tmp_path / "revision"

    result = CliRunner().invoke(
        main,
        (
            "modify",
            str(FIXTURE),
            "--request",
            str(invalid_path),
            "--rules",
            str(RULES),
            "--output",
            str(output),
        ),
    )

    assert result.exit_code == 2
    assert code in result.output
    assert not output.exists()


def test_cli_rejects_ambiguous_target_references(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    target = project / TARGET_PATH
    target.write_bytes(target.read_bytes().replace(b"R1,5,5", b"C1,5,5"))
    request_path = tmp_path / "request.json"
    request_path.write_text(
        f"{canonical_json(_project_request(project))}\n",
        encoding="utf-8",
    )
    output = tmp_path / "revision"

    result = CliRunner().invoke(
        main,
        (
            "modify",
            str(project),
            "--request",
            str(request_path),
            "--rules",
            str(RULES),
            "--output",
            str(output),
        ),
    )

    assert result.exit_code == 2
    assert "AUTHORING_PLACEMENT_REFERENCE_AMBIGUOUS" in result.output
    assert not output.exists()


def test_cli_rejects_unsupported_token_forms_without_publication(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    target = project / TARGET_PATH
    target.write_bytes(target.read_bytes().replace(b"C1,25,5,90", b"C1,1e2,5,90"))
    request_path = tmp_path / "request.json"
    request_path.write_text(
        f"{canonical_json(_project_request(project))}\n",
        encoding="utf-8",
    )
    output = tmp_path / "revision"

    result = CliRunner().invoke(
        main,
        (
            "modify",
            str(project),
            "--request",
            str(request_path),
            "--rules",
            str(RULES),
            "--output",
            str(output),
        ),
    )

    assert result.exit_code == 3
    assert "AUTHORING_PLACEMENT_COORDINATE_UNSUPPORTED" in result.output
    assert not output.exists()


def test_cli_rejects_non_metric_sources_without_publication(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    target = project / TARGET_PATH
    target.write_bytes(target.read_bytes().replace(b",mm,", b",in,"))
    request_path = tmp_path / "request.json"
    request_path.write_text(
        f"{canonical_json(_project_request(project))}\n",
        encoding="utf-8",
    )
    output = tmp_path / "revision"

    result = CliRunner().invoke(
        main,
        (
            "modify",
            str(project),
            "--request",
            str(request_path),
            "--rules",
            str(RULES),
            "--output",
            str(output),
        ),
    )

    assert result.exit_code == 3
    assert "AUTHORING_PLACEMENT_UNIT_UNSUPPORTED" in result.output
    assert not output.exists()


def test_completed_blocker_review_is_published_with_exit_one(tmp_path: Path) -> None:
    profile = load_rule_profile(RULES)
    blocker_profile = profile.model_copy(
        update={
            "fabrication": profile.fabrication.model_copy(
                update={"min_trace_width": 5.0}
            )
        }
    )
    profile_path = tmp_path / "blocker-profile.json"
    profile_path.write_text(
        f"{canonical_json(blocker_profile)}\n",
        encoding="utf-8",
    )
    request_path = tmp_path / "request.json"
    request_path.write_text(f"{canonical_json(_project_request())}\n", encoding="utf-8")
    output = tmp_path / "blocker-revision"

    result = CliRunner().invoke(
        main,
        (
            "modify",
            str(FIXTURE),
            "--request",
            str(request_path),
            "--rules",
            str(profile_path),
            "--output",
            str(output),
        ),
    )

    assert result.exit_code == 1, result.output
    validate_modification_workspace(output)
    modification = ModificationResult.model_validate_json(
        (output / "evidence" / "result.json").read_text(encoding="utf-8")
    )
    assert modification.validation.overall_status is (
        ReviewStatus.NOT_READY_FOR_FABRICATION
    )
    assert modification.validation.finding_ids


def test_workspace_validator_rejects_fabricated_spans(tmp_path: Path) -> None:
    workspace = tmp_path / "revision"
    ModificationService().modify(
        (FIXTURE,),
        _project_request(),
        load_rule_profile(RULES),
        workspace,
    )

    tampered_workspace = tmp_path / "span-tampered"
    shutil.copytree(workspace, tampered_workspace)
    result_path = tampered_workspace / "evidence" / "result.json"
    modification = ModificationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    span = modification.operation.output_value_span
    assert span.start_byte is not None and span.end_byte is not None
    shifted = span.model_copy(
        update={
            "start_byte": span.start_byte + 1,
            "end_byte": span.end_byte + 1,
        }
    )
    tampered_operation = modification.operation.model_copy(
        update={
            "input_value_span": shifted,
            "output_value_span": shifted,
        }
    )
    tampered_result = modification.model_copy(update={"operation": tampered_operation})
    result_path.write_text(
        f"{canonical_json(tampered_result)}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="token evidence"):
        validate_modification_workspace(tampered_workspace)


def test_analysis_failed_validation_publishes_no_revision_and_preserves_prior(
    tmp_path: Path,
) -> None:
    def unavailable_rules(
        project: PCBProject,
        profile: RuleProfile,
    ) -> ReviewResult:
        del project, profile
        raise RuntimeError("simulated unavailable rule stage")

    output = tmp_path / "existing-revision"
    output.mkdir()
    sentinel = output / "prior.txt"
    sentinel.write_text("preserve prior revision\n", encoding="utf-8")
    service = ModificationService(
        review_service=ReviewService(rule_evaluator=unavailable_rules)
    )

    with pytest.raises(ModificationExecutionError) as caught:
        service.modify(
            (FIXTURE,),
            _project_request(),
            load_rule_profile(RULES),
            output,
            overwrite=True,
        )

    assert caught.value.code == "MODIFICATION_VALIDATION_FAILED"
    assert sentinel.read_text(encoding="utf-8") == "preserve prior revision\n"
    assert _published_files(output) == ("prior.txt",)
    assert not tuple(tmp_path.glob(".existing-revision.staging-*"))
    assert not tuple(tmp_path.glob(".existing-revision.backup-*"))
