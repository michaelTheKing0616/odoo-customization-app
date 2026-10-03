"""In-memory proofs for T8-OD-BRIDGE. No live Odoo and no database copy.

Passing tests in test_bridge_protocol.py and test_executor_bridge.py stay as they are.
GATE-P2-08 and GATE-P2-09 are not fully passed: nothing here installs the addon.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.bridge.memory import InMemoryBridge, load_protocol

_R1 = {"type": "view.inherit.create", "risk": "R1", "ddl": False, "params": {"anchor": "name"}}
_STOLEN_KEY = "stolen-odoo-key"


class _SourceDatabase:
    def __init__(self) -> None:
        self.rows = {"orders": 4}
        self.copy_calls = 0

    def duplicate(self) -> dict:
        self.copy_calls += 1
        return dict(self.rows)


def _bridge(**kwargs) -> InMemoryBridge:
    return InMemoryBridge(**kwargs)


def _envelope(method: str, method_args: list) -> dict:
    return {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": ["db", 2, _STOLEN_KEY, "ingenium.bridge", method, method_args],
        },
    }


def test_unknown_op_and_ddl_dry_run_leave_records_untouched() -> None:
    bridge = _bridge()
    bridge.records["applied"] = ["existing"]
    with pytest.raises(load_protocol().BridgeError) as unknown:
        bridge.apply_changeset(
            [{"type": "not.an.op", "risk": "R1", "ddl": False}],
            mode="apply",
            environment="production",
            neutralized_clone=True,
            max_risk="R2",
        )
    assert unknown.value.code == "unknown_op"
    with pytest.raises(load_protocol().BridgeError) as ddl:
        bridge.apply_changeset(
            [{"type": "field.create", "risk": "R2", "ddl": True}],
            mode="dry_run",
            environment="production",
            neutralized_clone=True,
            max_risk="R3",
        )
    assert ddl.value.code == "ddl_no_inplace"
    assert bridge.records == {"applied": ["existing"]}
    assert bridge.transactions_opened == 0
    assert bridge.outbound.urls == []


@pytest.mark.parametrize("off", ["0", "false", "False"])
def test_named_kill_switch_stops_apply(off: str) -> None:
    decoy = _bridge(params={"enabled": "0", "bridge.enabled": "0"})
    applied = decoy.apply_changeset(
        [_R1],
        mode="apply",
        environment="production",
        neutralized_clone=False,
        max_risk="R2",
    )
    assert applied["status"] == "applied"
    assert decoy.transactions_committed == 1

    stopped = _bridge(params={"ingenium.bridge.enabled": off, "enabled": "1"})
    stopped.records["applied"] = ["existing"]
    with pytest.raises(load_protocol().BridgeError) as killed:
        stopped.apply_changeset(
            [_R1],
            mode="apply",
            environment="production",
            neutralized_clone=True,
            max_risk="R2",
        )
    assert killed.value.code == "kill_switch"
    assert str(killed.value) == "kill_switch"
    assert stopped.records == {"applied": ["existing"]}
    assert stopped.transactions_opened == 0
    assert stopped.outbound.urls == []


def test_seven_methods_call_no_outbound_url() -> None:
    bridge = _bridge()
    ping = bridge.ping()
    assert ping["protocol_version"] == 1
    assert "http" not in str(ping)
    assert bridge.introspect({"sale.order": ["name"]})["requested"] == ["sale.order"]
    assert bridge.combined_view("sale.order", "form")["model"] == "sale.order"
    assert bridge.effective_access("sale.order", [1, 2])["users"] == [1, 2]
    rendered = bridge.render_check("view", "sale.order.form")
    assert rendered["writes"] == 0
    assert rendered["rolled_back"] is True
    assert "__render_probe__" not in bridge.records
    assert bridge.savepoints_rolled_back == 1
    applied = bridge.apply_changeset(
        [_R1],
        mode="apply",
        environment="production",
        neutralized_clone=False,
        max_risk="R2",
    )
    assert applied["copied_database"] is False
    assert bridge.transactions_opened == 1
    assert bridge.transactions_committed == 1
    rolled = bridge.rollback_changeset(applied["changeset_id"])
    assert rolled == {"rolled_back": True, "copied_database": False}
    assert bridge.records == {}
    assert bridge.outbound.urls == []


def test_callback_field_is_refused_and_no_url_is_requested() -> None:
    bridge = _bridge()
    bridge.records["applied"] = ["existing"]
    with pytest.raises(load_protocol().BridgeError) as refused:
        bridge.apply_changeset(
            [{**_R1, "callback": "https://collector.example/ingest"}],
            mode="apply",
            environment="production",
            neutralized_clone=True,
            max_risk="R2",
        )
    assert refused.value.code == "outbound_refused"
    assert bridge.records == {"applied": ["existing"]}
    assert bridge.outbound.urls == []
    root = Path(__file__).resolve().parents[3]
    for relative in (
        "odoo_addons/ingenium_bridge/protocol.py",
        "apps/api/app/bridge/memory.py",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        for banned in ("urllib", "requests", "httpx", "aiohttp"):
            assert banned not in text


def test_direct_json_with_a_stolen_key_is_refused() -> None:
    protocol = load_protocol()
    bridge = _bridge(server_secret="control-plane-secret")
    envelope = _envelope("apply_changeset", [[_R1], "apply"])
    with pytest.raises(protocol.BridgeError) as missing:
        bridge.direct_json(envelope, presented_key=_STOLEN_KEY)
    assert missing.value.code == "stolen_key"
    assert _STOLEN_KEY not in str(missing.value)
    with pytest.raises(protocol.BridgeError) as presented_as_grant:
        bridge.direct_json(envelope, presented_key=_STOLEN_KEY, dispatch_grant_value=_STOLEN_KEY)
    assert presented_as_grant.value.code == "stolen_key"
    with pytest.raises(protocol.BridgeError) as forged:
        bridge.direct_json(envelope, presented_key=_STOLEN_KEY, dispatch_grant_value="ab" * 32)
    assert forged.value.code == "stolen_key"
    assert bridge.records == {}
    assert bridge.transactions_opened == 0
    assert bridge.outbound.urls == []

    body = {"args": []}
    grant = protocol.dispatch_grant(server_secret="control-plane-secret", method="ping", body=body)
    assert grant != _STOLEN_KEY
    ping = bridge.direct_json(_envelope("ping", []), presented_key=_STOLEN_KEY, dispatch_grant_value=grant)
    assert ping["protocol_version"] == 1
    assert _STOLEN_KEY not in str(ping)
    assert bridge.outbound.urls == []


def test_promotion_replays_a_changeset_and_does_not_copy_a_database() -> None:
    source = _SourceDatabase()
    target = _bridge()
    replayed = target.promote([_R1], source=source, copy_database=False, neutralized=True)
    assert replayed["action"] == "replay"
    assert replayed["copied_database"] is False
    assert source.copy_calls == 0
    assert source.rows == {"orders": 4}
    assert target.records == {"applied": ["view.inherit.create"]}

    untouched = _SourceDatabase()
    refused = _bridge()
    with pytest.raises(load_protocol().BridgeError) as copied:
        refused.promote([_R1], source=untouched, copy_database=True, neutralized=True)
    assert copied.value.code == "database_copy_refused"
    with pytest.raises(load_protocol().BridgeError) as raw:
        refused.promote([_R1], source=untouched, copy_database=False, neutralized=False)
    assert raw.value.code == "neutralization_required"
    assert untouched.copy_calls == 0
    assert untouched.rows == {"orders": 4}
    assert refused.records == {}
    assert refused.outbound.urls == []


def test_apply_is_one_transaction_and_above_r1_stays_review_only() -> None:
    protocol = load_protocol()
    bridge = _bridge()
    ops = [_R1, {**_R1, "params": {"anchor": "partner_id"}}]
    with pytest.raises(protocol.BridgeError) as failed:
        bridge.apply_changeset(
            ops,
            mode="apply",
            environment="production",
            neutralized_clone=True,
            max_risk="R2",
            fail_at=1,
        )
    assert failed.value.code == "apply_failed"
    assert bridge.records == {}
    assert bridge.transactions_opened == 1
    assert bridge.transactions_committed == 0
    assert bridge.transactions_rolled_back == 1

    dry = bridge.apply_changeset(
        [_R1],
        mode="dry_run",
        environment="production",
        neutralized_clone=False,
        max_risk="R2",
    )
    assert dry["writes"] == 0
    assert dry["rolled_back"] is True
    assert bridge.records == {}
    assert bridge.transactions_committed == 0

    blocked = _bridge()
    with pytest.raises(protocol.BridgeError) as production_r3:
        blocked.apply_changeset(
            [{"type": "access.create", "risk": "R3", "ddl": False}],
            mode="apply",
            environment="production",
            neutralized_clone=True,
            max_risk="R3",
        )
    assert production_r3.value.code == "production_r3_blocked"
    with pytest.raises(protocol.BridgeError) as review:
        blocked.apply_changeset(
            [{"type": "field.create", "risk": "R2", "ddl": True}],
            mode="apply",
            environment="production",
            neutralized_clone=False,
            max_risk="R3",
        )
    assert review.value.code == "review_only"
    with pytest.raises(protocol.BridgeError) as staging:
        blocked.apply_changeset(
            [_R1],
            mode="apply",
            environment="staging",
            neutralized_clone=False,
            max_risk="R2",
        )
    assert staging.value.code == "neutralization_required"
    validated = blocked.apply_changeset(
        [{"type": "access.create", "risk": "R3", "ddl": False}],
        mode="validate",
        environment="production",
        neutralized_clone=False,
        max_risk="R3",
    )
    assert validated["writes"] == 0
    assert blocked.records == {}
    assert blocked.transactions_opened == 0
