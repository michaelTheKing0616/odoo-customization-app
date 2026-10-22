"""GND-MOD: offer the stock Community app a request needs, install it, continue.

One map (user words and model -> Community module) and one confirm step that
every GND consumer uses. The install goes through the change-set op
``module.install`` (``app.changeset.dispatch.dispatch_op``). There is no other
install path here. Uninstall is never offered. A generated zip is never
installed by this module. Enterprise-only apps are explained, not installed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

STOCK_APP_CLARIFICATION_KIND = "stock_app_install"
INSTALL_DECISION = "install"
DECLINE_DECISION = "decline"
_COMMUNITY = "community"
_ENTERPRISE = "enterprise"


@dataclass(frozen=True, slots=True)
class StockApp:
    """One stock app: the module, the name people use, and what it provides.

    ``words`` are lowercase phrases matched on word boundaries. ``noun`` is
    the record name used in copy when the user's own word is unknown.
    """

    module: str
    label: str
    models: tuple[str, ...]
    words: tuple[str, ...]
    noun: str
    edition: str = _COMMUNITY

    @property
    def is_community(self) -> bool:
        return self.edition == _COMMUNITY


STOCK_APPS: tuple[StockApp, ...] = (
    StockApp(
        "sale",
        "Sales",
        ("sale.order",),
        ("quotation", "quotations", "quote", "quotes", "sale order", "sale orders",
         "sales order", "sales orders"),
        "quotations",
    ),
    StockApp(
        "purchase",
        "Purchase",
        ("purchase.order",),
        ("purchase order", "purchase orders", "rfq", "rfqs", "request for quotation",
         "requests for quotation"),
        "purchase orders",
    ),
    StockApp(
        "account",
        "Invoicing",
        ("account.move",),
        ("invoice", "invoices", "vendor bill", "vendor bills", "credit note",
         "credit notes", "journal entry", "journal entries"),
        "invoices",
    ),
    StockApp(
        "stock",
        "Inventory",
        ("stock.picking",),
        ("delivery order", "delivery orders", "transfer", "transfers", "picking",
         "pickings", "delivery slip", "delivery slips"),
        "transfers",
    ),
    StockApp(
        "crm",
        "CRM",
        ("crm.lead",),
        ("lead", "leads", "opportunity", "opportunities", "pipeline"),
        "leads",
    ),
    StockApp(
        "project",
        "Project",
        ("project.task", "project.project"),
        ("task", "tasks", "project", "projects"),
        "tasks",
    ),
    StockApp(
        "hr",
        "Employees",
        ("hr.employee",),
        ("employee", "employees"),
        "employees",
    ),
    StockApp(
        "mrp",
        "Manufacturing",
        ("mrp.production",),
        ("manufacturing order", "manufacturing orders", "production order",
         "production orders", "work order", "work orders"),
        "manufacturing orders",
    ),
    StockApp(
        "point_of_sale",
        "Point of Sale",
        ("pos.order",),
        ("pos order", "pos orders", "point of sale", "point-of-sale", "pos"),
        "point of sale orders",
    ),
    StockApp(
        "calendar",
        "Calendar",
        ("calendar.event",),
        ("meeting", "meetings", "calendar event", "calendar events", "calendar"),
        "meetings",
    ),
    StockApp(
        "helpdesk",
        "Helpdesk",
        ("helpdesk.ticket",),
        ("helpdesk", "helpdesk ticket", "helpdesk tickets"),
        "helpdesk tickets",
        edition=_ENTERPRISE,
    ),
    StockApp(
        "planning",
        "Planning",
        ("planning.slot",),
        ("planning shift", "planning shifts", "shift planning"),
        "planning shifts",
        edition=_ENTERPRISE,
    ),
    StockApp(
        "industry_fsm",
        "Field Service",
        ("project.task",),
        ("field service",),
        "field service tasks",
        edition=_ENTERPRISE,
    ),
)

_BY_MODEL: dict[str, StockApp] = {}
for _app in STOCK_APPS:
    if _app.edition == _COMMUNITY:
        for _model in _app.models:
            _BY_MODEL.setdefault(_model, _app)


@dataclass(frozen=True, slots=True)
class StockAppMatch:
    """Which app the words point at, and the word the user used for it."""

    app: StockApp
    model: str
    noun: str


@dataclass(frozen=True, slots=True)
class InstallFacts:
    """What the live database says about the existing form and its module.

    ``module_state`` is the ``ir.module.module`` state, or ``None`` when the
    database has no row for that module. ``edition`` is ``community``,
    ``enterprise`` or ``unknown`` (never assume Community when unknown).
    """

    model_present: bool
    module_state: str | None
    edition: str = "unknown"


@dataclass(frozen=True, slots=True)
class StockAppProposal:
    """The confirm step shown to the user. Contains no credentials."""

    module: str
    app_label: str
    model: str
    noun: str
    installable: bool
    question: str
    reason: str
    install_label: str
    decline_label: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "app_label": self.app_label,
            "model": self.model,
            "noun": self.noun,
            "installable": self.installable,
            "question": self.question,
            "reason": self.reason,
            "install_label": self.install_label,
            "decline_label": self.decline_label,
        }


@dataclass(frozen=True, slots=True)
class InstallOutcome:
    """Result of the approved install. ``message`` is one sentence, no traceback."""

    ok: bool
    module: str
    module_id: int | None = None
    message: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)


def stock_app_for_model(model: str | None) -> StockApp | None:
    """Community app that provides ``model``, or ``None``.

    Inputs: a technical model name. Output: the map row. Side effects: none.
    """
    return _BY_MODEL.get(str(model or "").strip())


def _word_hits(text: str) -> list[tuple[int, int, StockApp, str]]:
    hits: list[tuple[int, int, StockApp, str]] = []
    for app in STOCK_APPS:
        for word in app.words:
            match = re.search(rf"(?<![a-z0-9_]){re.escape(word)}(?![a-z0-9_])", text)
            if match:
                hits.append((len(word), match.start(), app, word))
    return hits


def match_stock_app(prompt: str, *, host_model: str | None = None) -> StockAppMatch | None:
    """Map the user's words (and an optional locked host) to one stock app.

    Inputs: the request text and an optional existing form already locked by the
    diagnosis. Output: the app, the model, and the noun to use in copy.
    The longest phrase wins, so "POS orders" is Point of Sale, not Sales.
    The user is never asked to name the app. Side effects: none.
    """
    text = (prompt or "").lower()
    hits = sorted(_word_hits(text), key=lambda row: (-row[0], row[1]))
    host = str(host_model or "").strip()
    if host:
        app = stock_app_for_model(host)
        if app is None:
            return None
        noun = next((word for _, _, hit_app, word in hits if hit_app is app), app.noun)
        return StockAppMatch(app=app, model=host, noun=noun)
    if hits:
        preferred = _preferred_host(prompt)
        for _, _, app, word in hits:
            if preferred and preferred in app.models and app.edition == _COMMUNITY:
                return StockAppMatch(app=app, model=preferred, noun=word)
        _, _, app, word = hits[0]
        return StockAppMatch(app=app, model=app.models[0], noun=word)
    preferred = _preferred_host(prompt)
    app = stock_app_for_model(preferred)
    if app is None or preferred is None:
        return None
    return StockAppMatch(app=app, model=preferred, noun=app.noun)


def match_stock_apps(prompt: str) -> list[StockAppMatch]:
    """Every stock app the user's words point at, in the order they appear.

    Inputs: the request text. Output: one match per app, Enterprise rows
    included so callers can explain them. A phrase inside a longer matched
    phrase does not count ("POS orders" is not also Sales). Side effects: none.
    """
    text = (prompt or "").lower()
    taken: list[tuple[int, int]] = []
    seen: set[str] = set()
    found: list[tuple[int, StockAppMatch]] = []
    for size, start, app, word in sorted(_word_hits(text), key=lambda row: (-row[0], row[1])):
        end = start + size
        if any(start < t_end and t_start < end for t_start, t_end in taken):
            continue
        taken.append((start, end))
        if app.module in seen:
            continue
        seen.add(app.module)
        found.append((start, StockAppMatch(app=app, model=app.models[0], noun=word)))
    return [match for _, match in sorted(found, key=lambda row: row[0])]


def _preferred_host(prompt: str) -> str | None:
    try:
        from app.ai_grain import preferred_inherit_host

        return preferred_inherit_host(prompt)
    except Exception:  # noqa: BLE001 — host inference is a hint, never a hard dependency
        return None


def proposal_for(match: StockAppMatch, facts: InstallFacts) -> StockAppProposal | None:
    """Turn a match and live facts into the confirm step, or ``None``.

    Inputs: the word match and what the database has. Output: ``None`` when
    the model is already there or the module is installed. Otherwise a
    proposal. Enterprise-only apps and modules the server cannot install are
    explained with ``installable=False``. Side effects: none.
    """
    if facts.model_present:
        return None
    app = match.app
    state = (facts.module_state or "").strip()
    if state == "installed":
        return None
    noun = match.noun
    singular = _singular(noun)
    if app.edition != _COMMUNITY and facts.edition == _COMMUNITY:
        return StockAppProposal(
            module=app.module,
            app_label=app.label,
            model=match.model,
            noun=noun,
            installable=False,
            question=(
                f"Your request edits {noun}, which come from {app.label}. "
                f"{app.label} is an Odoo Enterprise app, so it cannot be installed on Community."
            ),
            reason=(
                f"{app.label} is not in Odoo Community, so there is no {singular} to change here."
            ),
            install_label="",
            decline_label="Close",
        )
    if facts.module_state is None or state == "uninstallable":
        return StockAppProposal(
            module=app.module,
            app_label=app.label,
            model=match.model,
            noun=noun,
            installable=False,
            question=(
                f"Your request edits {noun}, which come from the {app.label} app. "
                f"This Odoo server cannot install {app.label}."
            ),
            reason=(
                f"{app.label} is not available to install on this server, "
                f"so there is no {singular} to change."
            ),
            install_label="",
            decline_label="Close",
        )
    return StockAppProposal(
        module=app.module,
        app_label=app.label,
        model=match.model,
        noun=noun,
        installable=True,
        question=(
            f"Your request edits {noun}, which come from the {app.label} app. "
            f"Install {app.label} to continue?"
        ),
        reason=f"{app.label} is not installed, so there is no {singular} to put this on yet.",
        install_label=f"Install {app.label} and continue",
        decline_label="Not now",
    )


def _singular(noun: str) -> str:
    if noun.endswith("ies"):
        return noun[:-3] + "y"
    if noun.endswith("s") and not noun.endswith("ss"):
        return noun[:-1]
    return noun


def read_install_facts(
    port: Any, model: str, module: str, *, edition: str = "unknown"
) -> InstallFacts:
    """Read whether ``model`` exists and the state of ``module``.

    Inputs: a port with ``execute_kw`` (the live client or a fake), a model,
    and a module technical name. Output: ``InstallFacts``.
    Side effects: two read-only RPCs (``ir.model`` and ``ir.module.module``).
    Raises whatever the port raises; callers decide how to degrade.
    """
    count = port.execute_kw("ir.model", "search_count", [[("model", "=", model)]], {})
    rows = port.execute_kw(
        "ir.module.module",
        "search_read",
        [[("name", "=", module)]],
        {"fields": ["id", "state"], "limit": 1},
    )
    state = str(rows[0].get("state") or "") if rows else None
    return InstallFacts(model_present=bool(count), module_state=state, edition=edition)


def propose_stock_app_install(
    prompt: str,
    port: Any | None,
    *,
    host_model: str | None = None,
    edition: str = "unknown",
) -> StockAppProposal | None:
    """The one confirm step every GND consumer calls before generating.

    Inputs: the request text, a read port for the connection (``None`` = no
    connection, out of scope), and an optional locked existing form.
    Output: a proposal when the existing form is missing because its stock app
    is not installed; ``None`` otherwise, including when the read fails.
    Side effects: read-only RPCs through ``read_install_facts``.
    """
    if port is None:
        return None
    match = match_stock_app(prompt, host_model=host_model)
    if match is None:
        return None
    try:
        facts = read_install_facts(port, match.model, match.app.module, edition=edition)
    except Exception:  # noqa: BLE001 — a failed read must not block the request
        return None
    return proposal_for(match, facts)


def install_stock_app(port: Any, proposal: StockAppProposal | Mapping[str, Any]) -> InstallOutcome:
    """Install the approved stock app through the change-set op ``module.install``.

    Inputs: a port with ``execute_kw`` and the proposal the user approved.
    Output: ``InstallOutcome``; ``ok=False`` carries one plain sentence.
    Side effects: ``dispatch_op`` runs ``ir.module.module.search_read`` and,
    when not installed, ``button_immediate_install``. Nothing else is written.
    Refuses before any port call when the proposal is not installable or the
    module is not a Community stock app in the map.
    """
    from app.changeset.dispatch import DispatchError, dispatch_op
    from app.changeset.setting_ops import install_reversal_warning

    data = proposal.as_dict() if isinstance(proposal, StockAppProposal) else dict(proposal)
    module = str(data.get("module") or "").strip()
    label = str(data.get("app_label") or module)
    # The proposal is stored server-side; ``installable`` already folds in the
    # detected edition and the live module state (Enterprise apps on Enterprise,
    # or on unknown edition when the server lists the module as installable).
    known = {app.module for app in STOCK_APPS}
    if not data.get("installable") or module not in known:
        return InstallOutcome(
            ok=False,
            module=module,
            message=f"{label} cannot be installed from here.",
        )
    op = {"type": "module.install", "params": {"module": module}}
    try:
        module_id = dispatch_op(port, op)
    except DispatchError as exc:
        return InstallOutcome(ok=False, module=module, message=_one_sentence(label, str(exc)))
    except Exception as exc:  # noqa: BLE001 — Odoo/RPC failures become one sentence
        return InstallOutcome(ok=False, module=module, message=_one_sentence(label, str(exc)))
    warning = install_reversal_warning("module.install")
    return InstallOutcome(
        ok=True,
        module=module,
        module_id=int(module_id) if module_id is not None else None,
        message=f"{label} is installed.",
        warnings=(warning,) if warning else (),
    )


def _one_sentence(label: str, detail: str) -> str:
    text = " ".join((detail or "").split())
    low = text.lower()
    if "observer" in low or "read-only" in low or "read only" in low:
        return f"{label} was not installed because this connection is read-only."
    if "access" in low and ("denied" in low or "error" in low):
        return f"{label} was not installed because this Odoo user cannot install apps."
    if "not on this database" in low:
        return f"{label} was not installed because this Odoo server does not have it."
    return f"{label} could not be installed. Odoo did not finish the install."


def stock_app_clarification(proposal: StockAppProposal) -> dict[str, Any]:
    """App Studio clarification payload for the confirm step.

    Output: a ``kind=stock_app_install`` clarification the web renders as the
    install card. The options never ask the user to name an app.
    Side effects: none.
    """
    options = []
    if proposal.installable:
        options.append({"id": INSTALL_DECISION, "label": proposal.install_label})
    options.append({"id": DECLINE_DECISION, "label": proposal.decline_label})
    return {
        "id": f"stock_app_install:{proposal.module}",
        "kind": STOCK_APP_CLARIFICATION_KIND,
        "merge_key": STOCK_APP_CLARIFICATION_KIND,
        "question": proposal.question,
        "help": proposal.reason,
        "options": options,
        "default_id": DECLINE_DECISION,
        "stock_app": proposal.as_dict(),
    }


def declined_message(proposal: Mapping[str, Any]) -> str:
    """One sentence shown after "Not now". Side effects: none."""
    label = str(proposal.get("app_label") or "The app")
    if not proposal.get("installable"):
        return f"Stopped. {label} is not available here, so this request was not built."
    # (Only a PRIMARY host app reaches this step; integration apps never block.)
    return f"Stopped. {label} was not installed, so this request was not built."


__all__ = [
    "DECLINE_DECISION",
    "INSTALL_DECISION",
    "STOCK_APPS",
    "STOCK_APP_CLARIFICATION_KIND",
    "InstallFacts",
    "InstallOutcome",
    "StockApp",
    "StockAppMatch",
    "StockAppProposal",
    "declined_message",
    "install_stock_app",
    "match_stock_app",
    "match_stock_apps",
    "proposal_for",
    "propose_stock_app_install",
    "read_install_facts",
    "stock_app_clarification",
    "stock_app_for_model",
]
