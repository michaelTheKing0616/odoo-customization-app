from app.bridge.gallery import (
    AUTH_KINDS,
    BY_KEY,
    CATEGORIES,
    GALLERY,
    ProbeResult,
    auth_plan,
    evaluate_health,
    list_gallery,
)


def test_catalog_complete_and_valid():
    keys = {c.key for c in GALLERY}
    for k in (
        "shopify",
        "woocommerce",
        "stripe",
        "paystack",
        "flutterwave",
        "quickbooks",
        "xero",
        "hubspot",
        "salesforce",
        "slack",
        "teams",
        "whatsapp",
        "google_sheets",
        "bank",
        "shipping",
        "payroll",
    ):
        assert k in keys
    for c in GALLERY:
        assert c.category in CATEGORIES and set(c.auth) <= set(AUTH_KINDS) and c.entities
    assert all(BY_KEY[k].money for k in ("stripe", "paystack", "quickbooks", "xero"))


def test_filter_and_no_secret_values():
    assert {c["key"] for c in list_gallery("payments")} == {"stripe", "paystack", "flutterwave"}
    assert list_gallery(q="invoices")
    plan = auth_plan("stripe")
    assert plan["money_guard"] and "secret_key" in plan["vault_fields"]
    assert "sk_" not in str(plan)


def test_health_ok_warn_fail():
    ok = evaluate_health(
        "salesforce",
        [
            ProbeResult("auth", True, 200),
            ProbeResult(
                "read",
                True,
                200,
                headers={"X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "90"},
            ),
        ],
    )
    assert ok["status"] == "ok" and ok["rate_limit"]["remaining"] == 90
    w = evaluate_health(
        "shopify",
        [ProbeResult("auth", True, 200, headers={"X-Shopify-Shop-Api-Call-Limit": "38/40"})],
    )
    assert w["status"] == "warn" and "Rate limit nearly used up" in w["warnings"]
    f = evaluate_health(
        "stripe",
        [ProbeResult("auth", False, 401, detail="Invalid key sk_live_abc")],
        needed_entities=["payouts", "widgets"],
    )
    assert (
        f["status"] == "fail"
        and "sk_live" not in str(f)
        and any("widgets" in i for i in f["issues"])
    )


class _R:
    def __init__(self, st, js=None, h=None):
        self.status_code, self._j, self.headers = st, js or {}, h or {}

    def json(self):
        return self._j


def test_vault_and_live_probe(tmp_path, monkeypatch):
    from app.bridge import live_probe as lp
    from app.code_runner import store

    monkeypatch.setattr(store, "root", lambda: tmp_path)
    assert lp.health("w1", "stripe")["status"] == "fail"  # nothing in vault
    lp.put_secrets("w1", "stripe", {"secret_key": "sk_test_SECRET123"}, "u")
    assert [n["name"] for n in lp.secret_names("w1", "stripe")] == ["secret_key"]
    assert "SECRET123" not in (tmp_path / "x").as_posix() + str(list(tmp_path.rglob("*")))
    seen = {}

    def get(url, headers):
        seen["auth"] = headers["Authorization"]
        return _R(200, h={"X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "50"})

    out = lp.health("w1", "stripe", http_get=get)
    assert seen["auth"].endswith("SECRET123") and "SECRET123" not in str(out)
    assert out["status"] == "warn"  # webhook not verified yet
    bad = lp.health("w1", "stripe", http_get=lambda u, headers: _R(401))
    assert bad["status"] == "fail"
    import pytest

    with pytest.raises(ValueError):
        lp.put_secrets("w1", "stripe", {"evil": "x"}, "u")
    assert lp.delete_secrets("w1", "stripe")
