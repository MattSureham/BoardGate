"""Phase 9 complete-review CLI acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from click.testing import CliRunner, Result

import boardgate.cli as cli_module
from boardgate.application import ReviewService
from boardgate.config.models import RuleProfile
from boardgate.domain.enums import ReviewStatus
from boardgate.domain.project import PCBProject
from boardgate.domain.source import ProjectManifest
from boardgate.ingestion.discovery import DiscoveredProject

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
RULES = ROOT / "rules" / "default.yaml"
SCHEMAS = ROOT / "schemas" / "v1"

DETERMINISTIC_ARTIFACTS = (
    "manifest.json",
    "project.json",
    "findings.json",
    "report.md",
    "preview.svg",
)
COMPLETE_ARTIFACTS = (*DETERMINISTIC_ARTIFACTS, "logs/run.jsonl")
JSON_ARTIFACT_SCHEMAS = {
    "manifest.json": "manifest.schema.json",
    "project.json": "project.schema.json",
    "findings.json": "findings.schema.json",
}
REQUIRED_REPORT_HEADINGS = (
    "# PCB Manufacturing Review",
    "## Executive Summary",
    "## Input Files",
    "## Project Interpretation",
    "## Blockers",
    "## High-Risk Findings",
    "## Requires Human Confirmation",
    "## Optimization Suggestions",
    "## Rules Executed",
    "## Rules Not Executed",
    "## Parser and Analysis Limitations",
    "## Evidence Index",
)


def invoke_inspect(*arguments: str) -> Result:
    return CliRunner().invoke(cli_module.main, ["inspect", *arguments])


def published_files(output: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            path.relative_to(output).as_posix()
            for path in output.rglob("*")
            if path.is_file()
        )
    )


def read_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def load_schema(name: str) -> dict[str, Any]:
    schema = read_json(SCHEMAS / name)
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def validate_complete_output(
    output: Path,
    *,
    expected_status: ReviewStatus,
    expected_finding_count: int,
) -> dict[str, Any]:
    assert published_files(output) == tuple(sorted(COMPLETE_ARTIFACTS))

    payloads: dict[str, dict[str, Any]] = {}
    for artifact, schema_name in JSON_ARTIFACT_SCHEMAS.items():
        payload = read_json(output / artifact)
        jsonschema.Draft202012Validator(load_schema(schema_name)).validate(payload)
        payloads[artifact] = payload

    findings = payloads["findings.json"]
    assert findings["overall_status"] == expected_status.value
    finding_items = findings["findings"]
    assert isinstance(finding_items, list)
    assert len(finding_items) == expected_finding_count
    finding_schema = load_schema("finding.schema.json")
    for finding in finding_items:
        jsonschema.Draft202012Validator(finding_schema).validate(finding)

    project_id = payloads["manifest.json"]["project_id"]
    assert payloads["project.json"]["project_id"] == project_id
    assert findings["project_id"] == project_id

    report = (output / "report.md").read_text(encoding="utf-8")
    for heading in REQUIRED_REPORT_HEADINGS:
        assert heading in report
    assert f"Overall status: **{expected_status.value}**" in report

    svg = (output / "preview.svg").read_text(encoding="utf-8")
    for finding in finding_items:
        finding_id = finding["finding_id"]
        assert finding_id in report
        assert f'data-finding-id="{finding_id}"' in svg

    run_event_schema = load_schema("run-log-event.schema.json")
    log_payload = (output / "logs/run.jsonl").read_text(encoding="utf-8")
    assert log_payload.endswith("\n")
    log_lines = log_payload.splitlines()
    assert log_lines
    events = [json.loads(line) for line in log_lines]
    for event in events:
        jsonschema.Draft202012Validator(run_event_schema).validate(event)
        assert event["project_id"] == project_id
    assert len({event["run_id"] for event in events}) == 1
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    return findings


@pytest.mark.parametrize(
    ("fixture_name", "expected_status", "expected_finding_count"),
    (
        ("valid_minimal_board", ReviewStatus.READY_FOR_REVIEW, 0),
        ("copper_too_close_to_edge", ReviewStatus.READY_FOR_REVIEW, 2),
    ),
)
def test_normative_fixture_command_publishes_schema_valid_complete_review(
    tmp_path: Path,
    fixture_name: str,
    expected_status: ReviewStatus,
    expected_finding_count: int,
) -> None:
    output = tmp_path / fixture_name

    result = invoke_inspect(
        str(FIXTURES / fixture_name),
        "--rules",
        str(RULES),
        "--output",
        str(output),
    )

    assert result.exit_code == 0, result.output
    findings = validate_complete_output(
        output,
        expected_status=expected_status,
        expected_finding_count=expected_finding_count,
    )
    assert f"Review {findings['project_id']}: {expected_status.value}" in result.output


def test_repeated_cli_review_keeps_first_five_bytes_stable_and_log_run_varying(
    tmp_path: Path,
) -> None:
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    common_arguments = (
        str(FIXTURES / "valid_minimal_board"),
        "--rules",
        str(RULES),
    )

    first = invoke_inspect(*common_arguments, "--output", str(first_output))
    second = invoke_inspect(*common_arguments, "--output", str(second_output))

    assert first.exit_code == second.exit_code == 0
    assert {
        artifact: (first_output / artifact).read_bytes()
        for artifact in DETERMINISTIC_ARTIFACTS
    } == {
        artifact: (second_output / artifact).read_bytes()
        for artifact in DETERMINISTIC_ARTIFACTS
    }
    assert (first_output / "logs/run.jsonl").read_bytes() != (
        second_output / "logs/run.jsonl"
    ).read_bytes()


def blocker_edge_profile(tmp_path: Path) -> Path:
    original = RULES.read_text(encoding="utf-8")
    warning_setting = (
        "  minimum_copper_to_edge:\n"
        '    version: "1.0"\n'
        "    enabled: true\n"
        "    severity: warning\n"
    )
    blocker_setting = warning_setting.replace("severity: warning", "severity: blocker")
    assert original.count(warning_setting) == 1
    profile = tmp_path / "blocker-edge.yaml"
    profile.write_text(
        original.replace(warning_setting, blocker_setting),
        encoding="utf-8",
    )
    return profile


def test_fail_on_blocker_changes_exit_code_without_suppressing_artifacts(
    tmp_path: Path,
) -> None:
    profile = blocker_edge_profile(tmp_path)
    fixture = FIXTURES / "copper_too_close_to_edge"
    none_output = tmp_path / "none"
    blocker_output = tmp_path / "blocker"

    none_result = invoke_inspect(
        str(fixture),
        "--rules",
        str(profile),
        "--output",
        str(none_output),
        "--fail-on",
        "none",
    )
    blocker_result = invoke_inspect(
        str(fixture),
        "--rules",
        str(profile),
        "--output",
        str(blocker_output),
        "--fail-on",
        "blocker",
    )

    assert none_result.exit_code == 0, none_result.output
    assert blocker_result.exit_code == 1, blocker_result.output
    none_review = validate_complete_output(
        none_output,
        expected_status=ReviewStatus.NOT_READY_FOR_FABRICATION,
        expected_finding_count=2,
    )
    blocker_review = validate_complete_output(
        blocker_output,
        expected_status=ReviewStatus.NOT_READY_FOR_FABRICATION,
        expected_finding_count=2,
    )
    assert all(finding["severity"] == "BLOCKER" for finding in none_review["findings"])
    assert {
        artifact: (none_output / artifact).read_bytes()
        for artifact in DETERMINISTIC_ARTIFACTS
    } == {
        artifact: (blocker_output / artifact).read_bytes()
        for artifact in DETERMINISTIC_ARTIFACTS
    }
    assert none_review == blocker_review


@pytest.mark.parametrize(
    ("log_level", "emits_summary"),
    (
        ("error", False),
        ("warning", False),
        ("info", True),
        ("debug", True),
    ),
)
def test_log_level_controls_success_console_summary(
    tmp_path: Path,
    log_level: str,
    *,
    emits_summary: bool,
) -> None:
    output = tmp_path / log_level

    result = invoke_inspect(
        str(FIXTURES / "valid_minimal_board"),
        "--rules",
        str(RULES),
        "--output",
        str(output),
        "--log-level",
        log_level,
    )

    assert result.exit_code == 0, result.output
    assert ("Review prj-" in result.output) is emits_summary
    assert (output / "logs/run.jsonl").is_file()


def _failing_project_builder(
    discovered: DiscoveredProject,
    manifest: ProjectManifest,
    profile: RuleProfile,
) -> PCBProject:
    del discovered, manifest, profile
    raise RuntimeError("deliberate CLI pipeline failure")


def test_post_ingestion_pipeline_failure_returns_three_with_complete_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ReviewService(project_builder=_failing_project_builder)

    def service_factory() -> ReviewService:
        return service

    monkeypatch.setattr(cli_module, "ReviewService", service_factory)
    output = tmp_path / "fallback"

    result = invoke_inspect(
        str(FIXTURES / "valid_minimal_board"),
        "--rules",
        str(RULES),
        "--output",
        str(output),
    )

    assert result.exit_code == 3, result.output
    findings = validate_complete_output(
        output,
        expected_status=ReviewStatus.ANALYSIS_FAILED,
        expected_finding_count=0,
    )
    assert findings["rule_results"] == []
    assert findings["risk_modes"] == []
    assert findings["analysis_diagnostics"][0]["code"] == (
        "PROJECT_CONSTRUCTION_FAILED"
    )
    assert "diagnostic fallback" in result.output


def test_invalid_input_and_profile_return_two_without_artifacts(
    tmp_path: Path,
) -> None:
    invalid_profile = tmp_path / "invalid.yaml"
    invalid_profile.write_text("schema_version: nope\n", encoding="utf-8")
    invalid_output = tmp_path / "invalid-output"
    missing_output = tmp_path / "missing-output"

    invalid_result = invoke_inspect(
        str(FIXTURES / "valid_minimal_board"),
        "--rules",
        str(invalid_profile),
        "--output",
        str(invalid_output),
    )
    missing_result = invoke_inspect(
        str(tmp_path / "missing-project"),
        "--rules",
        str(RULES),
        "--output",
        str(missing_output),
    )

    assert invalid_result.exit_code == missing_result.exit_code == 2
    assert "PROFILE_VALIDATION_ERROR" in invalid_result.output
    assert "INPUT_NOT_FOUND" in missing_result.output
    assert not invalid_output.exists()
    assert not missing_output.exists()
