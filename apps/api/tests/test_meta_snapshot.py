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
from app.changeset.meta_snapshot import (
    CAPTURE_SOURCES,
    EXPORT_KEYS,
    MetaSnapshot,
    capture,
    equal,
)
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
    assert during.to_dict()["xmlids"] == [{"module": "ingenium", "name": "field_sale_order_x_note"}]
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


_M2O = {
    "inherit_id",
    "model_id",
    "group_id",
    "parent_id",
    "category_id",
    "binding_model_id",
    "action_server_id",
    "ir_actions_server_id",
    "user_id",
    "company_id",
    "action_id",
}
_M2M = {"groups_id", "groups", "implied_ids", "trigger_field_ids"}


class _ReadPort:
    """Read-only fake port. ``search_read`` honours ``in``/``=`` and ``active_test``."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables
        self.calls: list[tuple[str, str, list[Any], dict[str, Any]]] = []

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        self.calls.append((model, method, list(args), dict(kwargs or {})))
        rows = self.tables.get(model, [])
        if method == "fields_get":
            names = {name for row in rows for name in row} | {
                name for source, odoo, wanted in CAPTURE_SOURCES if odoo == model for name in wanted
            }
            return {name: {"type": _type_of(name)} for name in names}
        if method != "search_read":
            raise AssertionError(f"capture called {method}")
        domain = args[0]
        fields = kwargs["fields"] if kwargs else []
        out = []
        for row in rows:
            if row.get("active") is False:
                continue
            if all(_matches(row, leaf) for leaf in domain):
                out.append({"id": row.get("id", 0), **{f: row[f] for f in fields if f in row}})
        return out


def _type_of(name: str) -> str:
    if name in _M2O:
        return "many2one"
    if name in _M2M:
        return "many2many"
    return "char"


def _matches(row: dict[str, Any], leaf: list[Any]) -> bool:
    field, operator, value = leaf
    if operator == "in":
        return row.get(field) in value
    if operator == "=":
        return row.get(field) == value
    raise AssertionError(f"unexpected operator {operator}")


def _tables() -> dict[str, list[dict[str, Any]]]:
    sources = {odoo for _category, odoo, _wanted in CAPTURE_SOURCES if odoo != "ir.rule"}
    sources.add("ir.rule")
    return {
        "ir.model": [{"model": name, "name": name, "state": "base"} for name in sorted(sources)]
        + [{"model": "x_job", "name": "Job", "state": "manual"}],
        "ir.model.fields": [{"model": "x_job", "name": "x_ref", "ttype": "char"}],
        "ir.ui.view": [
            {
                "name": "job form",
                "model": "x_job",
                "type": "form",
                "priority": 16,
                "inherit_id": [7, "base"],
            },
            {"name": "old form", "model": "x_job", "type": "form", "active": False},
        ],
        "ir.actions.act_window": [
            {"name": "Jobs", "type": "ir.actions.act_window", "res_model": "x_job"}
        ],
        "ir.actions.server": [
            {"name": "Mark", "type": "ir.actions.server", "model_id": [9, "Job"]}
        ],
        "ir.actions.report": [{"name": "Job PDF", "type": "ir.actions.report", "model": "x_job"}],
        "ir.ui.menu": [{"name": "Jobs", "sequence": 10, "groups_id": [3, 1, 2]}],
        "ir.model.access": [
            {"name": "job user", "model_id": [9, "Job"], "group_id": [3, "User"], "perm_read": True}
        ],
        "ir.access": [],
        "ir.rule": [
            {"name": "own jobs", "model_id": [9, "Job"], "groups": [5, 4], "domain_force": "[]"}
        ],
        "res.groups": [{"name": "Job User", "implied_ids": [1, 2]}],
        "base.automation": [{"name": "On create", "model_id": [9, "Job"], "trigger": "on_create"}],
        "ir.cron": [
            {"name": "Sweep", "model_id": [9, "Job"], "interval_number": 1, "nextcall": "x"}
        ],
        "mail.template": [{"name": "Job mail", "model": "x_job"}],
        "ir.sequence": [{"name": "Job", "code": "x.job", "prefix": "JOB", "number_next": 41}],
        "ir.config_parameter": [
            {"key": "sale.default_deposit_product_id", "value": "0"},
            {"key": "database.secret", "value": "nope"},
            {"key": "smtp_password", "value": "secret"},
            {"key": "not.allowlisted", "value": "x"},
        ],
        "ir.filters": [{"name": "Open", "model_id": "x_job", "domain": "[]"}],
        "ir.model.data": [
            {"module": "ingenium", "name": "menu_x_job", "model": "ir.ui.menu", "res_id": 4},
            {"module": "base", "name": "group_user", "model": "res.groups", "res_id": 1},
        ],
    }


def _shuffled(tables: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for model in reversed(list(tables)):
        rows = []
        for row in reversed(tables[model]):
            rows.append(
                {
                    key: list(reversed(value)) if key in _M2M else value
                    for key, value in reversed(list(row.items()))
                }
            )
        out[model] = rows
    return out


def test_capture_reads_every_export_category() -> None:
    port = _ReadPort(_tables())
    body = capture(port, config_allowlist=_ALLOW).to_dict()
    assert list(body) == list(EXPORT_KEYS)
    for key in EXPORT_KEYS:
        assert body[key], key
    assert {row["type"] for row in body["actions"]} == {
        "ir.actions.act_window",
        "ir.actions.server",
        "ir.actions.report",
    }
    assert body["views"] == [
        {"inherit_id": 7, "model": "x_job", "name": "job form", "priority": 16, "type": "form"}
    ]
    assert body["menus"][0]["groups_id"] == [1, 2, 3]
    assert body["menus"][0]["sequence"] == 10
    assert "nextcall" not in body["crons"][0]
    assert "number_next" not in body["sequences"][0]
    assert body["xmlids"] == [
        {"model": "ir.ui.menu", "module": "ingenium", "name": "menu_x_job", "res_id": 4}
    ]
    assert all(method in {"fields_get", "search_read"} for _m, method, _a, _k in port.calls)


def test_capture_never_reads_a_non_allowlisted_or_secret_config_param() -> None:
    port = _ReadPort(_tables())
    body = capture(port, config_allowlist=_ALLOW).to_dict()
    assert body["config_params"] == [{"key": "sale.default_deposit_product_id", "value": "0"}]
    domains = [
        args[0]
        for model, method, args, _k in port.calls
        if model == "ir.config_parameter" and method == "search_read"
    ]
    assert domains == [[["key", "in", ["sale.default_deposit_product_id"]]]]
    assert "database.secret" not in json.dumps(body)
    assert "smtp_password" not in json.dumps(body)


def test_capture_with_no_allowlist_skips_config_params() -> None:
    port = _ReadPort(_tables())
    body = capture(port).to_dict()
    assert body["config_params"] == []
    assert not [
        call for call in port.calls if call[0] == "ir.config_parameter" and call[1] == "search_read"
    ]


def test_capture_skips_a_model_that_is_not_installed() -> None:
    tables = _tables()
    tables["ir.model"] = [row for row in tables["ir.model"] if row["model"] != "ir.rule"]
    port = _ReadPort(tables)
    body = capture(port, config_allowlist=_ALLOW).to_dict()
    assert body["rules"] == []
    assert not [call for call in port.calls if call[0] == "ir.rule"]


def test_shuffled_records_and_m2m_ids_compare_equal() -> None:
    left = capture(_ReadPort(_tables()), config_allowlist=_ALLOW)
    right = capture(_ReadPort(_shuffled(_tables())), config_allowlist=_ALLOW)
    assert left == right
    assert left.diff(right) == []


def test_a_semantic_sequence_change_is_reported_by_category_and_key() -> None:
    changed = _tables()
    changed["ir.ui.menu"] = [{"name": "Jobs", "sequence": 20, "groups_id": [3, 1, 2]}]
    changed["ir.model.fields"].append({"model": "x_job", "name": "x_extra", "ttype": "char"})
    left = capture(_ReadPort(_tables()), config_allowlist=_ALLOW)
    right = capture(_ReadPort(changed), config_allowlist=_ALLOW)
    assert left != right
    report = left.diff(right)
    assert [(item["category"], item["key"]) for item in report] == [
        ("fields", {"model": "x_job", "name": "x_extra"}),
        ("menus", {"name": "Jobs"}),
    ]
    assert report[0]["before"] == []
    assert report[1]["before"][0]["sequence"] == 10
    assert report[1]["after"][0]["sequence"] == 20


def test_capture_refuses_a_port_without_execute_kw() -> None:
    with pytest.raises(TypeError):
        capture(object())
