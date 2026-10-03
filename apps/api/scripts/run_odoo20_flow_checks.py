#!/usr/bin/env python3
"""O20-11 / 5C-10: stock flow checks on the local Odoo 20 sandbox.

Quote-to-cash 7, procure-to-pay 6, manufacture 2. Records use prefix
``ingenium_o20_``. XML-RPC only. Localhost only. Never production.
"""

from __future__ import annotations

import json
import os
import sys
import time
import xmlrpc.client
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urlparse

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

PREFIX = "ingenium_o20_"
DEFAULT_URL = "http://127.0.0.1:8073"
DEFAULT_DB = "sandbox_test"
DEFAULT_USER = "admin"
DEFAULT_PASSWORD = "admin"

Q2C_NAMES = (
    "q2c.customer",
    "q2c.product",
    "q2c.quotation",
    "q2c.confirm",
    "q2c.delivery",
    "q2c.invoice",
    "q2c.invoice_post",
)
P2P_NAMES = (
    "p2p.vendor",
    "p2p.product",
    "p2p.rfq",
    "p2p.confirm",
    "p2p.receipt",
    "p2p.vendor_bill",
)
MFG_NAMES = (
    "mfg.order",
    "mfg.produce",
)
APP_BY_MODEL = {
    "sale.order": "sale",
    "purchase.order": "purchase",
    "mrp.production": "mrp",
    "mrp.bom": "mrp",
    "stock.picking": "stock",
    "account.move": "account",
    "product.template": "product",
}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class Created:
    model: str
    rid: int
    cancel: str | None = None


@dataclass
class RunState:
    checks: list[Check] = field(default_factory=list)
    created: list[Created] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    installed: list[str] = field(default_factory=list)


def _local_only(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(f"Refusing non-local URL {url!r}. O20-11 is sandbox-only.")


def _connect(url: str, db: str, user: str, password: str) -> OdooClient:
    client = OdooClient(
        ConnectionConfig(
            url=url,
            db=db,
            username=user,
            password=password,
            timeout=300.0,
            write_mode="standard",
            rpc_protocol="xmlrpc",
        )
    )
    client.connect()
    if int(client.capabilities.major) != 20:
        raise SystemExit(f"Expected Odoo 20, got major={client.capabilities.major!r}")
    return client


def _call(client: OdooClient, model: str, method: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Any:
    try:
        return client.execute_kw(model, method, args or [], kwargs or {})
    except xmlrpc.client.Fault as exc:
        if "cannot marshal None" in str(exc):
            return None
        raise


def _exists(client: OdooClient, model: str) -> bool:
    try:
        client.execute_kw(model, "fields_get", [], {"attributes": ["string"]})
        return True
    except Exception:  # noqa: BLE001
        return False


def _search(client: OdooClient, model: str, domain: list[Any], *, limit: int = 8) -> list[int]:
    ids = _call(client, model, "search", [domain], {"limit": limit}) or []
    return [int(i) for i in ids]


def _read(client: OdooClient, model: str, rid: int, fields: list[str]) -> dict[str, Any]:
    rows = _call(client, model, "read", [[rid], fields]) or []
    if rows and isinstance(rows[0], dict):
        return rows[0]
    rows = _call(client, model, "read", [[rid]], {"fields": fields}) or []
    return rows[0] if rows and isinstance(rows[0], dict) else {}


def _xmlid(client: OdooClient, module: str, name: str) -> int | None:
    rows = _call(
        client,
        "ir.model.data",
        "search_read",
        [[("module", "=", module), ("name", "=", name)]],
        {"fields": ["res_id"], "limit": 1},
    ) or []
    if rows and rows[0].get("res_id"):
        return int(rows[0]["res_id"])
    return None


def _first_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, (list, tuple)) and value:
        return _first_id(value[0])
    return None


def _record(state: RunState, name: str, ok: bool, detail: str) -> None:
    state.checks.append(Check(name, ok, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"{flag}  {name}  {detail}")


def _need_model(client: OdooClient, model: str) -> str | None:
    if _exists(client, model):
        return None
    app = APP_BY_MODEL.get(model, model.split(".", 1)[0])
    return f"model {model} missing (install {app})"


def _install_app(client: OdooClient, module_name: str, url: str, db: str, user: str, password: str) -> OdooClient:
    print(f"INSTALL  {module_name} on local sandbox only")
    try:
        client.ensure_module_installed(module_name)
    except OdooClientError as exc:
        raise SystemExit(f"blocker: ensure_module_installed({module_name!r}): {exc}") from exc
    time.sleep(2)
    return _connect(url, db, user, password)


def _ensure_apps(client: OdooClient, url: str, db: str, user: str, password: str, state: RunState) -> OdooClient:
    needed = ("sale_management", "purchase", "mrp")
    for module in needed:
        row = client.get_module_state(module)
        if row and row.get("state") == "installed":
            continue
        if row is None:
            try:
                client.update_module_list()
            except Exception as exc:  # noqa: BLE001
                state.blockers.append(f"update_list before {module}: {exc}")
                continue
            row = client.get_module_state(module)
        if row is None:
            state.blockers.append(f"module {module!r} not found on this instance")
            continue
        err = f"module {module} state={row.get('state')!r} (not installed)"
        print(f"MISSING  {err}")
        try:
            client = _install_app(client, module, url, db, user, password)
            state.installed.append(module)
        except SystemExit as exc:
            state.blockers.append(str(exc))
    return client


def _create_partner(client: OdooClient, state: RunState, name: str, *, supplier: bool) -> int:
    vals: dict[str, Any] = {"name": name}
    if supplier:
        vals["is_company"] = True
    rid = int(_call(client, "res.partner", "create", [vals]))
    state.created.append(Created("res.partner", rid))
    return rid


def _create_product(
    client: OdooClient,
    state: RunState,
    name: str,
    *,
    storable: bool,
    sale: bool,
    purchase: bool,
) -> tuple[int, int]:
    vals: dict[str, Any] = {
        "name": name,
        "list_price": 10.0,
        "standard_price": 4.0,
        "sale_ok": sale,
        "purchase_ok": purchase,
    }
    if storable:
        vals["is_storable"] = True
        vals["type"] = "consu"
        vals["invoice_policy"] = "order"
        vals["purchase_method"] = "receive"
    else:
        vals["type"] = "consu"
        vals["invoice_policy"] = "order"
    last_err = "create failed"
    tmpl_id: int | None = None
    for attempt in (
        vals,
        {k: v for k, v in vals.items() if k != "purchase_method"},
        {k: v for k, v in vals.items() if k not in {"purchase_method", "is_storable"}},
        {"name": name, "list_price": 10.0},
    ):
        try:
            tmpl_id = int(_call(client, "product.template", "create", [attempt]))
            break
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
    if tmpl_id is None:
        raise RuntimeError(last_err)
    state.created.append(Created("product.template", tmpl_id))
    ids = _search(client, "product.product", [("product_tmpl_id", "=", tmpl_id)], limit=1)
    if ids:
        product_id = ids[0]
    else:
        product_id = int(
            _call(client, "product.product", "create", [{"name": name, "product_tmpl_id": tmpl_id}])
        )
        state.created.append(Created("product.product", product_id))
    return tmpl_id, product_id


def _stock_location(client: OdooClient) -> int | None:
    loc = _xmlid(client, "stock", "stock_location_stock")
    if loc:
        return loc
    ids = _search(client, "stock.location", [("usage", "=", "internal")], limit=1)
    return ids[0] if ids else None


def _put_stock(client: OdooClient, product_id: int, qty: float = 20.0) -> str:
    if not _exists(client, "stock.quant"):
        return "stock.quant missing"
    loc = _stock_location(client)
    if loc is None:
        return "no internal stock.location"
    try:
        qid = int(
            _call(
                client,
                "stock.quant",
                "create",
                [{"product_id": product_id, "location_id": loc, "inventory_quantity": qty}],
            )
        )
    except Exception as exc:  # noqa: BLE001
        return f"quant create: {exc}"
    try:
        _call(client, "stock.quant", "action_apply_inventory", [[qid]])
    except Exception as exc:  # noqa: BLE001
        if "cannot marshal None" not in str(exc):
            return f"action_apply_inventory: {exc}"
    return f"quant={qid} qty={qty}"


def _validate_picking(client: OdooClient, picking_id: int) -> tuple[bool, str]:
    try:
        _call(client, "stock.picking", "action_set_quantities_to_reservation", [[picking_id]])
    except Exception:  # noqa: BLE001
        rec = _read(client, "stock.picking", picking_id, ["move_ids"])
        for mid in rec.get("move_ids") or []:
            move_id = int(mid if not isinstance(mid, (list, tuple)) else mid[0])
            move = _read(client, "stock.move", move_id, ["product_uom_qty", "quantity"])
            qty = move.get("product_uom_qty") or move.get("quantity") or 1.0
            try:
                _call(client, "stock.move", "write", [[move_id], {"quantity": qty, "picked": True}])
            except Exception:  # noqa: BLE001
                try:
                    _call(client, "stock.move", "write", [[move_id], {"quantity": qty}])
                except Exception:  # noqa: BLE001
                    pass
    try:
        result = _call(client, "stock.picking", "button_validate", [[picking_id]])
    except Exception as exc:  # noqa: BLE001
        state = _read(client, "stock.picking", picking_id, ["state"]).get("state")
        if state == "done":
            return True, f"id={picking_id} state=done after Fault {exc}"
        return False, str(exc)
    state = _read(client, "stock.picking", picking_id, ["state"]).get("state")
    if state == "done":
        return True, f"id={picking_id} state=done"
    if isinstance(result, dict) and result.get("res_model"):
        wiz_model = str(result["res_model"])
        ctx = result.get("context") or {}
        try:
            wiz_id = int(_call(client, wiz_model, "create", [{}], {"context": ctx}))
            for method in ("process", "button_validate", "action_confirm"):
                try:
                    _call(client, wiz_model, method, [[wiz_id]], {"context": ctx})
                    break
                except Exception:  # noqa: BLE001
                    continue
        except Exception as exc:  # noqa: BLE001
            return False, f"wizard {wiz_model}: {exc}"
        state = _read(client, "stock.picking", picking_id, ["state"]).get("state")
        if state == "done":
            return True, f"id={picking_id} via {wiz_model}"
        return False, f"picking {picking_id} state={state} after {wiz_model}"
    return False, f"picking {picking_id} state={state} result={result!r}"


def _run_q2c(client: OdooClient, state: RunState) -> None:
    missing = _need_model(client, "sale.order")
    if missing:
        for name in Q2C_NAMES:
            _record(state, name, False, missing)
        return
    try:
        partner_id = _create_partner(client, state, f"{PREFIX}customer", supplier=False)
        _record(state, "q2c.customer", True, f"id={partner_id}")
    except Exception as exc:  # noqa: BLE001
        _record(state, "q2c.customer", False, str(exc))
        for name in Q2C_NAMES[1:]:
            _record(state, name, False, "skipped: no customer")
        return
    try:
        _tmpl, product_id = _create_product(
            client, state, f"{PREFIX}sale_product", storable=True, sale=True, purchase=False
        )
        stock_note = _put_stock(client, product_id)
        _record(state, "q2c.product", True, f"product_id={product_id} {stock_note}")
    except Exception as exc:  # noqa: BLE001
        _record(state, "q2c.product", False, str(exc))
        for name in Q2C_NAMES[2:]:
            _record(state, name, False, "skipped: no product")
        return
    so_id: int | None = None
    try:
        so_id = int(
            _call(
                client,
                "sale.order",
                "create",
                [
                    {
                        "partner_id": partner_id,
                        "client_order_ref": f"{PREFIX}so",
                        "order_line": [
                            (0, 0, {"product_id": product_id, "product_uom_qty": 1, "price_unit": 10.0})
                        ],
                    }
                ],
            )
        )
        state.created.append(Created("sale.order", so_id, cancel="action_cancel"))
        _record(state, "q2c.quotation", True, f"id={so_id} with line")
    except Exception as exc:  # noqa: BLE001
        _record(state, "q2c.quotation", False, str(exc))
        for name in Q2C_NAMES[3:]:
            _record(state, name, False, "skipped: no quotation")
        return
    try:
        _call(client, "sale.order", "action_confirm", [[so_id]])
        rec = _read(client, "sale.order", so_id, ["state"])
        if rec.get("state") not in {"sale", "done"}:
            _record(state, "q2c.confirm", False, f"state={rec.get('state')!r}")
            for name in Q2C_NAMES[4:]:
                _record(state, name, False, "skipped: confirm failed")
            return
        _record(state, "q2c.confirm", True, f"id={so_id} state={rec.get('state')}")
    except Exception as exc:  # noqa: BLE001
        _record(state, "q2c.confirm", False, str(exc))
        for name in Q2C_NAMES[4:]:
            _record(state, name, False, "skipped: confirm failed")
        return
    so = _read(client, "sale.order", so_id, ["name", "picking_ids"])
    picking_ids = so.get("picking_ids") or []
    if not picking_ids and so.get("name"):
        picking_ids = _search(client, "stock.picking", [("origin", "=", so.get("name"))])
    if not picking_ids:
        _record(state, "q2c.delivery", False, "no stock.picking after confirm")
    else:
        pid = int(picking_ids[0] if not isinstance(picking_ids[0], (list, tuple)) else picking_ids[0][0])
        ok, detail = _validate_picking(client, pid)
        _record(state, "q2c.delivery", ok, detail)
    if not _exists(client, "sale.advance.payment.inv"):
        _record(state, "q2c.invoice", False, "sale.advance.payment.inv missing")
        _record(state, "q2c.invoice_post", False, "skipped: no invoice")
        return
    inv_id: int | None = None
    try:
        wiz_id = int(
            _call(
                client,
                "sale.advance.payment.inv",
                "create",
                [{"advance_payment_method": "delivered", "sale_order_ids": [(6, 0, [so_id])]}],
            )
        )
        try:
            inv = _call(client, "sale.advance.payment.inv", "create_invoices", [[wiz_id]])
            inv_id = _first_id(inv)
        except Exception as exc:  # noqa: BLE001
            so = _read(client, "sale.order", so_id, ["invoice_ids"])
            inv_id = _first_id(so.get("invoice_ids"))
            if inv_id is None:
                _record(state, "q2c.invoice", False, str(exc))
                _record(state, "q2c.invoice_post", False, "skipped: no invoice")
                return
        if inv_id is None:
            so = _read(client, "sale.order", so_id, ["invoice_ids"])
            inv_id = _first_id(so.get("invoice_ids"))
        if inv_id is None:
            _record(state, "q2c.invoice", False, "wizard returned no invoice_ids")
            _record(state, "q2c.invoice_post", False, "skipped: no invoice")
            return
        state.created.append(Created("account.move", inv_id, cancel="button_cancel"))
        _record(state, "q2c.invoice", True, f"id={inv_id}")
    except Exception as exc:  # noqa: BLE001
        _record(state, "q2c.invoice", False, str(exc))
        _record(state, "q2c.invoice_post", False, "skipped: no invoice")
        return
    try:
        _call(client, "account.move", "action_post", [[inv_id]])
        rec = _read(client, "account.move", inv_id, ["state"])
        if rec.get("state") == "posted":
            _record(state, "q2c.invoice_post", True, f"id={inv_id} posted")
        else:
            _record(state, "q2c.invoice_post", False, f"state={rec.get('state')!r}")
    except Exception as exc:  # noqa: BLE001
        _record(state, "q2c.invoice_post", False, str(exc))


def _run_p2p(client: OdooClient, state: RunState) -> int | None:
    """Return component product id when RFQ/receipt succeed (reuse for MRP)."""
    missing = _need_model(client, "purchase.order")
    if missing:
        for name in P2P_NAMES:
            _record(state, name, False, missing)
        return None
    try:
        vendor_id = _create_partner(client, state, f"{PREFIX}vendor", supplier=True)
        _record(state, "p2p.vendor", True, f"id={vendor_id}")
    except Exception as exc:  # noqa: BLE001
        _record(state, "p2p.vendor", False, str(exc))
        for name in P2P_NAMES[1:]:
            _record(state, name, False, "skipped: no vendor")
        return None
    try:
        _tmpl, product_id = _create_product(
            client, state, f"{PREFIX}buy_product", storable=True, sale=False, purchase=True
        )
        _record(state, "p2p.product", True, f"product_id={product_id}")
    except Exception as exc:  # noqa: BLE001
        _record(state, "p2p.product", False, str(exc))
        for name in P2P_NAMES[2:]:
            _record(state, name, False, "skipped: no product")
        return None
    po_id: int | None = None
    try:
        po_id = int(
            _call(
                client,
                "purchase.order",
                "create",
                [
                    {
                        "partner_id": vendor_id,
                        "partner_ref": f"{PREFIX}po",
                        "order_line": [
                            (0, 0, {"product_id": product_id, "product_qty": 5, "price_unit": 4.0})
                        ],
                    }
                ],
            )
        )
        state.created.append(Created("purchase.order", po_id, cancel="button_cancel"))
        _record(state, "p2p.rfq", True, f"id={po_id} with line")
    except Exception as exc:  # noqa: BLE001
        _record(state, "p2p.rfq", False, str(exc))
        for name in P2P_NAMES[3:]:
            _record(state, name, False, "skipped: no rfq")
        return None
    try:
        _call(client, "purchase.order", "button_confirm", [[po_id]])
        rec = _read(client, "purchase.order", po_id, ["state"])
        if rec.get("state") not in {"purchase", "done"}:
            _record(state, "p2p.confirm", False, f"state={rec.get('state')!r}")
            for name in P2P_NAMES[4:]:
                _record(state, name, False, "skipped: confirm failed")
            return product_id
        _record(state, "p2p.confirm", True, f"id={po_id} state={rec.get('state')}")
    except Exception as exc:  # noqa: BLE001
        _record(state, "p2p.confirm", False, str(exc))
        for name in P2P_NAMES[4:]:
            _record(state, name, False, "skipped: confirm failed")
        return product_id
    po = _read(client, "purchase.order", po_id, ["name", "picking_ids"])
    picking_ids = po.get("picking_ids") or []
    if not picking_ids and po.get("name"):
        picking_ids = _search(client, "stock.picking", [("origin", "=", po.get("name"))])
    if not picking_ids:
        _record(state, "p2p.receipt", False, "no stock.picking after confirm")
    else:
        pid = int(picking_ids[0] if not isinstance(picking_ids[0], (list, tuple)) else picking_ids[0][0])
        ok, detail = _validate_picking(client, pid)
        _record(state, "p2p.receipt", ok, detail)
    bill_id: int | None = None
    last_err = "no bill method"
    for method in ("action_create_invoice", "button_create_bill"):
        try:
            res = _call(client, "purchase.order", method, [[po_id]])
            bill_id = _first_id(res)
            if bill_id is None and isinstance(res, dict):
                bill_id = _first_id(res.get("res_id"))
            if bill_id is None:
                po = _read(client, "purchase.order", po_id, ["invoice_ids"])
                bill_id = _first_id(po.get("invoice_ids"))
            if bill_id:
                last_err = method
                break
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            po = _read(client, "purchase.order", po_id, ["invoice_ids"])
            bill_id = _first_id(po.get("invoice_ids"))
            if bill_id:
                break
    if bill_id is None:
        _record(state, "p2p.vendor_bill", False, last_err)
        return product_id
    state.created.append(Created("account.move", bill_id, cancel="button_cancel"))
    try:
        rec = _read(client, "account.move", bill_id, ["state", "invoice_date"])
        if rec.get("state") == "draft":
            if not rec.get("invoice_date"):
                _call(
                    client,
                    "account.move",
                    "write",
                    [[bill_id], {"invoice_date": date.today().isoformat()}],
                )
            _call(client, "account.move", "action_post", [[bill_id]])
            rec = _read(client, "account.move", bill_id, ["state"])
        if rec.get("state") == "posted":
            _record(state, "p2p.vendor_bill", True, f"id={bill_id} posted")
        elif rec.get("state"):
            _record(state, "p2p.vendor_bill", True, f"id={bill_id} created state={rec.get('state')}")
        else:
            _record(state, "p2p.vendor_bill", False, f"id={bill_id} unreadable after create")
    except Exception as exc:  # noqa: BLE001
        rec = _read(client, "account.move", bill_id, ["state"])
        if rec.get("id") or rec.get("state"):
            _record(state, "p2p.vendor_bill", True, f"id={bill_id} created state={rec.get('state')!r}; post: {exc}")
        else:
            _record(state, "p2p.vendor_bill", False, str(exc))
    return product_id


def _run_mfg(client: OdooClient, state: RunState, component_id: int | None) -> None:
    missing = _need_model(client, "mrp.production")
    if missing:
        for name in MFG_NAMES:
            _record(state, name, False, missing)
        return
    if not _exists(client, "mrp.bom"):
        for name in MFG_NAMES:
            _record(state, name, False, "mrp.bom missing")
        return
    try:
        finished_tmpl, finished_id = _create_product(
            client, state, f"{PREFIX}finished", storable=True, sale=False, purchase=False
        )
        if component_id is None:
            _ct, component_id = _create_product(
                client, state, f"{PREFIX}component", storable=True, sale=False, purchase=True
            )
            _put_stock(client, component_id)
        else:
            _put_stock(client, component_id)
        bom_id = int(
            _call(
                client,
                "mrp.bom",
                "create",
                [
                    {
                        "product_tmpl_id": finished_tmpl,
                        "product_qty": 1.0,
                        "type": "normal",
                        "bom_line_ids": [(0, 0, {"product_id": component_id, "product_qty": 1.0})],
                    }
                ],
            )
        )
        state.created.append(Created("mrp.bom", bom_id))
        mo_vals: dict[str, Any] = {
            "product_id": finished_id,
            "product_qty": 1.0,
            "bom_id": bom_id,
        }
        mo_id = int(_call(client, "mrp.production", "create", [mo_vals]))
        state.created.append(Created("mrp.production", mo_id, cancel="action_cancel"))
        _record(state, "mfg.order", True, f"mo={mo_id} bom={bom_id}")
    except Exception as exc:  # noqa: BLE001
        _record(state, "mfg.order", False, str(exc))
        _record(state, "mfg.produce", False, "skipped: no MO")
        return
    try:
        _call(client, "mrp.production", "action_confirm", [[mo_id]])
        try:
            _call(client, "mrp.production", "write", [[mo_id], {"qty_producing": 1.0}])
        except Exception:  # noqa: BLE001
            pass
        try:
            _call(client, "mrp.production", "button_mark_done", [[mo_id]])
        except Exception as exc:  # noqa: BLE001
            rec = _read(client, "mrp.production", mo_id, ["state"])
            if rec.get("state") != "done":
                raise RuntimeError(str(exc)) from exc
        rec = _read(client, "mrp.production", mo_id, ["state"])
        if rec.get("state") == "done":
            _record(state, "mfg.produce", True, f"id={mo_id} done")
        else:
            _record(state, "mfg.produce", False, f"state={rec.get('state')!r}")
    except Exception as exc:  # noqa: BLE001
        _record(state, "mfg.produce", False, str(exc))


def _cleanup(client: OdooClient, state: RunState) -> None:
    for item in reversed(state.created):
        if item.cancel:
            try:
                _call(client, item.model, item.cancel, [[item.rid]])
            except Exception:  # noqa: BLE001
                pass
        try:
            rec = _read(client, item.model, item.rid, ["state"])
            state_val = str(rec.get("state") or "")
            if state_val in {"posted", "done", "sale", "purchase"}:
                continue
            _call(client, item.model, "unlink", [[item.rid]])
        except Exception:  # noqa: BLE001
            pass


def _counts(state: RunState) -> dict[str, Any]:
    by = {c.name: c for c in state.checks}

    def _score(names: tuple[str, ...]) -> dict[str, Any]:
        passed = [n for n in names if by.get(n) and by[n].ok]
        failed = [n for n in names if not (by.get(n) and by[n].ok)]
        return {
            "passed": len(passed),
            "total": len(names),
            "failed": failed,
            "details": {n: {"ok": by[n].ok, "detail": by[n].detail} for n in names if n in by},
        }

    return {
        "quote_to_cash": _score(Q2C_NAMES),
        "procure_to_pay": _score(P2P_NAMES),
        "manufacture": _score(MFG_NAMES),
        "installed": state.installed,
        "blockers": state.blockers,
    }


def main() -> int:
    url = os.environ.get("ODOO20_URL", DEFAULT_URL)
    db = os.environ.get("ODOO20_DB", DEFAULT_DB)
    user = os.environ.get("ODOO20_USER", DEFAULT_USER)
    password = os.environ.get("ODOO20_PASSWORD", DEFAULT_PASSWORD)
    _local_only(url)
    print(f"O20-11 connect {url} db={db} rpc_protocol=xmlrpc prefix={PREFIX}")
    client = _connect(url, db, user, password)
    state = RunState()
    client = _ensure_apps(client, url, db, user, password, state)
    if state.blockers and not _exists(client, "sale.order") and not _exists(client, "purchase.order"):
        print(json.dumps({"blocker": state.blockers}, indent=2))
        return 2
    _run_q2c(client, state)
    component_id = _run_p2p(client, state)
    _run_mfg(client, state, component_id)
    _cleanup(client, state)
    summary = _counts(state)
    print(json.dumps(summary, indent=2))
    q = summary["quote_to_cash"]["passed"]
    p = summary["procure_to_pay"]["passed"]
    m = summary["manufacture"]["passed"]
    print(f"COUNTS  quote-to-cash {q}/7  procure-to-pay {p}/6  manufacture {m}/2")
    if state.blockers:
        print("BLOCKERS  " + " | ".join(state.blockers))
    return 0 if q == 7 and p == 6 and m == 2 else 1


if __name__ == "__main__":
    sys.exit(main())
