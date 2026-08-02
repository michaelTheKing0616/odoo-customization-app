#!/usr/bin/env bash
# Library UAT helper — build zip, verify menus/models/fields, optional live Odoo probe.
# Does not declare "full-scale UAT §8 complete"; prints checklist results only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ZIP_PATH="${ROOT}/docker/sandbox-addons/_library_uat.zip"
export ZIP_PATH
export PYTHONPATH="${ROOT}/packages/module-generator/src:${PYTHONPATH:-}"
export SANDBOX_EXTRA_MODULES="${SANDBOX_EXTRA_MODULES:-contacts,mail}"

MULTI_COMPANY="${LIBRARY_MULTI_COMPANY:-0}"

echo "=== Library UAT — zip + checklist ==="
echo "SANDBOX_EXTRA_MODULES=${SANDBOX_EXTRA_MODULES} LIBRARY_MULTI_COMPANY=${MULTI_COMPANY}"

python3 <<'PY'
import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path

from module_generator import build_module_zip, library_module_spec, render_module_files

multi = os.environ.get("LIBRARY_MULTI_COMPANY", "0") in {"1", "true", "True", "yes"}
spec = library_module_spec(
    technical_name="library_mgmt",
    display_name="Library Management",
    multi_company=multi,
)
out = Path(os.environ["ZIP_PATH"])
out.parent.mkdir(parents=True, exist_ok=True)
raw = build_module_zip(spec)
out.write_bytes(raw)
files = render_module_files(spec)
menus = files.get("library_mgmt/views/menus.xml", "")

checks: list[tuple[str, bool, str]] = []

def ok(label: str, cond: bool, detail: str = "") -> None:
    checks.append((label, cond, detail))

# Models / fields
model_names = {m.model for m in spec.models}
ok("models x_lib_category/author/book/loan", model_names == {
    "x_lib_category", "x_lib_author", "x_lib_book", "x_lib_loan"
})
book = next(m for m in spec.models if m.model == "x_lib_book")
loan = next(m for m in spec.models if m.model == "x_lib_loan")
book_fields = {f.name for f in book.fields}
loan_fields = {f.name for f in loan.fields}
ok("book has ISBN/barcode/status", {"x_isbn", "x_barcode", "x_status"} <= book_fields)
ok("book author → x_lib_author", any(
    f.name == "x_author_id" and f.relation == "x_lib_author" for f in book.fields
))
ok("loan has member/dates/returned", {"x_member_id", "x_due_date", "x_returned"} <= loan_fields)
ok("depends includes mail+contacts", "mail" in spec.depends and "contacts" in spec.depends)

# Menus in zip
ok("menu Books in zip", "Books" in menus)
ok("menu Authors in zip", "Authors" in menus)
ok("menu Loans in zip", "Loans" in menus)
ok("menu Active Loans in zip", "Active Loans" in menus)
ok("menu Categories in zip", "Categories" in menus)
ok("Active Loans domain", "x_returned" in menus and "False" in menus)
ok("root Library menu", 'name="Library"' in menus or ">Library<" in menus)

# Multi-company
if multi:
    ok("multi_company company_id fields", all(
        any(f.name == "company_id" for f in m.fields) for m in spec.models
    ))
    ok("multi_company record rules", len(spec.record_rules) == 4)
else:
    ok("multi_company off (default)", not any(
        f.name == "company_id" for m in spec.models for f in m.fields
    ))

# Zip integrity
with zipfile.ZipFile(BytesIO(raw)) as zf:
    names = zf.namelist()
ok("zip has menus.xml", any(n.endswith("menus.xml") for n in names))
ok("zip has loan model py", any(n.endswith("x_lib_loan.py") for n in names))
ok("zip has author model py", any(n.endswith("x_lib_author.py") for n in names))
ok("zip has mail templates", any(n.endswith("mail_templates.xml") for n in names))
ok("zip has QWeb loan report", any("report/reports.xml" in n or "loan_reports.xml" in n for n in names))
ok("due-soon mail template", any(t.xml_id == "mail_template_loan_due_soon" for t in spec.mail_templates))
ok("overdue mail template", any(t.xml_id == "mail_template_loan_overdue" for t in spec.mail_templates))
ok("loan receipt report", len(spec.reports) >= 1 and spec.reports[0].template_xml_id == "report_loan_receipt_doc")
loan_py = files.get("library_mgmt/models/x_lib_loan.py", "")
ok("fine + due-soon cron methods", "action_compute_fine" in loan_py and "mail_template_loan_due_soon" in loan_py)
ok("mail.thread mixins", "mail.thread" in str(book.mixins) and "mail.thread" in str(loan.mixins))
ok("loan kanban view", any(v.type == "kanban" and v.model == "x_lib_loan" for v in spec.views))

print(f"wrote {out} ({out.stat().st_size} bytes) multi_company={multi}")
print()
print("UAT checklist (zip / spec):")
failed = 0
for label, passed, detail in checks:
    mark = "PASS" if passed else "FAIL"
    if not passed:
        failed += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [{mark}] {label}{suffix}")

# Optional live Odoo probe (primary stack)
print()
print("Live Odoo probe (optional):")
try:
    import sys
    # ZIP_PATH = <repo>/docker/sandbox-addons/_library_uat.zip
    repo = Path(os.environ["ZIP_PATH"]).resolve().parents[2]
    odoo_src = repo / "packages" / "odoo-client" / "src"
    if odoo_src.is_dir() and str(odoo_src) not in sys.path:
        sys.path.insert(0, str(odoo_src))
    from odoo_client import OdooClient

    url = os.environ.get("ODOO_URL", "http://127.0.0.1:8069")
    db = os.environ.get("ODOO_DB", "odoo_dev")
    user = os.environ.get("ODOO_USER", "admin")
    password = os.environ.get("ODOO_PASSWORD", "admin")
    client = OdooClient(url=url, db=db, username=user, password=password)
    client.authenticate()
    for model in ("x_lib_category", "x_lib_book", "x_lib_loan"):
        exists = client.model_exists(model)
        mark = "PASS" if exists else "SKIP"
        print(f"  [{mark}] live model {model} exists={exists}")
        if exists and model == "x_lib_book":
            for fname in ("x_isbn", "x_barcode", "x_status"):
                fe = client.field_exists(model, fname)
                print(f"  [{'PASS' if fe else 'FAIL'}] live field {model}.{fname}")
    print("  (Scaffold via wizard or run-sandbox-library-gate.sh if models missing)")
except Exception as exc:  # noqa: BLE001
    print(f"  [SKIP] live Odoo unreachable: {exc}")

print()
print("Automated §8: ./docker/run-library-functional-uat.sh (+ multi_company sandbox probe).")
print("Optional human: wizard UI click-through, Print→Loan Receipt, promote to non-sandbox.")

sys.exit(1 if failed else 0)
PY
