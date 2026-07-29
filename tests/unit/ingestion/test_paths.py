"""Logical path validation tests."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from boardgate.ingestion.errors import IngestionError
from boardgate.ingestion.paths import normalize_logical_path, path_collision_key


@pytest.mark.parametrize(
    "path",
    [
        "../board.gtl",
        "folder/../board.gtl",
        "/board.gtl",
        "\\\\server\\board.gtl",
        "C:/board.gtl",
        "folder\\board.gtl",
        "board?.gtl",
        "board.gtl.",
        "\x00board.gtl",
        "CON",
        "nul.gtl",
        "fab/Com1.txt",
        "LPT9",
    ],
)
def test_unsafe_paths_are_rejected(path: str) -> None:
    with pytest.raises(IngestionError, match="UNSAFE_PATH"):
        normalize_logical_path(path, subject="archive.zip")


def test_safe_path_is_normalized() -> None:
    assert normalize_logical_path("./fab//board.gtl", subject="input") == (
        "fab/board.gtl"
    )


@given(
    st.text(
        alphabet=st.sampled_from(
            tuple("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/._-")
        ),
        min_size=1,
    )
)
def test_collision_key_is_case_insensitive(path: str) -> None:
    assert path_collision_key(path) == path_collision_key(path.swapcase())
