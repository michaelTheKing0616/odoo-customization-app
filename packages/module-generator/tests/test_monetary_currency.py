"""Monetary fields auto-get currency companion in generated modules."""

from module_generator import FieldSpec, ModelSpec, ModuleSpec, ensure_monetary_currency_fields


def test_ensure_monetary_currency_fields_adds_x_currency_id() -> None:
    spec = ModuleSpec(
        technical_name="x_test",
        display_name="Test",
        models=[
            ModelSpec(
                model="x_order",
                description="Order",
                fields=[
                    FieldSpec(
                        name="x_amount",
                        ttype="monetary",
                        string="Amount",
                    ),
                ],
            )
        ],
    )
    ensure_monetary_currency_fields(spec)
    names = {f.name for f in spec.models[0].fields}
    assert "x_currency_id" in names
    assert spec.models[0].fields[-1].relation == "res.currency"
    monetary = next(f for f in spec.models[0].fields if f.name == "x_amount")
    assert monetary.currency_field == "x_currency_id"
