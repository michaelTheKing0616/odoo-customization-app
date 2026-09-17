"""Locked diagnosis IR — parse the brief before App Studio generates.

Deterministic classify/host/gaps win. An optional fast LLM may fill summary,
constraints, and a missing host. It cannot override gold, refuse-clone, or
an allowlisted host the regex already named.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.ai_conversation.intent_llm import _coerce_host_model, intent_llm_enabled

logger = logging.getLogger(__name__)

UNDERSTANDING_KEY = "understanding_json"
DIAGNOSIS_KEY = "diagnosis"

_CLIENT_SOW_RE = re.compile(r"(?i)\b(the\s+client\s+wants|statement\s+of\s+work|sow)\b")
_MARKUP_RE = re.compile(r"(?i)mark-?up")
_WHT_RE = re.compile(r"(?i)withh?olding|\bwht\b")
_PCT_RANGE_RE = re.compile(r"(?i)10\s*%?\s*[-–to]+\s*25\s*%")

_UNDERSTAND_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "host_model": {"type": "string"},
        "inherit_existing": {"type": "boolean"},
        "needs_module": {"type": "boolean"},
        "capability": {"type": "string"},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "out_of_scope": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["high", "low"]},
    },
    "required": ["summary", "confidence"],
}


@dataclass
class Understanding:
    capability: str = "residual_app"
    grain: str = "full_app"
    host_model: str | None = None
    inherit_existing: bool = False
    needs_module: bool = False
    gold_artifact_id: str | None = None
    title: str = "Custom draft"
    summary: str = ""
    constraints: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    source: str = "deterministic"
    confidence: str = "high"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        from app.ai_grain import HOST_LABELS

        data["host_label"] = HOST_LABELS.get(self.host_model or "", self.host_model)
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> Understanding | None:
        if not raw or not isinstance(raw, dict):
            return None
        constraints = raw.get("constraints")
        out = raw.get("out_of_scope")
        return cls(
            capability=str(raw.get("capability") or "residual_app"),
            grain=str(raw.get("grain") or "full_app"),
            host_model=str(raw.get("host_model") or "").strip() or None,
            inherit_existing=bool(raw.get("inherit_existing")),
            needs_module=bool(raw.get("needs_module")),
            gold_artifact_id=str(raw.get("gold_artifact_id") or "").strip() or None,
            title=str(raw.get("title") or "Custom draft")[:80],
            summary=str(raw.get("summary") or "")[:400],
            constraints=[str(x) for x in constraints] if isinstance(constraints, list) else [],
            out_of_scope=[str(x) for x in out] if isinstance(out, list) else [],
            source=str(raw.get("source") or "deterministic"),
            confidence="low" if raw.get("confidence") == "low" else "high",
        )


def dump_understanding(answers: dict[str, str], understanding: Understanding) -> None:
    answers[UNDERSTANDING_KEY] = json.dumps(understanding.to_dict(), separators=(",", ":"))


def load_understanding(answers: dict[str, str] | None) -> Understanding | None:
    if not answers:
        return None
    raw = answers.get(UNDERSTANDING_KEY)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return Understanding.from_dict(parsed if isinstance(parsed, dict) else None)


def apply_understanding_edits(
    base: Understanding,
    edits: dict[str, Any] | None,
) -> Understanding:
    """Operator corrections on the diagnosis card — gold and refuse stay locked."""
    if not edits or not isinstance(edits, dict):
        return base
    if base.capability == "refuse_clone":
        return base
    title = str(edits.get("title") or base.title).strip()[:80] or base.title
    if title.lower().startswith("the client"):
        title = base.title
    summary = str(edits.get("summary") or base.summary).strip()[:400] or base.summary
    host = base.host_model
    if "host_model" in edits:
        raw = str(edits.get("host_model") or "").strip()
        if raw.lower() in {"", "none", "new"}:
            host = None
        else:
            host = _coerce_host_model(raw) or host
    inherit = (
        bool(edits["inherit_existing"]) if "inherit_existing" in edits else base.inherit_existing
    )
    needs = bool(edits["needs_module"]) if "needs_module" in edits else base.needs_module
    gold = base.gold_artifact_id
    if gold:
        needs = True
        inherit = True
    constraints = list(base.constraints)
    if isinstance(edits.get("constraints"), list):
        constraints = [str(x).strip() for x in edits["constraints"] if str(x).strip()][:12]
    note = str(edits.get("operator_note") or edits.get("correction") or "").strip()
    if note:
        constraints = _dedupe([*constraints, f"Operator: {note[:240]}"])
    out = list(base.out_of_scope)
    if isinstance(edits.get("out_of_scope"), list):
        out = [str(x).strip() for x in edits["out_of_scope"] if str(x).strip()][:8]
    if inherit:
        out = _dedupe([*out, "new home-screen app"])
    else:
        out = [row for row in out if row.lower() != "new home-screen app"]
    capability = base.capability
    grain = base.grain
    if not gold:
        if needs:
            capability = "option_a_authored"
            grain = "full_app"
        elif inherit:
            capability = "residual_app"
            grain = "field_pack"
        else:
            capability = "residual_app"
            grain = "full_app"
    return Understanding(
        capability=capability,
        grain=grain,
        host_model=host,
        inherit_existing=inherit,
        needs_module=needs,
        gold_artifact_id=gold,
        title=title,
        summary=summary,
        constraints=constraints,
        out_of_scope=out,
        source="operator",
        confidence="high",
    )


def diagnosis_confirmed(answers: dict[str, str] | None) -> bool:
    blob = str((answers or {}).get(DIAGNOSIS_KEY) or "").lower()
    return blob in {"confirm", "yes — build this", "yes - build this"}


def parse_locked_diagnosis(prompt: str) -> Understanding | None:
    """Rebuild IR from the locked block appended on confirm."""
    text = prompt or ""
    if "## Diagnosis (locked)" not in text:
        return None
    block = text.split("## Diagnosis (locked)", 1)[1]
    host = None
    m = re.search(r"(?im)^-\s*Host:\s*(\S+)", block)
    if m and m.group(1).lower() not in {"none", "—", "-"}:
        host = m.group(1).strip()
    cap_m = re.search(r"(?im)^-\s*Capability:\s*(\S+)", block)
    title_m = re.search(r"(?im)^-\s*Title:\s*(.+)$", block)
    gold_m = re.search(r"(?im)^-\s*Gold:\s*(\S+)", block)
    constraints = re.findall(r"(?im)^-\s*Constraint:\s*(.+)$", block)
    out = re.findall(r"(?im)^-\s*Out of scope:\s*(.+)$", block)
    inherit = bool(re.search(r"(?im)^-\s*Inherit existing form:\s*yes", block))
    needs = bool(re.search(r"(?im)^-\s*Needs module:\s*yes", block))
    return Understanding(
        capability=str(cap_m.group(1) if cap_m else "residual_app"),
        host_model=host,
        inherit_existing=inherit,
        needs_module=needs,
        gold_artifact_id=(
            gold_m.group(1).strip()
            if gold_m and gold_m.group(1).lower() not in {"none", "—"}
            else None
        ),
        title=(title_m.group(1).strip()[:80] if title_m else "Custom draft"),
        constraints=[c.strip() for c in constraints],
        out_of_scope=[o.strip() for o in out],
        source="locked",
        confidence="high",
    )


def append_locked_diagnosis(prompt: str, understanding: Understanding) -> str:
    lines = [
        prompt.rstrip(),
        "",
        "## Diagnosis (locked)",
        f"- Host: {understanding.host_model or 'none'}",
        f"- Inherit existing form: {'yes' if understanding.inherit_existing else 'no'}",
        f"- Needs module: {'yes' if understanding.needs_module else 'no'}",
        f"- Capability: {understanding.capability}",
        f"- Title: {understanding.title}",
        f"- Gold: {understanding.gold_artifact_id or 'none'}",
    ]
    for row in understanding.constraints:
        lines.append(f"- Constraint: {row}")
    for row in understanding.out_of_scope:
        lines.append(f"- Out of scope: {row}")
    return "\n".join(lines).strip()


def _dedupe(rows: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        key = row.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row.strip())
    return out


_NO_NEW_APP_RE = re.compile(
    r"(?i)\b(?:do\s+not\s+create\s+a\s+new\s+app|no\s+new\s+(?:home[- ]?screen\s+)?app|"
    r"not\s+a\s+new\s+(?:home[- ]?screen\s+)?app)\b"
)
_UNDER_GROUP_RE = re.compile(
    r"(?i)\bunder\s+(?:the\s+)?([A-Za-z][\w /&-]{0,40}?)\s+group\b"
)
_CHECKBOX_FIELD_RE = re.compile(
    r"(?i)\bcheckbox\s+[\"']?([^\"',.;]+?)[\"']?"
    r"(?=\s+and\b|\s+under\b|\s+on\b|,|\.|$)"
)
_TYPED_TEXT_FIELD_RE = re.compile(
    r"(?i)(?:\badd\b|\band\b|,)\s+([A-Z][\w /&-]{1,40}?)\s+text(?:\s+field)?\b"
)
_ADD_NAMED_FIELD_RE = re.compile(
    r"(?i)\badd\s+(?:a\s+|an\s+)?(?:checkbox\s+|boolean\s+|text\s+(?:field\s+)?)?[\"']?"
    r"((?-i:[A-Z])[^\"',.;]{1,60}?)[\"']?"
    r"(?=\s+(?:on|under|required|show|to|only)\b|,|\.|$)"
)
_PRONOUN_LABELS = frozenset(
    {"it", "this", "that", "them", "one", "field", "a field", "the field"}
)


def _brief_must_do_constraints(
    prompt: str,
    *,
    host: str | None,
    inherit: bool,
) -> list[str]:
    """Deterministic Must-do rows from a clear brief (fields, host, placement, no new app)."""
    text = (prompt or "").strip()
    if not text:
        return []
    rows: list[str] = []
    from app.ai_grain import HOST_LABELS

    if host and inherit:
        label = HOST_LABELS.get(host, host)
        rows.append(f"On {label} ({host})")

    for m in _CHECKBOX_FIELD_RE.finditer(text):
        label = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        if label:
            rows.append(f"Checkbox: {label}")

    for m in _TYPED_TEXT_FIELD_RE.finditer(text):
        label = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        low = label.lower()
        if not label or low in {"add", "a", "an", "the", "new", "and", "or"}:
            continue
        if low.startswith("checkbox"):
            continue
        rows.append(f"Text field: {label}")

    if not any(r.lower().startswith(("checkbox:", "text field:")) for r in rows):
        for m in _ADD_NAMED_FIELD_RE.finditer(text):
            label = re.sub(r"\s+", " ", m.group(1)).strip(" .")
            low = label.lower()
            if not label or low in {"checkbox", "boolean", "text", "field", "a field"}:
                continue
            if low in _PRONOUN_LABELS or len(label) < 3:
                continue
            rows.append(f"Field: {label}")

    gm = _UNDER_GROUP_RE.search(text)
    if gm:
        rows.append(f"Place under {gm.group(1).strip()} group")

    if _NO_NEW_APP_RE.search(text) or inherit:
        # Inherit already implies no new app; only add explicit phrasing when said or inherit.
        if _NO_NEW_APP_RE.search(text):
            rows.append("Do not create a new home-screen app")

    return _dedupe(rows)[:12]


def _deterministic_understanding(prompt: str) -> Understanding:
    from app.ai_generation_engine import classify_generation
    from app.ai_grain import HOST_LABELS, classify_grain, preferred_inherit_host
    from app.ai_option_a_author import _authored_display_name

    text = (prompt or "").strip()
    plan = classify_generation(text)
    grain = classify_grain(text)
    host = preferred_inherit_host(text)
    inherit = grain in {"field_pack", "feature_slice"}
    needs = plan.capability in {"option_a_authored", "option_a_standalone"}
    if needs:
        inherit = True
    constraints: list[str] = []
    out_of_scope: list[str] = ["new home-screen app"] if inherit or needs else []
    title = _authored_display_name(text, host) if needs else ""
    summary = (plan.honesty or "").strip()
    confidence = "high"

    if plan.gold_artifact_id == "currency_rate_cbn":
        title = "CBN currency rates"
        out_of_scope.extend(["new app tile", "x_fx model", "live Install of Python"])
        constraints.append("Module zip → sandbox prove → human Promote")
    elif plan.gold_artifact_id == "pos_receipt_options":
        title = "POS receipt options"
        out_of_scope.extend(["x_receipt app", "live thermal studio"])
    elif plan.gold_artifact_id == "invoice_qweb":
        title = "Invoice Pay + QR"
        host = host or "account.move"
    elif plan.capability == "option_a_authored":
        if _MARKUP_RE.search(text):
            constraints.append("Operator chooses markup % on the sale (10–25)")
            constraints.append("Selling price = cost + markup")
        if _WHT_RE.search(text):
            constraints.append("Withholding tax on the markup amount only")
            constraints.append("WHT on sales, not purchases")
            constraints.append("Use an existing tax xmlid — never create account.tax")
        if _PCT_RANGE_RE.search(text) and not any("10" in c and "25" in c for c in constraints):
            constraints.append("Markup percent is a range 10–25, chosen at entry")
        out_of_scope.extend(["live Install of Python", "invented account.tax"])
        if not title:
            title = _authored_display_name(text, host)
        if not summary:
            summary = (
                "Installable module on a stock form. Zip and sandbox stay locked "
                "until the authoring gate passes. Promote stays human."
            )
    elif plan.capability == "stock_reuse":
        title = "Stock Community apps"
        inherit = False
        needs = False
        summary = summary or "No custom residual. Job Autopilot is the done-bar."
        out_of_scope = ["new x_* document", "Install this app"]
    elif plan.capability == "refuse_clone":
        title = "Clone refused"
        summary = plan.honesty or "This platform does not clone Apps Store modules."
        inherit = False
        needs = False
        confidence = "high"
    elif grain == "field_pack" and host:
        title = title or f"{HOST_LABELS.get(host, host)} field"
        summary = summary or (
            f"Extra fields on the existing {HOST_LABELS.get(host, host)} form. "
            "Not a new home-screen app."
        )
        inherit = True
        constraints.extend(
            _brief_must_do_constraints(text, host=host, inherit=True)
        )
    else:
        title = title or (text.split(".")[0].strip()[:48] or "Custom draft")
        if len(title) > 48 or title.lower().startswith("the client"):
            title = "Custom draft"
        summary = summary or "A custom record people will open from the home screen."
        confidence = "low" if plan.capability == "residual_app" else "high"

    if not title:
        title = HOST_LABELS.get(host or "", "Custom draft")
    if not summary:
        summary = f"{title}."

    if plan.capability in {"option_a_authored", "option_a_standalone", "refuse_clone", "stock_reuse"}:
        confidence = "high"
    elif grain == "field_pack" and host:
        confidence = "high"

    if not constraints and inherit:
        constraints.extend(
            _brief_must_do_constraints(text, host=host, inherit=inherit)
        )

    return Understanding(
        capability=plan.capability,
        grain=grain,
        host_model=host,
        inherit_existing=inherit,
        needs_module=needs,
        gold_artifact_id=plan.gold_artifact_id,
        title=title[:80],
        summary=summary[:400],
        constraints=_dedupe(constraints),
        out_of_scope=_dedupe(out_of_scope),
        source="deterministic",
        confidence=confidence,
    )


def _should_llm_enrich(prompt: str, det: Understanding) -> bool:
    if not intent_llm_enabled():
        return False
    if det.capability == "refuse_clone":
        return False
    text = prompt or ""
    if len(text) >= 280 or _CLIENT_SOW_RE.search(text):
        return True
    if det.confidence == "low":
        return True
    if det.inherit_existing and not det.host_model:
        return True
    if det.inherit_existing and not det.constraints:
        return True
    return False


def _llm_enrich(prompt: str, det: Understanding) -> Understanding:
    from app.llm_provider import LLMError, get_llm_provider_for_tier

    provider = get_llm_provider_for_tier("fast")
    if provider is None:
        return det
    system = (
        "You diagnose an Odoo Community customization brief. Reply JSON only. "
        "Never invent a new home-screen app when the brief extends Sales, invoices, "
        "or a delivery slip. Never create account.tax. "
        "host_model must be an Odoo model like sale.order when inheriting a stock form."
    )
    user = (
        f"Operator brief:\n{prompt}\n\n"
        f"Deterministic draft: capability={det.capability} host={det.host_model} "
        f"inherit={det.inherit_existing} needs_module={det.needs_module} "
        f"gold={det.gold_artifact_id}\n"
        "Fill title, summary, constraints, out_of_scope. "
        "You may set host_model if missing. Do not change gold or refuse."
    )
    try:
        raw = provider.generate_json(
            user,
            system=system,
            timeout_s=20.0,
            temperature=0.0,
            format_schema=_UNDERSTAND_SCHEMA,
        )
    except LLMError as exc:
        logger.info("Understanding LLM skipped: %s", exc)
        return det
    parsed = raw if isinstance(raw, dict) else None
    if parsed is None and isinstance(raw, str):
        try:
            blob = json.loads(raw)
            parsed = blob if isinstance(blob, dict) else None
        except json.JSONDecodeError:
            parsed = None
    if not parsed:
        return det

    host = det.host_model
    coerced = _coerce_host_model(str(parsed.get("host_model") or ""))
    if coerced and not host:
        host = coerced
    constraints = list(det.constraints)
    extra = parsed.get("constraints")
    if isinstance(extra, list):
        constraints.extend(str(x) for x in extra if str(x).strip())
    out = list(det.out_of_scope)
    extra_out = parsed.get("out_of_scope")
    if isinstance(extra_out, list):
        out.extend(str(x) for x in extra_out if str(x).strip())
    title = str(parsed.get("title") or "").strip()[:80] or det.title
    if title.lower().startswith("the client"):
        title = det.title
    summary = str(parsed.get("summary") or "").strip()[:400] or det.summary
    inherit = det.inherit_existing or bool(parsed.get("inherit_existing"))
    needs = det.needs_module or bool(parsed.get("needs_module"))
    confidence = det.confidence
    if parsed.get("confidence") == "low" and det.confidence != "high":
        confidence = "low"
    return Understanding(
        capability=det.capability,
        grain=det.grain,
        host_model=host,
        inherit_existing=inherit,
        needs_module=needs,
        gold_artifact_id=det.gold_artifact_id,
        title=title,
        summary=summary,
        constraints=_dedupe(constraints),
        out_of_scope=_dedupe(out),
        source="mixed" if coerced or extra else "deterministic",
        confidence=confidence,
    )


def build_understanding(prompt: str) -> Understanding:
    det = _deterministic_understanding(prompt)
    if _should_llm_enrich(prompt, det):
        return _llm_enrich(prompt, det)
    return det


def diagnosis_clarification(understanding: Understanding) -> dict[str, Any]:
    from app.ai_grain import HOST_LABELS

    help_bits = [understanding.summary]
    if understanding.host_model:
        label = HOST_LABELS.get(understanding.host_model, understanding.host_model)
        help_bits.append(f"Lives on {label} ({understanding.host_model}).")
    if understanding.needs_module:
        help_bits.append("This is an Option A module — not Install this app.")
    elif understanding.inherit_existing:
        help_bits.append("Extra fields on a form people already use — not a new Apps tile.")
    return {
        "id": "diagnosis",
        "kind": "diagnosis",
        "merge_key": "diagnosis",
        "question": f"We'll build: {understanding.title}",
        "help": " ".join(bit for bit in help_bits if bit).strip(),
        "understanding": understanding.to_dict(),
        "host_choices": [
            {"id": model, "label": label} for model, label in HOST_LABELS.items()
        ],
        "options": [
            {"id": "confirm", "label": "Yes — build this"},
            {"id": "reject", "label": "That's not what I meant"},
        ],
        "default_id": "confirm",
    }


def inherit_hosts_from_draft(draft: dict[str, Any]) -> list[str]:
    hosts: list[str] = []
    for raw in draft.get("models") or []:
        if not isinstance(raw, dict):
            continue
        mid = str(raw.get("model") or "").strip()
        if not mid or mid.endswith("_line"):
            continue
        mode = str(raw.get("mode") or "")
        if mode == "inherit" or not mid.startswith("x_"):
            hosts.append(mid)
    return hosts


def primary_custom_model(draft: dict[str, Any]) -> str | None:
    for raw in draft.get("models") or []:
        if not isinstance(raw, dict):
            continue
        mid = str(raw.get("model") or "").strip()
        if mid.startswith("x_") and not mid.endswith("_line"):
            return mid
    return None


def understanding_contradictions(
    draft: dict[str, Any],
    understanding: Understanding,
) -> list[str]:
    """Compiler findings when the draft violates the locked diagnosis."""
    ir = draft.get("_generation_engine")
    cap = ""
    if isinstance(ir, dict):
        cap = str(ir.get("capability") or "")
    findings: list[str] = []
    if understanding.capability == "refuse_clone" and cap != "refuse_clone":
        findings.append("Locked as a refused Apps Store clone; draft is not refuse_clone.")
    option_a = {"option_a_authored", "option_a_standalone"}
    if understanding.needs_module and cap not in option_a and not draft.get("custom_code_blocks"):
        findings.append(
            f"Locked as Option A ({understanding.capability}); draft capability is {cap or 'empty'}."
        )
    if understanding.gold_artifact_id:
        gold = ir.get("gold_artifact_id") if isinstance(ir, dict) else None
        if gold != understanding.gold_artifact_id:
            findings.append(
                f"Locked gold {understanding.gold_artifact_id}; draft gold is {gold or 'none'}."
            )
    if understanding.inherit_existing and understanding.host_model:
        hosts = inherit_hosts_from_draft(draft)
        if hosts and understanding.host_model not in hosts:
            findings.append(
                f"Locked host {understanding.host_model}; draft inherits {', '.join(hosts)}."
            )
        if not hosts:
            invented = primary_custom_model(draft)
            if invented and understanding.capability in option_a | {"residual_app"}:
                if understanding.needs_module or understanding.inherit_existing:
                    findings.append(
                        f"Locked inherit {understanding.host_model}; draft invented {invented}."
                    )
    return findings


def attach_understanding(draft: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Stamp `_understanding` and surface contradictions so Install stays off."""
    u = parse_locked_diagnosis(prompt) or _deterministic_understanding(prompt)
    payload = u.to_dict()
    findings = understanding_contradictions(draft, u)
    payload["contradictions"] = findings
    draft["_understanding"] = payload
    live = draft.get("_live_apply")
    prior = list(live.get("findings") or []) if isinstance(live, dict) else []
    rows = [
        row
        for row in prior
        if not (isinstance(row, dict) and row.get("element") == "understanding")
    ]
    if findings:
        if not isinstance(live, dict):
            live = {"ready": False, "findings": []}
            draft["_live_apply"] = live
        for detail in findings:
            rows.append(
                {
                    "dimension": "surface",
                    "element": "understanding",
                    "detail": f"surface: {detail}",
                }
            )
        live["findings"] = rows
        live["ready"] = False
    elif isinstance(live, dict):
        live["findings"] = rows
    return draft


__all__ = [
    "DIAGNOSIS_KEY",
    "UNDERSTANDING_KEY",
    "Understanding",
    "append_locked_diagnosis",
    "attach_understanding",
    "build_understanding",
    "diagnosis_clarification",
    "diagnosis_confirmed",
    "dump_understanding",
    "load_understanding",
    "apply_understanding_edits",
    "parse_locked_diagnosis",
    "understanding_contradictions",
]
