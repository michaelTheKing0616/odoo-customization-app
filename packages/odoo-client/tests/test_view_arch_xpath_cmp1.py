"""CMP-1 xpath move and $0-wrap helpers."""

from odoo_client.view_arch import (
    render_inherit_xpath_arch,
    render_xpath_move_arch,
    render_xpath_wrap_arch,
    validate_xpath_arch,
)


def test_render_xpath_move_arch() -> None:
    arch = render_xpath_move_arch(expr="//field[@name='x_status']")
    assert 'position="move"' in arch
    assert validate_xpath_arch(arch) == []


def test_render_xpath_wrap_arch_with_dollar_zero() -> None:
    arch = render_xpath_wrap_arch(
        expr="//field[@name='partner_id']",
        wrapper_xml=(
            '<div class="o_row">$0<button name="action_go" type="object" string="Go"/></div>'
        ),
    )
    assert "$0" in arch
    assert 'position="replace"' in arch
    assert validate_xpath_arch(arch) == []


def test_render_xpath_wrap_requires_dollar_zero() -> None:
    try:
        render_xpath_wrap_arch(
            expr="//field[@name='x']",
            wrapper_xml="<div><field name='x'/></div>",
        )
    except ValueError as exc:
        assert "$0" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_validate_xpath_rejects_empty_non_move_body() -> None:
    arch = render_inherit_xpath_arch(
        expr="//sheet",
        position="inside",
        body_xml="<field name='x'/>",
    )
    assert validate_xpath_arch(arch) == []
    bad = (
        "<data>\n"
        '  <xpath expr="//sheet" position="inside">\n'
        "  </xpath>\n"
        "</data>"
    )
    issues = validate_xpath_arch(bad)
    assert any("empty" in i.lower() for i in issues)
