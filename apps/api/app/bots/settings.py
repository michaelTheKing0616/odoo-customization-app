"""BOT-T1-SETTINGS: change Odoo Settings (res.config.settings) through the write gate only.

plan(): every field must be a catalogue ``s:`` row for this version, exist on the live
settings form, be writable, and carry a value of the right type; anything else is refused.
Turning a ``module_*`` field off would uninstall an app: always refused. Before-values come from
``default_get`` (what the Settings page shows). Fields already at the target are dropped.

apply(): two guarded one-record jobs (create the settings wizard, then press its Save,
``execute``), each its own audit claim and grant. Re-running a plan whose target is already live
is a no-op. Afterwards the values are read back and the number of active administrators is
checked; a mismatch or a lost administrator turns the kill switch on.

undo(): a new plan back to the before-values, applied the same way. App installs have no undo.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.bots import guard as gd
from app.bots.risk import classifier as cl
from app.bots.risk import rules as rr
from app.bots.risk.rules import Refusal

MODEL = "res.config.settings"
RF, MISS = "RF-ANY", "settings"
Read = Callable[[str, str, Sequence[Any], dict[str, Any] | None], Any]
_SIMPLE = {
    "boolean": (bool,),
    "integer": (int,),
    "float": (int, float),
    "char": (str,),
    "selection": (str, int),
    "many2one": (int,),
}


# Reviewed: settings that change where outgoing mail goes. Undoable, but a person approves (L2).
L2_SETTINGS: Mapping[str, str] = {
    "external_email_server_default": "changes which server sends all outgoing email",
}


def _no(reason: str) -> Refusal:
    return Refusal(RF, MISS, reason[:180])


def _plain(v: Any) -> Any:
    if isinstance(v, (list, tuple)) and len(v) == 2 and isinstance(v[0], int):
        return v[0]  # many2one as [id, name]
    return False if v is None else v


@dataclass(frozen=True)
class Plan:
    values: dict[str, Any]  # only fields that change
    before: dict[str, Any]
    cls: str
    tier: int
    needs_snapshot: bool
    lines: tuple[str, ...] = ()

    @property
    def noop(self) -> bool:
        return not self.values


@dataclass
class Result:
    status: str  # done | noop | refused | needs-human | mismatch | lockout
    plan: Plan | None = None
    after: dict[str, Any] = field(default_factory=dict)
    refusal: Refusal | None = None
    replayed: bool = False


class SettingsBot:
    def __init__(self, read: Read, gate: gd.WriteGate, *, version: int, db: str) -> None:
        self.read, self.gate, self.version, self.db = read, gate, version, db

    # ---------- plan
    def plan(self, changes: Mapping[str, Any]) -> Plan | Refusal:
        if not changes:
            return _no("no settings to change")
        names = sorted(changes)
        try:
            meta = self.read(
                MODEL, "fields_get", [names], {"attributes": ["type", "selection", "readonly"]}
            )
        except Exception as exc:  # noqa: BLE001 - unreadable form = refused
            return _no(f"settings form unreadable ({type(exc).__name__})")
        cls, tier, snap, lines = "R2", 1, False, []
        for f in names:
            v, m = changes[f], (meta or {}).get(f)
            if m is None:
                return _no(f"{f}: not on this database's Settings page")
            if m.get("readonly"):
                return _no(f"{f}: read-only setting")
            if (ref := self._typed(f, v, m)) is not None:
                return ref
            if f.startswith("module_") and v is False:
                return _no(f"{f}: turning an app off uninstalls it and deletes its data: refused")
            try:
                d = cl.classify(f"s:{f}", cl.ClassifyCtx(self.version, "A", db_name=self.db))
            except Exception as exc:  # noqa: BLE001 - no audit of the refusal = still refused
                return _no(f"{f}: not classifiable ({type(exc).__name__})")
            if isinstance(d, Refusal) or not getattr(d, "allowed", False):
                return _no(f"{f}: {getattr(d, 'reason', 'not allowed')}")
            if rr.rank(d.cls) > rr.rank(cls):
                cls = d.cls
            tier = max(tier, d.tier)
            if f in L2_SETTINGS and tier < 2:
                tier = 2
                lines.append(f"{f}: {L2_SETTINGS[f]} (needs L2 approval)")
            if f.startswith("module_"):
                snap, tier = True, 3
                lines.append(f"{f}: installs an app (no automatic undo; snapshot required)")
        try:
            before = self._current(names)
        except Exception as exc:  # noqa: BLE001
            return _no(f"current settings unreadable ({type(exc).__name__})")
        vals = {f: changes[f] for f in names if before.get(f) != changes[f]}
        lines += [f"{f}: {before.get(f)!r} -> {v!r}" for f, v in vals.items()]
        return Plan(vals, {f: before.get(f) for f in vals}, cls, tier, snap, tuple(lines))

    def _typed(self, f: str, v: Any, m: Mapping[str, Any]) -> Refusal | None:
        t = m.get("type")
        ok = _SIMPLE.get(str(t))
        if ok is None:
            return _no(f"{f}: {t} settings are not supported")
        if t != "boolean" and isinstance(v, bool) or not isinstance(v, ok):
            if not (v is False and t != "boolean"):  # False clears a non-boolean setting
                return _no(f"{f}: value {v!r} is not a {t}")
        if t == "selection" and v is not False:
            keys = {k for k, _ in (m.get("selection") or [])}
            if v not in keys:
                return _no(f"{f}: {v!r} is not one of {sorted(map(str, keys))[:8]}")
        if t == "many2one" and v is not False and v <= 0:
            return _no(f"{f}: bad record id {v!r}")
        return None

    def _current(self, names: Sequence[str]) -> dict[str, Any]:
        got = self.read(MODEL, "default_get", [list(names)], None) or {}
        return {f: _plain(got.get(f, False)) for f in names}

    def admins(self) -> int:
        ref = self.read(
            "ir.model.data",
            "search_read",
            [[("module", "=", "base"), ("name", "=", "group_system")]],
            {"fields": ["res_id"], "limit": 1},
        )
        if not ref:
            raise RuntimeError("administrator group not found")
        fg = self.read("res.users", "fields_get", [["groups_id", "group_ids"]], {"attributes": []})
        col = "group_ids" if "group_ids" in (fg or {}) else "groups_id"
        dom = [(col, "in", [ref[0]["res_id"]]), ("share", "=", False), ("active", "=", True)]
        return int(self.read("res.users", "search_count", [dom], None))

    # ---------- apply
    def apply(self, plan: Plan, spec: gd.RunSpec) -> Result:
        if plan.noop:
            return Result("noop", plan)
        if spec.approval.level < plan.tier:
            return Result("refused", plan, refusal=_no(f"needs L{plan.tier} approval"))
        if plan.needs_snapshot and not spec.snapshot_id:
            return Result("refused", plan, refusal=_no("app install needs a snapshot first"))
        names = sorted(plan.values)
        try:
            now = self._current(names)
            if now == plan.values:  # already live (re-run after success or crash): no write
                return Result("done", plan, now, replayed=True)
            if now != plan.before:
                return Result("refused", plan, refusal=_no("changed since the preview: plan again"))
            admins = self.admins()
        except Exception as exc:  # noqa: BLE001
            return Result("refused", plan, refusal=_no(f"pre-check failed ({type(exc).__name__})"))
        try:
            wid = self.gate.call(self._spec(spec, plan, "create"), MODEL, "create", [plan.values])
            if wid is None:
                return Result("needs-human", plan, refusal=_no("gate saw this run already"))
            wid = wid[0] if isinstance(wid, list) else wid
            self.gate.call(self._spec(spec, plan, "execute"), MODEL, "execute", [[wid]])
        except PermissionError as exc:
            return Result("refused", plan, refusal=_no(str(exc)))
        except Exception as exc:  # noqa: BLE001 - incl. AuditError: stop, a person checks
            return Result("needs-human", plan, refusal=_no(f"save failed ({type(exc).__name__})"))
        return self._readback(plan, spec, admins)

    def _spec(self, spec: gd.RunSpec, plan: Plan, step: str) -> gd.RunSpec:
        return dataclasses.replace(
            spec,
            task_id="s:" + ",".join(sorted(plan.values))[:120],
            risk_class=plan.cls,
            idempotency_key=f"{spec.idempotency_key}:{step}",
            approval=dataclasses.replace(spec.approval),  # grants are single-use per job
        )

    def _readback(self, plan: Plan, spec: gd.RunSpec, admins: int) -> Result:
        try:
            after = self._current(sorted(plan.values))
            left = self.admins()
        except Exception as exc:  # noqa: BLE001
            self._kill(spec, "settings readback unreadable")
            return Result(
                "needs-human", plan, refusal=_no(f"readback failed ({type(exc).__name__})")
            )
        if left < 1 or left < admins:
            self._kill(spec, "settings change removed an administrator")
            return Result("lockout", plan, after, refusal=_no(f"administrators {admins} -> {left}"))
        if after != plan.values:
            self._kill(spec, "settings readback mismatch")
            bad = sorted(f for f in plan.values if after.get(f) != plan.values[f])
            return Result("mismatch", plan, after, refusal=_no(f"did not stick: {bad[:8]}"))
        return Result("done", plan, after)

    def _kill(self, spec: gd.RunSpec, why: str) -> None:
        try:
            self.gate.switch.turn_on(spec.db_fingerprint, "system", why)
        except Exception:  # noqa: BLE001, S110 - best effort; the result already says stop
            pass

    # ---------- undo
    def undo(self, done: Result) -> Plan | Refusal:
        """A plan back to the before-values; apply it like any plan (same checks)."""
        if done.status != "done" or done.plan is None or done.replayed:
            return _no("only a completed, non-replayed change can be undone")
        mods = [f for f in done.plan.values if f.startswith("module_")]
        if mods:
            return _no(f"app installs have no undo (needs a snapshot restore): {mods[:5]}")
        try:
            if self._current(sorted(done.after)) != done.after:
                return _no("settings changed since they were applied: undo refused")
        except Exception as exc:  # noqa: BLE001
            return _no(f"current settings unreadable ({type(exc).__name__})")
        return self.plan(done.plan.before)
