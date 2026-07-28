"""Deterministic PCBProject assembly tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
    parse_job,
)
from boardgate.application.project_builder import ProjectBuildError, build_project
from boardgate.config import load_rule_profile
from boardgate.domain.enums import FileType, LayerRole, RiskMode
from boardgate.domain.project import PCBProject
from boardgate.ingestion import build_manifest, discover_inputs
from boardgate.parsers import ParserError

OUTLINE = b"""G04 BoardGate square outline*
%FSLAX46Y46*%
%MOMM*%
%TF.FileFunction,Profile,NP*%
%ADD10C,0.100*%
D10*
X000000Y000000D02*
X10000000Y000000D01*
X10000000Y10000000D01*
X000000Y10000000D01*
X000000Y000000D01*
M02*
"""
TOP_COPPER = b"""G04 BoardGate top copper*
%FSLAX46Y46*%
%MOMM*%
%TF.FileFunction,Copper,L1,Top*%
%ADD10C,0.300*%
D10*
X5000000Y5000000D03*
M02*
"""
DRILL = b"""M48
METRIC,TZ,000.000
T01C0.300
%
T01
X5.000Y5.000
M30
"""


def _inline_executor(
    job: ParserJob,
    *,
    timeout_seconds: float,
) -> ParserExecution:
    del timeout_seconds
    try:
        return ParserExecution(
            file_type=job.file_type,
            source_file_id=job.source_file_id,
            result=parse_job(job),
        )
    except ParserError as error:
        return ParserExecution(
            file_type=job.file_type,
            source_file_id=job.source_file_id,
            failure=ParserFailure(code=error.code, detail=error.detail),
        )


def _write_project(root: Path) -> None:
    root.mkdir()
    (root / "board.gko").write_bytes(OUTLINE)
    (root / "board.gtl").write_bytes(TOP_COPPER)
    (root / "board.drl").write_bytes(DRILL)
    (root / "bom.csv").write_text(
        "Reference,Qty,Value\nR1,1,10k\n",
        encoding="utf-8",
    )
    (root / "placement.csv").write_text(
        "Reference,X (mm),Y (mm),Rotation,Side\nR1,5,5,90,Top\n",
        encoding="utf-8",
    )


def test_project_builder_assembles_all_normalized_inputs_stably(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "project"
    _write_project(source_root)
    profile = load_rule_profile(Path("rules/default.yaml"))

    with discover_inputs((source_root,)) as discovered:
        manifest = build_manifest(discovered)
        first = build_project(
            discovered,
            manifest,
            profile,
            parser_executor=_inline_executor,
        )
        second = build_project(
            discovered,
            manifest,
            profile,
            parser_executor=_inline_executor,
        )

    assert first == second
    assert first.project_id == manifest.project_id
    assert {layer.role for layer in first.layers} == {
        LayerRole.BOARD_OUTLINE,
        LayerRole.TOP_COPPER,
    }
    assert first.board_outline is not None
    assert first.board_outline.outer_contour_count == 1
    assert len(first.drills) == 1
    assert first.components[0].reference == "R1"
    assert first.bom_items[0].references == ("R1",)
    assert first.assembly_requirements.review_requested
    assert first.fabrication_requirements.min_trace_width_mm == 0.1
    assert not first.source_diagnostics
    assert PCBProject.model_validate_json(first.model_dump_json()) == first


def test_parser_failure_is_retained_without_losing_other_sources(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "project"
    _write_project(source_root)
    profile = load_rule_profile(Path("rules/default.yaml"))

    def fail_drill(
        job: ParserJob,
        *,
        timeout_seconds: float,
    ) -> ParserExecution:
        if job.file_type is FileType.EXCELLON:
            return ParserExecution(
                file_type=job.file_type,
                source_file_id=job.source_file_id,
                failure=ParserFailure(
                    code="PARSER_TIMEOUT",
                    detail=f"parser exceeded the {timeout_seconds:g}-second limit",
                ),
            )
        return _inline_executor(job, timeout_seconds=timeout_seconds)

    with discover_inputs((source_root,)) as discovered:
        manifest = build_manifest(discovered)
        project = build_project(
            discovered,
            manifest,
            profile,
            parser_executor=fail_drill,
        )

    assert not project.drills
    assert project.board_outline is not None
    assert project.source_diagnostics[0].code == "PARSER_TIMEOUT"
    assert project.source_diagnostics[0].level.value == "ERROR"
    assert any(
        uncertainty.risk_mode is RiskMode.PARSER_LIMITATION
        and "PARSER_TIMEOUT" in uncertainty.subject
        for uncertainty in project.uncertainties
    )


def test_project_builder_rejects_inventory_and_digest_changes(tmp_path: Path) -> None:
    source_root = tmp_path / "project"
    _write_project(source_root)
    profile = load_rule_profile(Path("rules/default.yaml"))

    with discover_inputs((source_root,)) as discovered:
        manifest = build_manifest(discovered)
        changed_path = next(
            item.staged_path
            for item in discovered.files
            if item.logical_path == "bom.csv"
        )
        changed_path.write_text(
            "Reference,Qty,Value\nR2,1,20k\n",
            encoding="utf-8",
        )
        with pytest.raises(ProjectBuildError) as caught:
            build_project(
                discovered,
                manifest,
                profile,
                parser_executor=_inline_executor,
            )

    assert caught.value.code == "PROJECT_SOURCE_CHANGED"
