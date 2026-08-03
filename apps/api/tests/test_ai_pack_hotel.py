"""Hotel pack retrieval + merge tests."""

from __future__ import annotations

from app.ai_domain_pack_hotel import hotel_pack
from app.ai_domain_pack_law_firm import scaffold_teaching_blob
from app.ai_domain_packs import merge_domain_pack, retrieve_domain_pack_lexical


def test_hotel_pack_uses_canonical_names() -> None:
    pack = hotel_pack()
    ids = {m["model"] for m in pack["models"] if isinstance(m, dict)}
    assert "x_hotel" in ids
    assert "x_room" in ids
    assert "x_booking" in ids
    assert "x_housekeeping_task" in ids
    assert "x_bill" in ids
    booking = next(m for m in pack["models"] if m["model"] == "x_booking")
    assert booking.get("is_workflow") is True
    assert "checked_out" in str(booking.get("state_field"))
    party = next(m for m in pack["models"] if m["model"] == "x_guest_party")
    assert party.get("is_workflow") is not True


def test_retrieve_hotel_from_prompt() -> None:
    hit = retrieve_domain_pack_lexical(
        "Hotel PMS with room bookings, check-in check-out workflow and housekeeping tasks"
    )
    assert hit is not None
    pack_id, pack, score = hit
    assert pack_id == "hotel"
    assert score >= 0.99
    assert pack.get("domain_pack") == "hotel"


def test_hotel_teaching_blob_depth() -> None:
    blob = scaffold_teaching_blob(hotel_pack())
    assert "x_booking" in blob
    assert "checked_in" in blob or "housekeeping" in blob
    assert "('specialty_a'" not in blob


def test_merge_deepens_thin_hotel_booking() -> None:
    thin = {
        "models": [
            {
                "model": "x_booking",
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
    merged, notes = merge_domain_pack(thin, hotel_pack())
    booking = next(m for m in merged["models"] if m["model"] == "x_booking")
    names = {f.get("name") for f in booking["fields"]}
    assert "x_status" in names
    assert "x_room_type_id" in names or "x_check_in" in names
    assert any("domain pack added field" in n for n in notes)
