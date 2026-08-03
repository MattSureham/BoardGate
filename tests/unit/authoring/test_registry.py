"""Complete, exact-version deterministic modification executor registry."""

import pytest

from boardgate.application.modification_registry import (
    ExcellonToolDiameterExecutor,
    OperationRegistryError,
    registered_operation_keys,
    resolve_operation_executor,
    resolve_operation_executor_key,
    validate_operation_registry,
)
from boardgate.authoring.models import MODIFICATION_OPERATION_KEYS

from .test_models_identifiers import operation


def test_registry_is_complete_and_resolves_the_admitted_operation() -> None:
    validate_operation_registry()

    assert registered_operation_keys() == MODIFICATION_OPERATION_KEYS
    assert isinstance(
        resolve_operation_executor(operation()),
        ExcellonToolDiameterExecutor,
    )


@pytest.mark.parametrize(
    ("kind", "version"),
    (
        ("set_excellon_tool_diameter", "2.0"),
        ("raw_text_patch", "1.0"),
    ),
)
def test_registry_rejects_unknown_kinds_and_versions_without_fallback(
    kind: str,
    version: str,
) -> None:
    with pytest.raises(OperationRegistryError) as caught:
        resolve_operation_executor_key(kind, version)

    assert caught.value.code == "MODIFICATION_OPERATION_UNREGISTERED"
