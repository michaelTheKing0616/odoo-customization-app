"""Plain business summary + UI JSON for one process document."""

from __future__ import annotations

from typing import Any

from app.bots.process.fitgap import FitGap
from app.bots.process.ingest import FlowGraph
from app.bots.process.plan import Plan

HEADER = (
    "These verdicts are suggestions from a keyword match on your document; "
    "a person confirms each one before anything is set up."
)
SUGGESTED = "suggested from keywords in your document, please confirm"

_WORDS = {
    "stock": "looks like it works in standard Odoo as is",
    "stock-with-config": "looks like it works in standard Odoo after setup",
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
    lines = [
        HEADER,
        f"We read {len(mapped)} steps from {graph.source}. Against {env}: "
        f"{n['stock']} look like they work as is (suggested), "
        f"{n['stock-with-config']} after setup (suggested), "
        f"{n['custom']} need custom work.",
    ]
    if not graph.confident:
        lines.append("The flow order was hard to read; please confirm the step order.")
    fit_ok = [f for f in mapped if f.verdict in ("stock", "stock-with-config")]
    if fit_ok:
        lines.append("Suggested fits:")
        lines += [
            f"- {f.text}: {_WORDS[f.verdict or 'stock']} ({SUGGESTED}; match: {f.confidence})"
            for f in fit_ok
        ]
    custom = [f for f in mapped if f.verdict == "custom"]
    if custom:
        lines.append("Needs custom work:")
        lines += [f"- {f.text}: {f.reasons[0]}" for f in custom]
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


def to_json(graph: FlowGraph, fit: FitGap, plan: Plan) -> dict[str, Any]:
    return {
        "flow": graph.to_dict(),
        "flow_order": [s.id for s in graph.order()],
        "fitgap": fit.to_dict(),
        "plan": plan.to_dict(),
        "summary": summary(graph, fit, plan),
    }
