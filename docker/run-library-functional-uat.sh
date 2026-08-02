#!/usr/bin/env bash
# Library functional UAT on sandbox (keep-alive probe then tear down).
# Exercises §8 automated subset: models, menus, chatter mixin, fines, mail, cron, report.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/packages/module-generator/src:${PYTHONPATH:-}"
export SANDBOX_EXTRA_MODULES="${SANDBOX_EXTRA_MODULES:-contacts,mail}"

echo "=== Library functional UAT (sandbox keep-alive) ==="

uv run --directory "${ROOT}/apps/api" python <<'PY'
from __future__ import annotations

import sys
import xmlrpc.client
from datetime import date, timedelta
from pathlib import Path

from module_generator import build_module_zip, library_module_spec
from app.sandbox import (
    SANDBOX_DB,
    SANDBOX_PASSWORD,
    SANDBOX_URL,
    SANDBOX_USER,
    run_sandbox_install,
    _compose,
)

spec = library_module_spec(
    technical_name="library_mgmt",
    display_name="Library Management",
    include_fines=True,
    include_reminders=True,
    multi_company=False,
)
zip_bytes = build_module_zip(spec)

print("Installing library_mgmt (keep_alive=True)…")
result = run_sandbox_install(
    zip_bytes,
    module_name="library_mgmt",
    keep_alive=True,
    extra_modules=None,
)
if not result.ok:
    print("INSTALL FAIL:", result.message)
    sys.exit(1)
print("install OK", result.sandbox_url or SANDBOX_URL)

checks: list[tuple[str, bool, str]] = []

def check(label: str, cond: bool, detail: str = "") -> None:
    checks.append((label, bool(cond), detail))

common = xmlrpc.client.ServerProxy(f"{SANDBOX_URL}/xmlrpc/2/common", allow_none=True)
uid = common.authenticate(SANDBOX_DB, SANDBOX_USER, SANDBOX_PASSWORD, {})
assert uid, "auth failed"
models = xmlrpc.client.ServerProxy(f"{SANDBOX_URL}/xmlrpc/2/object", allow_none=True)

def kw(model: str, method: str, args=None, kwargs=None):
    return models.execute_kw(
        SANDBOX_DB,
        uid,
        SANDBOX_PASSWORD,
        model,
        method,
        args if args is not None else [],
        kwargs or {},
    )

# Models + mixins
for m in ("x_lib_category", "x_lib_author", "x_lib_book", "x_lib_loan"):
    check(
        f"model {m}",
        bool(kw("ir.model", "search", [[("model", "=", m)]], {"limit": 1})),
    )

book_fields = kw("x_lib_book", "fields_get", [], {"attributes": ["type", "relation"]})
loan_fields = kw("x_lib_loan", "fields_get", [], {"attributes": ["type"]})
check("book barcode+isbn", "x_barcode" in book_fields and "x_isbn" in book_fields)
check(
    "book author → x_lib_author",
    book_fields.get("x_author_id", {}).get("relation") == "x_lib_author",
)
check("loan chatter (message_ids)", "message_ids" in loan_fields)
check("book chatter (message_ids)", "message_ids" in book_fields)
check("loan kanban possible", "x_returned" in loan_fields)

# Menus / actions
menu_ids = kw("ir.ui.menu", "search", [[("name", "=", "Library")]], {"limit": 5})
check("Library root menu", bool(menu_ids))
authors_menu = kw("ir.ui.menu", "search", [[("name", "=", "Authors")]], {"limit": 1})
check("Authors menu", bool(authors_menu))
active_act = kw(
    "ir.actions.act_window",
    "search_read",
    [[("name", "=", "Active Loans")]],
    {"fields": ["domain", "res_model"], "limit": 1},
)
check("Active Loans action", bool(active_act) and active_act[0]["res_model"] == "x_lib_loan")

# Mail templates + cron + report
tpl = kw(
    "mail.template",
    "search",
    [[("name", "ilike", "Library:")]],
    {"limit": 10},
)
check("mail templates (>=2)", len(tpl) >= 2, f"count={len(tpl)}")
cron = kw(
    "ir.cron",
    "search",
    [[("cron_name", "ilike", "Library")]],
    {"limit": 5},
)
if not cron:
    cron = kw("ir.cron", "search", [[("name", "ilike", "Library")]], {"limit": 5})
check("library reminder cron", bool(cron))
report = kw(
    "ir.actions.report",
    "search",
    [[("name", "=", "Loan Receipt")]],
    {"limit": 1},
)
check("QWeb loan receipt report", bool(report))

# Sample data + fine computation
cat_id = kw("x_lib_category", "create", [{"x_name": "UAT Fiction"}])
author_id = kw("x_lib_author", "create", [{"x_name": "UAT Author"}])
partner_id = kw(
    "res.partner",
    "create",
    [{"name": "UAT Member", "email": "uat.member@example.com"}],
)
book_id = kw(
    "x_lib_book",
    "create",
    [{
        "x_name": "UAT Book",
        "x_isbn": "9780000000001",
        "x_barcode": "LIB-UAT-001",
        "x_copies": 3,
        "x_available": True,
        "x_status": "available",
        "x_category_id": cat_id,
        "x_author_id": author_id,
        "x_fine_rate": 2.5,
    }],
)
due = (date.today() - timedelta(days=4)).isoformat()
loan_id = kw(
    "x_lib_loan",
    "create",
    [{
        "x_name": "UAT-LOAN-1",
        "x_book_id": book_id,
        "x_member_id": partner_id,
        "x_loan_date": (date.today() - timedelta(days=14)).isoformat(),
        "x_due_date": due,
        "x_returned": False,
    }],
)
check("create category/book/loan", bool(cat_id and book_id and loan_id))

# Chatter post
try:
    kw(
        "x_lib_loan",
        "message_post",
        [[loan_id]],
        {"body": "UAT chatter note", "message_type": "comment"},
    )
    check("chatter message_post", True)
except Exception as exc:  # noqa: BLE001
    check("chatter message_post", False, str(exc)[:120])

# Return + fine
kw("x_lib_loan", "write", [[loan_id], {"x_returned": True}])
try:
    kw("x_lib_loan", "action_compute_fine", [[loan_id]])
except Exception as exc:  # noqa: BLE001
    check("action_compute_fine callable", False, str(exc)[:160])
else:
    check("action_compute_fine callable", True)

loan = kw(
    "x_lib_loan",
    "read",
    [[loan_id]],
    {"fields": ["x_fine_amount", "x_days_overdue", "x_returned"]},
)[0]
fine_ok = float(loan["x_fine_amount"] or 0) >= 9.9 and int(loan["x_days_overdue"] or 0) >= 4
check(
    "fine amount on overdue return",
    fine_ok,
    f"fine={loan['x_fine_amount']} days={loan['x_days_overdue']}",
)

# Barcode search
found = kw("x_lib_book", "search", [[("x_barcode", "=", "LIB-UAT-001")]], {"limit": 1})
check("barcode find book", found == [book_id])

# Tear down sandbox
print("Tearing down sandbox…")
try:
    _compose("down", "-v")
except Exception as exc:  # noqa: BLE001
    print("compose down warning:", exc)

failed = 0
print()
print("Functional UAT results:")
for label, ok, detail in checks:
    mark = "PASS" if ok else "FAIL"
    if not ok:
        failed += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [{mark}] {label}{suffix}")

print()
if failed:
    print(f"FAILED {failed}/{len(checks)}")
    sys.exit(1)
print(f"ALL {len(checks)} CHECKS PASSED")
sys.exit(0)
PY
