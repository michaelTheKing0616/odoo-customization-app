"""Op dispatch writes real model names. Shopify signatures are HMAC checks."""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from app.bridge.connector import ShopifyConnector
from app.changeset.dispatch import DispatchError, dispatch_op
from app.changeset.executor import apply, get_journal, reset_journal


class RecordingPort:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def create(self, model: str, values: dict) -> int:
        self.calls.append(("create", model, values))
        return len(self.calls)

    def write(self, model: str, ids: list[int], values: dict) -> None:
        self.calls.append(("write", model, ids, values))


def test_field_create_writes_ir_model_fields() -> None:
    port = RecordingPort()
    created = dispatch_op(
        port,
        {"type": "field.create", "params": {"model": "res.partner", "name": "x_rc_number", "ttype": "char"}},
    )
    assert created == 1
    assert port.calls[0][1] == "ir.model.fields"
    assert port.calls[0][2]["name"] == "x_rc_number"


def test_studio_prefix_and_uninstall_never_call_the_port() -> None:
    port = RecordingPort()
    with pytest.raises(DispatchError):
        dispatch_op(port, {"type": "field.create", "params": {"model": "res.partner", "name": "x_studio_note"}})
    with pytest.raises(DispatchError):
        dispatch_op(port, {"type": "module.uninstall", "params": {"module": "sale"}})
    with pytest.raises(DispatchError):
        dispatch_op(port, {"type": "data.delete", "params": {}})
    assert port.calls == []


def test_groupless_access_is_refused() -> None:
    port = RecordingPort()
    with pytest.raises(DispatchError, match="group-less"):
        dispatch_op(port, {"type": "access.create", "params": {"name": "open", "model": "res.partner"}})
    assert port.calls == []


def test_apply_with_port_records_the_orm_call_in_the_journal() -> None:
    reset_journal()
    port = RecordingPort()
    result = apply(
        [{"type": "field.create", "params": {"model": "res.partner", "name": "x_note"}}],
        mode="T",
        port=port,
    )
    assert result["status"] == "VERIFIED"
    assert port.calls[0][1] == "ir.model.fields"
    kinds = [entry["kind"] for entry in get_journal()]
    assert kinds.index("RESULT") < kinds.index("VERIFIED")


def test_shopify_hmac_accepts_only_the_real_signature() -> None:
    secret = "shpss_test"
    body = b'{"id":99}'
    good = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    connector = ShopifyConnector(webhook_secret=secret)
    assert connector.verify_webhook_signature(body, good) is True
    assert connector.verify_webhook_signature(body, "not-a-signature") is False
    assert connector.verify_webhook_signature(body, "") is False
    event = connector.parse_webhook_event(body)
    assert event["idempotency_key"] == "shopify:99"


def test_shopify_rejects_unknown_entity_and_malformed_body() -> None:
    connector = ShopifyConnector(webhook_secret="shpss_test")
    with pytest.raises(ValueError):
        connector.fetch("customers")
    with pytest.raises(ValueError):
        connector.parse_webhook_event(b"not-json")
