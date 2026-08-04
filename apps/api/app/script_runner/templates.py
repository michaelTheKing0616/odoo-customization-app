"""DEV-3 starter script templates."""

from __future__ import annotations

SCRIPT_TEMPLATES: list[dict[str, str]] = [
    {
        "id": "batched_read_report",
        "label": "Batched read + report",
        "description": "Read partners in batches and log counts (safe read-only pattern).",
        "code": """# Batched read + report
BATCH = 50
offset = 0
total = 0
while True:
    rows = odoo.execute_kw(
        "res.partner",
        "search_read",
        [[]],
        {"fields": ["name", "email"], "limit": BATCH, "offset": offset},
    )
    if not rows:
        break
    for row in rows:
        log(f"{row['id']}: {row.get('name')}")
    total += len(rows)
    progress(total, total + BATCH)
    offset += BATCH
log(f"Reported {total} partners")
""",
    },
    {
        "id": "guarded_mass_write",
        "label": "Guarded mass write (dry-run)",
        "description": "Demonstrates DRY_RUN flag convention before writes.",
        "code": """DRY_RUN = True
MODEL = "res.partner"
ids = odoo.execute_kw(MODEL, "search", [[("active", "=", True)]], {"limit": 5})
log(f"Would touch {len(ids)} records (DRY_RUN={DRY_RUN})")
if not DRY_RUN:
    odoo.execute_kw(MODEL, "write", [ids, {"comment": "Script runner touch"}])
    log("Write applied")
else:
    log("Dry run only — set DRY_RUN=False after review")
""",
    },
    {
        "id": "csv_export",
        "label": "CSV export to output buffer",
        "description": "Export scalar fields to CSV printed to console (no filesystem).",
        "code": """import csv
import io
MODEL = "res.partner"
rows = odoo.execute_kw(
    MODEL,
    "search_read",
    [[]],
    {"fields": ["name", "email", "phone"], "limit": 100},
)
buf = io.StringIO()
writer = csv.DictWriter(buf, fieldnames=["id", "name", "email", "phone"])
writer.writeheader()
for row in rows:
    writer.writerow({k: row.get(k, "") for k in ["id", "name", "email", "phone"]})
log(buf.getvalue())
""",
    },
    {
        "id": "orphan_checker",
        "label": "Orphan checker",
        "description": "Find partners without email (report only).",
        "code": """MODEL = "res.partner"
orphans = odoo.execute_kw(
    MODEL,
    "search_read",
    [[("email", "=", False)]],
    {"fields": ["name"], "limit": 200},
)
log(f"Found {len(orphans)} without email")
for row in orphans[:20]:
    log(f"  #{row['id']} {row.get('name')}")
""",
    },
    {
        "id": "activity_scheduler",
        "label": "Activity scheduler sketch",
        "description": "Schedule follow-up activities on a sample set (guarded).",
        "code": """DRY_RUN = True
MODEL = "res.partner"
ids = odoo.execute_kw(MODEL, "search", [[("active", "=", True)]], {"limit": 3})
log(f"Targets: {ids}")
if DRY_RUN:
    log("DRY_RUN — would schedule mail.mail_activity_data_todo")
else:
    for rid in ids:
        odoo.execute_kw(
            MODEL,
            "message_post",
            [[rid]],
            {"body": "Script runner scheduled note", "message_type": "comment"},
        )
    log("Notes posted")
""",
    },
]
