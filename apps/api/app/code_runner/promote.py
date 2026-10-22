"""Promote a runner script to a scheduled job, server action or Action-menu button (item 20).

Test-then-publish: "test" creates the Odoo record unpublished (cron inactive, action unbound) so Odoo
itself compiles and checks the code; "publish" switches it on; "remove" archives/deletes only what we made.
Odoo runs server-action code in its own sandbox with `env`, so the script's odoo.execute_kw calls are
translated by a small shim. Only methods the shim knows are allowed; code (not AI) refuses the rest.
"""

from __future__ import annotations

import ast
import re
import time
import uuid
from typing import Any

from app.code_runner import store

SHIM_METHODS = {"search", "search_read", "search_count", "read", "create", "write", "unlink", "action_archive",
                "action_unarchive", "read_group", "name_search", "fields_get", "copy", "default_get"}
SHIM = '''# --- Ingenium runner shim: odoo.execute_kw → env (generated, do not edit) ---
def _ek(m, meth, args=None, kw=None):
        args, kw, M = list(args or []), dict(kw or {}), env[m]
        if meth == "search":
            return M.search(args[0] if args else kw.pop("domain", []), **kw).ids
        if meth == "search_read":
            if len(args) > 1:
                kw["fields"] = args[1]
            return M.search_read(args[0] if args else kw.pop("domain", []), **kw)
        if meth == "search_count":
            return M.search_count(args[0] if args else [])
        if meth == "read":
            return M.browse(args[0]).read(args[1] if len(args) > 1 else kw.get("fields"))
        if meth == "create":
            r = M.create(args[0])
            return r.ids if isinstance(args[0], list) else r.id
        if meth == "write":
            return M.browse(args[0]).write(args[1])
        if meth == "unlink":
            return M.browse(args[0]).unlink()
        if meth == "action_archive":
            return M.browse(args[0]).action_archive()
        if meth == "action_unarchive":
            return M.browse(args[0]).action_unarchive()
        if meth == "read_group":
            return M.read_group(args[0], args[1], args[2], **kw)
        if meth == "name_search":
            return M.name_search(args[0] if args else kw.pop("name", ""), **kw)
        if meth == "fields_get":
            return M.fields_get(attributes=kw.get("attributes"))
        if meth == "copy":
            return M.browse(args[0]).copy(args[1] if len(args) > 1 else None).id
        if meth == "default_get":
            return M.default_get(args[0])
        raise UserError("Method not available here: %%s" %% meth)
def progress(done, total):
    pass
def result(rows):
    pass
params = %(params)s
resume_from = 0
done_ids = {}
# --- end shim ---
'''


class NotPromotable(Exception):
    pass


def check(code: str) -> list[str]:
    """Reasons this script can't run inside Odoo; empty when it can."""
    reasons: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"Line {exc.lineno}: not valid Python."]
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            reasons.append(f"Line {n.lineno}: imports aren't allowed inside Odoo. Use the built-in datetime/time names instead.")
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "execute_kw" and len(n.args) >= 2:
            m = n.args[1]
            if not (isinstance(m, ast.Constant) and m.value in SHIM_METHODS):
                reasons.append(f"Line {n.lineno}: '{getattr(m, 'value', '?')}' can't be called from a scheduled job or button yet.")
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "secret":
            reasons.append(f"Line {n.lineno}: vault secrets stay in Ingenium and can't be copied into Odoo.")
        if isinstance(n, (ast.ClassDef, ast.Lambda)):
            reasons.append(f"Line {n.lineno}: classes and lambdas aren't allowed in Odoo server code.")
    return reasons


class _ToShim(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> Any:
        self.generic_visit(node)
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "execute_kw" and isinstance(f.value, ast.Name) and f.value.id == "odoo":
            node.func = ast.copy_location(ast.Name(id="_ek", ctx=ast.Load()), f)
        return node


def server_code(code: str, params: dict[str, Any]) -> str:
    tree = ast.fix_missing_locations(_ToShim().visit(ast.parse(code)))
    return SHIM % {"params": repr(params or {})} + ast.unparse(tree) + "\n"


def _key(connection_id: str) -> str:
    return f"promo_{connection_id}"


def list_promotions(connection_id: str) -> list[dict[str, Any]]:
    return store.load("promotions", _key(connection_id), [])


def _save(connection_id: str, items: list[dict[str, Any]]) -> None:
    store.save("promotions", _key(connection_id), items)


def test(client: Any, connection_id: str, *, name: str, code: str, params: dict[str, Any], kind: str,
         model: str, interval: dict[str, Any] | None, by: str | None, receipt_id: str) -> dict[str, Any]:
    reasons = check(code)
    if reasons:
        raise NotPromotable(" ".join(reasons))
    model_rows = client.execute_kw("ir.model", "search_read", [[("model", "=", model)]], {"fields": ["id"], "limit": 1})
    if not model_rows:
        raise NotPromotable(f"There is no model '{model}' on this database.")
    model_id = model_rows[0]["id"]
    label = f"[Ingenium test] {name}"[:120]
    vals = {"name": label, "model_id": model_id, "state": "code", "code": server_code(code, params)}
    item = {"id": str(uuid.uuid4()), "name": name, "kind": kind, "model": model, "status": "testing", "by": by,
            "at": time.time(), "receipt_id": receipt_id, "interval": interval, "records": {}}
    if kind == "cron":
        iv = interval or {"number": 1, "type": "days"}
        cron_vals = {**vals, "interval_number": int(iv.get("number") or 1), "interval_type": iv.get("type") or "days", "active": False}
        cid = client.execute_kw("ir.cron", "create", [cron_vals])
        cid = cid[0] if isinstance(cid, list) else cid
        item["records"]["ir.cron"] = cid
    else:
        aid = client.execute_kw("ir.actions.server", "create", [vals])  # Odoo compiles the code here
        aid = aid[0] if isinstance(aid, list) else aid
        item["records"]["ir.actions.server"] = aid
    items = list_promotions(connection_id) + [item]
    _save(connection_id, items)
    return item


def _get(connection_id: str, pid: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items = list_promotions(connection_id)
    item = next((i for i in items if i["id"] == pid), None)
    if item is None:
        raise NotPromotable("No such promotion.")
    return items, item


def run_once(client: Any, connection_id: str, pid: str) -> dict[str, Any]:
    """Run the tested record once now (a real run: only after the script's own real-run gates)."""
    items, item = _get(connection_id, pid)
    if "ir.cron" in item["records"]:
        client.execute_kw("ir.cron", "method_direct_trigger", [[item["records"]["ir.cron"]]])
    else:
        client.execute_kw("ir.actions.server", "run", [[item["records"]["ir.actions.server"]]])
    item["last_run"] = time.time()
    _save(connection_id, items)
    return item


def publish(client: Any, connection_id: str, pid: str, *, by: str | None) -> dict[str, Any]:
    items, item = _get(connection_id, pid)
    if item["status"] != "testing":
        raise NotPromotable("Only a tested promotion can be published.")
    name = item["name"][:120]
    if "ir.cron" in item["records"]:
        client.execute_kw("ir.cron", "write", [[item["records"]["ir.cron"]], {"active": True, "name": name}])
    else:
        aid = item["records"]["ir.actions.server"]
        vals: dict[str, Any] = {"name": name}
        if item["kind"] == "button":
            mid = client.execute_kw("ir.model", "search", [[("model", "=", item["model"])]], {"limit": 1})
            vals.update(binding_model_id=mid[0], binding_type="action")
        client.execute_kw("ir.actions.server", "write", [[aid], vals])
    item.update(status="published", published_by=by, published_at=time.time())
    _save(connection_id, items)
    return item


def remove(client: Any, connection_id: str, pid: str) -> dict[str, Any]:
    """Undo a promotion: delete only the records Ingenium created."""
    items, item = _get(connection_id, pid)
    for model, rid in item["records"].items():
        try:
            client.execute_kw(model, "unlink", [[rid]])
        except Exception:  # noqa: BLE001 — already gone in Odoo
            pass
    item["status"] = "removed"
    item["removed_at"] = time.time()
    _save(connection_id, items)
    return item


def safe_name(s: str) -> str:
    return re.sub(r"[^\w .-]", "", s)[:120]
