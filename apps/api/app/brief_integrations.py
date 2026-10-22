"""Optional-integration plan for App Studio briefs.

A missing or Enterprise-only app never refuses a whole brief. Only the brief's
PRIMARY host app can block, and only when it truly cannot be installed. Every
other stock app the brief mentions is an optional integration: present apps are
used, missing ones are left out or deferred with a plain note (what, why, how to
enable later). Pieces that need custom Python are labelled for the existing
custom-code path (author -> sandbox prove -> you publish on Odoo.sh / self-host)
when this host cannot install Python (Odoo Online). Side effects: read-only RPCs
through ``read_install_facts`` only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.stock_app_install import (
    StockAppMatch,
    StockAppProposal,
    _preferred_host,
    match_stock_app,
    match_stock_apps,
    proposal_for,
    read_install_facts,
)

_INTEGRATION_CUE = re.compile(
    r"(?i)\b(integrat\w*|connect\w*\s+(?:to|with)|link\w*\s+(?:to|with)|"
    r"sync\w*\s+with|pull\w*\s+from|feed\w*\s+into)\b"
)
_BIG_BRIEF_WORDS = 40

# Brief phrases that need custom Python (not metadata) to deliver.
_PYTHON_PIECES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "computed_score",
        "Computed scores (weighted 0-100 score)",
        re.compile(
            r"(?i)\b(?:health|risk|churn)\s+scor(?:e|es|ing)\b|\bweighted\b|"
            r"\b(?:calculated|computed)\s+(?:score|total|rate|amount)s?\b"
        ),
    ),
    (
        "rules_engine",
        "Rules engine",
        re.compile(r"(?i)\brules?\s+engine\b|\bno-code\s+rules?\b"),
    ),
    (
        "scheduled_actions",
        "Scheduled recompute / score history",
        re.compile(
            r"(?i)\bnightly\b|\bcron\b|"
            r"\bscheduled\s+(?:actions?|jobs?|tasks?|recalculat\w*|recomput\w*|sync\w*)\b|"
            r"\brecurring\s+(?:jobs?|tasks?|recalculat\w*|recomput\w*)\b|\bscore\s+history\b"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class IntegrationItem:
    module: str
    app_label: str
    model: str
    status: str  # available | deferred | left_out | unchecked
    note: str

    def as_dict(self) -> dict[str, str]:
        return {
            "module": self.module,
            "app_label": self.app_label,
            "model": self.model,
            "status": self.status,
            "note": self.note,
        }


@dataclass(slots=True)
class BriefPlan:
    primary_module: str | None = None
    edition: str = "unknown"
    hosting: str = "unknown"
    integrations: list[IntegrationItem] = field(default_factory=list)
    python_pieces: list[dict[str, str]] = field(default_factory=list)

    @property
    def left_out(self) -> list[IntegrationItem]:
        return [i for i in self.integrations if i.status == "left_out"]

    @property
    def omitted_models(self) -> list[str]:
        return [i.model for i in self.integrations if i.status in {"left_out", "deferred"}]

    @property
    def has_notes(self) -> bool:
        return bool(self.python_pieces or any(i.status != "available" for i in self.integrations))

    def summary(self) -> str:
        parts = ["Building the core app."]
        for item in self.integrations:
            if item.status != "available":
                parts.append(item.note)
        if self.python_pieces:
            parts.append(self.python_pieces[0]["lane_note"])
        return " ".join(parts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "primary_module": self.primary_module,
            "edition": self.edition,
            "hosting": self.hosting,
            "core_built": True,
            "integrations": [i.as_dict() for i in self.integrations],
            "left_out": [i.module for i in self.left_out],
            "omitted_models": self.omitted_models,
            "python_pieces": list(self.python_pieces),
            "summary": self.summary(),
        }


def _reads_as_integration(prompt: str) -> bool:
    text = prompt or ""
    return bool(_INTEGRATION_CUE.search(text)) or len(text.split()) >= _BIG_BRIEF_WORDS


def split_primary(
    prompt: str, *, host_model: str | None = None
) -> tuple[StockAppMatch | None, list[StockAppMatch]]:
    """Primary host app (may block) and optional integration apps (never block).

    A locked host is always primary. A short single-purpose brief keeps the
    existing longest-phrase primary. A big or integration-style brief has a
    primary only when the preferred inherit host belongs to a stock app.
    """
    matches = match_stock_apps(prompt)
    if host_model:
        primary = match_stock_app(prompt, host_model=host_model)
    elif not _reads_as_integration(prompt):
        primary = match_stock_app(prompt)
    else:
        preferred = _preferred_host(prompt)
        primary = next(
            (
                StockAppMatch(app=m.app, model=preferred, noun=m.noun)
                for m in matches
                if preferred and preferred in m.app.models
            ),
            None,
        )
    others = [m for m in matches if primary is None or m.app.module != primary.app.module]
    return primary, others


def python_pieces(prompt: str, hosting_hint: str) -> list[dict[str, str]]:
    """Brief pieces that need custom Python, labelled with the custom-code path."""
    from app.ai_class_stamp import ARTIFACT_COPY, LANE_COPY
    from app.hosting import online_option_a_python_blocked
    from app.text_negation import has_positive_match

    found = [
        (key, label) for key, label, pat in _PYTHON_PIECES if has_positive_match(pat, prompt or "")
    ]
    if not found:
        return []
    blocked = online_option_a_python_blocked(hosting_hint or "unknown")
    if blocked:
        lane_note = (
            "Pieces that need custom Python go to the custom-code path: authored as an "
            "installable module, proved in a sandbox, then published by a human on "
            "Odoo.sh or a self-hosted server. They cannot install on Odoo Online; the "
            "rest of the app is built as metadata here."
        )
    else:
        lane_note = (
            "Pieces that need custom Python go to the custom-code path: authored as an "
            "installable module, proved in a sandbox, then published by a human."
        )
    return [
        {
            "key": key,
            "label": label,
            "delivery_lane": "module_sh_or_self",
            "delivery_lane_copy": LANE_COPY["module_sh_or_self"],
            "artifact_kind": "option_a_module",
            "artifact_kind_copy": ARTIFACT_COPY["option_a_module"],
            "online_blocked": "true" if blocked else "false",
            "lane_note": lane_note,
        }
        for key, label in found
    ]


def _integration_item(match: StockAppMatch, port: Any, edition: str) -> IntegrationItem:
    app = match.app
    try:
        facts = read_install_facts(port, match.model, app.module, edition=edition)
    except Exception:  # noqa: BLE001 — a failed read never blocks the brief
        return IntegrationItem(
            app.module,
            app.label,
            match.model,
            "unchecked",
            f"{app.label} could not be checked, so its links are left for a later refine.",
        )
    if facts.model_present or (facts.module_state or "") == "installed":
        return IntegrationItem(app.module, app.label, match.model, "available", "")
    proposal: StockAppProposal | None = proposal_for(match, facts)
    if proposal is not None and proposal.installable:
        return IntegrationItem(
            app.module,
            app.label,
            match.model,
            "deferred",
            f"{app.label} is not installed, so its links are left out for now. "
            f"Install {app.label}, then refine this app to add them.",
        )
    if not app.is_community and facts.edition == "community":
        note = (
            f"{app.label} was left out: it is an Odoo Enterprise app and this database "
            f"is Community. To add it later, move to Odoo Enterprise, install "
            f"{app.label}, then refine this app."
        )
    else:
        note = (
            f"{app.label} was left out: this Odoo server cannot install it. To add it "
            f"later, make the {app.module} module available, install it, then refine this app."
        )
    return IntegrationItem(app.module, app.label, match.model, "left_out", note)


def build_brief_plan(
    prompt: str,
    port: Any | None,
    *,
    host_model: str | None = None,
    edition: str = "unknown",
    hosting_hint: str = "unknown",
) -> tuple[StockAppProposal | None, BriefPlan]:
    """The App Studio gate: a blocking proposal only for the primary host app.

    Output: (proposal or None, plan). ``proposal`` is the existing install /
    explain step and is returned only when the PRIMARY app is missing.
    Integration apps never produce a proposal; they land in ``plan``.
    """
    plan = BriefPlan(edition=edition, hosting=hosting_hint)
    # This remains recall-only for the integration plan. The App Design path
    # cannot authorize code from these labels: it requires a verified intent
    # contract before a Python piece reaches the Option A lane.
    plan.python_pieces = python_pieces(prompt, hosting_hint)
    if port is None:
        return None, plan
    primary, others = split_primary(prompt, host_model=host_model)
    proposal: StockAppProposal | None = None
    if primary is not None:
        plan.primary_module = primary.app.module
        try:
            facts = read_install_facts(port, primary.model, primary.app.module, edition=edition)
            proposal = proposal_for(primary, facts)
        except Exception:  # noqa: BLE001 — a failed read must not block the request
            proposal = None
    for match in others:
        plan.integrations.append(_integration_item(match, port, edition))
    return proposal, plan


__all__ = ["BriefPlan", "IntegrationItem", "build_brief_plan", "python_pieces", "split_primary"]
