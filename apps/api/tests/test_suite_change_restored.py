"""Restored bulk tools in Change records: security, message, recompute (money guard + undo)."""
from app import suite_change as sc


class Fake:
    def __init__(self):
        self.groups = {5: [1, 2], 6: [1]}
        self.writes, self.msgs = [], {}
        self.xml = {("res.groups", 1): "base.group_user", ("res.groups", 2): "sales_team.group_sale_salesman",
                    ("res.groups", 9): "account.group_account_manager", ("res.users", 2): "base.user_admin"}
        self.total = {7: 10}

    def execute_kw(self, model, method, args, kw):
        if model == "ir.model.fields":
            return [1]  # group_ids exists
        if model == "ir.model.data":
            dom = dict((d[0], d[2]) for d in args[0])
            if "res_id" in dom:
                return [{"module": v.split(".")[0], "name": v.split(".")[1], "res_id": i} for (m, i), v in self.xml.items() if m == dom["model"] and i in dom["res_id"]]
            return [{"res_id": i} for (m, i), v in self.xml.items() if v == f"{dom['module']}.{dom['name']}"]
        if model == "res.users" and method == "read":
            return [{"id": i, "display_name": f"U{i}", "share": False, "group_ids": list(self.groups.get(i, []))} for i in args[0]]
        if model == "res.users" and method == "write":
            self.groups[args[0][0]] = list(args[1]["group_ids"][0][2]); return True
        if method == "message_post":
            mid = 100 + len(self.msgs); self.msgs[mid] = kw["body"]; return mid
        if model == "mail.message" and method == "search":
            return [args[0][0][2]] if args[0][0][2] in self.msgs else []
        if model == "mail.message" and method == "unlink":
            self.msgs.pop(args[0][0]); return True
        if method == "fields_get" and model == "res.users":
            return {"group_ids": {"type": "many2many"}}
        if method == "fields_get":
            return {"amount_total": {"depends": ["order_line.price_total", "partner_id"]}, "order_line": {"type": "one2many", "store": True},
                    "partner_id": {"type": "many2one", "store": True, "readonly": False}}
        if method == "read":
            return [{"id": i, "display_name": f"R{i}", "amount_total": self.total.get(i, 0), "partner_id": [3, "P"]} for i in args[0]]
        if method == "write":
            self.writes.append((args, kw)); self.total[args[0][0]] = 12; return True
        raise AssertionError((model, method))


FM_USERS = {"group_ids": {}, "display_name": {}}


def test_security_add_check_run_undo():
    c, b = Fake(), {"tool": "security", "model": "res.users", "change": {"add": ["sales_team.group_sale_salesman"]}}
    assert sc.refuse(b, FM_USERS) is None
    recs = {r["id"]: r for r in sc.check_records(c, b, FM_USERS, [5, 6, 2])}
    assert recs[5]["verdict"] == "no_change" and recs[6]["verdict"] == "ready" and recs[2]["verdict"] == "blocked"
    res = sc.run_record(c, b, FM_USERS, recs[6])
    assert c.groups[6] == [1, 2]
    assert sc.undo_record(c, b, {"id": 6, **res})["state"] == "done" and c.groups[6] == [1]


def test_security_money_guard_refuses_accounting_groups():
    c, b = Fake(), {"tool": "security", "model": "res.users", "change": {"add": [9]}}
    recs = sc.check_records(c, b, FM_USERS, [6])
    assert recs[0]["verdict"] == "blocked" and "money guard" in recs[0]["reason"]
    assert sc.refuse({**b, "model": "res.partner"}, {}) is not None


def test_message_note_escaped_and_undo_removes():
    c, b = Fake(), {"tool": "message", "model": "res.partner", "change": {"body": "Hi {name} <b>", "kind": "note"}}
    assert sc.refuse(b, {"message_ids": {}}) is None and sc.refuse(b, {}) is not None
    res = sc.run_record(c, b, {}, {"id": 4})
    assert c.msgs[100] == "Hi R4 &lt;b&gt;"
    assert sc.undo_record(c, b, {"id": 4, **res})["state"] == "done" and not c.msgs
    assert sc.refuse({**b, "model": "account.move"}, {"message_ids": {}}).startswith("Refused by the money guard")


def test_recompute_touches_plain_dependency_untracked():
    c, b = Fake(), {"tool": "recompute", "model": "sale.order", "change": {"field": "amount_total"}}
    fm = {"amount_total": {"readonly": True, "store": True}}
    assert sc.refuse(b, fm) is None and sc.refuse(b, {"amount_total": {"readonly": False}}) is not None
    rec = sc.check_records(c, b, fm, [7])[0]
    assert rec["verdict"] == "ready" and rec["dep"] == "partner_id"
    res = sc.run_record(c, b, fm, rec)
    assert c.writes[0][0][1] == {"partner_id": 3} and c.writes[0][1]["context"]["tracking_disable"]
    assert res["state"] == "done" and sc.undo_record(c, b, {"id": 7, **res})["state"] == "skipped"
    assert sc.refuse({**b, "model": "account.move"}, fm).startswith("Refused by the money guard")
