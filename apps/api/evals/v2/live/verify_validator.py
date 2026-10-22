"""Live-verify stage-2 admission on local Odoo 17/18/19/20 (read-only: snapshot + validate, no writes)."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from odoo_client import ConnectionConfig, OdooClient
from app.odoo_snapshot import get_snapshot, clear_snapshot_cache
from app.design_admission import _admit

TARGETS = {17: ("http://127.0.0.1:8071", "odoo17_dev"), 18: ("http://127.0.0.1:8070", "odoo18_dev"),
           19: ("http://127.0.0.1:8069", "odoo_dev"), 20: ("http://127.0.0.1:8073", "sandbox_test")}
GOOD = {"app_name": "Cake Orders", "new_models": [{"name": "x_cake_order", "fields": [
            {"name": "x_customer_id", "ttype": "many2one", "relation": "res.partner"},
            {"name": "x_pickup_date", "ttype": "date"}, {"name": "x_deposit_paid", "ttype": "boolean"}]}],
        "stock_extensions": [], "automations": []}
BAD = {"app_name": "Bad", "new_models": [{"name": "x_bad", "fields": [
            {"name": "x_thing_id", "ttype": "many2one", "relation": "x_does_not_exist"}]}],
       "stock_extensions": [{"model": "no.such.model", "fields": []},
                            {"model": "res.partner", "fields": [{"name": "name", "ttype": "integer"}]}],
       "automations": [{"label": "Chase", "target_model": "x_bad", "requirement_id": "R1",
                        "automation": {"when": "on_time", "action": "activity", "date_field": "x_missing"}}]}
out = {}
for major, (url, db) in TARGETS.items():
    try:
        c = OdooClient(ConnectionConfig(url=url, db=db, username="admin", password=os.environ.get("ODOO_PASSWORD", "admin"))); c.connect()
        call = lambda m, meth, a, k, c=c: c.execute_kw(m, meth, a, k)
        clear_snapshot_cache(f"v{major}")
        snap = get_snapshot(call, f"v{major}", "", ["res.partner"], ttl=0.0)
        g, b = _admit(GOOD, snap, None), _admit(BAD, snap, None)
        out[major] = {"snap_major": snap.major, "good_ok": g.ok, "good_errors": [e.code for e in g.errors],
                      "bad_ok": b.ok, "bad_errors": sorted({e.code for e in b.errors})}
    except Exception as exc:  # noqa: BLE001
        out[major] = {"error": str(exc)[:200]}
print(json.dumps(out, indent=1))
