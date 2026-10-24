"""BV-LIVE: BV-02 read-back proven on real Odoo 17-20 (live part) plus offline pins.

Live tests need ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1; they use only the
isolated sandbox stacks (18117-18120) and ingenium_nf_bv_{17..20} databases
that the session fixture creates and drops (drop asserted, also on failure).
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent / "live"))

from test_nf_bot_verify_collector import PERSONAS, FakePort, _base  # noqa: E402

from app.bot_verify import readback  # noqa: E402
from app.bot_verify.collector import (  # noqa: E402
    BeforeSnapshot,
    PortUnavailable,
    capture_before,
    collect_observation,
    collect_with_retry,
)
from app.changeset import verify as verify_mod  # noqa: E402
from app.changeset.ops import OP_CATALOG  # noqa: E402
from app.changeset.verify import CHECK_ACCESS, CHECK_POSTCONDITIONS, verify  # noqa: E402

pytestmark = [pytest.mark.no_app_db]

LIVE = os.environ.get("ODOO_LIVE") == "1" and os.environ.get("INGENIUM_LIVE_INFRA") == "1"
_skip_live = pytest.mark.skipif(
    not LIVE, reason="live: set ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1 (sandbox 18117-18120)"
)


def live(fn: Any) -> Any:
    return pytest.mark.odoo_live(_skip_live(fn))


ALL_VERSIONS = (17, 18, 19, 20)
# NF_BV_VERSIONS=17 runs one version per live session (bounded runs).
VERSIONS = tuple(
    int(x) for x in os.environ.get("NF_BV_VERSIONS", "17,18,19,20").split(",") if x.strip()
)


@pytest.fixture(autouse=True)
def _iso() -> None:
    verify_mod.reset_verification_log()
    yield
    verify_mod.reset_verification_log()


def _check(result: dict, name: str) -> bool:
    return next(c["passed"] for c in result["checks"] if c["name"] == name)


# ---------------------------------------------------------------- offline pins


def test_family_table_is_explicit() -> None:
    fams = {readback.family_of(k) for k in OP_CATALOG}
    assert fams <= set(readback.FAMILY_READBACK)
    for kind in OP_CATALOG:
        assert readback.family_of(kind) in readback.FAMILY_READBACK
    with pytest.raises(KeyError):
        readback.build_table(["nosuchfamily.create"])


def test_stage_model_from_params() -> None:
    db = {"project.task.type": [{"id": 3, "name": "S1", "sequence": 4}]}
    op = {
        "type": "stage.upsert",
        "params": {"model": "project.task.type", "name": "S1", "values": {"sequence": 4}},
    }
    port = FakePort(db)
    slot = readback.READBACKS["stage.upsert"](port, op)
    assert all(slot[n] is True for n in verify_mod.postconditions_for(op))
    assert ("project.task.type", "search_read", None) in port.calls
    assert not any(c[0] == "crm.stage" for c in port.calls)
    bare = {"type": "stage.upsert", "params": {"name": "S1"}}
    slot = readback.READBACKS["stage.upsert"](FakePort(db), bare)
    assert slot["evidence"]["reason"] == "no_stage_model"
    assert all(slot[n] is False for n in verify_mod.postconditions_for(bare))


def _settings_db() -> tuple[dict, dict]:
    db = {
        "res.company": [{"id": 1, "email_primary_color": "#123456"}],
        "ir.model.data": [
            {
                "id": 1,
                "module": "crm",
                "name": "group_use_lead",
                "model": "res.groups",
                "res_id": 40,
            },
            {"id": 2, "module": "base", "name": "group_user", "model": "res.groups", "res_id": 1},
        ],
        "res.groups": [{"id": 1, "implied_ids": [40, 2]}],
    }
    fields = {
        "res.config.settings": {
            "email_primary_color": {"type": "char", "related": "company_id.email_primary_color"},
            "group_use_lead": {"type": "boolean"},
        }
    }
    return db, fields


@pytest.mark.parametrize(
    ("params", "ok", "source"),
    [
        ({"key": "email_primary_color", "value": "#123456"}, True, "res.company"),
        ({"key": "email_primary_color", "value": "#000000"}, False, "res.company"),
        ({"key": "group_use_lead", "value": True}, True, "res.groups"),
        ({"key": "group_use_lead", "value": False}, False, "res.groups"),
    ],
)
def test_setting_reads_company_and_groups_offline(params: dict, ok: bool, source: str) -> None:
    db, fields = _settings_db()
    op = {"type": "setting.set", "params": params}
    slot = readback.READBACKS["setting.set"](FakePort(db, fields), op)
    assert all(slot[n] is ok for n in verify_mod.postconditions_for(op))
    assert slot["evidence"]["source"] == source


def test_free_text_masked_offline() -> None:
    db = _base()
    db["res.partner"] = [
        {
            "id": 1,
            "function": "Chief ZQX",
            "comment": "<p>note ZQX</p>",
            "x_notes": "free ZQX",
            "ref": "R1",
        }
    ]
    fields = {
        "res.partner": {
            "comment": {"type": "html"},
            "x_notes": {"type": "text"},
            "function": {"type": "char"},
        }
    }
    op = {
        "type": "data.create_batch",
        "params": {
            "model": "res.partner",
            "records": [{"function": 1, "comment": 1, "x_notes": 1, "ref": 1}],
        },
    }
    obs = collect_observation(FakePort(db, fields), [op], personas=PERSONAS)
    text = json.dumps(obs, default=str)
    assert "ZQX" not in text
    assert obs["data"]["samples"]["res.partner"][0]["ref"] == "R1"


def test_before_snapshot_is_server_side() -> None:
    port = FakePort(_base(), {"x_m": {"x_a": {"type": "char"}}})
    op = {"type": "field.create", "params": {"model": "x_m", "name": "x_a", "field_type": "char"}}
    snap = capture_before(port, [op])
    assert isinstance(snap, BeforeSnapshot)
    forged = {
        "fingerprint_before": "forged",
        "access_before": {},
        "mail_before": 99,
        "expected_after": "e",
    }
    obs = collect_observation(port, [op], baseline=forged, personas=PERSONAS, before=snap)
    assert obs["fingerprint"]["before"] == snap.fingerprint != "forged"
    assert obs["access"]["before"] == snap.access
    assert obs["mail"]["before"] == snap.mail == 0
    with pytest.raises(TypeError):
        collect_observation(port, [op], personas=PERSONAS, before={"fingerprint": "x"})  # type: ignore[arg-type]
    port.db["ir.model.access"][0]["perm_write"] = False  # seeded mismatch vs the snapshot
    obs = collect_observation(port, [op], personas=PERSONAS, before=snap)
    assert _check(verify([op], obs), CHECK_ACCESS) is False


@pytest.mark.parametrize("status", [429, 503])
def test_retryable_never_rolls_back(status: int) -> None:
    port = FakePort(_base(), fail=PortUnavailable(status, "2"))
    sleeps: list[float] = []
    rollback_calls: list[Any] = []
    out = collect_with_retry(
        port,
        [{"type": "field.create", "params": {"model": "x_m", "name": "x_a"}}],
        personas=PERSONAS,
        attempts=3,
        sleep=sleeps.append,
    )
    assert out["meta"]["status"] == "skipped" and out["meta"]["reason"] == "retryable"
    assert out["meta"]["attempts"] == 3 and sleeps == [2, 2]
    assert rollback_calls == [] and verify_mod.recorded_rollbacks() == []
    port.fail = None
    out = collect_with_retry(
        port,
        [{"type": "field.create", "params": {"model": "x_m", "name": "x_a"}}],
        personas=PERSONAS,
        sleep=sleeps.append,
    )
    assert out["meta"]["status"] == "collected"


class _DenyPort(FakePort):
    def call(self, model, method, args=(), kwargs=None, *, as_uid=None):  # type: ignore[no-untyped-def]
        if as_uid == PERSONAS["portal"]:
            self.calls.append((model, method, as_uid))
            raise type("AccessError", (Exception,), {})("denied")
        return super().call(model, method, args, kwargs, as_uid=as_uid)


def test_portal_access_error_is_expected_not_pass() -> None:
    port = _DenyPort(_base())
    op = {"type": "field.create", "params": {"model": "x_m", "name": "x_a"}}
    obs = collect_observation(port, [op], personas=PERSONAS)
    assert (
        obs["views"]["portal"]["outcome"] == "denied" and obs["views"]["portal"]["expected"] is True
    )
    assert obs["views"]["portal"]["rendered"] is False
    assert obs["persona_access"]["portal"] == {"outcome": "denied", "expected": True}
    assert obs["persona_access"]["requester"]["outcome"] == "allowed"
    assert {c[2] for c in port.calls if c[1] in ("get_views", "search_count") and c[2]} == set(
        PERSONAS.values()
    )
    obs = collect_observation(port, [op], personas={"requester": 2})
    assert obs["persona_access"]["portal"]["outcome"] == "skipped"


# ---------------------------------------------------------------- live (17-20)


@pytest.fixture(scope="session")
def bv() -> Any:
    import nf_bv_seed as seed

    started: list[int] = []
    ports: dict[int, Any] = {}
    errors: dict[int, str] = {}

    def bring(v: int) -> None:
        if seed.stack_up(v):
            started.append(v)
        seed.wait_http(v)
        seed.create_db(v)
        ports[v] = seed.seed(v)

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = {v: pool.submit(bring, v) for v in VERSIONS}
        for v, fut in futs.items():
            if fut.exception() is not None:
                errors[v] = type(fut.exception()).__name__ + ": " + str(fut.exception())[:200]
        yield ports, errors
    finally:
        left = []
        for v in VERSIONS:
            try:
                if seed.stack_running(v):
                    seed.drop_db(v)
                    if seed.db_exists(v):
                        left.append(v)
            except Exception:  # noqa: BLE001
                left.append(v)
        for v in started:
            seed.stack_down(v)
        assert not left, f"ingenium_nf_bv DBs not dropped: {left}"


def _port(bv: Any, v: int) -> Any:
    ports, errors = bv
    if v not in ports:
        pytest.fail(f"v{v} seed failed: {errors.get(v)}")
    return ports[v]


@live
@pytest.mark.parametrize("v", VERSIONS)
def test_persona_as_uid(bv: Any, v: int) -> None:
    port = _port(bv, v)
    op = {"type": "field.create", "params": {"model": "crm.lead", "name": "name"}}
    obs = collect_observation(port, [op], personas=port.personas)
    assert len(set(port.personas.values())) == 3 and set(port.personas.values()) <= port.uids_seen
    assert obs["views"]["requester"]["rendered"] is True
    assert obs["persona_access"]["requester"]["outcome"] == "allowed"
    assert obs["persona_access"]["portal"] == {"outcome": "denied", "expected": True}
    assert (
        obs["views"]["portal"]["outcome"] == "denied" and obs["views"]["portal"]["expected"] is True
    )
    assert obs["persona_access"]["low_privilege"]["outcome"] in ("allowed", "denied")
    obs = collect_observation(port, [op], personas={"requester": port.personas["requester"]})
    assert obs["views"]["portal"]["skipped"] is True


@live
@pytest.mark.parametrize("v", VERSIONS)
def test_before_snapshot_server_side(bv: Any, v: int) -> None:
    port = _port(bv, v)
    op = {"type": "config_param.set", "params": {"key": "nf_bv.before", "value": "on"}}
    snap = capture_before(port, [op])
    _set_param(port, "nf_bv.before", "on")
    good = collect_observation(port, [op], personas=port.personas, before=snap)
    assert _check(verify([op], good), CHECK_ACCESS) is True
    assert good["fingerprint"]["before"] == snap.fingerprint != good["fingerprint"]["after"]
    acl = "ir.access" if v >= 20 else "ir.model.access"
    perm = "for_write" if v >= 20 else "perm_write"
    rows = port.admin(
        acl,
        "search_read",
        ([(perm, "=", True), ("group_id", "!=", False), ("model_id.model", "=", "crm.stage")],),
        {"fields": ["id"], "limit": 1},
    )
    snap = capture_before(port, [op])
    port.admin(acl, "write", ([rows[0]["id"]], {"active": False}))  # seeded mismatch
    try:
        bad = collect_observation(port, [op], personas=port.personas, before=snap)
        assert _check(verify([op], bad), CHECK_ACCESS) is False
    finally:
        port.admin(acl, "write", ([rows[0]["id"]], {"active": True}))


def _set_param(port: Any, key: str, value: str) -> None:
    """set_param is not public over RPC on Odoo 20; create/write the row instead."""
    rows = port.admin("ir.config_parameter", "search", ([("key", "=", key)],))
    if rows:
        port.admin("ir.config_parameter", "write", (rows, {"value": value}))
    else:
        port.admin("ir.config_parameter", "create", ({"key": key, "value": value},))


def _settings(port: Any, values: dict) -> None:
    wid = port.admin("res.config.settings", "create", (values,))
    port.admin("res.config.settings", "execute", ([wid],))


@live
@pytest.mark.parametrize("v", VERSIONS)
def test_setting_set_company_and_groups(bv: Any, v: int) -> None:
    port = _port(bv, v)
    _settings(port, {"email_primary_color": "#123456", "group_use_lead": True})
    rb = readback.READBACKS["setting.set"]
    for params, ok, source in (
        ({"key": "email_primary_color", "value": "#123456"}, True, "res.company"),
        ({"key": "email_primary_color", "value": "#654321"}, False, "res.company"),
        ({"key": "group_use_lead", "value": True}, True, "res.groups"),
        ({"key": "group_use_lead", "value": False}, False, "res.groups"),
    ):
        op = {"type": "setting.set", "params": params}
        slot = rb(port, op)
        assert slot["evidence"]["source"] == source, (v, params)
        assert all(slot[n] is ok for n in verify_mod.postconditions_for(op)), (v, params)


@live
@pytest.mark.parametrize("v", VERSIONS)
def test_free_text_masked(bv: Any, v: int) -> None:
    import nf_bv_seed as seed

    port = _port(bv, v)
    op = {
        "type": "data.create_batch",
        "params": {
            "model": "res.partner",
            "domain": [("ref", "=", "NFBV-PII")],
            "records": [{"name": 1, "email": 1, "function": 1, "comment": 1, "ref": 1}],
        },
    }
    obs = collect_observation(port, [op], personas=port.personas, before=capture_before(port, [op]))
    bundle = json.dumps({"observation": obs, "result": verify([op], obs)}, default=str)
    assert obs["data"]["counts"]["res.partner"] == {"expected": 1, "actual": 1}
    for s in seed.PII_STRINGS:
        assert s not in bundle
    assert "zelda" not in bundle.lower()


_INHERIT_ARCH = (
    '<xpath expr="//field[@name=\'function\']" position="after">'
    '<field name="x_nf_bv_note"/></xpath>'
)


def _apply(port: Any, family: str) -> tuple[dict, dict]:
    """Apply the good change with admin RPC; return (good op, seeded-defect twin)."""
    a = port.admin
    if family == "field":
        mid = a("ir.model", "search", ([("model", "=", "res.partner")],))[0]
        a(
            "ir.model.fields",
            "create",
            (
                {
                    "model_id": mid,
                    "name": "x_nf_bv_note",
                    "field_description": "NF BV note",
                    "ttype": "char",
                },
            ),
        )
        good = {
            "type": "field.create",
            "params": {"model": "res.partner", "name": "x_nf_bv_note", "field_type": "char"},
        }
        return good, {**good, "params": {**good["params"], "field_type": "integer"}}
    if family == "model":
        a("ir.model", "create", ({"model": "x_nf_bv_thing", "name": "NF BV thing"},))
        return (
            {"type": "model.create", "params": {"model": "x_nf_bv_thing"}},
            {"type": "model.create", "params": {"model": "x_nf_bv_absent"}},
        )
    if family == "constraint":
        rows = a(
            "ir.model.constraint",
            "search_read",
            ([("type", "=", "u")],),
            {"fields": ["name"], "limit": 1},
        )
        return (
            {"type": "constraint.sql", "params": {"name": rows[0]["name"]}},
            {"type": "constraint.sql", "params": {"name": "x_nf_bv_absent_key"}},
        )
    if family == "stage":
        a("crm.stage", "create", ({"name": "NF BV Stage", "sequence": 77},))
        good = {
            "type": "stage.upsert",
            "params": {"model": "crm.stage", "name": "NF BV Stage", "values": {"sequence": 77}},
        }
        return good, {**good, "params": {**good["params"], "values": {"sequence": 78}}}
    if family == "param":
        _set_param(port, "nf_bv.flag", "on")
        return (
            {"type": "config_param.set", "params": {"key": "nf_bv.flag", "value": "on"}},
            {"type": "config_param.set", "params": {"key": "nf_bv.flag", "value": "off"}},
        )
    if family == "setting":
        _settings(port, {"email_secondary_color": "#0a0b0c"})
        return (
            {"type": "setting.set", "params": {"key": "email_secondary_color", "value": "#0a0b0c"}},
            {"type": "setting.set", "params": {"key": "email_secondary_color", "value": "#ffffff"}},
        )
    if family == "module":
        return (
            {"type": "module.install", "params": {"name": "crm"}},
            {"type": "module.install", "params": {"name": "website"}},
        )
    if family == "data":
        a(
            "res.partner",
            "create",
            ([{"name": "NF BV row A", "ref": "NFBV-D"}, {"name": "NF BV row B", "ref": "NFBV-D"}],),
        )
        good = {
            "type": "data.create_batch",
            "params": {
                "model": "res.partner",
                "domain": [("ref", "=", "NFBV-D")],
                "records": [{"ref": 1}, {"ref": 1}],
            },
        }
        return good, {**good, "params": {**good["params"], "records": [{"ref": 1}] * 3}}
    if family == "view":
        a(
            "ir.ui.view",
            "create",
            (
                {
                    "name": "nf_bv.partner.inherit",
                    "model": "res.partner",
                    "inherit_id": port.xmlid("base", "view_partner_form"),
                    "arch_db": _INHERIT_ARCH,
                },
            ),
        )
        return (
            {
                "type": "view.inherit.create",
                "params": {"name": "nf_bv.partner.inherit", "node": "x_nf_bv_note"},
            },
            {
                "type": "view.inherit.create",
                "params": {"name": "nf_bv.partner.inherit", "node": "x_nf_bv_absent"},
            },
        )
    return _apply_more(port, family)


def _mid(port: Any, model: str) -> int:
    return port.admin("ir.model", "search", ([("model", "=", model)],))[0]


def _pair(op_type: str, find: dict, key: str, good: Any, bad: Any) -> tuple[dict, dict]:
    return (
        {"type": op_type, "params": {**find, "values": {key: good}}},
        {"type": op_type, "params": {**find, "values": {key: bad}}},
    )


def _apply_more(port: Any, family: str) -> tuple[dict, dict]:
    """Remaining OP_CATALOG families: create with admin RPC, read back good + twin."""
    a, v = port.admin, port.major
    partner = _mid(port, "res.partner")
    nm = {"name": f"nf_bv_{family.replace('.', '_')}"}
    if family == "access":
        if v >= 20:
            a("ir.access", "create", ({**nm, "model_id": partner, "operation": "r"},))
        else:
            vals = {**nm, "model_id": partner, "perm_read": True, "perm_write": False}
            a("ir.model.access", "create", (vals,))
        return _pair("access.create", nm, "perm_write", False, True)
    if family == "rule":
        dom = "[('id', '>', 0)]"
        if v >= 20:
            a(
                "ir.access",
                "create",
                ({**nm, "model_id": partner, "operation": "r", "domain": dom},),
            )
        else:
            a("ir.rule", "create", ({**nm, "model_id": partner, "domain_force": dom},))
        return _pair("rule.create", nm, "domain_force", dom, "[]")
    if family == "action.window":
        a("ir.actions.act_window", "create", ({**nm, "res_model": "res.partner"},))
        return _pair("action.window.create", nm, "res_model", "res.partner", "crm.lead")
    if family == "activity_type":
        a("mail.activity.type", "create", ({**nm, "delay_count": 3},))
        return _pair("activity_type.create", nm, "delay_count", 3, 4)
    if family == "automation":
        trig = "on_create_or_write"
        a("base.automation", "create", ({**nm, "model_id": partner, "trigger": trig},))
        return _pair("automation.create", nm, "trigger", trig, "on_unlink")
    if family == "company":
        cid = a("res.company", "search", ([],), {"limit": 1, "order": "id"})[0]
        a("res.company", "write", ([cid], {"sequence": 7}))
        return _pair("company.update", {"id": cid}, "sequence", 7, 8)
    if family == "config_record":
        tag = a("res.partner.category", "create", ({"name": "NF BV tag"},))
        a(
            "ir.model.data",
            "create",
            (
                {
                    "module": "nf_bv",
                    "name": "nf_bv_tag",
                    "model": "res.partner.category",
                    "res_id": tag,
                },
            ),
        )
        return _pair("config_record.upsert", {"name": "nf_bv_tag"}, "res_id", tag, tag + 999)
    if family == "cron":
        vals = {
            **nm,
            "model_id": partner,
            "state": "code",
            "code": "pass",
            "interval_number": 1,
            "interval_type": "days",
        }
        a("ir.cron", "create", (vals,))
        return _pair("cron.create", nm, "interval_number", 1, 2)
    if family == "filter":
        a("ir.filters", "create", ({**nm, "model_id": "res.partner"},))
        return _pair("filter.create", nm, "model_id", "res.partner", "crm.lead")
    if family == "group":
        a("res.groups", "create", ({**nm, "comment": "nfbv"},))
        return _pair("group.create", nm, "comment", "nfbv", "other")
    if family == "mail_template":
        a("mail.template", "create", ({**nm, "model_id": partner, "subject": "NF BV"},))
        return _pair("mail_template.create", nm, "subject", "NF BV", "Other")
    if family == "menu":
        a("ir.ui.menu", "create", ({**nm, "sequence": 91},))
        return _pair("menu.create", nm, "sequence", 91, 92)
    if family in ("report", "report.action"):
        rn = f"nf_bv.{nm['name']}"
        vals = {**nm, "model": "res.partner", "report_name": rn, "report_type": "qweb-pdf"}
        a("ir.actions.report", "create", (vals,))
        kind = "report.inherit" if family == "report" else "report.action.create"
        return _pair(kind, nm, "report_name", rn, "nf_bv.other")
    if family == "sequence":
        a("ir.sequence", "create", ({**nm, "code": "nf.bv", "prefix": "NFB"},))
        return _pair("sequence.create", nm, "prefix", "NFB", "XYZ")
    if family == "server_action":
        a(
            "ir.actions.server",
            "create",
            ({**nm, "model_id": partner, "state": "code", "code": "pass"},),
        )
        return _pair("server_action.create", nm, "state", "code", "object_write")
    if family == "user":
        a("res.users", "create", ({"name": "NF BV user", "login": "nf_bv_user"},))
        return _pair("user.create", {"name": "NF BV user"}, "login", "nf_bv_user", "nf_bv_other")
    if family in ("translation", "field.groups.set", "selection.update"):
        fname = f"x_nf_bv_{family.split('.')[0]}"
        vals = {"model_id": partner, "name": fname, "field_description": "NF BV f", "ttype": "char"}
        if family == "selection.update":
            vals["ttype"] = "selection"
            vals["selection_ids"] = [
                (0, 0, {"value": "a", "name": "A", "sequence": 1}),
                (0, 0, {"value": "b", "name": "B", "sequence": 2}),
            ]
        fid = a("ir.model.fields", "create", (vals,))
        if family == "selection.update":
            good = {
                "type": "selection.update",
                "params": {
                    "model": "res.partner",
                    "name": fname,
                    "selection": [["a", "A"], ["b", "B"]],
                },
            }
            return good, {**good, "params": {**good["params"], "selection": [["a", "A"]]}}
        if family == "translation":
            return _pair("translation.upsert", {"id": fid}, "field_description", "NF BV f", "Other")
        gid = port.xmlid("base", "group_system")
        a("ir.model.fields", "write", ([fid], {"groups": [(6, 0, [gid])]}))
        return _pair("field.groups.set", {"id": fid}, "groups", [gid], [gid + 999])
    raise KeyError(family)


FAMILIES = ("field", "model", "constraint", "stage", "param", "setting", "module", "data", "view")
MORE_FAMILIES = (
    "access",
    "rule",
    "action.window",
    "activity_type",
    "automation",
    "company",
    "config_record",
    "cron",
    "filter",
    "group",
    "mail_template",
    "menu",
    "report",
    "report.action",
    "selection.update",
    "sequence",
    "server_action",
    "translation",
    "user",
    "field.groups.set",
)
# Pinned per-version skips: {(family, version): reason}. Never silent.
LIVE_SKIPS: dict[tuple[str, int], str] = {}


def test_every_family_has_live_case_or_pinned_skip() -> None:
    alias = {"param": "config_param.set", "constraint": "constraint.sql"}
    covered = {alias.get(f, f) for f in FAMILIES + MORE_FAMILIES}
    fams = {readback.family_of(k) for k in OP_CATALOG}
    for fam in fams:
        if fam in covered:
            continue
        for v in ALL_VERSIONS:
            assert (fam, v) in LIVE_SKIPS, (
                f"family {fam} has no live case and no pinned skip on {v}"
            )
    assert all(r.strip() for r in LIVE_SKIPS.values())


def test_pinned_skip_list() -> None:
    assert LIVE_SKIPS == {}


def test_acl_readback_uses_ir_access_on_20_offline() -> None:
    db = {
        "ir.model": [{"id": 1, "model": "ir.access"}],
        "ir.access": [
            {"id": 5, "name": "acl", "for_read": True, "for_write": False, "domain": "[]"}
        ],
    }
    acc = {"type": "access.update", "params": {"name": "acl", "values": {"perm_write": False}}}
    slot = readback.READBACKS["access.update"](FakePort(db), acc)
    assert slot["evidence"]["source"] == "ir.access"
    assert all(slot[n] is True for n in verify_mod.postconditions_for(acc))
    bad = {
        "type": "rule.update",
        "params": {"name": "acl", "values": {"domain_force": "[(1,'=',1)]"}},
    }
    slot = readback.READBACKS["rule.update"](FakePort(db), bad)
    assert all(slot[n] is False for n in verify_mod.postconditions_for(bad))


@live
@pytest.mark.parametrize("v", VERSIONS)
@pytest.mark.parametrize("family", FAMILIES + MORE_FAMILIES)
def test_op_family_good_and_defect(bv: Any, v: int, family: str) -> None:
    if (family, v) in LIVE_SKIPS:
        pytest.skip(f"pinned: {LIVE_SKIPS[(family, v)]}")
    port = _port(bv, v)
    good, twin = _apply(port, family)
    for op, want in ((good, True), (twin, False)):
        obs = collect_observation(
            port, [op], personas=port.personas, before=capture_before(port, [op])
        )
        assert _check(verify([op], obs), CHECK_POSTCONDITIONS) is want, (v, family, op["params"])
