"""Unified, lifecycle-bounded discovery for files, directories, and ZIPs."""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from boardgate.ingestion.archive import ExpansionBudget, expand_zip
from boardgate.ingestion.errors import IngestionError
from boardgate.ingestion.limits import IngestionLimits
from boardgate.ingestion.paths import normalize_logical_path, path_collision_key

_COPY_CHUNK_BYTES = 1024 * 1024
_OFFICE_CONTAINER_SUFFIXES = frozenset({".xlsx", ".xlsm", ".xltx", ".xltm"})


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    """One safely staged project file."""

    logical_path: str
    staged_path: Path
    size_bytes: int
    source_kind: str


@dataclass(frozen=True, slots=True)
class DiscoveredProject:
    """All staged files valid only for the discovery context lifetime."""

    staging_directory: Path
    files: tuple[DiscoveredFile, ...]


def _input_subject(path: Path) -> str:
    return path.name or "<input>"


def _copy_regular_file(
    source: Path,
    destination: Path,
    *,
    logical_path: str,
    limits: IngestionLimits,
    budget: ExpansionBudget,
) -> int:
    subject = _input_subject(source)
    if source.is_symlink():
        raise IngestionError(
            "INPUT_SYMLINK",
            subject,
            "symbolic-link inputs are rejected",
        )
    try:
        stat_result = source.stat()
    except OSError as error:
        raise IngestionError(
            "INPUT_READ_ERROR",
            subject,
            "input metadata could not be read",
        ) from error
    if not source.is_file():
        raise IngestionError(
            "UNSUPPORTED_INPUT",
            subject,
            "input must be a regular file, directory, or ZIP",
        )
    budget.reserve(logical_path=logical_path, size_bytes=stat_result.st_size)
    destination.parent.mkdir(parents=True, exist_ok=True)
    actual_size = 0
    try:
        with source.open("rb") as input_stream, destination.open("xb") as output_stream:
            while chunk := input_stream.read(_COPY_CHUNK_BYTES):
                actual_size += len(chunk)
                if (
                    actual_size > stat_result.st_size
                    or actual_size > limits.max_file_bytes
                ):
                    raise IngestionError(
                        "INPUT_SIZE_CHANGED",
                        subject,
                        "input grew while being staged",
                    )
                output_stream.write(chunk)
    except OSError as error:
        raise IngestionError(
            "INPUT_READ_ERROR",
            subject,
            "input could not be staged",
        ) from error
    if actual_size != stat_result.st_size:
        raise IngestionError(
            "INPUT_SIZE_CHANGED",
            subject,
            "input size changed while being staged",
        )
    return actual_size


def _directory_files(
    root: Path,
    *,
    max_files: int,
) -> tuple[tuple[Path, str], ...]:
    subject = _input_subject(root)
    results: list[tuple[Path, str]] = []
    try:
        walker = os.walk(root, followlinks=False)
        for current, directory_names, filenames in walker:
            current_path = Path(current)
            for directory_name in directory_names:
                directory = current_path / directory_name
                if directory.is_symlink():
                    raise IngestionError(
                        "INPUT_SYMLINK",
                        subject,
                        "symbolic links inside directories are rejected",
                    )
            for filename in filenames:
                if len(results) >= max_files:
                    raise IngestionError(
                        "FILE_COUNT_LIMIT",
                        subject,
                        "directory exceeds the remaining project file-count limit",
                    )
                source = current_path / filename
                if source.is_symlink():
                    raise IngestionError(
                        "INPUT_SYMLINK",
                        subject,
                        "symbolic links inside directories are rejected",
                    )
                relative = source.relative_to(root).as_posix()
                logical_path = normalize_logical_path(relative, subject=subject)
                results.append((source, logical_path))
    except OSError as error:
        raise IngestionError(
            "INPUT_READ_ERROR",
            subject,
            "directory could not be traversed",
        ) from error
    return tuple(sorted(results, key=lambda item: item[1]))


def _looks_like_zip(path: Path) -> bool:
    if path.suffix.casefold() in _OFFICE_CONTAINER_SUFFIXES:
        return False
    if path.suffix.casefold() == ".zip":
        return True
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


@contextmanager
def discover_inputs(
    inputs: Sequence[Path],
    *,
    limits: IngestionLimits | None = None,
) -> Iterator[DiscoveredProject]:
    """Stage all inputs safely and remove the private workspace afterward."""
    if not inputs:
        raise IngestionError(
            "NO_INPUTS",
            "<inputs>",
            "at least one project input is required",
        )
    active_limits = limits or IngestionLimits()
    budget = ExpansionBudget(active_limits)
    collision_keys: set[str] = set()

    def register_path(logical_path: str) -> None:
        key = path_collision_key(logical_path)
        tree_conflict = any(
            key == existing
            or key.startswith(f"{existing}/")
            or existing.startswith(f"{key}/")
            for existing in collision_keys
        )
        if tree_conflict:
            raise IngestionError(
                "DUPLICATE_LOGICAL_PATH",
                logical_path,
                "multiple inputs resolve to conflicting logical paths",
            )
        collision_keys.add(key)

    with tempfile.TemporaryDirectory(prefix="boardgate-ingest-") as temporary:
        staging_directory = Path(temporary)
        discovered: list[DiscoveredFile] = []
        for input_path in inputs:
            subject = _input_subject(input_path)
            if input_path.is_symlink():
                raise IngestionError(
                    "INPUT_SYMLINK",
                    subject,
                    "symbolic-link inputs are rejected",
                )
            if input_path.is_dir():
                for source, logical_path in _directory_files(
                    input_path,
                    max_files=budget.remaining_file_count,
                ):
                    register_path(logical_path)
                    destination = staging_directory.joinpath(
                        *PurePosixPath(logical_path).parts
                    )
                    size = _copy_regular_file(
                        source,
                        destination,
                        logical_path=logical_path,
                        limits=active_limits,
                        budget=budget,
                    )
                    discovered.append(
                        DiscoveredFile(
                            logical_path=logical_path,
                            staged_path=destination,
                            size_bytes=size,
                            source_kind="directory",
                        )
                    )
            elif input_path.is_file() and _looks_like_zip(input_path):
                extracted = expand_zip(
                    input_path,
                    staging_directory,
                    limits=active_limits,
                    budget=budget,
                    register_path=register_path,
                )
                discovered.extend(
                    DiscoveredFile(
                        logical_path=logical_path,
                        staged_path=staged_path,
                        size_bytes=size,
                        source_kind="zip",
                    )
                    for logical_path, staged_path, size in extracted
                )
            elif input_path.is_file():
                logical_path = normalize_logical_path(subject, subject=subject)
                register_path(logical_path)
                destination = staging_directory / logical_path
                size = _copy_regular_file(
                    input_path,
                    destination,
                    logical_path=logical_path,
                    limits=active_limits,
                    budget=budget,
                )
                discovered.append(
                    DiscoveredFile(
                        logical_path=logical_path,
                        staged_path=destination,
                        size_bytes=size,
                        source_kind="file",
                    )
                )
            else:
                raise IngestionError(
                    "INPUT_NOT_FOUND",
                    subject,
                    "input does not exist or is not accessible",
                )
        ordered = tuple(sorted(discovered, key=lambda item: item.logical_path))
        try:
            yield DiscoveredProject(staging_directory, ordered)
        finally:
            for item in ordered:
                if item.staged_path.exists() and item.staged_path.is_symlink():
                    item.staged_path.unlink()
            shutil.rmtree(staging_directory, ignore_errors=True)
