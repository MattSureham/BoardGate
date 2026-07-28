"""BOM and component-placement domain invariants."""

import pytest
from pydantic import ValidationError

from boardgate.domain.component import BOMItem, ComponentPlacement
from boardgate.domain.enums import BoardSide
from boardgate.domain.geometry import Point
from boardgate.domain.provenance import Provenance


def make_provenance() -> Provenance:
    return Provenance(
        source_file_id="src-0123456789abcdef",
        parser="test",
        parser_version="1",
    )


def test_zero_quantity_requires_dnp() -> None:
    provenance = make_provenance()

    with pytest.raises(ValidationError, match="must be marked DNP"):
        BOMItem(references=("R1",), quantity=0, provenance=provenance)

    item = BOMItem(
        references=("R1",),
        quantity=0,
        dnp=True,
        provenance=provenance,
    )
    assert item.dnp


def test_component_placement_dnp_defaults_false_for_legacy_json() -> None:
    placement = ComponentPlacement(
        reference="R1",
        position=Point(x=1.0, y=2.0),
        rotation_degrees=90.0,
        side=BoardSide.TOP,
        provenance=make_provenance(),
    )

    legacy_payload = placement.model_dump_json(exclude={"dnp"})
    restored = ComponentPlacement.model_validate_json(legacy_payload)

    assert restored.dnp is False


@pytest.mark.parametrize("dnp", [False, True])
def test_component_placement_dnp_json_round_trip(dnp: bool) -> None:
    placement = ComponentPlacement(
        reference="R1",
        position=Point(x=1.0, y=2.0),
        rotation_degrees=90.0,
        side=BoardSide.TOP,
        dnp=dnp,
        provenance=make_provenance(),
    )

    restored = ComponentPlacement.model_validate_json(placement.model_dump_json())

    assert restored == placement
    assert restored.dnp is dnp
