"""Gold inspect: do not send operators to General Settings / Enterprise tease."""

from __future__ import annotations

from app.ai_gold_inspect import probe_gold_inspect


class _Client:
    def __init__(self, *, account_state: str) -> None:
        self.account_state = account_state

    def get_module_state(self, name: str) -> dict | None:
        if name == "account":
            return {"state": self.account_state}
        return None


def test_probe_cbn_without_account_has_no_settings_href() -> None:
    out = probe_gold_inspect(
        _Client(account_state="uninstalled"),
        gold_id="currency_rate_cbn",
        base_url="http://127.0.0.1:8069",
    )
    assert out["host_ready"] is False
    assert out["href"] is None
    assert out["install_module"] == "account"
    assert "Enterprise" in out["message"]
    assert "Invoicing" in out["message"]


def test_probe_cbn_with_account_uses_config_action(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.ai_gold_inspect.xml_id",
        lambda _client, xid: 314 if xid == "account.action_account_config" else None,
    )
    out = probe_gold_inspect(
        _Client(account_state="installed"),
        gold_id="currency_rate_cbn",
        base_url="http://127.0.0.1:8069/",
    )
    assert out["host_ready"] is True
    assert out["action_id"] == 314
    assert "action=314" in (out["href"] or "")
    assert "model=res.config.settings" in (out["href"] or "")
    assert "Enterprise" in out["message"]
