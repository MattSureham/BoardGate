"""Shared immutable revision-workspace helpers for authoring services."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from boardgate.application.artifacts import (
    COMPLETE_ARTIFACT_PATHS,
    CompleteArtifactBundle,
)
from boardgate.domain.base import StrictModel
from boardgate.domain.serialization import canonical_json

DESIGN_DIRECTORY = "design"
REQUEST_ARTIFACT = "evidence/request.json"
RESULT_ARTIFACT = "evidence/result.json"
VALIDATION_DIRECTORY = "validation"


def logical_destination(root: Path, logical_path: str) -> Path:
    """Resolve one validated logical path below a workspace root."""
    return root.joinpath(*PurePosixPath(logical_path).parts)


def load_validation_bundle(root: Path) -> CompleteArtifactBundle:
    """Load the nested six-artifact validation bundle from a workspace."""
    files: dict[str, str] = {}
    for logical_path in COMPLETE_ARTIFACT_PATHS:
        path = root / VALIDATION_DIRECTORY / logical_path
        files[logical_path] = path.read_text(encoding="utf-8")
    return CompleteArtifactBundle.from_files(files)


def canonical_artifact(model: StrictModel) -> str:
    """Serialize one evidence artifact in its canonical persisted form."""
    return f"{canonical_json(model)}\n"


def workspace_inventory(root: Path) -> tuple[set[str], set[str]]:
    """Inventory one staged revision workspace, rejecting unsafe nodes."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("revision workspace root must be a regular directory")
    files: set[str] = set()
    directories: set[str] = set()
    for path in root.rglob("*"):
        logical_path = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError("revision workspace must not contain symbolic links")
        if path.is_file():
            files.add(logical_path)
        elif path.is_dir():
            directories.add(logical_path)
        else:
            raise ValueError("revision workspace contains a non-regular node")
    return files, directories


def parent_directories(logical_paths: set[str]) -> set[str]:
    """Compute the complete set of logical parent directories."""
    return {
        parent.as_posix()
        for logical_path in logical_paths
        for parent in PurePosixPath(logical_path).parents
        if parent.as_posix() != "."
    }
