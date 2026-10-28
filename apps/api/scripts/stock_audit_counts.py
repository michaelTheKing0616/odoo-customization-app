"""CODE-AUDIT-11 M5: reproducible stock-Odoo audit counts.

Command (from apps/api):
    STOCK_ODOO_ADDONS=/path/to/odoo/addons PYTHONPATH=.:../../packages/module-generator/src \
        python scripts/stock_audit_counts.py [out.json]

Prints the exact source tree (path, git commit, odoo/release.py version), then for each rule
set (version=17, version=19) and each of the 19 modules: HIGH / MEDIUM / *-unaudited counts.
Exits non-zero when any module errors or has an *-unaudited finding (the same gate as
tests/test_nf_bot_code_audit_stock_gate.py, run with INGENIUM_STOCK_AUDIT=1)."""
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.bots import code_audit as ca  # noqa: E402

MODS = ["mail", "sale", "crm", "hr", "website_sale", "mrp", "account", "stock", "web", "portal", "auth_signup", "website",
        # CA12: product (M2/M3 false alarms) + 6 more stock modules
        "product", "purchase", "project", "point_of_sale", "hr_expense", "event", "survey"]


def main() -> int:
    root = Path(os.environ.get("STOCK_ODOO_ADDONS", "")).expanduser()
    if not (root / "web" / "__manifest__.py").is_file():
        print("set STOCK_ODOO_ADDONS to an odoo/addons directory", file=sys.stderr)
        return 2
    src = root.resolve().parent
    rev = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "?"
    dirty = subprocess.run(["git", "-C", str(src), "status", "--short"], capture_output=True, text=True).stdout.strip()
    rel = (src / "odoo" / "release.py").read_text() if (src / "odoo" / "release.py").is_file() else ""
    ver = (re.search(r"^version_info = \((\d+), (\d+)", rel, re.M) or [None, "?", "?"])
    print(f"source: {root.resolve()}  commit: {rev}{' (dirty)' if dirty else ''}  odoo: {ver[1]}.{ver[2]}")
    out, bad = {}, 0
    for v in (17, 19):
        for m in MODS:
            r = ca.audit(root / m, version=v)
            if not r.ok:
                print(f"v{v}/{m:13} ERROR {r.error}")
                bad += 1
                continue
            c = Counter(f.severity for f in r.findings)
            u = sum(1 for f in r.findings if "unaudited" in f.code)
            out[f"{v}/{m}"] = {"high": c["high"], "medium": c["medium"], "unaudited": u,
                               "codes": dict(Counter(f"{f.code}:{f.severity}" for f in r.findings if f.severity in ("high", "medium")))}
            print(f"v{v}/{m:13} HIGH={c['high']:4} MEDIUM={c['medium']:4} unaudited={u}")
            bad += u
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(out, indent=1, sort_keys=True))
    print("GATE OK: unaudited==0" if not bad else f"GATE FAIL: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
