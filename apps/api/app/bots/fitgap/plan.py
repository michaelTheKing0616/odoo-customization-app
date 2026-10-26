"""Stock mapping -> guarded dry-run Bot plan; custom gaps -> App Studio module-spec draft.

Nothing here executes. Each action names a catalogue task and its L-tier from the risk
rules; actions with no catalogue task (settings toggles, module installs, Enterprise-only
records) are marked for a human, never guessed into a tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.bots.fitgap.fitgap import FitGap, Table, load_table
from app.bots.risk import rules
from app.bots.risk.rules import Policy, Refusal, Route
from app.catalogue import loader


@dataclass
class PlanAction:
    concept: str
    action: str
    model: str
    step_ids: list[str]
    task_id: str | None
    tier: int | None
    controls: tuple[str, ...] = ()
    reasons: list[str] = field(default_factory=list)
    bot_can_do: bool = False


@dataclass
class Plan:
    dry_run: bool
    executed: bool
    actions: list[PlanAction]
    module_spec: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "executed": self.executed,
            "module_spec": self.module_spec,
            "actions": [vars(a) | {"controls": list(a.controls)} for a in self.actions],
        }


def build_plan(
    fit: FitGap,
    route: Route = "A",
    policy: Policy = rules.DEFAULT_POLICY,
    table: Table | None = None,
) -> Plan:
    t = table or load_table(packs=fit.packs)
    cat = loader.load()
    concepts = {c.id: c for c in t.concepts}
    actions: list[PlanAction] = []
    installs: dict[str, list[str]] = {}
    by_key: dict[tuple[str, str], PlanAction] = {}
    for f in fit.steps:
        if f.verdict not in ("stock-with-config", "stock", "partial"):
            continue
        if f.confidence == "model-suggested":
            continue  # model suggestions never add plan actions
        for use in f.concepts:  # partial steps: only the parts this edition has
            if use.status == "unavailable" or (
                use.status == "unverified" and concepts[use.concept].edition == "enterprise"
            ):
                continue
            if use.status == "install":
                installs.setdefault(use.module, []).append(f.step_id)
            for s in concepts[use.concept].setup:
                key = (use.concept, s["action"])
                if key in by_key:
                    by_key[key].step_ids.append(f.step_id)
                    continue
                a = PlanAction(
                    use.concept, s["action"], s["model"], [f.step_id], s.get("task"), None
                )
                by_key[key] = a
                actions.append(a)
    for a in actions:
        _tier(a, cat, fit, route, policy)
    for mod, steps in reversed(installs.items()):
        a = PlanAction(
            "module", f"install module {mod}", "ir.module.module", steps, f"mod:{mod}:install", None
        )
        _tier(a, cat, fit, route, policy, blast=1)
        actions.insert(0, a)
    return Plan(True, False, actions, module_spec(fit, t))


def _tier(
    a: PlanAction, cat: Any, fit: FitGap, route: Route, policy: Policy, blast: int | None = None
) -> None:
    if a.task_id is None:
        a.reasons.append("no Bot catalogue task for this action: a human does it")
        return
    task = cat.index.get(a.task_id)
    if task is None:
        a.reasons.append(f"catalogue task {a.task_id} missing: refused")
        return
    if fit.env is not None and fit.env.major not in task.versions:
        a.reasons.append(f"catalogue task {a.task_id} not valid on Odoo {fit.env.major}: refused")
        return
    tp = rules.plan_tier(task.risk_class, None, route, policy, blast or max(1, len(a.step_ids)))
    if isinstance(tp, Refusal):
        a.reasons.append(f"risk rules refused: {tp}")
        return
    a.tier, a.controls, a.bot_can_do = tp.tier, tuple(tp.controls), True
    a.reasons.extend(tp.reasons)


def module_spec(fit: FitGap, table: Table | None = None) -> dict[str, Any] | None:
    """App Studio draft (input of `module_spec_codec.draft_dict_to_module_spec`)."""
    t = table or load_table(packs=fit.packs)
    gaps = {g.id: g for g in t.gaps}
    used = [gaps[g] for g in fit.gaps if g in gaps]
    if not used:
        return None
    depends = sorted({d for g in used for d in g.spec["depends"]})
    models = [
        {
            "model": g.spec["model"],
            "description": g.label,
            "fields": [dict(f) for f in g.spec["fields"]],
        }
        for g in used
    ]
    return {
        "technical_name": "ingenium_fit_gaps",
        "display_name": "Business fit-gap: custom gaps",
        "depends": depends,
        "models": models,
        "odoo_major": fit.env.major if fit.env else None,
    }
