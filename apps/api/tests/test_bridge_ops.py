from app.bridge.ops import (
    build_alert,
    client_may,
    digest,
    mask_pii,
    mask_record,
    plain_cause,
    quota_watch,
    reconciliation_report,
    slack_blocks,
    uptime,
)


def test_alerts():
    assert "sign-in" in plain_cause("HTTP 401 Unauthorized")["cause"]
    assert "limiting" in plain_cause("429 Too Many Requests")["cause"]
    a = build_alert("Shopify orders", "500 Bad Gateway", record="ada@x.ng", count=3)
    assert "a***@x.ng" in a["text"] and "ada@" not in a["text"]
    assert digest([a, a])["lines"] == [f"2× {a['title']}"] and slack_blocks(a)["text"] == a["title"]


def test_reports_uptime_quota():
    r = reconciliation_report(
        {
            "stripe": {"ok": False, "missing_in_odoo": ["A"], "amount_mismatch": []},
            "x": {"ok": True},
        },
        "2026-10-19",
    )
    assert not r["ok"] and "1 flow" in r["title"]
    u = uptime([{"ok": True, "latency_ms": 100}] * 199 + [{"ok": False}])
    assert u["uptime"] == 0.995 and u["meets_sla"]
    q = quota_watch(900, 1000, 0.01, budget=10)
    assert q["warnings"] and not q["pause"] and quota_watch(1000, 1000)["pause"]


def test_pii_and_client_mode():
    t = mask_pii(
        "call +234 803 111 2222 or ada@x.ng, key sk_live_abc123, Bearer eyJ.x.y, acct 0123456789"
    )
    assert (
        "803" not in t
        and "ada@" not in t
        and "abc123" not in t
        and "eyJ" not in t
        and "0123456789" not in t
    )
    assert mask_record({"email": "a@b.c", "n": [{"phone": "1"}]}) == {
        "email": "***",
        "n": [{"phone": "***"}],
    }
    assert client_may("GET", "/api/bridge/flows/f") and client_may(
        "POST", "/api/bridge/flows/f/approve"
    )
    assert not client_may("POST", "/api/bridge/flows/f/rollout") and not client_may(
        "DELETE", "/api/bridge/gallery/x/secrets"
    )
