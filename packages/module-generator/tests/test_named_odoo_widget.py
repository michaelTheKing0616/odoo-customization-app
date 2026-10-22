"""Named Odoo widgets stay on the generated view. No second view generator."""

from __future__ import annotations

from module_generator import (
    FieldSpec,
    ModelSpec,
    ModuleSpec,
    ViewSpec,
    render_module_files,
    render_xpath_field_inject,
    render_xpath_fields_inject,
    resolve_named_widget,
)


def test_named_widget_is_emitted_on_generated_view() -> None:
    arch = render_xpath_field_inject("x_priority", "form", widget="priority")
    assert 'widget="priority"' in arch
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_named_widget",
            display_name="Named Widget",
            models=[
                ModelSpec(
                    model="sale.order",
                    description="Sales Order",
                    mode="inherit",
                    inherit="sale.order",
                    fields=[
                        FieldSpec(name="x_priority", ttype="selection", string="Priority")
                    ],
                )
            ],
            views=[
                ViewSpec(
                    name="sale.order.form.priority",
                    model="sale.order",
                    type="form",
                    arch=arch,
                    inherit_xml_id="sale.view_order_form",
                    mode="extension",
                )
            ],
        )
    )
    views_xml = files["demo_named_widget/views/views.xml"]
    assert 'name="x_priority"' in views_xml
    assert 'widget="priority"' in views_xml
    assert 'widget="char"' not in views_xml
    assert 'widget="text"' not in views_xml


def test_generic_standin_does_not_replace_named_widget() -> None:
    assert resolve_named_widget("monetary", standin="char") == "monetary"
    assert resolve_named_widget("priority", standin="text") == "priority"
    assert resolve_named_widget("barcode", standin="input") == "barcode"
    arch = render_xpath_field_inject(
        "x_amount", "form", widget="monetary", standin="char"
    )
    files = render_module_files(
        ModuleSpec(
            technical_name="demo_keep_monetary",
            display_name="Keep Monetary",
            models=[
                ModelSpec(
                    model="x_bill",
                    description="Bill",
                    fields=[
                        FieldSpec(name="x_name", ttype="char", string="Name", required=True),
                        FieldSpec(name="x_amount", ttype="monetary", string="Amount"),
                    ],
                )
            ],
            views=[
                ViewSpec(
                    name="x_bill.form",
                    model="x_bill",
                    type="form",
                    arch=f"<form><sheet>{arch}</sheet></form>",
                )
            ],
        )
    )
    views_xml = files["demo_keep_monetary/views/views.xml"]
    assert 'widget="monetary"' in views_xml
    assert 'widget="char"' not in views_xml


def test_named_widgets_dict_survives_multi_field_inject() -> None:
    arch = render_xpath_fields_inject(
        ["x_barcode", "x_notes"],
        "form",
        widgets={"x_barcode": "barcode"},
        standin="char",
    )
    assert 'name="x_barcode" widget="barcode"' in arch
    assert 'name="x_notes"/>' in arch
    assert 'widget="char"' not in arch
