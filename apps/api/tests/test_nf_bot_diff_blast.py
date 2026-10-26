"""BOT-DIFF-BLAST: diff preview, cascade blast, caps/tiers, stale approval, readback trip."""

from __future__ import annotations

import ast
import copy
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.bots import blast as bl
from app.bots import diff as df
from app.bots import guard as gd
from app.bots.audit import REDACTED
from app.bots.risk import rules
from tests.test_nf_bot_kill_audit import (  # noqa: F401
    ANCHOR,
    OWNER,
    REH,
    Undo,
    _clean,
    engine,
    env,
    fake_owner,
)

pytestmark = pytest.mark.no_app_db
BOTS = Path(__file__).resolve().parents[1] / "app" / "bots"


class Odoo:
    """Tiny in-memory Odoo: fields_get/read/search/search_count/search_read + ir.model.fields."""

    def __init__(self) -> None:
        self.meta: dict[str, dict[str, dict]] = {
            "res.partner": {
                "name": {"type": "char"},
                "email": {"type": "char"},
                "api_key": {"type": "char"},
                "parent_id": {"type": "many2one", "relation": "res.partner"},
                "company_id": {"type": "many2one", "relation": "res.company"},
                "category_id": {
                    "type": "many2many",
                    "relation": "res.partner.category",
                    "store": True,
                },
                "credit": {"type": "monetary"},
                "display_name": {"type": "char", "readonly": True, "store": False},
                "image_1920": {"type": "binary"},
                "x_pin": {"type": "char"},
            },
            "res.users": {"partner_id": {"type": "many2one", "relation": "res.partner"}},
            "crm.lead": {"partner_id": {"type": "many2one", "relation": "res.partner"}},
            "account.move": {"partner_id": {"type": "many2one", "relation": "res.partner"}},
            "res.partner.bank": {"partner_id": {"type": "many2one", "relation": "res.partner"}},
            "res.company": {},
        }
        self.rows: dict[str, dict[int, dict]] = {
            "res.partner": {
                1: {
                    "name": "Acme",
                    "email": "a@x",
                    "api_key": "k",
                    "parent_id": False,
                    "company_id": [1, "C1"],
                    "category_id": [3],
                    "credit": 1.0,
                },
                2: {
                    "name": "Bob",
                    "email": "b@x",
                    "api_key": "k",
                    "parent_id": [1, "Acme"],
                    "company_id": [2, "C2"],
                    "category_id": [],
                    "credit": 2.0,
                },
            },
            "res.users": {7: {"partner_id": [2, "Bob"]}},
            "crm.lead": {},
            "account.move": {},
            "res.partner.bank": {},
            "res.company": {1: {}, 2: {}},
        }
        self.imf = [
            dict(model="res.partner", name="parent_id", ttype="many2one", on_delete="cascade"),
            dict(model="res.users", name="partner_id", ttype="many2one", on_delete="restrict"),
            dict(model="crm.lead", name="partner_id", ttype="many2one", on_delete="set null"),
            dict(
                model="res.partner.bank", name="partner_id", ttype="many2one", on_delete="cascade"
            ),
            dict(model="res.partner", name="category_id", ttype="many2many", on_delete=False),
        ]
        self.calls: list[tuple] = []
        self.deny: set[str] = set()
        self.n_rules = 0

    def _match(self, model: str, dom: list) -> list[int]:
        out = []
        for rid, r in self.rows[model].items():
            ok = True
            for f, op, v in dom:
                val = df.norm_read(self.meta[model][f]["type"], r.get(f))
                vals = val if isinstance(val, list) else [val]
                ok &= op == "in" and any(x in v for x in vals)
            if ok:
                out.append(rid)
        return out

    def __call__(self, model, method, args, kw=None):
        self.calls.append((model, method))
        if model in self.deny:
            raise PermissionError("AccessError")
        kw = kw or {}
        if model == "ir.rule":
            return self.n_rules
        if model == "ir.model.fields":
            dom = dict((f, v) for f, _o, v in args[0])
            if "depends" in dom:
                return []
            return [
                dict(r)
                for r in self.imf
                if r["ttype"] in dom["ttype"]
                and self.meta[r["model"]][r["name"]]["relation"] == dom["relation"]
            ]
        if method == "fields_get":
            return {f: m for f, m in self.meta[model].items() if not args[0] or f in args[0]}
        if method == "read":
            return [
                {"id": i, **{f: copy.deepcopy(self.rows[model][i].get(f)) for f in args[1]}}
                for i in args[0]
                if i in self.rows[model]
            ]
        if method == "search":
            return self._match(model, args[0])
        if method == "search_count":
            return len(self._match(model, args[0]))
        if method == "write":  # test-side only (WriteGate rpc)
            for i in args[0]:
                self.rows[model][i].update(args[1])
            return True
        raise AssertionError(method)


def pv(o, model="res.partner", ids=(1,), values=None, op="write", cls="R1", sub=None, **kw):
    return bl.preview(o, model, list(ids), values, op=op, cls=cls, subkind=sub, route="A", **kw)


# ---------------------------------------------------------------- AC1 diff
def test_ac1_diff_per_record_field_old_new() -> None:
    d = df.build_diff(Odoo(), "res.partner", [1, 2], {"name": "Acme", "email": "new@x"})
    got = [e.as_dict() for e in d.entries]
    assert got == [
        {"model": "res.partner", "id": 1, "field": "email", "old": "a@x", "new": "new@x"},
        {"model": "res.partner", "id": 2, "field": "email", "old": "b@x", "new": "new@x"},
        {"model": "res.partner", "id": 2, "field": "name", "old": "Bob", "new": "Acme"},
    ]


def test_ac1_secrets_masked_both_sides() -> None:
    d = df.build_diff(Odoo(), "res.partner", [1], {"api_key": "sk_live_abcdefghijklmnop"})
    (e,) = d.entries
    assert (e.old, e.new, e.masked) == (REDACTED, REDACTED, True)
    assert "sk_live" not in str(pv(Odoo(), values={"api_key": "sk_live_abcdefghijklmnop"}))


def test_ac1_m2o_and_m2m_normalised_and_unchanged_listed() -> None:
    d = df.build_diff(
        Odoo(), "res.partner", [1, 2], {"company_id": 1, "category_id": [(6, 0, [3])]}
    )
    assert [(e.id, e.field, e.old, e.new) for e in d.entries] == [
        (2, "category_id", [], [3]),
        (2, "company_id", 2, 1),
    ]
    assert d.unchanged == (1,)


@pytest.mark.parametrize(
    ("ids", "values", "missing"),
    [
        ([], {"name": "x"}, "diff-ids"),
        ([True], {"name": "x"}, "diff-ids"),
        ([1, 99], {"name": "x"}, "diff-ids"),
        ([1], {}, "diff-shape"),
        ([1], {"nope": 1}, "diff-field"),
        ([1], {"write_uid": 1}, "diff-field"),
        ([1], {"display_name": "x"}, "diff-field"),
        ([1], {"category_id": [(4, 3, 0)]}, "diff-shape"),
        ([1], {"category_id": [(6, 0, [3]), (5, 0, 0)]}, "diff-shape"),
        ([1], {"parent_id": [1, "x"]}, "diff-shape"),
        ([1], {"parent_id": True}, "diff-shape"),
        ([1], {"name": {"en_US": "x"}}, "diff-shape"),
    ],
)
def test_ac1_adversarial_shapes_refuse(ids, values, missing) -> None:
    with pytest.raises(df.DiffRefused) as ei:
        df.build_diff(Odoo(), "res.partner", ids, values)
    assert ei.value.refusal.missing == missing


def test_ac1_access_error_refuses() -> None:
    o = Odoo()
    o.deny.add("res.partner")
    with pytest.raises(df.DiffRefused) as ei:
        df.build_diff(o, "res.partner", [1], {"name": "x"})
    assert ei.value.refusal.missing == "diff-read"


@pytest.mark.parametrize("method", ["write", "create", "unlink", "action_post", "copy"])
def test_readonly_wrapper_refuses_every_non_read(method) -> None:
    with pytest.raises(PermissionError):
        df.ReadOnly(Odoo())("res.partner", method, [[1]])


def test_preview_modules_make_no_raw_writes() -> None:
    for name in ("diff.py", "blast.py"):
        tree = ast.parse((BOTS / name).read_text())
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not attrs & {"write", "create", "unlink", "execute_kw"}, name
    assert df.READ_METHODS == {"read", "search", "search_read", "search_count", "fields_get"}


# ---------------------------------------------------------------- AC2 blast
def test_ac2_unlink_walks_cascade_set_null_m2m_and_owners() -> None:
    o = Odoo()
    o.rows["res.users"] = {}
    o.rows["crm.lead"] = {5: {"partner_id": [2, "Bob"]}}
    o.rows["res.partner.bank"] = {9: {"partner_id": [2, "Bob"]}}
    b = bl.build_blast(o, "res.partner", [1], "unlink")
    p = b.payload()
    assert p["ids"] == {"res.partner": [1, 2], "res.partner.bank": [9]}  # 1 -> child 2 -> bank 9
    assert p["nulled"] == {"crm.lead.partner_id": 1}
    assert p["links"] == {"res.partner.category_id": 1}
    assert p["companies"] == [1, 2] and p["total"] == 4
    assert any("mail.thread" in r or "reviewed" in r for r in p["low_count"])


def test_ac2_restrict_gives_refusal_preview() -> None:
    r = pv(Odoo(), op="unlink", cls="R6", sub="delete")
    assert isinstance(r, rules.Refusal)
    assert (r.rule, r.missing) == ("RF-R6", "cascade-graph-count")
    assert "res.users.partner_id" in r.reason


def test_ac2_write_counts_users_of_partners() -> None:
    b = bl.build_blast(Odoo(), "res.partner", [1, 2], "write")
    assert (b.total, sorted(b.users), sorted(b.companies)) == (2, [7], [1, 2])


def test_ac2_self_cycle_terminates() -> None:
    o = Odoo()
    o.rows["res.users"] = {}
    o.rows["res.partner"][1]["parent_id"] = [2, "Bob"]  # 1 <-> 2
    b = bl.build_blast(o, "res.partner", [1], "unlink")
    assert b.payload()["per_model"] == {"res.partner": 2}


# ---------------------------------------------------------------- AC3 uncountable
def test_ac3_access_error_in_graph_is_rf_r6() -> None:
    o = Odoo()
    o.deny.add("crm.lead")
    r = bl.build_blast(o, "res.partner", [1], "unlink")
    assert isinstance(r, rules.Refusal) and (r.rule, r.missing) == ("RF-R6", "cascade-graph-count")


def test_ac3_unknown_on_delete_and_caps(monkeypatch) -> None:
    o = Odoo()
    o.imf[2]["on_delete"] = "no action"
    o.rows["res.users"] = {}
    assert not isinstance(bl.build_blast(o, "res.partner", [1], "unlink"), rules.Refusal)
    o.rows["crm.lead"] = {5: {"partner_id": [1, "Acme"]}}  # now referenced
    r = bl.build_blast(o, "res.partner", [1], "unlink")
    assert isinstance(r, rules.Refusal) and "unknown" in r.reason
    o = Odoo()
    o.rows["res.users"] = {}
    monkeypatch.setattr(bl, "MAX_NODES", 1)
    assert "over 1" in bl.build_blast(o, "res.partner", [1], "unlink").reason
    monkeypatch.setattr(bl, "MAX_NODES", 20000)
    monkeypatch.setattr(bl, "MAX_DEPTH", 1)
    assert "deeper" in bl.build_blast(o, "res.partner", [1], "unlink").reason


def test_ac3_bad_op_and_unlink_values_refuse() -> None:
    assert isinstance(bl.build_blast(Odoo(), "res.partner", [1], "merge"), rules.Refusal)
    assert isinstance(pv(Odoo(), op="unlink", values={"name": "x"}), rules.Refusal)


# ---------------------------------------------------------------- AC4 caps + tiers
@pytest.mark.parametrize(
    ("cls", "n", "tier", "batches"),
    [
        ("R1", 1, 1, 1),
        ("R1", 50, 1, 1),
        ("R1", 51, 1, 2),
        ("R3", 10, 2, 1),
        ("R1", 500, 1, 10),
        ("R1", 501, 3, 11),
        ("R6", 1, 3, 1),
    ],
)
def test_ac4_tier_and_batches(cls, n, tier, batches) -> None:
    t = rules.plan_tier(cls, None, "A", rules.DEFAULT_POLICY, n)
    assert (t.tier, t.batches, t.controls) == (tier, batches, rules.TIER_CONTROLS[tier])
    assert t.reasons and all(t.reasons)


def test_ac4_low_count_forces_l3_with_reason() -> None:
    t = rules.plan_tier("R1", None, "A", rules.DEFAULT_POLICY, 1, ["custom unlink"])
    assert t.tier == 3 and any("count may be low" in r for r in t.reasons)


@pytest.mark.parametrize("n", [0, -1, True, 1.5, None])
def test_ac4_bad_counts_refuse(n) -> None:
    assert isinstance(rules.plan_tier("R1", None, "A", rules.DEFAULT_POLICY, n), rules.Refusal)
    assert isinstance(rules.plan_tier("RX", None, "A", rules.DEFAULT_POLICY, 1), rules.Refusal)


def test_ac4_tier_controls_cover_card() -> None:
    assert rules.TIER_CONTROLS[1] == ("quick-tap",)
    assert {"diff-preview", "blast-count"} <= set(rules.TIER_CONTROLS[2])
    assert {"clone-rehearsal", "snapshot", "typed-blast-count"} <= set(rules.TIER_CONTROLS[3])


def test_ac4_tier_never_below_gate_tier() -> None:
    """Drift: plan_tier agrees with the gate's required_tier for every class (derived)."""
    for cls in rules.CLASSES:
        for sub in (None, "delete"):
            t = rules.plan_tier(cls, sub, "A", rules.DEFAULT_POLICY, 1)
            assert t.tier == rules.required_tier(cls, sub, "A", rules.DEFAULT_POLICY)


def Snap(sid="snap:abc", fp="fp1", ok=True):  # noqa: N802 - real snapshot.Verified instances
    from app.bots import snapshot as sn

    v = sn.Verified.__new__(sn.Verified)
    v.snap = type("S", (), {"id": sid, "fingerprint": fp})()
    v.refusal = None if ok is True else rules.Refusal("RF-R3", "snapshot-proof", "x")
    return v


def test_ac4_confirm_l3_needs_typed_count_and_verified_snapshot() -> None:
    o = Odoo()
    o.rows["res.users"] = {}
    p = pv(o, op="unlink", cls="R6", sub="delete")
    assert p.tier.tier == 3 and p.tier.blast_count == 2
    c = lambda **k: bl.confirm(p, **{"approval": 3, "typed": "2", "fingerprint": "fp1", **k})  # noqa: E731
    assert c(approval=2, snapshot=Snap()).missing == "human-approve-L3"
    assert c(typed="3", snapshot=Snap()).missing == "typed-confirmation"
    for bad in (
        None,
        " ",
        "snap:abc",
        Snap(sid=" "),
        Snap(sid="x"),
        Snap(fp="other"),
        Snap(ok=False),
        Snap(sid="snap:"),
        Snap(sid="snap:  "),
        type("Duck", (), {"snap": Snap().snap, "__call__": lambda self, c: True})(),
    ):
        assert c(snapshot=bad).missing == "snapshot-proof", bad
    assert c(snapshot=Snap(), fingerprint="").missing == "snapshot-proof"
    assert c(typed=" 2", snapshot=Snap()) is None


def test_r2_constructed_verifier_with_failed_restore_blocks() -> None:
    from app.bots import snapshot as sn

    o = Odoo()
    o.rows["res.users"] = {}
    p = pv(o, op="unlink", cls="R6", sub="delete")
    v = sn.Verified(None, Snap().snap, "fp1")  # real constructor: verify() fails -> refused
    assert v.refusal is not None
    assert bl.confirm(p, approval=3, typed="2", snapshot=v, fingerprint="fp1").missing == (
        "snapshot-proof"
    )


def test_m1_real_snapshot_verifier_refusal_blocks() -> None:
    from app.bots import snapshot as sn

    o = Odoo()
    o.rows["res.users"] = {}
    p = pv(o, op="unlink", cls="R6", sub="delete")
    v = sn.Verified.__new__(sn.Verified)
    v.snap, v.refusal = type("S", (), {"id": "snap:x", "fingerprint": "fp1"})(), object()
    assert bl.confirm(p, approval=3, typed="2", snapshot=v, fingerprint="fp1").missing == (
        "snapshot-proof"
    )


def test_m2_record_rules_or_companies_force_l3() -> None:
    o = Odoo()
    o.rows["res.users"] = {}
    o.rows["res.company"] = {1: {}}
    assert not [
        r
        for r in bl.build_blast(o, "res.partner", [1], "unlink").low_count
        if "rule" in r or "compan" in r
    ]
    o.n_rules = 2
    lc = bl.build_blast(o, "res.partner", [1], "unlink").low_count
    assert any(bl.RULE_HIDE in r for r in lc)
    o.n_rules = 0
    o.rows["res.company"] = {1: {}, 2: {}}
    assert any(
        "more than one company" in r
        for r in bl.build_blast(o, "res.partner", [1], "unlink").low_count
    )
    o.deny.add("ir.rule")
    assert any("unreadable" in r for r in bl.build_blast(o, "res.partner", [1], "unlink").low_count)
    t = pv(o, op="unlink", cls="R6", sub="delete").tier
    assert t.tier == 3 and any("record rules may hide rows" in r for r in t.reasons)


def test_l3_binary_summarised_and_pin_masked() -> None:
    import base64

    raw = base64.b64encode(b"\x89PNG" + b"x" * 500).decode()
    d = df.build_diff(Odoo(), "res.partner", [1], {"image_1920": raw})
    (e,) = d.entries
    assert e.masked and e.new["bytes"] == 504 != len(raw) and len(e.new["sha256"]) == 64
    assert raw not in str(d.payload())
    (e,) = df.build_diff(Odoo(), "res.partner", [1], {"x_pin": "1234"}).entries
    assert (e.old, e.new) == (REDACTED, REDACTED)
    for f in ("x_pin", "x_user_otp", "x_secret", "x_api_key", "pin", "x_card_cvv"):
        assert df.secret("res.partner", f, "v"), f
    assert not df.secret("res.partner", "x_shipping_note", "v")


def test_l4_unlink_hash_binds_record_versions() -> None:
    o = Odoo()
    o.rows["res.users"] = {}
    h = pv(o, op="unlink", cls="R6", sub="delete").payload_hash
    o.rows["res.partner"][2]["write_date"] = "2026-10-26 09:00:00"  # child edited
    assert pv(o, op="unlink", cls="R6", sub="delete").payload_hash != h


def test_l6_set_null_owners_in_payload() -> None:
    o = Odoo()
    o.rows["res.users"] = {}
    o.meta["crm.lead"]["company_id"] = {"type": "many2one", "relation": "res.company"}
    o.rows["res.company"][3] = {}
    o.rows["crm.lead"] = {5: {"partner_id": [2, "Bob"], "company_id": [3, "C3"]}}
    p = bl.build_blast(o, "res.partner", [1], "unlink").payload()
    assert p["nulled_ids"] == {"crm.lead": [5]} and 3 in p["companies"]


def test_low_count_reasons_derived_from_catalogue() -> None:
    assert rules.MAIL_THREAD and rules.LOW_RISK_MODELS
    m = sorted(rules.MAIL_THREAD)[0]
    assert any("mail.thread" in r for r in bl.low_count_reasons(m, "unlink"))
    assert bl.low_count_reasons(m, "write") == []
    for lm in sorted(rules.LOW_RISK_MODELS - rules.MAIL_THREAD):
        assert bl.low_count_reasons(lm, "unlink") == []


# ---------------------------------------------------------------- AC5 stale approval
def _guard(o, approved):
    return bl.StaleGuard(REH, approved, lambda m, ids, v: pv(o, m, ids, v))


def test_ac5_hash_stable_and_stale_refused() -> None:
    o = Odoo()
    p = pv(o, ids=[1, 2], values={"name": "Z"})
    assert pv(o, ids=[1, 2], values={"name": "Z"}).payload_hash == p.payload_hash
    s = gd.RunSpec("fp", "t", "bot", "R1", "RF-ANY", gd.Approval(1), "k", rehearsal_id="rh")
    assert _guard(o, p.payload_hash).reserve(s, "res.partner", [1, 2], {"name": "Z"}) is None
    o.rows["res.partner"][2]["name"] = "Bobby"  # someone edits between preview and execute
    r = _guard(o, p.payload_hash).reserve(s, "res.partner", [1, 2], {"name": "Z"})
    assert r.missing == bl.STALE
    for args in (([1], {"name": "Z"}), ([1, 2], {"name": "Y"})):  # other ids / values
        assert _guard(o, p.payload_hash).reserve(s, "res.partner", *args).missing == bl.STALE
    assert _guard(o, "").reserve(s, "res.partner", [1, 2], {"name": "Z"}).missing == bl.STALE
    o.deny.add("res.partner")
    assert (
        _guard(o, p.payload_hash).reserve(s, "res.partner", [1, 2], {"name": "Z"}).allowed is False
    )


def test_ac5_stale_blocks_gate_before_any_write(env) -> None:  # noqa: F811
    engine, sw, log = env
    o = Odoo()
    p = pv(o, ids=[1], values={"name": "Z"})
    o.rows["res.partner"][1]["email"] = "changed@x"
    o.rows["res.partner"][1]["name"] = "Changed"
    gate = gd.WriteGate(sw, log, o, _guard(o, p.payload_hash))
    s = gd.RunSpec(
        "fp-db",
        "m:res.partner:change",
        "bot",
        "R1",
        "RF-ANY",
        gd.Approval(2, "alice"),
        uuid.uuid4().hex,
        rehearsal_id="rh",
    )
    d = df.build_diff(o, "res.partner", [1], {"name": "Z"})
    rep = gate.run(
        s,
        "res.partner",
        [1],
        {"name": "Z"},
        before_image=lambda c: ("bi", c),
        readback=df.readback(o, d, {"name": "Z"}),
        undo=Undo(),
    )
    assert rep.status == "refused" and rep.refusal.missing == bl.STALE
    assert ("res.partner", "write") not in o.calls


# ---------------------------------------------------------------- AC6 readback
def test_ac6_readback_matches_and_mismatches() -> None:
    o = Odoo()
    v = {"name": "Z", "credit": 3.0}
    d = df.build_diff(o, "res.partner", [1, 2], v)
    rb = df.readback(o, d, v)
    assert rb([1]) is False
    for i in (1, 2):
        o.rows["res.partner"][i].update(v)
    assert rb([1, 2]) is True
    assert rb([1, 3]) is False and rb([]) is False  # outside the plan / empty
    o.rows["res.partner"][2]["credit"] = 3.01
    assert rb([2]) is False
    o.deny.add("res.partner")
    assert rb([1]) is False


def test_ac6_chaos_batch3_of_10_trips_and_resume(env) -> None:  # noqa: F811
    engine, sw, log = env
    o = Odoo()
    o.rows["res.partner"] = {i: {"name": f"p{i}"} for i in range(1, 501)}
    ids, v = list(range(1, 501)), {"name": "Z"}
    d = df.build_diff(o, "res.partner", ids, v)
    rb = df.readback(o, d, v)

    def rpc(model, method, args, kw=None):
        if method == "write" and args[0][0] in range(101, 151):
            return True  # batch 3 silently not applied
        return o(model, method, args, kw)

    undo = Undo()
    s = gd.RunSpec(
        "fp-chaos",
        "m:res.partner:change",
        "bot",
        "R1",
        "RF-ANY",
        gd.Approval(2, "alice"),
        uuid.uuid4().hex,
        rehearsal_id="rh",
    )
    rep = gd.WriteGate(sw, log, rpc, REH).run(
        s, "res.partner", ids, v, before_image=lambda c: ("bi", list(c)), readback=rb, undo=undo
    )
    assert (rep.status, rep.written, rep.batches) == ("tripped", 100, 3)
    assert sw.check("fp-chaos") is not None  # kill switch on
    assert sum(o.rows["res.partner"][i]["name"] == "Z" for i in ids) == 100
    rep2 = gd.WriteGate(sw, log, o, REH).run(
        s, "res.partner", ids, v, before_image=lambda c: ("bi", list(c)), readback=rb, undo=undo
    )
    assert rep2.status == "refused"  # resume refused while the switch is on


def _unused(_: Any) -> None:  # keep fixtures imported for pytest
    _clean, engine, fake_owner, ANCHOR, OWNER  # noqa: B018
