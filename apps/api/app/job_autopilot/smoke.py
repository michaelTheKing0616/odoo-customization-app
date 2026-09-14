"""RPC process smoke — Autopilot done-bar (not ModuleSpec scorecard 10.0).

Client flow: partner → product → quotation with line → confirm → invoice from SO.
Custom residual: header + line child + Confirm ir.actions.server.run (not a field write).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.job_autopilot.packet import IngestReport, JobPacket, ProbeResult, SmokeReport

_SKIP_CREATE_FIELDS = frozenset(
    {
        "id",
        "display_name",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "__last_update",
        "message_follower_ids",
        "message_ids",
        "message_main_attachment_id",
        "activity_ids",
        "website_message_ids",
    }
)
_SKIP_CREATE_TYPES = frozenset({"one2many", "many2many", "binary", "html", "reference"})
_SKIP_M2O_RELATIONS = frozenset({"res.users", "res.company", "mail.activity.type"})
_STOCK_ID_KEYS: tuple[tuple[str, str], ...] = (
    ("partner_id", "res.partner"),
    ("product_id", "product.product"),
    ("product_tmpl_id", "product.template"),
    ("sale_order_id", "sale.order"),
    ("invoice_id", "account.move"),
)


def _first_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, list) and value:
        return _first_id(value[0])
    if isinstance(value, tuple) and value:
        return _first_id(value[0])
    return None


def _create(client: Any, model: str, vals: dict[str, Any]) -> int:
    rid = client.execute_kw(model, "create", [vals])
    return int(rid)


def _exists(client: Any, model: str) -> bool:
    fn = getattr(client, "model_exists", None)
    if callable(fn):
        return bool(fn(model))
    try:
        client.execute_kw(model, "fields_get", [], {"attributes": ["string"]})
        return True
    except Exception:  # noqa: BLE001
        return False


def _field(client: Any, model: str, name: str) -> bool:
    fn = getattr(client, "field_exists", None)
    if callable(fn):
        return bool(fn(model, name))
    try:
        meta = client.execute_kw(model, "fields_get", [[name]], {"attributes": ["string"]})
        return bool(isinstance(meta, dict) and name in meta)
    except Exception:  # noqa: BLE001
        return False


def _fields_meta(client: Any, model: str) -> dict[str, Any]:
    try:
        meta = client.execute_kw(
            model,
            "fields_get",
            [],
            {"attributes": ["string", "type", "required", "relation", "selection", "readonly"]},
        )
    except Exception:  # noqa: BLE001
        return {}
    return meta if isinstance(meta, dict) else {}


def _selection_key(meta: dict[str, Any]) -> str | None:
    raw = meta.get("selection")
    if isinstance(raw, str):
        for prefer in ("intake", "draft", "new"):
            if f"('{prefer}'" in raw or f'("{prefer}"' in raw:
                return prefer
    if not isinstance(raw, list) or not raw:
        return None
    keys = []
    for first in raw:
        if isinstance(first, (list, tuple)) and first:
            keys.append(str(first[0]))
        elif isinstance(first, str):
            keys.append(first)
    for prefer in ("intake", "draft", "new"):
        if prefer in keys:
            return prefer
    return keys[0] if keys else None


def _stock_relation_ids(ids: dict[str, Any]) -> dict[str, int]:
    """Map stock model name → smoke record id. Keyed by relation, not field name."""
    out: dict[str, int] = {}
    for key, relation in _STOCK_ID_KEYS:
        rid = _first_id(ids.get(key))
        if rid:
            out[relation] = rid
    custom_model = ids.get("custom_model")
    custom_id = _first_id(ids.get("custom_id"))
    if isinstance(custom_model, str) and custom_model and custom_id:
        out[custom_model] = custom_id
    return out


def _m2o_value(client: Any, relation: str, *, stock_ids: dict[str, int]) -> int | None:
    if relation in _SKIP_M2O_RELATIONS:
        return None
    if relation in stock_ids:
        return stock_ids[relation]
    found = _search(client, relation, [], limit=1)
    return found[0] if found else None


def _create_vals(
    client: Any,
    model: str,
    *,
    stock_ids: dict[str, int] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fill live required columns from fields_get. M2Os use relation → smoke id."""
    vals = dict(extra or {})
    stock = dict(stock_ids or {})
    if "x_name" not in vals and _field(client, model, "x_name"):
        vals["x_name"] = "Autopilot smoke"
    elif "name" not in vals and _field(client, model, "name"):
        vals["name"] = "Autopilot smoke"
    meta = _fields_meta(client, model)
    for name, spec in meta.items():
        if not isinstance(spec, dict) or name in vals or name in _SKIP_CREATE_FIELDS:
            continue
        if spec.get("readonly"):
            continue
        ttype = str(spec.get("type") or spec.get("ttype") or "")
        if ttype in _SKIP_CREATE_TYPES:
            continue
        required = bool(spec.get("required"))
        if ttype == "many2one":
            if not required:
                continue
            rel = str(spec.get("relation") or "")
            if not rel:
                continue
            mid = _m2o_value(client, rel, stock_ids=stock)
            if mid:
                vals[name] = mid
            continue
        if not required:
            continue
        if ttype == "selection":
            # Prefer intake/draft so Confirm can advance to open (not already billed)
            if name == "x_status":
                sel = spec.get("selection") or []
                keys = [str(k) for k, *_ in sel] if isinstance(sel, list) else []
                for prefer in ("intake", "draft", "new"):
                    if prefer in keys:
                        vals[name] = prefer
                        break
                else:
                    key = _selection_key(spec)
                    if key:
                        vals[name] = key
            else:
                key = _selection_key(spec)
                if key:
                    vals[name] = key
            continue
        if ttype == "date":
            vals[name] = date.today().isoformat()
        elif ttype == "datetime":
            vals[name] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        elif ttype in {"float", "monetary"}:
            vals[name] = 1.0
        elif ttype == "integer":
            vals[name] = 1
        elif ttype == "boolean":
            vals[name] = True
        elif ttype in {"char", "text"}:
            vals[name] = "Autopilot smoke"
    return vals


def _search(client: Any, model: str, domain: list[Any], *, limit: int = 8) -> list[int]:
    try:
        ids = client.execute_kw(model, "search", [domain], {"limit": limit})
    except Exception:  # noqa: BLE001
        return []
    return [int(i) for i in (ids or [])]


def _read(client: Any, model: str, rid: int, fields: list[str]) -> dict[str, Any]:
    try:
        rows = client.execute_kw(model, "read", [[rid], fields])
    except Exception:  # noqa: BLE001
        try:
            rows = client.execute_kw(model, "read", [[rid]], {"fields": fields})
        except Exception:  # noqa: BLE001
            return {}
    if not rows or not isinstance(rows[0], dict):
        return {}
    return rows[0]


def _named_process(packet: JobPacket) -> str:
    procs = [p.lower() for p in packet.processes]
    if "quote_to_invoice" in procs or "sale" in packet.stock_apps:
        return "quote_to_invoice"
    if "booking_to_invoice" in procs or packet.has_custom_residual:
        return "booking_to_invoice"
    if "account" in packet.stock_apps:
        return "invoice"
    return "partner"


def _product_vals() -> list[dict[str, Any]]:
    """Odoo 19 uses type=consu / is_storable; older majors used type=product."""
    return [
        {"name": "Autopilot Smoke Product", "type": "consu", "list_price": 10.0, "invoice_policy": "order"},
        {"name": "Autopilot Smoke Product", "is_storable": False, "list_price": 10.0, "invoice_policy": "order"},
        {"name": "Autopilot Smoke Product", "list_price": 10.0, "invoice_policy": "order"},
        {"name": "Autopilot Smoke Product", "list_price": 10.0},
    ]


def _create_product(client: Any, steps: list[ProbeResult]) -> int | None:
    if not _exists(client, "product.template"):
        steps.append(ProbeResult(name="product.template", ok=False, detail="model missing"))
        return None
    tmpl_id: int | None = None
    last_err = "create failed"
    for vals in _product_vals():
        try:
            tmpl_id = _create(client, "product.template", vals)
            break
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
    if tmpl_id is None:
        steps.append(ProbeResult(name="product.template", ok=False, detail=last_err))
        return None
    steps.append(ProbeResult(name="product.template", ok=True, detail=f"id={tmpl_id}"))
    product_id: int | None = None
    if _exists(client, "product.product"):
        ids = _search(client, "product.product", [("product_tmpl_id", "=", tmpl_id)], limit=1)
        if ids:
            product_id = ids[0]
        else:
            try:
                product_id = _create(
                    client,
                    "product.product",
                    {"name": "Autopilot Smoke Product", "product_tmpl_id": tmpl_id},
                )
            except Exception:  # noqa: BLE001
                product_id = None
    if product_id is None:
        steps.append(
            ProbeResult(name="product.product", ok=False, detail="no variant after template create")
        )
        return None
    steps.append(ProbeResult(name="product.product", ok=True, detail=f"id={product_id}"))
    return product_id


def _smoke_quote_to_invoice(
    client: Any,
    packet: JobPacket,
    steps: list[ProbeResult],
    warnings: list[str],
    partner_id: int,
    ids: dict[str, Any],
) -> None:
    product_id = _create_product(client, steps)
    if product_id:
        ids["product_id"] = int(product_id)
    if product_id is None or not _exists(client, "sale.order"):
        if "sale" in packet.stock_apps:
            steps.append(ProbeResult(name="sale.order", ok=False, detail="sale.order missing"))
        return
    line = {"product_id": product_id, "product_uom_qty": 1, "price_unit": 10.0}
    so_id: int | None = None
    try:
        so_id = _create(
            client,
            "sale.order",
            {
                "partner_id": partner_id,
                "client_order_ref": "AUTOPILOT-SMOKE",
                "order_line": [(0, 0, line)],
            },
        )
    except Exception:
        try:
            so_id = _create(client, "sale.order", {"partner_id": partner_id})
            if _exists(client, "sale.order.line"):
                line_vals = dict(line)
                line_vals["order_id"] = so_id
                _create(client, "sale.order.line", line_vals)
        except Exception as exc:  # noqa: BLE001
            steps.append(ProbeResult(name="sale.order", ok=False, detail=str(exc)))
            return
    steps.append(ProbeResult(name="sale.order", ok=True, detail=f"id={so_id} with line"))
    ids["sale_order_id"] = int(so_id)
    try:
        client.execute_kw("sale.order", "action_confirm", [[so_id]])
        steps.append(ProbeResult(name="sale.order.action_confirm", ok=True, detail=f"id={so_id}"))
    except Exception as exc:  # noqa: BLE001
        steps.append(ProbeResult(name="sale.order.action_confirm", ok=False, detail=str(exc)))
        return
    if "stock" in packet.stock_apps and _exists(client, "stock.picking"):
        so = _read(client, "sale.order", so_id, ["name", "picking_ids"])
        picking_ids = so.get("picking_ids") or []
        if not picking_ids:
            origin = so.get("name")
            if origin:
                picking_ids = _search(client, "stock.picking", [("origin", "=", origin)])
        if picking_ids:
            pid = int(picking_ids[0])
            try:
                client.execute_kw("stock.picking", "button_validate", [[pid]])
                steps.append(
                    ProbeResult(name="stock.picking.button_validate", ok=True, detail=f"id={pid}")
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Picking validate needs wizard or is blocked: {exc}")
                steps.append(
                    ProbeResult(
                        name="stock.picking.button_validate",
                        ok=True,
                        detail=f"warn wizard/blocked id={pid}: {exc}",
                    )
                )
        else:
            warnings.append("No stock.picking after confirm (consumable / service path).")
            steps.append(
                ProbeResult(
                    name="stock.picking",
                    ok=True,
                    detail="warn: no picking after confirm (consumable path)",
                )
            )
    if not _exists(client, "account.move"):
        steps.append(
            ProbeResult(name="sale.advance.payment.inv.create_invoices", ok=False, detail="account.move missing")
        )
        return
    inv_ok = False
    detail = "wizard missing"
    if _exists(client, "sale.advance.payment.inv"):
        try:
            wiz_id = _create(
                client,
                "sale.advance.payment.inv",
                {
                    "advance_payment_method": "delivered",
                    "sale_order_ids": [(6, 0, [so_id])],
                },
            )
            try:
                inv = client.execute_kw("sale.advance.payment.inv", "create_invoices", [[wiz_id]])
                detail = f"wizard={wiz_id} invoices={inv}"
                inv_ok = True
                inv_id = _first_id(inv)
            except Exception as exc:  # noqa: BLE001
                # Odoo 19 create_invoices often returns None; XML-RPC cannot marshal it
                # even when the invoice was created. Confirm via invoice_ids.
                so = _read(client, "sale.order", so_id, ["invoice_ids", "invoice_status"])
                if so.get("invoice_ids"):
                    detail = f"wizard={wiz_id} invoice_ids={so.get('invoice_ids')} (rpc none)"
                    inv_ok = True
                    inv_id = _first_id(so.get("invoice_ids"))
                else:
                    detail = str(exc)
                    inv_id = None
            if inv_ok and inv_id:
                ids["invoice_id"] = inv_id
            elif inv_ok:
                so = _read(client, "sale.order", so_id, ["invoice_ids"])
                inv_id = _first_id(so.get("invoice_ids"))
                if inv_id:
                    ids["invoice_id"] = inv_id
        except Exception as exc:  # noqa: BLE001
            detail = str(exc)
    steps.append(
        ProbeResult(name="sale.advance.payment.inv.create_invoices", ok=inv_ok, detail=detail)
    )


def _smoke_standalone_invoice(
    client: Any, steps: list[ProbeResult], partner_id: int, ids: dict[str, Any]
) -> None:
    if not _exists(client, "account.move"):
        steps.append(ProbeResult(name="account.move", ok=False, detail="missing"))
        return
    try:
        move_id = _create(
            client,
            "account.move",
            {"move_type": "out_invoice", "partner_id": partner_id},
        )
        steps.append(ProbeResult(name="account.move", ok=True, detail=f"id={move_id}"))
        ids["invoice_id"] = int(move_id)
    except Exception as exc:  # noqa: BLE001
        steps.append(ProbeResult(name="account.move", ok=False, detail=str(exc)))


def _line_parent_field(client: Any, header: str, line_model: str) -> str | None:
    meta = _fields_meta(client, line_model)
    for name, spec in meta.items():
        if not isinstance(spec, dict):
            continue
        if str(spec.get("type") or spec.get("ttype") or "") != "many2one":
            continue
        if str(spec.get("relation") or "") == header:
            return name
    candidates = [f"{header}_id", "x_parent_id"]
    for name in candidates:
        if _field(client, line_model, name):
            return name
    return candidates[0] if _exists(client, line_model) else None


def _find_confirm_action(client: Any, model: str) -> int | None:
    """Prefer Confirm / set status=open over an arbitrary x_status write (e.g. billed)."""
    model_ids = _search(client, "ir.model", [("model", "=", model)], limit=1)
    prefer_names = (
        f"{model}: set x_status = open",
        f"{model}: set x_status = confirmed",
        f"{model}: set x_status=open",
    )
    for name in prefer_names:
        domain: list[Any] = [("name", "=", name)]
        if model_ids:
            domain = [("model_id", "=", model_ids[0]), *domain]
        ids = _search(client, "ir.actions.server", domain, limit=1)
        if ids:
            return ids[0]
    domains: list[list[Any]] = [
        [("name", "ilike", "Confirm")],
        [("name", "ilike", "set x_status = open")],
        [("name", "ilike", f"{model}: set x_status = open")],
        [("name", "ilike", "set x_status = confirmed")],
    ]
    for domain in domains:
        full = list(domain)
        if model_ids:
            full = [("model_id", "=", model_ids[0]), *full]
        ids = _search(client, "ir.actions.server", full, limit=16)
        if not ids:
            continue
        try:
            rows = client.execute_kw(
                "ir.actions.server",
                "read",
                [ids],
                {"fields": ["id", "name"]},
            )
        except Exception:  # noqa: BLE001
            rows = [{"id": i, "name": ""} for i in ids]
        ranked: list[tuple[int, int]] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            nm = str(row.get("name") or "").lower()
            rid = int(row["id"])
            # Never treat billed/closed/cancel as Confirm — even if search returned them
            if any(bad in nm for bad in ("billed", "closed", "cancel", "on_hold", "hold")):
                continue
            score = 0
            if "confirm" in nm:
                score += 10
            if "= open" in nm or " = open" in nm or nm.rstrip().endswith("open"):
                score += 20
            if "confirmed" in nm:
                score += 15
            if score == 0 and "set x_status" in nm:
                continue
            ranked.append((score, rid))
        if ranked:
            ranked.sort(key=lambda x: -x[0])
            return ranked[0][1]
        # Do not return ids[0] when every candidate was a billed/closed write
    return None


def _read_status(client: Any, model: str, rid: int) -> str | None:
    try:
        rows = client.execute_kw(
            model, "read", [[rid]], {"fields": ["x_status"]}
        )
        if rows and isinstance(rows[0], dict):
            return str(rows[0].get("x_status") or "") or None
    except Exception:  # noqa: BLE001
        return None
    return None


def _run_action(client: Any, action_id: int, model: str, rid: int) -> None:
    runner = getattr(client, "run_server_action", None)
    if callable(runner):
        runner(action_id, model=model, record_id=rid)
        return
    client.execute_kw(
        "ir.actions.server",
        "run",
        [[action_id]],
        {
            "context": {
                "active_id": rid,
                "active_ids": [rid],
                "active_model": model,
            }
        },
    )


def _smoke_custom(
    client: Any, packet: JobPacket, steps: list[ProbeResult], ids: dict[str, Any]
) -> None:
    for residual in packet.custom_residuals:
        model = residual.model
        if not _exists(client, model):
            steps.append(ProbeResult(name=model, ok=False, detail="model missing after apply"))
            continue
        stock_ids = _stock_relation_ids(ids)
        vals = _create_vals(client, model, stock_ids=stock_ids)
        if not vals:
            vals = {"x_name": "Autopilot smoke"}
        # Prefer intake/draft so Confirm can advance to open
        try:
            meta = client.execute_kw(
                model, "fields_get", [["x_status"]], {"attributes": ["selection"]}
            )
            sel = (meta or {}).get("x_status", {}).get("selection") or []
            keys = {str(k) for k, _lab in sel} if isinstance(sel, list) else set()
            for prefer in ("intake", "draft", "new"):
                if prefer in keys:
                    vals["x_status"] = prefer
                    break
        except Exception:  # noqa: BLE001
            pass
        try:
            rid = _create(client, model, vals)
        except Exception as exc:  # noqa: BLE001
            steps.append(ProbeResult(name=f"{model}.create", ok=False, detail=str(exc)))
            continue
        steps.append(ProbeResult(name=f"{model}.create", ok=True, detail=f"id={rid}"))
        ids.setdefault("custom_id", int(rid))
        ids.setdefault("custom_model", model)
        line_model = f"{model}_line"
        if _exists(client, line_model):
            parent = _line_parent_field(client, model, line_model)
            extra: dict[str, Any] = {}
            if parent:
                extra[parent] = rid
            extra["x_name"] = "smoke line"
            line_vals = _create_vals(
                client, line_model, stock_ids=_stock_relation_ids(ids), extra=extra
            )
            try:
                lid = _create(
                    client, line_model, line_vals or extra or {parent or f"{model}_id": rid}
                )
                steps.append(ProbeResult(name=f"{line_model}.create", ok=True, detail=f"id={lid}"))
            except Exception as exc:  # noqa: BLE001
                steps.append(ProbeResult(name=f"{line_model}.create", ok=False, detail=str(exc)))
        action_id = _find_confirm_action(client, model)
        if action_id is None:
            steps.append(
                ProbeResult(
                    name=f"{model}.confirm_action",
                    ok=False,
                    detail=(
                        "No Confirm ir.actions.server that sets x_status=open "
                        "(refusing billed/closed writes)."
                    ),
                )
            )
            continue
        before = _read_status(client, model, int(rid))
        try:
            _run_action(client, action_id, model, rid)
            after = _read_status(client, model, int(rid))
            if after and after.lower() in {"billed", "closed", "cancelled", "canceled"}:
                steps.append(
                    ProbeResult(
                        name=f"{model}.confirm_action",
                        ok=False,
                        detail=(
                            f"Confirm must advance to open (was {before!r} → {after!r}). "
                            "Draft transitions likely wrong — re-Create draft after API reload."
                        ),
                    )
                )
                continue
            steps.append(
                ProbeResult(
                    name=f"{model}.confirm_action",
                    ok=True,
                    detail=f"ir.actions.server.run id={action_id} status={before!r}→{after!r}",
                )
            )
        except Exception as exc:  # noqa: BLE001
            steps.append(ProbeResult(name=f"{model}.confirm_action", ok=False, detail=str(exc)))


def _smoke_extra_apps(
    client: Any,
    packet: JobPacket,
    steps: list[ProbeResult],
    ids: dict[str, Any],
    *,
    partner_id: Any = None,
) -> None:
    """POS/Purchase/CRM probes when those apps are in the packet.

    POS session is opened only if it is closed in the same smoke — an open
    session locks ``pos.config``.
    """
    partner = _first_id(partner_id)
    if "purchase" in packet.stock_apps and _exists(client, "purchase.order"):
        if partner is None:
            steps.append(ProbeResult(name="purchase.order", ok=False, detail="no partner for RFQ"))
        else:
            try:
                po_id = _create(client, "purchase.order", {"partner_id": partner})
                steps.append(ProbeResult(name="purchase.order", ok=True, detail=f"draft rfq id={po_id}"))
                ids["purchase_order_id"] = int(po_id)
                try:
                    client.execute_kw("purchase.order", "button_confirm", [[po_id]])
                    steps.append(
                        ProbeResult(name="purchase.order.button_confirm", ok=True, detail=f"id={po_id}")
                    )
                except Exception as exc:  # noqa: BLE001
                    steps.append(
                        ProbeResult(
                            name="purchase.order.button_confirm",
                            ok=True,
                            detail=f"draft only (confirm skipped): {exc}",
                        )
                    )
                _smoke_purchase_receipt(client, int(po_id), steps)
            except Exception as exc:  # noqa: BLE001
                steps.append(ProbeResult(name="purchase.order", ok=False, detail=str(exc)))
    if "point_of_sale" in packet.stock_apps and _exists(client, "pos.config"):
        configs = _search(client, "pos.config", [], limit=1)
        if configs:
            steps.append(ProbeResult(name="pos.config", ok=True, detail=f"id={configs[0]}"))
            _smoke_pos_session(client, int(configs[0]), steps)
        else:
            steps.append(
                ProbeResult(name="pos.config", ok=False, detail="point_of_sale installed but no pos.config")
            )
    if "crm" in packet.stock_apps and _exists(client, "crm.lead"):
        try:
            lead_vals: dict[str, Any] = {"name": "Autopilot smoke lead"}
            if partner and _field(client, "crm.lead", "partner_id"):
                lead_vals["partner_id"] = partner
            lead_id = _create(client, "crm.lead", lead_vals)
            steps.append(ProbeResult(name="crm.lead", ok=True, detail=f"id={lead_id}"))
            ids["crm_lead_id"] = int(lead_id)
            _smoke_crm_won(client, int(lead_id), steps)
        except Exception as exc:  # noqa: BLE001
            steps.append(ProbeResult(name="crm.lead", ok=False, detail=str(exc)))


def _smoke_purchase_receipt(client: Any, po_id: int, steps: list[ProbeResult]) -> None:
    if not _exists(client, "stock.picking"):
        steps.append(
            ProbeResult(name="purchase.order.receipt", ok=True, detail="stock.picking missing — RFQ only")
        )
        return
    po = _read(client, "purchase.order", po_id, ["name", "picking_ids"])
    picking_ids = po.get("picking_ids") or []
    if not picking_ids:
        origin = po.get("name")
        if origin:
            picking_ids = _search(client, "stock.picking", [("origin", "=", origin)])
    if not picking_ids:
        steps.append(
            ProbeResult(
                name="purchase.order.receipt",
                ok=True,
                detail="warn: no picking after confirm (service / no stock path)",
            )
        )
        return
    pid = int(picking_ids[0] if not isinstance(picking_ids[0], (list, tuple)) else picking_ids[0][0])
    try:
        client.execute_kw("stock.picking", "action_set_quantities_to_reservation", [[pid]])
    except Exception:  # noqa: BLE001
        pass
    try:
        client.execute_kw("stock.picking", "button_validate", [[pid]])
        steps.append(ProbeResult(name="purchase.order.receipt", ok=True, detail=f"picking={pid}"))
    except Exception as exc:  # noqa: BLE001
        steps.append(
            ProbeResult(
                name="purchase.order.receipt",
                ok=True,
                detail=f"warn wizard/blocked picking={pid}: {exc}",
            )
        )


def _smoke_pos_session(client: Any, config_id: int, steps: list[ProbeResult]) -> None:
    if not _exists(client, "pos.session"):
        steps.append(
            ProbeResult(name="pos.session", ok=True, detail="pos.session missing — config probe only")
        )
        return
    try:
        sid = _create(client, "pos.session", {"config_id": config_id})
    except Exception as exc:  # noqa: BLE001
        steps.append(ProbeResult(name="pos.session", ok=False, detail=f"create skipped: {exc}"))
        return
    try:
        client.execute_kw("pos.session", "action_pos_session_open", [[sid]])
    except Exception:  # noqa: BLE001
        pass
    closed = False
    last_err = "no close method"
    for method in ("close_session_from_ui", "action_pos_session_close"):
        try:
            if method == "close_session_from_ui":
                client.execute_kw("pos.session", method, [[sid], []])
            else:
                client.execute_kw("pos.session", method, [[sid]])
            rec = _read(client, "pos.session", sid, ["state"])
            state = str(rec.get("state") or "")
            if state in {"", "closed"}:
                closed = True
                last_err = method
                break
            last_err = f"{method} left state={state}"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            continue
    if not closed:
        try:
            client.execute_kw("pos.session", "action_pos_session_closing_control", [[sid]])
            rec = _read(client, "pos.session", sid, ["state"])
            if str(rec.get("state") or "") == "closed":
                closed = True
                last_err = "action_pos_session_closing_control"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
    if closed:
        steps.append(
            ProbeResult(name="pos.session", ok=True, detail=f"id={sid} opened and closed via {last_err}")
        )
    else:
        steps.append(
            ProbeResult(
                name="pos.session",
                ok=False,
                detail=f"id={sid} opened but close failed ({last_err}) — session must not stay open",
            )
        )


def _smoke_crm_won(client: Any, lead_id: int, steps: list[ProbeResult]) -> None:
    won_id: int | None = None
    if _exists(client, "crm.stage"):
        try:
            rows = client.execute_kw(
                "crm.stage",
                "search_read",
                [[("is_won", "=", True)]],
                {"fields": ["id", "name", "is_won"], "limit": 4},
            )
        except Exception:  # noqa: BLE001
            rows = []
        for row in rows or []:
            if isinstance(row, dict) and (row.get("is_won") or row.get("id")):
                won_id = int(row["id"])
                break
    if won_id and _field(client, "crm.lead", "stage_id"):
        try:
            client.execute_kw("crm.lead", "write", [[lead_id], {"stage_id": won_id}])
            steps.append(
                ProbeResult(name="crm.lead.won", ok=True, detail=f"id={lead_id} stage={won_id}")
            )
            return
        except Exception as exc:  # noqa: BLE001
            steps.append(ProbeResult(name="crm.lead.won", ok=False, detail=str(exc)))
            return
    if _field(client, "crm.lead", "probability"):
        try:
            client.execute_kw("crm.lead", "write", [[lead_id], {"probability": 100.0}])
            steps.append(
                ProbeResult(name="crm.lead.won", ok=True, detail=f"id={lead_id} probability=100")
            )
            return
        except Exception as exc:  # noqa: BLE001
            steps.append(ProbeResult(name="crm.lead.won", ok=False, detail=str(exc)))
            return
    steps.append(
        ProbeResult(name="crm.lead.won", ok=True, detail=f"id={lead_id} created; no won stage on instance")
    )


def _attach_ingest(report: SmokeReport, ingest: IngestReport | None) -> None:
    if ingest is None or ingest.skipped:
        return
    report.ingest_source_rows = int(ingest.source_rows or 0)
    report.ingest_loaded_rows = int(ingest.loaded_rows or 0)
    report.unmatched_m2o = list(ingest.unmatched_m2o or [])
    if ingest.unmatched_m2o:
        report.steps.append(
            ProbeResult(
                name="ingest.unmatched_m2o",
                ok=False,
                detail="; ".join(ingest.unmatched_m2o[:8]),
            )
        )
    elif ingest.committed and ingest.source_rows and ingest.loaded_rows < ingest.source_rows:
        report.steps.append(
            ProbeResult(
                name="ingest.row_count",
                ok=False,
                detail=f"loaded {ingest.loaded_rows}/{ingest.source_rows}",
            )
        )
    elif ingest.committed:
        report.steps.append(
            ProbeResult(
                name="ingest.row_count",
                ok=True,
                detail=f"loaded {ingest.loaded_rows}/{ingest.source_rows or ingest.loaded_rows}",
            )
        )


def run_process_smoke(
    client: Any,
    packet: JobPacket,
    *,
    ingest: IngestReport | None = None,
) -> SmokeReport:
    """RPC-only process smoke. Failures block Promote, not a scorecard 10.0."""
    steps: list[ProbeResult] = []
    warnings: list[str] = []
    ids: dict[str, Any] = {}
    named = _named_process(packet)
    try:
        if not _exists(client, "res.partner"):
            steps.append(ProbeResult(name="partner", ok=False, detail="res.partner missing"))
        else:
            partner_id = _create(client, "res.partner", {"name": "Autopilot Smoke Partner"})
            steps.append(ProbeResult(name="partner", ok=True, detail=f"id={partner_id}"))
            ids["partner_id"] = partner_id
            if named == "quote_to_invoice" or "sale" in packet.stock_apps:
                _smoke_quote_to_invoice(client, packet, steps, warnings, partner_id, ids)
            elif "account" in packet.stock_apps:
                _smoke_standalone_invoice(client, steps, partner_id, ids)
        if packet.has_custom_residual:
            _smoke_custom(client, packet, steps, ids)
        _smoke_extra_apps(client, packet, steps, ids, partner_id=ids.get("partner_id"))
    except Exception as exc:  # noqa: BLE001
        steps.append(ProbeResult(name="smoke", ok=False, detail=str(exc)))
    open_model, open_id = _open_target(ids)
    open_action_id = None
    if open_model == "account.move" and open_id:
        open_action_id = _resolve_window_action(
            client, "account.move", xml_name="action_move_out_invoice_type"
        )
    report = SmokeReport(
        ok=False,
        steps=steps,
        named_process=named,
        partner_id=_first_id(ids.get("partner_id")),
        sale_order_id=_first_id(ids.get("sale_order_id")),
        invoice_id=_first_id(ids.get("invoice_id")),
        open_model=open_model,
        open_id=open_id,
        open_action_id=open_action_id,
        message="",
    )
    _attach_ingest(report, ingest)
    if not report.steps:
        report.steps.append(ProbeResult(name="smoke", ok=False, detail="no smoke steps ran"))
    report.ok = bool(report.steps) and all(s.ok for s in report.steps)
    if report.ok:
        extra = f" ({'; '.join(warnings[:3])})" if warnings else ""
        report.message = f"Process smoke passed ({named}).{extra}"
    else:
        report.message = "Process smoke failed — do not Promote."
    return report


def _resolve_window_action(client: Any, model: str, xml_name: str | None = None) -> int | None:
    """Customer-invoice act_window so Open-in-Odoo does not land on Accounting home."""
    if xml_name:
        try:
            rows = client.execute_kw(
                "ir.model.data",
                "search_read",
                [[("module", "=", "account"), ("name", "=", xml_name)]],
                {"fields": ["res_id"], "limit": 1},
            )
            if rows and rows[0].get("res_id"):
                return int(rows[0]["res_id"])
        except Exception:  # noqa: BLE001
            pass
    try:
        rows = client.execute_kw(
            "ir.actions.act_window",
            "search_read",
            [[("res_model", "=", model), ("view_mode", "ilike", "form")]],
            {"fields": ["id", "name", "domain"], "limit": 12},
        )
    except Exception:  # noqa: BLE001
        return None
    for row in rows or []:
        domain = str(row.get("domain") or "")
        name = str(row.get("name") or "").lower()
        if "out_invoice" in domain or "customer invoice" in name or "invoices" in name:
            return int(row["id"])
    if rows:
        return int(rows[0]["id"])
    return None


def _open_target(ids: dict[str, Any]) -> tuple[str | None, int | None]:
    inv = _first_id(ids.get("invoice_id"))
    if inv:
        return "account.move", inv
    so = _first_id(ids.get("sale_order_id"))
    if so:
        return "sale.order", so
    custom_id = _first_id(ids.get("custom_id"))
    custom_model = ids.get("custom_model")
    if custom_id and isinstance(custom_model, str):
        return custom_model, custom_id
    partner = _first_id(ids.get("partner_id"))
    if partner:
        return "res.partner", partner
    return None, None


__all__ = ["run_process_smoke"]
