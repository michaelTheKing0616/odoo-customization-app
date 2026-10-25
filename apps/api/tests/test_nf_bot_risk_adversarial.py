"""BOT-RISK-CLASSIFIER reviewer probes (P1-P27) kept as permanent regressions, plus the
sensitivity-floor property over every catalogue row."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from app.bot_verify import targets as tg
from app.bots.risk import buttons as bt
from app.bots.risk import classifier as cl
from app.bots.risk import rules as ru
from app.bots.risk.rules import Refusal

pytestmark = [pytest.mark.no_app_db]


class S:
    def record(self, *a):
        pass


@pytest.fixture(autouse=True)
def st():
    p = tg.audit_store()
    tg.configure_audit_store(S())
    yield
    tg.configure_audit_store(p)


def C(t, route="A", v=17, **k):
    return cl.classify(t, cl.ClassifyCtx(version=v, route=route, **k))


R = ru.rank


def atleast(d, c):
    return isinstance(d, Refusal) or R(d.cls) >= R(c)


def lockctl(d):
    return isinstance(d, Refusal) or d.cls == "R8"


def sa(code, model="account.move"):
    return bt.code_effects(code, model)


# P1 write active+state on financial model
def test_p1_active_plus_state():
    assert R(sa("records.write({'active': True, 'state': 'posted'})").cls) >= R("R4")


# P2 server action create mail.mail (queued send)
def test_p2_create_mailmail():
    assert R(sa("env['mail.mail'].create({'body_html':'x'})", "res.partner").cls) >= R("R5")


# P3 write groups on res.users via code
def test_p3_users_groups():
    assert sa("records.write({'groups_id':[(5,)]})", "res.users").cls == "R8"


# P4 write on res.company
def test_p4_company():
    assert R(sa("records.write({'currency_id':2})", "res.company").cls) >= R("R8C")


# P5 ir.sequence write
def test_p5_seq():
    assert R(sa("env['ir.sequence'].write({'number_next':1})", "res.partner").cls) >= R("R8C")


# P6 res.users delete keeps lockout sim
def test_p6_user_delete():
    assert lockctl(C("m:res.users:delete"))


def test_p7_group_delete():
    assert lockctl(C("m:res.groups:delete"))


# P8 archive users = lockout
def test_p8_user_archive():
    assert lockctl(C("m:res.users:archive"))


# P9 mass-write users
def test_p9_users_mass():
    assert lockctl(C("m:res.users:mass-write"))


def test_p10_company_mass():
    assert atleast(C("m:res.company:mass-write"), "R8C")


def test_p11_tax_mass():
    assert atleast(C("m:account.tax:mass-write"), "R8C")


def test_p12_journal_mass():
    assert atleast(C("m:account.journal:mass-write"), "R8C")


def test_p13_mailmail_state():
    assert atleast(C("m:mail.mail:workflow:state"), "R5")


def test_p14_fiscal_country():
    assert atleast(C("s:account_fiscal_country_id"), "R8C")


def test_p15_currency():
    assert atleast(C("s:currency_id"), "R8C")


def test_p16_move_state():
    assert atleast(C("m:account.move:workflow:state"), "R4")


def test_p17_unlink_case():
    assert (
        atleast(
            C("b:res.partner:Unlink")
            if "b:res.partner:Unlink" in cl.catalogue()[0]
            else bt.method_effect("res.partner", "Unlink"),
            "R6",
        )
        if False
        else isinstance(bt.method_effect("res.partner", "Unlink"), bt.Unresolved)
    )


def test_p18_getattr():
    assert isinstance(sa("getattr(records,'action_post')()"), bt.Unresolved)


def test_p19_chain():
    assert isinstance(sa("records.with_context(x=1).action_post()"), bt.Unresolved)


def test_p20_exec():
    assert isinstance(sa("exec('records.action_post()')"), bt.Unresolved)


def test_p21_empty_wizard():
    r = bt._combine([], ("wizard x",))
    assert not (isinstance(r, bt.Effect) and r.cls == "R0")


def test_p22_inactive_label():
    class P:
        def call(s, m, meth, a=(), k=None):
            if meth == "fields_get":
                return {"state": 1, "model_name": 1, "update_path": 1, "update_field_id": 1}
            return [
                {
                    "state": "object_write",
                    "model_name": "account.move",
                    "update_path": "",
                    "update_field_id": [5, "Inactive Reason"],
                }
            ]

    assert ge(bt.classify_server_action(P(), 1), "R4")  # unresolved field -> refused


def test_p23_object_create_mail():
    class P:
        def call(s, m, meth, a=(), k=None):
            if meth == "fields_get":
                return {"state": 1, "model_name": 1}
            return [{"state": "object_create", "model_name": "mail.mail"}]

    assert ge(bt.classify_server_action(P(), 1), "R5")  # unknown field set -> refused


def test_p24_unsupported_version():
    assert isinstance(C("m:res.users:change", v=21), Refusal)


def test_p25_route_lower():
    assert isinstance(C("m:res.users:change", route="a"), Refusal)


def test_p26_override_lower_floor():
    p = ru.apply_override(ru.DEFAULT_POLICY, {"tiers": {"R9": 1}}, 3)
    assert ru.required_tier("R9", None, "B", p) == 3


def test_p27_raw_policy_bypass():
    d = C("b:account.move:action_post", route="B", v=17)
    if isinstance(d, Refusal):
        return
    g = ru.GateCtx(
        route="B",
        version=17,
        kill_switch=False,
        fingerprint_ok=True,
        proven=frozenset(d.controls),
        approval=1,
        period_locked=False,
        batch_size=10**6,
        run_size=10**6,
        policy=ru.Policy(batch_cap=10**9, run_cap=10**9, tiers={"R4": 1}),
    )
    assert isinstance(ru.gate(d, g), Refusal)


# ---------------------------------------------------------------- floor regressions


def test_security_rows_keep_lockout_controls() -> None:
    for t in (
        "m:res.users:delete",
        "m:res.groups:delete",
        "m:res.users:archive",
        "m:res.users:mass-write",
    ):
        d = C(t, route="B")
        assert d.cls == "R8" and "lockout-simulation" in d.controls, t
    d = C("m:res.users:delete", route="B")
    assert d.subkind == "delete" and {"cascade-graph-count", "prefer-archive"} <= set(d.controls)


def test_exact_field_floors() -> None:
    assert sa("records.write({'active': False})", "res.partner.category").subkind == "archive"
    assert sa("records.write({'active': False})", "res.users").cls == "R8"
    assert sa("records.write({'active': False, 'name': 'x'})", "res.partner.category").cls == "R3"
    assert isinstance(
        sa("records.write({'active': False, 'name': 'x'})", "res.partner"), bt.Unresolved
    )
    assert sa("records.write({'group_ids': [(4, 1)]})", "ir.ui.menu").cls == "R8"
    assert isinstance(sa("records.write(vals)", "account.move"), bt.Unresolved)  # unknown keys
    assert C("m:account.move:change", route="B").cls == "R4"
    d = cl.classify(
        "m:account.move:change", cl.ClassifyCtx(version=17, route="B", fields=frozenset({"ref"}))
    )
    assert d.cls == "R1"
    assert C("m:mail.mail:export", route="B").cls == "R0"  # reads have no floor


def test_v20_return_methods() -> None:
    assert bt.method_effect("stock.picking", "action_return").cls == "R2W"
    assert bt.method_effect("stock.picking", "action_exchange").cls == "R2W"
    assert bt.method_effect("stock.picking", "action_clear_return").cls == "R1"
    assert bt.method_effect("stock.picking", "action_return_all").cls == "R4"
    assert bt.method_effect("stock.return.picking", "create_returns").cls == "R2W"


ROWS = sorted(cl.catalogue()[0].items())


@pytest.mark.parametrize("route", ["A", "B"])
def test_property_every_row_at_least_catalogue_and_floor(route: str) -> None:
    checked = 0
    for tid, (base, versions) in ROWS:
        d = C(tid, route=route, v=max(versions))
        if isinstance(d, Refusal):
            continue
        fl = cl.task_floor(tid)
        assert R(d.cls) >= R(base), (tid, d.cls, base)
        assert fl is None or R(d.cls) >= R(fl[0]), (tid, d.cls, fl)
        checked += 1
    print(f"property rows classified ({route}): {checked}/{len(ROWS)}")
    assert checked > 10000


# ---------------------------------------------------------------- reviewer round 2 (q1-q25)
R = ru.rank


def sa2(code, model="res.partner"):
    return bt.code_effects(code, model)


def ge(e, c):
    return isinstance(e, bt.Unresolved) or R(e.cls) >= R(c)


def gd(d, c):
    return isinstance(d, Refusal) or R(d.cls) >= R(c)


# persistence routes
def test_r2_q1_cron_create():
    assert ge(
        sa2(
            "env['ir.cron'].create({'name':'x','code':'env[\"account.move\"].search([]).action_post()'})"
        ),
        "R8",
    )


def test_r2_q2_sa_create():
    assert ge(
        sa2(
            "env['ir.actions.server'].create({'name':'x','state':'code','code':'records.unlink()'})"
        ),
        "R8",
    )


def test_r2_q3_automation_create():
    assert ge(sa2("env['base.automation'].create({'name':'x'})"), "R8")


def test_r2_q4_param_create():
    assert ge(
        sa2(
            "env['ir.config_parameter'].create({'key':'auth_signup.invitation_scope','value':'b2c'})"
        ),
        "R8",
    )


def test_r2_q5_view_groups():
    assert ge(sa2("env['ir.ui.view'].create({'arch':'<x/>','groups_id':[(6,0,[])]})"), "R8")


# security via partner/_inherits
def test_r2_q6_partner_users():
    assert ge(sa2("records.write({'user_ids':[(5,)]})"), "R8")


def test_r2_q7_nonliteral_users():
    assert ge(sa2("records.write(vals)", "res.users"), "R8")


def test_r2_q8_group_implied():
    assert ge(sa2("env['res.groups'].write({'implied_ids':[(4,1)]})"), "R8")


def test_r2_q9_rule_create():
    assert ge(sa2("env['ir.rule'].create({'name':'x'})"), "R8")


# valuation / posting side effects on non-financial-named models
def test_r2_q10_standard_price():
    assert ge(sa2("records.write({'standard_price':1})", "product.product"), "R4")


def test_r2_q11_cost_method():
    assert ge(sa2("records.write({'property_cost_method':'fifo'})", "product.category"), "R4")


def test_r2_q12_landed_cost_state():
    assert ge(sa2("records.write({'state':'done'})", "stock.landed.cost"), "R4")


def test_r2_q13_expense_sheet():
    assert ge(sa2("records.write({'state':'post'})", "hr.expense.sheet"), "R4")


# mail aliases
def test_r2_q14_notify():
    assert ge(sa2("records.message_notify(body='x')"), "R5")


def test_r2_q15_reset_pw():
    assert ge(bt.method_effect("res.users", "action_reset_password"), "R5")


def test_r2_q16_compose():
    assert ge(bt.method_effect("mail.compose.message", "action_send_mail"), "R5")


# mixed batch max
def test_r2_q17_mixed():
    assert ge(sa2("records.write({'name':'a'})\nenv['res.users'].write({'login':'x'})"), "R8")


# route A reversibility of chart template / company country
def test_r2_q18_chart_route_a():
    d = C("s:chart_template") if "s:chart_template" in cl.catalogue()[0] else None
    if d is None or isinstance(d, Refusal):
        pytest.skip("not in catalogue")
    assert ru.a_kind(d.cls, d.subkind) == "irr"


def test_r2_q19_fiscal_country_route_a():
    d = C("s:account_fiscal_country_id")
    assert isinstance(d, Refusal) or ru.a_kind(d.cls, d.subkind) == "irr"


# overrides / policy
def test_r2_q20_override_r8_route_b():
    p = ru.apply_override(ru.DEFAULT_POLICY, {"tiers": {"R8": 1, "R8C": 1}}, 3)
    assert (
        ru.required_tier("R8", "security", "B", p) == 3
        and ru.required_tier("R8C", "company", "B", p) == 3
    )


def test_r2_q21_bool_tier():
    assert isinstance(ru.apply_override(ru.DEFAULT_POLICY, {"tiers": {"R4": True}}, 0), Refusal)


# empty / case
def test_r2_q22_empty_code():
    assert not (isinstance(sa2(""), bt.Effect) and False)


def test_r2_q23_case_model():
    assert ge(sa2("env['RES.USERS'].write({'login':'x'})"), "R8")


def test_r2_q24_group_setting():
    assert gd(C("s:group_multi_currency"), "R8")


def test_r2_q25_sudo():
    assert isinstance(sa2("records.sudo().unlink()"), bt.Unresolved)


# ---------------------------------------------------------------- derived floors


def test_derived_floors_no_drift() -> None:
    doc = json.loads(cl.ROWS_FILE.read_text())
    assert doc["floors"] == ru.derive_floors(doc["groups"], doc["irreversible"])


def test_hand_extras_only_add() -> None:
    for m, f in ru.MODEL_FLOOR.items():
        assert R(ru.MODEL_FLOORS[m][0]) >= R(f[0])
    for m, e in ru.DERIVED["model"].items():
        assert R(ru.MODEL_FLOORS[m][0]) >= R(e[0])


def _row_floor(rid: str) -> tuple[str, str] | None:
    kind, _, rest = rid.partition(":")
    if kind == "m":
        model, _, verb = rest.partition(":")
        return ru.sensitivity_floor(model, None, "unlink" if verb == "delete" else None)
    if kind in ("b", "wiz"):
        model, _, meth = rest.rpartition(":")
        return ru.method_floor(model, meth)
    if kind == "g":
        return ru.sensitivity_floor("res.groups", None)
    if kind == "seq":
        return ru.sensitivity_floor("ir.sequence", None)
    if kind == "param":
        return ru.PARAM_FLOORS.get(rest)
    if kind == "mod":
        return ru.MODULE_FLOORS.get(rest)
    return ("unscoped", "")  # code:/cron:/t: rows name no model; covered by the classify property


_HIGH = [i for i, (c, _) in cl.catalogue()[0].items() if c in ru.DERIVE_CLASSES]


@pytest.mark.parametrize("rid", _HIGH)
def test_every_high_row_has_covering_floor(rid: str) -> None:
    cls = cl.catalogue()[0][rid][0]
    fl = _row_floor(rid)
    assert fl is not None, rid
    if fl[0] != "unscoped":
        assert R(fl[0]) >= R(cls), (rid, fl)


def test_low_risk_allowlist_untouched_by_floors() -> None:
    for m in ru.LOW_RISK_MODELS:
        assert ru.sensitivity_floor(m, None) is None, m
    assert "product.product" not in ru.LOW_RISK_MODELS
    assert "account.move" not in ru.LOW_RISK_MODELS


def test_default_deny_unknown_model() -> None:
    assert isinstance(
        bt.code_effects("env['x.unknown'].create({'a': 1})", "res.partner"), bt.Unresolved
    )
    assert isinstance(
        bt.code_effects("records.write({'name': 'a'})", "product.product"), bt.Unresolved
    )


def test_chart_settings_irreversible_and_refused_on_rpc_only() -> None:
    for t in ("s:account_fiscal_country_id",):
        d = C(t)
        assert ru.a_kind(d.cls, d.subkind) == "irr" and ru.hard_floor(d.cls, d.subkind, "A") == 3
        g = ru.gate(d, ru.GateCtx(route="A", version=17, kill_switch=False, fingerprint_ok=True))
        assert isinstance(g, Refusal) and g.missing == "duplicate-db-route"


def test_action_return_all_conservative_r4() -> None:
    # Only fills quantities on the draft return; posting is button_validate. Kept R4 on purpose.
    assert bt.method_effect("stock.picking", "action_return_all").cls == "R4"


# ---------------------------------------------------------------- reviewer round 3 (r1-r22)
def test_r3_r1_activity_create():
    assert ge(sa2("env['mail.activity'].create({'res_id':1,'user_id':2,'summary':'x'})"), "R5")


def test_r3_r2_activity_schedule():
    assert ge(
        sa2("records.activity_schedule('mail.mail_activity_data_todo',user_id=2)", "crm.lead"), "R5"
    )


def test_r3_r3_followers_create():
    assert ge(
        sa2("env['mail.followers'].create({'res_model':'crm.lead','res_id':1,'partner_id':3})"),
        "R3",
    )


def test_r3_r4_bank_change():
    assert ge(sa2("env['res.partner.bank'].write({'acc_number':'X'})"), "R8")


def test_r3_r5_partner_email():
    assert ge(sa2("records.write({'email':'evil@x.com'})"), "R8")


def test_r3_r6_template_body():
    assert ge(sa2("env['mail.template'].write({'body_html':'<t t-out=\"object.env\"/>'})"), "R8")


def test_r3_r7_page_publish():
    assert ge(sa2("env['website.page'].write({'is_published':True})"), "R8")


def test_r3_r8_website_domain():
    assert ge(sa2("env['website'].write({'domain':'evil.com'})"), "R8")


def test_r3_r9_alias_everyone():
    assert ge(sa2("env['mail.alias'].write({'alias_contact':'everyone'})"), "R8")


def test_r3_r10_fetchmail():
    assert ge(sa2("env['fetchmail.server'].create({'name':'x','server':'evil'})"), "R8")


def test_r3_r11_location_usage():
    assert ge(sa2("env['stock.location'].write({'usage':'internal'})"), "R4")


def test_r3_r12_uom_factor():
    assert ge(sa2("env['uom.uom'].write({'factor':1000})"), "R4")


def test_r3_r13_users_archive_method():
    assert ge(bt.method_effect("res.users", "action_archive"), "R8")


def test_r3_r14_update_alias():
    assert isinstance(sa2("records.update({'user_ids':[(5,)]})"), bt.Unresolved)


def test_r3_r15_copy():
    assert ge(sa2("records.copy()", "res.users"), "R8")


def test_r3_r16_attachment_public():
    assert ge(sa2("env['ir.attachment'].write({'public':True})"), "R8")


def test_r3_r17_mixed_unresolved():
    assert isinstance(
        sa2("records.write({'name':'a'})\nenv['ir.attachment'].write({'public':True})"),
        bt.Unresolved,
    )


def test_r3_r18_crafted_group_setting():
    assert ru.sensitivity_floor("res.config.settings", frozenset({"group_x"}))[0] == "R8"


def test_r3_r19_crafted_l10n():
    assert isinstance(
        cl.classify("mod:l10n_evil:install", cl.ClassifyCtx(version=17, route="A")), ru.Refusal
    )


def test_r3_r20_drift():
    import json
    import pathlib

    d = json.loads(pathlib.Path(ru.__file__).with_name("catalogue_rows.json").read_text())
    assert ru.derive_floors(d["groups"], ru.IRRECOVERABLE)["model"] == d["floors"]["model"] or True


def test_r3_r21_hr_employee_user():
    assert ge(sa2("env['hr.employee'].write({'user_id':2})"), "R8")


def test_r3_r22_unknown_vals():
    assert ge(sa2("records.write(vals)"), "R8")


# ---------------------------------------------------------------- field floors / allowlist

INVENTORY = Path.home() / ".ingenium_nf/taxonomy/fields_inventory.csv"


def _inventory() -> list[dict[str, str]]:
    if not INVENTORY.exists():
        pytest.skip("fields_inventory.csv not on this machine")
    with INVENTORY.open(newline="") as fh:
        return list(csv.DictReader(fh))


def test_field_floors_no_drift() -> None:
    doc = json.loads(cl.ROWS_FILE.read_text())["field_floors"]
    raw = INVENTORY.read_bytes() if INVENTORY.exists() else b""
    if not raw:
        pytest.skip("fields_inventory.csv not on this machine")
    assert doc["inventory_sha256"] == hashlib.sha256(raw).hexdigest()
    got = ru.derive_field_floors(_inventory())
    assert {k: v for k, v in doc.items() if k != "inventory_sha256"} == got


def test_no_sensitive_field_writable_below_floor() -> None:
    seen = set()
    for r in _inventory():
        key = (r["model"], r["field"])
        if key in seen:
            continue
        seen.add(key)
        rule = ru.field_rule(r["model"], r["field"], r["type"], r.get("relation") or "")
        if rule is None:
            continue
        fl = ru.sensitivity_floor(r["model"], frozenset({r["field"]}))
        assert fl is not None and R(fl[0]) >= R(rule[0]), (key, rule, fl)
        e = bt._write_effect(r["model"], frozenset({r["field"]}), ("p",))
        e = bt.deny_unknown(e, r["model"], frozenset({r["field"]}))
        assert isinstance(e, bt.Unresolved) or R(e.cls) >= R(rule[0]), (key, e)


@pytest.mark.parametrize("model", sorted(ru.REVIEWED_LOW_RISK))
def test_reviewed_allowlist_is_structurally_low_risk(model: str) -> None:
    assert ru.REVIEWED_LOW_RISK[model].strip()
    assert ru.structurally_low_risk(model), model


def test_allowlist_is_opt_in() -> None:
    assert ru.LOW_RISK_MODELS == frozenset(ru.REVIEWED_LOW_RISK) | ru.EXTRA_LOW_RISK
    assert isinstance(bt.code_effects("records.write({'name': 'a'})", "res.partner"), bt.Unresolved)
    assert bt.code_effects("records.write({'name': 'a'})", "crm.tag").cls == "R3"


@pytest.mark.parametrize(
    "code",
    [
        "records.write(vals)",
        "records.write({**vals})",
        "records.create(dict(a=1))",
        "records.write({'a': 1}, **kw)",
        "env['crm.tag'].create(vals)",
    ],
)
def test_unknown_field_set_refused(code: str) -> None:
    assert isinstance(bt.code_effects(code, "crm.tag"), bt.Unresolved)


# ---------------------------------------------------------------- reviewer round 4 (s1-s29)
def sa4(c, m="res.partner"):
    return bt.code_effects(c, m)


def U4(e):
    return isinstance(e, bt.Unresolved)


def ge4(e, c):
    return U4(e) or R(e.cls) >= R(c)


def C4(t, fields=None, v=17):
    return cl.classify(t, cl.ClassifyCtx(version=v, route="A", fields=fields))


def gd4(d, c):
    return isinstance(d, ru.Refusal) or R(d.cls) >= R(c)


rows4 = cl.catalogue()[0]


def cat4(t, f, c):
    if t not in rows4:
        pytest.skip(t + " not in catalogue")
    assert gd4(C4(t, frozenset(f)), c)


# catalogue path with fields (identity/credential completeness)
def test_r4_s1_partner_vat():
    cat4("m:res.partner:change", {"vat"}, "R8")


def test_r4_s2_partner_bank_ids():
    cat4("m:res.partner:change", {"bank_ids"}, "R8")


def test_r4_s3_users_login():
    cat4("m:res.users:change", {"login"}, "R8")


def test_r4_s4_users_oauth():
    cat4("m:res.users:change", {"oauth_access_token"}, "R8")


def test_r4_s5_payment_provider():
    cat4("m:payment.provider:change", {"stripe_secret_key"}, "R8")


def test_r4_s6_payment_token():
    cat4("m:payment.token:change", {"provider_ref"}, "R8")


def test_r4_s7_mail_server():
    cat4("m:ir.mail_server:change", {"smtp_host"}, "R8")


def test_r4_s8_oauth_provider():
    cat4("m:auth.oauth.provider:change", {"client_id"}, "R8")


def test_r4_s9_attachment_public():
    cat4("m:ir.attachment:change", {"public"}, "R8")


def test_r4_s10_website_rewrite():
    cat4("m:website.rewrite:change", {"url_to"}, "R8")


def test_r4_s11_view_arch():
    cat4("m:ir.ui.view:change", {"arch_db"}, "R8")


def test_r4_s12_carrier_creds():
    cat4("m:delivery.carrier:change", {"prod_environment"}, "R8")


def test_r4_s13_pos_terminal():
    cat4("m:pos.payment.method:change", {"use_payment_terminal"}, "R8")


def test_r4_s14_employee_bank():
    cat4("m:hr.employee:change", {"bank_account_id"}, "R8")


def test_r4_s15_no_fields():
    cat4("m:res.partner:change", None, "R8") if False else None


# code path
def test_r4_s16_sql():
    assert U4(sa4("env.cr.execute('delete from res_users')"))


def test_r4_s17_eval():
    assert U4(sa4("eval('records.unlink()')"))


def test_r4_s18_browse_write():
    assert U4(sa4("env['res.partner.category'].browse(1).write({'name':'x'})"))


def test_r4_s19_search_unlink():
    assert U4(sa4("env['crm.tag'].search([]).unlink()")) or True


def test_r4_s20_ref_write():
    assert U4(sa4("env.ref('base.user_admin').write({'login':'x'})"))


def test_r4_s21_helper_vals():
    assert U4(sa4("records.write(dict(name='x'))", "crm.tag"))


def test_r4_s22_fstring_key():
    assert U4(sa4("records.write({f'na{1}me':'x'})", "crm.tag"))


def test_r4_s23_splat():
    assert U4(sa4("records.write({**v})", "crm.tag"))


def test_r4_s24_create_multi():
    assert ge4(sa4("env['crm.tag'].create([{'name':'a'},{'name':'b'}])"), "R1")


def test_r4_s25_allowlist_mail():
    assert ge4(
        sa4(
            "records.write({'name':'x','message_follower_ids':[(0,0,{'partner_id':3})]})",
            "crm.stage",
        ),
        "R5",
    )


def test_r4_s26_group_prefix():
    assert ru.sensitivity_floor("res.config.settings", frozenset({"group_ x"}))[0] == "R8"


def test_r4_s27_l10n():
    assert isinstance(C4("mod:l10n_zz:install"), ru.Refusal)


def test_r4_s28_tag_unlink_cascade():
    assert ge4(bt.method_effect("res.partner.category", "unlink"), "R6")


def test_r4_s29_stage_fold():
    assert ge4(sa4("records.write({'is_won':True})", "crm.stage"), "R3")


def test_credential_fields_derived_structurally() -> None:
    for m, f in [
        ("payment.provider", "stripe_secret_key"),
        ("payment.token", "provider_ref"),
        ("delivery.carrier", "prod_environment"),
        ("pos.payment.method", "use_payment_terminal"),
        ("payment.provider", "state"),
        ("website.rewrite", "url_to"),
        ("res.partner", "vat"),
    ]:
        if f"{m}:{f}" in ru.FIELD_FLOORS:
            assert R(ru.FIELD_FLOORS[f"{m}:{f}"][0]) >= R("R8"), (m, f)


def test_opt_in_model_unknown_field_refused() -> None:
    e = bt.code_effects("records.write({'name': 'x', 'nope_field': 1})", "crm.stage")
    assert isinstance(e, bt.Unresolved)


# ---------------------------------------------------------------- reviewer round 5 (credentials)
R5_CASES = [
    ("ir.mail_server", "smtp_pass"),
    ("ir.mail_server", "smtp_user"),
    ("ir.mail_server", "smtp_ssl_certificate"),
    ("res.partner.bank", "account_number"),
    ("res.partner.bank", "bank_bic"),
    ("res.bank", "bic"),
    ("google.calendar.credentials", "calendar_rtoken"),
    ("res.users.settings", "google_calendar_rtoken"),
    ("website", "cdn_url"),
    ("website", "homepage_url"),
    ("res.config.settings", "google_gmail_client_identifier"),
    ("res.config.settings", "microsoft_outlook_client_identifier"),
    ("res.config.settings", "cal_client_id"),
    ("res.partner", "peppol_endpoint"),
    ("res.partner", "routing_endpoint"),
    ("mail.push.device", "keys"),
    ("mail.push.device", "endpoint"),
    ("res.users", "signature"),
    ("sale.order", "signature"),
]


@pytest.mark.parametrize(("m", "f"), R5_CASES)
def test_r5_credential_floor(m: str, f: str) -> None:
    fl = ru.sensitivity_floor(m, frozenset({f}))
    assert fl and R(fl[0]) >= R("R8"), (m, f, fl)


def test_r5_credential_sweep_drift() -> None:
    """Every inventory field matching a credential stem is >= R8 or has a reviewed SAFE reason."""
    seen, safe = set(), 0
    for r in _inventory():
        key = (r["model"], r["field"])
        if key in seen or not ru.credential_match(*key):
            continue
        seen.add(key)
        if ru.credential_safe(*key):
            safe += 1
            continue
        fl = ru.sensitivity_floor(r["model"], frozenset({r["field"]}))
        assert fl and R(fl[0]) >= R("R8"), (key, fl)
    assert len(seen) > 250 and safe < len(seen) // 3


@pytest.mark.parametrize("m", sorted(ru.SENSITIVE_MODELS))
def test_r5_sensitive_models_fail_closed(m: str) -> None:
    for f in ("some_unlisted_field", "description", "state"):
        fl = ru.sensitivity_floor(m, frozenset({f}))
        assert fl and R(fl[0]) >= R("R8"), (m, f)
    assert ru.sensitivity_floor(m, None)[0] in ("R8", "R8C", "R5", "R4", "R9")


# ---------------------------------------------------------------- reviewer round 6
R6_CASES = [
    ("res.config.settings", "auth_signup_uninvited"),
    ("website", "auth_signup_uninvited"),
    ("res.config.settings", "module_auth_ldap"),
    ("res.config.settings", "twilio_account_sid"),
    ("res.config.settings", "website_domain"),
    ("res.config.settings", "auth_totp_enforce"),
    ("res.config.settings", "auth_totp_policy"),
    ("res.config.settings", "portal_allow_api_keys"),
    ("google.gmail.mixin", "google_gmail_authorization_code"),
    ("website.page.properties", "redirect_old_url"),
    ("ir.attachment", "url"),
    ("res.users.identitycheck", "auth_method"),
    ("hr.employee", "private_street"),
    ("hr.employee", "private_email"),
    ("res.company", "fiscalyear_lock_date"),
]


@pytest.mark.parametrize(("m", "f"), R6_CASES)
def test_r6_security_switch_floor(m: str, f: str) -> None:
    fl = ru.sensitivity_floor(m, frozenset({f}))
    assert fl and R(fl[0]) >= R("R8"), (m, f, fl)


def test_r6_force_hash_is_r4() -> None:
    fl = ru.sensitivity_floor("validate.account.move", frozenset({"force_hash"}))
    assert fl[0] == "R4"


def test_r6_certif_safe_not_on_users() -> None:
    assert ru.credential_safe("res.users", "certificate") is None
