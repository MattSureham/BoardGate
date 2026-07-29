"""Properties for safe, stable logical-path normalization."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import DrawFn, SearchStrategy

from boardgate.ingestion.errors import IngestionError
from boardgate.ingestion.paths import normalize_logical_path

SAFE_COMPONENT = st.text(
    alphabet=st.sampled_from(
        tuple("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    ),
    min_size=0,
    max_size=19,
).map(lambda suffix: f"a{suffix}")


@st.composite
def redundant_safe_paths(draw: DrawFn) -> tuple[str, str]:
    """Build safe paths with removable dot segments and duplicate separators."""
    parts = draw(st.lists(SAFE_COMPONENT, min_size=1, max_size=5))
    separator_widths = draw(
        st.lists(
            st.integers(min_value=1, max_value=3),
            min_size=len(parts) - 1,
            max_size=len(parts) - 1,
        )
    )
    prefix = "./" * draw(st.integers(min_value=0, max_value=3))
    raw = prefix + parts[0]
    for width, part in zip(separator_widths, parts[1:], strict=True):
        raw += "/" * width + part
    return raw, "/".join(parts)


@st.composite
def unsafe_paths(draw: DrawFn) -> str:
    """Inject an unsafe root, traversal, or platform-specific separator."""
    parts = draw(st.lists(SAFE_COMPONENT, min_size=1, max_size=4))
    safe = "/".join(parts)
    mutation: SearchStrategy[str] = st.sampled_from(
        (
            f"../{safe}",
            f"{parts[0]}/../{safe}",
            f"/{safe}",
            f"C:/{safe}",
            f"{parts[0]}\\{safe}",
        )
    )
    return draw(mutation)


@given(case=redundant_safe_paths())
@settings(derandomize=True)
def test_normalization_is_canonical_and_idempotent(
    case: tuple[str, str],
) -> None:
    raw, expected = case

    normalized = normalize_logical_path(raw, subject="property-input")

    assert normalized == expected
    assert (
        normalize_logical_path(
            normalized,
            subject="property-input",
        )
        == normalized
    )


@given(path=unsafe_paths())
@settings(derandomize=True)
def test_generated_unsafe_paths_are_rejected(path: str) -> None:
    with pytest.raises(IngestionError) as caught:
        normalize_logical_path(path, subject="property-input")

    assert caught.value.code == "UNSAFE_PATH"
