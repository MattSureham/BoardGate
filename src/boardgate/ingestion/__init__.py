"""Safe, deterministic project input ingestion."""

from boardgate.ingestion.discovery import (
    DiscoveredFile,
    DiscoveredProject,
    discover_inputs,
)
from boardgate.ingestion.errors import IngestionError
from boardgate.ingestion.limits import IngestionLimits

__all__ = [
    "DiscoveredFile",
    "DiscoveredProject",
    "IngestionError",
    "IngestionLimits",
    "discover_inputs",
]
