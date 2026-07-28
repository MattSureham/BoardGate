"""BOM domain invariants."""

import pytest
from pydantic import ValidationError

from boardgate.domain.component import BOMItem
from boardgate.domain.provenance import Provenance


def test_zero_quantity_requires_dnp() -> None:
    provenance = Provenance(
        source_file_id="src-0123456789abcdef",
        parser="test",
        parser_version="1",
    )

    with pytest.raises(ValidationError, match="must be marked DNP"):
        BOMItem(references=("R1",), quantity=0, provenance=provenance)

    item = BOMItem(
        references=("R1",),
        quantity=0,
        dnp=True,
        provenance=provenance,
    )
    assert item.dnp
