"""Field modifier emission — Odoo 16 attrs= vs 17+ direct attributes."""

from odoo_client.field_attrs import emit_field_modifiers


def test_major16_static_required_uses_attrs() -> None:
    out = emit_field_modifiers(major=16, required=True)
    assert "attrs" in out
    assert "required" in out["attrs"]


def test_major19_static_required_direct() -> None:
    out = emit_field_modifiers(major=19, required=True)
    assert out.get("required") == "1"
    assert "attrs" not in out


def test_major16_conditional_invisible_domain() -> None:
    out = emit_field_modifiers(major=16, invisible="[('state', '=', 'draft')]")
    assert "attrs" in out
    assert "invisible" in out["attrs"]


def test_major19_conditional_invisible_expr() -> None:
    out = emit_field_modifiers(major=19, invisible="[('state', '=', 'draft')]")
    assert out.get("invisible") == "state == 'draft'"


def test_major19_readonly_domain() -> None:
    out = emit_field_modifiers(major=18, readonly="[('active', '=', False)]")
    assert "readonly" in out
    assert "active" in out["readonly"]


def test_major19_required_domain() -> None:
    out = emit_field_modifiers(major=19, required="[('x_status', '=', 'done')]")
    assert out.get("required")
    assert "x_status" in out["required"]


def test_empty_invisible_omitted() -> None:
    out = emit_field_modifiers(major=19, invisible="  ")
    assert "invisible" not in out


def test_major19_always_invisible_emits_one() -> None:
    out = emit_field_modifiers(major=19, invisible=True)
    assert out.get("invisible") == "1"


def test_major16_always_invisible_uses_attrs() -> None:
    out = emit_field_modifiers(major=16, invisible=True)
    assert "attrs" in out
    assert "invisible" in out["attrs"]


def test_field_xml_emits_label_widget_options_modifiers() -> None:
    from odoo_client.view_arch import FieldNode, _field_xml

    xml = _field_xml(
        FieldNode(
            name="x_photo",
            string="Photo",
            required=True,
            readonly="[('state', '=', 'done')]",
            invisible="[('active', '=', False)]",
            widget="image",
            options='{"size": [128, 128]}',
            help="Company logo",
            placeholder="Drop an image",
            class_name="oe_avatar",
            groups="base.group_user",
        ),
        major=19,
    )
    assert 'name="x_photo"' in xml
    assert 'string="Photo"' in xml
    assert 'required="1"' in xml
    assert 'widget="image"' in xml
    assert "128" in xml
    assert "readonly" in xml
    assert "invisible" in xml
    assert 'help="Company logo"' in xml
    assert 'placeholder="Drop an image"' in xml
    assert 'class="oe_avatar"' in xml
    assert 'groups="base.group_user"' in xml


def test_additive_inherit_preserves_field_properties() -> None:
    from odoo_client.view_arch import (
        FieldNode,
        FormViewSpec,
        GroupNode,
        build_additive_form_inherit_arch,
    )

    arch = build_additive_form_inherit_arch(
        FormViewSpec(
            string="Form",
            children=[
                GroupNode(
                    string="Props",
                    children=[
                        FieldNode(
                            name="x_code",
                            string="Scan code",
                            required=True,
                            widget="barcode",
                            help="Scan the shelf tag",
                            placeholder="Code",
                            class_name="oe_inline",
                            groups="base.group_user",
                        )
                    ],
                )
            ],
        ),
        existing_field_names=set(),
    )
    assert 'string="Scan code"' in arch
    assert 'required="1"' in arch
    assert 'widget="barcode"' in arch
    assert 'name="x_code"' in arch
    assert 'help="Scan the shelf tag"' in arch
    assert 'placeholder="Code"' in arch
    assert 'class="oe_inline"' in arch
    assert 'groups="base.group_user"' in arch
