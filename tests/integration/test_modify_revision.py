"""End-to-end evidence for one constrained, independently reviewed revision."""

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
from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
)
from boardgate.authoring import (
    ModificationRequest,
    ModificationResult,
    SetExcellonToolDiameter,
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
FIXTURE = ROOT / "tests" / "fixtures" / "drill_too_small"
RULES = ROOT / "rules" / "default.yaml"
SCHEMAS = ROOT / "schemas" / "v1"
TARGET_PATH = "board-plated.drl"


def _project_request(
    project: Path = FIXTURE,
    *,
    target_path: str = TARGET_PATH,
    expected_diameter_mm: float = 0.1,
    new_diameter_mm: float = 0.3,
) -> ModificationRequest:
    with discover_inputs((project,)) as discovered:
        manifest = build_manifest(discovered)
    source = next(
        item for item in manifest.source_files if item.logical_path == target_path
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
            expected_diameter_mm=expected_diameter_mm,
            new_diameter_mm=new_diameter_mm,
            instruction=(
                "Increase the confirmed T01 round-drill diameter to 0.300 mm."
            ),
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
            assert before.count(b"T01C0.100") == 1
            assert after == before.replace(b"T01C0.100", b"T01C0.300")
        else:
            assert after == before


def test_base_fixture_has_the_exact_target_review_finding(tmp_path: Path) -> None:
    request = _project_request()
    baseline_workspace = tmp_path / "baseline-review"
    ReviewService().inspect(
        (FIXTURE,),
        load_rule_profile(RULES),
        baseline_workspace,
    )
    baseline_review = ReviewResult.model_validate_json(
        (baseline_workspace / "findings.json").read_text(encoding="utf-8")
    )

    assert baseline_review.overall_status is ReviewStatus.NOT_READY_FOR_FABRICATION
    assert len(baseline_review.findings) == 1
    baseline_finding = baseline_review.findings[0]
    assert baseline_finding.rule_id == "minimum_drill_diameter"
    assert baseline_finding.evidence[0].provenance.source_file_id == (
        request.operation.source_file_id
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

    request_payload = _read_object(cli_workspace / "evidence" / "request.json")
    result_payload = _read_object(cli_workspace / "evidence" / "result.json")
    _validate_public_schema(request_payload, "modification-request.schema.json")
    _validate_public_schema(result_payload, "modification-result.schema.json")
    admitted_request = ModificationRequest.model_validate_json(
        (cli_workspace / "evidence" / "request.json").read_text(encoding="utf-8")
    )
    modification = ModificationResult.model_validate_json(
        (cli_workspace / "evidence" / "result.json").read_text(encoding="utf-8")
    )
    assert admitted_request == request
    assert modification.base_project_id == request.base_project_id
    assert modification.output_project_id != modification.base_project_id
    assert [
        item.logical_path for item in modification.payload_files if item.changed
    ] == [TARGET_PATH]
    assert modification.operation.input_value_span.start_line == 4
    assert modification.operation.input_value_span == (
        modification.operation.output_value_span
    )
    assert len(modification.operation.affected_input_drill_ids) == 1
    assert len(modification.operation.affected_output_drill_ids) == 1

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
    assert validation_project.drills[0].diameter_mm == pytest.approx(0.3)
    assert validation_review.overall_status is ReviewStatus.READY_FOR_REVIEW
    drill_result = next(
        item
        for item in validation_review.rule_results
        if item.rule_id.value == "minimum_drill_diameter"
    )
    assert drill_result.outcome.value == "PASS"
    assert drill_result.coverage.value == "FULL"
    assert not any(
        finding.rule_id == "minimum_drill_diameter"
        for finding in validation_review.findings
    )
    assert validation_review.findings == ()
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


def test_cli_distinguishes_request_preconditions_from_capability_failures(
    tmp_path: Path,
) -> None:
    invalid_request = _project_request().model_copy(
        update={
            "operation": _project_request().operation.model_copy(
                update={"expected_diameter_mm": 0.2}
            )
        }
    )
    invalid_path = tmp_path / "invalid-precondition.json"
    invalid_path.write_text(
        f"{canonical_json(invalid_request)}\n",
        encoding="utf-8",
    )
    invalid_output = tmp_path / "invalid-precondition-output"
    invalid_result = CliRunner().invoke(
        main,
        (
            "modify",
            str(FIXTURE),
            "--request",
            str(invalid_path),
            "--rules",
            str(RULES),
            "--output",
            str(invalid_output),
        ),
    )
    assert invalid_result.exit_code == 2
    assert "AUTHORING_PRECONDITION_MISMATCH" in invalid_result.output
    assert not invalid_output.exists()

    inch_source = ROOT / "tests" / "fixtures" / "parser" / "excellon" / "inch_hits.drl"
    unsupported_request = _project_request(
        inch_source,
        target_path=inch_source.name,
        expected_diameter_mm=0.254,
        new_diameter_mm=0.3,
    )
    unsupported_path = tmp_path / "unsupported-source.json"
    unsupported_path.write_text(
        f"{canonical_json(unsupported_request)}\n",
        encoding="utf-8",
    )
    unsupported_output = tmp_path / "unsupported-source-output"
    unsupported_result = CliRunner().invoke(
        main,
        (
            "modify",
            str(inch_source),
            "--request",
            str(unsupported_path),
            "--rules",
            str(RULES),
            "--output",
            str(unsupported_output),
        ),
    )
    assert unsupported_result.exit_code == 3
    assert "AUTHORING_EXCELLON_UNIT_UNSUPPORTED" in unsupported_result.output
    assert not unsupported_output.exists()


@pytest.mark.parametrize("control_name", ("request", "rules"))
def test_cli_rejects_control_files_inside_design_inputs(
    tmp_path: Path,
    control_name: str,
) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    outside_request = tmp_path / "request.json"
    outside_request.write_text(
        f"{canonical_json(_project_request())}\n",
        encoding="utf-8",
    )
    request_path = outside_request
    rules_path = RULES
    if control_name == "request":
        request_path = project / "request.json"
        request_path.write_bytes(outside_request.read_bytes())
    else:
        rules_path = project / "rules.yaml"
        rules_path.write_bytes(RULES.read_bytes())
    output = tmp_path / "revision"

    result = CliRunner().invoke(
        main,
        (
            "modify",
            str(project),
            "--request",
            str(request_path),
            "--rules",
            str(rules_path),
            "--output",
            str(output),
        ),
    )

    assert result.exit_code == 2
    assert "MODIFICATION_CONTROL_INSIDE_INPUT" in result.output
    assert not output.exists()


def test_service_rejects_non_design_siblings_before_emission(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    (project / "boardgate.toml").write_text(
        '[review]\noutput = "elsewhere"\n',
        encoding="utf-8",
    )
    request = _project_request(project)
    output = tmp_path / "revision"

    with pytest.raises(ModificationInputError) as caught:
        ModificationService().modify(
            (project,),
            request,
            load_rule_profile(RULES),
            output,
        )

    assert caught.value.code == "MODIFICATION_NON_DESIGN_INPUT"
    assert not output.exists()


def test_workspace_validator_rejects_fabricated_spans_symlinks_and_extra_dirs(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "revision"
    ModificationService().modify(
        (FIXTURE,),
        _project_request(),
        load_rule_profile(RULES),
        workspace,
    )

    span_workspace = tmp_path / "span-tampered"
    shutil.copytree(workspace, span_workspace)
    result_path = span_workspace / "evidence" / "result.json"
    result = ModificationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    span = result.operation.output_value_span
    assert span.start_byte is not None and span.end_byte is not None
    shifted = span.model_copy(
        update={
            "start_byte": span.start_byte + 1,
            "end_byte": span.end_byte + 1,
        }
    )
    tampered_operation = result.operation.model_copy(
        update={
            "input_value_span": shifted,
            "output_value_span": shifted,
        }
    )
    tampered_result = result.model_copy(update={"operation": tampered_operation})
    result_path.write_text(
        f"{canonical_json(tampered_result)}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="token evidence"):
        validate_modification_workspace(span_workspace)

    symlink_workspace = tmp_path / "symlink-tampered"
    shutil.copytree(workspace, symlink_workspace)
    linked_payload = symlink_workspace / "design" / "board-top-copper.gtl"
    linked_payload.unlink()
    linked_payload.symlink_to(FIXTURE / "board-top-copper.gtl")
    with pytest.raises(ValueError, match="symbolic links"):
        validate_modification_workspace(symlink_workspace)

    directory_workspace = tmp_path / "directory-tampered"
    shutil.copytree(workspace, directory_workspace)
    (directory_workspace / "unexpected-empty-directory").mkdir()
    with pytest.raises(ValueError, match="inventory"):
        validate_modification_workspace(directory_workspace)


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
    request_path.write_text(
        f"{canonical_json(_project_request())}\n",
        encoding="utf-8",
    )
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


def test_parser_failure_publishes_no_revision_or_temporary_state(
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

    output = tmp_path / "revision"
    service = ModificationService(parser_executor=fail_parser)

    with pytest.raises(ModificationExecutionError) as caught:
        service.modify(
            (FIXTURE,),
            _project_request(),
            load_rule_profile(RULES),
            output,
        )

    assert caught.value.code == "MODIFICATION_SOURCE_PARSE_FAILED"
    assert not output.exists()
    assert not tuple(tmp_path.glob(".revision.staging-*"))
    assert not tuple(tmp_path.glob(".revision.backup-*"))
