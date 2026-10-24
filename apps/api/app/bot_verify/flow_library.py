"""BV-05 flow library: end-to-end business flows per Odoo app, as RPC steps.

Each step runs as the clone's admin over the caller's port (``admin(model,
method, args, kwargs)`` plus ``major``) and returns the record it touched;
the runner then reads that record back and asserts its state. Steps only
use public methods and wizards, so they behave the same on Odoo 17-20.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

Ctx = dict[str, Any]
StepFn = Callable[[Any, Ctx], tuple[str, int]]


@dataclass(frozen=True)
class FlowStep:
    name: str
    run: StepFn
    field: str
    expect: tuple[Any, ...]


@dataclass(frozen=True)
class Flow:
    app: str
    name: str
    steps: tuple[FlowStep, ...]


# Model prefix -> app module; module.install names map to themselves.
APP_OF_PREFIX: tuple[tuple[str, str], ...] = (
    ("sale.", "sale"),
    ("purchase.", "purchase"),
    ("account.", "account"),
    ("stock.", "stock"),
    ("hr.leave", "hr_holidays"),
    ("crm.", "crm"),
    ("project.", "project"),
)
# The least app groups a walk user needs to open each app's records (never group_system).
APP_GROUPS: dict[str, tuple[tuple[str, str], ...]] = {
    "sale": (("sales_team", "group_sale_salesman"),),
    "purchase": (("purchase", "group_purchase_user"),),
    "account": (("account", "group_account_invoice"),),
    "stock": (("stock", "group_stock_user"),),
    "hr_holidays": (("hr_holidays", "group_hr_holidays_user"),),
    "crm": (("sales_team", "group_sale_salesman"),),
    "project": (("project", "group_project_user"),),
}


def _create(port: Any, model: str, vals: Mapping[str, Any], ctx: Mapping | None = None) -> int:
    kw = {"context": dict(ctx)} if ctx else {}
    res = port.admin(model, "create", (dict(vals),), kw)
    return int(res[0] if isinstance(res, list) else res)


def _call(port: Any, model: str, method: str, rid: int, ctx: Mapping | None = None) -> Any:
    kw = {"context": dict(ctx)} if ctx else {}
    try:
        return port.admin(model, method, ([rid],), kw)
    except Exception as exc:  # noqa: BLE001
        # The method ran and committed; only its None return failed XML-RPC marshalling.
        if "cannot marshal None" in str(getattr(exc, "faultString", exc)):
            return None
        raise


def _partner(port: Any, c: Ctx) -> int:
    if "partner" not in c:
        c["partner"] = _create(port, "res.partner", {"name": "NF Flow Customer"})
    return c["partner"]


def _product(port: Any, c: Ctx, kind: str) -> int:
    key = f"product_{kind}"
    if key not in c:
        vals: dict[str, Any] = {"name": f"NF Flow {kind}", "list_price": 10.0}
        if kind == "service":
            vals["type"] = "service"
        elif int(port.major) >= 18:
            vals.update(type="consu", is_storable=True)
        else:
            vals["type"] = "product"
        tmpl = _create(port, "product.template", vals)
        rows = port.admin(
            "product.product", "search", ([("product_tmpl_id", "=", tmpl)],), {"limit": 1}
        )
        c[key] = int(rows[0])
    return c[key]


# --- sale: quote -> confirm -> invoice -------------------------------------------
def _sale_quote(port: Any, c: Ctx) -> tuple[str, int]:
    line = {"product_id": _product(port, c, "service"), "product_uom_qty": 1, "price_unit": 10.0}
    c["so"] = _create(
        port, "sale.order", {"partner_id": _partner(port, c), "order_line": [(0, 0, line)]}
    )
    return "sale.order", c["so"]


def _sale_confirm(port: Any, c: Ctx) -> tuple[str, int]:
    _call(port, "sale.order", "action_confirm", c["so"])
    return "sale.order", c["so"]


def _sale_invoice(port: Any, c: Ctx) -> tuple[str, int]:
    ctx = {"active_model": "sale.order", "active_ids": [c["so"]], "active_id": c["so"]}
    wiz = _create(port, "sale.advance.payment.inv", {"advance_payment_method": "delivered"}, ctx)
    _call(port, "sale.advance.payment.inv", "create_invoices", wiz, ctx)
    rows = port.admin("sale.order", "read", ([c["so"]], ["invoice_ids"]))
    inv = int(rows[0]["invoice_ids"][0])
    _call(port, "account.move", "action_post", inv)
    return "account.move", inv


# --- purchase: RFQ -> confirm --------------------------------------------------
def _po_rfq(port: Any, c: Ctx) -> tuple[str, int]:
    line = {"product_id": _product(port, c, "service"), "product_qty": 1, "price_unit": 5.0}
    c["po"] = _create(
        port, "purchase.order", {"partner_id": _partner(port, c), "order_line": [(0, 0, line)]}
    )
    return "purchase.order", c["po"]


def _po_confirm(port: Any, c: Ctx) -> tuple[str, int]:
    _call(port, "purchase.order", "button_confirm", c["po"])
    return "purchase.order", c["po"]


# --- account: draft invoice -> post ------------------------------------------
def _inv_draft(port: Any, c: Ctx) -> tuple[str, int]:
    line = {"name": "NF Flow line", "quantity": 1, "price_unit": 7.0}
    c["inv"] = _create(
        port,
        "account.move",
        {
            "move_type": "out_invoice",
            "partner_id": _partner(port, c),
            "invoice_line_ids": [(0, 0, line)],
        },
    )
    return "account.move", c["inv"]


def _inv_post(port: Any, c: Ctx) -> tuple[str, int]:
    _call(port, "account.move", "action_post", c["inv"])
    return "account.move", c["inv"]


# --- stock: receipt -> move -> done ------------------------------------------
def _receipt(port: Any, c: Ctx) -> tuple[str, int]:
    wh = port.admin("stock.warehouse", "search_read", ([],), {"fields": ["in_type_id"], "limit": 1})
    ptype = port.admin(
        "stock.picking.type",
        "read",
        ([wh[0]["in_type_id"][0]], ["default_location_src_id", "default_location_dest_id"]),
    )[0]
    src = ptype["default_location_src_id"]
    if not src:
        src = port.admin("stock.location", "search", ([("usage", "=", "supplier")],), {"limit": 1})
    src_id = int(src[0])
    dst_id = int(ptype["default_location_dest_id"][0])
    prod = _product(port, c, "stored")
    move = {
        "product_id": prod,
        "product_uom_qty": 2,
        "location_id": src_id,
        "location_dest_id": dst_id,
    }
    if int(port.major) < 19:
        move["name"] = "NF Flow receipt"
    if int(port.major) < 19:
        uom = port.admin("product.product", "read", ([prod], ["uom_id"]))[0]["uom_id"][0]
        move["product_uom"] = uom
    c["pick"] = _create(
        port,
        "stock.picking",
        {
            "picking_type_id": int(wh[0]["in_type_id"][0]),
            "location_id": src_id,
            "location_dest_id": dst_id,
            "partner_id": _partner(port, c),
            "move_ids": [(0, 0, move)],
        },
    )
    _call(port, "stock.picking", "action_confirm", c["pick"])
    return "stock.picking", c["pick"]


def _receipt_move(port: Any, c: Ctx) -> tuple[str, int]:
    moves = port.admin("stock.move", "search", ([("picking_id", "=", c["pick"])],))
    port.admin("stock.move", "write", (moves, {"quantity": 2}))
    if int(port.major) >= 18:
        port.admin("stock.move", "write", (moves, {"picked": True}))
    c["move"] = int(moves[0])
    return "stock.move", c["move"]


def _receipt_done(port: Any, c: Ctx) -> tuple[str, int]:
    res = _call(port, "stock.picking", "button_validate", c["pick"])
    if isinstance(res, dict) and res.get("res_model") and res.get("res_id"):
        # A follow-up wizard (immediate transfer / backorder): process it.
        model, rid = str(res["res_model"]), int(res["res_id"])
        for meth in ("process", "process_cancel_backorder"):
            try:
                _call(port, model, meth, rid, res.get("context") or {})
                break
            except Exception:  # noqa: BLE001
                continue
    return "stock.picking", c["pick"]


# --- hr_holidays: leave request -> approve -----------------------------------
def _leave_request(port: Any, c: Ctx) -> tuple[str, int]:
    # Odoo 20 folds leave types into hr.work.entry.type (hr.leave.work_entry_type_id).
    v20 = int(port.major) >= 20
    vals: dict[str, Any] = {"name": "NF Flow leave", "leave_validation_type": "hr"}
    vals["requires_allocation"] = False if v20 or int(port.major) == 19 else "no"
    if v20:
        vals["code"] = "NFFLOW"
    lt_model = "hr.work.entry.type" if v20 else "hr.leave.type"
    try:
        lt = _create(port, lt_model, vals)
    except Exception:  # noqa: BLE001 - selection vs boolean allocation flag differs by build
        vals["requires_allocation"] = "no" if vals["requires_allocation"] is False else False
        lt = _create(port, lt_model, vals)
    # The request comes from a plain employee (an approver's own request may auto-validate).
    uid = int((getattr(port, "personas", None) or {}).get("low_privilege") or port.admin_uid)
    emp = port.admin("hr.employee", "search", ([("user_id", "=", uid)],), {"limit": 1})
    if not emp:
        emp = [_create(port, "hr.employee", {"name": "NF Flow Employee", "user_id": uid})]
    vals = {
        ("work_entry_type_id" if v20 else "holiday_status_id"): lt,
        "employee_id": int(emp[0]),
        "request_date_from": "2031-03-03",
        "request_date_to": "2031-03-04",
    }
    if v20 and uid != int(port.admin_uid):
        # Odoo 20 gates hr.work.entry.type behind "Time Off / Employee"; grant only that
        # group to the requester on the disposable clone.
        gx = port.admin(
            "ir.model.data",
            "search_read",
            (
                [
                    ("module", "=", "hr_holidays"),
                    ("model", "=", "res.groups"),
                    ("name", "=like", "%employee%"),
                ],
            ),
            {"fields": ["res_id"], "limit": 1},
        )
        if gx:
            port.admin("res.users", "write", ([uid], {"group_ids": [(4, int(gx[0]["res_id"]))]}))
    if uid == int(port.admin_uid):
        c["leave"] = _create(port, "hr.leave", vals)
    else:
        res = port.call("hr.leave", "create", (vals,), {}, as_uid=uid)
        c["leave"] = int(res[0] if isinstance(res, list) else res)
    return "hr.leave", c["leave"]


def _leave_approve(port: Any, c: Ctx) -> tuple[str, int]:
    _call(port, "hr.leave", "action_approve", c["leave"])
    st = port.admin("hr.leave", "read", ([c["leave"]], ["state"]))[0]["state"]
    if st == "validate1":
        _call(port, "hr.leave", "action_validate", c["leave"])
    return "hr.leave", c["leave"]


# --- crm: lead -> opportunity -> won -----------------------------------------
def _crm_lead(port: Any, c: Ctx) -> tuple[str, int]:
    c["lead"] = _create(
        port,
        "crm.lead",
        {"name": "NF Flow lead", "type": "opportunity", "partner_id": _partner(port, c)},
    )
    return "crm.lead", c["lead"]


def _crm_won(port: Any, c: Ctx) -> tuple[str, int]:
    _call(port, "crm.lead", "action_set_won", c["lead"])
    return "crm.lead", c["lead"]


# --- project: project -> task -> done ----------------------------------------
def _project_task(port: Any, c: Ctx) -> tuple[str, int]:
    proj = _create(port, "project.project", {"name": "NF Flow project"})
    c["task"] = _create(port, "project.task", {"name": "NF Flow task", "project_id": proj})
    return "project.task", c["task"]


def _project_done(port: Any, c: Ctx) -> tuple[str, int]:
    port.admin("project.task", "write", ([c["task"]], {"state": "1_done"}))
    return "project.task", c["task"]


def _ok(*vals: Any) -> tuple[Any, ...]:
    return tuple(vals)


FLOWS: dict[str, tuple[Flow, ...]] = {
    "sale": (
        Flow(
            "sale",
            "quote_confirm_invoice",
            (
                FlowStep("quote", _sale_quote, "state", _ok("draft")),
                FlowStep("confirm", _sale_confirm, "state", _ok("sale")),
                FlowStep("invoice", _sale_invoice, "state", _ok("posted")),
            ),
        ),
    ),
    "purchase": (
        Flow(
            "purchase",
            "rfq_confirm",
            (
                FlowStep("rfq", _po_rfq, "state", _ok("draft")),
                FlowStep("confirm", _po_confirm, "state", _ok("purchase")),
            ),
        ),
    ),
    "account": (
        Flow(
            "account",
            "invoice_post",
            (
                FlowStep("draft", _inv_draft, "state", _ok("draft")),
                FlowStep("post", _inv_post, "state", _ok("posted")),
            ),
        ),
    ),
    "stock": (
        Flow(
            "stock",
            "receipt_move_done",
            (
                FlowStep("receipt", _receipt, "state", _ok("assigned", "confirmed")),
                FlowStep("move", _receipt_move, "quantity", _ok(2.0, 2)),
                FlowStep("done", _receipt_done, "state", _ok("done")),
            ),
        ),
    ),
    "hr_holidays": (
        Flow(
            "hr_holidays",
            "leave_request_approve",
            (
                FlowStep("request", _leave_request, "state", _ok("confirm")),
                FlowStep("approve", _leave_approve, "state", _ok("validate")),
            ),
        ),
    ),
    "crm": (
        Flow(
            "crm",
            "lead_won",
            (
                FlowStep("lead", _crm_lead, "active", _ok(True)),
                FlowStep("won", _crm_won, "probability", _ok(100.0, 100)),
            ),
        ),
    ),
    "project": (
        Flow(
            "project",
            "task_done",
            (
                FlowStep("task", _project_task, "state", _ok("01_in_progress")),
                FlowStep("done", _project_done, "state", _ok("1_done")),
            ),
        ),
    ),
}
REQUIRED_APPS: frozenset[str] = frozenset(
    {"sale", "purchase", "account", "stock", "hr_holidays", "crm", "project"}
)


def app_of_model(model: Any) -> str | None:
    if not isinstance(model, str):
        return None
    for prefix, app in APP_OF_PREFIX:
        if model.startswith(prefix):
            return app
    return None


def touched_apps(changeset: Sequence[Mapping[str, Any]]) -> set[str]:
    apps: set[str] = set()
    for op in changeset:
        params = op.get("params") or {}
        if str(op.get("type", "")).startswith("module."):
            name = params.get("name")
            if name in FLOWS:
                apps.add(name)
        app = app_of_model(params.get("model"))
        if app:
            apps.add(app)
    return apps


def flows_for(changeset: Sequence[Mapping[str, Any]], installed: set[str]) -> list[Flow]:
    """AC1: every installed app the change-set touches gets >= 1 flow."""
    return [f for app in sorted(touched_apps(changeset) & set(installed)) for f in FLOWS[app]]
