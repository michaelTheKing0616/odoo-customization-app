"""BOT-RISK-CLASSIFIER: per-button resolution from live Odoo metadata (never from labels).

A button is resolved from the combined form arch returned by the model's public
`get_views` (inheritance already applied, so the last-applied arch wins) to a target:
type=object -> (model, method) looked up in a hand-curated method->effect table;
type=action -> the action record: server actions are classified from their state (code is
parsed statically and only plain `records.method()` calls are accepted), act_window on a
wizard resolves the wizard's own buttons (depth <= 3). Anything that cannot be resolved is
`Unresolved` and the caller refuses. Public ORM over the given port only.
"""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Protocol

from app.bots.risk.rules import (
    LOW_RISK_MODELS,
    apply_floor,
    method_floor,
    sensitivity_floor,
    unknown_fields,
    worst,
)

FINANCIAL_PREFIXES = ("account.", "stock.", "mrp.", "pos.", "repair.")
MAX_DEPTH = 3
MAX_ARCH = 2_000_000


class RpcPort(Protocol):
    def call(self, model: str, method: str, args: Any = (), kwargs: dict | None = None) -> Any: ...


@dataclass(frozen=True)
class Effect:
    cls: str
    subkind: str | None
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class Unresolved:
    reason: str
    evidence: tuple[str, ...] = ()


# (model or "*", method) -> (class, subkind). Grows only via catalogue regression fixtures.
EFFECTS: dict[tuple[str, str], tuple[str, str | None]] = {
    # posting / valuation (R4)
    ("account.move", "action_post"): ("R4", "post"),
    ("account.move", "button_draft"): ("R4", "reset-draft"),
    ("account.move", "button_cancel"): ("R4", "post"),
    ("account.payment", "action_post"): ("R4", "post"),
    ("account.payment", "action_validate"): ("R4", "post"),
    ("account.payment", "action_draft"): ("R4", "reset-draft"),
    ("account.payment", "action_cancel"): ("R4", "post"),
    ("account.payment.register", "action_create_payments"): ("R4", "post"),
    ("account.move.reversal", "refund_moves"): ("R4", "post"),
    ("account.move.reversal", "modify_moves"): ("R4", "post"),
    ("account.move.line", "reconcile"): ("R4", "reconcile"),
    ("account.move.line", "action_reconcile"): ("R4", "reconcile"),
    ("account.move.line", "remove_move_reconcile"): ("R4", "reconcile"),
    ("stock.picking", "button_validate"): ("R4", "stock"),
    ("stock.picking", "action_done"): ("R4", "stock"),
    ("stock.immediate.transfer", "process"): ("R4", "stock"),
    ("stock.backorder.confirmation", "process"): ("R4", "stock"),
    ("stock.backorder.confirmation", "process_cancel_backorder"): ("R4", "stock"),
    ("stock.scrap", "action_validate"): ("R4", "scrap"),
    ("stock.quant", "action_apply_inventory"): ("R4", "inventory"),
    ("mrp.production", "button_mark_done"): ("R4", "mrp"),
    ("mrp.immediate.production", "process"): ("R4", "mrp"),
    ("mrp.production.backorder", "action_close_mo"): ("R4", "mrp"),
    ("mrp.production.backorder", "action_backorder"): ("R4", "mrp"),
    ("pos.session", "action_pos_session_close"): ("R4", "pos"),
    ("pos.session", "action_pos_session_validate"): ("R4", "pos"),
    ("pos.session", "action_pos_session_closing_control"): ("R4", "pos"),
    ("repair.order", "action_repair_end"): ("R4", "repair"),
    # counter-documents (true class; they create drafts, they do not post).
    # Per version: 17 stock.return.picking.create_returns; 18-19 action_create_returns(_all);
    # 20 has no stock.return.picking: stock.picking.action_return opens/creates the draft
    # return, action_return_all fills it and continues toward validation (R4).
    ("stock.picking", "action_return"): ("R2W", "counter-doc"),
    ("stock.picking", "action_exchange"): ("R2W", "counter-doc"),
    ("stock.picking", "action_clear_return"): ("R1", "counter-doc"),
    ("stock.picking", "action_return_all"): ("R4", "stock"),
    ("stock.return.picking", "create_returns"): ("R2W", "counter-doc"),
    ("stock.return.picking", "action_create_returns"): ("R2W", "counter-doc"),
    ("stock.return.picking", "action_create_returns_all"): ("R2W", "counter-doc"),
    # outbound (R5)
    ("*", "message_post"): ("R5", "send"),
    ("*", "send_mail"): ("R5", "send"),
    ("*", "action_send_mail"): ("R5", "send"),
    ("*", "action_send_and_print"): ("R5", "send"),
    ("*", "action_send_sms"): ("R5", "send"),
    ("mailing.mailing", "action_launch"): ("R5", "send"),
    ("mailing.mailing", "action_schedule"): ("R5", "send"),
    ("account.move", "action_invoice_sent"): ("R5", "send"),
    ("sale.order", "action_quotation_send"): ("R5", "send"),
    # delete / merge / archive (R6)
    ("*", "unlink"): ("R6", "delete"),
    ("*", "action_merge"): ("R6", "merge"),
    ("*", "action_archive"): ("R6", "archive"),
    ("*", "action_unarchive"): ("R6", "archive"),
    ("*", "toggle_active"): ("R6", "archive"),
    # verified harmless / non-financial workflow
    ("crm.lead", "action_set_won"): ("R2W", None),
    ("crm.lead", "action_set_won_rainbowman"): ("R2W", None),
    ("res.partner", "open_commercial_entity"): ("R0", "navigate"),
    ("res.partner", "open_parent"): ("R0", "navigate"),
}


def is_financial(model: str) -> bool:
    return model.startswith(FINANCIAL_PREFIXES)


def floored(
    e: Effect | Unresolved, model: str, fields: frozenset[str] | None
) -> Effect | Unresolved:
    """Apply the one sensitivity floor (rules.sensitivity_floor) to a resolved effect."""
    if isinstance(e, Unresolved):
        return e
    fl = sensitivity_floor(model, fields)
    cls, sub = apply_floor(e.cls, e.subkind, fl)
    return (
        e
        if (cls, sub) == (e.cls, e.subkind)
        else Effect(cls, sub, e.evidence + (f"floor {model}",))
    )


def method_effect(model: str, method: str) -> Effect | Unresolved:
    # Methods are not field writes: only the model floor applies here.
    e = floored(_method_effect(model, method), model, frozenset())
    if isinstance(e, Unresolved):
        return e
    fl = method_floor(model, method) or (
        sensitivity_floor(model, frozenset(), "unlink") if method == "unlink" else None
    )
    cls, sub = apply_floor(e.cls, e.subkind, fl)
    return e if (cls, sub) == (e.cls, e.subkind) else Effect(cls, sub, e.evidence + ("floor",))


def deny_unknown(
    e: Effect | Unresolved, model: str, fields: frozenset[str] | None
) -> Effect | Unresolved:
    """Default-deny on code paths: a write/create on a model outside the reviewed opt-in
    allowlist is refused as unresolved unless a sensitivity floor classifies it."""
    if isinstance(e, Unresolved):
        return e
    bad = unknown_fields(model, fields) if fields else frozenset()
    if bad:  # unknown to the inventory: worst field floor of the model, else refuse
        worst = sensitivity_floor(model, None)
        if worst is None:
            return Unresolved(f"{model} fields not in inventory: {sorted(bad)}", e.evidence)
        cls, sub = apply_floor(e.cls, e.subkind, worst)
        return Effect(cls, sub, e.evidence + (f"unknown fields {sorted(bad)}",))
    if model in LOW_RISK_MODELS:
        return e
    if sensitivity_floor(model, fields) is not None:
        return e
    return Unresolved(f"{model} not in known-low-risk allowlist", e.evidence)


def _method_effect(model: str, method: str) -> Effect | Unresolved:
    ev = (f"{model}.{method}",)
    hit = EFFECTS.get((model, method)) or EFFECTS.get(("*", method))
    if hit:
        return Effect(hit[0], hit[1], ev)
    if method.startswith("action_send"):
        return Effect("R5", "send", ev)
    if is_financial(model):
        return Effect("R4", "fail-safe", ev + ("unknown method on financial model",))
    return Unresolved(f"unclassified method {model}.{method}", ev)


def _combine(results: list[Effect | Unresolved], ev: tuple[str, ...]) -> Effect | Unresolved:
    bad = [r for r in results if isinstance(r, Unresolved)]
    if bad:
        return Unresolved(bad[0].reason, ev + bad[0].evidence)
    if not results:
        return Unresolved("no resolvable effects", ev)
    eff = [r for r in results if isinstance(r, Effect)]
    top = worst([e.cls for e in eff])
    sub = next(e.subkind for e in eff if e.cls == top)
    return Effect(top, sub, ev + tuple(x for e in eff for x in e.evidence))


# ---------------------------------------------------------------- arch


def form_arch(port: RpcPort, model: str, view_id: int | None = None) -> str:
    res = port.call(model, "get_views", ([[view_id or False, "form"]],), {})
    arch = res["views"]["form"]["arch"]
    if not isinstance(arch, str) or len(arch) > MAX_ARCH:
        raise ValueError("bad arch")
    return arch


def buttons(arch: str) -> list[dict[str, str]]:
    root = ET.fromstring(arch)
    out = []
    for b in root.iter("button"):
        label = (b.get("string") or " ".join(t.strip() for t in b.itertext() if t.strip())).strip()
        out.append(
            {
                "type": b.get("type") or "",
                "name": b.get("name") or "",
                "label": label,
                "special": b.get("special") or "",
                "context": b.get("context") or "",
            }
        )
    return out


def find(arch: str, *, label: str | None = None, name: str | None = None) -> list[dict[str, str]]:
    """Match by label OR by target name; the label only locates, it never classifies."""
    want = (label or "").strip().casefold()
    return [
        b
        for b in buttons(arch)
        if (name and b["name"] == name) or (want and b["label"].casefold() == want)
    ]


def resolve_button(
    port: RpcPort,
    model: str,
    *,
    label: str | None = None,
    name: str | None = None,
    view_id: int | None = None,
) -> Effect | Unresolved:
    arch = form_arch(port, model, view_id)
    hits = find(arch, label=label, name=name)
    if not hits:
        return Unresolved(f"button {label or name!r} not in live {model} form arch")
    ev = (f"form:{model}",)
    return _combine([classify_ref(port, model, b, 0) for b in hits], ev)


def classify_ref(port: RpcPort, model: str, b: dict[str, str], depth: int) -> Effect | Unresolved:
    if b.get("special"):
        return Effect("R0", "navigate", ("special",))
    if b["type"] == "object":
        return method_effect(model, b["name"])
    if b["type"] == "action":
        if not b["name"].isdigit():
            return Unresolved(f"action ref {b['name']!r} not resolved to an id")
        return classify_action(port, int(b["name"]), depth)
    return Unresolved(f"button type {b['type']!r}")


# ---------------------------------------------------------------- actions


def _read(port: RpcPort, model: str, rid: int, want: list[str]) -> dict[str, Any]:
    have = port.call(model, "fields_get", (), {"attributes": ["type"]})
    rows = port.call(model, "read", ([rid],), {"fields": [f for f in want if f in have]})
    if not rows:
        raise LookupError(f"{model} {rid} not found")
    return rows[0]


def classify_action(port: RpcPort, action_id: int, depth: int = 0) -> Effect | Unresolved:
    if depth > MAX_DEPTH:
        return Unresolved("action chain deeper than 3")
    kind = _read(port, "ir.actions.actions", action_id, ["type"])["type"]
    ev = (f"{kind}:{action_id}",)
    if kind == "ir.actions.server":
        return classify_server_action(port, action_id, depth)
    if kind == "ir.actions.report":
        return Effect("R0", "print", ev)
    if kind != "ir.actions.act_window":
        return Unresolved(f"opaque action type {kind}", ev)
    act = _read(port, "ir.actions.act_window", action_id, ["res_model", "view_id"])
    res_model = act["res_model"]
    mrow = port.call(
        "ir.model", "search_read", ([("model", "=", res_model)],), {"fields": ["transient"]}
    )
    if not mrow:
        return Unresolved(f"window model {res_model} unknown", ev)
    if not mrow[0]["transient"]:
        return Effect("R0", "navigate", ev + (f"opens {res_model}",))
    vid = act.get("view_id")
    arch = form_arch(port, res_model, vid[0] if isinstance(vid, list) and vid else None)
    inner = [classify_ref(port, res_model, b, depth + 1) for b in buttons(arch)]
    res = _combine(inner, ev + (f"wizard {res_model}",))
    if isinstance(res, Unresolved) and is_financial(res_model):
        return Effect("R4", "fail-safe", res.evidence + (res.reason,))
    return res


_RECEIVERS = {"records", "record", "model"}


def _call_target(node: ast.AST, model: str, loopvars: set[str]) -> tuple[str, str] | None:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return None
    recv, meth = node.func.value, node.func.attr
    if isinstance(recv, ast.Name) and recv.id in _RECEIVERS | loopvars:
        return model, meth
    if (
        isinstance(recv, ast.Subscript)
        and isinstance(recv.slice, ast.Constant)
        and isinstance(recv.slice.value, str)
        and (
            (isinstance(recv.value, ast.Name) and recv.value.id == "env")
            or (isinstance(recv.value, ast.Attribute) and recv.value.attr == "env")
        )
    ):
        return recv.slice.value, meth
    return None


def _write_effect(model: str, fields: frozenset[str] | None, ev: tuple[str, ...]) -> Effect:
    """`active` is an archive only when it is the only key; otherwise MAX over all keys."""
    base = (
        Effect("R6", "archive", ev) if fields == frozenset({"active"}) else Effect("R3", None, ev)
    )
    return floored(base, model, fields)  # type: ignore[return-value]


def _literal_keys(call: ast.Call) -> frozenset[str] | None:
    arg = call.args[0] if len(call.args) == 1 and not call.keywords else None
    if isinstance(arg, ast.Dict) and all(
        isinstance(k, ast.Constant) and isinstance(k.value, str) for k in arg.keys
    ):
        return frozenset(k.value for k in arg.keys)  # type: ignore[union-attr]
    return None


def _orm_effect(model: str, meth: str, call: ast.Call) -> Effect | Unresolved:
    if meth == "create":
        keys = _literal_keys(call)
        if keys is None:
            return Unresolved(f"{model}.create with non-literal keys", (f"{model}.create",))
        e = floored(Effect("R1", None, (f"{model}.create",)), model, keys)
        return deny_unknown(e, model, keys)
    if meth == "write":
        keys = _literal_keys(call)
        if keys is None:
            return Unresolved(f"{model}.write with non-literal keys", (f"{model}.write",))
        return deny_unknown(_write_effect(model, keys, (f"{model}.write",)), model, keys)
    return method_effect(model, meth)


def code_effects(code: str, model: str) -> Effect | Unresolved:
    """Accept only `records.m()`, `action = records.m()`, `env['x'].m()`, `for r in records:`."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return Unresolved("server action code does not parse")
    out: list[Effect | Unresolved] = []

    def walk(stmts: list[ast.stmt], loopvars: set[str]) -> bool:
        for st in stmts:
            if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant):
                continue  # docstring / comment string
            if (
                isinstance(st, ast.For)
                and isinstance(st.target, ast.Name)
                and isinstance(st.iter, ast.Name)
                and st.iter.id in _RECEIVERS
                and not st.orelse
            ):
                if not walk(st.body, loopvars | {st.target.id}):
                    return False
                continue
            call = None
            if isinstance(st, ast.Expr):
                call = st.value
            elif (
                isinstance(st, ast.Assign)
                and len(st.targets) == 1
                and isinstance(st.targets[0], ast.Name)
                and st.targets[0].id == "action"
            ):
                call = st.value
            tgt = _call_target(call, model, loopvars) if call is not None else None
            if tgt is None or any(_has_call(a) for a in call.args):  # type: ignore[union-attr]
                return False
            out.append(_orm_effect(tgt[0], tgt[1], call))  # type: ignore[arg-type]
        return True

    if not walk(tree.body, set()):
        return Unresolved("server action code not statically resolvable")
    return _combine(out, ("code",))


def _has_call(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Call) for n in ast.walk(node))


_STATE_EFFECT = {
    "mail_post": ("R5", "send"),
    "sms": ("R5", "send"),
    "webhook": ("R5", "send"),
    "next_activity": ("R5", "send"),  # assignee notification e-mail
    "followers": ("R1", None),
    "remove_followers": ("R1", None),
    "object_create": ("R1", None),
}


def classify_server_action(port: RpcPort, sa_id: int, depth: int = 0) -> Effect | Unresolved:
    if depth > MAX_DEPTH:
        return Unresolved("server action chain deeper than 3")
    row = _read(
        port,
        "ir.actions.server",
        sa_id,
        ["state", "model_name", "code", "child_ids", "update_path", "update_field_id"],
    )
    state, model = row.get("state"), row.get("model_name") or ""
    ev = (f"server:{sa_id}:{state}:{model}",)
    if state == "code":
        res = code_effects(row.get("code") or "", model)
        return (
            Effect(res.cls, res.subkind, ev + res.evidence)
            if isinstance(res, Effect)
            else (Unresolved(res.reason, ev + res.evidence))
        )
    if state == "multi":
        kids = [classify_server_action(port, k, depth + 1) for k in row.get("child_ids") or []]
        return _combine(kids, ev)
    if state == "object_write":
        fields = _sa_field(port, row)
        if fields is None:
            return Unresolved("server action write field not resolved", ev)
        return deny_unknown(_write_effect(model, fields, ev), model, fields)
    if state in _STATE_EFFECT:
        c, s = _STATE_EFFECT[state]
        if state == "object_create":
            return Unresolved("server action create: field set not resolved", ev)
        fl = frozenset()
        e = floored(Effect(c, s, ev), model, fl)
        return deny_unknown(e, model, fl) if state == "object_create" else e
    return Unresolved(f"server action state {state!r}", ev)


# ---------------------------------------------------------------- automations


def _sa_field(port: RpcPort, row: dict[str, Any]) -> frozenset[str] | None:
    """Exact technical field name written by an object_write action (None = unknown)."""
    path = row.get("update_path")
    if isinstance(path, str) and path:
        return frozenset({path.split(".")[0]})
    fld = row.get("update_field_id")
    if isinstance(fld, list) and fld and isinstance(fld[0], int):
        try:
            got = port.call("ir.model.fields", "read", ([fld[0]],), {"fields": ["name"]})
            name = got[0].get("name") if got else None
        except Exception:  # noqa: BLE001 - unknown field -> assume sensitive
            name = None
        if isinstance(name, str) and name:
            return frozenset({name})
    return None


_NOT_WRITE_TRIGGERED = ("on_time", "on_webhook")


def automation_floor(port: RpcPort, model: str) -> Effect | Unresolved | None:
    """Write/onchange-triggered base.automation on the model raise the class of a write."""
    if not port.call("ir.model", "search", ([("model", "=", "base.automation")],), {}):
        return None
    have = port.call("base.automation", "fields_get", (), {"attributes": ["type"]})
    acts = "action_server_ids" if "action_server_ids" in have else "action_server_id"
    rows = port.call(
        "base.automation",
        "search_read",
        ([("model_id.model", "=", model), ("active", "=", True)],),
        {"fields": ["trigger", acts]},
    )
    found: list[Effect | Unresolved] = []
    for r in rows:
        if str(r.get("trigger") or "").startswith(_NOT_WRITE_TRIGGERED):
            continue
        ids = r.get(acts) or []
        ids = [ids[0]] if acts == "action_server_id" and ids else ids
        found += [classify_server_action(port, int(i), 1) for i in ids]
    if not found:
        return None
    return _combine(found, (f"automation:{model}",))


def server_action_by_name(port: RpcPort, name: str, model: str | None) -> int | None:
    dom: list[Any] = [("name", "=", name)]
    if model:
        dom.append(("model_id.model", "=", model))
    ids = port.call("ir.actions.server", "search", (dom,), {"limit": 2})
    return ids[0] if len(ids) == 1 else None


def cron_action(port: RpcPort, name: str) -> int | None:
    rows = port.call(
        "ir.cron",
        "search_read",
        ([("cron_name", "=", name)],),
        {"fields": ["ir_actions_server_id"], "context": {"active_test": False}},
    )
    if len(rows) != 1 or not rows[0].get("ir_actions_server_id"):
        return None
    return rows[0]["ir_actions_server_id"][0]


def has_button(port: RpcPort, model: str, method: str) -> bool:
    try:
        return bool(find(form_arch(port, model), name=method))
    except Exception:  # noqa: BLE001 - model absent on this version -> not verified
        return False
