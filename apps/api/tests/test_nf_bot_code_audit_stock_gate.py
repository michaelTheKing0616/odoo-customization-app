"""CODE-AUDIT-10 stock gate: every *-unaudited finding on stock Odoo is an auditor gap, so the
count must stay 0 (CODE-AUDIT-8 counted only the HIGH whole-file codes and missed the MEDIUMs).
Opt-in (slow): INGENIUM_STOCK_AUDIT=1 and STOCK_ODOO_ADDONS pointing at odoo/addons."""
import os
from pathlib import Path

import pytest

from app.bots import code_audit as ca

ROOT = Path(os.environ.get("STOCK_ODOO_ADDONS", ""))
MODS = ["mail", "sale", "crm", "hr", "website_sale", "mrp", "account", "stock", "web", "portal", "auth_signup", "website",
        # CA12: product (M2/M3 false alarms) + 6 more stock modules
        "product", "purchase", "project", "point_of_sale", "hr_expense", "event", "survey"]
pytestmark = pytest.mark.skipif(
    os.environ.get("INGENIUM_STOCK_AUDIT") != "1" or not (ROOT / "web" / "__manifest__.py").is_file(),
    reason="stock gate is opt-in")


@pytest.mark.parametrize("version", [17, 19])
@pytest.mark.parametrize("mod", MODS)
def test_stock_has_no_unaudited(mod, version):
    left = [(f.code, f.file, f.line) for f in ca.audit(ROOT / mod, version=version).findings if "unaudited" in f.code]
    assert left == []
