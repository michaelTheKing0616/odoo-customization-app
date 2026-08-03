"""Restaurant pack retrieval + merge tests."""

from __future__ import annotations

from app.ai_domain_pack_law_firm import scaffold_teaching_blob
from app.ai_domain_pack_restaurant import restaurant_pack
from app.ai_domain_packs import merge_domain_pack, retrieve_domain_pack_lexical


def test_restaurant_pack_uses_canonical_names() -> None:
    pack = restaurant_pack()
    ids = {m["model"] for m in pack["models"] if isinstance(m, dict)}
    assert "x_restaurant" in ids
    assert "x_order" in ids
    assert "x_order_line" in ids
    assert "x_menu_item" in ids
    assert "x_bill" in ids
    order = next(m for m in pack["models"] if m["model"] == "x_order")
    assert order.get("is_workflow") is True
    assert order.get("state_field", {}).get("transitions")
    server = next(m for m in pack["models"] if m["model"] == "x_server")
    assert next(f for f in server["fields"] if f["name"] == "x_user_id")["relation"] == "res.users"


def test_retrieve_restaurant_from_prompt() -> None:
    hit = retrieve_domain_pack_lexical(
        "Build a restaurant POS-lite app with table reservations and kitchen order flow"
    )
    assert hit is not None
    pack_id, pack, score = hit
    assert pack_id == "restaurant"
    assert score >= 0.99
    assert pack.get("domain_pack") == "restaurant"


def test_restaurant_teaching_blob_depth() -> None:
    blob = scaffold_teaching_blob(restaurant_pack())
    assert "x_order" in blob
    assert "x_reservation" in blob or "confirmed" in blob
    assert "('specialty_a'" not in blob


def test_merge_deepens_thin_restaurant_order() -> None:
    thin = {
        "models": [
            {
                "model": "x_order",
                "fields": [
                    {"name": "x_name", "ttype": "char"},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "relation": "res.partner",
                    },
                ],
            }
        ]
    }
    merged, notes = merge_domain_pack(thin, restaurant_pack())
    order = next(m for m in merged["models"] if m["model"] == "x_order")
    names = {f.get("name") for f in order["fields"]}
    assert "x_status" in names
    assert "x_line_ids" in names or "x_menu_item_id" in str(order)
    assert any("domain pack added field" in n for n in notes)
