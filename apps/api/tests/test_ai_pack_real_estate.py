"""Real-estate pack retrieval + merge tests."""

from __future__ import annotations

from app.ai_domain_pack_law_firm import scaffold_teaching_blob
from app.ai_domain_pack_real_estate import real_estate_pack
from app.ai_domain_packs import merge_domain_pack, retrieve_domain_pack_lexical


def test_real_estate_pack_uses_canonical_names() -> None:
    pack = real_estate_pack()
    ids = {m["model"] for m in pack["models"] if isinstance(m, dict)}
    assert "x_property" in ids
    assert "x_unit" in ids
    assert "x_lease" in ids
    assert "x_deposit" in ids
    assert "x_tenant_party" in ids
    lease = next(m for m in pack["models"] if m["model"] == "x_lease")
    assert lease.get("is_workflow") is True
    status = next(f for f in lease["fields"] if f["name"] == "x_status")
    assert "terminated" in status.get("selection", "") or "expired" in status.get("selection", "")
    party = next(m for m in pack["models"] if m["model"] == "x_tenant_party")
    assert party.get("is_workflow") is not True


def test_retrieve_real_estate_from_prompt() -> None:
    hit = retrieve_domain_pack_lexical(
        "Real estate property management with unit leases, viewings, and tenant deposits"
    )
    assert hit is not None
    pack_id, pack, score = hit
    assert pack_id == "real_estate"
    assert score >= 0.99
    assert pack.get("domain_pack") == "real_estate"


def test_real_estate_teaching_blob_depth() -> None:
    blob = scaffold_teaching_blob(real_estate_pack())
    assert "x_lease" in blob
    assert "active" in blob or "terminated" in blob
    assert "('specialty_a'" not in blob


def test_merge_deepens_thin_real_estate_lease() -> None:
    thin = {
        "models": [
            {
                "model": "x_lease",
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
    merged, notes = merge_domain_pack(thin, real_estate_pack())
    lease = next(m for m in merged["models"] if m["model"] == "x_lease")
    names = {f.get("name") for f in lease["fields"]}
    assert "x_status" in names
    assert "x_unit_id" in names
    assert any("domain pack added field" in n for n in notes)
