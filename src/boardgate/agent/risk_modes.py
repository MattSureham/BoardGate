"""Explicit deterministic behavior for every supported review risk mode."""

from __future__ import annotations

from collections.abc import Iterable

from boardgate.agent.models import RiskDirective
from boardgate.domain.enums import FileType, RiskMode
from boardgate.domain.source import ProjectManifest

_RISK_BEHAVIORS: dict[RiskMode, tuple[bool, bool, bool, str]] = {
    RiskMode.FILE_INCOMPLETE: (
        True,
        True,
        True,
        "List missing capabilities and run only checks independent of them.",
    ),
    RiskMode.FILE_TYPE_UNKNOWN: (
        True,
        True,
        True,
        "Retain classification candidates and exclude the source from parsers.",
    ),
    RiskMode.UNIT_AMBIGUITY: (
        True,
        True,
        True,
        "Do not guess units or publish dependent physical measurements.",
    ),
    RiskMode.COORDINATE_MISMATCH: (
        True,
        True,
        True,
        "Report the proven coordinate mismatch without claiming pad alignment.",
    ),
    RiskMode.LAYER_MAPPING_UNCERTAIN: (
        True,
        True,
        True,
        "Preserve mapping candidates and do not promote an uncertain layer role.",
    ),
    RiskMode.OUTLINE_UNCERTAIN: (
        True,
        True,
        True,
        "Avoid outline-dependent readiness claims and request contour confirmation.",
    ),
    RiskMode.GEOMETRY_VIOLATION: (
        True,
        True,
        False,
        "Present deterministic measurements and their configured requirements.",
    ),
    RiskMode.CROSS_FILE_INCONSISTENCY: (
        True,
        True,
        True,
        "Keep each source fact visible and request reconciliation.",
    ),
    RiskMode.DESIGN_INTENT_UNKNOWN: (
        True,
        True,
        True,
        "Report measurable facts only and ask an engineer to confirm intent.",
    ),
    RiskMode.MANUFACTURER_RULE_MISMATCH: (
        True,
        True,
        True,
        "Show the selected profile requirement and require fabricator confirmation.",
    ),
    RiskMode.PARSER_LIMITATION: (
        True,
        True,
        True,
        "Expose unsupported syntax and suppress conclusions that depend on it.",
    ),
}


def risk_directive(risk_mode: RiskMode) -> RiskDirective:
    """Return the immutable behavior assigned to a supported risk mode."""
    (
        continue_independent_checks,
        suppress_unconditional_ready,
        require_human_confirmation,
        action,
    ) = _RISK_BEHAVIORS[risk_mode]
    return RiskDirective(
        risk_mode=risk_mode,
        continue_independent_checks=continue_independent_checks,
        suppress_unconditional_ready=suppress_unconditional_ready,
        require_human_confirmation=require_human_confirmation,
        action=action,
    )


def identify_risk_modes(
    manifest: ProjectManifest,
    declared: Iterable[RiskMode] = (),
) -> tuple[RiskMode, ...]:
    """Combine explicit modes with manifest evidence in canonical order."""
    modes = {
        *declared,
        *(uncertainty.risk_mode for uncertainty in manifest.uncertainties),
    }
    if any(source.file_type is FileType.UNKNOWN for source in manifest.source_files):
        modes.add(RiskMode.FILE_TYPE_UNKNOWN)
    return tuple(sorted(modes, key=str))


def directives_for(
    risk_modes: Iterable[RiskMode],
) -> tuple[RiskDirective, ...]:
    """Return unique directives in canonical risk-mode order."""
    return tuple(
        risk_directive(risk_mode) for risk_mode in sorted(set(risk_modes), key=str)
    )


def supported_risk_modes() -> tuple[RiskMode, ...]:
    """Expose the complete behavior-table coverage for verification."""
    return tuple(sorted(_RISK_BEHAVIORS, key=str))
