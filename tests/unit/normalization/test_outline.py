"""Trusted board-outline reconstruction tests."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from boardgate.domain.enums import (
    ApertureShape,
    BoardSide,
    LayerRole,
    Polarity,
    RiskMode,
)
from boardgate.domain.geometry import BoundingBox, Point
from boardgate.domain.layer import (
    Aperture,
    ArcPrimitive,
    FlashPrimitive,
    GraphicPrimitive,
    LinePrimitive,
    PCBLayer,
)
from boardgate.domain.provenance import Provenance
from boardgate.normalization.outline import (
    OutlineReconstruction,
    reconstruct_board_outline,
)

SOURCE_ID = "src-0123456789abcdef"
APERTURE = Aperture(shape=ApertureShape.CIRCLE, width_mm=0.1)


def provenance(identifier: str) -> Provenance:
    return Provenance(
        source_file_id=SOURCE_ID,
        object_id=identifier,
        parser="test",
        parser_version="1",
    )


def line(
    identifier: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    polarity: Polarity = Polarity.DARK,
) -> LinePrimitive:
    return LinePrimitive(
        primitive_id=identifier,
        start=Point(x=start[0], y=start[1]),
        end=Point(x=end[0], y=end[1]),
        aperture=APERTURE,
        polarity=polarity,
        provenance=provenance(identifier),
    )


def square(
    prefix: str,
    minimum: tuple[float, float],
    maximum: tuple[float, float],
    *,
    closing_gap: float = 0.0,
) -> tuple[LinePrimitive, ...]:
    x1, y1 = minimum
    x2, y2 = maximum
    return (
        line(f"{prefix}-1", (x1 + closing_gap, y1), (x2, y1)),
        line(f"{prefix}-2", (x2, y1), (x2, y2)),
        line(f"{prefix}-3", (x2, y2), (x1, y2)),
        line(f"{prefix}-4", (x1, y2), (x1, y1)),
    )


def layer(
    primitives: Iterable[GraphicPrimitive],
    *,
    trusted: bool = True,
) -> PCBLayer:
    primitive_tuple = tuple(primitives)
    bounds = None
    points = [
        point
        for primitive in primitive_tuple
        if isinstance(primitive, LinePrimitive | ArcPrimitive)
        for point in (primitive.start, primitive.end)
    ]
    if points:
        bounds = BoundingBox(
            minimum=Point(
                x=min(point.x for point in points),
                y=min(point.y for point in points),
            ),
            maximum=Point(
                x=max(point.x for point in points),
                y=max(point.y for point in points),
            ),
        )
    return PCBLayer(
        layer_id="layer-outline",
        source_file_id=SOURCE_ID,
        role=LayerRole.BOARD_OUTLINE if trusted else LayerRole.UNKNOWN,
        side=(BoardSide.NOT_APPLICABLE if trusted else BoardSide.UNKNOWN),
        mapping_confidence=0.99 if trusted else 0.0,
        primitives=primitive_tuple,
        bounding_box=bounds,
    )


def reconstruct(outline_layer: PCBLayer) -> OutlineReconstruction:
    return reconstruct_board_outline(
        (outline_layer,),
        closure_tolerance_mm=0.01,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
    )


def test_closed_rectangle_reconstructs_stable_outer_outline() -> None:
    result = reconstruct(layer(square("outer", (0.0, 0.0), (10.0, 5.0))))

    assert result.outline is not None
    assert result.outline.outer_contour_count == 1
    assert result.outline.contours[0].kind == "outer"
    assert result.outline.contours[0].closed
    assert len(result.outline.contours[0].segments) == 4
    assert result.outline.bounding_box.maximum == Point(x=10.0, y=5.0)
    assert result.outline.measurement_error_mm == 0.0
    assert not result.uncertainties
    assert type(result).model_validate_json(result.model_dump_json()) == result


def test_nested_loop_is_cutout_not_second_outer() -> None:
    primitives = (
        *square("outer", (0.0, 0.0), (10.0, 10.0)),
        *square("inner", (2.0, 2.0), (4.0, 4.0)),
    )

    result = reconstruct(layer(primitives))

    assert result.outline is not None
    assert result.outline.outer_contour_count == 1
    assert [contour.kind for contour in result.outline.contours] == [
        "outer",
        "cutout",
    ]
    assert not result.uncertainties


def test_disjoint_outer_loops_are_reconstructed_but_uncertain() -> None:
    primitives = (
        *square("first", (0.0, 0.0), (2.0, 2.0)),
        *square("second", (5.0, 0.0), (7.0, 2.0)),
    )

    result = reconstruct(layer(primitives))

    assert result.outline is not None
    assert result.outline.outer_contour_count == 2
    assert result.uncertainties[0].risk_mode is RiskMode.OUTLINE_UNCERTAIN
    assert "Multiple disjoint" in result.uncertainties[0].summary


def test_small_endpoint_gap_is_snapped_with_error_bound() -> None:
    result = reconstruct(
        layer(
            square(
                "outer",
                (0.0, 0.0),
                (10.0, 5.0),
                closing_gap=0.006,
            )
        )
    )

    assert result.outline is not None
    assert 0.0 < result.outline.measurement_error_mm <= 0.006
    contour = result.outline.contours[0]
    assert contour.points[0] == contour.points[-1]


@pytest.mark.parametrize(
    "primitives",
    [
        square("open", (0.0, 0.0), (10.0, 5.0), closing_gap=0.02),
        (
            *square("outer", (0.0, 0.0), (10.0, 5.0)),
            line("branch", (0.0, 0.0), (-1.0, 0.0)),
        ),
    ],
)
def test_open_and_branching_graphs_remain_uncertain(
    primitives: tuple[LinePrimitive, ...],
) -> None:
    result = reconstruct(layer(primitives))

    assert result.outline is None
    assert result.uncertainties[0].risk_mode is RiskMode.OUTLINE_UNCERTAIN
    assert "non-cycle degrees" in result.uncertainties[0].summary


def test_quarter_arc_outline_retains_arc_and_chord_error() -> None:
    arc = ArcPrimitive(
        primitive_id="arc-1",
        start=Point(x=1.0, y=0.0),
        end=Point(x=0.0, y=1.0),
        center=Point(x=0.0, y=0.0),
        clockwise=False,
        aperture=APERTURE,
        polarity=Polarity.DARK,
        provenance=provenance("arc-1"),
    )
    primitives = (
        arc,
        line("line-1", (0.0, 1.0), (0.0, 0.0)),
        line("line-2", (0.0, 0.0), (1.0, 0.0)),
    )

    result = reconstruct(layer(primitives))

    assert result.outline is not None
    contour = result.outline.contours[0]
    assert any(segment.kind == "arc" for segment in contour.segments)
    assert 0.0 < contour.approximation_error_mm <= 0.001
    assert len(contour.points) > len(contour.segments)


def test_untrusted_or_unsupported_outline_is_not_guessed() -> None:
    untrusted = reconstruct(layer(square("outer", (0, 0), (1, 1)), trusted=False))
    flash = FlashPrimitive(
        primitive_id="flash-1",
        position=Point(x=0.0, y=0.0),
        aperture=APERTURE,
        polarity=Polarity.DARK,
        provenance=provenance("flash-1"),
    )
    unsupported = reconstruct(layer((*square("outer", (0, 0), (1, 1)), flash)))

    assert untrusted.outline is None
    assert "No trusted" in untrusted.uncertainties[0].summary
    assert unsupported.outline is None
    assert "unsupported" in unsupported.uncertainties[0].summary


def test_multiple_trusted_outline_layers_require_confirmation() -> None:
    first = layer(square("first", (0, 0), (1, 1)))
    second = first.model_copy(
        update={
            "layer_id": "layer-outline-2",
            "source_file_id": "src-fedcba9876543210",
        }
    )

    result = reconstruct_board_outline(
        (first, second),
        closure_tolerance_mm=0.01,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
    )

    assert result.outline is None
    assert "Multiple trusted" in result.uncertainties[0].summary


def test_invalid_tolerance_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        reconstruct_board_outline(
            (layer(square("outer", (0, 0), (1, 1))),),
            closure_tolerance_mm=0.0,
            arc_chord_error_mm=0.001,
            geometry_epsilon_mm=0.001,
        )
