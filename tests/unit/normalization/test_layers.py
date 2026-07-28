"""Evidence-preserving Gerber layer mapping tests."""

from __future__ import annotations

import hashlib

import pytest

from boardgate.domain.enums import BoardSide, FileType, LayerRole, RiskMode
from boardgate.domain.identifiers import source_file_id
from boardgate.domain.layer import PCBLayer
from boardgate.domain.source import SourceFile
from boardgate.normalization.layers import normalize_gerber_layer
from boardgate.parsers import parse_gerber

GERBER_TEMPLATE = """G04 layer fixture*
%FSLAX46Y46*%
%MOMM*%
{attributes}
%ADD10C,0.200*%
D10*
X000000Y000000D03*
M02*
"""


def normalize(
    logical_path: str,
    *,
    file_function: str | None = None,
    same_coordinates: str | None = None,
) -> PCBLayer:
    attributes = []
    if file_function is not None:
        attributes.append(f"%TF.FileFunction,{file_function}*%")
    if same_coordinates is not None:
        attributes.append(f"%TF.SameCoordinates,{same_coordinates}*%")
    payload = GERBER_TEMPLATE.format(attributes="\n".join(attributes)).encode()
    digest = hashlib.sha256(payload).hexdigest()
    source_id = source_file_id(logical_path, digest)
    source = SourceFile(
        source_file_id=source_id,
        logical_path=logical_path,
        sha256=digest,
        size_bytes=len(payload),
        file_type=FileType.GERBER,
    )
    parsed = parse_gerber(
        payload,
        logical_path=logical_path,
        source_file_id=source_id,
    )
    return normalize_gerber_layer(source, parsed)


def test_agreeing_x2_filename_and_extension_resolve_top_copper() -> None:
    layer = normalize(
        "board-top-copper.gtl",
        file_function="Copper,L1,Top",
        same_coordinates="origin-a",
    )

    assert layer.role is LayerRole.TOP_COPPER
    assert layer.side is BoardSide.TOP
    assert layer.mapping_confidence == 0.99
    evidence = {
        item for candidate in layer.mapping_candidates for item in candidate.evidence
    }
    assert "extension:.gtl" in evidence
    assert "filename:board-top-copper.gtl" in evidence
    assert "x2:file-function:Copper,L1,Top" in evidence
    assert layer.coordinate_evidence == ("x2:same-coordinates:origin-a",)
    assert not layer.uncertainties


def test_conflicting_x2_and_extension_remain_unknown() -> None:
    layer = normalize("renamed.gbl", file_function="Copper,L1,Top")

    assert layer.role is LayerRole.UNKNOWN
    assert layer.side is BoardSide.UNKNOWN
    assert layer.mapping_confidence == 0.0
    assert layer.uncertainties[0].risk_mode is RiskMode.LAYER_MAPPING_UNCERTAIN
    assert set(layer.uncertainties[0].candidates) == {
        "top_copper/top",
        "bottom_copper/bottom",
    }
    assert "conflicts" in layer.uncertainties[0].summary


@pytest.mark.parametrize(
    ("filename", "role", "side"),
    [
        ("board.gtl", LayerRole.TOP_COPPER, BoardSide.TOP),
        ("board.gbl", LayerRole.BOTTOM_COPPER, BoardSide.BOTTOM),
        ("board.gts", LayerRole.TOP_SOLDER_MASK, BoardSide.TOP),
        ("board.gbs", LayerRole.BOTTOM_SOLDER_MASK, BoardSide.BOTTOM),
        ("board.gto", LayerRole.TOP_SILKSCREEN, BoardSide.TOP),
        ("board.gbo", LayerRole.BOTTOM_SILKSCREEN, BoardSide.BOTTOM),
        ("board.gtp", LayerRole.TOP_PASTE, BoardSide.TOP),
        ("board.gbp", LayerRole.BOTTOM_PASTE, BoardSide.BOTTOM),
        (
            "board.gko",
            LayerRole.BOARD_OUTLINE,
            BoardSide.NOT_APPLICABLE,
        ),
        ("board.g1", LayerRole.INNER_COPPER, BoardSide.INNER),
    ],
)
def test_extension_mapping(
    filename: str,
    role: LayerRole,
    side: BoardSide,
) -> None:
    layer = normalize(filename)

    assert layer.role is role
    assert layer.side is side
    assert layer.mapping_confidence == 0.86


@pytest.mark.parametrize(
    ("file_function", "role", "side"),
    [
        ("Copper,L2,Inr", LayerRole.INNER_COPPER, BoardSide.INNER),
        (
            "Soldermask,Top",
            LayerRole.TOP_SOLDER_MASK,
            BoardSide.TOP,
        ),
        (
            "Legend,Bot",
            LayerRole.BOTTOM_SILKSCREEN,
            BoardSide.BOTTOM,
        ),
        ("Paste,Top", LayerRole.TOP_PASTE, BoardSide.TOP),
        (
            "Profile,NP",
            LayerRole.BOARD_OUTLINE,
            BoardSide.NOT_APPLICABLE,
        ),
    ],
)
def test_x2_mapping(
    file_function: str,
    role: LayerRole,
    side: BoardSide,
) -> None:
    layer = normalize("generic.gbr", file_function=file_function)

    assert layer.role is role
    assert layer.side is side


def test_generic_name_remains_explicitly_unknown_and_stable() -> None:
    first = normalize("drawing.gbr")
    second = normalize("drawing.gbr")

    assert first == second
    assert first.role is LayerRole.UNKNOWN
    assert first.mapping_candidates == ()
    assert first.uncertainties[0].risk_mode is RiskMode.LAYER_MAPPING_UNCERTAIN
    assert "cannot be confirmed" in first.uncertainties[0].summary
    assert type(first).model_validate_json(first.model_dump_json()) == first


def test_mismatched_source_id_is_rejected() -> None:
    layer = normalize("board.gtl")
    payload = GERBER_TEMPLATE.format(attributes="").encode()
    parsed = parse_gerber(
        payload,
        logical_path="board.gtl",
        source_file_id="src-ffffffffffffffff",
    )
    source = SourceFile(
        source_file_id=layer.source_file_id,
        logical_path="board.gtl",
        sha256="a" * 64,
        size_bytes=len(payload),
        file_type=FileType.GERBER,
    )

    with pytest.raises(ValueError, match="does not match"):
        normalize_gerber_layer(source, parsed)
