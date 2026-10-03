"""Bridge protocol: kill switch, protocol version, and reader versus operator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.changeset.ops import OP_CATALOG

_PROTOCOL_PATH = Path(__file__).resolve().parents[3] / "odoo_addons" / "ingenium_bridge" / "protocol.py"


def _protocol():
    spec = importlib.util.spec_from_file_location("ingenium_bridge_protocol", _PROTOCOL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_reader_can_ping_and_cannot_apply_or_impersonate() -> None:
    protocol = _protocol()
    protocol.authorize(method="ping", protocol_version=1, enabled=True, groups={"reader"}, caller_id=7)
    with pytest.raises(protocol.BridgeError) as denied:
        protocol.authorize(method="apply_changeset", protocol_version=1, enabled=True, groups={"reader"}, caller_id=7)
    assert denied.value.code == "operator_required"
    with pytest.raises(protocol.BridgeError) as unknown_method:
        protocol.authorize(method="sql", protocol_version=1, enabled=True, groups={"operator"}, caller_id=7)
    assert unknown_method.value.code == "unknown_method"
    with pytest.raises(protocol.BridgeError) as impersonated:
        protocol.authorize(
            method="combined_view",
            protocol_version=1,
            enabled=True,
            groups={"reader"},
            caller_id=7,
            user_id=8,
        )
    assert impersonated.value.code == "impersonation_denied"


def test_kill_switch_protocol_and_escalation_refuse_before_work() -> None:
    protocol = _protocol()
    with pytest.raises(protocol.BridgeError) as killed:
        protocol.authorize(method="ping", protocol_version=1, enabled=False, groups={"operator"}, caller_id=1)
    assert killed.value.code == "kill_switch"
    with pytest.raises(protocol.BridgeError) as mismatched:
        protocol.authorize(method="ping", protocol_version=2, enabled=True, groups={"operator"}, caller_id=1)
    assert mismatched.value.code == "protocol_mismatch"
    with pytest.raises(protocol.BridgeError) as escalated:
        protocol.authorize(
            method="introspect",
            protocol_version=1,
            enabled=True,
            groups={"operator"},
            caller_id=1,
            escalated=True,
        )
    assert escalated.value.code == "system_escalation"


def test_apply_refuses_unknown_prohibited_and_inplace_ddl() -> None:
    protocol = _protocol()
    known = set(OP_CATALOG)
    base = dict(protocol_version=1, enabled=True, groups={"operator"}, caller_id=1, max_risk="R2", mode="dry_run")
    with pytest.raises(protocol.BridgeError) as unknown:
        protocol.authorize_apply([{"type": "rpc.write", "risk": "R1"}], known_types=known, **base)
    assert unknown.value.code == "unknown_op"
    with pytest.raises(protocol.BridgeError) as prohibited:
        protocol.authorize_apply([{"type": "data.delete", "risk": "R4"}], known_types=known, **base)
    assert prohibited.value.code == "prohibited_op"
    with pytest.raises(protocol.BridgeError) as uninstall:
        protocol.authorize_apply([{"type": "module.uninstall", "risk": "R4"}], known_types=known, **base)
    assert uninstall.value.code == "prohibited_op"
    with pytest.raises(protocol.BridgeError) as bad_risk:
        protocol.authorize_apply([{"type": "view.inherit.create", "risk": "R9"}], known_types=known, **base)
    assert bad_risk.value.code == "unknown_risk"
    with pytest.raises(protocol.BridgeError) as ddl:
        protocol.authorize_apply(
            [{"type": "field.create", "risk": "R2", "ddl": True}],
            known_types=known,
            **base,
        )
    assert ddl.value.code == "ddl_no_inplace"
    with pytest.raises(protocol.BridgeError) as ceiling:
        protocol.authorize_apply([{"type": "access.create", "risk": "R3"}], known_types=known, **base)
    assert ceiling.value.code == "max_risk"
    protocol.authorize_apply(
        [{"type": "view.inherit.create", "risk": "R1", "ddl": False}],
        known_types=known,
        **base,
    )
    payload = protocol.ping_payload(server_version="19.0", edition="community", module_hash="abc", capabilities={})
    assert payload["protocol_version"] == 1
    assert "secret" not in payload
