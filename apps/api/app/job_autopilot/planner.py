"""Deterministic Job Packet planner. Optional frontier LLM enrich only."""

from __future__ import annotations

import json
import re

from app.expert.stack_inference import infer_odoo_stack_for_job
from app.ingest.classify import classify_structured
from app.job_autopilot.connectors.catalog import infer_connector_ids
from app.job_autopilot.packet import (
    CustomResidual,
    DataFileClass,
    JobPacket,
    SCORECARD_IS_NOT_GOLIVE,
)

_PLANNER_MODULE_SIGNALS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)\b(sell|sales|sold|quotations?|quotes?|orders?|"
            r"invoices?|invoicing|billing|revenue)\b"
        ),
        "sale",
    ),
    (re.compile(r"(?i)\b(account(?:ing)?|finance|ledger|books)\b"), "account"),
    (
        re.compile(
            r"(?i)\b(inventory|warehouses?|stock picking|stock location|"
            r"goods (?:in|out)|fulfilment|fulfillment)\b"
        ),
        "stock",
    ),
    (re.compile(r"(?i)\b(purchase|procurement|vendor|supplier|rfq)\b"), "purchase"),
    (re.compile(r"(?i)\b(crm|lead|pipeline|opportunit)\b"), "crm"),
    (re.compile(r"(?i)\b(hr|employees?|crew|payroll|timesheet)\b"), "hr"),
    (re.compile(r"(?i)\b(calendar|scheduling|appointments?)\b"), "calendar"),
    (re.compile(r"(?i)\b(projects?|milestones?)\b"), "project"),
    (re.compile(r"(?i)\b(pos|point of sale)\b"), "point_of_sale"),
    (re.compile(r"(?i)\b(manufactur|mrp|bill of materials)\b"), "mrp"),
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


def _classify_files(excerpts: list[tuple[str, str]]) -> list[DataFileClass]:
    out: list[DataFileClass] = []
    for filename, text in excerpts:
        headers: list[str] = []
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        if lines:
            headers = [h.strip() for h in re.split(r"[,;\t]", lines[0]) if h.strip()]
        result = classify_structured(filename=filename, headers=headers)
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
    for pat, mod in _PLANNER_MODULE_SIGNALS:
        if pat.search(prompt) and mod not in apps:
            apps.append(mod)
    if "sale" in apps and "account" not in apps:
        apps.append("account")
    if "mrp" in apps and "stock" not in apps:
        apps.append("stock")
    if "contacts" not in apps:
        apps.insert(0, "contacts")
    if "mail" not in apps:
        apps.insert(0, "mail")
    return list(dict.fromkeys(apps)), stack.domain_label


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


def _enrich_with_llm(packet: JobPacket, prompt: str, excerpts: str) -> JobPacket:
    from app.llm_provider import get_llm_provider

    provider = get_llm_provider()
    if provider is None:
        packet.warnings.append("Frontier LLM not configured — deterministic packet kept.")
        return packet
    system = (
        "You extract ERP job facts. Return JSON only. Do not add custom x_* models "
        "that duplicate stock Odoo (invoice, partner, employee, warehouse, product). "
        "You may add actors, processes, documents, roles, and risks. "
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
    packet.planner = "deterministic+frontier"
    return packet


def build_job_packet(
    prompt: str,
    *,
    file_excerpts: list[tuple[str, str]] | None = None,
    country_code: str | None = None,
    company_name: str | None = None,
    use_llm: bool | None = None,
) -> JobPacket:
    """NL + optional file excerpts → typed packet. Never mutates Odoo."""
    text = (prompt or "").strip()
    if not text:
        raise ValueError("prompt is required")
    files = file_excerpts or []
    blob = text + "\n" + "\n".join(f"{n}\n{b}" for n, b in files)

    stock, domain = _stock_apps(blob)
    residuals = _residuals_from_brief(blob)
    residuals = [r for r in residuals if not _FORBIDDEN_PARALLEL.search(r.model)]
    country = _detect_country(blob, country_code)
    currency = _detect_currency(blob, country)
    company = _detect_company(blob, company_name)
    l10n = COUNTRY_L10N.get(country or "") if country else None
    warehouse = "stock" in stock
    data_files = _classify_files(files)

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
    ]
    if residuals:
        decisions.append(
            "Custom residual: "
            + "; ".join(f"{r.model} ({r.reason})" for r in residuals)
        )
    else:
        decisions.append("No custom residual — skip ModuleSpec apply.")
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
    extra_warnings: list[str] = []
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
            "POS receipt designer is Option A OWL/QWeb on point_of_sale — "
            "no custom x_receipt residual."
        )
        packet.warnings.append(
            "A GM-style visual receipt designer is not a Draft Studio residual. "
            "Autopilot can install point_of_sale; print layout is a human Option A module."
        )
    if _should_use_frontier(use_llm):
        try:
            excerpt_blob = "\n\n".join(f"## {n}\n{b[:2000]}" for n, b in files)
            packet = _enrich_with_llm(packet, text, excerpt_blob)
        except Exception as exc:  # noqa: BLE001
            packet.warnings.append(f"LLM enrich skipped: {exc}")
    return packet


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
    "file_excerpts_from_bytes",
]
