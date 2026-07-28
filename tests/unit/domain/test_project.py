"""Unified PCB project model tests."""

import pytest
from pydantic import ValidationError

from boardgate.domain.enums import FileType
from boardgate.domain.geometry import CoordinateSystem
from boardgate.domain.identifiers import project_id, source_file_id
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.source import ProjectManifest, SourceFile

SHA_A = "a" * 64
PROFILE_SHA = "b" * 64


def make_source() -> SourceFile:
    source_id = source_file_id("board.gtl", SHA_A)
    return SourceFile(
        source_file_id=source_id,
        logical_path="board.gtl",
        sha256=SHA_A,
        size_bytes=10,
        file_type=FileType.GERBER,
    )


def make_project() -> PCBProject:
    source = make_source()
    project_identifier = project_id([(source.logical_path, source.sha256)])
    manifest = ProjectManifest(
        project_id=project_identifier,
        source_files=(source,),
    )
    return PCBProject(
        project_id=project_identifier,
        source_files=(source,),
        manifest=manifest,
        coordinate_system=CoordinateSystem(),
        fabrication_requirements=FabricationRequirements(
            profile_id="default",
            profile_sha256=PROFILE_SHA,
            min_trace_width_mm=0.1,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def test_project_json_round_trip() -> None:
    project = make_project()

    assert PCBProject.model_validate_json(project.model_dump_json()) == project


def test_project_rejects_manifest_id_mismatch() -> None:
    project = make_project()
    other_id = project_id([("other.gtl", "c" * 64)])

    with pytest.raises(ValidationError, match="must match manifest"):
        PCBProject.model_validate(
            {
                **project.model_dump(),
                "project_id": other_id,
            }
        )


def test_source_path_rejects_traversal_and_platform_separators() -> None:
    source = make_source()

    for path in ("../board.gtl", "/board.gtl", "folder\\board.gtl"):
        with pytest.raises(ValidationError):
            SourceFile.model_validate({**source.model_dump(), "logical_path": path})
