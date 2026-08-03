"""Golden README for generated modules (PROD-2)."""

from __future__ import annotations

from module_generator import FieldSpec, ModelSpec, ModuleSpec, build_module_zip
from module_generator.readme import render_module_readme


def test_readme_golden_sections() -> None:
    spec = ModuleSpec(
        technical_name="demo_library",
        display_name="Demo Library",
        depends=["base", "contacts"],
        models=[
            ModelSpec(
                model="x_book",
                description="Book",
                fields=[FieldSpec(name="x_name", ttype="char", string="Title")],
            )
        ],
    )
    readme = render_module_readme(spec, odoo_major=19)
    assert "## What was generated" in readme
    assert "## Install steps" in readme
    assert "## Module contents map" in readme
    assert "## Hand to your developer" in readme
    assert "`x_book`" in readme
    assert "Self-hosted" in readme


def test_readme_in_zip() -> None:
    spec = ModuleSpec(
        technical_name="readme_demo",
        display_name="Readme Demo",
        depends=["base"],
        models=[
            ModelSpec(
                model="x_item",
                description="Item",
                fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
            )
        ],
    )
    import io
    import zipfile

    z = build_module_zip(spec, odoo_major=19)
    with zipfile.ZipFile(io.BytesIO(z)) as zf:
        names = zf.namelist()
    assert "readme_demo/README.md" in names
    with zipfile.ZipFile(io.BytesIO(z)) as zf:
        body = zf.read("readme_demo/README.md").decode()
    assert "Hand to your developer" in body
