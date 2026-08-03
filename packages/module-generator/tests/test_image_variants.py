"""CMP-6 module generator image variant emission."""

from __future__ import annotations

from module_generator import (
    ActionSpec,
    FieldSpec,
    ModelSpec,
    ModuleSpec,
    ViewSpec,
    ensure_image_variant_fields,
    render_module_files,
)


def _spec_with_photo_kanban() -> ModuleSpec:
    return ModuleSpec(
        technical_name="x_image_demo",
        display_name="Image Demo",
        depends=["base"],
        models=[
            ModelSpec(
                model="x_staff",
                description="Staff",
                fields=[
                    FieldSpec(
                        name="x_photo",
                        ttype="binary",
                        string="Photo",
                        is_image=True,
                        image_role="avatar",
                    ),
                    FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                ],
            )
        ],
        views=[
            ViewSpec(
                name="x_staff.kanban",
                model="x_staff",
                type="kanban",
                arch='<kanban><templates><t t-name="card"><field name="x_name"/></t></templates></kanban>',
            ),
            ViewSpec(
                name="x_staff.form",
                model="x_staff",
                type="form",
                arch="<form><sheet><field name=\"x_photo\"/></sheet></form>",
            ),
        ],
        actions=[
            ActionSpec(
                name="Staff",
                model="x_staff",
                view_mode="kanban,form",
            )
        ],
    )


def test_ensure_image_variant_fields_adds_128_and_256() -> None:
    spec = _spec_with_photo_kanban()
    ensure_image_variant_fields(spec)
    names = {f.name for f in spec.models[0].fields}
    assert "x_photo_128" in names
    assert "x_photo_256" in names


def test_render_module_emits_image_and_variants() -> None:
    spec = _spec_with_photo_kanban()
    files = render_module_files(spec)
    model_py = files["x_image_demo/models/x_staff.py"]
    assert "x_photo = fields.Image(" in model_py
    assert "x_photo_128 = fields.Image(" in model_py
    assert "related='x_photo'" in model_py
    assert "max_width=128" in model_py
