"""Shared domain enumerations."""

from enum import StrEnum


class FileType(StrEnum):
    """Supported and recognized project file types."""

    GERBER = "gerber"
    EXCELLON = "excellon"
    BOM_CSV = "bom_csv"
    BOM_XLSX = "bom_xlsx"
    PLACEMENT_CSV = "placement_csv"
    RULES_YAML = "rules_yaml"
    RULES_JSON = "rules_json"
    UNKNOWN = "unknown"


class LayerRole(StrEnum):
    """Normalized PCB layer roles."""

    TOP_COPPER = "top_copper"
    BOTTOM_COPPER = "bottom_copper"
    INNER_COPPER = "inner_copper"
    TOP_SOLDER_MASK = "top_solder_mask"
    BOTTOM_SOLDER_MASK = "bottom_solder_mask"
    TOP_SILKSCREEN = "top_silkscreen"
    BOTTOM_SILKSCREEN = "bottom_silkscreen"
    TOP_PASTE = "top_paste"
    BOTTOM_PASTE = "bottom_paste"
    BOARD_OUTLINE = "board_outline"
    DRILL_PLATED = "drill_plated"
    DRILL_NON_PLATED = "drill_non_plated"
    UNKNOWN = "unknown"


class BoardSide(StrEnum):
    """Physical board side."""

    TOP = "top"
    BOTTOM = "bottom"
    INNER = "inner"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class Polarity(StrEnum):
    """Gerber material polarity."""

    DARK = "dark"
    CLEAR = "clear"
    UNKNOWN = "unknown"


class ApertureShape(StrEnum):
    """Normalized aperture shape."""

    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    OBROUND = "obround"
    POLYGON = "polygon"
    MACRO = "macro"
    UNKNOWN = "unknown"


class Plating(StrEnum):
    """Drill plating interpretation."""

    PLATED = "plated"
    NON_PLATED = "non_plated"
    UNKNOWN = "unknown"


class RiskMode(StrEnum):
    """Explicit risk modes understood by orchestration and reporting."""

    FILE_INCOMPLETE = "FILE_INCOMPLETE"
    FILE_TYPE_UNKNOWN = "FILE_TYPE_UNKNOWN"
    UNIT_AMBIGUITY = "UNIT_AMBIGUITY"
    COORDINATE_MISMATCH = "COORDINATE_MISMATCH"
    LAYER_MAPPING_UNCERTAIN = "LAYER_MAPPING_UNCERTAIN"
    OUTLINE_UNCERTAIN = "OUTLINE_UNCERTAIN"
    GEOMETRY_VIOLATION = "GEOMETRY_VIOLATION"
    CROSS_FILE_INCONSISTENCY = "CROSS_FILE_INCONSISTENCY"
    DESIGN_INTENT_UNKNOWN = "DESIGN_INTENT_UNKNOWN"
    MANUFACTURER_RULE_MISMATCH = "MANUFACTURER_RULE_MISMATCH"
    PARSER_LIMITATION = "PARSER_LIMITATION"
    ANALYSIS_LIMITATION = "ANALYSIS_LIMITATION"


class Severity(StrEnum):
    """Finding severity."""

    BLOCKER = "BLOCKER"
    HIGH = "HIGH"
    WARNING = "WARNING"
    INFO = "INFO"


class FindingStatus(StrEnum):
    """Finding lifecycle state."""

    OPEN = "OPEN"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"
    RESOLVED = "RESOLVED"


class ReviewStatus(StrEnum):
    """Overall deterministic review result."""

    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    NOT_READY_FOR_FABRICATION = "NOT_READY_FOR_FABRICATION"
    READY_WITH_CONFIRMATIONS = "READY_WITH_CONFIRMATIONS"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
