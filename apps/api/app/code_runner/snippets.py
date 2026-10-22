"""Odoo snippets with fill-ins (Monaco snippet syntax: ${1:placeholder})."""

from __future__ import annotations

SNIPPETS: list[dict[str, str]] = [
    {"id": "search_read", "label": "Find records", "detail": "search_read with fields and a limit",
     "body": 'rows = odoo.execute_kw("${1:res.partner}", "search_read", [[${2:("active", "=", True)}]], {"fields": [${3:"name"}], "limit": ${4:80}})\nfor row in rows:\n    log(row)\n'},
    {"id": "count", "label": "Count records", "detail": "search_count",
     "body": 'n = odoo.execute_kw("${1:res.partner}", "search_count", [[${2}]])\nlog(f"{n} records")\n'},
    {"id": "batch_loop", "label": "Read in batches", "detail": "offset loop with progress",
     "body": 'BATCH = ${1:200}\noffset = 0\nwhile True:\n    rows = odoo.execute_kw("${2:res.partner}", "search_read", [[${3}]], {"fields": [${4:"name"}], "limit": BATCH, "offset": offset})\n    if not rows:\n        break\n    for row in rows:\n        ${5:log(row)}\n    offset += BATCH\n    progress(offset, offset + BATCH)\n'},
    {"id": "create", "label": "Create a record", "detail": "create(vals)",
     "body": 'new_id = odoo.execute_kw("${1:res.partner}", "create", [{${2:"name": "New"}}])\nlog(f"Created {new_id}")\n'},
    {"id": "write", "label": "Update records", "detail": "write(ids, vals)",
     "body": 'ids = odoo.execute_kw("${1:res.partner}", "search", [[${2}]], {"limit": ${3:100}})\nodoo.execute_kw("$1", "write", [ids, {${4:"comment": "checked"}}])\nlog(f"Updated {len(ids)}")\n'},
    {"id": "archive", "label": "Archive records", "detail": "action_archive (reversible, unlike delete)",
     "body": 'ids = odoo.execute_kw("${1:res.partner}", "search", [[${2}]])\nodoo.execute_kw("$1", "action_archive", [ids])\n'},
    {"id": "group_count", "label": "Count by group", "detail": "read_group (formatted_read_group on 19+)",
     "body": 'groups = odoo.execute_kw("${1:sale.order}", "read_group", [[${2}], [${3:"amount_total:sum"}], [${4:"state"}]], {"lazy": False})\nfor g in groups:\n    log(g)\n'},
    {"id": "display_name", "label": "Record labels", "detail": "display_name (name_get is gone on 17+)",
     "body": 'rows = odoo.execute_kw("${1:res.partner}", "read", [${2:[1]}, ["display_name"]])\n'},
    {"id": "fields", "label": "List a model's fields", "detail": "fields_get",
     "body": 'meta = odoo.execute_kw("${1:res.partner}", "fields_get", [], {"attributes": ["string", "type"]})\nfor name, f in sorted(meta.items()):\n    log(f"{name}: {f[\'type\']} ({f[\'string\']})")\n'},
]
