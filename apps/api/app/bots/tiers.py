"""TAX-TIERS: every bot task falls in one tier; cross-tier tasks compose; refusals are graded.

T1 data/settings  - records, settings, sequences, parameters, groups, stock module
                    install/upgrade/uninstall, running existing buttons/wizards/actions/reports.
T2 metadata/automation - fields, views, reports, automations defined as data (no module code).
T3 module code    - Python/XML module code (migrations, integrations, performance work).

A tier runs only when every capability it requires is present in ``_CAPABILITIES`` (code
constants, flipped only when the real module lands; never by task text or caller input).
T3 needs module authoring and a module test gate; both are absent today -> "not built yet".

Grades, mildest first: ok, approval-required (uninstall), needs-step (install an app first),
needs-edition, not-in-version, not-built-yet, unknown.

Read-only: never writes to Odoo. Uses the risk classifier (sensitivity floor, model of a
task) and versioncaps (does the model exist in this version/edition). Fail closed: an
unknown task kind, an unextractable model, bad input or a failing check is "unknown".
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.bots.risk import classifier
from app.bots.versioncaps import caps

T1, T2, T3 = 1, 2, 3
TIER_NAMES = {T1: "data and settings", T2: "metadata and automation", T3: "module code"}

# Capability registry. Set True only in code, in the commit that ships the real module.
_CAPABILITIES = MappingProxyType(
    {
        "data-settings": True,
        "metadata-automation": True,
        "module-authoring": False,
        "module-test-gate": False,
    }
)
# Human review switch for module authoring. A reviewer flips this literal to True in a reviewed
# commit after verifying module_authoring.REVIEW_CHECKLIST and the gate's T3 preconditions.
# Nothing reads it from input or the environment; module_authoring.derived_capability() shows
# how 'module-authoring' would be derived. It does not change _CAPABILITIES or REQUIRED.
MODULE_AUTHORING_REVIEWED = False
REQUIRED = MappingProxyType(
    {
        T1: ("data-settings",),
        T2: ("metadata-automation",),
        T3: ("module-authoring", "module-test-gate"),
    }
)

_T1_KINDS = frozenset({"m", "s", "seq", "param", "g", "b", "wiz", "sa", "cron", "t", "r"})
_T2_KINDS = frozenset({"c", "v"})
_T3_KINDS = frozenset({"code"})
_T1_MOD_VERBS = frozenset({"install", "upgrade", "uninstall"})
# Kinds graded by the app (module) that ships the record, not by a model.
_MODULE_KINDS = frozenset({"r", "cron"})
_MODULE_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
# Kinds whose id carries no model; nothing to check against versioncaps.
_NO_MODEL_KINDS = frozenset({"s", "seq", "param", "g", "mod", "code"})

OK = "ok"
APPROVAL_REQUIRED = "approval-required"  # uninstall: data loss, owner + backup
NEEDS_STEP = "needs-step"
NEEDS_EDITION = "needs-edition"
NOT_IN_VERSION = "not-in-version"
NOT_BUILT_YET = "not-built-yet"
UNKNOWN = "unknown"
_GRADE_RANK = {
    OK: 0,
    APPROVAL_REQUIRED: 1,
    NEEDS_STEP: 2,
    NEEDS_EDITION: 3,
    NOT_IN_VERSION: 4,
    NOT_BUILT_YET: 5,
    UNKNOWN: 6,
}

CLAIM = (
    "Ingenium bots can check and plan Odoo data and settings tasks (T1) and metadata and "
    "automation tasks (T2: fields, views, reports, automations) on Odoo 17 to 20. A task "
    "runs only when its app and model are confirmed for your Odoo version, and uninstalling "
    "an app always needs your approval and a backup. Module code (T3) is coming but not yet "
    "available: bots say so and tell you what you can do instead. When a task cannot be "
    "checked, nothing runs. Report tasks are checked against the app that ships the "
    "report; scheduled-action tasks only run when you name the app they belong to."
)


def tier_ready(tier: int) -> bool:
    req = REQUIRED.get(tier)
    return bool(req) and all(_CAPABILITIES.get(c) is True for c in req)


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


def model_of(task_id: str) -> str | None:
    """Model named by a task id. Pinned by tests: m/b/wiz/sa via the classifier; c/v
    (``c:<model>:<verb>``, ``v:<model>:<type>``) and t (``t:<name>:<model>:<verb>``) here.
    r/cron ids carry no model -> None (graded by module, see module_of). Raises on classifier
    faults (caller fails closed)."""
    kind, _, rest = task_id.partition(":")
    if kind in ("m", "b", "wiz", "sa"):
        return classifier._model_of(task_id)  # noqa: SLF001 - shared task-id parser
    if kind in ("c", "v"):
        m = rest.rpartition(":")[0]
        return m if m and ":" not in m else None
    if kind == "t":
        parts = rest.split(":")
        return parts[-2] if len(parts) >= 3 and parts[-2] else None
    return None


def module_of(task_id: str, module_hint: str | None = None, version: Any = None) -> str | None:
    """App that owns a report or scheduled-action task. ``r:<module>.<xml id>``: the xml id
    prefix (Odoo names a record's xml id after the module that defines it). ``cron:<name>``:
    the owning app stored in the version catalogue (generator, ir.model.data); a caller's
    ``module_hint`` is never trusted: it must equal that owner, else None (refused)."""
    kind, _, rest = task_id.partition(":")
    if kind == "r":
        mod, dot, name = rest.partition(".")
        return mod if dot and name and _MODULE_RE.fullmatch(mod) else None
    if kind == "cron":
        owner = caps.cron_owner(version, rest)
        if owner is None or (module_hint is not None and module_hint != owner):
            return None
        return owner
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
        if self.allowed:
            return ""
        txt = self.reason
        if self.instead:
            txt += " What you can do instead: " + "; ".join(self.instead) + "."
        return txt


_INSTEAD_T3 = (
    "check whether a field, view, report or automation (T2) gives the same result",
    "ask a developer to build it as a module; Ingenium can write the requirement",
    "after the module is installed, bots can configure and use it (T1)",
)


def _unknown(tid: str, tier: int | None, reason: str, *instead: str, floor=None) -> Assessment:
    return Assessment(tid, tier, UNKNOWN, reason, tuple(instead), floor)


def assess(
    task_id: Any,
    *,
    version: Any,
    edition: str = "community",
    installed_modules: Iterable[str] | None = None,
    fields: Iterable[str] = (),
    module_hint: str | None = None,
) -> Assessment:
    tid = task_id if isinstance(task_id, str) else repr(task_id)
    if isinstance(edition, str):
        edition = edition.strip().lower()  # "Enterprise" is enterprise
    tier = tier_of(task_id)
    if tier is None:
        return _unknown(
            tid,
            None,
            "Ingenium does not recognise this kind of task, so it will not run it.",
            "describe the change as a record, setting, field, view or automation change",
        )
    try:
        floor = classifier.task_floor(tid)
    except Exception:  # noqa: BLE001 - fail closed
        return _unknown(tid, tier, "The safety check for this task failed, so nothing runs.")
    if not tier_ready(tier):
        return Assessment(
            tid,
            tier,
            NOT_BUILT_YET,
            f"Bots cannot do {TIER_NAMES[tier]} (T{tier}) yet. It is planned but not built.",
            _INSTEAD_T3 if tier == T3 else (),
            floor,
        )
    if tid.startswith("mod:") and tid.endswith(":uninstall"):
        return Assessment(
            tid,
            tier,
            APPROVAL_REQUIRED,
            "Uninstalling an app deletes its data and cannot be undone in production. "
            "It needs your explicit approval and a fresh backup first.",
            ("archive or hide what you no longer use instead of uninstalling",),
            floor,
        )
    kind = tid.partition(":")[0]
    if kind in _MODULE_KINDS:
        return _assess_by_module(tid, tier, floor, version, edition, installed_modules, module_hint)
    if kind in _NO_MODEL_KINDS:
        return Assessment(tid, tier, OK, "", (), floor)
    try:
        model = model_of(tid)
    except Exception:  # noqa: BLE001 - fail closed
        return _unknown(
            tid, tier, "Ingenium could not read this task, so nothing runs.", floor=floor
        )
    if model is None:
        return _unknown(
            tid,
            tier,
            "Ingenium cannot tell which app this task belongs to, so it cannot "
            "confirm it is possible here.",
            "name the record type (model) it applies to",
            floor=floor,
        )
    if (
        installed_modules is None
        or isinstance(installed_modules, (str, bytes))
        or not (isinstance(installed_modules, (list, tuple, set, frozenset)))
    ):
        return _unknown(
            tid,
            tier,
            "Ingenium could not read which apps are installed, so it cannot check this task.",
            "reconnect the database and try again",
            floor=floor,
        )
    try:
        v = caps.availability(
            version, edition, installed_modules, model, tuple(fields), module_hint
        )
    except Exception:  # noqa: BLE001 - fail closed
        return _unknown(tid, tier, "The version check failed, so nothing runs.", floor=floor)
    status = getattr(v, "status", None)
    if status == "installed-ok":
        return Assessment(tid, tier, OK, "", (), floor)
    if status == "available-needs-install":
        mods = ((v.module,) if v.module else ()) + tuple(v.missing_depends)
        return Assessment(
            tid,
            tier,
            NEEDS_STEP,
            f"This needs an app that is not installed yet. {v.reason}",
            ("install the app first (bots can do this as a separate, approved step)",),
            floor,
            tuple(dict.fromkeys(f"mod:{m}:install" for m in mods)),
        )
    if status == "enterprise-only":
        return Assessment(
            tid,
            tier,
            NEEDS_EDITION,
            f"This is only in Odoo Enterprise. {v.reason}",
            ("use a Community alternative if one exists, or upgrade to Enterprise",),
            floor,
        )
    if status == "not-in-this-version":
        alt = tuple(f"this exists in Odoo {o}" for o in v.other_versions)
        return Assessment(
            tid, tier, NOT_IN_VERSION, f"This is not in this Odoo version. {v.reason}", alt, floor
        )
    return _unknown(
        tid,
        tier,
        f"Ingenium could not confirm this is possible. {getattr(v, 'reason', '')}",
        "check the model name, or connect a database that has it",
        floor=floor,
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
        lines = [f"Nothing runs: {len(bad)} of {len(self.parts)} parts cannot be done as asked."]
        lines += [f"- {p.task_id}: {p.message()}" for p in bad]
        if ok:
            lines.append(
                "These parts could run on their own if you still want them: " + ", ".join(ok) + "."
            )
        return "\n".join(lines)


def _rank(grade: Any) -> int:
    return _GRADE_RANK.get(grade, _GRADE_RANK[UNKNOWN])


def compose(parts: Iterable[Assessment]) -> Plan:
    """Composition rule: tier = highest part tier; grade = worst part grade (unrecognised
    grades count as unknown); all or nothing, no partial run; order T3, then T2, then T1 so
    data never lands before the structure it needs. Prior steps are never added silently."""
    ps = tuple(parts)
    if not ps:
        return Plan((), (), None, UNKNOWN)
    tiers = [p.tier for p in ps]
    tier = None if None in tiers else max(t for t in tiers if t is not None)
    worst = max((p.grade for p in ps), key=_rank)
    grade = worst if worst in _GRADE_RANK else UNKNOWN
    order = tuple(p.task_id for p in sorted(ps, key=lambda p: -(p.tier or 0)))
    return Plan(ps, order, tier, grade)


def _installed_ok(installed_modules: Any) -> bool:
    return isinstance(installed_modules, (list, tuple, set, frozenset)) and all(
        isinstance(m, str) for m in installed_modules
    )


def _assess_by_module(
    tid: str,
    tier: int,
    floor: tuple[str, str] | None,
    version: Any,
    edition: Any,
    installed_modules: Any,
    module_hint: str | None,
) -> Assessment:
    """Report / scheduled-action task: the catalogue row must list this version, then the app
    that ships it is graded like any app (installed, needs install, Enterprise-only)."""
    try:
        row = classifier.catalogue()[0].get(tid)
    except Exception:  # noqa: BLE001 - fail closed
        return _unknown(tid, tier, "The task list could not be read, so nothing runs.", floor=floor)
    if row is None:
        return _unknown(
            tid,
            tier,
            "This report or scheduled action is not in Ingenium's task list, so it will not run.",
            "check the name of the report or scheduled action",
            floor=floor,
        )
    versions = row[1]
    if isinstance(version, bool) or not isinstance(version, int) or version not in versions:
        if isinstance(version, int) and not isinstance(version, bool) and versions:
            alt = tuple(f"this exists in Odoo {v}" for v in sorted(versions))
            return Assessment(
                tid, tier, NOT_IN_VERSION, "This is not in this Odoo version.", alt, floor
            )
        return _unknown(tid, tier, "The version check failed, so nothing runs.", floor=floor)
    mod = module_of(tid, module_hint, version)
    if mod is None and tid.startswith("cron:") and module_hint is not None:
        owner = module_of(tid, None, version)
        if owner is not None:
            return _unknown(
                tid,
                tier,
                f"This scheduled action belongs to the app '{owner}', not '{module_hint}', "
                "so it will not run.",
                f"name the app '{owner}' or check the scheduled action",
                floor=floor,
            )
    if mod is None:
        return _unknown(
            tid,
            tier,
            "Ingenium cannot tell which app this scheduled action belongs to, so it cannot "
            "confirm it is possible here.",
            "name the app (module) the scheduled action belongs to",
            floor=floor,
        )
    if not _installed_ok(installed_modules) or not isinstance(edition, str):
        return _unknown(
            tid,
            tier,
            "Ingenium could not read which apps are installed, so it cannot check this task.",
            "reconnect the database and try again",
            floor=floor,
        )
    if mod in installed_modules:
        return Assessment(tid, tier, OK, "", (), floor)
    try:
        info = caps.module_info(version, mod)
    except Exception:  # noqa: BLE001 - fail closed
        info = None
    if not isinstance(info, dict):
        return _unknown(
            tid,
            tier,
            f"Ingenium could not confirm the app '{mod}' exists in this Odoo version.",
            "check the app name, or connect a database that has it",
            floor=floor,
        )
    if info.get("edition") == "enterprise" and edition != "enterprise":
        return Assessment(
            tid,
            tier,
            NEEDS_EDITION,
            f"The app '{mod}' is only in Odoo Enterprise.",
            ("use a Community alternative if one exists, or upgrade to Enterprise",),
            floor,
        )
    return Assessment(
        tid,
        tier,
        NEEDS_STEP,
        f"This needs the app '{mod}', which is not installed yet.",
        ("install the app first (bots can do this as a separate, approved step)",),
        floor,
        (f"mod:{mod}:install",),
    )
