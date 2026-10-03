"""T8-META. MetaSnapshot from an in-memory payload. No live Odoo.

The round-trip below is apply, verify, inverse, then MetaSnapshot equality
for one ``field.create``. It is not engine suite 2 for every catalog op.
"""

from __future__ import annotations

import json
import socket
from typing import Any

import pytest

from app.changeset.handlers import apply_memory, compensate_memory
from app.changeset.meta_snapshot import EXPORT_KEYS, MetaSnapshot, equal
from app.changeset.rollback import snapshots_match
from app.changeset.verify import REQUIRED_SMOKE, postconditions_for, verify

pytestmark = pytest.mark.no_app_db

_ALLOW = frozenset(
    {
        "sale.default_deposit_product_id",
        "database.secret",
        "web.base.url",
        "smtp_password",
    }
)


@pytest.fixture(autouse=True)
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("MetaSnapshot opened a socket")

    monkeypatch.setattr(socket, "socket", _refuse_socket)


def _payload() -> dict[str, Any]:
    return {
        "models": [
            {"model": "x_job", "name": "Job"},
            {"model": "sale.order", "name": "Sales Order"},
        ],
        "ir.model.fields": [
            {"model": "sale.order", "name": "x_note", "ttype": "char", "selection": ["b", "a"]},
            {"model": "x_job", "name": "x_ref", "ttype": "char"},
        ],
        "views": [
            {"name": "job form", "model": "x_job", "type": "form", "write_date": "2020-01-01"}
        ],
        "ir.actions.act_window": [{"name": "Jobs", "res_model": "x_job"}],
        "ir.actions.server": [{"name": "Mark done", "model": "x_job", "state": "object_write"}],
        "menus": [{"name": "Jobs"}],
        "ir.model.access": [
            {"model": "x_job", "group": "ingenium.group_job_user", "perm_read": True}
        ],
        "ir.access": [{"model": "x_job", "group": "ingenium.group_job_user", "perm_write": True}],
        "rules": [{"name": "own jobs", "model": "x_job", "domain": "[('x_owner','=',user.id)]"}],
        "groups": [{"name": "Job User", "implied_ids": [3, 1]}],
        "automations": [{"name": "On create", "model": "x_job", "trigger": "on_create"}],
        "crons": [{"name": "Sweep", "model": "x_job", "interval_number": 1}],
        "mail.template": [{"name": "Job mail", "model": "x_job"}],
        "sequences": [{"name": "Job", "code": "x.job", "prefix": "JOB"}],
        "ir.config_parameter": [
            {"key": "sale.default_deposit_product_id", "value": "0"},
            {"key": "database.secret", "value": "nope"},
            {"key": "web.base.url", "value": "http://example"},
            {"key": "smtp_password", "value": "secret"},
            {"key": "not.allowlisted", "value": "x"},
        ],
        "ir.filters": [{"name": "Open", "model": "x_job", "domain": "[]"}],
        "xmlids": [
            "ingenium.action_x_job",
            {"module": "base", "name": "module_sale"},
            {"module": "ingenium", "name": "menu_x_job"},
            "studio.custom_view",
            {"xmlid": "ingenium.group_job_user", "res_id": 4, "write_date": "2020-01-01"},
            {"module": "ingenium", "name": "x_studio_hidden"},
        ],
        "partners": [{"name": "not exported"}],
    }


def _reverse(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _reverse(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse(item) for item in reversed(value)]
    return value


def _passing_observation(ops: list[dict[str, Any]]) -> dict[str, Any]:
    posts: dict[str, dict[str, bool]] = {}
    for index, op in enumerate(ops):
        posts[str(index)] = {name: True for name in postconditions_for(op)}
    return {
        "postconditions": posts,
        "fingerprint": {
            "before": "fp-before",
            "after": "fp-after",
            "expected_after": "fp-after",
        },
        "views": {
            "requester": {"rendered": True, "error": None, "live": False},
            "low_privilege": {"rendered": True, "error": None, "live": False},
            "portal": {"rendered": True, "error": None, "live": False},
        },
        "smoke": [{"name": name, "passed": True} for name in REQUIRED_SMOKE],
        "access": {
            "before": {"sales": {"sale.order": ["read"]}},
            "after": {"sales": {"sale.order": ["read"]}},
        },
        "mail": {"before": 2, "after": 2},
        "data": {
            "counts": {"sale.order": {"expected": 4, "actual": 4}},
            "samples": {"sale.order": [{"id": "row-1"}]},
        },
    }


def test_reordered_payload_matches() -> None:
    left = MetaSnapshot.build(_payload(), config_allowlist=_ALLOW)
    right = MetaSnapshot.build(_reverse(_payload()), config_allowlist=_ALLOW)
    assert left == right
    assert equal(_payload(), _reverse(_payload()), config_allowlist=_ALLOW) is True
    assert snapshots_match(left.to_dict(), right.to_dict()) is True


def test_export_keeps_allowlisted_config_and_ingenium_xmlids_only() -> None:
    body = MetaSnapshot.build(_payload(), config_allowlist=_ALLOW).to_dict()
    assert list(body) == list(EXPORT_KEYS)
    assert body["config_params"] == [{"key": "sale.default_deposit_product_id", "value": "0"}]
    assert body["xmlids"] == [
        {"module": "ingenium", "name": "action_x_job"},
        {"module": "ingenium", "name": "group_job_user", "res_id": 4},
        {"module": "ingenium", "name": "menu_x_job"},
    ]
    assert body["fields"][0]["selection"] == ["a", "b"]
    assert "write_date" not in body["views"][0]
    assert len(body["actions"]) == 2
    assert len(body["acl"]) == 2
    assert "partners" not in body
    assert all(body[key] for key in EXPORT_KEYS)


def test_flat_config_map_uses_the_allowlist() -> None:
    payload = {
        "config_params": {
            "sale.default_deposit_product_id": "0",
            "database.secret": "nope",
        }
    }
    body = MetaSnapshot.build(payload, config_allowlist=_ALLOW).to_dict()
    assert body["config_params"] == [{"key": "sale.default_deposit_product_id", "value": "0"}]


def test_a_real_field_difference_does_not_match() -> None:
    changed = _payload()
    changed["ir.model.fields"] = list(changed["ir.model.fields"])
    changed["ir.model.fields"][0] = {"model": "sale.order", "name": "x_other", "ttype": "char"}
    assert equal(_payload(), changed, config_allowlist=_ALLOW) is False


def test_json_round_trip_of_a_shuffled_export_matches() -> None:
    original = MetaSnapshot.build(_payload(), config_allowlist=_ALLOW)
    encoded = json.loads(json.dumps(original.to_dict()))
    restored = MetaSnapshot.build(_reverse(encoded), config_allowlist=_ALLOW)
    assert original == restored
    assert original.to_dict() == restored.to_dict()


def test_apply_verify_inverse_round_trip_restores_meta_snapshot() -> None:
    """Apply, verify, inverse, then MetaSnapshot equality for field.create."""
    store: dict[str, dict[str, Any]] = {}
    before = MetaSnapshot.from_memory(store, config_allowlist=_ALLOW)
    op = {
        "type": "field.create",
        "params": {
            "model": "sale.order",
            "name": "x_note",
            "ttype": "char",
            "xmlid": "ingenium.field_sale_order_x_note",
        },
    }
    apply_memory(store, op)
    during = MetaSnapshot.from_memory(store, config_allowlist=_ALLOW)
    assert during != before
    assert during.to_dict()["fields"] == [
        {
            "model": "sale.order",
            "name": "x_note",
            "ttype": "char",
            "xmlid": "ingenium.field_sale_order_x_note",
        }
    ]
    assert during.to_dict()["xmlids"] == [
        {"module": "ingenium", "name": "field_sale_order_x_note"}
    ]
    report = verify([op], _passing_observation([op]), model_success=False)
    assert report["verified"] is True
    assert report["contacted_odoo"] is False
    compensate_memory(store, op)
    after = MetaSnapshot.from_memory(store, config_allowlist=_ALLOW)
    assert before == after
    assert snapshots_match(before.to_dict(), after.to_dict()) is True


def test_memory_projection_is_order_independent() -> None:
    first: dict[str, dict[str, Any]] = {}
    second: dict[str, dict[str, Any]] = {}
    ops = [
        {
            "type": "menu.create",
            "params": {"model": "ir.ui.menu", "name": "Jobs", "xmlid": "ingenium.menu_jobs"},
        },
        {
            "type": "filter.create",
            "params": {"model": "x_job", "name": "Open", "domain": "[]"},
        },
    ]
    for op in ops:
        apply_memory(first, op)
    for op in reversed(ops):
        apply_memory(second, op)
    assert MetaSnapshot.from_memory(first) == MetaSnapshot.from_memory(second)


def test_build_rejects_non_json() -> None:
    with pytest.raises(TypeError):
        MetaSnapshot.build({"fields": [{"name": "x_note", "tags": {"a", "b"}}]})
    with pytest.raises(TypeError):
        MetaSnapshot.build({"models": []}, config_allowlist="sale.default_deposit_product_id")
