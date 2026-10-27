"""BOT-RISK-CLASSIFIER: classifier, per-button resolver, RF-* engine, caps/tiers, routes.

Offline part uses a fake public-ORM port; live part (ODOO_LIVE=1 + INGENIUM_LIVE_INFRA=1)
resolves seed buttons from real views on ingenium_nf_bv_* DBs via BV-LIVE's session fixture.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.bot_verify import targets as tg
from app.bots.risk import buttons as bt
from app.bots.risk import classifier as cl
from app.bots.risk import rules as ru

pytestmark = [pytest.mark.no_app_db]
CSV = Path.home() / ".ingenium_nf/taxonomy/catalogue.csv"


def check(d, g, proofs=None):
    """Test verifier: proof-backed controls named in g.proven stand for proofs that a real
    RouteA / snapshot.Verified confirmed (the snapshot suite exercises the real ones)."""
    return cl.check(d, g, proofs or (lambda c: c in g.proven))


class MemAuditStore:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def record(self, connection_id: Any, db_name: str, decision: str, reason: str) -> None:
        self.rows.append(
            dict(connection_id=connection_id, db_name=db_name, decision=decision, reason=reason)
        )


class BrokenStore:
    def record(self, *a: Any) -> None:
        raise OSError("db down")


@pytest.fixture(autouse=True)
def store() -> Any:
    prev, s = tg.audit_store(), MemAuditStore()
    tg.configure_audit_store(s)
    yield s
    tg.configure_audit_store(prev)


class FakePort:
    """Minimal public-ORM double: get_views/fields_get/read/search/search_read."""

    def __init__(
        self,
        archs: dict[tuple[str, Any], str],
        recs: dict[str, dict[int, dict]] | None = None,
        transient: set[str] | None = None,
    ) -> None:
        self.archs, self.recs, self.transient = archs, recs or {}, transient or set()
        self.calls: list[tuple[str, str]] = []

    def call(self, model: str, method: str, args: Any = (), kwargs: dict | None = None) -> Any:
        self.calls.append((model, method))
        kw = kwargs or {}
        if method == "get_views":
            vid = args[0][0][0] or None
            return {"views": {"form": {"arch": self.archs[(model, vid)]}}}
        if method == "fields_get":
            keys = {k for r in self.recs.get(model, {}).values() for k in r}
            return {k: {"type": "char"} for k in keys}
        if method == "read":
            return (
                [{k: v for k, v in self.recs[model][args[0][0]].items() if k in kw["fields"]}]
                if args[0][0] in self.recs.get(model, {})
                else []
            )
        if model == "ir.model" and method == "search":
            return [1] if args[0][0][2] in self.recs or args[0][0][2] in self.transient else []
        if model == "ir.model" and method == "search_read":
            m = args[0][0][2]
            return (
                [{"transient": m in self.transient}]
                if m in self.transient | {"res.partner"}
                else []
            )
        if method == "search_read":
            return list(self.recs.get(model, {}).values())
        if method == "search":
            return [
                i for i, r in self.recs.get(model, {}).items() if r.get("name") == args[0][0][2]
            ]
        raise AssertionError((model, method))


def form(*btns: str) -> str:
    return "<form><header>" + "".join(btns) + "</header><sheet/></form>"


def ctx(v: int = 17, route: ru.Route = "B", **kw: Any) -> cl.ClassifyCtx:
    return cl.ClassifyCtx(version=v, route=route, connection_id="c1", db_name="ingenium_nf_x", **kw)


def ok(task: str, **kw: Any) -> cl.Decision:
    d = cl.classify(task, ctx(**kw))
    assert isinstance(d, cl.Decision), d
    return d


# ---------------------------------------------------------------- catalogue data


def test_catalogue_rows_complete_and_traceable() -> None:
    rows, controls, sha = cl.catalogue()
    assert len(rows) == 11937 and set(controls) == set(ru.CLASSES)
    assert {c for c, _ in rows.values()} == set(ru.CLASSES)
    if CSV.exists():
        assert hashlib.sha256(CSV.read_bytes()).hexdigest() == sha


# ---------------------------------------------------------------- AC1


def test_ac1_shape_and_unknown_task_refused(store: MemAuditStore) -> None:
    d = ok("m:res.partner.category:mass-write")
    out = d.as_dict()
    assert set(out) == {"class", "controls", "tier"} and out["class"] == "R3"
    assert out["tier"] == "L2" and "snapshot-proof" in out["controls"]
    r = cl.classify("m:res.partner:frobnicate", ctx())
    assert isinstance(r, ru.Refusal) and r.rule == "RF-ANY" and "unknown task" in r.reason
    assert store.rows[-1]["decision"] == "refused" and store.rows[-1]["reason"].startswith("RF-ANY")


# ---------------------------------------------------------------- AC2 per-button


def test_ac2_label_never_classifies() -> None:
    p = FakePort(
        {
            ("account.move", None): form(
                '<button name="action_post" type="object" string="Process"/>'
            ),
            ("res.partner", None): form(
                '<button name="open_commercial_entity" type="object" string="Post"/>'
            ),
        }
    )
    assert bt.resolve_button(p, "account.move", label="Process").cls == "R4"
    assert bt.resolve_button(p, "res.partner", label="Post").cls == "R0"


def test_ac2_unknown_method_failsafe_or_refused() -> None:
    assert bt.method_effect("account.move", "action_zz").cls == "R4"
    for m in ("stock.picking", "mrp.production", "pos.order", "repair.order"):
        assert bt.method_effect(m, "do_thing").subkind == "fail-safe"
    assert isinstance(bt.method_effect("res.partner", "do_thing"), bt.Unresolved)
    v = max(cl.catalogue()[0]["b:res.partner:action_schedule_meeting"][1])
    r = cl.classify("b:res.partner:action_schedule_meeting", ctx(v=v))
    assert isinstance(r, ru.Refusal) and "unclassified" in r.reason  # catalogue said R2W


def test_ac2_same_method_two_models() -> None:
    assert bt.method_effect("account.move", "action_post").cls == "R4"
    assert isinstance(bt.method_effect("x_custom.model", "action_post"), bt.Unresolved)
    assert bt.method_effect("x_custom.model", "unlink").cls == "R6"


def test_ac2_inherited_arch_last_applied_wins() -> None:
    # get_views returns the combined arch: an inheriting view retargeted the button.
    p = FakePort(
        {
            ("crm.lead", None): form(
                '<button name="action_post_custom" type="object" string="Mark won"/>'
            ),
            ("crm.lead", 9): form(
                '<button name="action_set_won" type="object" string="Mark won"/>'
            ),
        }
    )
    assert isinstance(bt.resolve_button(p, "crm.lead", label="Mark won"), bt.Unresolved)
    assert bt.resolve_button(p, "crm.lead", label="Mark won", view_id=9).cls == "R2W"
    assert ("crm.lead", "get_views") in p.calls and ("ir.ui.view", "read") not in p.calls


def _sa(state: str, model: str, code: str = "", kids: list[int] | None = None) -> dict:
    return {
        "state": state,
        "model_name": model,
        "code": code,
        "child_ids": kids or [],
        "update_path": "",
        "name": "sa",
    }


def test_ac2_server_action_buttons() -> None:
    recs = {
        "ir.actions.actions": {
            7: {"type": "ir.actions.server"},
            8: {"type": "ir.actions.server"},
            9: {"type": "ir.actions.server"},
            10: {"type": "ir.actions.client"},
        },
        "ir.actions.server": {
            7: _sa("code", "res.partner", "for rec in records:\n    rec.message_post(body='x')"),
            8: _sa("code", "res.partner", "import os\nos.system('x')"),
            9: _sa("multi", "res.partner", kids=[11, 12]),
            11: _sa("object_create", "res.partner"),
            12: _sa("code", "res.partner", "env['account.move'].browse(1).action_post()"),
        },
    }
    p = FakePort(
        {("res.partner", None): form('<button name="7" type="action" string="Tidy"/>')}, recs
    )
    assert bt.classify_action(p, 7).cls == "R5"
    assert isinstance(bt.classify_action(p, 8), bt.Unresolved)
    assert isinstance(bt.classify_action(p, 9), bt.Unresolved)  # nested call arg -> refuse
    recs["ir.actions.server"][12] = _sa("code", "res.partner", "env['account.move'].action_post()")
    # kid 11 is object_create with an unresolved field set -> the whole chain is refused
    assert isinstance(bt.classify_action(p, 9), bt.Unresolved)
    assert isinstance(bt.classify_action(p, 10), bt.Unresolved)  # opaque client action
    assert bt.resolve_button(p, "res.partner", label="Tidy").cls == "R5"
    assert (
        bt.code_effects("records.write({'active': False})", "res.partner.category").subkind
        == "archive"
    )
    assert isinstance(
        bt.code_effects("records.write({'active': False})", "res.partner"), bt.Unresolved
    )
    # default-deny: account.move is not on the low-risk allowlist and `ref` has no floor
    assert isinstance(bt.code_effects("records.write({'ref': 1})", "account.move"), bt.Unresolved)
    assert bt.code_effects("records.write({'state': 'posted'})", "account.move").cls == "R4"


def test_ac2_wizard_wrapped_posting() -> None:
    recs = {
        "ir.actions.actions": {
            5: {"type": "ir.actions.act_window"},
            6: {"type": "ir.actions.act_window"},
        },
        "ir.actions.act_window": {
            5: {"res_model": "account.payment.register", "view_id": False},
            6: {"res_model": "x.wiz", "view_id": False},
        },
    }
    p = FakePort(
        {
            ("res.partner", None): form('<button name="5" type="action" string="Settle"/>'),
            ("account.payment.register", None): form(
                '<button name="action_create_payments" type="object" string="OK"/>',
                '<button special="cancel" string="Discard"/>',
            ),
            ("x.wiz", None): form('<button name="go" type="object" string="Go"/>'),
        },
        recs,
        transient={"account.payment.register", "x.wiz"},
    )
    assert bt.resolve_button(p, "res.partner", label="Settle").cls == "R4"
    assert isinstance(bt.classify_action(p, 6), bt.Unresolved)


def test_ac2_mislabelled_catalogue_button_refused() -> None:
    p = FakePort(
        {
            ("account.move", None): form(
                '<button name="action_zz_harmless" type="object" string="Post"/>'
            )
        }
    )
    r = cl.classify("b:account.move:action_post", ctx(port=p, label="Post"))
    assert isinstance(r, ru.Refusal) and "not action_post" in r.reason


def test_onchange_or_write_automation_raises_class() -> None:
    recs = {
        "base.automation": {
            1: {"trigger": "on_change", "action_server_ids": [7]},
            2: {"trigger": "on_time", "action_server_ids": [8]},
        },
        "ir.actions.server": {
            7: _sa("code", "res.partner", "records.message_post()"),
            8: _sa("code", "res.partner", "nope()"),
        },
    }
    p = FakePort({}, recs)
    d = ok("m:res.partner:change", port=p)
    assert d.cls == "R5" and any("automation" in e for e in d.evidence)
    recs["base.automation"][2]["trigger"] = "on_write"
    assert isinstance(cl.classify("m:res.partner:change", ctx(port=p)), ru.Refusal)


# ---------------------------------------------------------------- AC3 mapping


def _first(prefix: str, pred: Any = lambda i: True) -> str:
    return next(i for i in sorted(cl.catalogue()[0]) if i.startswith(prefix) and pred(i))


@pytest.mark.parametrize(
    "task,cls",
    [
        (_first("seq:"), "R8C"),
        ("param:auth_signup.reset_password", "R8"),
        (_first("param:", lambda i: "web.base.url" in i or "database" in i or "auth" in i), "R8"),
        ("cron:Digest Emails", "R5"),
        ("cron:Event: Mail Scheduler", "R5"),
        ("s:module_account", "R7"),
        ("m:res.partner:delete", "R6"),
        ("mod:crm:uninstall", "R9"),
    ],
)
def test_ac3_mapping_overrides(task: str, cls: str) -> None:
    assert ok(task).cls == cls
    assert cl.mapped_class("cron:Attendance: Process daily time rules", "R7") == ("R7", None)
    assert cl.mapped_class("cron:Generate recurring", "R7") == ("R7", None)


# ---------------------------------------------------------------- AC4 policy


def full(d: cl.Decision, **kw: Any) -> ru.GateCtx:
    proven = frozenset(c for c in d.controls if c not in ru.POST_CONTROLS | ru.POLICY_CONTROLS)
    base = dict(
        route=d.route,
        version=d.version,
        connection_id="c1",
        db_name="ingenium_nf_x",
        kill_switch=False,
        fingerprint_ok=True,
        proven=proven,
        approval=3,
        typed_confirmation="7",
        blast_count=7,
        stated_limit_ack=True,
        batch_size=7,
        run_size=7,
        rate_per_min=1,
        clone_age_h=1.0,
        period_locked=False,
        transactions_exist=False,
        archive_possible=False,
        has_dependents=False,
        admins_after=2,
        removes_bot_access=False,
        idempotency_key="k",
    )
    base.update(kw)
    return ru.GateCtx(**base)


def test_ac4_caps() -> None:
    d = ok("m:res.partner.category:mass-write")
    assert isinstance(check(d, full(d)), ru.Allowed)
    r = check(d, full(d, batch_size=51))
    assert r.missing == "size-cap" and "51 > 50" in r.reason
    r = check(d, full(d, run_size=501, approval=2))
    assert r.missing == "size-cap" and "without L3" in r.reason
    assert isinstance(check(d, full(d, run_size=501)), ru.Allowed)
    assert check(d, full(d, run_size=501, typed_confirmation=None)).missing == "typed-confirmation"


def test_ac4_tiers_and_override() -> None:
    assert [
        ok(t).tier
        for t in (
            "m:res.partner.category:change",
            "m:res.partner.category:mass-write",
            "mod:crm:uninstall",
        )
    ] == [1, 2, 3]
    p = ru.apply_override(ru.DEFAULT_POLICY, {"batch_cap": 20, "tiers": {"R1": 2}}, approval=1)
    assert isinstance(p, ru.Policy) and p.batch_cap == 20
    d = ok("m:res.partner.category:mass-write")
    assert check(d, full(d, batch_size=21, policy=p)).missing == "size-cap"
    for loose in ({"batch_cap": 100}, {"run_cap": 1000}, {"tiers": {"R3": 1}}):
        r = ru.apply_override(ru.DEFAULT_POLICY, loose, approval=2)
        assert isinstance(r, ru.Refusal) and r.missing == "human-approve-L3", loose
        assert isinstance(ru.apply_override(ru.DEFAULT_POLICY, loose, approval=3), ru.Policy)
    lo = ru.apply_override(ru.DEFAULT_POLICY, {"tiers": {"R6": 1, "R4": 1}}, approval=3)
    assert ok("m:res.partner:delete", policy=lo).tier == 3  # RF floor never lowered
    assert ok("b:account.move:action_post", route="A", policy=lo).tier == 3
    assert ok("b:account.move:action_post", route="B", policy=lo).tier == 1
    assert isinstance(ru.apply_override(ru.DEFAULT_POLICY, {"batch_cap": 0}, 3), ru.Refusal)
    assert isinstance(ru.apply_override(ru.DEFAULT_POLICY, {"nope": 1}, 3), ru.Refusal)


# ---------------------------------------------------------------- AC5 control x class

REPRESENTATIVE = {
    "R3": "m:res.partner.category:mass-write",
    "R4": "b:account.move:action_post",
    "R5": "cron:Digest Emails",
    "R6": "m:res.partner:delete",
    "R8": "param:auth_signup.reset_password",
    "R8C": None,
    "R9": "mod:crm:uninstall",
}
REPRESENTATIVE["R8C"] = _first("seq:")
_FACT = {
    "kill-switch": {"kill_switch": None},
    "size-cap": {"batch_size": None},
    "rate-cap": {"rate_per_min": None},
    "period-lock-check": {"period_locked": None},
    "transaction-existence-check": {"transactions_exist": None},
    "prefer-archive": {"archive_possible": None},
    "idempotency-key": {"idempotency_key": None},
    "typed-confirmation": {"typed_confirmation": None},
    "stated-limit": {"stated_limit_ack": False},
}


def _cases() -> list[tuple[str, str, str]]:
    out = []
    for cls, task in REPRESENTATIVE.items():
        for route in ("A", "B"):
            d = ok(task, route=route)
            assert d.cls == cls
            out += [(task, route, c) for c in d.controls if c not in ru.POST_CONTROLS | {"audit"}]
    return out


CASES = _cases()


def test_ac5_every_irrecoverable_class_has_rule_and_cases() -> None:
    assert {cls for cls, t in REPRESENTATIVE.items() if t} == set(ru.IRRECOVERABLE)
    print(f"AC5 control x class x route negative cases: {len(CASES)}")
    assert len(CASES) >= 70


@pytest.mark.parametrize("task,route,control", CASES)
def test_ac5_missing_control_named(
    task: str, route: str, control: str, store: MemAuditStore
) -> None:
    d = ok(task, route=route)
    assert isinstance(check(d, full(d)), ru.Allowed)  # complete ctx passes
    if control in _FACT:
        g = full(d, **_FACT[control])
    else:
        drop = {control} | ({"batch1-undo-proof"} if control == "copy-rehearsal" else set())
        g = full(d, proven=full(d).proven - drop)
    r = check(d, g)
    assert isinstance(r, ru.Refusal) and r.missing == control, (r, control)
    assert r.rule in (f"RF-{d.cls}", "RF-ANY")
    assert store.rows[-1]["reason"].startswith(r.rule) and control in store.rows[-1]["reason"]


def test_rf_any_and_class_facts() -> None:
    d = ok("m:res.partner.category:mass-write")
    assert check(d, full(d, kill_switch=True)).reason == "kill switch is on"
    assert check(d, full(d, fingerprint_ok=False)).missing == "fingerprint"
    assert check(d, full(d, version=19)).missing == "fingerprint"
    p = ok("b:account.move:action_post")
    assert "locked period" in check(p, full(p, period_locked=True)).reason
    assert check(p, full(p, clone_age_h=25)).missing == "clone-rehearsal"
    m = ok("cron:Digest Emails")
    assert "11/min" in check(m, full(m, rate_per_min=11)).reason
    dl = ok("m:res.partner:delete")
    assert "archive is possible" in check(dl, full(dl, archive_possible=True)).reason
    s = ok("param:auth_signup.reset_password")
    assert "no working admin" in check(s, full(s, admins_after=0)).reason
    assert "Bot's own" in check(s, full(s, removes_bot_access=True)).reason


# ---------------------------------------------------------------- AC6 versions


@pytest.mark.parametrize("v", [16, 21])
def test_ac6_version_outside_refused(v: int) -> None:
    r = cl.classify("m:res.partner:change", ctx(v=v))
    assert isinstance(r, ru.Refusal) and r.missing == "version"


def test_ac6_v20_security_and_transport() -> None:
    d20 = ok("param:auth_signup.reset_password", v=20)
    assert d20.security_models == ("ir.access",) and d20.rpc == ("json2",)
    d17 = ok("param:auth_signup.reset_password", v=17)
    assert d17.security_models == ("ir.model.access", "ir.rule")
    for v in (17, 18, 19, 20):
        assert "xmlrpc" not in ok("m:res.partner.category:change", v=v).rpc
    only17 = _first("m:", lambda i: cl.catalogue()[0][i][1] == frozenset({17}))
    r = cl.classify(only17, ctx(v=20))
    assert isinstance(r, ru.Refusal) and "Odoo 20" in r.reason


def test_ac6_v20_fixture_stock_return_route() -> None:
    off = ok("b:stock.picking:button_validate", v=20)
    assert "not verified" in off.mitigation_refusal
    assert check(off, full(off)).missing == "counter-document"
    p20 = FakePort(
        {
            ("stock.picking", None): form(
                '<button name="button_validate" type="object" string="Validate"/>',
                '<button name="action_return" type="object" string="Return"/>',
            )
        }
    )
    on = ok("b:stock.picking:button_validate", v=20, port=p20)
    assert on.mitigation["counter"] == "stock.picking.action_return" and not on.mitigation_refusal
    assert (
        ok("b:stock.picking:button_validate", v=19).mitigation["counter"] == "stock.return.picking"
    )


# ---------------------------------------------------------------- AC7 audit


def test_ac7_refusals_audited_and_fail_closed(store: MemAuditStore) -> None:
    cl.classify("nope:x", ctx())
    d = ok("m:res.partner.category:mass-write")
    check(d, full(d, batch_size=99))
    rows = [r for r in store.rows if r["connection_id"] == "c1"]
    assert [r["decision"] for r in rows] == ["refused", "refused"]
    assert rows[0]["reason"].startswith("RF-ANY") and rows[1]["reason"].startswith("RF-R3")
    tg.configure_audit_store(BrokenStore())
    with pytest.raises(cl.RiskAuditUnavailable):
        cl.classify("nope:x", ctx())
    tg.configure_audit_store(None)
    with pytest.raises(cl.RiskAuditUnavailable):
        check(d, full(d, batch_size=99))


# ---------------------------------------------------------------- AC8 routes

ROUTE_CLASSES = list(REPRESENTATIVE.items()) + [
    ("R2W", "b:crm.lead:action_set_won")
    if "b:crm.lead:action_set_won" in cl.catalogue()[0]
    else ("R2W", _first("m:", lambda i: i.endswith(":archive"))),
    ("R7", "mod:crm:install"),
]


@pytest.mark.parametrize("cls,task", ROUTE_CLASSES)
def test_ac8_route_controls(cls: str, task: str) -> None:
    a, b = ok(task, route="A"), ok(task, route="B")
    assert "copy-rehearsal" not in b.controls
    if "snapshot-proof" in cl.catalogue()[1][a.cls]:
        assert "snapshot-proof" in b.controls and "snapshot-proof" not in a.controls
    if ru.a_kind(a.cls, a.subkind) == "rev":
        assert {"before-image", "batch1-undo-proof"} <= set(a.controls)
    else:
        assert {"typed-confirmation", "stated-limit"} <= set(a.controls) and a.tier == 3
    # hosted / RPC-only is never a refusal reason by itself
    if not a.mitigation_refusal:
        assert isinstance(check(a, full(a)), ru.Allowed)


def test_ac8_reversible_on_a_accepts_batch1_undo_without_copy() -> None:
    d = ok("m:res.partner.category:mass-write", route="A")
    assert not d.strict_copy
    pr = full(d).proven - {"copy-rehearsal"}
    assert isinstance(check(d, full(d, proven=pr | {"full-image-proof"})), ru.Allowed)
    # batch-1 proof without a full-image proof (side effects / unrestorable): rehearsal stays
    assert check(d, full(d, proven=pr)).missing == "copy-rehearsal"
    s = ok("param:auth_signup.reset_password", route="A")
    assert s.strict_copy and "bot-apikey-kept" in s.controls
    assert check(s, full(s, proven=full(s).proven - {"copy-rehearsal"})).missing == "copy-rehearsal"


def test_name_only_proofs_refused() -> None:
    d = ok("m:res.partner.category:mass-write", route="A")
    b = ok("m:res.partner.category:mass-write", route="B")
    for x in (d, b):
        g = full(x)
        assert g.proven & ru.PROOF_CONTROLS
        r = cl.check(x, g)  # names only, no verifier
        assert isinstance(r, ru.Refusal) and r.missing in ru.PROOF_CONTROLS
        assert isinstance(cl.check(x, g, lambda c, g=g: c in g.proven), ru.Allowed)


def test_ac8_mitigations() -> None:
    assert (
        "account.move.reversal" in ok("b:account.move:action_post", route="A").mitigation["counter"]
    )
    r5 = ok("cron:Digest Emails", route="A")
    assert "mail_server" in r5.mitigation["hold"].replace(".", "_")
    assert {"outbox-hold", "mail-server-inactive-on-copy"} <= set(r5.controls)
    assert "action_archive" in ok("m:res.partner:delete", route="A").mitigation["prefer"]
    assert "apikeys" in ok("param:auth_signup.reset_password", route="A").mitigation["keep"]
    u = ok("mod:crm:uninstall", route="A")
    assert "base.module.uninstall" in u.mitigation["preview"] and "uninstall-preview" in u.controls
    dl = ok("m:res.partner:delete", route="A")
    assert "dependents" in check(dl, full(dl, has_dependents=None)).reason
    sq = ok(_first("seq:"), route="A")
    r = check(sq, full(sq, transactions_exist=True))
    assert r.missing == "data-impact-report"
    assert isinstance(
        check(sq, full(sq, transactions_exist=True, data_impact_report=True)), ru.Allowed
    )


def test_r4_reset_draft_and_failsafe_refused() -> None:
    assert bt.method_effect("account.move", "button_draft").subkind == "reset-draft"
    d = replace(ok("b:account.move:action_post"), subkind="reset-draft")
    assert "never reset" in check(d, full(d)).reason
    assert isinstance(check(d, full(d, is_prod=False)), ru.Allowed)
    fs = cl.mitigation("R4", "fail-safe", 17, None)
    assert fs[1].startswith("no documented counter-document")


# ---------------------------------------------------------------- live 17 / 19 / 20

LIVE = os.environ.get("ODOO_LIVE") == "1" and os.environ.get("INGENIUM_LIVE_INFRA") == "1"
if LIVE:
    from test_nf_bot_verify_live import VERSIONS, _port, bv  # noqa: F401
else:
    VERSIONS = ()

LIVE_TABLE: list[str] = []


def _install(port: Any, mods: list[str]) -> None:
    ids = port.admin(
        "ir.module.module", "search", ([("name", "in", mods), ("state", "!=", "installed")],)
    )
    if ids:
        port.admin("ir.module.module", "button_immediate_install", (ids,))


def _inherit(port: Any, model: str, arch: str, name: str) -> int:
    base = port.admin(
        "ir.ui.view",
        "search",
        ([("model", "=", model), ("type", "=", "form"), ("mode", "=", "primary")],),
        {"limit": 1, "order": "priority,id"},
    )[0]
    return port.admin(
        "ir.ui.view", "create", ({"name": name, "model": model, "inherit_id": base, "arch": arch},)
    )


class _P:
    def __init__(self, port: Any) -> None:
        self.port = port

    def call(self, model: str, method: str, args: Any = (), kwargs: dict | None = None) -> Any:
        return self.port.admin(model, method, args, kwargs or {})


@pytest.mark.odoo_live
@pytest.mark.skipif(not LIVE, reason="live: set ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1")
@pytest.mark.parametrize("v", VERSIONS)
def test_live_per_button_resolution(bv: Any, v: int) -> None:
    port = _port(bv, v)
    _install(port, ["account", "stock"])
    p = _P(port)
    row = lambda k, e: LIVE_TABLE.append(f"v{v} {k} -> {getattr(e, 'cls', e)}")  # noqa: E731
    e = bt.resolve_button(p, "account.move", name="action_post")
    assert e.cls == "R4", e
    row("account.move.action_post", e)
    e = bt.resolve_button(p, "stock.picking", name="button_validate")
    assert e.cls == "R4", e
    row("stock.picking.button_validate", e)
    # mislabelled: an inherited view relabels Post as "Process" -> still R4 (last arch wins)
    _inherit(
        port,
        "account.move",
        "<xpath expr=\"//button[@name='action_post']\" "
        'position="attributes"><attribute name="string">Process</attribute></xpath>',
        "nf p",
    )
    e = bt.resolve_button(p, "account.move", label="Process")
    assert e.cls == "R4", e
    row("label 'Process' (action_post)", e)
    # a harmless method labelled "Post", and a server-action button posting moves
    sa = port.admin(
        "ir.actions.server",
        "create",
        (
            {
                "name": "nf post",
                "model_id": port.admin("ir.model", "search", ([("model", "=", "res.partner")],))[0],
                "state": "code",
                "code": "env['account.move'].action_post()",
            },
        ),
    )
    _inherit(
        port,
        "res.partner",
        '<xpath expr="//sheet" position="before"><header>'
        '<button name="open_commercial_entity" type="object" string="Post"/>'
        f'<button name="{sa}" type="action" string="Tidy up"/></header></xpath>',
        "nf q",
    )
    e = bt.resolve_button(p, "res.partner", label="Post")
    assert e.cls == "R0", e
    row("label 'Post' (open_commercial_entity)", e)
    e = bt.resolve_button(p, "res.partner", label="Tidy up")
    assert e.cls == "R4", e
    row("server-action button -> action_post", e)
    # wizard-wrapped posting via act_window on account.payment.register
    aw = port.admin(
        "ir.actions.act_window",
        "create",
        ({"name": "nf pay", "res_model": "account.payment.register", "view_mode": "form"},),
    )
    e = bt.classify_action(p, aw)
    assert e.cls == "R4", e
    row("act_window account.payment.register", e)
    # write-triggered automation sends mail -> partner change becomes R5
    _automation(port, v)
    d = cl.classify("m:res.partner:change", ctx(v=v, port=p))
    assert isinstance(d, cl.Decision) and d.cls == "R5", d
    row("m:res.partner:change with on-write mail automation", d)
    if v == 20:
        d = cl.classify("b:stock.picking:button_validate", ctx(v=20, port=p))
        row("v20 return route", d.mitigation or d.mitigation_refusal)
    print("\n".join(LIVE_TABLE))


def _automation(port: Any, v: int) -> None:
    mid = port.admin("ir.model", "search", ([("model", "=", "res.partner")],))[0]
    aid = port.admin(
        "base.automation",
        "create",
        ({"name": "nf mail on write", "model_id": mid, "trigger": "on_create_or_write"},),
    )
    port.admin(
        "ir.actions.server",
        "create",
        (
            {
                "name": "nf mail",
                "model_id": mid,
                "state": "code",
                "base_automation_id": aid,
                "code": "records.message_post(body='hi')",
            },
        ),
    )


def _nil(port: Any, model: str, method: str, ids: list[int], ctx: dict | None = None) -> None:
    """Call a method that returns None (XML-RPC cannot marshal it; the call still commits)."""
    try:
        port.admin(model, method, (ids,), {"context": ctx} if ctx else {})
    except Exception as e:  # noqa: BLE001
        assert "marshal None" in str(e), e


@pytest.mark.odoo_live
@pytest.mark.skipif(not LIVE, reason="live: set ODOO_LIVE=1 and INGENIUM_LIVE_INFRA=1")
@pytest.mark.parametrize("v", [x for x in VERSIONS if x in (17, 20)])
def test_live_return_flow(bv: Any, v: int) -> None:
    """Full return on the sandbox DB: 17 stock.return.picking.create_returns;
    20 stock.picking.action_return -> action_return_all -> button_validate."""
    port = _port(bv, v)
    a = port.admin
    _install(port, ["stock"])
    pf = a("product.product", "fields_get", (), {"attributes": ["type"]})
    vals: dict = {"name": f"nf return {v}", "type": "consu" if "is_storable" in pf else "product"}
    if "is_storable" in pf:
        vals["is_storable"] = True
    prod = a("product.product", "create", (vals,))
    wh = a(
        "stock.warehouse",
        "search_read",
        ([],),
        {"fields": ["out_type_id", "lot_stock_id"], "limit": 1},
    )[0]
    loc = wh["lot_stock_id"][0]
    a(
        "stock.quant",
        "create",
        ({"product_id": prod, "location_id": loc, "inventory_quantity": 10},),
    )
    q = a("stock.quant", "search", ([("product_id", "=", prod), ("location_id", "=", loc)],))
    _nil(port, "stock.quant", "action_apply_inventory", q)
    cust = a("ir.model.data", "check_object_reference", ("stock", "stock_location_customers"))[1]
    mv = {"product_id": prod, "product_uom_qty": 3, "location_id": loc, "location_dest_id": cust}
    if v < 18:
        mv["name"] = "nf"
    pk = a(
        "stock.picking",
        "create",
        (
            {
                "picking_type_id": wh["out_type_id"][0],
                "location_id": loc,
                "location_dest_id": cust,
                "move_ids": [(0, 0, mv)],
            },
        ),
    )
    _nil(port, "stock.picking", "action_confirm", [pk])
    _nil(port, "stock.picking", "action_assign", [pk])
    if v < 18:
        a(
            "stock.move",
            "write",
            (a("stock.move", "search", ([("picking_id", "=", pk)],)), {"quantity": 3}),
        )
    r = a("stock.picking", "button_validate", ([pk],))
    if isinstance(r, dict) and r.get("res_model"):  # immediate-transfer / backorder wizard
        ctx = r.get("context") or {}
        wid = a(r["res_model"], "create", ({},), {"context": ctx})
        a(r["res_model"], "process", ([wid],), {"context": ctx})
    assert a("stock.picking", "read", ([pk],), {"fields": ["state"]})[0]["state"] == "done"
    if v == 17:
        ctx = {"active_id": pk, "active_ids": [pk], "active_model": "stock.picking"}
        wid = a("stock.return.picking", "create", ({"picking_id": pk},), {"context": ctx})
        assert a("stock.return.picking.line", "search_count", ([("wizard_id", "=", wid)],)) == 1
        r = a("stock.return.picking", "create_returns", ([wid],), {"context": ctx})
        rid = r["res_id"]
        assert bt.method_effect("stock.return.picking", "create_returns").cls == "R2W"
    else:
        r = a("stock.picking", "action_return", ([pk],))
        rid = r["res_id"]
        assert a("stock.picking", "read", ([rid],), {"fields": ["state"]})[0]["state"] == "draft"
        _nil(port, "stock.picking", "action_return_all", [rid])
        p = _P(port)
        assert bt.resolve_button(p, "stock.picking", name="action_return").cls == "R2W"
        assert bt.resolve_button(p, "stock.picking", name="action_return_all").cls == "R4"
    moves = a(
        "stock.move",
        "search_read",
        ([("picking_id", "=", rid)],),
        {"fields": ["product_uom_qty", "quantity"]},
    )
    assert [m["product_uom_qty"] for m in moves] == [3.0], moves
    ret = a("stock.picking", "read", ([rid],), {"fields": ["location_dest_id"]})[0]
    assert ret["location_dest_id"][0] == loc
    if v < 18:
        a("stock.move", "write", ([m["id"] for m in moves], {"quantity": 3}))
    r = a("stock.picking", "button_validate", ([rid],))
    assert a("stock.picking", "read", ([rid],), {"fields": ["state"]})[0]["state"] == "done", r
    LIVE_TABLE.append(f"v{v} return flow -> return picking {rid} qty 3 done")


def test_outside_plan_changes_need_l2_review() -> None:
    import dataclasses

    d = ok("m:res.partner.category:mass-write", route="A")
    g = full(d, proven=full(d).proven | {"full-image-proof"})
    side = frozenset({"street"})
    low = dataclasses.replace(g, approval=1, outside_plan_fields=side)
    assert check(d, low).missing == "outside-plan-review"
    hi = dataclasses.replace(g, approval=max(2, g.approval), outside_plan_fields=side)
    assert getattr(check(d, hi), "missing", "") != "outside-plan-review"
