"""Wave 6 — view_has_field Live/Fake contract."""

from __future__ import annotations

from app.ai_schema_client import DenySchemaClient, FakeSchemaClient, LiveSchemaClient


def test_fake_view_has_field_present_absent() -> None:
    fake = FakeSchemaClient(
        models={"sale.order"},
        fields={"sale.order": {"partner_id": {"ttype": "many2one", "relation": "res.partner"}}},
        view_fields={"sale.order": {"partner_id", "date_order"}},
    )
    assert fake.view_has_field("sale.order", "partner_id") is True
    assert fake.view_has_field("sale.order", "x_missing") is False
    assert fake.view_has_field("res.partner", "name") is False


def test_deny_view_has_field_always_false() -> None:
    assert DenySchemaClient().view_has_field("sale.order", "partner_id") is False


def test_live_view_has_field_parses_get_views_arch() -> None:
    class _Client:
        def execute_kw(self, model, method, args, kwargs=None):
            if method == "get_views":
                return {
                    "views": {
                        "form": {
                            "arch": '<form><field name="partner_id"/><field name="date_order"/></form>'
                        }
                    }
                }
            raise AssertionError(method)

    live = LiveSchemaClient(_Client())
    assert live.view_has_field("sale.order", "partner_id") is True
    assert live.view_has_field("sale.order", "amount_total") is False


def test_form_slots_fallback_when_view_has_field_false() -> None:
    from app.ai_form_slots import apply_form_slots
    from app.ai_schema_client import FakeSchemaClient

    draft = {
        "_user_prompt": "Add TIN next to the customer on Sales Orders",
        "_schema_client": FakeSchemaClient(
            models={"sale.order"},
            fields={
                "sale.order": {
                    "partner_id": {"ttype": "many2one", "relation": "res.partner"}
                }
            },
            # Arch map present but partner_id absent → fail closed to new_tab.
            view_fields={"sale.order": {"date_order"}},
        ),
        "models": [
            {
                "model": "sale.order",
                "mode": "inherit",
                "inherit": "sale.order",
                "fields": [
                    {"name": "x_tin", "ttype": "char", "string": "TIN"},
                ],
            }
        ],
        "views": [],
    }
    notes = apply_form_slots(draft, prompt=draft["_user_prompt"])
    slot = ((draft.get("_form_slots") or {}).get("fields") or {}).get("x_tin")
    assert slot == "new_tab"
    assert any("view_has_field miss" in n and "partner_id" in n for n in notes)


def test_form_slots_keeps_anchor_when_view_has_field_true() -> None:
    from app.ai_form_slots import apply_form_slots
    from app.ai_schema_client import FakeSchemaClient

    draft = {
        "_user_prompt": "Add TIN next to the customer on Sales Orders",
        "_schema_client": FakeSchemaClient(
            models={"sale.order"},
            fields={
                "sale.order": {
                    "partner_id": {"ttype": "many2one", "relation": "res.partner"}
                }
            },
            view_fields={"sale.order": {"partner_id", "date_order"}},
        ),
        "models": [
            {
                "model": "sale.order",
                "mode": "inherit",
                "inherit": "sale.order",
                "fields": [
                    {"name": "x_tin", "ttype": "char", "string": "TIN"},
                ],
            }
        ],
        "views": [],
    }
    apply_form_slots(draft, prompt=draft["_user_prompt"])
    slot = ((draft.get("_form_slots") or {}).get("fields") or {}).get("x_tin")
    assert slot == "next_to_partner"
