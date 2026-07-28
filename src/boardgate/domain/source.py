"""Source files and project manifest models."""

from pathlib import PurePosixPath
from typing import Self

from pydantic import Field, model_validator

from boardgate.domain.base import VersionedModel
from boardgate.domain.enums import FileType, RiskMode
from boardgate.domain.provenance import Provenance


class ClassificationCandidate(VersionedModel):
    """A deterministic file-classification candidate and its evidence."""

    file_type: FileType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[str, ...] = ()


class SourceFile(VersionedModel):
    """Immutable metadata for one safely ingested source file."""

    source_file_id: str = Field(pattern=r"^src-[0-9a-f]{16}$")
    logical_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    file_type: FileType
    candidates: tuple[ClassificationCandidate, ...] = ()

    @model_validator(mode="after")
    def require_safe_logical_path(self) -> Self:
        """Keep persisted paths relative, normalized, and platform neutral."""
        path = PurePosixPath(self.logical_path)
        if path.is_absolute() or ".." in path.parts or "." in path.parts:
            msg = "logical_path must be a normalized relative POSIX path"
            raise ValueError(msg)
        if "\\" in self.logical_path:
            msg = "logical_path must use POSIX separators"
            raise ValueError(msg)
        return self


class Uncertainty(VersionedModel):
    """An explicit unknown or ambiguous project fact."""

    risk_mode: RiskMode
    subject: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    candidates: tuple[str, ...] = ()
    evidence: tuple[Provenance, ...] = ()
    requires_human_confirmation: bool = True


class ProjectManifest(VersionedModel):
    """Stable inventory and classification snapshot for one project."""

    project_id: str = Field(pattern=r"^prj-[0-9a-f]{16}$")
    source_files: tuple[SourceFile, ...]
    uncertainties: tuple[Uncertainty, ...] = ()

    @model_validator(mode="after")
    def require_unique_sources(self) -> Self:
        """Reject ambiguous duplicate identifiers and logical paths."""
        source_ids = [source.source_file_id for source in self.source_files]
        paths = [source.logical_path.casefold() for source in self.source_files]
        if len(source_ids) != len(set(source_ids)):
            msg = "manifest source_file_id values must be unique"
            raise ValueError(msg)
        if len(paths) != len(set(paths)):
            msg = "manifest logical paths must be unique when case-folded"
            raise ValueError(msg)
        return self
