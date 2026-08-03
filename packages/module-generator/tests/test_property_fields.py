"""CMP-7 module generator properties emission."""

from __future__ import annotations

from module_generator import FieldSpec, ModelSpec, ModuleSpec, render_module_files


def test_render_properties_fields() -> None:
    spec = ModuleSpec(
        technical_name="x_prop_demo",
        display_name="Prop Demo",
        depends=["base"],
        models=[
            ModelSpec(
                model="x_parent",
                description="Parent",
                fields=[
                    FieldSpec(
                        name="x_properties_definition",
                        ttype="properties_definition",
                        string="Definition",
                    ),
                ],
            ),
            ModelSpec(
                model="x_child",
                description="Child",
                fields=[
                    FieldSpec(
                        name="x_parent_id",
                        ttype="many2one",
                        string="Parent",
                        relation="x_parent",
                    ),
                    FieldSpec(
                        name="x_properties",
                        ttype="properties",
                        string="Properties",
                        definition_record="x_parent_id",
                        definition_record_field="x_properties_definition",
                    ),
                ],
            ),
        ],
    )
    files = render_module_files(spec)
    parent_py = files["x_prop_demo/models/x_parent.py"]
    child_py = files["x_prop_demo/models/x_child.py"]
    assert "fields.PropertiesDefinition" in parent_py
    assert "fields.Properties" in child_py
    assert "definition=" in child_py
