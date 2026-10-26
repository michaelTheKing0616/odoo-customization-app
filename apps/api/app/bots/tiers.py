"""TAX-TIERS: every bot task falls in one tier; cross-tier tasks compose; refusals are graded.

T1 data/settings  - records, settings, sequences, parameters, groups, stock module
                    install/upgrade, running existing buttons/wizards/actions/reports.
T2 metadata/automation - fields, views, reports, automations, server actions defined as
                    data in Odoo (no module code).
T3 module code    - Python/XML module code (migrations, integrations, performance work).

Read-only: never writes to Odoo. Uses the risk classifier (sensitivity floor, model of a
task) and versioncaps (does the model exist in this version/edition). Fail closed: an
unknown task kind, an unknown model verdict or a failing check is "unknown", never allowed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.bots.risk import classifier
from app.bots.versioncaps import caps

T1, T2, T3 = 1, 2, 3
TIER_NAMES = {T1: "data and settings", T2: "metadata and automation", T3: "module code"}

# What bots may run today. T3 needs code authoring + module test gate (not built yet).
SUPPORTED_TIERS: frozenset[int] = frozenset({T1, T2})

_T1_KINDS = frozenset({"m", "s", "seq", "param", "g", "b", "wiz", "sa", "cron", "t", "r"})
_T2_KINDS = frozenset({"c", "v"})
_T3_KINDS = frozenset({"code"})
_T1_MOD_VERBS = frozenset({"install", "upgrade", "uninstall"})

# Grades, mildest first.
OK = "ok"
NEEDS_STEP = "needs-step"  # possible after a named prior step (install a module)
NEEDS_EDITION = "needs-edition"  # Enterprise-only in this version
NOT_IN_VERSION = "not-in-version"  # model/field does not exist in this Odoo version
OUT_OF_TIER = "out-of-tier"  # tier exists but bots do not run it yet
UNKNOWN = "unknown"  # could not classify or verify: nothing runs

CLAIM = (
    "Ingenium bots handle Odoo data and settings (T1) and Odoo metadata and automation "
    "(T2: fields, views, reports, automations) on Odoo 17 to 20, with checks before every "
    "change. Module code (T3) is not done by bots yet: they say so and tell you what you "
    "can do instead. When a task cannot be checked, nothing runs."
)


def tier_of(task_id: Any) -> int | None:
    """Tier of a catalogue task id; None when the kind is unknown (fail closed)."""
    if not isinstance(task_id, str) or ":" not in task_id:
        return None
    kind, _, rest = task_id.partition(":")
    if not rest:
        return None
    if kind == "mod":
        return T1 if rest.rpartition(":")[2] in _T1_MOD_VERBS else None
    if kind in _T1_KINDS:
        return T1
    if kind in _T2_KINDS:
        return T2
    if kind in _T3_KINDS:
        return T3
    return None


@dataclass(frozen=True)
class Assessment:
    task_id: str
    tier: int | None
    grade: str
    reason: str
    instead: tuple[str, ...] = ()
    floor: tuple[str, str] | None = None
    prior_steps: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.grade == OK

    def message(self) -> str:
        """Plain-language refusal (empty when allowed)."""
        if self.allowed:
            return ""
        txt = self.reason
        if self.instead:
            txt += " What you can do instead: " + "; ".join(self.instead) + "."
        return txt


def _instead_t3(task_id: str) -> tuple[str, ...]:
    return (
        "check whether a field, view, report or automation (T2) gives the same result",
        "ask a developer to build it as a module; Ingenium can write the requirement",
        "after the module is installed, bots can configure and use it (T1)",
    )


def assess(
    task_id: Any,
    *,
    version: Any,
    edition: str = "community",
    installed_modules: Iterable[str] | None = None,
    supported: frozenset[int] = SUPPORTED_TIERS,
) -> Assessment:
    tid = task_id if isinstance(task_id, str) else repr(task_id)
    tier = tier_of(task_id)
    if tier is None:
        return Assessment(
            tid,
            None,
            UNKNOWN,
            "Ingenium does not recognise this kind of task, so it will not run it.",
            ("describe the change as a record, setting, field, view or automation change",),
        )
    try:
        floor = classifier.task_floor(tid)
    except Exception:  # noqa: BLE001 - fail closed
        return Assessment(
            tid, tier, UNKNOWN, "The safety check for this task failed, so nothing runs."
        )
    if tier not in supported:
        return Assessment(
            tid,
            tier,
            OUT_OF_TIER,
            f"This needs {TIER_NAMES[tier]} (T{tier}), which bots do not do yet.",
            _instead_t3(tid) if tier == T3 else (),
            floor,
        )
    model = classifier._model_of(tid)  # noqa: SLF001 - shared task-id parser
    if model is None:
        return Assessment(tid, tier, OK, "", (), floor)
    if installed_modules is None:
        return Assessment(
            tid,
            tier,
            UNKNOWN,
            "Ingenium could not read which apps are installed, so it cannot check this task.",
            ("reconnect the database and try again",),
            floor,
        )
    v = caps.availability(version, edition, list(installed_modules), model)
    if v.status == "installed-ok":
        return Assessment(tid, tier, OK, "", (), floor)
    if v.status == "available-needs-install":
        steps = tuple(
            f"mod:{m}:install" for m in ((v.module,) if v.module else ()) + v.missing_depends
        )
        return Assessment(
            tid,
            tier,
            NEEDS_STEP,
            f"This needs an app that is not installed yet. {v.reason}",
            ("install the app first (bots can do this as a separate, approved step)",),
            floor,
            tuple(dict.fromkeys(steps)),
        )
    if v.status == "enterprise-only":
        return Assessment(
            tid,
            tier,
            NEEDS_EDITION,
            f"This is only in Odoo Enterprise. {v.reason}",
            ("use a Community alternative if one exists, or upgrade to Enterprise",),
            floor,
        )
    if v.status == "not-in-this-version":
        alt = tuple(f"this exists in Odoo {o}" for o in v.other_versions)
        return Assessment(
            tid, tier, NOT_IN_VERSION, f"This is not in this Odoo version. {v.reason}", alt, floor
        )
    return Assessment(
        tid,
        tier,
        UNKNOWN,
        f"Ingenium could not confirm this is possible. {v.reason}",
        ("check the model name, or connect a database that has it",),
        floor,
    )


@dataclass(frozen=True)
class Plan:
    """Composition of a cross-tier task. Runs only if every part is allowed (all or nothing)."""

    parts: tuple[Assessment, ...]
    order: tuple[str, ...] = field(default=())
    tier: int | None = None
    grade: str = UNKNOWN

    @property
    def allowed(self) -> bool:
        return self.grade == OK

    def message(self) -> str:
        if self.allowed:
            return ""
        bad = [p for p in self.parts if not p.allowed]
        ok = [p.task_id for p in self.parts if p.allowed]
        lines = [f"Nothing runs: {len(bad)} of {len(self.parts)} parts cannot be done."]
        lines += [f"- {p.task_id}: {p.message()}" for p in bad]
        if ok:
            lines.append(
                "These parts could run on their own if you still want them: " + ", ".join(ok) + "."
            )
        return "\n".join(lines)


_GRADE_RANK = {
    OK: 0,
    NEEDS_STEP: 1,
    NEEDS_EDITION: 2,
    NOT_IN_VERSION: 3,
    OUT_OF_TIER: 4,
    UNKNOWN: 5,
}


def compose(parts: Iterable[Assessment]) -> Plan:
    """Composition rule: the task's tier is its highest part tier; the grade is its worst part
    grade (all-or-nothing, no partial run); order is code (T3), then metadata (T2), then data
    (T1), each tier in the given order, so data never lands before the structure it needs.
    Prior steps (module installs) are not added silently: they stay a NEEDS_STEP refusal."""
    ps = tuple(parts)
    if not ps:
        return Plan((), (), None, UNKNOWN)
    tiers = [p.tier for p in ps]
    tier = None if None in tiers else max(t for t in tiers if t is not None)
    grade = max((p.grade for p in ps), key=_GRADE_RANK.__getitem__)
    order = tuple(p.task_id for p in sorted(ps, key=lambda p: -(p.tier or 0)))
    return Plan(ps, order, tier, grade)
