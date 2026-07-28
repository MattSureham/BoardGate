"""Versioned BoardGate domain models."""

from boardgate.domain.diagnostic import SourceDiagnostic, SourceDiagnosticLevel
from boardgate.domain.geometry import (
    AxisDirection,
    BoundingBox,
    CoordinateSystem,
    Point,
    Unit,
)
from boardgate.domain.project import PCBProject
from boardgate.domain.provenance import Provenance, SourceSpan
from boardgate.domain.source import ProjectManifest, SourceFile, Uncertainty

__all__ = [
    "AxisDirection",
    "BoundingBox",
    "CoordinateSystem",
    "PCBProject",
    "Point",
    "ProjectManifest",
    "Provenance",
    "SourceDiagnostic",
    "SourceDiagnosticLevel",
    "SourceFile",
    "SourceSpan",
    "Uncertainty",
    "Unit",
]
