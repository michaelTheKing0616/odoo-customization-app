"""Business fit-gap: plain business summary + UI JSON for one client document."""

from __future__ import annotations

from typing import Any

from app.bots.fitgap.fitgap import FitGap
from app.bots.fitgap.ingest import FlowGraph
from app.bots.fitgap.plan import Plan

TITLE = "Business fit-gap"
HEADER = (
    "Business fit-gap. These verdicts are suggestions from a keyword match on your document; "
    "a person confirms each one before anything is set up."
)
SUGGESTED = "suggested from keywords in your document, please confirm"
MODEL = "suggested by the assistant from your wording, please confirm"
_PRIO = {"must": 0, "should": 1, "could": 2, "wont": 3, None: 2}

_WORDS = {
    "stock": "looks like it works in standard Odoo as is",
    "stock-with-config": "looks like it works in standard Odoo after setup",
    "partial": "partly unavailable on this edition",
    "custom": "needs custom work",
}


def summary(graph: FlowGraph, fit: FitGap, plan: Plan) -> str:
    mapped = [f for f in fit.steps if f.verdict]
    n = {v: sum(1 for f in mapped if f.verdict == v) for v in _WORDS}
    env = (
        f"Odoo {fit.env.major} {fit.env.edition.title()}"
        if fit.env
        else "your Odoo (not yet checked)"
    )
    unit = "requirements" if any(s.kind == "requirement" for s in graph.steps) else "steps"
    lines = [
        HEADER,
        f"We read {len(mapped)} {unit} from {graph.source}. Against {env}: "
        f"{n['stock']} look like they work as is (suggested), "
        f"{n['stock-with-config']} after setup (suggested), "
        f"{n['partial']} are partly unavailable on this edition, "
        f"{n['custom']} need custom work.",
    ]
    if fit.merged:
        lines.append(f"{fit.merged} repeated steps merged (each counted once).")
    lines.append(f"Overall: {_VERDICT[fit.overall]}.")
    if not fit.enough_input:
        return "\n".join(lines)
    ok, incl = fit.fit_percent()
    lines.append(
        f"Confirmed fit: {ok}% (strong matches only). Including suggestions to confirm: {incl}%."
    )
    areas = fit.area_fit()
    if areas:
        lines.append(
            "Confirmed fit by area: "
            + "; ".join(
                f"{a} {v['percent']}% ({v['fit']}/{v['steps']}"
                + (f", +{v['suggested']} suggested" if v["suggested"] else "")
                + ")"
                for a, v in areas.items()
            )
            + "."
        )
    if fit.packs:
        lines.append("Industry knowledge used: " + ", ".join(fit.packs) + ".")
    if not graph.confident:
        lines.append("The flow order was hard to read; please confirm the step order.")
    fit_ok = [f for f in mapped if f.verdict in ("stock", "stock-with-config")]
    if fit_ok:
        lines.append("Suggested fits:")
        lines += [
            f"- {f.text}: {_WORDS[f.verdict or 'stock']} ({_label(f)}; match: {f.confidence})"
            for f in fit_ok
        ]
    partial = [f for f in mapped if f.verdict == "partial"]
    if partial:
        lines.append("Partly unavailable on this edition (needs the edition or module named):")
        lines += [
            f"- {f.text}: "
            + "; ".join(
                r.removeprefix("missing on this edition: ")
                for r in f.reasons
                if r.startswith("missing on this edition: ")
            )
            for f in partial
        ]
    custom = sorted(
        (f for f in mapped if f.verdict == "custom"),
        key=lambda f: (_PRIO.get(f.priority, 2), f.needs_human),
    )
    if custom:
        lines.append("Needs custom work (most important first):")
        lines += [
            f"- {'[' + f.priority + '] ' if f.priority else ''}{f.text}: {f.reasons[0]}"
            + (f" ({MODEL})" if f.confidence == "model-suggested" else "")
            for f in custom
        ]
    setup = [a.action for a in plan.actions]
    if setup:
        lines.append(
            "Setup we would prepare for your approval (nothing changed yet): "
            + "; ".join(setup[:8])
            + (" …" if len(setup) > 8 else "")
            + "."
        )
    if fit.questions:
        lines.append("Questions: " + " ".join(fit.questions))
    return "\n".join(lines)


_VERDICT = {
    "not-enough-input": "not enough input, needs a human",
    "suggested-fit": "standard Odoo may be enough, but some fits are only suggestions "
    "a person must confirm",
    "stock": "standard Odoo looks enough as is (suggested)",
    "stock-with-config": "standard Odoo with setup looks enough (suggested)",
    "custom": "custom work is needed for at least one item",
    "partial": "partly unavailable on this edition: some steps need a feature this database "
    "does not have (see below)",
}


def _label(f: Any) -> str:
    return MODEL if f.confidence == "model-suggested" else SUGGESTED


def to_json(graph: FlowGraph, fit: FitGap, plan: Plan) -> dict[str, Any]:
    return {
        "title": TITLE,
        "flow": graph.to_dict(),
        "flow_order": [s.id for s in graph.order()],
        "fitgap": fit.to_dict(),
        "plan": plan.to_dict(),
        "summary": summary(graph, fit, plan),
    }
