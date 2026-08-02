"""Parametrized views adapter tests for normalize_view_mode / list_arch_root (16–19)."""

from __future__ import annotations

import pytest

from odoo_client.compat.adapters import views_v16, views_v17, views_v18, views_v19

_TREE_MAJORS = (
    (16, views_v16),
    (17, views_v17),
)
_LIST_MAJORS = (
    (18, views_v18),
    (19, views_v19),
)


@pytest.mark.parametrize("major,mod", _TREE_MAJORS)
def test_list_arch_root_tree_on_le17(major: int, mod: object) -> None:
    assert mod.list_arch_root() == "tree", major  # type: ignore[attr-defined]
    assert mod.list_arch_root("list") == "tree", major  # type: ignore[attr-defined]
    assert mod.list_arch_root("tree") == "tree", major  # type: ignore[attr-defined]


@pytest.mark.parametrize("major,mod", _LIST_MAJORS)
def test_list_arch_root_list_on_ge18(major: int, mod: object) -> None:
    assert mod.list_arch_root() == "list", major  # type: ignore[attr-defined]
    assert mod.list_arch_root("list") == "list", major  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "major,mod,inp,expected",
    [
        (16, views_v16, "list,form", "tree,form"),
        (16, views_v16, "tree,form", "tree,form"),
        (16, views_v16, "list,kanban,form", "tree,kanban,form"),
        (16, views_v16, "", "tree,form"),
        (16, views_v16, "   ", "tree,form"),
        (16, views_v16, "list", "tree"),
        (17, views_v17, "list,form", "tree,form"),
        (17, views_v17, "kanban,list,form", "kanban,tree,form"),
        (18, views_v18, "list,form", "list,form"),
        (18, views_v18, "tree,form", "list,form"),
        (18, views_v18, "", "list,form"),
        (18, views_v18, "tree,kanban,form", "list,kanban,form"),
        (19, views_v19, "list,form", "list,form"),
        (19, views_v19, "tree,form", "list,form"),
        (19, views_v19, "tree", "list"),
        (19, views_v19, "form,tree,kanban", "form,list,kanban"),
    ],
)
def test_normalize_view_mode_matrix(
    major: int, mod: object, inp: str, expected: str
) -> None:
    assert mod.normalize_view_mode(inp) == expected, (major, inp)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "major,mod,expected",
    [
        (16, views_v16, "tree,form"),
        (17, views_v17, "tree,form"),
        (18, views_v18, "list,form"),
        (19, views_v19, "list,form"),
    ],
)
def test_default_window_view_mode(major: int, mod: object, expected: str) -> None:
    assert mod.default_window_view_mode() == expected, major  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "major,mod,view_type,expected",
    [
        (16, views_v16, "list", ["tree", "list"]),
        (16, views_v16, "tree", ["tree", "list"]),
        (16, views_v16, "form", ["form"]),
        (17, views_v17, "list", ["tree", "list"]),
        (18, views_v18, "list", ["list", "tree"]),
        (19, views_v19, "list", ["list", "tree"]),
        (19, views_v19, "form", ["form"]),
    ],
)
def test_list_type_fallbacks(
    major: int, mod: object, view_type: str, expected: list[str]
) -> None:
    assert mod.list_type_fallbacks(view_type) == expected, major  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "major,mod,expected",
    [
        (16, views_v16, ["form", "tree", "search"]),
        (17, views_v17, ["form", "tree", "search"]),
        (18, views_v18, ["form", "list", "search"]),
        (19, views_v19, ["form", "list", "search"]),
    ],
)
def test_default_field_inject_view_types(
    major: int, mod: object, expected: list[str]
) -> None:
    assert mod.default_field_inject_view_types() == expected, major  # type: ignore[attr-defined]


def test_v16_and_v19_normalize_disagree_on_list_token() -> None:
    assert views_v16.normalize_view_mode("list,form") == "tree,form"
    assert views_v19.normalize_view_mode("list,form") == "list,form"
    assert views_v16.normalize_view_mode("tree,form") == "tree,form"
    assert views_v19.normalize_view_mode("tree,form") == "list,form"
