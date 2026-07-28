"""Security limits for all project input forms."""

from pydantic import Field

from boardgate.domain.base import StrictModel

MEBIBYTE = 1024 * 1024


class IngestionLimits(StrictModel):
    """Bounded discovery and expansion limits."""

    max_file_count: int = Field(default=256, ge=1)
    max_archive_bytes: int = Field(default=100 * MEBIBYTE, ge=1)
    max_file_bytes: int = Field(default=50 * MEBIBYTE, ge=1)
    max_total_expanded_bytes: int = Field(default=250 * MEBIBYTE, ge=1)
    max_compression_ratio: float = Field(default=50.0, ge=1.0)
