"""Evidence-preserving Gerber layer mapping."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath

from boardgate import __version__
from boardgate.domain.enums import BoardSide, LayerRole, RiskMode
from boardgate.domain.identifiers import object_id
from boardgate.domain.layer import LayerMappingCandidate, PCBLayer
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import SourceFile, Uncertainty
from boardgate.parsers.gerber import GerberParseResult

_STRONG_MAPPING_CONFIDENCE = 0.75
_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class _MappingSignal:
    role: LayerRole
    side: BoardSide
    confidence: float
    evidence: str


_EXTENSION_MAPPINGS: dict[str, tuple[LayerRole, BoardSide]] = {
    ".gtl": (LayerRole.TOP_COPPER, BoardSide.TOP),
    ".gbl": (LayerRole.BOTTOM_COPPER, BoardSide.BOTTOM),
    ".gts": (LayerRole.TOP_SOLDER_MASK, BoardSide.TOP),
    ".gbs": (LayerRole.BOTTOM_SOLDER_MASK, BoardSide.BOTTOM),
    ".gto": (LayerRole.TOP_SILKSCREEN, BoardSide.TOP),
    ".gbo": (LayerRole.BOTTOM_SILKSCREEN, BoardSide.BOTTOM),
    ".gtp": (LayerRole.TOP_PASTE, BoardSide.TOP),
    ".gbp": (LayerRole.BOTTOM_PASTE, BoardSide.BOTTOM),
    ".gko": (LayerRole.BOARD_OUTLINE, BoardSide.NOT_APPLICABLE),
    ".gml": (LayerRole.BOARD_OUTLINE, BoardSide.NOT_APPLICABLE),
    ".gm1": (LayerRole.BOARD_OUTLINE, BoardSide.NOT_APPLICABLE),
    ".g1": (LayerRole.INNER_COPPER, BoardSide.INNER),
    ".g2": (LayerRole.INNER_COPPER, BoardSide.INNER),
}

_FILENAME_MARKERS: tuple[
    tuple[frozenset[str], tuple[str, ...], LayerRole, BoardSide],
    ...,
] = (
    (
        frozenset({"top", "copper"}),
        ("topcopper", "fcu", "frontcopper"),
        LayerRole.TOP_COPPER,
        BoardSide.TOP,
    ),
    (
        frozenset({"bottom", "copper"}),
        ("bottomcopper", "bcu", "backcopper"),
        LayerRole.BOTTOM_COPPER,
        BoardSide.BOTTOM,
    ),
    (
        frozenset({"top", "mask"}),
        ("topsoldermask", "fmask"),
        LayerRole.TOP_SOLDER_MASK,
        BoardSide.TOP,
    ),
    (
        frozenset({"bottom", "mask"}),
        ("bottomsoldermask", "bmask"),
        LayerRole.BOTTOM_SOLDER_MASK,
        BoardSide.BOTTOM,
    ),
    (
        frozenset({"top", "silk"}),
        ("topsilkscreen", "fsilk", "fsilks"),
        LayerRole.TOP_SILKSCREEN,
        BoardSide.TOP,
    ),
    (
        frozenset({"bottom", "silk"}),
        ("bottomsilkscreen", "bsilk", "bsilks"),
        LayerRole.BOTTOM_SILKSCREEN,
        BoardSide.BOTTOM,
    ),
    (
        frozenset({"top", "paste"}),
        ("toppaste", "fpaste"),
        LayerRole.TOP_PASTE,
        BoardSide.TOP,
    ),
    (
        frozenset({"bottom", "paste"}),
        ("bottompaste", "bpaste"),
        LayerRole.BOTTOM_PASTE,
        BoardSide.BOTTOM,
    ),
    (
        frozenset({"outline"}),
        ("edgecuts", "boardoutline", "profile"),
        LayerRole.BOARD_OUTLINE,
        BoardSide.NOT_APPLICABLE,
    ),
)


def _x2_signal(  # noqa: PLR0911
    file_function: tuple[str, ...],
) -> _MappingSignal | None:
    if not file_function:
        return None
    function = file_function[0].casefold()
    values = tuple(value.casefold() for value in file_function[1:])
    evidence = "x2:file-function:" + ",".join(file_function)
    if function == "copper":
        side_marker = values[-1] if values else ""
        if side_marker in {"top", "front"}:
            return _MappingSignal(
                LayerRole.TOP_COPPER,
                BoardSide.TOP,
                0.99,
                evidence,
            )
        if side_marker in {"bot", "bottom", "back"}:
            return _MappingSignal(
                LayerRole.BOTTOM_COPPER,
                BoardSide.BOTTOM,
                0.99,
                evidence,
            )
        return _MappingSignal(
            LayerRole.INNER_COPPER,
            BoardSide.INNER,
            0.97,
            evidence,
        )
    mapping: dict[str, tuple[LayerRole, LayerRole]] = {
        "soldermask": (
            LayerRole.TOP_SOLDER_MASK,
            LayerRole.BOTTOM_SOLDER_MASK,
        ),
        "legend": (
            LayerRole.TOP_SILKSCREEN,
            LayerRole.BOTTOM_SILKSCREEN,
        ),
        "paste": (LayerRole.TOP_PASTE, LayerRole.BOTTOM_PASTE),
    }
    if function in mapping:
        side_marker = values[-1] if values else ""
        if side_marker in {"top", "front"}:
            return _MappingSignal(
                mapping[function][0],
                BoardSide.TOP,
                0.99,
                evidence,
            )
        if side_marker in {"bot", "bottom", "back"}:
            return _MappingSignal(
                mapping[function][1],
                BoardSide.BOTTOM,
                0.99,
                evidence,
            )
        return None
    if function in {"profile", "outline", "rout"}:
        return _MappingSignal(
            LayerRole.BOARD_OUTLINE,
            BoardSide.NOT_APPLICABLE,
            0.99,
            evidence,
        )
    return None


def _extension_signal(logical_path: str) -> _MappingSignal | None:
    suffix = PurePosixPath(logical_path).suffix.casefold()
    mapping = _EXTENSION_MAPPINGS.get(suffix)
    if mapping is None:
        return None
    return _MappingSignal(*mapping, 0.86, f"extension:{suffix}")


def _filename_signals(logical_path: str) -> tuple[_MappingSignal, ...]:
    stem = PurePosixPath(logical_path).stem.casefold()
    tokens = set(filter(None, _TOKEN_SPLIT.split(stem)))
    compact = "".join(character for character in stem if character.isalnum())
    results: list[_MappingSignal] = []
    for required_tokens, compact_markers, role, side in _FILENAME_MARKERS:
        if required_tokens <= tokens or any(
            marker in compact for marker in compact_markers
        ):
            results.append(
                _MappingSignal(
                    role,
                    side,
                    0.80,
                    f"filename:{PurePosixPath(logical_path).name}",
                )
            )
    return tuple(results)


def _layer_hint_signals(hints: tuple[str, ...]) -> tuple[_MappingSignal, ...]:
    results: list[_MappingSignal] = []
    for hint in hints:
        normalized = hint.casefold()
        if "outline" in normalized:
            results.append(
                _MappingSignal(
                    LayerRole.BOARD_OUTLINE,
                    BoardSide.NOT_APPLICABLE,
                    0.60,
                    f"parser-layer-hint:{hint}",
                )
            )
    return tuple(results)


def _aggregate(
    signals: tuple[_MappingSignal, ...],
) -> tuple[LayerMappingCandidate, ...]:
    grouped: defaultdict[
        tuple[LayerRole, BoardSide],
        list[_MappingSignal],
    ] = defaultdict(list)
    for signal in signals:
        grouped[(signal.role, signal.side)].append(signal)
    candidates = [
        LayerMappingCandidate(
            role=role,
            side=side,
            confidence=max(signal.confidence for signal in group),
            evidence=tuple(sorted({signal.evidence for signal in group})),
        )
        for (role, side), group in grouped.items()
    ]
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                -candidate.confidence,
                candidate.role.value,
                candidate.side.value,
            ),
        )
    )


def _coordinate_evidence(parsed: GerberParseResult) -> tuple[str, ...]:
    values = parsed.file_attributes.get(".SameCoordinates", ())
    return ("x2:same-coordinates:" + ",".join(values),) if values else ()


def normalize_gerber_layer(
    source: SourceFile,
    parsed: GerberParseResult,
) -> PCBLayer:
    """Resolve one Gerber layer only when independent evidence agrees."""
    if parsed.source_file_id != source.source_file_id:
        msg = "parser result source_file_id does not match source"
        raise ValueError(msg)
    signals: list[_MappingSignal] = []
    file_function = parsed.file_attributes.get(".FileFunction")
    if file_function is not None:
        x2 = _x2_signal(file_function)
        if x2 is not None:
            signals.append(x2)
    extension = _extension_signal(source.logical_path)
    if extension is not None:
        signals.append(extension)
    signals.extend(_filename_signals(source.logical_path))
    signals.extend(_layer_hint_signals(parsed.layer_hints))
    candidates = _aggregate(tuple(signals))
    strong = tuple(
        candidate
        for candidate in candidates
        if candidate.confidence >= _STRONG_MAPPING_CONFIDENCE
    )
    uncertainty: tuple[Uncertainty, ...] = ()
    if len(strong) == 1:
        role = strong[0].role
        side = strong[0].side
        confidence = strong[0].confidence
    else:
        role = LayerRole.UNKNOWN
        side = BoardSide.UNKNOWN
        confidence = 0.0
        candidate_labels = tuple(
            f"{candidate.role.value}/{candidate.side.value}" for candidate in candidates
        )
        uncertainty = (
            Uncertainty(
                risk_mode=RiskMode.LAYER_MAPPING_UNCERTAIN,
                subject=source.logical_path,
                summary=(
                    "Strong layer-mapping evidence conflicts."
                    if len(strong) > 1
                    else "Layer role cannot be confirmed from available evidence."
                ),
                candidates=candidate_labels,
                evidence=(
                    Provenance(
                        source_file_id=source.source_file_id,
                        parser="boardgate-layer-mapper",
                        parser_version=__version__,
                        metadata={
                            "candidate_count": len(candidates),
                            "strong_candidate_count": len(strong),
                        },
                    ),
                ),
            ),
        )
    layer_identifier = object_id(
        "layer",
        source.source_file_id,
        0,
        source.logical_path,
    )
    return PCBLayer(
        layer_id=layer_identifier,
        source_file_id=source.source_file_id,
        role=role,
        side=side,
        mapping_confidence=confidence,
        mapping_candidates=candidates,
        coordinate_evidence=_coordinate_evidence(parsed),
        primitives=parsed.primitives,
        bounding_box=parsed.bounding_box,
        uncertainties=uncertainty,
    )
