"""Real-database check of the stock-first to-do automation on Odoo 17-20.

Skipped unless ODOO_LIVE=1. Start the disposable stack first (own project, own ports):
  docker compose -p ingenium-live-test -f tests/odoo_live/docker-compose.yml up -d
  ODOO_LIVE=1 uv run pytest -m odoo_live tests/test_odoo_live_automation.py
  docker compose -p ingenium-live-test -f tests/odoo_live/docker-compose.yml down -v
"""

from __future__ import annotations

import datetime as dt
import os
import time
import xmlrpc.client

import pytest

pytestmark = [
    pytest.mark.odoo_live,
    pytest.mark.no_app_db,
    pytest.mark.skipif(os.environ.get("ODOO_LIVE") != "1", reason="set ODOO_LIVE=1 with the live stack up"),
]

PORTS = {17: 18917, 18: 18918, 19: 18919, 20: 18920}


def _client(major: int):
    from odoo_client import OdooClient
    from odoo_client.models import ConnectionConfig

    url = f"http://127.0.0.1:{PORTS[major]}"
    try:
        xmlrpc.client.ServerProxy(url + "/xmlrpc/2/common").version()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Odoo {major} not reachable at {url}: {exc}")
    client = OdooClient(ConnectionConfig(url=url, db=f"live{major}", username="admin", password="admin"))
    client.connect()
    return client


@pytest.mark.parametrize("major", sorted(PORTS))
def test_todo_n_days_before_date_is_built_and_fires(major: int) -> None:
    from app.ai_apply_readiness import prepare_spec_for_live_apply
    from app.ai_design_compile import compile_design_draft
    from app.odoo_snapshot import _SNAPSHOT, clear_snapshot_cache, get_snapshot, set_snapshot
    from app.spec_apply_ui import apply_module_spec_ui
    from test_studio_stock_first_corpus import BRIEF, DATE, OWNER, _design, _reminder, _verified

    client = _client(major)
    ex = client.execute_kw

    def call(model, method, args, kwargs):
        return ex(model, method, args, kwargs)

    clear_snapshot_cache(f"live{major}")
    snap = get_snapshot(call, f"live{major}", BRIEF)
    assert snap.ok and snap.major == major, snap.problems
    caps = snap.capabilities()
    assert caps["automated_actions"] and caps["time_triggers"] and caps["schedule_todo_action"]
    assert snap.groups and "res.partner" in snap.views

    design = _design([DATE, OWNER], _verified([_reminder()], BRIEF))
    token = set_snapshot(snap)
    try:
        draft = compile_design_draft(design, prompt=BRIEF)
    finally:
        _SNAPSHOT.reset(token)
    assert len(draft["automations"]) == 1, draft["_design_notes"]
    spec, _notes = prepare_spec_for_live_apply(draft)
    result = apply_module_spec_ui(client, spec)
    assert not [w for w in result.warnings if "failed" in w.lower() or "skipped" in w.lower()], result.warnings
    # Every new x_ model gets a window action and a menu leaf that opens it (was missing: res_model key).
    for model in ("x_renewal", "x_renewal_note"):
        acts = ex("ir.actions.act_window", "search", [[["res_model", "=", model]]], {})
        assert acts, f"no window action for {model} on {major}"
        assert ex("ir.ui.menu", "search", [[["action", "in", [f"ir.actions.act_window,{i}" for i in acts]]]], {}), model
    assert result.open_action_id and result.root_menu_id

    autos = ex("base.automation", "search_read", [[["model_id.model", "=", "x_renewal"]]],
               {"fields": ["trigger", "trg_date_id", "trg_date_range", "trg_date_range_type", "action_server_ids"]})
    assert len(autos) == 1, autos
    auto = autos[0]
    assert auto["trigger"] == "on_time" and auto["trg_date_range_type"] == "day"
    assert auto["trg_date_id"] and "x_renewal_date" in str(
        ex("ir.model.fields", "read", [[auto["trg_date_id"][0]]], {"fields": ["name"]})[0]["name"])
    if major >= 19:
        mode = ex("base.automation", "read", [[auto["id"]]], {"fields": ["trg_date_range_mode"]})[0]
        assert (auto["trg_date_range"], mode["trg_date_range_mode"]) == (7, "before")
    else:
        assert auto["trg_date_range"] == -7
    action = ex("ir.actions.server", "read", [auto["action_server_ids"]],
                {"fields": ["state", "activity_user_type", "activity_user_field_name"]})[0]
    assert action["state"] == "next_activity"
    assert (action["activity_user_type"], action["activity_user_field_name"]) == ("generic", "x_owner_id")

    # A record whose renewal is 6 days out is already inside the 7-day window.
    uid = client.uid if isinstance(getattr(client, "uid", None), int) else 2
    due = (dt.date.today() + dt.timedelta(days=6)).isoformat()
    rec = ex("x_renewal", "create", [{"x_name": f"Live {major}", "x_renewal_date": due, "x_owner_id": uid}])
    rec = rec[0] if isinstance(rec, list) else rec
    # Re-runs on the same database: let the rule see records created after its last run.
    ex("base.automation", "write", [[auto["id"]], {"last_run": False}])
    crons = ex("ir.cron", "search", [[["model_id.model", "=", "base.automation"]]], {})
    assert crons, "time-based automation cron missing"
    acts: list = []
    for _ in range(20):
        try:
            ex("ir.cron", "method_direct_trigger", [crons], {})
        except Exception:  # noqa: BLE001 - None-returning RPCs on some majors
            pass
        acts = ex("mail.activity", "search_read", [[["res_model", "=", "x_renewal"], ["res_id", "=", rec]]],
                  {"fields": ["user_id", "summary"]})
        if acts:
            break
        time.sleep(3)
    assert acts, "no activity created by the time-based automation"
    assert acts[0]["user_id"] and acts[0]["user_id"][0] == uid


def test_odoo20_access_domain_limits_users_to_own_records() -> None:
    """Odoo 20 has no ir.rule: a group ir.access row with a domain is the row-level rule."""
    from odoo_client import OdooClient
    from odoo_client.models import ConnectionConfig
    from odoo_client.security import CreateAccessRightRequest

    test_todo_n_days_before_date_is_built_and_fires(20)  # ensures x_renewal exists (idempotent)
    admin = _client(20)
    ex = admin.execute_kw
    group_user = admin.resolve_xml_id("base.group_user")
    # Replace the open default row for internal users with an own-records-only row.
    ex("ir.access", "write", [ex("ir.access", "search", [[["model_id.model", "=", "x_renewal"],
                                                          ["group_id", "=", group_user],
                                                          ["domain", "=", False]]]), {"active": False}])
    if not ex("ir.access", "search", [[["name", "=", "x_renewal own"]]]):
        admin.create_access_right(CreateAccessRightRequest(
            model="x_renewal", name="x_renewal own", group_id=group_user,
            domain="[('x_owner_id', '=', user.id)]"))
    row = ex("ir.access", "search_read", [[["name", "=", "x_renewal own"]]], {"fields": ["kind", "operation", "domain"]})[0]
    assert (row["kind"], row["operation"]) == ("permission", "crud") and "user.id" in row["domain"]

    login = "live_restricted"
    uid = (ex("res.users", "search", [[["login", "=", login]]]) or [None])[0]
    if uid is None:
        uid = ex("res.users", "create", [{"name": "Restricted", "login": login, "password": "restricted-pw",
                                          "group_ids": [(6, 0, [group_user])]}])
        uid = uid[0] if isinstance(uid, list) else uid
    mine_admin = ex("x_renewal", "create", [{"x_name": "admin own", "x_owner_id": admin.uid or 2}])
    mine_admin = mine_admin[0] if isinstance(mine_admin, list) else mine_admin

    user = OdooClient(ConnectionConfig(url=f"http://127.0.0.1:{PORTS[20]}", db="live20",
                                       username=login, password="restricted-pw"))
    user.connect()
    own = user.execute_kw("x_renewal", "create", [{"x_name": "user own", "x_owner_id": uid}])
    own = own[0] if isinstance(own, list) else own
    seen = user.execute_kw("x_renewal", "search", [[]], {})
    assert own in seen and mine_admin not in seen
    assert all(r["x_owner_id"][0] == uid for r in user.execute_kw("x_renewal", "search_read", [[]], {"fields": ["x_owner_id"]}))
    with pytest.raises(Exception, match="(?i)not allowed|access"):
        user.execute_kw("x_renewal", "write", [[mine_admin], {"x_name": "hijack"}])


def test_odoo20_overview_snapshot_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both Overview endpoints against live Odoo 20: metadata only, ir.access domains, no arch."""
    from types import SimpleNamespace

    import app.routers.connections as rc
    from app.odoo_snapshot import clear_snapshot_cache

    test_odoo20_access_domain_limits_users_to_own_records()
    client = _client(20)
    reads: list[str] = []

    def call(model, method, args, kwargs):
        if method in {"search_read", "read", "search"}:
            reads.append(model)
        return client.execute_kw(model, method, args, kwargs)

    row = SimpleNamespace(id="live20-overview", url=f"http://127.0.0.1:{PORTS[20]}", server_version="20.0")
    clear_snapshot_cache(row.id)
    monkeypatch.setattr(rc, "get_scoped_connection_or_404", lambda db, cid, auth: row)
    monkeypatch.setattr(rc, "_snapshot_call", lambda r, db: call)

    snap = rc.get_connection_snapshot("x", db=None, auth=None)
    assert snap["major"] == 20 and snap["hosting"] == "onprem"
    assert {"model": "x_renewal", "label": "Renewal"} in snap["custom_models"]
    assert any(a["name"] for a in snap["automations"]) and snap["counts"]["groups"] > 0
    caps = {c["key"]: c["available"] for c in snap["can_change"]}
    assert caps.get("python_module_install") == "yes" and caps.get("custom_fields") == "yes"

    d = rc.get_connection_snapshot_model("x", "x_renewal", db=None, auth=None)
    assert {"x_name", "x_owner_id", "x_renewal_date"} <= {f["name"] for f in d["fields"]}
    assert "form" in d["views"]["types"] and "<" not in str(d["views"])
    rules = d["record_rules"]
    assert rules["source"] == "ir.access"
    assert any("user.id" in r["domain"] and r["kind"] == "permission" for r in rules["rows"])
    assert any(a["kind"] == "next_activity" for a in d["server_actions"])
    acts = client.execute_kw("ir.actions.act_window", "search", [[["res_model", "=", "x_renewal"]]], {})
    assert bool(d["menus"]) == bool(acts and client.execute_kw(
        "ir.ui.menu", "search", [[["action", "in", [f"ir.actions.act_window,{i}" for i in acts]]]], {}))
    assert "x_renewal" not in reads and "res.partner" not in reads  # no business records


def test_odoo20_apply_restricted_access_switches_off_the_open_row() -> None:
    """Apply a domain-restricted ir.access for a group; the open row for that group must stop granting."""
    from app.spec_apply_ui import UiApplyResult, _apply_access_rules

    test_todo_n_days_before_date_is_built_and_fires(20)
    admin = _client(20)
    ex = admin.execute_kw
    group_user = admin.resolve_xml_id("base.group_user")
    # Start from an open row for internal users (what a plain Apply leaves behind).
    for rid in ex("ir.access", "search", [[["name", "in", ["x_renewal own (applied)"]]]]):
        ex("ir.access", "unlink", [[rid]])
    opened = ex("ir.access", "search", [[["model_id.model", "=", "x_renewal"], ["group_id", "=", group_user],
                                          ["domain", "=", False]]], {"context": {"active_test": False}})
    if opened:
        ex("ir.access", "write", [opened, {"active": True}])
    else:
        admin.create_access_right(__import__("odoo_client.security", fromlist=["x"]).CreateAccessRightRequest(
            model="x_renewal", name="x_renewal open", group_id=group_user))
    for rid in ex("ir.access", "search", [[["name", "=", "x_renewal own"]]]):
        ex("ir.access", "write", [[rid], {"active": False}])

    result = UiApplyResult()
    spec = {"access_rules": [{"name": "x_renewal own (applied)", "model": "x_renewal", "group": "base.group_user",
                              "domain": "[('x_owner_id', '=', user.id)]"}]}
    _apply_access_rules(admin, spec, result)
    assert result.access_rights_created == 1, result.warnings
    assert any("Turned off the open access" in w for w in result.warnings), result.warnings
    assert not ex("ir.access", "search", [[["model_id.model", "=", "x_renewal"], ["group_id", "=", group_user],
                                            ["domain", "=", False]]])
    row = ex("ir.access", "search_read", [[["name", "=", "x_renewal own (applied)"]]],
             {"fields": ["operation", "domain", "group_id"]})[0]
    assert row["operation"] == "crud" and "user.id" in row["domain"] and row["group_id"][0] == group_user

    from odoo_client import OdooClient
    from odoo_client.models import ConnectionConfig

    login = "live_restricted"
    uid = (ex("res.users", "search", [[["login", "=", login]]]) or [None])[0]
    if uid is None:
        uid = ex("res.users", "create", [{"name": "Restricted", "login": login, "password": "restricted-pw",
                                          "group_ids": [(6, 0, [group_user])]}])
        uid = uid[0] if isinstance(uid, list) else uid
    other = ex("x_renewal", "create", [{"x_name": "admin only", "x_owner_id": admin.uid or 2}])
    other = other[0] if isinstance(other, list) else other
    user = OdooClient(ConnectionConfig(url=f"http://127.0.0.1:{PORTS[20]}", db="live20",
                                       username=login, password="restricted-pw"))
    user.connect()
    assert other not in user.execute_kw("x_renewal", "search", [[]], {})


def _fix_spec(kind: str, model: str, label: str) -> dict:
    """Same shape the Overview's AttentionFix sends (apps/web .../edit/AttentionFix.tsx)."""
    base = {"technical_name": f"overview_fix_{model}", "display_name": label,
            "models": [{"model": model, "description": label, "mode": "new", "fields": []}]}
    if kind == "access":
        return {**base, "access_rules": [{"name": f"access_{model}_user", "model": model, "group": "base.group_user",
                                          "perm_read": True, "perm_write": True, "perm_create": True, "perm_unlink": False}]}
    return {**base,
            "actions": [{"xml_id": f"action_{model}", "name": label, "res_model": model, "view_mode": "list,form"}],
            "menus": [{"xml_id": f"menu_{model}_root", "name": label, "sequence": 50},
                      {"xml_id": f"menu_{model}", "name": label, "parent_xml_id": f"menu_{model}_root",
                       "action_xml_id": f"action_{model}", "sequence": 10}]}


@pytest.mark.parametrize("major", sorted(PORTS))
def test_overview_edits_add_field_and_fix_attention(major: int) -> None:
    from odoo_client import CreateFieldRequest, FieldType

    from app.odoo_snapshot import clear_snapshot_cache, connection_overview, model_detail, overview_attention
    from app.spec_apply_ui import apply_module_spec_ui

    client = _client(major)
    ex = client.execute_kw

    def call(model, method, args, kwargs):
        return ex(model, method, args, kwargs)

    model, label, key = "x_overview_probe", "Overview probe", f"ov{major}"
    if not ex("ir.model", "search", [[["model", "=", model]]]):
        ex("ir.model", "create", [{"name": label, "model": model}])
    # 1. Add a field the way the Overview does (POST /fields -> client.create_field).
    if not ex("ir.model.fields", "search", [[["model", "=", model], ["name", "=", "x_note"]]]):
        client.create_field(CreateFieldRequest(model=model, name="x_note", field_description="Note", ttype=FieldType.CHAR))
    clear_snapshot_cache(key)
    connection_overview(call, key)
    detail = model_detail(call, key, model)
    note = next(f for f in detail["fields"] if f["name"] == "x_note")
    assert note["custom"] is True and isinstance(note["id"], int)
    keys = {i["key"] for i in overview_attention(call, key, None) if model in i["names"]}
    if not ex("ir.actions.act_window", "search", [[["res_model", "=", model]]]):
        assert "custom_no_menu" in keys
    # 2. The attention fixes, through the same Apply path the Overview uses.
    for kind in ("access", "menu"):
        r = apply_module_spec_ui(client, _fix_spec(kind, model, label))
        assert not [w for w in r.warnings if "failed" in w.lower() or "skipped" in w.lower()], (kind, r.warnings)
    clear_snapshot_cache(key)
    connection_overview(call, key)
    left = {i["key"] for i in overview_attention(call, key, None) if model in i["names"]}
    assert not ({"custom_no_access", "custom_no_menu"} & left), left
    acts = ex("ir.actions.act_window", "search", [[["res_model", "=", model]]])
    assert acts and ex("ir.ui.menu", "search", [[["action", "in", [f"ir.actions.act_window,{i}" for i in acts]]]])
    # Re-running a fix is harmless (idempotent).
    again = apply_module_spec_ui(client, _fix_spec("menu", model, label))
    assert len(ex("ir.actions.act_window", "search", [[["res_model", "=", model]]])) == len(acts), again.warnings


# ---------------------------------------------------------------- stock-model extension (Overview)

def _overlay(major: int, client, body: dict):
    """POST /views/overlay/apply exactly as the Overview's Extend this view sends it."""
    import app.snapshots as snapshots
    from types import SimpleNamespace

    from app.routers import views

    mp = pytest.MonkeyPatch()
    mp.setattr(views, "_client", lambda cid, db: client)
    mp.setattr(snapshots, "snapshot_view", lambda *a, **k: SimpleNamespace(id="snap"))
    try:
        return views.overlay_apply(f"live{major}", views.OverlayApplyBody(**body), db=None)
    finally:
        mp.undo()


@pytest.mark.parametrize("major", sorted(PORTS))
def test_stock_model_extension_form_automation_access(major: int) -> None:
    from odoo_client import CreateFieldRequest, FieldType

    from app.spec_apply_ui import apply_module_spec_ui

    client = _client(major)
    ex = client.execute_kw
    # 1. Own field on a built-in model, then shown on Odoo's form through an extension view.
    if not ex("ir.model.fields", "search", [[["model", "=", "res.partner"], ["name", "=", "x_overview_tier"]]], {}):
        client.create_field(CreateFieldRequest(model="res.partner", name="x_overview_tier", field_description="Tier", ttype=FieldType.CHAR))
    stale = ex("ir.ui.view", "search", [[["name", "=", "res.partner.overlay.form"]]], {})
    if stale:
        ex("ir.ui.view", "unlink", [stale], {})
    primary = client.find_view("res.partner", "form", primary_only=True)
    before = ex("ir.ui.view", "read", [[primary.id]], {"fields": ["arch_db"]})[0]["arch_db"]
    out = _overlay(major, client, {"model": "res.partner", "view_type": "form", "operation": "add_field",
                                   "expr": "(//field[@name='email'])[1]", "add_field_name": "x_overview_tier", "add_position": "after"})
    child = ex("ir.ui.view", "read", [[out.view_id]], {"fields": ["inherit_id", "mode", "arch_db"]})[0]
    assert child["inherit_id"][0] == primary.id and child["mode"] == "extension"
    assert ex("ir.ui.view", "read", [[primary.id]], {"fields": ["arch_db"]})[0]["arch_db"] == before, "original arch was edited"
    merged = ex("res.partner", "get_views", [[[primary.id, "form"]]], {})["views"]["form"]["arch"]
    assert merged.count('name="x_overview_tier"') == 1
    _overlay(major, client, {"model": "res.partner", "view_type": "form", "operation": "add_field",
                             "expr": "(//field[@name='email'])[1]", "add_field_name": "x_overview_tier", "add_position": "after"})
    again = ex("res.partner", "get_views", [[[primary.id, "form"]]], {})["views"]["form"]["arch"]
    assert again.count('name="x_overview_tier"') == 1, "pressing Apply twice duplicated the field"
    # It lands right after the main form's email, not inside the nested child-contact form.
    first_email = merged.index('name="email"')
    second_email = merged.find('name="email"', first_email + 1)
    tier = merged.index('name="x_overview_tier"')
    assert first_email < tier and (second_email == -1 or tier < second_email)

    # 2. Automation rule on the built-in model (same Apply + checks as App Studio).
    spec = {"technical_name": "overview_auto_res_partner", "display_name": "Welcome call", "models": [],
            "automations": [{"name": "Overview welcome call", "model": "res.partner", "trigger": "on_create",
                             "safe_actions": [{"kind": "next_activity", "summary": "Welcome call",
                                               "user_type": "generic", "activity_user_field_name": "user_id"}]}]}
    res = apply_module_spec_ui(client, spec, apply_views=False, apply_menus=False, apply_automations=True)
    assert not [w for w in res.warnings if "failed" in w.lower() or "skipped" in w.lower()], res.warnings
    autos = ex("base.automation", "search_read", [[["model_id.model", "=", "res.partner"], ["name", "=", "Overview welcome call"]]],
               {"fields": ["trigger", "action_server_ids"]})
    assert autos and autos[0]["trigger"] == "on_create"
    act = ex("ir.actions.server", "read", [autos[0]["action_server_ids"][:1]], {"fields": ["state", "activity_user_field_name"]})[0]
    assert (act["state"], act["activity_user_field_name"]) == ("next_activity", "user_id")

    # 3. Own-records access for portal users on the built-in model.
    domain = "[('create_uid', '=', user.id)]"
    spec = {"technical_name": "overview_access_res_partner", "display_name": "res.partner", "models": [],
            "access_rules": [{"name": "access_res_partner_group_portal_own", "model": "res.partner", "group": "base.group_portal",
                              "perm_read": True, "perm_write": True, "perm_create": False, "perm_unlink": False, "domain": domain}]}
    res = apply_module_spec_ui(client, spec, apply_views=False, apply_menus=False, apply_automations=False)
    assert not [w for w in res.warnings if "failed" in w.lower()], res.warnings
    if major >= 20:
        rows = ex("ir.access", "search_read", [[["model_id.model", "=", "res.partner"], ["name", "=", "access_res_partner_group_portal_own"]]],
                  {"fields": ["domain", "group_id"]})
        assert rows and "create_uid" in str(rows[0]["domain"])
    else:
        rules = ex("ir.rule", "search_read", [[["model_id.model", "=", "res.partner"], ["domain_force", "=", domain]]], {"fields": ["groups"]})
        assert rules and all(r["groups"] for r in rules), "own-records rule must be bound to its group, never global"
        # Portal already has Odoo's own access row on contacts; it is kept, and the limit rides on the rule.
        assert ex("ir.model.access", "search", [[["model_id.model", "=", "res.partner"], ["group_id.name", "ilike", "portal"]]], {})
    again = apply_module_spec_ui(client, spec, apply_views=False, apply_menus=False, apply_automations=False)
    assert again.access_rights_created == 0 or major < 20


@pytest.mark.parametrize("major", sorted(PORTS))
def test_stock_extension_custom_code_installs_on_a_test_copy(major: int, tmp_path) -> None:
    """Odoo.sh / self-host path: scaffold + test step only (fresh test database), never published."""
    import base64
    import io
    import subprocess
    import zipfile

    from app.code_studio_service import export_option_a_zip, stock_extension_scaffold
    from app.routers.code_studio import _model_depends

    client = _client(major)
    code = stock_extension_scaffold(model="res.partner", kind="selection_options", field_name="type",
                                    options=[{"value": "branch", "label": "Branch"}])
    pkg = export_option_a_zip(name="Contact extension", model="res.partner", code=code,
                              technical_name="res_partner_extension", depends=_model_depends(client, "res.partner"),
                              as_extension=True, odoo_major=major)
    zipfile.ZipFile(io.BytesIO(base64.b64decode(pkg["content_base64"]))).extractall(tmp_path)
    svc = ["docker", "compose", "-p", "ingenium-live-test", "-f", os.path.join(os.path.dirname(__file__), "odoo_live", "docker-compose.yml")]
    cid = subprocess.run([*svc, "ps", "-q", f"odoo{major}"], capture_output=True, text=True, check=True).stdout.strip()
    assert cid, f"odoo{major} container not running"
    subprocess.run(["docker", "exec", "-u", "root", cid, "rm", "-rf", "/mnt/extra-addons/res_partner_extension"], check=True)
    subprocess.run(["docker", "cp", str(tmp_path / "res_partner_extension"), f"{cid}:/mnt/extra-addons/"], check=True)
    db = f"testcopy{major}_{int(time.time())}"
    run = subprocess.run(["docker", "exec", cid, "odoo", "--db_host", "db", "-r", "odoo", "-w", "odoo", "-d", db,
                          "-i", "res_partner_extension", "--without-demo=all", "--stop-after-init", "--no-http",
                          "--addons-path=/mnt/extra-addons," + ("/usr/lib/python3/dist-packages/odoo/addons")],
                         capture_output=True, text=True, timeout=600)
    log = run.stdout + run.stderr
    assert run.returncode == 0, log[-2000:]
    assert " ERROR " not in log and "CRITICAL" not in log, log[-2000:]
    assert "res_partner_extension" in log
