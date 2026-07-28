"""Third-party parser adapters that emit only BoardGate domain models."""

from boardgate.parsers.errors import ParserError
from boardgate.parsers.excellon import ExcellonParseResult, parse_excellon

__all__ = ["ExcellonParseResult", "ParserError", "parse_excellon"]
