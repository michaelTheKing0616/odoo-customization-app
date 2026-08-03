"""Subscription pack retrieval + merge tests."""

from __future__ import annotations

from app.ai_domain_pack_law_firm import scaffold_teaching_blob
from app.ai_domain_pack_subscription import subscription_pack
from app.ai_domain_packs import merge_domain_pack, retrieve_domain_pack_lexical


def test_subscription_pack_uses_canonical_names() -> None:
    pack = subscription_pack()
    ids = {m["model"] for m in pack["models"] if isinstance(m, dict)}
    assert "x_subscription_plan" in ids
    assert "x_subscription" in ids
    assert "x_usage_line" in ids
    assert "x_bill" in ids
    sub = next(m for m in pack["models"] if m["model"] == "x_subscription")
    assert sub.get("is_workflow") is True
    party = next(m for m in pack["models"] if m["model"] == "x_subscriber_party")
    assert party.get("is_workflow") is not True


def test_retrieve_subscription_from_prompt() -> None:
    hit = retrieve_domain_pack_lexical(
        "Membership subscription plan with renewal workflow and usage lines"
    )
    assert hit is not None
    pack_id, pack, score = hit
    assert pack_id == "subscription"
    assert score >= 0.99
    assert pack.get("domain_pack") == "subscription"


def test_subscription_teaching_blob_depth() -> None:
    blob = scaffold_teaching_blob(subscription_pack())
    assert "x_subscription" in blob
    assert "renewal" in blob.lower()
    assert "('specialty_a'" not in blob


def test_merge_deepens_thin_subscription() -> None:
    thin = {
        "models": [
            {
                "model": "x_subscription",
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
    merged, notes = merge_domain_pack(thin, subscription_pack())
    sub = next(m for m in merged["models"] if m["model"] == "x_subscription")
    names = {f.get("name") for f in sub["fields"]}
    assert "x_status" in names
    assert "x_plan_id" in names
    assert any("domain pack added field" in n for n in notes)
