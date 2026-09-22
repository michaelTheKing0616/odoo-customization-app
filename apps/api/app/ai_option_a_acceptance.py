"""Option A acceptance contracts — prove operator outcomes, not just install.

Stamped on authored drafts as ``_option_a_acceptance``. Sandbox RPC smoke
executes the checks; failures become Failure IR for self-heal repair.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from app.ai_option_a_view_fields import collect_draft_python_fields

ExecuteKw = Callable[..., Any]

_MARKUP_RE = re.compile(r"(?i)mark-?up|withh?olding\s+tax|\bwht\b")
_REPORT_SCRUB_RE = re.compile(
    r"(?i)\b("
    r"delivery\s+(?:note|slip)|shipping\s+address|address\s+block|"
    r"invoice\s+address|remove.{0,60}(?:customer|partner)\s+name|"
    r"(?:customer|partner)\s+name.{0,40}(?:removed|strip|scrub)|"
    r"qweb\s+(?:inherit|layout|report)"
    r")\b"
)
_PREFER_CONTACTS_RE = re.compile(
    r"(?i)\bprefer\s+for\s+delivery|delivery\s+notes?\s+on\s+contacts\b"
)
_NOTE_XPATH_RE = re.compile(
    r"""xpath\s+expr=["'][^"']*@name=["']note["'][^"']*["']""",
    re.I,
)
_FIELD_STRING_KW_RE = re.compile(
    r"""^\s*([a-zA-Z_][\w]*)\s*=\s*fields\.\w+\s*\(([^)]*)\)""",
    re.M,
)
_STRING_KW_RE = re.compile(r"""\bstring\s*=\s*['\"]([^'\"]+)['\"]""")


def is_sales_markup_prompt(prompt: str) -> bool:
    return bool(_MARKUP_RE.search(prompt or ""))


def is_report_layout_scrub_prompt(prompt: str) -> bool:
    """Document/report address scrub CLASS — not Contacts Prefer delivery-notes."""
    from app.ai_report_layout_scrub import is_report_layout_scrub_brief

    return is_report_layout_scrub_brief(prompt)


def report_layout_online_checklist(*, prompt: str = "", host_model: str = "") -> dict[str, Any]:
    """Online checklist IR for Studio report metadata path (not Python promote)."""
    from app.ai_class_stamp import apply_class_stamp, resolve_class_stamp

    host = host_model or "stock.picking"
    ir = {
        "intent_id": "report_layout_online_checklist",
        "host_model": host,
        "path": "studio_report_metadata",
        "checks": [
            {"id": "report_action_present", "required": True},
            {"id": "paperformat_ok", "required": False},
            {"id": "preview_renders", "required": True},
            {"id": "no_python_promote", "required": True},
        ],
        "operator_copy": (
            "Online lane: edit report layout via Reports / Studio metadata. "
            "QWeb partner-name scrub that needs inherit Python stays module lane "
            "(.sh / self-host) — Prefer must not steal as Contacts delivery-notes."
        ),
    }
    apply_class_stamp(
        ir,
        resolve_class_stamp(
            prompt=prompt,
            capability="",
            grain="field_pack",
            needs_module=False,
            inherit_only=False,
        ),
    )
    # Force report_layout + online for this checklist surface.
    ir["artifact_kind"] = "report_layout"
    ir["delivery_lane"] = "online_metadata"
    ir["prove_status"] = "not_required"
    return ir


def acceptance_for_draft(draft: dict[str, Any], *, prompt: str = "") -> dict[str, Any]:
    """Build the acceptance contract for an Option A authored draft."""
    text = (prompt or str(draft.get("_user_prompt") or "")).strip()
    host = _host_model(draft)
    if host == "sale.order" and is_sales_markup_prompt(text):
        return {
            "intent_id": "sale_order_markup_wht",
            "host_model": "sale.order",
            "checks": [
                {"id": "field_labeled", "required": True},
                {"id": "xpath_anchor", "required": True, "anchor": "tax_totals"},
                {"id": "price_effect", "required": True},
                {"id": "fields_present", "required": True},
            ],
        }
    if is_report_layout_scrub_prompt(text):
        from app.ai_report_layout_scrub import (
            REPORT_SCRUB_TARGETS,
            report_scrub_host_from_prompt,
            targets_for_host,
        )

        scrub_host = host if host in REPORT_SCRUB_TARGETS else report_scrub_host_from_prompt(text)
        # Prefer draft inherit when it is a commercial document host.
        if host in REPORT_SCRUB_TARGETS:
            scrub_host = host
        report_ids = [t["inherit_id"] for t in targets_for_host(scrub_host, prompt=text)]
        return {
            "intent_id": "report_layout_address_scrub",
            "host_model": scrub_host,
            "parameterized_reports": report_ids
            or [
                "stock.report_deliveryslip",
                "stock.report_picking",
                "account.report_invoice_document",
                "sale.report_saleorder_document",
            ],
            "checks": [
                {"id": "qweb_inherit_present", "required": True},
                {"id": "partner_name_scrubbed", "required": True},
                {"id": "address_block_preserved", "required": True},
                {"id": "not_contacts_prefer", "required": True},
            ],
            "fixtures": {
                "brief_class": "report_layout_scrub",
                "must_not_route": "contacts_prefer_delivery_notes",
                "host_model": scrub_host,
                "report_xmlids": report_ids,
            },
        }
    checks: list[dict[str, Any]] = [
        {"id": "field_labeled", "required": True},
        {"id": "fields_present", "required": True},
        {"id": "form_loads", "required": True},
    ]
    return {
        "intent_id": "option_a_generic",
        "host_model": host or "",
        "checks": checks,
    }


def stamp_option_a_acceptance(draft: dict[str, Any], *, prompt: str = "") -> dict[str, Any]:
    from app.ai_class_stamp import apply_class_stamp, resolve_class_stamp

    contract = acceptance_for_draft(draft, prompt=prompt)
    draft["_option_a_acceptance"] = contract
    ir = draft.get("_generation_engine")
    text = (prompt or str(draft.get("_user_prompt") or "")).strip()
    stamp = resolve_class_stamp(
        prompt=text,
        capability=str((ir or {}).get("capability") or "option_a_authored")
        if isinstance(ir, dict)
        else "option_a_authored",
        grain=str(draft.get("grain") or "full_app"),
        needs_module=True,
        gold_artifact_id=(ir or {}).get("gold_artifact_id") if isinstance(ir, dict) else None,
        module_delivery=True,
        prove_ok=None,
    )
    apply_class_stamp(contract, stamp)
    if isinstance(ir, dict):
        ir["option_a_acceptance"] = {
            "intent_id": contract.get("intent_id"),
            "host_model": contract.get("host_model"),
            "check_count": len(contract.get("checks") or []),
            "delivery_lane": contract.get("delivery_lane"),
            "artifact_kind": contract.get("artifact_kind"),
            "prove_status": contract.get("prove_status"),
        }
        apply_class_stamp(ir, stamp)
    return contract


def _host_model(draft: dict[str, Any]) -> str | None:
    for row in draft.get("models") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("mode") or "").lower() == "inherit":
            mid = str(row.get("model") or "").strip()
            if mid:
                return mid
    py = collect_draft_python_fields(draft)
    for mid in py:
        if not mid.startswith("x_"):
            return mid
    return None


def python_fields_missing_labels(draft: dict[str, Any]) -> list[str]:
    """Authored ``fields.*`` assignments without a human ``string=`` kwarg."""
    missing: list[str] = []
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = str(block.get("source_file") or "")
        if not path.endswith(".py"):
            continue
        content = str(block.get("content") or "")
        for m in _FIELD_STRING_KW_RE.finditer(content):
            fname = m.group(1)
            if fname.startswith("_") or not fname.startswith("x_"):
                continue
            args = m.group(2) or ""
            sm = _STRING_KW_RE.search(args)
            if not sm or not sm.group(1).strip():
                missing.append(fname)
                continue
            label = sm.group(1).strip()
            if label == fname or label.replace(" ", "_").lower() == fname.lower():
                missing.append(fname)
    return sorted(set(missing))


def draft_xpath_anchor_ok(draft: dict[str, Any], *, anchor: str = "tax_totals") -> dict[str, Any]:
    """True when sale inherit views anchor xpath on ``anchor``, not on ``note`` alone."""
    xml_blobs: list[str] = []
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = str(block.get("source_file") or "")
        kind = str(block.get("kind") or "")
        if path.endswith(".xml") or kind in {"xml", "qweb"}:
            xml_blobs.append(str(block.get("content") or ""))
    blob = "\n".join(xml_blobs)
    if not blob.strip():
        return {"ok": False, "detail": "no view XML"}
    has_anchor = bool(
        re.search(
            rf"""xpath\s+expr=["'][^"']*@name=["']{re.escape(anchor)}["']""",
            blob,
            flags=re.I,
        )
    )
    has_note_only = bool(_NOTE_XPATH_RE.search(blob)) and not has_anchor
    if has_note_only:
        return {
            "ok": False,
            "detail": "xpath anchors on note (Terms) — use tax_totals instead",
        }
    if "sale.order" in blob or "sale.view_order_form" in blob:
        if not has_anchor and _NOTE_XPATH_RE.search(blob):
            return {"ok": False, "detail": "note xpath without tax_totals"}
        if not has_anchor and "xpath" in blob.lower():
            return {
                "ok": False,
                "detail": f"sale.order inherit missing xpath @{anchor}",
            }
    return {"ok": True, "detail": "ok" if has_anchor else "no sale form xpath"}


def ensure_python_field_strings(content: str) -> str:
    """Add a default ``string=`` derived from the field name when missing."""

    def repl(m: re.Match[str]) -> str:
        fname = m.group(1)
        args = m.group(2) or ""
        full = m.group(0)
        if not fname.startswith("x_"):
            return full
        if _STRING_KW_RE.search(args):
            return full
        label = _label_from_fname(fname)
        insert = f"string={label!r}"
        # Append after positional comodel (Many2one/One2many) — never
        # `string=..., 'model'` which is a SyntaxError and blanks field extract.
        if args.strip():
            new_args = f"{args.strip()}, {insert}"
        else:
            new_args = insert
        return full[: m.start(2) - m.start(0)] + new_args + full[m.end(2) - m.start(0) :]

    return _FIELD_STRING_KW_RE.sub(repl, content or "")


def _label_from_fname(fname: str) -> str:
    bare = fname[2:] if fname.startswith("x_") else fname
    parts = [p for p in bare.split("_") if p]
    if not parts:
        return "Custom"
    if "percent" in bare.lower() or bare.lower().endswith("pct"):
        if "markup" in bare.lower():
            return "Markup %"
    return " ".join(
        p.upper() if p.lower() in {"wht", "qr", "id"} else p.capitalize() for p in parts
    )


def rewrite_note_xpath_to_tax_totals(content: str) -> str:
    """Retarget inherit xpaths that park custom fields on Terms (note)."""
    blob = content or ""
    if "note" not in blob.lower():
        return blob
    if "sale.order" not in blob and "sale.view_order_form" not in blob:
        return blob
    return re.sub(
        r"""(field\[@name=['\"])note(['\"])""",
        r"\1tax_totals\2",
        blob,
        flags=re.I,
    )


REPAIR_HINTS: dict[str, str] = {
    "field_labeled": (
        "Every x_* fields.* must set string='Human Label' (e.g. string='Markup %'). "
        "Never leave the technical name as the only label."
    ),
    "xpath_anchor": (
        "sale.order form inherit MUST xpath //field[@name='tax_totals'] position='before'. "
        "Do not insert next to note / Terms and Conditions."
    ),
    "price_effect": (
        "Choosing markup % must change the selling price: @api.onchange('x_markup_percent') "
        "setting order_line.price_unit from product.standard_price * (1 + pct/100), "
        "and/or x_markup_amount Monetary compute. Do not redefine stock _compute_amount."
    ),
    "fields_present": (
        "Declare x_* fields on the inherit model in Python and show them in the form arch."
    ),
    "form_loads": (
        "get_views/form must succeed — fix undefined arch fields and Python field defs."
    ),
}


def run_acceptance_smoke(
    draft: dict[str, Any],
    *,
    execute_kw: ExecuteKw,
) -> dict[str, Any]:
    """Execute stamped acceptance checks against a live sandbox RPC."""
    contract = draft.get("_option_a_acceptance")
    if not isinstance(contract, dict) or not contract.get("checks"):
        contract = stamp_option_a_acceptance(
            draft, prompt=str(draft.get("_user_prompt") or "")
        )
    checks_out: list[dict[str, Any]] = []
    ok = True
    host = str(contract.get("host_model") or _host_model(draft) or "")
    py_by_model = collect_draft_python_fields(draft)
    authored: set[str] = set()
    for mid, names in py_by_model.items():
        if not host or mid == host:
            authored.update(names)

    for row in contract.get("checks") or []:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "")
        required = bool(row.get("required", True))
        result = _run_one_check(
            cid,
            draft=draft,
            execute_kw=execute_kw,
            host=host,
            authored=authored,
            check_row=row,
        )
        checks_out.append(result)
        if required and not result.get("ok"):
            ok = False

    failed = [c for c in checks_out if not c.get("ok")]
    message = ""
    if failed:
        parts = [f"{c.get('id')}: {c.get('detail')}" for c in failed]
        message = "Acceptance smoke failed — " + "; ".join(parts)
    return {
        "ok": ok,
        "acceptance_ok": ok,
        "level": "acceptance",
        "checks": checks_out,
        "message": message,
        "intent_id": contract.get("intent_id"),
    }


def _run_one_check(
    cid: str,
    *,
    draft: dict[str, Any],
    execute_kw: ExecuteKw,
    host: str,
    authored: set[str],
    check_row: dict[str, Any],
) -> dict[str, Any]:
    hint = REPAIR_HINTS.get(cid, "")
    if cid == "field_labeled":
        return _check_field_labeled(execute_kw, host, authored, draft, hint)
    if cid == "xpath_anchor":
        anchor = str(check_row.get("anchor") or "tax_totals")
        live = _check_xpath_anchor_live(execute_kw, host, authored, anchor, hint)
        if live.get("ok") or live.get("detail") != "no_extension_views":
            return live
        static = draft_xpath_anchor_ok(draft, anchor=anchor)
        return {
            "id": "xpath_anchor",
            "ok": bool(static.get("ok")),
            "detail": static.get("detail"),
            "repair_hint": hint,
        }
    if cid == "price_effect":
        return _check_price_effect(execute_kw, host, authored, hint)
    if cid == "fields_present":
        return _check_fields_present(execute_kw, host, authored, hint)
    if cid == "form_loads":
        return _check_form_loads(execute_kw, host, hint)
    if cid in {
        "qweb_inherit_present",
        "partner_name_scrubbed",
        "address_block_preserved",
        "not_contacts_prefer",
    }:
        return _check_report_layout_scrub(cid, draft=draft, hint=hint)
    return {"id": cid, "ok": True, "detail": "unknown check skipped", "repair_hint": hint}


def _check_report_layout_scrub(
    cid: str,
    *,
    draft: dict[str, Any],
    hint: str,
) -> dict[str, Any]:
    from app.ai_report_layout_scrub import static_scrub_findings

    findings = static_scrub_findings(
        draft, prompt=str(draft.get("_user_prompt") or "")
    )
    key = cid
    ok = bool(findings.get(key))
    detail = "ok" if ok else f"failed — host={findings.get('host_model')} inherits={findings.get('inherit_ids')}"
    return {"id": cid, "ok": ok, "detail": detail, "repair_hint": hint, "findings": findings}


def _check_field_labeled(
    execute_kw: ExecuteKw,
    host: str,
    authored: set[str],
    draft: dict[str, Any],
    hint: str,
) -> dict[str, Any]:
    static_missing = python_fields_missing_labels(draft)
    if not host:
        return {
            "id": "field_labeled",
            "ok": not static_missing,
            "detail": (
                "ok"
                if not static_missing
                else f"missing string= on {', '.join(static_missing)}"
            ),
            "repair_hint": hint,
        }
    try:
        fg = execute_kw(host, "fields_get", [], {"attributes": ["string"]}) or {}
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "field_labeled",
            "ok": False,
            "detail": str(exc)[:200],
            "repair_hint": hint,
        }
    bad: list[str] = []
    for fname in sorted(authored):
        meta = fg.get(fname) if isinstance(fg.get(fname), dict) else None
        if not meta:
            continue
        label = str(meta.get("string") or "").strip()
        if not label or label == fname:
            bad.append(fname)
    for fname in static_missing:
        if fname not in bad:
            bad.append(fname)
    return {
        "id": "field_labeled",
        "ok": not bad,
        "detail": "ok" if not bad else f"unlabeled or technical-only: {', '.join(bad)}",
        "repair_hint": hint,
    }


def _check_fields_present(
    execute_kw: ExecuteKw,
    host: str,
    authored: set[str],
    hint: str,
) -> dict[str, Any]:
    if not host or not authored:
        return {
            "id": "fields_present",
            "ok": bool(authored),
            "detail": "ok" if authored else "no authored x_* fields",
            "repair_hint": hint,
        }
    try:
        fg = execute_kw(host, "fields_get", [], {"attributes": ["string"]}) or {}
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "fields_present",
            "ok": False,
            "detail": str(exc)[:200],
            "repair_hint": hint,
        }
    missing = sorted(f for f in authored if f not in fg)
    return {
        "id": "fields_present",
        "ok": not missing,
        "detail": "ok" if not missing else f"absent after install: {', '.join(missing)}",
        "repair_hint": hint,
    }


def _check_form_loads(execute_kw: ExecuteKw, host: str, hint: str) -> dict[str, Any]:
    if not host:
        return {"id": "form_loads", "ok": True, "detail": "no host", "repair_hint": hint}
    try:
        execute_kw(
            host,
            "get_views",
            [],
            {"views": [(False, "form")], "options": {"toolbar": False}},
        )
        return {"id": "form_loads", "ok": True, "detail": "get_views ok", "repair_hint": hint}
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "form_loads",
            "ok": False,
            "detail": str(exc)[:240],
            "repair_hint": hint,
        }


def _check_xpath_anchor_live(
    execute_kw: ExecuteKw,
    host: str,
    authored: set[str],
    anchor: str,
    hint: str,
) -> dict[str, Any]:
    if not host:
        return {
            "id": "xpath_anchor",
            "ok": False,
            "detail": "no host",
            "repair_hint": hint,
        }
    try:
        views = (
            execute_kw(
                "ir.ui.view",
                "search_read",
                [[("model", "=", host), ("mode", "=", "extension")]],
                {"fields": ["id", "name", "arch_db"], "limit": 40},
            )
            or []
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "xpath_anchor",
            "ok": False,
            "detail": str(exc)[:200],
            "repair_hint": hint,
        }
    ours: list[str] = []
    for view in views:
        arch = str(view.get("arch_db") or view.get("arch") or "")
        if any(f'name="{f}"' in arch or f"name='{f}'" in arch for f in authored):
            ours.append(arch)
        elif "x_" in arch and ("markup" in arch.lower() or "wht" in arch.lower()):
            ours.append(arch)
    if not ours:
        return {
            "id": "xpath_anchor",
            "ok": False,
            "detail": "no_extension_views",
            "repair_hint": hint,
        }
    blob = "\n".join(ours)
    if ("name=\"note\"" in blob or "name='note'" in blob) and not (
        f'name="{anchor}"' in blob or f"name='{anchor}'" in blob
    ):
        return {
            "id": "xpath_anchor",
            "ok": False,
            "detail": "extension near note without tax_totals",
            "repair_hint": hint,
        }
    return {
        "id": "xpath_anchor",
        "ok": True,
        "detail": f"extension present (near {anchor} or resolved)",
        "repair_hint": hint,
    }


def _check_price_effect(
    execute_kw: ExecuteKw,
    host: str,
    authored: set[str],
    hint: str,
) -> dict[str, Any]:
    if host != "sale.order":
        return {
            "id": "price_effect",
            "ok": True,
            "detail": "skipped (not sale.order)",
            "repair_hint": hint,
        }
    markup_fields = [f for f in authored if "markup" in f.lower() and "percent" in f.lower()]
    if not markup_fields:
        markup_fields = [f for f in authored if f.startswith("x_markup")]
    amount_fields = [
        f
        for f in authored
        if "markup" in f.lower()
        and any(k in f.lower() for k in ("amount", "value", "total"))
        and "percent" not in f.lower()
    ]
    try:
        product_id = execute_kw(
            "product.product",
            "create",
            [
                {
                    "name": "Acceptance Markup Probe",
                    "list_price": 100.0,
                    "standard_price": 100.0,
                    "type": "consu",
                }
            ],
        )
        order_id = execute_kw(
            "sale.order",
            "create",
            [{"partner_id": _demo_partner_id(execute_kw)}],
        )
        line_id = execute_kw(
            "sale.order.line",
            "create",
            [
                {
                    "order_id": order_id,
                    "product_id": product_id,
                    "product_uom_qty": 1.0,
                    "price_unit": 100.0,
                }
            ],
        )
        before = execute_kw(
            "sale.order.line",
            "read",
            [[line_id], ["price_unit"]],
        )
        before_price = float((before or [{}])[0].get("price_unit") or 0)
        pct = 15.0
        write_vals: dict[str, Any] = {}
        fg = (
            execute_kw("sale.order", "fields_get", [], {"attributes": ["type", "selection"]})
            or {}
        )
        for fname in markup_fields:
            meta = fg.get(fname) or {}
            ttype = str(meta.get("type") or "")
            if ttype == "selection":
                sel = meta.get("selection") or []
                key = None
                for pair in sel:
                    if isinstance(pair, (list, tuple)) and pair:
                        if str(pair[0]) in {"15", "15.0"} or "15" in str(pair[0]):
                            key = pair[0]
                            break
                write_vals[fname] = key if key is not None else (sel[0][0] if sel else "15")
            else:
                write_vals[fname] = pct
        if not write_vals:
            return {
                "id": "price_effect",
                "ok": False,
                "detail": "no markup percent field on sale.order",
                "repair_hint": hint,
            }
        execute_kw("sale.order", "write", [[order_id], write_vals])
        try:
            execute_kw(
                "sale.order",
                "onchange",
                [[order_id], write_vals, list(write_vals.keys()), {}],
            )
        except Exception:  # noqa: BLE001
            pass
        after_line = execute_kw(
            "sale.order.line",
            "read",
            [[line_id], ["price_unit"]],
        )
        after_price = float((after_line or [{}])[0].get("price_unit") or 0)
        order_read_fields = list(amount_fields) + list(markup_fields)
        order_row: dict[str, Any] = {}
        if order_read_fields:
            order_row = (
                execute_kw("sale.order", "read", [[order_id], order_read_fields]) or [{}]
            )[0]

        expected = before_price * (1.0 + pct / 100.0)
        price_ok = abs(after_price - expected) <= 0.05 or after_price > before_price + 0.01
        amount_ok = False
        for af in amount_fields:
            try:
                val = float(order_row.get(af) or 0)
            except (TypeError, ValueError):
                continue
            if abs(val - (before_price * pct / 100.0)) <= 0.05 or val > 0.01:
                amount_ok = True
                break
        passed = bool(price_ok or amount_ok)
        detail = (
            f"price {before_price}→{after_price} expected~{expected:.2f}; "
            f"amount_fields={ {k: order_row.get(k) for k in amount_fields} }"
        )
        return {
            "id": "price_effect",
            "ok": passed,
            "detail": detail if passed else f"no price/markup effect — {detail}",
            "repair_hint": hint,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "price_effect",
            "ok": False,
            "detail": str(exc)[:240],
            "repair_hint": hint,
        }


def _demo_partner_id(execute_kw: ExecuteKw) -> int:
    ids = execute_kw("res.partner", "search", [[("name", "ilike", "Azure")]], {"limit": 1})
    if ids:
        return int(ids[0])
    ids = execute_kw("res.partner", "search", [[("customer_rank", ">", 0)]], {"limit": 1})
    if ids:
        return int(ids[0])
    ids = execute_kw("res.partner", "search", [[]], {"limit": 1})
    if ids:
        return int(ids[0])
    return int(execute_kw("res.partner", "create", [{"name": "Acceptance Partner"}]))


__all__ = [
    "REPAIR_HINTS",
    "acceptance_for_draft",
    "draft_xpath_anchor_ok",
    "ensure_python_field_strings",
    "is_sales_markup_prompt",
    "is_report_layout_scrub_prompt",
    "report_layout_online_checklist",
    "python_fields_missing_labels",
    "rewrite_note_xpath_to_tax_totals",
    "run_acceptance_smoke",
    "stamp_option_a_acceptance",
]
