from app.bridge.mapping import apply_transform, preview, suggest, validate_mapping

ODOO = {
    "name": {"type": "char", "string": "Name", "required": True},
    "email": {"type": "char", "string": "Email"},
    "phone": {"type": "char", "string": "Phone"},
    "list_price": {"type": "float", "string": "Sales Price"},
    "is_company": {"type": "boolean", "string": "Is a Company"},
    "partner_id": {"type": "many2one", "string": "Customer"},
    "display_name": {"type": "char", "readonly": True, "store": False},
}
REMOTE = {
    "full_name": "char",
    "email_address": "char",
    "price": "integer",
    "customer": "many2one",
    "zzz": "char",
    "vip": "boolean",
}


def test_suggest():
    m = {x["remote"]: x for x in suggest(REMOTE, ODOO)}
    assert m["full_name"]["odoo"] == "name" and m["email_address"]["odoo"] == "email"
    assert m["price"]["odoo"] == "list_price" and m["price"]["transform"] == "to_float"
    assert (
        m["customer"]["odoo"] == "partner_id"
        and m["zzz"]["odoo"] is None
        and m["zzz"]["needs_review"]
    )


def test_validate_refuses():
    errs = validate_mapping(
        [{"remote": "vip", "odoo": "email"}, {"remote": "price", "odoo": "nope"}], REMOTE, ODOO
    )
    assert (
        any("can't go into" in e for e in errs)
        and any("nope" in e for e in errs)
        and any("Required" in e for e in errs)
    )
    assert (
        validate_mapping(
            [{"remote": "full_name", "odoo": "name", "transform": "trim"}], REMOTE, ODOO
        )
        == []
    )


def test_transforms_preview():
    assert (
        apply_transform("cents_to_units", 1999) == 19.99
        and apply_transform("to_date", "2026-10-01T09:00:00Z") == "2026-10-01"
    )
    p = preview(
        [{"remote": "price", "odoo": "list_price", "transform": "to_float"}],
        [{"price": "12"}, {"price": "x"}],
    )
    assert p[0]["values"] == {"list_price": 12.0} and p[1]["problems"]
