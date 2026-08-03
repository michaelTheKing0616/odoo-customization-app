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
