"""AppBlueprint layout rendering tests (no live Odoo)."""

from odoo_client.blueprint import FormGroupLayout, ModelFormLayout, render_layout_form_arch


def test_render_layout_form_arch_groups_and_o2m() -> None:
    arch = render_layout_form_arch(
        ModelFormLayout(
            model="x_lib_book",
            string="Book",
            groups=[
                FormGroupLayout(string="Identity", fields=["x_name", "x_author_id"]),
                FormGroupLayout(
                    string="Catalog",
                    fields=["x_barcode"],
                    widgets={"x_barcode": "barcode"},
                ),
                FormGroupLayout(string="Loans", fields=["x_loan_ids"]),
            ],
            o2m_lists={"x_loan_ids": ["x_name", "x_due_date"]},
        )
    )
    assert 'group string="Identity"' in arch
    assert 'widget="barcode"' in arch
    assert "<list>" in arch
    assert 'name="x_due_date"' in arch


def test_render_layout_form_arch_o2m_tree_for_17() -> None:
    arch = render_layout_form_arch(
        ModelFormLayout(
            model="x_lib_book",
            string="Book",
            groups=[FormGroupLayout(string="Loans", fields=["x_loan_ids"])],
            o2m_lists={"x_loan_ids": ["x_name"]},
        ),
        list_root="tree",
    )
    assert "<tree>" in arch
    assert "<list>" not in arch
