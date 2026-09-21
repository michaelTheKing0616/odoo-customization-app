"""Operator surface map — where a custom app shows up in Odoo (menus + smart buttons).

Stamps ``_operator_surface`` so Draft Studio can show a production-style placement
panel without inventing Contact/PoS stat buttons next to existing many2ones.

Completeness ≠ Cert ≠ Autopilot. Promote stays human.
"""

from __future__ import annotations

import re
from typing import Any

# Friendly host names when app_bar commercial table has no entry.
_HOST_LABELS: dict[str, str] = {
    "res.partner": "Contacts",
    "res.users": "Users",
    "hr.employee": "Employees",
    "pos.order": "Point of Sale orders",
    "pos.session": "PoS sessions",
    "pos.payment.method": "PoS payment methods",
    "sale.order": "Sales orders",
    "account.move": "Invoices",
    "account.payment": "Payments",
    "crm.lead": "CRM leads",
    "project.task": "Tasks",
    "project.project": "Projects",
    "calendar.event": "Calendar",
    "purchase.order": "Purchase orders",
    "stock.picking": "Transfers",
    "hr.expense": "Expenses",
}


def _host_label(model: str) -> str:
    mid = str(model or "").strip()
    if mid in _HOST_LABELS:
        return _HOST_LABELS[mid]
    try:
        from app.ai_odoo_app_bar import short_model_label

        return short_model_label(mid, plural=True)
    except Exception:  # noqa: BLE001
        leaf = mid.split(".")[-1].replace("_", " ").strip()
        return leaf.title() if leaf else mid


def _option_a_is_qweb_report_only(draft: dict[str, Any]) -> bool:
    """True when authored blocks are report/QWeb inherit without new form fields."""
    blocks = [b for b in (draft.get("custom_code_blocks") or []) if isinstance(b, dict)]
    if not blocks:
        return False
    has_report = False
    has_form_fields = False
    for block in blocks:
        path = str(block.get("source_file") or block.get("path") or "").lower()
        content = str(block.get("content") or "")
        kind = str(block.get("kind") or "").lower()
        if (
            "report" in path
            or kind in {"qweb", "xml"}
            and ("inherit_id=" in content and "report_" in content)
        ):
            has_report = True
        if (path.endswith(".py") or kind == "python") and re.search(
            r"fields\.(Char|Integer|Float|Boolean|Selection|Many2one|One2many|Many2many)",
            content,
        ):
            has_form_fields = True
        if "views/" in path and "<field " in content and "report_" not in content:
            has_form_fields = True
    return has_report and not has_form_fields


def _root_menu(draft: dict[str, Any]) -> dict[str, str] | None:
    menus = [m for m in (draft.get("menus") or []) if isinstance(m, dict)]
    if not menus:
        return None
    roots = [
        m
        for m in menus
        if not m.get("parent_xml_id") and not m.get("parent_id")
    ]
    pick = roots[0] if roots else menus[0]
    name = str(pick.get("name") or draft.get("display_name") or "").strip()
    tech = str(
        pick.get("technical_name") or pick.get("xml_id") or draft.get("technical_name") or ""
    ).strip()
    if not name and not tech:
        return None
    return {"label": name or tech, "technical_name": tech}


def _has_residual_x_new(draft: dict[str, Any]) -> bool:
    """True when the draft carries a new residual x_* model (not inherit-only)."""
    return any(
        isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and str(m.get("mode") or "new") != "inherit"
        for m in (draft.get("models") or [])
    )


def _residual_full_app_find_it(draft: dict[str, Any]) -> bool:
    """Find-it for residual full_app = app menu + residual buttons only (no invented host).

    Locked ``full_app`` + x_new keeps craft-only gating through feature_slice flips.
    Explicit field_pack (Prefer) stays open; feature_slice + x_new suppresses invent.
    """
    try:
        from app.ai_stock_host_smart_buttons import partner_tie_allows_contacts_button

        prompt = str(draft.get("_user_prompt") or "")
        if partner_tie_allows_contacts_button(prompt):
            return False  # punch/loyalty — keep intentional Contacts host button
    except Exception:  # noqa: BLE001
        pass

    engine = draft.get("_generation_engine")
    if isinstance(engine, dict) and engine.get("capability") in {
        "option_a_authored",
        "option_a_standalone",
        "stock_reuse",
    }:
        return False
    if draft.get("_component"):
        return False

    x_new = _has_residual_x_new(draft)
    u = draft.get("_understanding") if isinstance(draft.get("_understanding"), dict) else {}
    locked_grain = str(u.get("grain") or "")
    locked_inherit = bool(u.get("inherit_existing"))

    if locked_inherit and not x_new:
        return False

    if locked_grain == "full_app" and not locked_inherit and x_new:
        return True

    grain = str(draft.get("grain") or "full_app")
    eg = str(engine.get("grain") or "") if isinstance(engine, dict) else ""

    if (grain == "field_pack" or eg == "field_pack") and locked_grain != "full_app":
        return False

    if x_new and not locked_inherit and (grain == "feature_slice" or eg == "feature_slice"):
        return True

    if grain in {"field_pack", "feature_slice"}:
        return False
    if eg in {"field_pack", "feature_slice"}:
        return False
    return x_new or grain == "full_app"


def build_operator_surface(draft: dict[str, Any]) -> dict[str, Any]:
    """Build a placement map from menus, smart_buttons, and residual stock M2Os.

    Residual full_app find-it: app menu + residual smart buttons only. Stock M2Os to
    Contacts/Employees stay ``stock_links`` (fields), never invented «{app}» host buttons.
    """
    display = str(draft.get("display_name") or draft.get("technical_name") or "App").strip()
    app_menu = _root_menu(draft)
    host_buttons: list[dict[str, str]] = []
    residual_buttons: list[dict[str, str]] = []
    seen_host: set[tuple[str, str, str]] = set()
    seen_res: set[tuple[str, str, str]] = set()
    suppress_host_invent = _residual_full_app_find_it(draft)
    # When Contract IR carries craft_smart_buttons (incl. empty), residual stock-host
    # find-it lines are ⊆ that list only — never invent Contacts/Employees from M2O.
    u_pre = draft.get("_understanding") if isinstance(draft.get("_understanding"), dict) else None
    if (
        not suppress_host_invent
        and isinstance(u_pre, dict)
        and "craft_smart_buttons" in u_pre
        and not u_pre.get("inherit_existing")
        and _has_residual_x_new(draft)
    ):
        try:
            from app.ai_stock_host_smart_buttons import partner_tie_allows_contacts_button

            if not partner_tie_allows_contacts_button(str(draft.get("_user_prompt") or "")):
                suppress_host_invent = True
        except Exception:  # noqa: BLE001
            suppress_host_invent = True

    for btn in draft.get("smart_buttons") or []:
        if not isinstance(btn, dict):
            continue
        on_model = str(btn.get("on_model") or "").strip()
        related = str(btn.get("related_model") or "").strip()
        label = str(btn.get("label") or related or "Open").strip()
        if not on_model or not related:
            continue
        if on_model.startswith("x_"):
            key = (on_model, related, label)
            if key in seen_res:
                continue
            seen_res.add(key)
            residual_buttons.append(
                {
                    "on_model": on_model,
                    "related_model": related,
                    "button_label": label,
                }
            )
            continue
        # Residual full_app: stock-host find-it ⊆ confirmed craft only.
        # Empty craft ⇒ no stock-host line (never invent Contacts/Employees from M2O).
        # Prefer craft label («Visits») over invent/pluralize («Visitor Logs»).
        if suppress_host_invent:
            u = draft.get("_understanding") if isinstance(draft.get("_understanding"), dict) else {}
            craft = u.get("craft_smart_buttons") or []
            craft_by_key = {
                (
                    str(c.get("on_model") or c.get("host_model") or ""),
                    str(c.get("related_model") or c.get("residual_model") or ""),
                ): c
                for c in craft
                if isinstance(c, dict)
                and (
                    str(c.get("on_model") or c.get("host_model") or "")
                    and str(c.get("related_model") or c.get("residual_model") or "")
                )
            }
            craft_row = craft_by_key.get((on_model, related))
            # Residual find-it ⊆ confirmed craft only — never source-tag invent.
            if craft_row is None:
                continue
            craft_label = str(craft_row.get("label") or "").strip()
            if craft_label:
                label = craft_label

        key = (on_model, related, label)
        if key in seen_host:
            continue
        seen_host.add(key)
        host_buttons.append(
            {
                "host_model": on_model,
                "host_label": _host_label(on_model),
                "button_label": label,
                "residual_model": related,
            }
        )

    # Defence: craft rows missing from smart_buttons still appear on find-it.
    if suppress_host_invent:
        u_craft = draft.get("_understanding") if isinstance(draft.get("_understanding"), dict) else {}
        for c in u_craft.get("craft_smart_buttons") or []:
            if not isinstance(c, dict):
                continue
            on_model = str(c.get("on_model") or c.get("host_model") or "").strip()
            related = str(c.get("related_model") or c.get("residual_model") or "").strip()
            label = str(c.get("label") or related or "Open").strip()
            if not on_model or not related or on_model.startswith("x_"):
                continue
            key = (on_model, related, label)
            if any(
                h.get("host_model") == on_model and h.get("residual_model") == related
                for h in host_buttons
            ):
                continue
            if key in seen_host:
                continue
            seen_host.add(key)
            host_buttons.append(
                {
                    "host_model": on_model,
                    "host_label": _host_label(on_model),
                    "button_label": label,
                    "residual_model": related,
                }
            )

    stock_links: list[dict[str, str]] = []
    seen_link: set[tuple[str, str]] = set()
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or mid.endswith("_line"):
            continue
        if str(model.get("mode") or "new") == "inherit":
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if str(field.get("ttype") or "") != "many2one":
                continue
            rel = str(field.get("relation") or "").strip()
            fname = str(field.get("name") or "").strip()
            if not rel or rel.startswith("x_"):
                continue
            key = (fname, rel)
            if key in seen_link:
                continue
            seen_link.add(key)
            stock_links.append(
                {
                    "field": fname,
                    "field_label": str(field.get("string") or fname),
                    "stock_model": rel,
                    "stock_label": _host_label(rel),
                    "on_model": mid,
                }
            )

    parts: list[str] = []
    if app_menu and app_menu.get("label"):
        parts.append(f"Open «{app_menu['label']}» from the Odoo home / app switcher.")
    if host_buttons:
        bits: list[str] = []
        seen_bit: set[str] = set()
        for b in host_buttons[:6]:
            bit = f"«{b['button_label']}» on {b['host_label']}"
            key = bit.lower()
            if key in seen_bit:
                continue
            seen_bit.add(key)
            bits.append(bit)
        if bits:
            parts.append("Also on stock forms: " + "; ".join(bits) + ".")
    if residual_buttons:
        parts.append(
            f"{len(residual_buttons)} smart button(s) on your custom form(s) "
            "link related custom documents."
        )
    if stock_links and not host_buttons:
        examples = []
        for row in stock_links[:3]:
            fl = str(row.get("field_label") or row.get("field") or "").strip()
            sl = str(row.get("stock_label") or "").strip()
            if fl and sl:
                examples.append(f"{fl} → {sl}")
        if examples:
            parts.append(
                "Linked stock records appear as form fields on the residual "
                f"({'; '.join(examples)})."
            )
        else:
            parts.append(
                "Linked stock records appear as form fields on the residual."
            )
    elif stock_links:
        labels = [
            str(row.get("field_label") or row.get("field") or "").strip()
            for row in stock_links[:4]
            if str(row.get("field_label") or row.get("field") or "").strip()
        ]
        if labels:
            shown = ", ".join(labels)
            if len(stock_links) > len(labels):
                shown += ", …"
            parts.append(
                f"Stock links on the residual form stay as fields ({shown}) "
                "— not duplicate smart buttons."
            )
        else:
            parts.append(
                "Stock links on the residual form stay as fields "
                "— not duplicate smart buttons."
            )
    if not parts:
        engine = draft.get("_generation_engine")
        host = ""
        if isinstance(engine, dict):
            host = str(engine.get("host_model") or engine.get("preferred_inherit_host") or "").strip()
        if not host:
            for model in draft.get("models") or []:
                if not isinstance(model, dict):
                    continue
                if str(model.get("mode") or "").lower() == "inherit":
                    host = str(model.get("model") or "").strip()
                    if host:
                        break
        cap = ""
        if isinstance(engine, dict):
            cap = str(engine.get("capability") or "")
        if (
            draft.get("_capability_primary_option_a")
            or cap in {"option_a_authored", "option_a_standalone"}
        ) and host and not host.startswith("x_"):
            qweb_only = _option_a_is_qweb_report_only(draft)
            if qweb_only and host == "stock.picking":
                parts.append(
                    f"«{display}» changes the printed Delivery slip / Delivery note "
                    f"(QWeb on {host}) via an Option A module — not new form fields on "
                    "Transfers. Zip → sandbox → Promote. Install Inventory if stock.picking "
                    "is missing. Not a new Apps tile. Do not click Install this app."
                )
            elif qweb_only:
                parts.append(
                    f"«{display}» changes a printed document (QWeb inherit on "
                    f"{_host_label(host)} / {host}) via an Option A module — the form "
                    "canvas may show no new fields. Zip → sandbox → Promote. Not a new "
                    "Apps tile. Do not click Install this app."
                )
            else:
                parts.append(
                    f"«{display}» extends {_host_label(host)} ({host}) via an Option A module — "
                    "zip → sandbox → Promote. Not a new Apps tile. Do not click Install this app."
                )
        else:
            parts.append(
                f"«{display}» is a residual app — open it from the app menu after Apply."
            )

    return {
        "app_menu": app_menu,
        "host_buttons": host_buttons,
        "residual_buttons": residual_buttons,
        "stock_links": stock_links,
        "summary": " ".join(parts),
        "display_name": display,
    }


def attach_operator_surface(draft: dict[str, Any]) -> list[str]:
    """Stamp ``_operator_surface`` for Wizard discoverability."""
    if not isinstance(draft, dict):
        return []
    # Scrub invented Contacts host buttons before find-it (do not stamp new ones here).
    try:
        from app.ai_stock_host_smart_buttons import scrub_residual_contacts_host_buttons

        scrub_residual_contacts_host_buttons(
            draft, prompt=str(draft.get("_user_prompt") or "")
        )
    except Exception:  # noqa: BLE001
        pass
    engine = draft.get("_generation_engine")
    if isinstance(engine, dict) and engine.get("capability") == "stock_reuse":
        draft["_operator_surface"] = {
            "app_menu": None,
            "host_buttons": [],
            "residual_buttons": [],
            "stock_links": [],
            "summary": "Stock Community apps cover this brief — no custom smart buttons.",
            "display_name": str(draft.get("display_name") or "Stock apps"),
        }
        return ["operator_surface: stock_reuse"]
    if draft.get("_component"):
        return []
    surface = build_operator_surface(draft)
    draft["_operator_surface"] = surface
    n_host = len(surface.get("host_buttons") or [])
    n_res = len(surface.get("residual_buttons") or [])
    return [
        f"operator_surface: {n_host} host button(s), {n_res} residual button(s)"
    ]


__all__ = [
    "attach_operator_surface",
    "build_operator_surface",
]
