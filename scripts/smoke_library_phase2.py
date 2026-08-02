#!/usr/bin/env python3
"""Live Phase-2 Acme Library smoke against local Odoo 19 (RPC gate).

Usage (repo root):
  uv run --directory packages/odoo-client python scripts/smoke_library_phase2.py

Requires: odoo:19 on http://127.0.0.1:8069 db=odoo_dev admin/admin with Acme Library models.
"""

from __future__ import annotations

import sys
import traceback

from odoo_client import (
    ConnectionConfig,
    CreateAutomationRequest,
    CreateMailPostServerAction,
    CreateNextActivityServerAction,
    CreateSmartButtonBundle,
    CreateUpdateFieldServerAction,
    MailPostAction,
    OdooClient,
)
from odoo_client.automation import AutomationTrigger
from odoo_client.view_arch import parse_form_arch, render_inherit_xpath_arch

PASS: list[str] = []
FAIL: list[tuple[str, str]] = []


def ok(name: str, detail: str = "") -> None:
    PASS.append(name)
    print(f"PASS  {name}" + (f" — {detail}" if detail else ""))


def bad(name: str, err: object) -> None:
    FAIL.append((name, str(err)))
    print(f"FAIL  {name} — {err}")


def main() -> int:
    c = OdooClient(
        ConnectionConfig(
            url="http://127.0.0.1:8069",
            db="odoo_dev",
            username="admin",
            password="admin",
        )
    )
    c.connect()
    ok("connect")

    for m in ("x_lib_book", "x_lib_loan"):
        c._model_id(m)
        ok(f"model:{m}")

    books = c.execute_kw("x_lib_book", "search", [[]], {"limit": 1})
    if not books:
        books = [c.execute_kw("x_lib_book", "create", [{"x_name": "UAT Book"}])]
    book_id = int(books[0])
    ok("book", f"id={book_id}")

    # Status selection keys (library uses loaned not borrowed)
    status_meta = c.execute_kw(
        "ir.model.fields",
        "search_read",
        [[("model", "=", "x_lib_book"), ("name", "=", "x_status")]],
        {"fields": ["selection"], "limit": 1},
    )[0]
    ok("x_status_selection", str(status_meta.get("selection")))

    sa = c.create_update_field_server_action(
        CreateUpdateFieldServerAction(
            name="UAT2 Mark Available",
            model="x_lib_book",
            field_name="x_status",
            value="available",
        )
    )
    ok("create_update_field", f"id={sa.id}")
    c.execute_kw("x_lib_book", "write", [[book_id], {"x_status": "loaned"}])
    c.run_server_action(sa.id, model="x_lib_book", record_id=book_id)
    status = c.execute_kw("x_lib_book", "read", [[book_id], ["x_status"]])[0]["x_status"]
    if status == "available":
        ok("run_update_field", f"status={status}")
    else:
        bad("run_update_field", f"got {status!r}")

    bundle = c.create_smart_button_bundle(
        CreateSmartButtonBundle(
            name="UAT2 Loans",
            source_model="x_lib_book",
            target_model="x_lib_loan",
            relation_field="x_book_id",
            one2many_field="x_loan_ids",
            count_field_name="x_uat2_loan_count",
            create_count_field=True,
            icon="fa-book",
        )
    )
    ok("smart_bundle", f"wa={bundle.window_action.id} count={bundle.count_field}")
    cnt = c.execute_kw("x_lib_book", "read", [[book_id], [bundle.count_field]])[0][
        bundle.count_field
    ]
    ok("count_read", f"{cnt}")

    c.ensure_mail_mixins("x_lib_book")
    types = c.list_activity_types(limit=3)
    na = c.create_next_activity_server_action(
        CreateNextActivityServerAction(
            name="UAT2 Activity",
            model="x_lib_book",
            activity_type_id=int(types[0]["id"]),
            summary="UAT2 follow-up",
            # user_field auto-resolves to create_uid on custom models
        )
    )
    ok("create_next_activity", f"id={na.id}")
    c.run_server_action(na.id, model="x_lib_book", record_id=book_id)
    ok("run_next_activity")

    mp = c.create_mail_post_server_action(
        CreateMailPostServerAction(
            name="UAT2 Mail Note",
            model="x_lib_book",
            mail_post_method="note",
            subject="UAT2",
            body_html="<p>UAT2</p>",
        )
    )
    ok("create_mail_post", f"id={mp.id}")
    c.run_server_action(mp.id, model="x_lib_book", record_id=book_id)
    ok("run_mail_post")

    primary = c.find_view("x_lib_book", "form", primary_only=True) or c.find_view(
        "x_lib_book", "form"
    )
    assert primary is not None
    hdr = (
        f'<header><button name="{sa.id}" type="action" string="Mark Available" '
        f'class="btn-primary"/><field name="x_status" widget="statusbar"/></header>'
    )
    box = (
        f'<div name="button_box" class="oe_button_box">'
        f'<button name="{bundle.window_action.id}" type="action" class="oe_stat_button" '
        f'icon="fa-book" string="Loans">'
        f'<field name="{bundle.count_field}" widget="statinfo" string="Loans"/>'
        f"</button></div>"
    )
    combined = (
        "<data>\n"
        + render_inherit_xpath_arch(expr="//sheet", position="before", body_xml=hdr)
        .replace("<data>", "")
        .replace("</data>", "")
        + render_inherit_xpath_arch(expr="//sheet", position="inside", body_xml=box)
        .replace("<data>", "")
        .replace("</data>", "")
        + "</data>"
    )
    name = "x_lib_book.studio.header_actions"
    existing = c.execute_kw("ir.ui.view", "search", [[("name", "=", name)]], {"limit": 1})
    if existing:
        c.execute_kw("ir.ui.view", "write", [existing, {"arch": combined}])
        vid = existing[0]
    else:
        vid = c.create_inherit_view(
            model="x_lib_book",
            name=name,
            view_type="form",
            inherit_id=primary.id,
            arch=combined,
        ).id
    ok("inherit_view", f"id={vid}")
    # Guard against stacked UAT inherits from older smoke runs
    stale = c.execute_kw(
        "ir.ui.view",
        "search",
        [
            [
                ("model", "=", "x_lib_book"),
                ("id", "!=", vid),
                "|",
                ("name", "ilike", "%.uat.%"),
                ("name", "ilike", "%.uat2.%"),
            ]
        ],
    )
    if stale:
        c.execute_kw("ir.ui.view", "unlink", [stale])
        ok("removed_stale_inherits", str(stale))
    arch = c.execute_kw("x_lib_book", "get_view", [], {"view_type": "form"})["arch"]
    mark_n = arch.count("Mark Available")
    if mark_n != 1:
        bad("arch:Mark Available", f"expected 1 got {mark_n}")
    else:
        ok("arch:Mark Available")
    for needle in ("oe_stat_button", bundle.count_field, "statusbar"):
        if needle in arch:
            ok(f"arch:{needle}")
        else:
            bad(f"arch:{needle}", "missing")
    parsed = parse_form_arch(arch)
    ok(
        "parse",
        f"header={len(parsed.header_buttons)} box={len(parsed.button_box)} sb={parsed.statusbar_field}",
    )

    auto = c.create_automation(
        CreateAutomationRequest(
            name="UAT2 mail_post inactive",
            model="x_lib_book",
            trigger=AutomationTrigger.ON_WRITE,
            action=MailPostAction(mail_post_method="note", subject="auto", body_html="<p>a</p>"),
            active=False,
        )
    )
    ok("automation_mail_post", f"id={auto.id}")

    print(f"\n=== SUMMARY PASS={len(PASS)} FAIL={len(FAIL)} ===")
    for n, e in FAIL:
        print(f"  - {n}: {e[:240]}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
