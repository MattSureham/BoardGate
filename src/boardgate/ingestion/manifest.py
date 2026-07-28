"""Stable project manifest construction."""

from __future__ import annotations

import json

from boardgate import __version__
from boardgate.domain.enums import FileType, RiskMode
from boardgate.domain.identifiers import project_id, source_file_id
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import ProjectManifest, SourceFile, Uncertainty
from boardgate.ingestion.classifier import classify_file
from boardgate.ingestion.discovery import DiscoveredProject
from boardgate.ingestion.hashing import sha256_file


def build_manifest(discovered: DiscoveredProject) -> ProjectManifest:
    """Hash and classify all staged files into a stable manifest."""
    source_files: list[SourceFile] = []
    uncertainties: list[Uncertainty] = []
    for item in discovered.files:
        digest = sha256_file(
            item.staged_path,
            expected_size=item.size_bytes,
            subject=item.logical_path,
        )
        source_id = source_file_id(item.logical_path, digest)
        classification = classify_file(item.staged_path, item.logical_path)
        source = SourceFile(
            source_file_id=source_id,
            logical_path=item.logical_path,
            sha256=digest,
            size_bytes=item.size_bytes,
            file_type=classification.file_type,
            candidates=classification.candidates,
        )
        source_files.append(source)
        if classification.file_type is FileType.UNKNOWN:
            candidate_names = tuple(
                candidate.file_type.value
                for candidate in classification.candidates
                if candidate.file_type is not FileType.UNKNOWN
            )
            summary = (
                "Conflicting strong file-type evidence requires confirmation."
                if classification.ambiguous
                else "No supported file type could be confirmed."
            )
            uncertainties.append(
                Uncertainty(
                    risk_mode=RiskMode.FILE_TYPE_UNKNOWN,
                    subject=item.logical_path,
                    summary=summary,
                    candidates=candidate_names,
                    evidence=(
                        Provenance(
                            source_file_id=source_id,
                            parser="boardgate-classifier",
                            parser_version=__version__,
                            metadata={
                                "logical_path": item.logical_path,
                                "classification_ambiguous": (classification.ambiguous),
                            },
                        ),
                    ),
                )
            )
    ordered_sources = tuple(
        sorted(source_files, key=lambda source: source.logical_path)
    )
    identifier = project_id(
        [(source.logical_path, source.sha256) for source in ordered_sources]
    )
    return ProjectManifest(
        project_id=identifier,
        source_files=ordered_sources,
        uncertainties=tuple(
            sorted(uncertainties, key=lambda uncertainty: uncertainty.subject)
        ),
    )


def manifest_json(manifest: ProjectManifest) -> str:
    """Serialize a human-readable manifest with stable bytes."""
    return (
        json.dumps(
            manifest.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
