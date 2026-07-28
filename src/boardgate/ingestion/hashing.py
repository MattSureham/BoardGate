"""Bounded streaming hashes for safely staged files."""

from hashlib import sha256
from pathlib import Path

from boardgate.ingestion.errors import IngestionError

_HASH_CHUNK_BYTES = 1024 * 1024


def sha256_file(path: Path, *, expected_size: int, subject: str) -> str:
    """Hash a staged file and verify its immutable staged size."""
    digest = sha256()
    actual_size = 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(_HASH_CHUNK_BYTES):
                actual_size += len(chunk)
                if actual_size > expected_size:
                    raise IngestionError(
                        "STAGED_FILE_CHANGED",
                        subject,
                        "staged file grew before hashing completed",
                    )
                digest.update(chunk)
    except OSError as error:
        raise IngestionError(
            "STAGED_FILE_READ_ERROR",
            subject,
            "staged file could not be hashed",
        ) from error
    if actual_size != expected_size:
        raise IngestionError(
            "STAGED_FILE_CHANGED",
            subject,
            "staged file size changed before hashing completed",
        )
    return digest.hexdigest()
