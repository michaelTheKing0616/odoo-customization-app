"""BV-02: live evidence collector (fake port only; no Odoo import)."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from app.bot_verify import collector, readback
from app.bot_verify.collector import OdooUnavailable, PortUnavailable, collect_observation
from app.changeset import verify as verify_mod
from app.changeset.data_ops import SAMPLE_LIMIT
from app.changeset.ops import OP_CATALOG
from app.changeset.verify import CHECK_POSTCONDITIONS, verify

READS = {"search_read", "read", "fields_get", "get_views", "search_count"}


@pytest.fixture(autouse=True)
def _iso() -> None:
    verify_mod.reset_verification_log()
    yield
    verify_mod.reset_verification_log()


def _match(row: dict, domain: list) -> bool:
    for term in domain or []:
        if not isinstance(term, (list, tuple)) or len(term) != 3:
            continue
        f, op, v = term
        val = row.get(f)
        if op == "=" and val != v:
            return False
        if op == "in" and val not in v:
            return False
    return True


class FakePort:
    def __init__(
        self,
        db: dict[str, list[dict]] | None = None,
        fields: dict | None = None,
        *,
        db_name: str = "ingenium_wt_bv02",
        fail: Any = None,
    ) -> None:
        self.db_name = db_name
        self.db = db or {}
        self.fields = fields or {}
        self.calls: list[tuple[str, str, Any]] = []
        self.fail = fail

    def call(
        self,
        model: str,
        method: str,
        args: Any = (),
        kwargs: dict | None = None,
        *,
        as_uid: int | None = None,
    ) -> Any:
        self.calls.append((model, method, as_uid))
        if self.fail:
            raise self.fail
        kwargs = kwargs or {}
        rows = self.db.get(model, [])
        if method == "search_read":
            hit = [r for r in rows if _match(r, args[0] if args else kwargs.get("domain", []))]
            lim = kwargs.get("limit")
            out = hit[:lim] if lim else hit
            fl = kwargs.get("fields")
            return [{k: v for k, v in r.items() if not fl or k in fl} for r in out]
        if method == "search_count":
            return len([r for r in rows if _match(r, args[0] if args else [])])
        if method == "read":
            ids = args[0]
            return [dict(r) for r in rows if r.get("id") in ids]
        if method == "fields_get":
            return self.fields.get(model, {})
        if method == "get_views":
            return {"views": {"form": {"arch": "<form/>"}}}
        raise AssertionError(f"write call {method}")

    def writes(self) -> list:
        return [c for c in self.calls if c[1] not in READS]


def _base() -> dict:
    return {
        "ir.model.access": [
            {
                "id": 1,
                "name": "a",
                "group_id": [3, "Users"],
                "model_id": [9, "x_m"],
                "perm_read": True,
                "perm_write": True,
                "perm_create": False,
                "perm_unlink": False,
            }
        ],
        "mail.mail": [],
        "ir.actions.act_window": [{"id": 5, "name": "Act", "res_model": "x_m"}],
        "x_m": [{"id": 1, "name": "r"}],
    }


def _field_op(value_type: str = "char") -> dict:
    return {
        "type": "field.create",
        "params": {"model": "x_m", "name": "x_a", "field_type": value_type},
    }


PERSONAS = {"requester": 2, "low_privilege": 6, "portal": 8}
BASE = {
    "fingerprint_before": "f0",
    "access_before": {"Users": {"x_m": ["read", "write"]}},
    "mail_before": 0,
}


def test_t1_zero_write_calls_and_full_mapping() -> None:
    port = FakePort(_base(), {"x_m": {"x_a": {"type": "char"}}})
    obs = collect_observation(port, [_field_op()], baseline=BASE, personas=PERSONAS)
    assert port.writes() == []
    for key in ("postconditions", "fingerprint", "views", "smoke", "access", "mail", "data"):
        assert key in obs
    assert {c[1] for c in port.calls} <= READS


def test_t1b_collector_takes_no_run_or_artifact_ids() -> None:
    params = set(inspect.signature(collect_observation).parameters)
    assert not params & {"run_id", "artifact_id", "connection_id"}


def test_t2_readbacks_cover_op_catalog() -> None:
    assert set(readback.READBACKS) == set(OP_CATALOG)
    assert all(callable(f) for f in readback.READBACKS.values())


@pytest.mark.parametrize(
    ("op", "db", "fields", "ok"),
    [
        (_field_op(), {}, {"x_m": {"x_a": {"type": "char"}}}, True),
        (_field_op(), {}, {"x_m": {"x_a": {"type": "integer"}}}, False),
        (
            {"type": "access.update", "params": {"id": 1, "values": {"perm_create": True}}},
            _base(),
            {},
            False,
        ),
        (
            {"type": "access.update", "params": {"id": 1, "values": {"perm_write": True}}},
            _base(),
            {},
            True,
        ),
        (
            {"type": "config_param.set", "params": {"key": "k", "value": "v"}},
            {"ir.config_parameter": [{"id": 1, "key": "k", "value": "v"}]},
            {},
            True,
        ),
        (
            {"type": "setting.set", "params": {"key": "k", "value": "new"}},
            {"ir.config_parameter": [{"id": 1, "key": "k", "value": "old"}]},
            {},
            False,
        ),
        (
            {"type": "module.install", "params": {"name": "crm"}},
            {"ir.module.module": [{"id": 1, "name": "crm", "state": "installed"}]},
            {},
            True,
        ),
        (
            {"type": "module.install", "params": {"name": "crm"}},
            {"ir.module.module": [{"id": 1, "name": "crm", "state": "uninstalled"}]},
            {},
            False,
        ),
        (
            {"type": "view.inherit.create", "params": {"name": "v1", "node": "x_a"}},
            {
                "ir.ui.view": [
                    {"id": 1, "name": "v1", "arch_db": "<field name='x_a'/>", "active": True}
                ]
            },
            {},
            True,
        ),
        (
            {"type": "view.inherit.create", "params": {"name": "v1", "node": "x_a"}},
            {"ir.ui.view": [{"id": 1, "name": "v1", "arch_db": "<form/>", "active": True}]},
            {},
            False,
        ),
        (
            {"type": "automation.create", "params": {"name": "au"}},
            {"base.automation": [{"id": 1, "name": "au", "active": True}]},
            {},
            True,
        ),
        (
            {"type": "automation.create", "params": {"name": "au"}},
            {"base.automation": [{"id": 1, "name": "au", "active": False}]},
            {},
            False,
        ),
        (
            {"type": "automation.disable", "params": {"name": "au"}},
            {"base.automation": [{"id": 1, "name": "au", "active": False}]},
            {},
            True,
        ),
        (
            {"type": "data.create_batch", "params": {"model": "x_m", "records": [{"name": "r"}]}},
            _base(),
            {},
            True,
        ),
        ({"type": "data.delete", "params": {"model": "x_m", "ids": [1]}}, _base(), {}, False),
    ],
)
def test_t3_postcondition_kinds(op: dict, db: dict, fields: dict, ok: bool) -> None:
    slot = readback.READBACKS[op["type"]](FakePort(db, fields), op)
    names = verify_mod.postconditions_for(op)
    assert all(slot[n] is ok for n in names)


def test_t4_missing_persona_skipped_never_pass() -> None:
    port = FakePort(_base(), {"x_m": {"x_a": {"type": "char"}}})
    obs = collect_observation(port, [_field_op()], baseline=BASE, personas={"requester": 2})
    assert obs["views"]["portal"]["skipped"] is True
    assert obs["views"]["portal"]["reason"] == "persona_missing"
    res = verify([_field_op()], obs)
    by = {c["name"]: c["passed"] for c in res["checks"]}
    assert by["view_render_requester"] is True
    assert by["view_render_portal"] is False and by["view_render_low_privilege"] is False
    assert ("x_m", "get_views", 2) in port.calls


def test_t5_seeded_mismatch_fails_and_claims_ignored() -> None:
    port = FakePort(_base(), {"x_m": {"x_a": {"type": "integer"}}})
    cs = [dict(_field_op(), status="applied", verified=True, success=True)]
    obs = collect_observation(port, cs, baseline=BASE, personas=PERSONAS)
    res = verify(cs, obs, model_success=True)
    assert CHECK_POSTCONDITIONS in res["failed"]
    assert res["verified"] is False


def test_t5b_all_pass_when_live_matches() -> None:
    port = FakePort(_base(), {"x_m": {"x_a": {"type": "char"}}})
    obs = collect_observation(
        port, [_field_op()], baseline=dict(BASE, expected_after=None), personas=PERSONAS
    )
    obs["fingerprint"]["expected_after"] = obs["fingerprint"]["after"]
    res = verify([_field_op()], obs)
    assert res["failed"] == [], res["checks"]


def test_t6_samples_capped() -> None:
    db = _base()
    db["x_m"] = [{"id": i, "name": f"r{i}"} for i in range(1, 60)]
    op = {
        "type": "data.create_batch",
        "params": {"model": "x_m", "records": [{} for _ in range(59)]},
    }
    obs = collect_observation(FakePort(db), [op], baseline=BASE, personas=PERSONAS)
    assert len(obs["data"]["samples"]["x_m"]) <= SAMPLE_LIMIT
    assert obs["data"]["counts"]["x_m"] == {"expected": 59, "actual": 59}


def test_t7_pii_masked() -> None:
    db = _base()
    db["res.partner"] = [
        {
            "id": 1,
            "name": "Ada Obi",
            "email": "ada@example.com",
            "phone": "+234 803 555 0101",
            "street": "1 Marina",
        }
    ]
    op = {"type": "data.create_batch", "params": {"model": "res.partner", "records": [{}]}}
    obs = collect_observation(FakePort(db), [op], baseline=BASE, personas=PERSONAS)
    text = repr(obs)
    for secret in ("ada@example.com", "Ada Obi", "803 555", "1 Marina"):
        assert secret not in text


@pytest.mark.parametrize(("status", "header", "want"), [(429, "17", 17), (503, None, 5)])
def test_t8_unavailable_skipped_with_retry(status: int, header: str | None, want: int) -> None:
    port = FakePort(fail=PortUnavailable(status, header))
    obs = collect_observation(port, [_field_op()], baseline=BASE, personas=PERSONAS)
    assert obs["meta"] == {"status": "skipped", "reason": "odoo_unavailable", "retry_after_s": want}
    assert verify([_field_op()], obs)["verified"] is False
    assert issubclass(OdooUnavailable, Exception)


def test_t9_non_ingenium_db_rejected() -> None:
    with pytest.raises(ValueError):
        collect_observation(
            FakePort(db_name="aonb_prod"), [_field_op()], baseline=BASE, personas=PERSONAS
        )


def test_no_odoo_import() -> None:
    src = inspect.getsource(collector) + inspect.getsource(readback)
    assert "import odoo" not in src and "xmlrpc" not in src


def test_t7b_m2o_display_name_email_from_masked_and_fields_limited() -> None:
    db = _base()
    db["crm.lead"] = [
        {
            "id": 1,
            "partner_id": [7, "Jane Doe"],
            "display_name": "Jane Doe Lead",
            "email_from": "jane@corp.ng",
            "contact_address": "Lekki Phase 1",
            "function": "CEO Secret",
        }
    ]
    op = {
        "type": "data.create_batch",
        "params": {
            "model": "crm.lead",
            "records": [{}],
            "fields": ["partner_id", "display_name", "email_from", "contact_address"],
        },
    }
    port = FakePort(db)
    obs = collect_observation(port, [op], baseline=BASE, personas=PERSONAS)
    text = repr(obs)
    for secret in ("Jane Doe", "jane@corp.ng", "Lekki", "CEO Secret"):
        assert secret not in text
    assert obs["data"]["samples"]["crm.lead"][0]["partner_id"][0] == 7
    assert set(readback.sample_fields(op)) == {
        "id",
        "partner_id",
        "display_name",
        "email_from",
        "contact_address",
    }


@pytest.mark.parametrize(
    "key",
    [
        "email_normalized",
        "phone_sanitized",
        "mobile2",
        "complete_name",
        "login",
        "street2",
        "city",
        "zip",
        "website",
        "commercial_company_name",
    ],
)
def test_t7c_key_patterns_masked(key: str) -> None:
    assert readback.mask({key: "SECRETVAL"})[key] != "SECRETVAL"


@pytest.mark.parametrize(("left", "ok"), [(1, True), (2, False), (0, False)])
def test_t10_merge_checks_expected_count(left: int, ok: bool) -> None:
    db = {"res.partner": [{"id": i} for i in range(1, left + 1)]}
    op = {"type": "data.merge", "params": {"model": "res.partner", "ids": [1, 2]}}
    slot = readback.READBACKS["data.merge"](FakePort(db), op)
    assert all(slot[n] is ok for n in verify_mod.postconditions_for(op))


def test_t11_no_model_no_partner_fallback() -> None:
    assert readback.target_model([{"type": "module.install", "params": {"name": "crm"}}]) is None
    assert readback.target_model([_field_op()]) == "x_m"


def test_t12_no_model_views_and_smoke_skipped() -> None:
    cs = [{"type": "module.install", "params": {"name": "crm"}}]
    db = _base()
    db["ir.module.module"] = [{"id": 1, "name": "crm", "state": "installed"}]
    db["res.partner"] = [{"id": 1}]
    port = FakePort(db)
    obs = collect_observation(port, cs, baseline=BASE, personas=PERSONAS)
    assert not any(c[0] == "res.partner" for c in port.calls)
    for name in ("requester", "low_privilege", "portal"):
        assert obs["views"][name]["skipped"] is True
        assert obs["views"][name]["reason"] == "no_target_model"
    assert all(p["passed"] is False and p["reason"] == "no_target_model" for p in obs["smoke"])
    by = {c["name"]: c["passed"] for c in verify(cs, obs)["checks"]}
    assert not any(
        by[k]
        for k in (
            "view_render_requester",
            "view_render_low_privilege",
            "view_render_portal",
            "smoke_probes",
        )
    )
