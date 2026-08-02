"""Module export targets connection major (one zip — not multi-manifest)."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from module_generator import (
    ActionSpec,
    FieldSpec,
    ModelSpec,
    ModuleSpec,
    ViewSpec,
    build_module_zip,
    list_view_for_major,
    manifest_version_for_major,
    normalize_module_spec_list_views,
    render_module_files,
    render_xpath_fields_inject,
)


@pytest.mark.parametrize(
    "major,expected",
    [
        (16, "16.0.1.0.0"),
        (17, "17.0.1.0.0"),
        (18, "18.0.1.0.0"),
        (19, "19.0.1.0.0"),
        (20, "20.0.1.0.0"),  # version string only — export floor still gated elsewhere
    ],
)
def test_manifest_version_for_major(major: int, expected: str) -> None:
    assert manifest_version_for_major(major) == expected


@pytest.mark.parametrize("major", [15, 14, 0, -1])
def test_manifest_version_for_major_refuses_below_16(major: int) -> None:
    with pytest.raises(ValueError, match="Unsupported Odoo major for module export"):
        manifest_version_for_major(major)


def test_xpath_list_vs_tree_roots() -> None:
    assert "//list" in render_xpath_fields_inject(["x_a"], "list")
    assert "//tree" in render_xpath_fields_inject(["x_a"], "tree")


@pytest.mark.parametrize(
    "major,expected",
    [
        (16, ("tree", "tree")),
        (17, ("tree", "tree")),
        (18, ("list", "list")),
        (19, ("list", "list")),
    ],
)
def test_list_view_for_major(major: int, expected: tuple[str, str]) -> None:
    assert list_view_for_major(major) == expected


@pytest.mark.parametrize("major", [15, 14, 0])
def test_list_view_for_major_refuses_below_16(major: int) -> None:
    with pytest.raises(ValueError, match="Unsupported Odoo major for list views"):
        list_view_for_major(major)


def test_normalize_module_spec_list_views_rewrites_for_16() -> None:
    spec = ModuleSpec(
        technical_name="smoke_m16",
        display_name="Smoke 16",
        version=manifest_version_for_major(16),
        odoo_major=16,
        models=[
            ModelSpec(
                model="x_smoke",
                description="Smoke",
                fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
            )
        ],
        views=[
            ViewSpec(
                name="x_smoke.list",
                model="x_smoke",
                type="list",
                arch='<list string="Smoke"><field name="x_name"/></list>',
            ),
            ViewSpec(
                name="x_smoke.form",
                model="x_smoke",
                type="form",
                arch=(
                    '<form><sheet><field name="x_line_ids">'
                    '<list><field name="x_name"/></list>'
                    "</field></sheet></form>"
                ),
            ),
        ],
        actions=[
            ActionSpec(name="Smoke", model="x_smoke", view_mode="list,form"),
        ],
    )
    normalize_module_spec_list_views(spec)
    listing = next(v for v in spec.views if v.name == "x_smoke.list")
    assert listing.type == "tree"
    assert listing.arch.startswith("<tree")
    assert "</tree>" in listing.arch
    form = next(v for v in spec.views if v.name == "x_smoke.form")
    assert "<tree>" in form.arch
    assert "<list>" not in form.arch
    assert spec.actions[0].view_mode == "tree,form"


def test_build_module_zip_odoo_major_kwarg_normalizes() -> None:
    spec = ModuleSpec(
        technical_name="smoke_m17",
        display_name="Smoke 17",
        version="17.0.1.0.0",
        models=[
            ModelSpec(
                model="x_smoke",
                description="Smoke",
                fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
            )
        ],
        views=[
            ViewSpec(
                name="x_smoke.list",
                model="x_smoke",
                type="list",
                arch='<list string="Smoke"><field name="x_name"/></list>',
            ),
        ],
    )
    raw = build_module_zip(spec, odoo_major=17)
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        views_xml = zf.read("smoke_m17/views/views.xml").decode()
    assert ">tree<" in views_xml or 'name="type">tree</field>' in views_xml
    assert "<tree" in views_xml
    assert 'name="type">list</field>' not in views_xml


def test_library_unchanged_without_odoo_major() -> None:
    """Library templates stay 19-primary when odoo_major is unset."""
    from module_generator import library_module_spec

    spec = library_module_spec("library_mgmt", "Library")
    assert spec.odoo_major is None
    files = render_module_files(spec)
    xml = files["library_mgmt/views/views.xml"]
    assert 'name="type">list</field>' in xml
    assert "<list" in xml


def test_normalize_module_spec_noop_without_odoo_major() -> None:
    spec = ModuleSpec(
        technical_name="noop",
        display_name="Noop",
        version="19.0.1.0.0",
        odoo_major=None,
        models=[],
        views=[
            ViewSpec(
                name="x.list",
                model="x",
                type="list",
                arch='<list><field name="x_name"/></list>',
            )
        ],
        actions=[ActionSpec(name="X", model="x", view_mode="list,form")],
    )
    normalize_module_spec_list_views(spec)
    assert spec.views[0].type == "list"
    assert spec.views[0].arch.startswith("<list")
    assert spec.actions[0].view_mode == "list,form"


@pytest.mark.parametrize("major", [18, 19])
def test_normalize_module_spec_list_views_keeps_list_on_ge18(major: int) -> None:
    spec = ModuleSpec(
        technical_name=f"smoke_m{major}",
        display_name=f"Smoke {major}",
        version=manifest_version_for_major(major),
        odoo_major=major,
        models=[
            ModelSpec(
                model="x_smoke",
                description="Smoke",
                fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
            )
        ],
        views=[
            ViewSpec(
                name="x_smoke.list",
                model="x_smoke",
                type="tree",
                arch='<tree string="Smoke"><field name="x_name"/></tree>',
            ),
        ],
        actions=[
            ActionSpec(name="Smoke", model="x_smoke", view_mode="tree,form"),
        ],
    )
    normalize_module_spec_list_views(spec)
    listing = next(v for v in spec.views if v.name == "x_smoke.list")
    assert listing.type == "list"
    assert listing.arch.startswith("<list")
    assert "</list>" in listing.arch
    assert "<tree" not in listing.arch
    assert spec.actions[0].view_mode == "list,form"


def test_normalize_dedupes_list_tree_in_view_mode() -> None:
    spec = ModuleSpec(
        technical_name="dedupe",
        display_name="Dedupe",
        version=manifest_version_for_major(16),
        odoo_major=16,
        models=[],
        views=[],
        actions=[
            ActionSpec(name="A", model="x", view_mode="list,tree,form"),
        ],
    )
    normalize_module_spec_list_views(spec)
    assert spec.actions[0].view_mode == "tree,form"
