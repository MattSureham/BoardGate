"""Third-party parser adapters that emit only BoardGate domain models."""

from boardgate.parsers.errors import ParserError
from boardgate.parsers.excellon import ExcellonParseResult, parse_excellon
from boardgate.parsers.gerber import GerberParseResult, parse_gerber

__all__ = [
    "ExcellonParseResult",
    "GerberParseResult",
    "ParserError",
    "parse_excellon",
    "parse_gerber",
]
