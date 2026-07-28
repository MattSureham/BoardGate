"""Deterministic identifier helper tests."""

from boardgate.domain.identifiers import object_id, project_id, source_file_id


def test_source_and_project_ids_are_reproducible() -> None:
    digest_a = "a" * 64
    digest_b = "b" * 64

    assert source_file_id("a.gtl", digest_a) == source_file_id("a.gtl", digest_a)
    assert project_id([("b.gbl", digest_b), ("a.gtl", digest_a)]) == project_id(
        [("a.gtl", digest_a), ("b.gbl", digest_b)]
    )


def test_object_id_changes_with_evidence() -> None:
    first = object_id("line", "src-0123456789abcdef", 1, "D01")
    second = object_id("line", "src-0123456789abcdef", 2, "D01")

    assert first.startswith("line-")
    assert first != second
