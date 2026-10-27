"""BOT-RISK-CLASSIFIER: task id -> exactly one class (R0-R9/R2W/R8C), controls and tier.

`classify(task_id, ctx)` returns a Decision or a Refusal; `check(decision, gate_ctx)` runs
the RF-* engine. Every refusal is written to the BV-AUDIT store (decision="refused", reason
starts with the rule id); if that write fails, RiskAuditUnavailable is raised (fail-closed).

Buttons, server actions, wizards and crons are classified per target (buttons.py), never by
label or by the catalogue's name-derived class. Catalogue data: catalogue_rows.json,
generated from ~/.ingenium_nf/taxonomy/catalogue.csv by gen_risk_rows.py (sha256 inside).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.bots.risk import buttons as bt
from app.bots.risk import rules
from app.bots.risk.rules import DEFAULT_POLICY, Allowed, Policy, Refusal, Route

ROWS_FILE = Path(__file__).with_name("catalogue_rows.json")


class RiskAuditUnavailable(RuntimeError):
    """A refusal could not be audited. Nothing may run."""


@dataclass(frozen=True)
class ClassifyCtx:
    version: int
    route: Route
    connection_id: str | None = None
    db_name: str = ""
    port: Any = None  # bt.RpcPort over public ORM; None = offline (catalogue + tables only)
    label: str | None = None  # b: tasks: locate the live button by label (never classifies)
    view_id: int | None = None
    fields: frozenset[str] | None = None  # m: writes: exact fields (None = unknown, assume worst)
    policy: Policy = DEFAULT_POLICY


@dataclass(frozen=True)
class Decision:
    task_id: str
    cls: str
    subkind: str | None
    controls: tuple[str, ...]
    tier: int
    route: Route
    version: int
    strict_copy: bool
    rpc: tuple[str, ...]
    security_models: tuple[str, ...]
    mitigation: dict[str, Any] = field(default_factory=dict)
    mitigation_refusal: str = ""
    evidence: tuple[str, ...] = ()
    allowed: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {"class": self.cls, "controls": list(self.controls), "tier": f"L{self.tier}"}


@lru_cache(maxsize=1)
def catalogue() -> tuple[dict[str, tuple[str, frozenset[int]]], dict[str, list[str]], str]:
    doc = json.loads(ROWS_FILE.read_text())
    rows: dict[str, tuple[str, frozenset[int]]] = {}
    for key, ids in doc["groups"].items():
        cls, *vers = key.split("|")
        vs = frozenset(int(v) for v in vers)
        for i in ids:
            rows[i] = (cls, vs)
    if len(rows) != doc["rows_total"]:
        raise ValueError("catalogue_rows.json is inconsistent")
    return rows, doc["controls"], doc["sha256"]


# ---------------------------------------------------------------- audit


def audit_refusal(cid: str | None, db_name: str, r: Refusal) -> Refusal:
    from app.bot_verify import targets as tg

    store = tg.ensure_audit_store()
    if store is None:
        raise RiskAuditUnavailable("audit store not configured")
    try:
        store.record(cid, db_name, "refused", r.text())
    except Exception as exc:  # noqa: BLE001 - an unaudited refusal must stop everything
        raise RiskAuditUnavailable("audit write failed") from exc
    return r


def check(
    decision: Decision, ctx: rules.GateCtx, proofs: Callable[[str], bool] | None = None
) -> Allowed | Refusal:
    """``proofs`` verifies proof-backed controls (before_image.RouteA.check /
    snapshot.Verified); without it they are refused even when named in ``ctx.proven``."""
    res = rules.gate_with_proofs(decision, ctx, proofs)
    if isinstance(res, Refusal):
        audit_refusal(ctx.connection_id, ctx.db_name, res)
    return res


# ---------------------------------------------------------------- mapping overrides (AC3)

_AUTH_PARAM = re.compile(r"auth|password|web\.base\.url|signup|database", re.I)
_OUTBOUND_CRON = re.compile(r"\b(e-?mails?|mails?|sms|sync\w*|synchroni[sz]\w*|rates?|iap)\b", re.I)
_SECURITY = ("ir.access", "ir.model.access", "ir.rule", "res.groups", "res.users")


def _parts(task_id: str) -> tuple[str, str]:
    kind, _, rest = task_id.partition(":")
    return kind, rest


def mapped_class(task_id: str, cls: str) -> tuple[str, str | None]:
    kind, rest = _parts(task_id)
    if kind == "seq":
        return "R8C", "sequence"
    if kind == "param" and _AUTH_PARAM.search(rest):
        return "R8", "auth-param"
    if kind == "cron" and _OUTBOUND_CRON.search(rest):
        return "R5", "send"
    if kind == "s" and rest.startswith("module_"):
        return "R7", "module"
    if kind == "mod":
        verb = rest.rsplit(":", 1)[-1]
        return ("R9", "uninstall") if verb == "uninstall" else ("R7", "module")
    if kind == "m":
        verb = rest.split(":")[-1]
        if verb in ("delete", "unlink"):
            return "R6", "delete"
        if verb == "merge":
            return "R6", "merge"
        if verb == "archive":
            return (cls, "archive") if rules.rank(cls) >= rules.rank("R2W") else ("R2W", "archive")
    if cls == "R9":
        return "R9", "metadata"
    return cls, None


# ---------------------------------------------------------------- mitigations (AC8)

_COUNTER = {
    "post": "account.move.reversal (reversal entry)",
    "reconcile": "account.move.line reconcile/remove_move_reconcile (counter-action)",
    "inventory": "stock.quant re-count (action_apply_inventory)",
    "mrp": "mrp.unbuild",
}


def mitigation(cls: str, sub: str | None, version: int, port: Any) -> tuple[dict, str]:
    if cls == "R4":
        if sub == "reset-draft":
            return {}, ""  # gate refuses on prod; allowed only on disposable copies
        if sub == "stock":
            if version <= 19:
                return {"counter": "stock.return.picking", "versions": "17-19"}, ""
            if port is not None and bt.has_button(port, "stock.picking", "action_return"):
                return {"counter": "stock.picking.action_return", "verified": "live v20"}, ""
            return {}, "Odoo 20 stock return route not verified on this target"
        if sub in _COUNTER:
            return {"counter": _COUNTER[sub]}, ""
        return {}, f"no documented counter-document for R4 ({sub})"
    if cls == "R5":
        return {"hold": "queued mail.mail; ir.mail_server inactive on the copy"}, ""
    if cls == "R6":
        return {"prefer": "action_archive / action_unarchive"}, ""
    if cls == "R8":
        return {"keep": "res.users.apikeys of the Bot user", "lockout": "simulate on copy"}, ""
    if cls == "R8C":
        return {"report": "data-impact report for L3 when transactions exist"}, ""
    if cls == "R9":
        return {"preview": "base.module.uninstall data-loss list on the copy"}, ""
    return {}, ""


# ---------------------------------------------------------------- classify


def _refuse(ctx: ClassifyCtx, rule: str, missing: str, reason: str) -> Refusal:
    return audit_refusal(ctx.connection_id, ctx.db_name, Refusal(rule, missing, reason))


def _effect(task_id: str, base: str, ctx: ClassifyCtx) -> bt.Effect | bt.Unresolved:
    kind, rest = _parts(task_id)
    port = ctx.port
    if kind == "b":
        model, _, method = rest.rpartition(":")
        if port is not None and (ctx.label or ctx.view_id):
            live = bt.find(bt.form_arch(port, model, ctx.view_id), label=ctx.label, name=method)
            got = {(b["type"], b["name"]) for b in live}
            if got != {("object", method)}:
                res = bt.resolve_button(
                    port, model, label=ctx.label, name=method, view_id=ctx.view_id
                )
                why = f"live button resolves to {sorted(got)} not {method}"
                ev = res.evidence + ((f"class {res.cls}",) if isinstance(res, bt.Effect) else ())
                return bt.Unresolved(why, ev)
        return bt.method_effect(model, method)
    if kind == "sa":
        name, _, model = rest.rpartition(":")
        if port is None:
            return bt.Unresolved("server action needs live resolution")
        sid = bt.server_action_by_name(port, name, model or None)
        if sid is None:
            return bt.Unresolved("server action not found uniquely")
        return bt.classify_server_action(port, sid)
    if kind == "wiz":
        model = rest.rpartition(":")[0]
        if port is None:
            if bt.is_financial(model):
                return bt.Effect("R4", "fail-safe", (f"wizard {model} offline",))
            return bt.Unresolved("wizard needs live resolution")
        arch = bt.form_arch(port, model)
        inner = [bt.classify_ref(port, model, b, 1) for b in bt.buttons(arch)]
        res = bt._combine(inner, (f"wizard {model}",))
        if isinstance(res, bt.Unresolved) and bt.is_financial(model):
            return bt.Effect("R4", "fail-safe", res.evidence + (res.reason,))
        return res
    cls, sub = mapped_class(task_id, base)
    if kind == "cron" and port is not None:
        sid = bt.cron_action(port, rest)
        if sid is None:
            return bt.Unresolved("cron not found uniquely")
        live = bt.classify_server_action(port, sid)
        if isinstance(live, bt.Unresolved):
            return live
        if rules.rank(live.cls) > rules.rank(cls):
            return live
    return bt.Effect(cls, sub, ("catalogue",))


_READ_VERBS = ("export",)


def _tier_floor(task_id: str, ctx: ClassifyCtx) -> int:
    """Reviewed approval floor (rules.FIELD_TIER_FLOORS) for the fields a write task touches."""
    kind, rest = _parts(task_id)
    if kind == "s":
        return rules.field_tier_floor("res.config.settings", frozenset({rest}))
    if kind == "m" and rest.rsplit(":", 1)[-1] not in _READ_VERBS:
        return rules.field_tier_floor(_model_of(task_id), ctx.fields)
    return 1


def task_floor(task_id: str, fields: frozenset[str] | None = None) -> tuple[str, str] | None:
    """The sensitivity floor of the model/fields/key a task touches (reads have none)."""
    kind, rest = _parts(task_id)
    if kind == "s":
        return rules.sensitivity_floor("res.config.settings", frozenset({rest}))
    if kind == "seq":
        return rules.sensitivity_floor("ir.sequence", None)
    if kind == "g":
        return rules.sensitivity_floor("res.groups", None)
    if kind == "param":
        return rules.PARAM_FLOORS.get(rest) or rules.sensitivity_floor("ir.config_parameter", None)
    if kind == "mod":
        fl = rules.MODULE_FLOORS.get(rest)
        if rest.startswith("l10n_") and rest.endswith(":install"):  # chart install
            fl = rules.max_floor(fl, ("R8C", "irr"))
        return fl
    model = _model_of(task_id)
    if not model:
        return None
    if kind == "m":
        parts = rest.split(":")
        verb = parts[-1]
        if verb in _READ_VERBS:
            return None
        if fields is None:
            if len(parts) >= 3 and parts[1] == "workflow":
                fields = frozenset({verb})
            elif verb == "archive":
                fields = frozenset({"active"})
            elif verb in ("delete", "unlink", "merge"):
                return rules.sensitivity_floor(model, frozenset(), "unlink")
        return rules.sensitivity_floor(model, fields)
    if kind in ("b", "wiz"):
        meth = rest.rpartition(":")[2]
        return (
            rules.max_floor(
                rules.sensitivity_floor(model, frozenset()), rules.method_floor(model, meth)
            )
            if rules.method_floor(model, meth)
            else rules.sensitivity_floor(model, frozenset())
        )
    return rules.sensitivity_floor(model, frozenset())


def _model_of(task_id: str) -> str | None:
    kind, rest = _parts(task_id)
    if kind == "m":
        return rest.split(":")[0] or None
    if kind in ("b", "wiz"):
        return rest.rpartition(":")[0] or None
    if kind == "sa":
        return rest.rpartition(":")[2] or None
    return None


def classify(task_id: str, ctx: ClassifyCtx) -> Decision | Refusal:
    if ctx.version not in rules.SUPPORTED_VERSIONS:
        return _refuse(ctx, "RF-ANY", "version", f"Odoo {ctx.version} outside 17-20")
    if ctx.route not in ("A", "B"):
        return _refuse(ctx, "RF-ANY", "route", f"unknown route {ctx.route!r}")
    rows, controls, _ = catalogue()
    row = rows.get(task_id)
    if row is None:
        return _refuse(ctx, "RF-ANY", "catalogue", "unknown task: escalate, never improvise")
    base, versions = row
    if ctx.version not in versions:
        return _refuse(ctx, "RF-ANY", "catalogue", f"task not in catalogue for Odoo {ctx.version}")
    try:
        eff = _effect(task_id, base, ctx)
        model = _model_of(task_id)
        if isinstance(eff, bt.Effect) and ctx.port is not None and model:
            floor = bt.automation_floor(ctx.port, model)
            if isinstance(floor, bt.Unresolved):
                eff = bt.Unresolved(f"automation on {model}: {floor.reason}", floor.evidence)
            elif floor is not None and rules.rank(floor.cls) > rules.rank(eff.cls):
                eff = bt.Effect(floor.cls, floor.subkind, eff.evidence + floor.evidence)
    except Exception as exc:  # noqa: BLE001 - live metadata unreadable -> refuse, never guess
        return _refuse(ctx, "RF-ANY", "classification", f"live resolution failed: {exc!s}"[:150])
    if isinstance(eff, bt.Unresolved):
        return _refuse(ctx, "RF-ANY", "classification", f"unclassified: {eff.reason}")
    # One floor on every path: MAX(path, catalogue class, model/field sensitivity floor).
    cls, sub = rules.apply_floor(eff.cls, eff.subkind, (base, eff.subkind or ""))
    model = _model_of(task_id)
    if ctx.fields and task_id.startswith("m:") and model:
        bad = rules.unknown_fields(model, ctx.fields)
        if bad and rules.sensitivity_floor(model, None) is None:
            return _refuse(
                ctx, "RF-ANY", "classification", f"fields not in inventory: {sorted(bad)}"
            )
    fl = task_floor(task_id, ctx.fields)
    if (
        ctx.fields
        and task_id.startswith("m:")
        and model
        and rules.unknown_fields(model, ctx.fields)
    ):
        fl = rules.max_floor(fl, rules.sensitivity_floor(model, None))  # type: ignore[arg-type]
    cls, sub = rules.apply_floor(cls, sub or None, fl)
    mit, mit_refusal = mitigation(cls, sub, ctx.version, ctx.port)
    v20 = ctx.version >= 20
    sec = cls == "R8" or (model or "").startswith(_SECURITY)
    return Decision(
        task_id=task_id,
        cls=cls,
        subkind=sub,
        controls=tuple(rules.route_controls(cls, sub, ctx.route, controls[cls])),
        tier=max(rules.required_tier(cls, sub, ctx.route, ctx.policy), _tier_floor(task_id, ctx)),
        route=ctx.route,
        version=ctx.version,
        strict_copy=rules.strict_copy(cls, sub, ctx.route),
        rpc=("json2",) if v20 else ("json2", "jsonrpc") if ctx.version == 19 else ("jsonrpc",),
        security_models=(("ir.access",) if v20 else ("ir.model.access", "ir.rule")) if sec else (),
        mitigation=mit,
        mitigation_refusal=mit_refusal,
        evidence=eff.evidence,
    )
