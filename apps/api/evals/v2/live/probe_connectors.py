"""Read-only: which payment/SMS/delivery/WhatsApp connectors and webhook automations exist per version."""
import os, sys, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from odoo_client import ConnectionConfig, OdooClient
from verify_validator import TARGETS  # noqa: E402

PATTERNS = ["payment_%", "sms%", "delivery_%", "%whatsapp%", "base_automation", "iap%"]
out = {}
for major, (url, db) in TARGETS.items():
    for attempt in range(20):
        try:
            c = OdooClient(ConnectionConfig(url=url, db=db, username="admin", password=os.environ.get("ODOO_PASSWORD", "admin"))); c.connect()
            break
        except Exception as exc:  # noqa: BLE001
            err = str(exc)[:120]; time.sleep(6)
    else:
        out[major] = {"error": err}; continue
    mods = {}
    for p in PATTERNS:
        for r in c.execute_kw("ir.module.module", "search_read", [[["name", "=like", p]]], {"fields": ["name", "state"]}):
            mods[r["name"]] = r["state"]
    fs = c.execute_kw("ir.actions.server", "fields_get", [["state"]], {"attributes": ["selection"]})
    states = [s[0] for s in fs.get("state", {}).get("selection", [])]
    prov = []
    if "payment.provider" in {m["model"] for m in c.execute_kw("ir.model", "search_read", [[["model", "=", "payment.provider"]]], {"fields": ["model"]})}:
        prov = [r["code"] for r in c.execute_kw("payment.provider", "search_read", [[]], {"fields": ["code"]})]
    out[major] = {"server_action_states": states, "modules": mods, "payment_provider_codes": sorted(set(prov))}
print(json.dumps(out, indent=1))
