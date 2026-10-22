"""Deterministic Job Packet planner. Optional frontier LLM enrich only."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.expert.stack_inference import infer_odoo_stack_for_job
from app.ingest.classify import classify_structured
from app.job_autopilot.connectors.catalog import infer_connector_ids
from app.job_autopilot.packet import (
    SCORECARD_IS_NOT_GOLIVE,
    CustomResidual,
    DataFileClass,
    JobPacket,
)
from app.live_schema_context import (
    SchemaPacket,
    model_in_packet,
    prepend_schema_packet,
    studio_schema_packet,
)
from app.stock_app_install import (
    STOCK_APPS,
    InstallFacts,
    StockAppMatch,
    match_stock_apps,
    proposal_for,
    stock_app_for_model,
)

# Business vocabulary -> host model. The module for each model comes from the
# shared stock-app map (``app.stock_app_install``), never from this table.
_PLANNER_MODEL_SIGNALS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)\b(sell|sales|sold|quotations?|quotes?|orders?|"
            r"invoices?|invoicing|billing|revenue)\b"
        ),
        "sale.order",
    ),
    (re.compile(r"(?i)\b(account(?:ing)?|finance|ledger|books)\b"), "account.move"),
    (
        re.compile(
            r"(?i)\b(inventory|warehouses?|stock picking|stock location|"
            r"goods (?:in|out)|fulfilment|fulfillment)\b"
        ),
        "stock.picking",
    ),
    (re.compile(r"(?i)\b(purchase|procurement|vendor|supplier|rfq)\b"), "purchase.order"),
    (re.compile(r"(?i)\b(crm|lead|pipeline|opportunit)\b"), "crm.lead"),
    (re.compile(r"(?i)\b(hr|employees?|crew|payroll|timesheet)\b"), "hr.employee"),
    (re.compile(r"(?i)\b(calendar|scheduling|appointments?)\b"), "calendar.event"),
    (re.compile(r"(?i)\b(projects?|milestones?)\b"), "project.task"),
    (re.compile(r"(?i)\b(pos|point of sale)\b"), "pos.order"),
    (re.compile(r"(?i)\b(manufactur|mrp|bill of materials)\b"), "mrp.production"),
)

_SKIP_INSTALL = frozenset({"base", "web"})

# Stock-first residual: only documents Community apps do not cover.
_RESIDUAL_NEEDLES: tuple[tuple[re.Pattern[str], str, str, str], ...] = (
    (
        re.compile(
            r"(?i)\b(bookings?|studio sessions?|recording sessions?|"
            r"session bookings?|appointment book)\b"
        ),
        "booking",
        "x_booking",
        "Booking/session document — Calendar + CRM do not replace a lined booking record.",
    ),
    (
        re.compile(r"(?i)\b(legal matter|case file|matter management|law firm)\b"),
        "matter",
        "x_matter",
        "Legal matter document — Project/CRM do not replace a matter file.",
    ),
    (
        re.compile(
            r"(?i)\b(hotel stay|room reservations?|guest stay|"
            r"hotel check-?in|pms check-?in)\b"
        ),
        "stay",
        "x_stay",
        "Stay/reservation document — stock Event/CRM do not replace hotel stay.",
    ),
    (
        re.compile(r"(?i)\b(patient encounter|clinic visit|treatment plan|consult)\b"),
        "encounter",
        "x_encounter",
        "Clinical encounter — Calendar does not replace a visit document.",
    ),
    (
        re.compile(r"(?i)\b(library (loan|checkout)|book loan|circulation)\b"),
        "loan",
        "x_loan",
        "Circulation loan — stock does not replace a loan document.",
    ),
    (
        re.compile(r"(?i)\b(rental (contract|agreement)|vehicle hire|car hire)\b"),
        "rental",
        "x_rental",
        "Rental contract — Sale Order is not a vehicle-hire document.",
    ),
)

_FORBIDDEN_PARALLEL = re.compile(
    r"(?i)\b(x_invoice|x_client|x_customer|x_employee|x_warehouse|x_product|"
    r"x_partner|x_sale_order|x_bill)\b"
)

_COUNTRY: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b(united states|\bu\.?s\.?a\.?\b|\bus\b)\b"), "US"),
    (re.compile(r"(?i)\b(united kingdom|\buk\b|great britain|england)\b"), "GB"),
    (re.compile(r"(?i)\bnigeria\b"), "NG"),
    (re.compile(r"(?i)\bgermany|\bdeutschland\b"), "DE"),
    (re.compile(r"(?i)\bfrance\b"), "FR"),
    (re.compile(r"(?i)\bnetherlands|\bholland\b"), "NL"),
    (re.compile(r"(?i)\bbelgium\b"), "BE"),
    (re.compile(r"(?i)\bindia\b"), "IN"),
    (re.compile(r"(?i)\baustralia\b"), "AU"),
    (re.compile(r"(?i)\bcanada\b"), "CA"),
    (re.compile(r"(?i)\bmexico\b"), "MX"),
    (re.compile(r"(?i)\bsouth africa\b"), "ZA"),
    (re.compile(r"(?i)\bspain\b"), "ES"),
    (re.compile(r"(?i)\bitaly\b"), "IT"),
    (re.compile(r"(?i)\bkenya\b"), "KE"),
    (re.compile(r"(?i)\bghana\b"), "GH"),
)

COUNTRY_L10N: dict[str, str] = {
    "US": "l10n_us",
    "GB": "l10n_uk",
    "DE": "l10n_de",
    "FR": "l10n_fr",
    "NL": "l10n_nl",
    "BE": "l10n_be",
    "IN": "l10n_in",
    "AU": "l10n_au",
    "CA": "l10n_ca",
    "MX": "l10n_mx",
    "NG": "l10n_ng",
    "ZA": "l10n_za",
    "ES": "l10n_es",
    "IT": "l10n_it",
    "KE": "l10n_ke",
    "GH": "l10n_generic_coa",
}

# ISO currency for the company write. NGN/KES/GHS are often inactive until activated.
COUNTRY_CURRENCY: dict[str, str] = {
    "US": "USD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "NL": "EUR",
    "BE": "EUR",
    "IN": "INR",
    "AU": "AUD",
    "CA": "CAD",
    "MX": "MXN",
    "NG": "NGN",
    "ZA": "ZAR",
    "ES": "EUR",
    "IT": "EUR",
    "KE": "KES",
    "GH": "GHS",
}

_CURRENCY: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b(naira|\bngn\b)\b"), "NGN"),
    (re.compile(r"(?i)\b(us dollars?|\busd\b|\$)\b"), "USD"),
    (re.compile(r"(?i)\b(pound sterling|\bgbp\b|£)\b"), "GBP"),
    (re.compile(r"(?i)\b(euro|\beur\b|€)\b"), "EUR"),
    (re.compile(r"(?i)\b(naira)\b"), "NGN"),
    (re.compile(r"(?i)\b(cad|canadian dollar)\b"), "CAD"),
    (re.compile(r"(?i)\b(inr|rupee)\b"), "INR"),
    (re.compile(r"(?i)\b(aud|australian dollar)\b"), "AUD"),
    (re.compile(r"(?i)\b(zar|rand)\b"), "ZAR"),
    (re.compile(r"(?i)\b(mxn|peso)\b"), "MXN"),
)

_CLIENT_NAME_RE = re.compile(
    r"(?i)(?:client|company|business)\s+name\s*:\s*(.+)"
)
_GENERIC_COMPANY = frozenset(
    {
        "one company",
        "a company",
        "the company",
        "this company",
        "our company",
        "my company",
        "your company",
        "the business",
        "our business",
        "the client",
    }
)

_RESTAURANT_DOMINANT = re.compile(
    r"(?i)\b(restaurant|lounge|kitchen|dine-?in|takeaway|jollof|waiter|pos)\b"
)
_HOTEL_OPERATIONS = re.compile(
    r"(?i)\b(hotel stay|housekeeping|guest folio|room booking|"
    r"room reservations?|\bpms\b|"
    r"(?:hotel|pms).{0,48}front desk|front desk.{0,48}(?:hotel|pms|room|housekeeping))\b"
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SKIP_EMAILS = frozenset({"admin@example.com", "odoo@example.com"})

_ACTOR_RE = re.compile(
    r"(?i)\b(accountant|sales(?:person| team)?|warehouse staff|technician|"
    r"manager|receptionist|nurse|doctor|lawyer|producer|engineer|hr)\b"
)

_PROCESS_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bquote|quotation|sales order\b"), "quote_to_invoice"),
    (re.compile(r"(?i)\bdeliver|picking|shipment\b"), "deliver"),
    (re.compile(r"(?i)\binvoice|billing\b"), "invoice"),
    (re.compile(r"(?i)\bbooking|session\b"), "booking_to_invoice"),
    (re.compile(r"(?i)\bpurchase|rfq\b"), "procure"),
    (re.compile(r"(?i)\bpayslip|payroll\b"), "payroll"),
)

# Method names the version table may admit or omit for a major.
_VERSION_METHOD_NAMES: tuple[str, ...] = ("read_group", "formatted_read_group")
_TECH_REF_RE = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]+)+\b")


def _resolve_schema_packet(schema_packet: SchemaPacket | None) -> SchemaPacket | None:
    if schema_packet is not None:
        return schema_packet
    try:
        from app.ai_conversation.intent_llm import current_schema_packet

        return current_schema_packet()
    except Exception:  # noqa: BLE001
        return None


def _is_custom_model(name: str) -> bool:
    return name.startswith("x_")


def _method_in_packet(
    packet: SchemaPacket | None,
    method: str,
    *,
    model: str | None = None,
) -> bool:
    name = str(method or "").strip()
    if not name:
        return False
    if packet is None:
        return True
    if model:
        row = packet.models.get(model)
        return bool(row and name in row.methods)
    return any(name in row.methods for row in packet.models.values())


def drop_unknown_planner_refs(
    models: Sequence[str],
    methods: Sequence[str],
    packet: SchemaPacket | None,
) -> tuple[list[str], list[str]]:
    """Keep planner model/method names the live schema packet admits.

    Inputs: candidate technical names and the packet from
    ``live_schema_context``. ``packet is None`` (no connection) leaves the
    lists unchanged. Custom ``x_*`` residuals are invent-to-create and stay.
    Output: admitted models, admitted methods. Side effects: none.
    """

    kept_models: list[str] = []
    for raw in models:
        name = str(raw or "").strip()
        if not name or name in kept_models:
            continue
        if _is_custom_model(name) or model_in_packet(packet, name):
            kept_models.append(name)
    kept_methods: list[str] = []
    for raw in methods:
        name = str(raw or "").strip()
        if not name or name in kept_methods:
            continue
        if _method_in_packet(packet, name):
            kept_methods.append(name)
    return kept_models, kept_methods


def _collect_refs_from_text(
    text: str,
    packet: SchemaPacket | None,
) -> tuple[list[str], list[str]]:
    models: list[str] = []
    methods: list[str] = []
    blob = text or ""
    for name in _VERSION_METHOD_NAMES:
        if re.search(rf"\b{re.escape(name)}\b", blob):
            methods.append(name)
    for match in _TECH_REF_RE.finditer(blob):
        token = match.group(0)
        if packet is not None and token in packet.models:
            models.append(token)
            continue
        if _is_custom_model(token):
            models.append(token)
            continue
        if "." in token:
            head, tail = token.rsplit(".", 1)
            if packet is not None and head in packet.models:
                models.append(head)
                methods.append(tail)
                continue
            models.append(token)
    return models, methods


def _strip_dropped_tokens(text: str, dropped: Sequence[str]) -> str:
    cleaned = text
    for token in sorted(dropped, key=len, reverse=True):
        cleaned = re.sub(rf"\b{re.escape(token)}\b", "", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip(" ,;.-")


def _scrub_seq(items: list[str], dropped: Sequence[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        cleaned = _strip_dropped_tokens(item, dropped)
        if cleaned:
            out.append(cleaned)
    return out


def _scrub_tree(value: Any, dropped: Sequence[str]) -> Any:
    if isinstance(value, str):
        return _strip_dropped_tokens(value, dropped)
    if isinstance(value, list):
        cleaned = [_scrub_tree(item, dropped) for item in value]
        return [item for item in cleaned if item not in ("", None, [], {})]
    if isinstance(value, Mapping):
        return {key: _scrub_tree(item, dropped) for key, item in value.items()}
    return value


def filter_job_packet_to_schema(
    job: JobPacket,
    schema_packet: SchemaPacket | None,
    *,
    planned_models: Sequence[str] | None = None,
    planned_methods: Sequence[str] | None = None,
) -> JobPacket:
    """Drop planner models/methods the live slice does not contain.

    Inputs: a Job Packet, optional extra planned names, and the schema
    packet. Runs before sandbox apply. ``schema_packet is None`` leaves
    the job unchanged. Side effects: mutates ``job`` lists and
    ``operator_brief``; does not call Odoo or a language model.
    """

    packet = _resolve_schema_packet(schema_packet)
    proposed_models: list[str] = []
    proposed_methods: list[str] = []
    for raw in planned_models or ():
        name = str(raw or "").strip()
        if name:
            proposed_models.append(name)
    for raw in planned_methods or ():
        name = str(raw or "").strip()
        if name:
            proposed_methods.append(name)
    brief = job.operator_brief if isinstance(job.operator_brief, dict) else {}
    for raw in brief.get("schema_models") or ():
        name = str(raw or "").strip()
        if name:
            proposed_models.append(name)
    for raw in brief.get("schema_methods") or ():
        name = str(raw or "").strip()
        if name:
            proposed_methods.append(name)
    for residual in job.custom_residuals:
        proposed_models.append(residual.model)
    scan_parts = [
        job.structured_brief,
        *job.actors,
        *job.processes,
        *job.documents,
        *job.roles,
        *job.risks,
        *job.warnings,
        *job.decision_record,
        *job.grounding,
    ]
    for part in scan_parts:
        found_models, found_methods = _collect_refs_from_text(str(part), packet)
        proposed_models.extend(found_models)
        proposed_methods.extend(found_methods)
    prompt_models, prompt_methods = _collect_refs_from_text(job.prompt, packet)
    proposed_models.extend(prompt_models)
    proposed_methods.extend(prompt_methods)

    kept_models, kept_methods = drop_unknown_planner_refs(
        proposed_models, proposed_methods, packet
    )
    if packet is None:
        brief["schema_models"] = list(dict.fromkeys(proposed_models))
        brief["schema_methods"] = list(dict.fromkeys(proposed_methods))
        job.operator_brief = brief
        return job

    dropped = [name for name in dict.fromkeys(proposed_models) if name not in kept_models]
    dropped.extend(name for name in dict.fromkeys(proposed_methods) if name not in kept_methods)
    job.custom_residuals = [
        residual
        for residual in job.custom_residuals
        if _is_custom_model(residual.model) or model_in_packet(packet, residual.model)
    ]
    job.actors = _scrub_seq(job.actors, dropped)
    job.processes = _scrub_seq(job.processes, dropped)
    job.documents = _scrub_seq(job.documents, dropped)
    job.roles = _scrub_seq(job.roles, dropped)
    job.risks = _scrub_seq(job.risks, dropped)
    job.warnings = _scrub_seq(job.warnings, dropped)
    job.decision_record = _scrub_seq(job.decision_record, dropped)
    job.grounding = _scrub_seq(job.grounding, dropped)
    job.structured_brief = _strip_dropped_tokens(job.structured_brief, dropped)
    job.operator_brief = _scrub_tree(brief, dropped)
    job.operator_brief["schema_models"] = kept_models
    job.operator_brief["schema_methods"] = kept_methods
    return job


def _detect_country(text: str, override: str | None = None) -> str | None:
    if override:
        return override.strip().upper()[:2]
    for pat, code in _COUNTRY:
        if pat.search(text):
            return code
    return None


def _detect_currency(text: str, country: str | None) -> str | None:
    for pat, code in _CURRENCY:
        if pat.search(text):
            return code
    return COUNTRY_CURRENCY.get(country or "")


def _plausible_company_name(name: str) -> bool:
    cleaned = " ".join(name.split()).strip(" .,")
    if len(cleaned) < 3:
        return False
    if cleaned.lower() in _GENERIC_COMPANY:
        return False
    return True


def _detect_company(text: str, override: str | None = None) -> str | None:
    """Only labeled Client/Company/Business name — never 'for one company' / 'for B2B'."""
    if override and override.strip():
        name = override.strip()[:80]
        return name if _plausible_company_name(name) else None
    labeled = _CLIENT_NAME_RE.search(text)
    if labeled:
        name = labeled.group(1).strip(" .,")
        if _plausible_company_name(name):
            return name[:80]
    return None


def _residuals_from_brief(text: str) -> list[CustomResidual]:
    found: list[CustomResidual] = []
    seen: set[str] = set()
    restaurant_not_hotel = bool(_RESTAURANT_DOMINANT.search(text)) and not bool(
        _HOTEL_OPERATIONS.search(text)
    )
    for pat, key, model, reason in _RESIDUAL_NEEDLES:
        if key in seen:
            continue
        if key == "stay" and restaurant_not_hotel:
            continue
        if pat.search(text):
            seen.add(key)
            found.append(CustomResidual(key=key, model=model, reason=reason))
    from app.ai_stock_first import extract_explicit_residuals

    for key, model, reason in extract_explicit_residuals(text):
        if key in seen:
            continue
        seen.add(key)
        found.append(CustomResidual(key=key, model=model, reason=reason))
    return found


def _classify_files(
    excerpts: list[tuple[str, str]],
    *,
    schema_packet: SchemaPacket | None = None,
) -> list[DataFileClass]:
    out: list[DataFileClass] = []
    for filename, text in excerpts:
        headers: list[str] = []
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        if lines:
            headers = [h.strip() for h in re.split(r"[,;\t]", lines[0]) if h.strip()]
        result = classify_structured(
            filename=filename,
            headers=headers,
            schema_packet=schema_packet,
        )
        out.append(
            DataFileClass(
                filename=filename,
                doc_type=result.doc_type,
                confidence=float(result.confidence or 0.0),
                excerpt=(text or "")[:500],
            )
        )
    return out


def _stock_apps(prompt: str) -> tuple[list[str], str]:
    from app.ai_operator_brief import (
        build_operator_brief,
        has_named_stock_section,
        is_explicit_stock_first,
        is_residual_none,
        wants_stock_reuse,
    )

    brief = build_operator_brief(prompt)
    stack = infer_odoo_stack_for_job(prompt)
    named = [m for m in brief.stock_reuse if m]
    if named and (
        has_named_stock_section(prompt)
        or is_explicit_stock_first(prompt)
        or is_residual_none(prompt)
        or wants_stock_reuse(prompt)
    ):
        apps = ["mail", "contacts", *named]
        domain = (
            "Point of Sale"
            if "point_of_sale" in apps and "website_sale" not in named
            else stack.domain_label
        )
        return list(dict.fromkeys(apps)), domain
    apps = [m for m in stack.stock_modules if m not in _SKIP_INSTALL]
    for pat, model in _PLANNER_MODEL_SIGNALS:
        app = stock_app_for_model(model)
        if app is not None and pat.search(prompt) and app.module not in apps:
            apps.append(app.module)
    if "sale" in apps and "account" not in apps:
        apps.append("account")
    if "mrp" in apps and "stock" not in apps:
        apps.append("stock")
    if "contacts" not in apps:
        apps.insert(0, "contacts")
    if "mail" not in apps:
        apps.insert(0, "mail")
    return list(dict.fromkeys(apps)), stack.domain_label


_STOCK_APP_BY_MODULE = {app.module: app for app in STOCK_APPS}
_EDITION_UNKNOWN_NOTE = "Edition not detected: "
_PLANNED_INSTALL_FACTS = InstallFacts(model_present=False, module_state="uninstalled")
_ENTERPRISE_FACTS = InstallFacts(model_present=False, module_state=None, edition="community")


def _packet_edition(schema_packet: SchemaPacket | None) -> tuple[str, dict[str, str]]:
    """Detected edition and module states from the live slice (``unknown`` without one)."""
    if schema_packet is None:
        return "unknown", {}
    from app.tier_matrix import detect_edition

    states = {
        str(row.get("name") or ""): str(row.get("state") or "")
        for row in (schema_packet.modules or ())
    }
    installed = {name for name, state in states.items() if state == "installed"}
    return detect_edition(schema_packet.server_version, installed), states


def _stock_app_plan(
    prompt: str,
    apps: list[str],
    schema_packet: SchemaPacket | None,
) -> tuple[list[str], list[str], list[str]]:
    """Drop Enterprise-only apps and state why each stock app is installed.

    Approving the Autopilot plan is the GND-MOD confirm, so the plan itself
    carries the shared ``stock_app_install`` wording and no other prompt follows.
    Inputs: the request text, the planned modules, and the live slice
    (``None`` = no connection). Output: modules to install, one plan line per
    stock-app install with the shared reason, and one explanation per
    Enterprise-only app (never installed). Side effects: none.
    """
    by_words = {match.app.module: match for match in match_stock_apps(prompt)}
    edition, module_states = _packet_edition(schema_packet)
    enterprise = [m for m in by_words.values() if not m.app.is_community]
    for module in apps:
        app = _STOCK_APP_BY_MODULE.get(module)
        if app is not None and not app.is_community and module not in by_words:
            enterprise.append(StockAppMatch(app=app, model=app.models[0], noun=app.noun))
    explanations: list[str] = []
    allowed_ee: set[str] = set()
    for match in enterprise:
        module = match.app.module
        state = module_states.get(module)
        if edition == "enterprise" or (edition == "unknown" and state not in {None, "uninstallable"}):
            allowed_ee.add(module)
            continue
        if edition == "unknown":
            # Unknown edition never hard-blocks: keep it, say what it depends on.
            allowed_ee.add(module)
            explanations.append(
                f"{_EDITION_UNKNOWN_NOTE}{match.app.label} is an Odoo Enterprise app; it "
                "installs only if this database is Enterprise."
            )
            continue
        proposal = proposal_for(match, _ENTERPRISE_FACTS)
        if proposal is not None:
            explanations.append(f"{proposal.question} {proposal.reason}")

    keep: list[str] = []
    why: list[str] = []
    for module in apps:
        app = _STOCK_APP_BY_MODULE.get(module)
        if app is not None and not app.is_community and module not in allowed_ee:
            continue
        keep.append(module)
        if app is None:
            continue
        if schema_packet is not None and model_in_packet(schema_packet, app.models[0]):
            continue
        match = by_words.get(module) or StockAppMatch(
            app=app, model=app.models[0], noun=app.noun
        )
        proposal = proposal_for(match, _PLANNED_INSTALL_FACTS)
        if proposal is not None:
            why.append(f"Install {app.label} ({module}): {proposal.reason}")
    return keep, why, explanations


def _should_use_frontier(use_llm: bool | None) -> bool:
    if use_llm is False:
        return False
    if use_llm is True:
        return True
    from app.llm_provider import resolve_provider_mode

    return resolve_provider_mode() in {
        "anthropic",
        "openai",
        "gemini",
        "openai-compatible",
    }


def _enrich_with_llm(
    packet: JobPacket,
    prompt: str,
    excerpts: str,
    *,
    schema_packet: SchemaPacket | None = None,
) -> JobPacket:
    from app.llm_provider import get_llm_provider

    provider = get_llm_provider()
    if provider is None:
        packet.warnings.append("Frontier LLM not configured — deterministic packet kept.")
        return packet
    system = (
        "You extract ERP job facts. Return JSON only. Do not add custom x_* models "
        "that duplicate stock Odoo (invoice, partner, employee, warehouse, product). "
        "You may add actors, processes, documents, roles, and risks. "
        "Do not name a model or method that is not in the live schema packet. "
        "Leave stock_apps, custom_residuals, and connectors unchanged."
    )
    user = (
        f"Brief:\n{prompt}\n\nFile excerpts:\n{excerpts[:8000]}\n\n"
        f"Current packet JSON:\n{packet.model_dump_json()}\n"
    )
    try:
        from app.ai_operator_brief import prompt_for_generators

        user = (
            f"{prompt_for_generators(prompt)}\n\nFile excerpts:\n{excerpts[:8000]}\n\n"
            f"Current packet JSON:\n{packet.model_dump_json()}\n"
        )
    except Exception:
        pass
    user = prepend_schema_packet(user, schema_packet)
    raw = provider.generate_json(user, system=system, timeout_s=60.0, temperature=0.1)
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, dict):
        packet.warnings.append("LLM enrich returned non-object — ignored.")
        return packet
    for key in ("actors", "processes", "documents", "roles", "risks"):
        extra = data.get(key)
        if isinstance(extra, list):
            cur = list(getattr(packet, key))
            for item in extra:
                s = str(item).strip()
                if s and s not in cur:
                    cur.append(s)
            setattr(packet, key, cur)
    brief = dict(packet.operator_brief or {})
    extra_models = [
        str(item).strip()
        for item in (data.get("models") or [])
        if str(item).strip()
    ]
    extra_methods = [
        str(item).strip()
        for item in (data.get("methods") or [])
        if str(item).strip()
    ]
    if extra_models:
        brief["schema_models"] = list(
            dict.fromkeys([*(brief.get("schema_models") or []), *extra_models])
        )
    if extra_methods:
        brief["schema_methods"] = list(
            dict.fromkeys([*(brief.get("schema_methods") or []), *extra_methods])
        )
    packet.operator_brief = brief
    packet.planner = "deterministic+frontier"
    return packet


def build_job_packet(
    prompt: str,
    *,
    file_excerpts: list[tuple[str, str]] | None = None,
    country_code: str | None = None,
    company_name: str | None = None,
    use_llm: bool | None = None,
    schema_packet: SchemaPacket | None = None,
    planned_models: Sequence[str] | None = None,
    planned_methods: Sequence[str] | None = None,
) -> JobPacket:
    """NL + optional file excerpts → typed packet. Never mutates Odoo.

    When ``schema_packet`` is supplied (or the request already set one),
    models and methods outside that slice are dropped before sandbox apply.
    """
    text = (prompt or "").strip()
    if not text:
        raise ValueError("prompt is required")
    files = file_excerpts or []
    blob = text + "\n" + "\n".join(f"{n}\n{b}" for n, b in files)
    packet_slice = _resolve_schema_packet(schema_packet)

    stock, domain = _stock_apps(blob)
    stock, install_why, enterprise_notes = _stock_app_plan(blob, stock, packet_slice)
    residuals = _residuals_from_brief(blob)
    residuals = [r for r in residuals if not _FORBIDDEN_PARALLEL.search(r.model)]
    country = _detect_country(blob, country_code)
    currency = _detect_currency(blob, country)
    company = _detect_company(blob, company_name)
    l10n = COUNTRY_L10N.get(country or "") if country else None
    warehouse = "stock" in stock
    data_files = _classify_files(files, schema_packet=packet_slice)

    actors = sorted({m.group(0).lower() for m in _ACTOR_RE.finditer(blob)})
    processes: list[str] = []
    for pat, name in _PROCESS_HINTS:
        if pat.search(blob) and name not in processes:
            processes.append(name)
    if not processes and "sale" in stock:
        processes.append("quote_to_invoice")

    documents = [d.doc_type for d in data_files if d.doc_type != "other"]
    if residuals:
        documents.extend(r.key for r in residuals)

    org_emails = []
    for m in _EMAIL_RE.finditer(blob):
        email = m.group(0).lower()
        if email not in _SKIP_EMAILS and email not in org_emails:
            org_emails.append(email)
    org_emails = org_emails[:12]

    decisions = [
        "Stock-first: install Community apps that cover the brief; custom x_* is residual only.",
        f"Stock apps: {', '.join(stock) or '(none)'}.",
        *install_why,
        *(
            note if note.startswith(_EDITION_UNKNOWN_NOTE) else f"No install planned. {note}"
            for note in enterprise_notes
        ),
    ]
    if residuals:
        decisions.append(
            "Custom code: "
            + "; ".join(f"{r.model} ({r.reason})" for r in residuals)
        )
    else:
        decisions.append("No custom code — skip app plan apply.")
    if l10n:
        decisions.append(f"Fiscal: install {l10n} for country {country}.")
    decisions.append(SCORECARD_IS_NOT_GOLIVE)

    risks = [
        "Autopilot writes only a sandbox (or staging with confirm). Production is refused.",
        "Promote to customer prod stays a human confirm.",
    ]
    if warehouse:
        risks.append("Warehouse/locations will be created if stock is empty.")
    if data_files:
        risks.append("Client files ingest after dry-run; prod/staging still need confirm.")

    connectors = infer_connector_ids(blob, country)
    extra_warnings: list[str] = list(enterprise_notes)
    if connectors:
        extra_warnings.append(
            "Connector recipes are domain-agnostic (payments → inbound orders → "
            "messaging → hardware → statutory payroll). They configure stock Odoo "
            "and fixtures; they do not invent a vertical-specific x_* model."
        )
        extra_warnings.append(
            "Live partner APIs stay off until secrets exist in env / Odoo. "
            "Autopilot never writes API keys into the job packet or ir.config_parameter."
        )
        if "statutory_payroll" in connectors:
            extra_warnings.append(
                "Statutory payroll is compute-only (golden-file pack). "
                "It never writes hr.payslip. Verify rates against current law."
            )
    decisions.append(
        "Connectors (ordered, domain-agnostic): "
        + (", ".join(connectors) if connectors else "none detected.")
    )

    packet = JobPacket(
        prompt=text,
        domain_label=domain,
        actors=actors,
        processes=processes,
        documents=list(dict.fromkeys(documents)),
        stock_apps=stock,
        custom_residuals=residuals,
        data_files=data_files,
        country_code=country,
        l10n_module=l10n,
        company_name=company,
        currency=currency,
        warehouse_needed=warehouse,
        roles=list(actors),
        org_emails=org_emails,
        risks=risks,
        warnings=extra_warnings,
        decision_record=decisions,
        planner="deterministic",
        connectors=connectors,
    )
    from app.ai_operator_brief import (
        build_operator_brief,
        is_explicit_stock_first,
        is_pos_receipt_prompt,
        wants_stock_reuse,
    )

    op_brief = build_operator_brief(text)
    packet.structured_brief = op_brief.formatted
    packet.operator_brief = op_brief.to_dict()
    if op_brief.unknowns:
        packet.warnings.append(
            "Unknowns (not assumed): " + "; ".join(op_brief.unknowns)
        )
    if is_pos_receipt_prompt(text) and not (
        is_explicit_stock_first(text) or wants_stock_reuse(text)
    ):
        packet.custom_residuals = []
        packet.decision_record.append(
            "POS receipt designer is custom code OWL/QWeb on point_of_sale — "
            "no custom x_receipt residual."
        )
        packet.warnings.append(
            "A GM-style visual receipt designer is not a Draft Studio residual. "
            "Autopilot can install point_of_sale; print layout is a huma custom-code module."
        )
    if _should_use_frontier(use_llm):
        try:
            excerpt_blob = "\n\n".join(f"## {n}\n{b[:2000]}" for n, b in files)
            packet = _enrich_with_llm(
                packet, text, excerpt_blob, schema_packet=packet_slice
            )
        except Exception as exc:  # noqa: BLE001
            packet.warnings.append(f"LLM enrich skipped: {exc}")
    return filter_job_packet_to_schema(
        packet,
        packet_slice,
        planned_models=planned_models,
        planned_methods=planned_methods,
    )


def build_job_packet_for_connection(
    prompt: str,
    connection: Any,
    *,
    file_excerpts: list[tuple[str, str]] | None = None,
    country_code: str | None = None,
    company_name: str | None = None,
    use_llm: bool | None = None,
    planned_models: Sequence[str] | None = None,
    planned_methods: Sequence[str] | None = None,
    schema_client: Any | None = None,
    schema_graph: Any | None = None,
    host: str | None = None,
    available: list[str] | None = None,
    draft: dict[str, Any] | None = None,
) -> JobPacket:
    """Route entry: build the live packet from ``connection``, then plan.

    The caller does not pass ``schema_packet``. Draft Studio's
    ``studio_schema_packet`` is used. ``current_schema_packet()`` is set
    for workflow / ingest on this request. No live language model.
    """

    from app.ai_conversation.intent_llm import reset_schema_packet, set_schema_packet

    slice_packet = studio_schema_packet(
        connection,
        prompt=prompt,
        host=host,
        available=available,
        draft=draft,
        schema_client=schema_client,
        schema_graph=schema_graph,
    )
    token = set_schema_packet(slice_packet)
    try:
        return build_job_packet(
            prompt,
            file_excerpts=file_excerpts,
            country_code=country_code,
            company_name=company_name,
            use_llm=use_llm,
            planned_models=planned_models,
            planned_methods=planned_methods,
        )
    finally:
        reset_schema_packet(token)


def file_excerpts_from_bytes(
    files: list[tuple[str, bytes]],
    *,
    max_chars: int = 8000,
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, raw in files:
        if not raw:
            out.append((name, ""))
            continue
        if raw[:4] == b"%PDF":
            try:
                from app.ingest.extract_pdf import extract_text_from_pdf

                text = extract_text_from_pdf(raw)[:max_chars]
            except Exception:  # noqa: BLE001
                text = ""
            out.append((name, text))
            continue
        try:
            text = raw.decode("utf-8", errors="replace")[:max_chars]
        except Exception:  # noqa: BLE001
            text = ""
        out.append((name, text))
    return out


__all__ = [
    "COUNTRY_CURRENCY",
    "COUNTRY_L10N",
    "build_job_packet",
    "build_job_packet_for_connection",
    "drop_unknown_planner_refs",
    "file_excerpts_from_bytes",
    "filter_job_packet_to_schema",
]
