"""Safe, deterministic project input ingestion."""

from boardgate.ingestion.discovery import (
    DiscoveredFile,
    DiscoveredProject,
    discover_inputs,
)
from boardgate.ingestion.errors import IngestionError
from boardgate.ingestion.limits import IngestionLimits
from boardgate.ingestion.manifest import build_manifest, manifest_json

__all__ = [
    "DiscoveredFile",
    "DiscoveredProject",
    "IngestionError",
    "IngestionLimits",
    "build_manifest",
    "discover_inputs",
    "manifest_json",
]
