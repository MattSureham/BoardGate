"""Third-party parser adapters that emit only BoardGate domain models."""

from boardgate.parsers.bom import BOMParseResult, parse_bom_csv
from boardgate.parsers.errors import ParserError
from boardgate.parsers.excellon import ExcellonParseResult, parse_excellon
from boardgate.parsers.gerber import GerberParseResult, parse_gerber
from boardgate.parsers.placement import (
    PlacementParseResult,
    parse_placement_csv,
)

__all__ = [
    "BOMParseResult",
    "ExcellonParseResult",
    "GerberParseResult",
    "ParserError",
    "PlacementParseResult",
    "parse_bom_csv",
    "parse_excellon",
    "parse_gerber",
    "parse_placement_csv",
]
