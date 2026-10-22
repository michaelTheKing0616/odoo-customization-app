"""Configuration Suite stage 2: Change records (5 tools), Upkeep, After an upgrade, Ask validator."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import dry_run_ledger as ledger
from app import suite_ask as sa
from app import suite_upkeep as su
from app import view_engine_store as vs
from app.mutation_lock import reset_mutation_locks_for_tests
from app.routers import suite as rs
from app.routers import suite_change as rsc
from app.routers import suite_upkeep as rsu


class MemStore:
    def __init__(self) -> None:
        self.seen: set[str] = set()

    def remember(self, digest: str, *, now: Any = None) -> None:
        self.seen.add(digest)

    def contains(self, digest: str, *, now: Any = None) -> bool:
        return digest in self.seen


def _match(rec: dict[str, Any], dom: list[Any]) -> bool:
    for t in dom:
        if not isinstance(t, list | tuple):
            continue
        f, op, v = t
        cur = rec.get(f)
        cur = cur[0] if isinstance(cur, list) and len(cur) == 2 and isinstance(cur[0], int) else cur
        if op == "=":
            ok = cur == v or (v is False and not cur)
        elif op == "!=":
            ok = cur != v
        elif op == "in":
            ok = cur in v
        elif op == "not in":
            ok = cur not in v
        elif op == "=ilike":
            ok = str(cur or "").lower() == str(v).lower()
        else:
            ok = str(cur or "").startswith(str(v).rstrip("%"))
        if not ok:
            return False
    return True


class Fake:
    def __init__(self) -> None:
        self.t: dict[str, dict[int, dict[str, Any]]] = {}
        self.n = 1000
        self.capabilities = type("C", (), {"major": 19})()
        self.meta: dict[str, dict[str, Any]] = {
            "sale.order": {"state": {"type": "selection", "selection": [["draft", "Q"], ["sent", "S"], ["sale", "O"]], "store": True},
                           "payment_term_id": {"type": "many2one", "relation": "account.payment.term", "store": True, "string": "Payment Terms"},
                           "amount_total": {"type": "monetary", "readonly": True, "store": True, "string": "Total"}, "display_name": {"type": "char", "store": False}},
            "res.partner": {"name": {"type": "char", "store": True}, "email": {"type": "char", "store": True}, "active": {"type": "boolean", "store": True},
                            "user_ids": {"type": "one2many", "store": True}, "display_name": {"type": "char", "store": False}},
            "crm.lead": {"name": {"type": "char", "store": True}, "activity_ids": {"type": "one2many", "store": True}, "display_name": {"type": "char", "store": False}},
            "account.move": {"name": {"type": "char", "store": True}},
        }

    def add(self, _model: str, /, **vals: Any) -> int:
        self.n += 1
        self.t.setdefault(_model, {})[self.n] = {"id": self.n, "display_name": vals.get("name", f"#{self.n}"), "active": True, **vals}
        return self.n

    def execute_kw(self, model: str, method: str, args: list[Any], kw: dict[str, Any]) -> Any:
        tab = self.t.setdefault(model, {})
        if method == "fields_get":
            return self.meta.get(model, {})
        if method in ("search", "search_read", "search_count"):
            dom = args[0] if args else []
            act = (kw.get("context") or {}).get("active_test", True) and not any(isinstance(x, list | tuple) and x[0] == "active" for x in dom)
            rows = [r for r in tab.values() if _match(r, dom) and (not act or r.get("active", True))]
            if method == "search":
                return [r["id"] for r in rows]
            if method == "search_count":
                return len(rows)
            return [dict(r) for r in rows]
        if method == "read":
            return [dict(tab[i]) for i in args[0] if i in tab]
        if method == "write":
            for i in args[0]:
                tab[i].update(args[1])
            return True
        if method == "create":
            return self.add(model, **args[0])
        if method == "unlink":
            for i in args[0]:
                tab.pop(i, None)
            return True
        if method == "action_confirm":
            for i in args[0]:
                tab[i]["state"] = "sale"
            return True
        if method == "action_grant_access":
            for i in args[0]:
                pid = tab[i]["partner_id"]
                self.add("res.users", partner_id=pid, login=self.t["res.partner"][pid]["email"], share=True, group_ids=[7])
            return True
        if model == "portal.wizard" and method == "create":
            return self.add(model)
        raise AssertionError(f"unexpected {model}.{method}")


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine("sqlite://")
    db = sessionmaker(bind=engine)()
    vs._ensure_tables(db)
    ledger.bind_store(MemStore())
    reset_mutation_locks_for_tests()
    odoo = Fake()
    for mod in (rs, rsc, rsu):
        monkeypatch.setattr(mod, "_client", lambda cid, db: odoo)
    monkeypatch.setattr(rsc, "RUN_INLINE", True)
    odoo.add("ir.module.module", name="mail", state="installed")
    odoo.add("ir.model", model="sale.order", name="Sales Order")
    odoo.add("ir.model", model="crm.lead", name="Lead")
    odoo.add("ir.model", model="res.partner", name="Contact")
    return db, odoo


def _batch(db: Any, **kw: Any) -> str:
    return rsc.batch_create("c1", rsc.BatchBody(**kw), None, db)["id"]


def test_confirm_17_ready_3_blocked_with_odoos_reason_then_run(env) -> None:
    db, o = env
    ids = [o.add("sale.order", name=f"S{i}", state="draft") for i in range(17)]
    ids += [o.add("sale.order", name=f"X{i}", state="sale") for i in range(3)]
    bid = _batch(db, tool="transitions", model="sale.order", ids=ids, change={"button": "confirm"})
    with pytest.raises(HTTPException) as e:
        rsc.batch_run("c1", bid, None, db)
    assert e.value.status_code == 428
    ck = rsc.batch_check("c1", bid, db)
    assert ck["counts"]["ready"] == 17 and ck["counts"]["blocked"] == 3
    assert {r["reason"] for r in ck["records"] if r["verdict"] == "blocked"} == {"Some orders are not in a state requiring confirmation."}
    run = rsc.change_run_get("c1", rsc.batch_run("c1", bid, None, db)["id"], db)["payload"]
    assert run["counts"]["done"] == 17 and sum(1 for r in o.t["sale.order"].values() if r["state"] == "sale") == 20
    with pytest.raises(HTTPException) as e:
        rsc.change_run_undo("c1", run["records"] and rsc.change_runs("c1", db)["runs"][0]["id"], None, db)
    assert e.value.status_code == 409


def test_mass_edit_payment_terms_then_undo_restores_exact_old_values(env) -> None:
    db, o = env
    t1, t2 = o.add("account.payment.term", name="Immediate"), o.add("account.payment.term", name="30 Days")
    ids = [o.add("sale.order", name=f"S{i}", state="draft", payment_term_id=[t1 if i % 2 else False, "x"] if i % 2 else False) for i in range(30)]
    before = {i: o.t["sale.order"][i]["payment_term_id"] for i in ids}
    bid = _batch(db, tool="edit", model="sale.order", ids=ids, change={"field": "payment_term_id", "value": {"ref": "30 Days"}})
    assert rsc.batch_check("c1", bid, db)["counts"]["ready"] == 30
    run_id = rsc.batch_run("c1", bid, None, db)["id"]
    assert all(o.t["sale.order"][i]["payment_term_id"] == t2 for i in ids)
    rsc.change_run_undo("c1", run_id, None, db)
    norm = {i: (v[0] if isinstance(v, list) else v) for i, v in before.items()}
    assert {i: o.t["sale.order"][i]["payment_term_id"] for i in ids} == norm


def test_money_guard_refuses_invoice_edit_and_readonly_fields(env) -> None:
    db, o = env
    bid = _batch(db, tool="edit", model="account.move", ids=[1], change={"field": "name", "value": "x"})
    ck = rsc.batch_check("c1", bid, db)
    assert ck["refused"].startswith("Refused by the money guard") and "Accounting" in ck["refused"] and not ck["receipt"]
    bid = _batch(db, tool="edit", model="sale.order", ids=[1], change={"field": "amount_total", "value": 1})
    assert "can't be edited" in rsc.batch_check("c1", bid, db)["refused"]
    bid = _batch(db, tool="transitions", model="account.move", ids=[1], change={"button": "post"})
    assert "reason" in rsc.batch_check("c1", bid, db)["refused"]


def test_activities_split_13_12_with_words(env) -> None:
    db, o = env
    u1, u2 = o.add("res.users", name="A", share=False), o.add("res.users", name="B", share=False)
    ids = [o.add("crm.lead", name=f"L{i}") for i in range(25)]
    bid = _batch(db, tool="activities", model="crm.lead", ids=ids, change={"user_ids": [u1, u2], "due": {"mode": "spread", "days": 5}, "summary": "Call"})
    ck = rsc.batch_check("c1", bid, db)
    split = [sum(1 for r in ck["records"] if r["user_id"] == u) for u in (u1, u2)]
    assert split == [13, 12] and "working days" in " ".join(ck["also"])
    run_id = rsc.batch_run("c1", bid, None, db)["id"]
    assert len(o.t["mail.activity"]) == 25
    rsc.change_run_undo("c1", run_id, None, db)
    assert not o.t["mail.activity"]


def test_portal_8_ready_2_blocked_with_fix(env) -> None:
    db, o = env
    o.add("ir.model.data", module="base", name="group_portal", res_id=7)
    ids = [o.add("res.partner", name=f"P{i}", email=(f"p{i}@x.test" if i < 8 else ""), user_ids=[]) for i in range(10)]
    bid = _batch(db, tool="portal", model="res.partner", ids=ids, change={"action": "grant"})
    ck = rsc.batch_check("c1", bid, db)
    assert ck["counts"]["ready"] == 8 and ck["counts"]["blocked"] == 2
    assert all(r.get("fix") for r in ck["records"] if r["verdict"] == "blocked")
    assert ck["limits"]["pace_ms"] >= 1000


def test_merge_moves_links_archives_and_undo_unarchives(env, monkeypatch) -> None:
    db, o = env
    a = o.add("res.partner", name="Ada Obi", email="ada@x.test")
    b = o.add("res.partner", name="Ada  Obi", email="ada@x.test")
    so = o.add("sale.order", name="S1", state="draft", partner_id=[b, "Ada"])
    msg = o.add("mail.message", model="res.partner", res_id=b)
    o.add("ir.model.fields", model="sale.order", name="partner_id", ttype="many2one", relation="res.partner", store=True, readonly=False)
    groups = rsc.duplicates_scan("c1", rsc.ScanBody(model="res.partner", fields=["email", "name"]), db)["groups"]
    assert groups and groups[0]["strength"] == "Strong" and groups[0]["ids"] == [a, b]
    bid = _batch(db, tool="duplicates", model="res.partner", change={"groups": [{"keep": a, "merge": [b]}]})
    assert rsc.batch_check("c1", bid, db)["counts"]["ready"] == 1
    run_id = rsc.batch_run("c1", bid, None, db)["id"]
    assert o.t["sale.order"][so]["partner_id"] == a and o.t["mail.message"][msg]["res_id"] == a and o.t["res.partner"][b]["active"] is False
    rsc.change_run_undo("c1", run_id, None, db)
    assert o.t["res.partner"][b]["active"] is True and o.t["sale.order"][so]["partner_id"] == b and o.t["mail.message"][msg]["res_id"] == b


def test_merge_refused_when_invoices_point_at_contact(env) -> None:
    db, o = env
    a, b = o.add("res.partner", name="A", email="a@x.test"), o.add("res.partner", name="A", email="a@x.test")
    o.add("account.move", name="INV1", partner_id=[b, "A"])
    bid = _batch(db, tool="duplicates", model="res.partner", change={"groups": [{"keep": a, "merge": [b]}]})
    rec = rsc.batch_check("c1", bid, db)["records"][0]
    assert rec["verdict"] == "blocked" and "money guard" in rec["reason"]


def test_cron_sentences_never_show_method_names() -> None:
    assert su.validate_cron_sentence("Calls model._run_queue() daily", "every day", "Mail") == "Runs every day on Mail."
    assert su.validate_cron_sentence("Sends reminders.", "every day", "Event") == "Sends reminders."
    assert su.how_often(1, "days") == "every day" and su.how_often(5, "minutes") == "every 5 minutes"
    for _k, text in su.KNOWN_CRONS:
        assert not su.CODE_LIKE.search(text), text
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert len(su.timeline("2026-01-01 00:30:00", 1, "hours", now=now)) == 24


def test_schedules_pause_records_who_when_why_and_resume(env) -> None:
    db, o = env
    o.meta["ir.cron"] = {f: {"type": "char"} for f in ("cron_name", "model_id", "interval_number", "interval_type", "nextcall", "lastcall", "active")}
    cid = o.add("ir.cron", cron_name="Mail: Email Queue Manager", model_id=[1, "Email"], interval_number=1, interval_type="hours", nextcall="2026-01-01 00:00:00")
    o.add("ir.cron", cron_name="Custom: x_do_thing", model_id=[2, "Contact"], interval_number=2, interval_type="days", nextcall="2026-01-01 00:00:00")
    out = rsu.schedules("c1", db)["schedules"]
    assert out[0]["description"].startswith("Sends the emails") and out[1]["description"] == "Runs every 2 days on Contact."
    assert not any("_" in s["description"] or "(" in s["description"] for s in out)
    p = rsu.schedule_pause("c1", cid, rsu.PauseBody(reason="Mail server moving"), None, db)["paused"]
    assert p["reason"] == "Mail server moving" and p["at"] and o.t["ir.cron"][cid]["active"] is False
    assert rsu.schedules("c1", db)["schedules"][0]["paused"]["reason"] == "Mail server moving"
    rsu.schedule_resume("c1", cid, None, db)
    assert o.t["ir.cron"][cid]["active"] is True


def test_files_space_is_measured_and_accounting_files_never_offered() -> None:
    rows = [{"id": 1, "name": "a.txt", "file_size": 100, "checksum": "A", "type": "binary"},
            {"id": 2, "name": "b.pdf", "file_size": 50, "checksum": "B", "res_model": "res.partner", "res_id": 3, "type": "binary"},
            {"id": 3, "name": "b.pdf", "file_size": 50, "checksum": "B", "res_model": "res.partner", "res_id": 3, "type": "binary"},
            {"id": 4, "name": "inv.pdf", "file_size": 70, "checksum": "C", "res_model": "account.move", "res_id": 9, "type": "binary"},
            {"id": 5, "name": "inv.pdf", "file_size": 70, "checksum": "C", "res_model": "account.move", "res_id": 9, "type": "binary"}]
    scan = su.file_scan(rows)
    assert [u["id"] for u in scan["unattached"]] == [1] and scan["repeats"][0]["copies"] == [3] and len(scan["repeats"]) == 1
    assert scan["stored_bytes"] == 220 and scan["accounting_excluded"] == 2
    assert su.space_freed(rows, {1, 3}) == 100 and su.space_freed(rows, {2, 3}) == 50
    v = {x["id"]: x["verdict"] for x in su.file_verdicts(rows, [1, 3, 4, 2])}
    assert v == {1: "ready", 3: "ready", 4: "blocked", 2: "blocked"}


def test_upgrade_flags_list_tag_and_fix_resolves() -> None:
    arch = '<xpath expr="//tree/field[@name=\'name\']" position="after"><field name="email"/></xpath>'
    row = su.upgrade_matrix([{"id": 1, "name": "ingenium_x", "model": "res.partner", "type": "tree", "arch": arch}], 18)[0]
    assert row["flags"][0]["key"] == "list_tag" and "//list" in row["fixed_arch"]
    ok, missing = su.xpaths_resolve(row["fixed_arch"], '<list><field name="name"/></list>')
    assert ok and not missing
    assert su.upgrade_matrix([{"id": 1, "name": "x", "model": "m", "type": "tree", "arch": arch}], 17)[0]["status"] == "ok"


def _pk() -> dict[str, Any]:
    return {"record_types": [{"model": "sale.order", "label": "Sales Order", "buttons": [{"key": "confirm", "label": "Confirm"}],
                              "fields": [{"name": "payment_term_id", "label": "Payment Terms", "type": "many2one", "choices": []},
                                         {"name": "state", "label": "Status", "type": "selection", "choices": ["draft", "sent", "sale"]}]}]}


def test_ask_money_routes_and_validator_drops_unknown_names() -> None:
    assert "Accounting > Configuration > Taxes" in sa.money_route_for("change the VAT rate to 7.5%")
    res = sa.validate_plan({"record_type": "sale.order", "filters": [["x_injected", "=", 1], ["state", "=", "draft"]], "change": {"button": "confirm"}}, _pk())
    assert res["plan"]["filters"] == [["state", "=", "draft"]] and res["dropped"]
    res = sa.validate_plan({"record_type": "sale.order", "filters": [], "change": {"field": "x_discount_level", "value": 3}}, _pk())
    assert res["plan"] is None and "no field called" in res["unclear"]
    assert sa.validate_plan({"record_type": "x.secret", "change": {"button": "confirm"}}, _pk())["plan"] is None
    plan = sa.validate_plan(sa.read_request("set payment terms to 30 Days on quotations", _pk()), _pk())["plan"]
    assert plan["change"] == {"tool": "edit", "field": "payment_term_id", "value": {"ref": "30 Days"}}
    assert sa.validate_plan(sa.read_request("set warp speed to 9 on quotations", _pk()), _pk())["plan"] is None


def test_guide_is_grounded_in_facts() -> None:
    g = sa.guide("costing", [{"id": "posted_entries", "value": 3}])
    assert g["decided"] and not g["options"]
    g = sa.guide("delivery_steps", [{"id": "stock_installed", "value": True}])
    assert len(g["options"]) <= 4
    assert sa.validate_guide({"options": [{"label": "x", "reversible": "maybe"}]}, set()) is None


def _docx(rows: list[list[str]]) -> bytes:
    import io
    import zipfile

    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    cells = "".join("<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in r) + "</w:tr>" for r in rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:body><w:tbl>{cells}</w:tbl></w:body></w:document>')
    return buf.getvalue()


def test_import_reads_paste_markdown_csv_and_word() -> None:
    from app import suite_import as si

    t, _ = si.read_document(text="Name\tEmail\nAda\tada@x.test\nBo\tbo@x.test")
    assert t[0]["headers"] == ["Name", "Email"] and len(t[0]["rows"]) == 2
    t, _ = si.read_document(text="| Name | City |\n|---|---|\n| Ada | Lagos |")
    assert t[0]["rows"] == [["Ada", "Lagos"]]
    t, _ = si.read_document("c.csv", b"Name,Email\nAda,ada@x.test\n")
    assert t[0]["rows"] == [["Ada", "ada@x.test"]]
    t, _ = si.read_document("d.docx", _docx([["Name", "Phone"], ["Ada", "123"]]))
    assert t[0]["headers"] == ["Name", "Phone"] and t[0]["rows"] == [["Ada", "123"]]
    t, notes = si.read_document(text="just a sentence")
    assert not t and notes


def test_import_maps_by_code_and_asks_about_unknown_columns() -> None:
    from app import suite_import as si

    fm = {"name": {"type": "char", "string": "Name", "required": True}, "email": {"type": "char", "string": "Email"},
          "child_ids": {"type": "one2many", "string": "Contacts"}, "credit": {"type": "monetary", "string": "Credit", "readonly": True}}
    mapping, qs = si.map_columns(["Name", "E-mail", "Favourite colour", "Credit"], fm)
    assert mapping["Name"] == "name" and mapping["E-mail"] == "email"
    assert {q["column"] for q in qs} == {"Favourite colour", "Credit"}
    assert si.required_missing({"Email": "email"}, fm) == ["Name"]


class ImportOdoo:
    def __init__(self, errors: bool = False) -> None:
        self.errors, self.calls, self.made = errors, [], {}

    def execute_kw(self, model: str, method: str, args: list[Any], kw: dict[str, Any]) -> Any:
        self.calls.append((model, method, kw.get("dryrun")))
        if model == "base_import.import" and method == "create":
            return 1
        if method == "execute_import":
            if self.errors:
                return {"messages": [{"type": "error", "message": "Missing required value for the field 'Name'", "rows": {"from": 1, "to": 1}}], "ids": False}
            if kw.get("dryrun"):
                return {"messages": [], "ids": [1, 2]}
            self.made = {f"r{i}": 50 + i for i in range(2)}
            return {"messages": [], "ids": list(self.made.values())}
        if model == "ir.model.data":
            return [{"res_id": v} for v in self.made.values()]
        if method == "search":
            return list(self.made.values())
        if method == "unlink":
            self.made = {}
            return True
        raise AssertionError((model, method))


def test_import_step_check_is_dry_run_apply_uses_external_ids_undo_removes() -> None:
    from app import suite_import as si
    from app import suite_setup as ss

    fm = {"name": {"type": "char", "string": "Name"}}
    step = {"id": "i", "type": "import", "inputs": {"model": "res.partner", "headers": ["Name"], "rows": [["A"], ["B"]], "mapping": {"Name": "name"},
                                                    "job": "j1", "table": 1}}
    o = ImportOdoo()
    ck = si.check_import(o, step, fm)
    assert ck["verdict"] == "ready" and all(c[2] is True for c in o.calls if c[1] == "execute_import")
    res = si.apply_import(o, step)
    assert res["undo"]["xmlids"] == ["__ingenium_import__.j1_1_1", "__ingenium_import__.j1_1_2"]
    undo, cannot = ss.undo_steps([step], {"waves": [{"steps": [{"id": "i", "state": "done", "undo": res["undo"]}]}]})
    assert undo[0]["type"] == "remove" and undo[0]["inputs"]["xmlids"] and not cannot
    assert si.remove_imported(o, "res.partner", res["undo"]["xmlids"])["state"] == "done" and not o.made
    assert si.check_import(ImportOdoo(errors=True), step, fm)["verdict"] == "needs_input"
    bad = {**step, "inputs": {**step["inputs"], "mapping": {"Name": None}}}
    assert si.check_import(o, bad, fm)["verdict"] == "needs_input"
    assert ss.money_guard({"type": "import", "inputs": {"model": "account.move"}}, posted_entries=0, done_moves=0)


def test_record_editor_rules_and_plan(env, monkeypatch) -> None:
    from app import suite_records as sr
    from app.routers import suite_records as rsr

    db, o = env
    monkeypatch.setattr(rsr, "_client", lambda cid, db: o)
    monkeypatch.setattr(rs, "_row", lambda db, cid: type("Row", (), {"url": "http://x", "db_name": "d", "server_version": "19.0"})())
    o.meta["res.partner"].update({"comment": {"type": "text", "store": True, "string": "Notes"},
                                  "country_id": {"type": "many2one", "relation": "res.country", "store": True, "string": "Country"},
                                  "credit": {"type": "monetary", "readonly": True, "store": True, "string": "Credit"},
                                  "name": {"type": "char", "store": True, "string": "Name", "required": True}})
    assert sr.validate_edit(o.meta["res.partner"], "res.partner", "credit", 5)[1]
    assert "needs a value" in sr.validate_edit(o.meta["res.partner"], "res.partner", "name", "")[1]
    assert sr.validate_edit(o.meta["res.partner"], "res.partner", "country_id", "Nigeria")[0] == {"ref": "Nigeria"}
    assert "Journal entries are view only" in sr.validate_edit({}, "account.move", "ref", "x")[1]
    rows = [{"id": 1, "comment": "Call Lagos office"}, {"id": 2, "comment": "lagos"}, {"id": 3, "comment": None}]
    assert [e["value"] for e in sr.replace_edits(rows, "comment", "lagos", "Abuja")] == ["Call Abuja office", "Abuja"]
    a, b = o.add("res.partner", name="A"), o.add("res.partner", name="B")
    o.execute_kw = (lambda orig: (lambda m, meth, args, kw: True if meth in ("has_access", "check_access_rights") else orig(m, meth, args, kw)))(o.execute_kw)
    out = rsr.records_plan("c1", "res.partner", rsr.StageBody(edits=[rsr.Edit(id=a, field="comment", value="x"), rsr.Edit(id=a, field="name", value="A2"),
                                                                     rsr.Edit(id=b, field="credit", value=1)]), None, db)
    steps = out["plan"]["payload"]["steps"]
    assert len(steps) == 1 and steps[0]["inputs"]["values"] == {"comment": "x", "name": "A2"} and out["refused"][0]["field"] == "credit"
    with pytest.raises(HTTPException) as e:
        rsr.records_plan("c1", "account.move", rsr.StageBody(edits=[rsr.Edit(id=1, field="ref", value="x")]), None, db)
    assert e.value.status_code == 403


def test_record_replace_html_keeps_tags():
    from app import suite_records as sr
    out = sr.replace_edits([{"id": 1, "c": "<p class=\"p\">Lagos p</p>"}], "c", "p", "Q", html=True)
    assert out[0]["value"] == "<p class=\"p\">Lagos Q</p>"
    assert sr.replace_edits([{"id": 2, "c": "a\\1"}], "c", "a", "\\g<0>")[0]["value"] == "\\g<0>\\1"


def test_steps_carry_changeset_op():
    from app import suite_setup as ss
    assert ss.changeset_op({"type": "install", "inputs": {}}) == ("module.install", "R3")
    assert ss.changeset_op({"type": "update", "inputs": {}}) == ("data.update_batch", "R2")
