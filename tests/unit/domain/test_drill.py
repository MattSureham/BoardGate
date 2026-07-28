"""Drill domain shape tests."""

import pytest
from pydantic import ValidationError

from boardgate.domain.drill import DrillSlot
from boardgate.domain.geometry import Point
from boardgate.domain.provenance import Provenance


def slot_data() -> dict[str, object]:
    return {
        "slot_id": "slot-1",
        "start": Point(x=0.0, y=0.0),
        "end": Point(x=1.0, y=0.0),
        "width_mm": 0.3,
        "provenance": Provenance(
            source_file_id="src-0123456789abcdef",
            parser="test",
            parser_version="1",
        ),
    }


def test_arc_slot_requires_center_and_direction() -> None:
    with pytest.raises(ValidationError, match="arc slots require"):
        DrillSlot.model_validate({"kind": "arc", **slot_data()})

    arc = DrillSlot.model_validate(
        {
            "kind": "arc",
            "center": Point(x=0.5, y=0.5),
            "clockwise": True,
            **slot_data(),
        }
    )
    assert arc.center == Point(x=0.5, y=0.5)


def test_line_slot_rejects_arc_metadata() -> None:
    with pytest.raises(ValidationError, match="line slots"):
        DrillSlot.model_validate(
            {
                "center": Point(x=0.5, y=0.5),
                **slot_data(),
            }
        )
