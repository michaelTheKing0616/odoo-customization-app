"""The executor refuses before it journals when the bridge gate refuses."""

from __future__ import annotations

import pytest

from app.changeset.executor import _protocol, apply, get_journal, reset_journal


class _Port:
    def __init__(self) -> None:
        self.created: list[str] = []

    def create(self, model: str, values: dict) -> int:
        self.created.append(model)
        return 1

    def write(self, model: str, ids: list[int], values: dict) -> None:
        return None


def test_reader_and_kill_switch_do_not_touch_the_port_or_journal() -> None:
    reset_journal()
    error = _protocol().BridgeError
    port = _Port()
    op = {"type": "field.create", "params": {"model": "sale.order", "name": "x_po"}}
    with pytest.raises(error) as reader:
        apply([op], mode="T", port=port, groups={"reader"})
    assert reader.value.code == "operator_required"
    with pytest.raises(error) as killed:
        apply([op], mode="T", port=port, enabled=False)
    assert killed.value.code == "kill_switch"
    assert port.created == []
    assert get_journal() == []


def test_prohibited_op_and_hash_mismatch_write_nothing() -> None:
    reset_journal()
    error = _protocol().BridgeError
    port = _Port()
    with pytest.raises(error) as prohibited:
        apply([{"type": "data.delete", "params": {"model": "res.partner"}}], mode="T", port=port)
    assert prohibited.value.code == "prohibited_op"
    op = [{"type": "field.create", "params": {"model": "sale.order", "name": "x_po"}}]
    with pytest.raises(error) as mismatch:
        apply(op, mode="T", port=port, approved_hash="0" * 16)
    assert mismatch.value.code == "approval_hash_mismatch"
    assert port.created == []
    assert get_journal() == []


def test_caller_risk_does_not_override_the_catalog() -> None:
    reset_journal()
    error = _protocol().BridgeError
    port = _Port()
    with pytest.raises(error) as lowered:
        apply(
            [{"type": "access.create", "params": {"model": "sale.order", "group": "sales"}, "risk": "R0", "ddl": False}],
            mode="T",
            port=port,
            max_risk="R2",
        )
    assert lowered.value.code == "max_risk"
    with pytest.raises(error) as unknown:
        apply([{"type": "rpc.write", "params": {}, "risk": "R0"}], mode="T", port=port)
    assert unknown.value.code == "unknown_op"
    assert port.created == []
    assert get_journal() == []


def test_stale_fingerprint_protected_target_and_unknown_outcome_do_not_claim_success() -> None:
    reset_journal()
    error = _protocol().BridgeError
    port = _Port()
    for model in ("stock.quant", "account.move", "account.move.line", "account.payment"):
        for op_type in ("data.delete", "data.update_batch", "data.merge", "data.archive_batch"):
            with pytest.raises(error) as protected:
                apply(
                    [{"type": op_type, "params": {"model": model, "domain": [["id", "=", 1]], "values": {}}}],
                    mode="T",
                    port=port,
                )
            assert protected.value.code == "protected_deny"
    field = {"type": "field.create", "params": {"model": "sale.order", "name": "x_po"}}
    with pytest.raises(error) as stale:
        apply([field], mode="T", port=port, expected_fingerprint="aaa", live_fingerprint="bbb")
    assert stale.value.code == "stale_fingerprint"
    assert port.created == []
    assert get_journal() == []

    from app.changeset.executor import UnknownOutcome

    class _Uncertain:
        def create(self, model: str, values: dict) -> int:
            raise UnknownOutcome()

        def write(self, model: str, ids: list[int], values: dict) -> None:
            return None

    reset_journal()
    result = apply([field], mode="T", port=_Uncertain())
    assert result["status"] == "NEEDS_HUMAN"
    assert result["applied_count"] == 0
    assert any(entry.get("kind") == "UNKNOWN" for entry in get_journal())
    assert not any(entry.get("kind") == "RESULT" for entry in get_journal())
    reset_journal()
    error = _protocol().BridgeError
    port = _Port()
    with pytest.raises(error) as refused:
        apply([{"type": "data.merge", "params": {"model": "res.partner"}}], mode="C", port=port)
    assert refused.value.code == "mode_c_irreversible"
    assert port.created == []
    assert get_journal() == []
