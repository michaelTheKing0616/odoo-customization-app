"""Locked diagnosis IR — parse the brief before App Studio generates.

Deterministic classify/host/gaps win for routing. Must-do (constraints) is
LLM-first when intent LLM is enabled: the deterministic extractor is only a
seed/backstop. A scorer validates coverage, host consistency, and forbidden
invents; weak LLM output gets one repair retry, then a merge of the best of
det + LLM. Gold, refuse-clone, and an allowlisted host the regex already named
are never overridden.
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
        score = getattr(self, "_must_do_score", None)
        if isinstance(score, dict):
            data["_must_do_score"] = score
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
    # "under Delivery group" | "under the Delivery group" |
    # "under a small \"Delivery\" group" | "under a small Delivery group"
    r"(?i)\bunder\s+"
    r"(?:(?:the|a|an)\s+)?"
    r"(?:(?:small|tiny|new|compact|simple|short)\s+)?"
    r"[\"']?"
    r"([A-Za-z][\w /&-]{0,40}?)"
    r"[\"']?"
    r"\s+group\b"
)
_GROUP_TITLE_NOISE_RE = re.compile(
    r"(?i)^(small|tiny|new|compact|simple|short)\s+"
)
_LEADING_ARTICLE_RE = re.compile(r"(?i)^(a|an|the)\s+")
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

# Ops-extension briefs (reuse existing fields → wire into workflows).
_REUSE_EXISTING_RE = re.compile(
    r"(?i)\b(?:"
    r"already\s+persist|already\s+exist|already\s+on\s+res\.partner|"
    r"reuse|do\s+not\s+recreate|don'?t\s+recreate|"
    r"extend\s+so\s+they|matter\s+in\s+workflows?|"
    r"functional\s+extension|still\s+inherit[- ]only"
    r")\b"
)
_PICKING_SURFACE_RE = re.compile(
    r"(?i)\b(?:"
    r"pickings?|transfers?|smart\s+buttons?|"
    r"surface\s+preferred|preferred[- ]delivery\s+contacts?"
    r")\b"
)
_LIST_FILTER_RE = re.compile(
    r"(?i)\b(?:optional\s+)?filter\b.{0,48}\b(?:delivery|inventory)\b|"
    r"\b(?:delivery|inventory)\b.{0,48}\b(?:lists?|filter)\b|"
    r"\bfilter\s+on\s+(?:delivery|inventory)\b"
)
_LIGHT_AUTOMATION_RE = re.compile(
    r"(?i)\b(?:light\s+)?automation\b|"
    r"\bwhen\s+(?:the\s+)?(?:box|checkbox)\s+is\s+checked\b|"
    r"\bwhen\s+prefer(?:red)?(?:\s+for\s+delivery)?\s+is\s+checked\b"
)
_PREFER_DELIVERY_RE = re.compile(r"(?i)\bprefer(?:red)?\s+for\s+delivery\b")
_DELIVERY_NOTES_RE = re.compile(r"(?i)\bdelivery\s+notes?\b")


def _brief_ops_extension_themes(prompt: str) -> list[tuple[str, re.Pattern[str]]]:
    """Required Must-do themes for reuse→ops briefs (not plain field packs)."""
    text = (prompt or "").strip()
    if not text:
        return []
    themes: list[tuple[str, re.Pattern[str]]] = []
    # Only treat as ops-extension when wiring verbs appear (not S1 field-create).
    wiring = bool(
        _PICKING_SURFACE_RE.search(text)
        or _LIST_FILTER_RE.search(text)
        or _LIGHT_AUTOMATION_RE.search(text)
    )
    if not wiring:
        return []
    if _REUSE_EXISTING_RE.search(text) or _PREFER_DELIVERY_RE.search(text):
        themes.append(
            (
                "reuse existing fields",
                re.compile(r"(?i)\breuse|do\s+not\s+recreate|already\s+(?:persist|exist)"),
            )
        )
    if _PICKING_SURFACE_RE.search(text):
        themes.append(
            (
                "pickings/transfers surface",
                re.compile(r"(?i)\bpickings?|transfers?|smart\s+button|domain"),
            )
        )
    if _LIST_FILTER_RE.search(text):
        themes.append(
            (
                "Delivery/Inventory filter",
                re.compile(r"(?i)\bfilter\b"),
            )
        )
    if _LIGHT_AUTOMATION_RE.search(text):
        themes.append(
            (
                "light automation",
                re.compile(r"(?i)\bautomation\b|when\s+prefer"),
            )
        )
    return themes


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
        label = _LEADING_ARTICLE_RE.sub("", label).strip()
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
        gtitle = _LEADING_ARTICLE_RE.sub("", gm.group(1).strip()).strip()
        gtitle = _GROUP_TITLE_NOISE_RE.sub("", gtitle).strip()
        if gtitle:
            rows.append(f"Place under {gtitle} group")

    # Ops-extension: reuse existing Contact fields and wire into workflows.
    # Keep host on res.partner — never claim stock.picking as the form host.
    themes = _brief_ops_extension_themes(text)
    if themes:
        if any(label == "reuse existing fields" for label, _ in themes):
            names: list[str] = []
            if _PREFER_DELIVERY_RE.search(text):
                names.append("Prefer for delivery")
            if _DELIVERY_NOTES_RE.search(text):
                names.append("Delivery notes")
            if names:
                rows.append(
                    f"Reuse existing {' + '.join(names)} — do not recreate"
                )
            else:
                rows.append("Reuse existing Contact fields — do not recreate")
        if any(label == "pickings/transfers surface" for label, _ in themes):
            rows.append(
                "Surface preferred-delivery Contacts on pickings/transfers "
                "(domain or smart button)"
            )
        if any(label == "Delivery/Inventory filter" for label, _ in themes):
            rows.append(
                "Optional filter on Delivery/Inventory lists for preferred contacts"
            )
        if any(label == "light automation" for label, _ in themes):
            rows.append("Light automation when Prefer for delivery is checked")

    if _NO_NEW_APP_RE.search(text) or inherit:
        # Inherit already implies no new app; only add explicit phrasing when said or inherit.
        if _NO_NEW_APP_RE.search(text):
            rows.append("Do not create a new home-screen app")

    return _dedupe(rows)[:12]


_MUST_DO_PASS = 0.65
_FORBIDDEN_MUST_DO_RE = re.compile(
    r"(?i)\b(?:create(?:s|d)?\s+(?:an?\s+)?account\.tax|"
    r"new\s+account\.tax|"
    r"invent(?:ed)?\s+account\.tax|"
    r"env\[\s*['\"]account\.tax['\"]\s*\]\s*\.create|"
    r"clone\s+(?:the\s+)?(?:apps?\s+store|odoo\s+apps))\b"
)
_NEW_APP_CLAIM_RE = re.compile(
    r"(?i)\b(?:create|build|add)\s+(?:a\s+)?new\s+(?:home[- ]?screen\s+)?app\b"
)
_NO_NEW_APP_CLAIM_RE = re.compile(
    r"(?i)\b(?:do\s+not|don't|no)\s+(?:create\s+)?(?:a\s+)?new\s+(?:home[- ]?screen\s+)?app\b"
)


def _brief_named_entities(prompt: str) -> list[str]:
    """Field labels, groups, and explicit host phrases the brief names."""
    text = (prompt or "").strip()
    if not text:
        return []
    entities: list[str] = []
    for m in _CHECKBOX_FIELD_RE.finditer(text):
        label = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        if label:
            entities.append(label)
    for m in _TYPED_TEXT_FIELD_RE.finditer(text):
        label = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        label = _LEADING_ARTICLE_RE.sub("", label).strip()
        low = label.lower()
        if label and low not in {"add", "a", "an", "the", "new", "and", "or"}:
            if not low.startswith("checkbox"):
                entities.append(label)
    for m in _ADD_NAMED_FIELD_RE.finditer(text):
        label = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        low = label.lower()
        if (
            label
            and low not in {"checkbox", "boolean", "text", "field", "a field"}
            and low not in _PRONOUN_LABELS
            and len(label) >= 3
        ):
            entities.append(label)
    gm = _UNDER_GROUP_RE.search(text)
    if gm:
        gtitle = _LEADING_ARTICLE_RE.sub("", gm.group(1).strip()).strip()
        gtitle = _GROUP_TITLE_NOISE_RE.sub("", gtitle).strip()
        if gtitle:
            entities.append(gtitle)
    from app.ai_grain import HOST_ALIASES, HOST_LABELS

    low = text.lower()
    for phrase, model in sorted(HOST_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if phrase in low and len(phrase) >= 4:
            entities.append(HOST_LABELS.get(model, phrase))
            entities.append(model)
            break
    # Workflow / state words when present
    for token in ("draft", "confirm", "approved", "done", "cancel", "workflow", "stage"):
        if re.search(rf"(?i)\b{re.escape(token)}\b", text):
            entities.append(token)
    return _dedupe(entities)


def _brief_is_clear_for_must_do(
    prompt: str,
    *,
    host: str | None,
    inherit: bool,
) -> bool:
    """True when an empty Must-do list is a product failure (operator had enough detail)."""
    text = (prompt or "").strip()
    if len(text) < 24:
        return False
    entities = _brief_named_entities(text)
    if host and inherit and len(entities) >= 2:
        return True
    if len(entities) >= 3:
        return True
    if _NO_NEW_APP_RE.search(text) and (host or entities):
        return True
    return False


def score_must_do_constraints(
    prompt: str,
    constraints: list[str],
    *,
    host: str | None = None,
    inherit: bool = False,
    needs_module: bool = False,
) -> dict[str, Any]:
    """Score Must-do bullets vs the brief. Returns score 0..1, reasons, pass."""
    rows = [str(r).strip() for r in (constraints or []) if str(r).strip()]
    reasons: list[str] = []
    score = 1.0
    entities = _brief_named_entities(prompt)
    joined = " | ".join(rows).lower()
    clear = _brief_is_clear_for_must_do(prompt, host=host, inherit=inherit)

    if not rows:
        if clear:
            return {
                "score": 0.0,
                "reasons": ["empty Must do on a clear brief"],
                "pass": False,
            }
        return {"score": 0.35, "reasons": ["empty constraints"], "pass": False}

    # Entity coverage
    if entities:
        hits = 0
        for ent in entities:
            key = ent.lower()
            if len(key) < 3:
                continue
            if key in joined:
                hits += 1
            else:
                # soft match on significant tokens
                toks = [t for t in re.split(r"\W+", key) if len(t) >= 4]
                if toks and all(t in joined for t in toks[:2]):
                    hits += 1
        coverage = hits / max(len(entities), 1)
        if coverage < 0.4:
            score -= 0.4
            reasons.append(f"low entity coverage ({hits}/{len(entities)})")
        elif coverage < 0.7:
            score -= 0.2
            reasons.append(f"partial entity coverage ({hits}/{len(entities)})")
    elif clear and len(rows) < 2:
        score -= 0.25
        reasons.append("thin Must do for a clear brief")

    # Ops-extension theme coverage (pickings / filter / automation / reuse)
    ops_themes = _brief_ops_extension_themes(prompt)
    if ops_themes:
        missing = 0
        for label, pat in ops_themes:
            if not pat.search(joined):
                missing += 1
                reasons.append(f"missing Must-do for {label}")
        if missing:
            score -= min(0.55, 0.2 * missing)
        if clear and len(rows) < 4:
            score -= 0.2
            reasons.append("thin Must do for ops-extension brief")

    # Host consistency / host-steal
    if host:
        from app.ai_grain import HOST_LABELS

        label = HOST_LABELS.get(host, host).lower()
        host_l = host.lower()
        rivals = {
            "res.partner": ("stock.picking", "sale.order", "purchase.order"),
            "sale.order": ("purchase.order", "stock.picking"),
            "account.move": ("sale.order", "purchase.order"),
            "stock.picking": ("res.partner", "sale.order"),
            "purchase.order": ("sale.order",),
        }.get(host, ())
        for rival in rivals:
            rival_label = HOST_LABELS.get(rival, rival).lower()
            # Claim that Must-do lives on the rival host (not merely mentioning a field word).
            steal_pat = re.compile(
                rf"(?i)\b(?:on|host|inherit(?:s|ing)?)\s+{re.escape(rival_label)}\b|"
                rf"\b{re.escape(rival)}\b"
            )
            # Host-line claim always steals, even if the brief mentions the rival
            # for surface/filter wiring (ops-extension on Contacts).
            host_line_steal = re.compile(
                rf"(?i)(?:^|[|])\s*on\s+{re.escape(rival_label)}"
                rf"(?:\s*\(\s*{re.escape(rival)}\s*\))?\b|"
                rf"\bhost(?:ed)?\s+(?:on\s+)?{re.escape(rival)}\b"
            )
            if host_line_steal.search(joined):
                score -= 0.45
                reasons.append(f"host-steal: claimed {rival} while host is {host}")
                break
            if steal_pat.search(joined) and rival not in (prompt or "").lower():
                # Soft steal for rival tokens when the brief never named them
                score -= 0.45
                reasons.append(f"host-steal: claimed {rival} while host is {host}")
                break
        # Prefer seeing the locked host somewhere when inherit
        if inherit and host_l not in joined and label not in joined:
            score -= 0.15
            reasons.append(f"host {host} not reflected in Must do")

    # Forbidden invents
    for row in rows:
        if _FORBIDDEN_MUST_DO_RE.search(row):
            score -= 0.5
            reasons.append("forbidden invent (account.tax / Apps Store clone)")
            break
        if inherit and _NEW_APP_CLAIM_RE.search(row) and not _NO_NEW_APP_CLAIM_RE.search(row):
            score -= 0.35
            reasons.append("contradicts inherit: claims new home-screen app")
            break

    # Online honesty when Python / Option A
    if needs_module:
        honesty_bits = ("option a", "module", "sandbox", "promote", "not install this app", "zip")
        if not any(bit in joined for bit in honesty_bits):
            score -= 0.1
            reasons.append("Option A honesty missing (module/sandbox/Promote)")

    # Min length / quality
    short = [r for r in rows if len(r) < 8]
    if short and len(short) >= max(2, len(rows) // 2):
        score -= 0.2
        reasons.append("too many short / low-quality Must-do rows")
    if entities and len(entities) >= 3 and len(rows) < 2:
        score -= 0.25
        reasons.append("too few Must-do bullets for multi-req brief")
    if any(len(r) > 220 for r in rows):
        score -= 0.05
        reasons.append("overlong Must-do row")

    score = max(0.0, min(1.0, round(score, 3)))
    return {"score": score, "reasons": reasons, "pass": score >= _MUST_DO_PASS}


def _merge_must_do(
    det_rows: list[str],
    llm_rows: list[str],
    *,
    prompt: str,
    host: str | None,
    inherit: bool,
    needs_module: bool,
) -> list[str]:
    """Prefer LLM Must-do; backfill missing det seed bullets the LLM dropped."""
    llm = _dedupe([str(x).strip() for x in llm_rows if str(x).strip()])[:12]
    det = _dedupe([str(x).strip() for x in det_rows if str(x).strip()])[:12]
    if not llm:
        return det
    if not det:
        return llm
    merged = list(llm)
    joined = " | ".join(merged).lower()
    for row in det:
        key = row.lower()
        # Skip host-only det lines if LLM already named host/label
        if key.startswith("on ") and any(
            bit in joined for bit in ("on contacts", "res.partner", host or "\0")
        ):
            continue
        # Significant tokens from det row must appear somewhere
        toks = [t for t in re.split(r"\W+", key) if len(t) >= 4]
        if toks and all(t in joined for t in toks[:3]):
            continue
        if key not in joined:
            merged.append(row)
    merged = _dedupe(merged)[:12]
    # Pick the better of llm-only vs merged vs det-only by score
    candidates = [llm, merged, det]
    best = max(
        candidates,
        key=lambda rows: score_must_do_constraints(
            prompt, rows, host=host, inherit=inherit, needs_module=needs_module
        )["score"],
    )
    return best


def _parse_enrich_payload(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            blob = json.loads(raw)
            return blob if isinstance(blob, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _stamp_must_do_score(understanding: Understanding, score: dict[str, Any]) -> Understanding:
    object.__setattr__(understanding, "_must_do_score", {
        "score": float(score.get("score") or 0.0),
        "reasons": list(score.get("reasons") or []),
        "pass": bool(score.get("pass")),
    })
    return understanding



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
    """LLM-first Must-do whenever intent LLM is on (except refuse_clone).

    Deterministic constraints remain a seed/backstop; high confidence + host
    present must not skip enrich.
    """
    _ = prompt
    if not intent_llm_enabled():
        return False
    if det.capability == "refuse_clone":
        return False
    return True


def _must_do_system_prompt() -> str:
    return (
        "You diagnose an Odoo Community customization brief for App Studio. "
        "Reply JSON only. constraints are operator-facing Must-do bullets — "
        "as careful as a human reading the brief. Cover: (1) host/placement "
        "(model + form/group when named), (2) fields with types when stated, "
        "(3) workflows/states if implied, (4) live Install vs Option A module "
        "delivery when Python/QWeb/HTTP is needed, (5) non-goals, (6) Online "
        "honesty when Python cannot Install live (module zip → sandbox → human "
        "Promote). Infer beyond literal copy when the brief implies it, but "
        "never invent account.tax, never invent a fake x_* app when inheriting, "
        "never contradict inherit vs new home-screen tile. "
        "host_model must be an Odoo model like sale.order / res.partner when "
        "inheriting. Do not override gold or refuse_clone."
    )


def _must_do_user_prompt(
    prompt: str,
    det: Understanding,
    *,
    repair_reasons: list[str] | None = None,
) -> str:
    seed = det.constraints[:8]
    base = (
        f"Operator brief:\n{prompt}\n\n"
        f"Deterministic draft (seed/backstop only): capability={det.capability} "
        f"host={det.host_model} inherit={det.inherit_existing} "
        f"needs_module={det.needs_module} gold={det.gold_artifact_id} "
        f"grain={det.grain}\n"
        f"Deterministic Must-do seed: {json.dumps(seed)}\n"
        "Fill title, summary, constraints (Must-do), out_of_scope. "
        "constraints must be concrete Must-do bullets for this brief's complexity. "
        "You may set host_model only if missing. Do not change gold or refuse."
    )
    if repair_reasons:
        base += (
            "\n\nREPAIR PASS — previous Must-do scored low for: "
            + "; ".join(repair_reasons[:6])
            + ". Rewrite constraints to fix those gaps. Keep host consistent "
            "with the deterministic host when set. Stay compact (≤10 bullets)."
        )
    return base


def _llm_enrich(prompt: str, det: Understanding) -> Understanding:
    from app.llm_provider import LLMError, get_llm_provider_for_tier

    provider = get_llm_provider_for_tier("fast")
    if provider is None:
        scored = score_must_do_constraints(
            prompt,
            det.constraints,
            host=det.host_model,
            inherit=det.inherit_existing,
            needs_module=det.needs_module,
        )
        return _stamp_must_do_score(det, scored)

    def _call(*, repair_reasons: list[str] | None = None) -> dict[str, Any] | None:
        try:
            raw = provider.generate_json(
                _must_do_user_prompt(prompt, det, repair_reasons=repair_reasons),
                system=_must_do_system_prompt(),
                timeout_s=20.0,
                temperature=0.0,
                format_schema=_UNDERSTAND_SCHEMA,
            )
        except LLMError as exc:
            logger.info("Understanding LLM skipped: %s", exc)
            return None
        return _parse_enrich_payload(raw)

    parsed = _call()
    if not parsed:
        scored = score_must_do_constraints(
            prompt,
            det.constraints,
            host=det.host_model,
            inherit=det.inherit_existing,
            needs_module=det.needs_module,
        )
        return _stamp_must_do_score(det, scored)

    host = det.host_model
    coerced = _coerce_host_model(str(parsed.get("host_model") or ""))
    # Deterministic host wins. Never let LLM steal Contacts → stock.picking
    # when the brief named Contacts / res.partner.
    if coerced and not host:
        host = coerced
    elif (
        coerced
        and host
        and coerced != host
        and host == "res.partner"
        and coerced in {"stock.picking", "stock.picking.type"}
    ):
        coerced = None  # keep Contacts host

    llm_constraints: list[str] = []
    extra = parsed.get("constraints")
    if isinstance(extra, list):
        llm_constraints = [str(x).strip() for x in extra if str(x).strip()]

    constraints = _merge_must_do(
        det.constraints,
        llm_constraints,
        prompt=prompt,
        host=host,
        inherit=det.inherit_existing,
        needs_module=det.needs_module,
    )
    score = score_must_do_constraints(
        prompt,
        constraints,
        host=host,
        inherit=det.inherit_existing,
        needs_module=det.needs_module,
    )

    # One compact repair retry when weak
    if not score["pass"]:
        repaired = _call(repair_reasons=list(score.get("reasons") or []))
        if repaired:
            repair_extra = repaired.get("constraints")
            repair_rows = (
                [str(x).strip() for x in repair_extra if str(x).strip()]
                if isinstance(repair_extra, list)
                else []
            )
            if repair_rows:
                candidate = _merge_must_do(
                    det.constraints,
                    repair_rows,
                    prompt=prompt,
                    host=host,
                    inherit=det.inherit_existing,
                    needs_module=det.needs_module,
                )
                repair_score = score_must_do_constraints(
                    prompt,
                    candidate,
                    host=host,
                    inherit=det.inherit_existing,
                    needs_module=det.needs_module,
                )
                if repair_score["score"] >= score["score"]:
                    constraints = candidate
                    score = repair_score
                    # Prefer repaired title/summary when present
                    parsed = {**parsed, **{
                        k: repaired[k] for k in ("title", "summary", "out_of_scope", "confidence")
                        if k in repaired
                    }}

    # Final downgrade path: if still weak, prefer stronger of det vs current
    det_score = score_must_do_constraints(
        prompt,
        det.constraints,
        host=host or det.host_model,
        inherit=det.inherit_existing,
        needs_module=det.needs_module,
    )
    if det_score["score"] > score["score"]:
        constraints = list(det.constraints)
        score = det_score


    # Never ship empty Must-do when the brief is clear / field-pack+host.
    if not constraints and _brief_is_clear_for_must_do(
        prompt, host=host or det.host_model, inherit=det.inherit_existing
    ):
        constraints = list(det.constraints) or _brief_must_do_constraints(
            prompt, host=host or det.host_model, inherit=det.inherit_existing
        )
        score = score_must_do_constraints(
            prompt,
            constraints,
            host=host or det.host_model,
            inherit=det.inherit_existing,
            needs_module=det.needs_module,
        )

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
    # Soft-downgrade confidence when Must-do still fails after repair+merge
    if not score["pass"] and _brief_is_clear_for_must_do(
        prompt, host=host, inherit=inherit
    ):
        confidence = "low"

    result = Understanding(
        capability=det.capability,
        grain=det.grain,
        host_model=host,
        inherit_existing=inherit,
        needs_module=needs,
        gold_artifact_id=det.gold_artifact_id,
        title=title,
        summary=summary,
        constraints=_dedupe(constraints)[:12],
        out_of_scope=_dedupe(out)[:8],
        source="mixed" if (coerced or llm_constraints) else "deterministic",
        confidence=confidence,
    )
    return _stamp_must_do_score(result, score)


def build_understanding(prompt: str) -> Understanding:
    det = _deterministic_understanding(prompt)
    if _should_llm_enrich(prompt, det):
        return _llm_enrich(prompt, det)
    constraints = list(det.constraints)
    if not constraints and _brief_is_clear_for_must_do(
        prompt, host=det.host_model, inherit=det.inherit_existing
    ):
        constraints = _brief_must_do_constraints(
            prompt, host=det.host_model, inherit=det.inherit_existing
        )
        det = Understanding(
            capability=det.capability,
            grain=det.grain,
            host_model=det.host_model,
            inherit_existing=det.inherit_existing,
            needs_module=det.needs_module,
            gold_artifact_id=det.gold_artifact_id,
            title=det.title,
            summary=det.summary,
            constraints=constraints,
            out_of_scope=det.out_of_scope,
            source=det.source,
            confidence=det.confidence,
        )
    scored = score_must_do_constraints(
        prompt,
        det.constraints,
        host=det.host_model,
        inherit=det.inherit_existing,
        needs_module=det.needs_module,
    )
    return _stamp_must_do_score(det, scored)


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
    "score_must_do_constraints",
    "understanding_contradictions",
]
