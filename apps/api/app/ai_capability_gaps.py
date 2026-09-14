"""Domain-agnostic capability gaps — live metadata vs Option A.

Stitch-like prompts often ask for PDF/QWeb, QR on documents, click-to-pay,
website controllers, OWL widgets, or Python. Those are not field packs.
Detect them without vertical packs; stamp Option A; never invent ``x_dynamic``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.text_negation import has_positive_match


@dataclass(frozen=True)
class CapabilityGap:
    """One surface the live Apply path cannot finish alone."""

    id: str
    label: str
    detail: str
    option_a_path: str
    # Honest live stubs only — never padding.
    stub_fields: tuple[dict[str, Any], ...] = ()


@dataclass
class CapabilityAssessment:
    gaps: list[CapabilityGap] = field(default_factory=list)
    # True when the prompt is primarily a non-live surface (not "SLA + QR").
    primary_option_a: bool = False
    # Nouns the scorecard should treat as covered by the gap stamp.
    covered_nouns: set[str] = field(default_factory=set)

    @property
    def option_a_paths(self) -> list[str]:
        return [g.option_a_path for g in self.gaps]


# Adverbs / chrome / mechanism words — not domain entities.
CAPABILITY_NOISE_NOUNS = frozenset(
    {
        "add",
        "attach",
        "extend",
        "plug",
        "dynamic",
        "static",
        "directly",
        "automatically",
        "online",
        "click",
        "button",
        "buttons",
        "code",
        "codes",
        "pdf",
        "print",
        "printed",
        "show",
        "display",
        "using",
        "via",
        "onto",
        "into",
        "from",
        "with",
        "also",
        "just",
        "please",
        "need",
        "want",
        "make",
        "create",
        "build",
        "custom",
        "extra",
        "extras",
        # Mechanism / Option A surfaces — never become x_<mechanism>.
        "website",
        "controller",
        "portal",
        "endpoint",
        "route",
        "http",
        "owl",
        "widget",
        "widgets",
        "javascript",
        "frontend",
        "python",
        "compute",
        "computed",
        "cron",
        "constraint",
        "override",
        "template",
        "templates",
        "mail",
        "email",
        "qweb",
        "report",
        "reports",
        "layout",
        "qr",
    }
)

# Live metadata patterns that mean the prompt still wants a field pack too.
_LIVE_FIELD_SIGNAL_RE = re.compile(
    r"\b("
    r"sla|due\s+date|deadline|status|stage|field|column|checkbox|selection|"
    r"warranty|inspection|checklist|compliance|expiry|expir|"
    r"amount|fee|rate|owner|assigned|responsible|notes?\s+on|"
    r"add\s+a\s+field|new\s+field"
    r")\b",
    re.I,
)

_GAP_SPECS: tuple[tuple[str, re.Pattern[str], str, str, str, tuple[dict[str, Any], ...]], ...] = (
    (
        "pdf_report",
        re.compile(
            r"\b(pdf|qweb|paperformat|report\s+template|invoice\s+pdf|"
            r"on\s+the\s+(pdf|report|print)|print(?:ed)?\s+(layout|template)|"
            r"delivery\s+(?:note|slip)|shipping\s+address)\b",
            re.I,
        ),
        "PDF / QWeb report",
        "Document layout and print templates are not live form fields.",
        "reports/<host>_document_layout.xml (Option A: module → sandbox → promote)",
        (),
    ),
    (
        "qr_on_document",
        re.compile(
            r"\b(qr\s*codes?|dynamic\s+qr|qr\s+on\s+(the\s+)?(pdf|invoice|report))\b",
            re.I,
        ),
        "QR on document",
        "QR rendering belongs on the QWeb/PDF report (or a binary field fed by Python).",
        "reports/<host>_qr.xml + optional models compute (Option A)",
        (
            {
                "name": "x_qr_payload",
                "ttype": "char",
                "string": "QR payload",
                "help": "Raw payload for a report QR. PDF wiring is Option A.",
            },
        ),
    ),
    (
        "click_to_pay",
        re.compile(
            r"\b(click[\s-]?to[\s-]?pay|pay\s+now|payment\s+button|pay\s+button|"
            r"payment\s+link|pay\s+link|online\s+payment\s+button)\b",
            re.I,
        ),
        "Click-to-pay on document",
        "Payment CTAs on PDFs need a payment URL + report/portal wiring — not a form char stub alone.",
        "reports/<host>_pay_button.xml + payment provider / portal (Option A)",
        (
            {
                "name": "x_payment_url",
                "ttype": "char",
                "string": "Payment link",
                "help": "URL for click-to-pay. Embed on the PDF via Option A report inherit.",
                "widget": "url",
            },
        ),
    ),
    (
        "website_controller",
        re.compile(
            r"\b(website\s+controller|http\s+route|public\s+endpoint|portal\s+page|"
            r"customer\s+portal\s+button)\b",
            re.I,
        ),
        "Website / portal controller",
        "HTTP routes and portal pages require an installable module.",
        "controllers/<feature>.py (Option A)",
        (),
    ),
    (
        "python_logic",
        re.compile(
            r"\b(python\s+compute|@api\.depends|cron\s+job|scheduled\s+action|"
            r"constraint|sql\s+constraint|override\s+create|override\s+write|"
            r"mark-?up(?:\s+line)?|withh?olding\s+tax|\bwht\b|"
            r"every\s+sale|percentage\s+of\s+every\s+sale|"
            r"external\s+api|pulls?\s+from.{0,40}api)\b",
            re.I,
        ),
        "Python / cron logic",
        "Computes, constraints, and crons are Option A — not live metadata.",
        "models/<host>_logic.py (Option A)",
        (),
    ),
    (
        "owl_widget",
        re.compile(
            r"\b(owl\s+widget|js\s+widget|client\s+action|kanban\s+js|"
            r"custom\s+frontend|dashboard\s+widget)\b",
            re.I,
        ),
        "OWL / JS widget",
        "Client-side widgets ship as module assets.",
        "static/src/<feature>.js (Option A)",
        (),
    ),
    (
        "email_template_html",
        re.compile(
            r"\b(mail\s+template\s+html|email\s+template\s+with\s+(qr|button|pdf)|"
            r"html\s+mail\s+template)\b",
            re.I,
        ),
        "Rich mail template",
        "Complex HTML mail templates with embedded QR/buttons are Option A.",
        "data/mail_template_<feature>.xml (Option A)",
        (),
    ),
    (
        "payment_provider",
        re.compile(
            r"\b(payment\s+provider|paystack|stripe\s+checkout|flutterwave|"
            r"payment\.provider|acquirer|card\s+checkout|dynamic\s+qr|"
            r"qr\s+and\s+card|checkout\s+on\s+(retainer\s+)?invoices?)\b",
            re.I,
        ),
        "Payment provider wiring",
        "Provider keys and checkout flows are Option A / Autopilot connectors — not form fields.",
        "data/payment_provider_stub.xml (Option A)",
        (
            {
                "name": "x_payment_url",
                "ttype": "char",
                "string": "Payment URL",
                "help": "Filled by Option A / portal; never store provider secrets here.",
            },
        ),
    ),
    (
        "webhook_inbound",
        re.compile(
            r"\b(webhook|inbound\s+http|callback\s+url|signed\s+webhook)\b",
            re.I,
        ),
        "Inbound webhook",
        "HTTP webhooks need a controller + auth token — Option A module.",
        "controllers/webhook_inbound.py (Option A)",
        (),
    ),
    (
        "report_paperformat",
        re.compile(
            r"\b(paperformat|paper\s+format|a4\s+landscape|custom\s+page\s+size)\b",
            re.I,
        ),
        "Report paperformat",
        "Paper formats are report XML (Option A), not live form fields.",
        "report/paperformat_<host>.xml (Option A)",
        (),
    ),
    (
        "pos_receipt_designer",
        re.compile(
            r"\b("
            r"pos\s+receipt|point of sale receipt|receipt designer|"
            r"receipt configurator|receipt design(?:s)?|thermal receipt|"
            r"receipt preview|live preview that matches"
            r")\b",
            re.I,
        ),
        "POS receipt designer",
        "Community POS receipts are OWL/QWeb on point_of_sale — not ir.ui.view "
        "and not a custom x_receipt residual. Visual designers, drag-drop columns, "
        "thermal mm widths, and cashier print selectors are Option A.",
        "static/src/app/screens/receipt_screen/ + xml inherit of OrderReceipt (Option A)",
        (),
    ),
    (
        "http_integration",
        re.compile(
            r"\b(external\s+api|https?://|urllib|public\s+http|"
            r"fetch(?:es)?\s+(?:from|rates)|pulls?\s+from\s+(?:the\s+)?(?:cbn|api))\b",
            re.I,
        ),
        "External HTTP integration",
        "Outbound HTTP belongs in an Option A module (sandbox → promote), not live metadata.",
        "models/<host>_http.py (Option A)",
        (),
    ),
    (
        "qweb_inherit",
        re.compile(
            r"\b(delivery\s+(?:note|slip)|shipping\s+address|"
            r"inherit\s+(?:the\s+)?(?:report|qweb)|remove.{0,40}from\s+the\s+(?:pdf|note|slip))\b",
            re.I,
        ),
        "QWeb report inherit",
        "Changing stock PDF/QWeb layout is an installable inherit — not View Designer.",
        "report/<host>_inherit.xml (Option A)",
        (),
    ),
)


def assess_capability_gaps(prompt: str) -> CapabilityAssessment:
    """Classify Option A surfaces in any vertical prompt."""
    from app.ai_operator_brief import intent_corpus

    raw = (prompt or "").strip()
    if not raw:
        return CapabilityAssessment()
    text = intent_corpus(raw)
    if not text:
        return CapabilityAssessment()

    gaps: list[CapabilityGap] = []
    covered: set[str] = set(CAPABILITY_NOISE_NOUNS)
    for gid, pattern, label, detail, path, stubs in _GAP_SPECS:
        if not has_positive_match(pattern, text):
            continue
        gaps.append(
            CapabilityGap(
                id=gid,
                label=label,
                detail=detail,
                option_a_path=path,
                stub_fields=stubs,
            )
        )
        covered |= {t for t in re.findall(r"[a-z]{3,}", gid.replace("_", " ")) if len(t) >= 3}
        covered |= {t for t in re.findall(r"[a-z]{3,}", label.lower()) if len(t) >= 3}

    if not gaps:
        return CapabilityAssessment()

    has_live = bool(_LIVE_FIELD_SIGNAL_RE.search(text))
    # Any Option A-only ask (PDF/QR/pay, website, OWL, Python, …) without a
    # clear metadata field signal → primary Option A (honest stubs or empty).
    primary = bool(gaps) and not has_live
    # Receipt “show/hide fields” is print layout, not ir.model.fields.
    if any(g.id == "pos_receipt_designer" for g in gaps):
        primary = True
    # QWeb inherit (delivery slip address, etc.) is never a field pack.
    if any(g.id == "qweb_inherit" for g in gaps):
        primary = True
    # Markup % + WHT on sales is Python even if clarify said "add fields".
    if any(g.id == "python_logic" for g in gaps) and re.search(
        r"(?i)mark-?up|withh?olding\s+tax|\bwht\b",
        text,
    ):
        primary = True
    if primary:
        covered |= {"qr", "payment", "pay", "link", "report", "template", "print", "invoice"}

    return CapabilityAssessment(
        gaps=gaps,
        primary_option_a=primary,
        covered_nouns=covered,
    )


def stub_fields_for_gaps(assessment: CapabilityAssessment) -> list[dict[str, Any]]:
    """Deduped honest stubs from assessed gaps."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for gap in assessment.gaps:
        for stub in gap.stub_fields:
            name = str(stub.get("name") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(dict(stub))
    return out


def stamp_capability_gaps(draft: dict[str, Any], prompt: str) -> list[str]:
    """Attach gaps + Option A blocks; strip junk when primary Option A."""
    notes: list[str] = []
    ir = draft.get("_generation_engine")
    if isinstance(ir, dict) and ir.get("capability") == "stock_reuse":
        draft.pop("_capability_gaps", None)
        draft["_capability_primary_option_a"] = False
        return notes
    assessment = assess_capability_gaps(prompt)
    if not assessment.gaps:
        draft.pop("_capability_gaps", None)
        return notes

    # Custom x_* residual + Pay/QR is mixed, not Option A-primary. Completeness
    # can be 10.0; Certification stays Reject until sandbox prove.
    has_residual = any(
        isinstance(m, dict)
        and str(m.get("mode") or "new") != "inherit"
        and str(m.get("model") or "").startswith("x_")
        for m in (draft.get("models") or [])
    )
    if has_residual and assessment.primary_option_a:
        assessment.primary_option_a = False
        notes.append(
            "capability: custom x_* residual present — mixed live+Option A, not primary"
        )

    draft["_capability_primary_option_a"] = assessment.primary_option_a
    draft["_noun_skips"] = sorted(
        set(draft.get("_noun_skips") or []) | assessment.covered_nouns
    )

    if isinstance(ir, dict) and ir.get("capability") == "option_a_authored":
        notes.append("capability: LLM authoring owns custom_code_blocks — skip scaffolds")
        return notes

    from app.ai_capability_option_a_scaffold import scaffold_blocks_for_gaps

    gap_ids = {g.id for g in assessment.gaps}
    scaffolds = scaffold_blocks_for_gaps(draft, gap_ids)
    blocks = [b for b in (draft.get("custom_code_blocks") or []) if isinstance(b, dict)]
    # Drop prior empty gap placeholders / older scaffolds (host may have changed
    # from calendar.event → account.move, so paths will not match).
    scaffold_paths = {
        str(b.get("source_file") or b.get("path") or "")
        for b in scaffolds
        if b.get("source_file") or b.get("path")
    }
    kept: list[dict[str, Any]] = []
    for b in blocks:
        key = str(b.get("source_file") or b.get("path") or "")
        if key and key in scaffold_paths:
            continue
        src = b.get("source")
        if src in {"capability_gap", "capability_gap_scaffold"}:
            if not b.get("content"):
                continue
            if _is_stale_document_extras_scaffold(key):
                continue
        kept.append(b)
    existing = {
        str(b.get("source_file") or b.get("path") or "")
        for b in kept
        if b.get("source_file") or b.get("path")
    }
    for block in scaffolds:
        key = str(block.get("source_file") or block.get("path") or "")
        if key and key in existing:
            continue
        kept.append(block)
        existing.add(key)
        notes.append(f"capability: Option A scaffold — {key}")
    for gap in assessment.gaps:
        notes.append(f"capability: Option A — {gap.id}")
    draft["custom_code_blocks"] = kept

    # Surface real scaffold paths on the gap stamp for the wizard Callout.
    path_by_gap = _scaffold_paths_by_gap(gap_ids, kept)
    draft["_capability_gaps"] = [
        {
            "id": g.id,
            "label": g.label,
            "detail": g.detail,
            "option_a_path": path_by_gap.get(g.id) or g.option_a_path,
        }
        for g in assessment.gaps
    ]

    if assessment.primary_option_a:
        notes.extend(_strip_junk_inherit_for_option_a(draft, assessment))
        notes.extend(_ensure_honest_stubs(draft, assessment))
        notes.extend(rebuild_extension_view_if_needed(draft))

    return notes


def _is_stale_document_extras_scaffold(path: str) -> bool:
    p = (path or "").replace("\\", "/")
    return (
        "_document_extras" in p
        or p.endswith("payment_provider_stub.xml")
        or "calendar_event_document_extras" in p
    )


def _scaffold_paths_by_gap(
    gap_ids: set[str], blocks: list[dict[str, Any]]
) -> dict[str, str]:
    """Map gap id → primary scaffold path for operator-facing Option A lists."""
    by_path = {
        str(b.get("source_file") or b.get("path") or ""): b
        for b in blocks
        if isinstance(b, dict)
    }
    out: dict[str, str] = {}
    report_xml = next(
        (p for p in by_path if p.endswith("_document_extras.xml")),
        "",
    )
    report_py = next(
        (p for p in by_path if p.endswith("_document_extras.py")),
        "",
    )
    if "pdf_report" in gap_ids and report_xml:
        out["pdf_report"] = report_xml
    if "qr_on_document" in gap_ids and report_xml:
        out["qr_on_document"] = report_xml
    if "click_to_pay" in gap_ids and report_py:
        out["click_to_pay"] = report_py
    if "website_controller" in gap_ids:
        out["website_controller"] = "controllers/document_extras_portal.py"
    if "owl_widget" in gap_ids:
        out["owl_widget"] = "static/src/document_extras_widget.js"
    if "python_logic" in gap_ids:
        py = next((p for p in by_path if p.endswith("_logic.py")), report_py)
        if py:
            out["python_logic"] = py
    if "email_template_html" in gap_ids:
        mail = next((p for p in by_path if "mail_template_" in p), "")
        if mail:
            out["email_template_html"] = mail
    if "payment_provider" in gap_ids:
        out["payment_provider"] = "data/payment_provider_stub.xml"
    if "webhook_inbound" in gap_ids:
        out["webhook_inbound"] = "controllers/webhook_inbound.py"
    if "report_paperformat" in gap_ids:
        pf = next((p for p in by_path if "paperformat_" in p), "")
        if pf:
            out["report_paperformat"] = pf
    return out


def _strip_junk_inherit_for_option_a(
    draft: dict[str, Any], assessment: CapabilityAssessment
) -> list[str]:
    """Drop padding fields invented from mechanism words (x_dynamic, x_notes, …)."""
    notes: list[str] = []
    keep_names = {str(f.get("name")) for f in stub_fields_for_gaps(assessment)}
    junk_leaves = {
        "dynamic",
        "notes",
        "active",
        "ref",
        "extension_note",
        "click",
        "button",
        "code",
        "pdf",
        "directly",
    }
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        if str(model.get("mode") or "new") != "inherit":
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        kept: list[dict[str, Any]] = []
        for f in fields:
            name = str(f.get("name") or "")
            leaf = name[2:] if name.startswith("x_") else name
            if name in keep_names:
                kept.append(f)
                continue
            if leaf in junk_leaves or leaf in CAPABILITY_NOISE_NOUNS:
                notes.append(f"capability: dropped junk inherit field {name}")
                continue
            kept.append(f)
        model["fields"] = kept
    return notes


def _ensure_honest_stubs(
    draft: dict[str, Any], assessment: CapabilityAssessment
) -> list[str]:
    notes: list[str] = []
    stubs = stub_fields_for_gaps(assessment)
    if not stubs:
        for model in draft.get("models") or []:
            if isinstance(model, dict) and str(model.get("mode")) == "inherit":
                if not (model.get("fields") or []):
                    notes.append("capability: no live form fields — report/Option A only")
        return notes

    from app.ai_capability_option_a_scaffold import (
        _ensure_host_inherit_and_stubs,
        host_model_from_draft,
    )

    host = host_model_from_draft(draft, prompt=str(draft.get("_user_prompt") or ""))
    _ensure_host_inherit_and_stubs(draft, host)
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or str(model.get("mode")) != "inherit":
            continue
        if str(model.get("model") or "") != host:
            continue
        existing = {
            str(f.get("name"))
            for f in (model.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        }
        for stub in stubs:
            name = str(stub.get("name") or "")
            if not name or name in existing:
                continue
            model.setdefault("fields", []).append(dict(stub))
            existing.add(name)
            notes.append(f"capability: honest stub {name}")
    return notes


def rebuild_extension_view_if_needed(draft: dict[str, Any]) -> list[str]:
    """Refresh or drop the inherit form extension after field surgery.

    Pay/QR/PDF extras live on the QWeb document, not as form chrome. When the
    brief is Option A–primary, do not inject a form group for stubs.
    """
    from app.ai_capability_option_a_scaffold import (
        _NEVER_PAY_QR_HOSTS,
        host_model_from_draft,
    )

    notes: list[str] = []
    host = host_model_from_draft(draft, prompt=str(draft.get("_user_prompt") or ""))
    inherit = None
    for model in draft.get("models") or []:
        if (
            isinstance(model, dict)
            and str(model.get("mode")) == "inherit"
            and str(model.get("model") or "") == host
        ):
            inherit = model
            break
    views = [v for v in (draft.get("views") or []) if isinstance(v, dict)]
    # Drop leftover form extensions on diary/HR/CRM hosts (Pay/QR never belong there).
    cleaned: list[dict[str, Any]] = []
    for v in views:
        vhost = str(v.get("model") or "")
        if (
            vhost in _NEVER_PAY_QR_HOSTS
            and str(v.get("mode")) == "extension"
            and str(v.get("type") or "") == "form"
            and str(v.get("source") or "") in {"capability_gap", "capability_gap_scaffold"}
        ):
            notes.append(f"capability: dropped form chrome on {vhost}")
            continue
        cleaned.append(v)
    views = cleaned

    stub_names = {"x_payment_url", "x_qr_payload"}
    primary = bool(draft.get("_capability_primary_option_a"))
    fields: list[dict[str, Any]] = []
    if inherit is not None and not primary:
        fields = [
            f
            for f in (inherit.get("fields") or [])
            if isinstance(f, dict)
            and f.get("name")
            and f.get("ttype") != "one2many"
            and str(f.get("name")) not in stub_names
        ]

    draft["views"] = [
        v
        for v in views
        if not (
            str(v.get("model")) == host
            and str(v.get("mode")) == "extension"
            and str(v.get("type") or "") == "form"
        )
    ]
    if primary:
        notes.append("capability: no form chrome for Option A PDF extras")
        return notes
    if inherit is None or not fields:
        notes.append("capability: removed empty form extension")
        return notes

    from app.ai_form_slots import apply_form_slots

    notes.extend(apply_form_slots(draft, prompt=str(draft.get("_user_prompt") or "")))
    if notes and notes[-1].startswith("slots:"):
        notes.append(f"capability: rebuilt extension view on {host}")
    return notes


__all__ = [
    "CAPABILITY_NOISE_NOUNS",
    "CapabilityAssessment",
    "CapabilityGap",
    "assess_capability_gaps",
    "rebuild_extension_view_if_needed",
    "stamp_capability_gaps",
    "stub_fields_for_gaps",
]
