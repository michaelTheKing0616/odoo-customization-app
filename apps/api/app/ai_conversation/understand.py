"""Locked diagnosis IR — parse the brief before App Studio generates.

Deterministic classify/host/gaps win for routing. Must-do (constraints) flows
through a hybrid constraint AST (``app.ai_constraint_ast``):

1. Deterministic floor — structural anchors always produce a complete baseline
   (``AI_INTENT_LLM=off`` tests must pass).
2. Structured fill — optional Flash/constrained JSON maps free prose → AST
   (strict ``CONSTRAINT_AST_SCHEMA``, expert-gated acceptance, process cache;
   behind ``AI_INTENT_LLM``; never required for correctness).
3. Merge — AST → Must-do bullets; enrich/merge never shrinks below the det floor.

Regex is an anchor inside det parse, not the only brain. Gold, refuse-clone,
and an allowlisted host the det path already named are never overridden.
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

# Process-local Flash enrich cache (prompt+seed → parsed JSON). Never required
# for correctness; AI_INTENT_LLM=off never hits this path.
_ENRICH_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_ENRICH_CACHE_TTL_S = 300.0
_ENRICH_CACHE_MAX = 64


def _enrich_cache_key(prompt: str, det: "Understanding") -> str:
    import hashlib

    seed = "|".join(
        [
            (prompt or "").strip().lower(),
            str(det.grain or ""),
            str(det.host_model or ""),
            str(bool(det.inherit_existing)),
            "|".join(det.constraints[:8]),
        ]
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:40]


def _enrich_cache_get(key: str) -> dict[str, Any] | None:
    import time

    row = _ENRICH_CACHE.get(key)
    if not row:
        return None
    ts, payload = row
    if time.monotonic() - ts > _ENRICH_CACHE_TTL_S:
        _ENRICH_CACHE.pop(key, None)
        return None
    return dict(payload)


def _enrich_cache_put(key: str, payload: dict[str, Any]) -> None:
    import time

    if len(_ENRICH_CACHE) >= _ENRICH_CACHE_MAX:
        # Drop oldest
        oldest = min(_ENRICH_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _ENRICH_CACHE.pop(oldest, None)
    _ENRICH_CACHE[key] = (time.monotonic(), dict(payload))


def clear_enrich_cache() -> None:
    """Test helper — wipe Flash enrich cache."""
    _ENRICH_CACHE.clear()


def _coerce_craft_list(raw) -> list[dict]:
    try:
        from app.ai_craft_smart_buttons import normalize_craft_rows

        return normalize_craft_rows(raw)
    except Exception:  # noqa: BLE001
        if not isinstance(raw, list):
            return []
        return [x for x in raw if isinstance(x, dict)][:2]


def _attach_craft_proposals(prompt: str, understanding: "Understanding") -> "Understanding":
    """Fill craft_proposals for Diagnosis Nice-to-have chips (all grains).

    ``propose_craft_smart_buttons`` itself skips Prefer/inherit-without-residual
    and empty-relation briefs — do not grain-gate here.
    """
    try:
        from app.ai_craft_smart_buttons import propose_craft_smart_buttons

        understanding.craft_proposals = propose_craft_smart_buttons(prompt, understanding)
    except Exception:  # noqa: BLE001
        understanding.craft_proposals = []
    return understanding


_MARKUP_RE = re.compile(r"(?i)mark-?up")
_WHT_RE = re.compile(r"(?i)withh?olding|\bwht\b")
_PCT_RANGE_RE = re.compile(r"(?i)10\s*%?\s*[-–to]+\s*25\s*%")


_OPTION_A_BRIEF_RE = re.compile(
    r"(?is)\b("
    r"python\b|qweb\b|owl\b|controller\b|http\s+route|cron\s+python|"
    r"pdf\s+report|report\s+template|module\s+zip|installable\s+module|"
    r"@override|api\.depends|models\.Model|website\s+controller|"
    r"webhook\b|compute\s*=\s*|constraint\s*=\s*"
    r")\b"
)


def brief_implies_option_a(prompt: str) -> bool:
    """True only when the brief itself asks for Python/QWeb/controllers/OWL/zip modules."""
    return bool(_OPTION_A_BRIEF_RE.search(prompt or ""))


def _force_live_fields_for_residual(understanding: "Understanding", prompt: str) -> "Understanding":
    """Residual full_app create/read/list/form → Live fields; never Option A from pack/LLM noise."""
    if understanding.grain != "full_app":
        return understanding
    if understanding.inherit_existing:
        return understanding
    if understanding.capability in {"option_a_authored", "option_a_standalone", "refuse_clone", "stock_reuse"}:
        return understanding
    if understanding.gold_artifact_id:
        return understanding
    if brief_implies_option_a(prompt):
        return understanding
    understanding.needs_module = False
    if understanding.capability not in {"residual_app", "stock_reuse", "refuse_clone"}:
        understanding.capability = "residual_app"
    return understanding


def _build_understand_schema() -> dict[str, Any]:
    """Flash enrich schema — embeds strict CONSTRAINT_AST_SCHEMA for any prompt."""
    schema: dict[str, Any] = {
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
    try:
        from app.ai_constraint_ast import CONSTRAINT_AST_SCHEMA

        schema["properties"]["constraint_ast"] = CONSTRAINT_AST_SCHEMA
    except Exception:  # noqa: BLE001
        schema["properties"]["constraint_ast"] = {"type": "object"}
    return schema


_UNDERSTAND_SCHEMA: dict[str, Any] = _build_understand_schema()



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
    craft_proposals: list[dict] = field(default_factory=list)
    craft_smart_buttons: list[dict] = field(default_factory=list)
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
            craft_proposals=_coerce_craft_list(raw.get("craft_proposals")),
            craft_smart_buttons=_coerce_craft_list(raw.get("craft_smart_buttons")),
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
    craft_proposals = list(base.craft_proposals or [])
    if isinstance(edits.get("craft_proposals"), list):
        craft_proposals = _coerce_craft_list(edits.get("craft_proposals"))
    craft_buttons = list(base.craft_smart_buttons or [])
    if "craft_smart_buttons" in edits:
        craft_buttons = _coerce_craft_list(edits.get("craft_smart_buttons"))
    elif isinstance(edits.get("nice_to_have"), list):
        wanted = {str(x).strip().lower() for x in edits["nice_to_have"] if str(x).strip()}
        pool = craft_proposals or base.craft_proposals or []
        craft_buttons = [
            row
            for row in pool
            if str(row.get("chip_label") or row.get("label") or "").strip().lower() in wanted
            or str(row.get("id") or "").strip().lower() in wanted
        ]
        craft_buttons = _coerce_craft_list(craft_buttons)

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
        craft_proposals=craft_proposals,
        craft_smart_buttons=craft_buttons,
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
    craft_raw = re.findall(
        r"(?im)^-\s*Craft smart button:\s*(.+?)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*$",
        block,
    )
    craft_buttons = _coerce_craft_list(
        [
            {
                "label": lab.strip(),
                "on_model": on.strip(),
                "related_model": rel.strip(),
                "relation_field": fld.strip(),
                "chip_label": f"«{lab.strip()}»",
                "default_on": True,
            }
            for lab, on, rel, fld in craft_raw
        ]
    )
    inherit = bool(re.search(r"(?im)^-\s*Inherit existing form:\s*yes", block))
    needs = bool(re.search(r"(?im)^-\s*Needs module:\s*yes", block))
    gold = (
        gold_m.group(1).strip()
        if gold_m and gold_m.group(1).lower() not in {"none", "—"}
        else None
    )
    if gold or needs:
        grain = "full_app"
    elif inherit:
        grain = "field_pack"
    else:
        grain = "full_app"
    return Understanding(
        capability=str(cap_m.group(1) if cap_m else "residual_app"),
        grain=grain,
        host_model=host,
        inherit_existing=inherit,
        needs_module=needs,
        gold_artifact_id=gold,
        title=(title_m.group(1).strip()[:80] if title_m else "Custom draft"),
        constraints=[c.strip() for c in constraints],
        out_of_scope=[o.strip() for o in out],
        craft_proposals=[],
        craft_smart_buttons=craft_buttons,
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
    for row in understanding.craft_smart_buttons or []:
        if not isinstance(row, dict):
            continue
        on_model = row.get("on_model") or row.get("host_model") or ""
        related = row.get("related_model") or row.get("residual_model") or ""
        rel_field = row.get("relation_field") or ""
        lines.append(
            "- Craft smart button: "
            f"{row.get('label') or 'Records'} | {on_model} | "
            f"{related} | {rel_field}"
        )
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
    r"(?i)\b(?:do\s+not|don't|never)\s+(?:create|invent|build)\s+(?:a\s+)?"
    r"(?:new\s+|parallel\s+)?(?:home[- ]?screen\s+)?(?:[A-Za-z][\w-]*\s+)?app\b|"
    r"\bno\s+new\s+(?:home[- ]?screen\s+)?app\b|"
    r"\bnot\s+a\s+new\s+(?:home[- ]?screen\s+)?app\b|"
    r"\bdo\s+not\s+invent\b|"
    r"\bprefer\s+(?:inherit|extend)\b"
)
_UNDER_GROUP_RE = re.compile(
    r"(?i)\bunder\s+(?:(?:the|a|an)\s+)?([A-Za-z][\w /&-]{0,40}?)\s+group\b"
)
_LEADING_ARTICLE_RE = re.compile(r"(?i)^(a|an|the)\s+")
_CHECKBOX_FIELD_RE = re.compile(
    r"(?i)\bcheckbox\s+[\"']?([^\"',.;]+?)[\"']?"
    r"(?=\s+and\b|\s+under\b|\s+on\b|,|\.|$)"
)
_TYPED_TEXT_FIELD_RE = re.compile(
    r"(?i)(?:\badd\b|\band\b|,)\s+([A-Z][\w /&-]{1,40}?)\s+text(?:\s+field)?\b"
)
# Legacy single-capture kept for scoring entity fallback; Prefer briefs use
# `_iter_add_field_labels` (conjunction + date-range aware) instead.
# `required` is ONLY a stop when NOT starting a Title-Case field name.
_ADD_NAMED_FIELD_RE = re.compile(
    r"(?i)\badd\s+(?:a\s+|an\s+)?(?:checkbox\s+|boolean\s+|text\s+(?:field\s+)?)?[\"']?"
    r"((?-i:[A-Z])[^\"',.;]{1,80}?)[\"']?"
    r"(?=\s+(?:on|under|show|to|only)\b|,|\.|$|"
    r"\s+required\b(?!\s+(?-i:[A-Z])))"
)
_PRONOUN_LABELS = frozenset(
    {"it", "this", "that", "them", "one", "field", "a field", "the field"}
)

# Add-clause body: stop before form/Prefer/Do-not/Show-hint sentences.
_ADD_CLAUSE_RE = re.compile(
    r"(?i)\badd\s+(?:a\s+|an\s+)?(?!checkbox\b|boolean\b)"
    r"(.+?)(?="
    r"\.\s*(?:On\s+the\s+form|Prefer|Do\s+not|Don't|Show\s+a\s+|When\b)|"
    r"\.\s*$|;\s*|\n|$)"
)
_DATE_RANGE_PAREN_RE = re.compile(
    r"(?i)\(\s*(?:a\s+)?"
    r"(?:date\s*range(?:\s+or\s+start\s*/\s*end(?:\s+dates?)?)?|"
    r"start\s*/\s*end(?:\s+dates?)?|"
    r"start\s+and\s+end(?:\s+dates?)?|"
    r"start\s+or\s+end(?:\s+dates?)?)"
    r"[^)]*\)\s*$"
)
_STATUS_HINT_RE = re.compile(
    r"(?i)\b(?:show|display)\s+(?:a\s+)?(?:status\s+hint|banner|alert|decoration|ribbon)"
    r"\s+when\s+(.+?)(?:\.|$)"
)
_FIELD_CHUNK_NOISE_RE = re.compile(
    r"(?i)^(a|an|the|add|checkbox|boolean|text(?:\s+field)?)\s+"
)
_TRAILING_AND_RE = re.compile(r"(?i)\s+\band\b\s*$")


def _split_conjunction_chunks(body: str) -> list[str]:
    """Split field lists on commas / 'and' while keeping parentheticals intact."""
    chunks: list[str] = []
    buf = ""
    depth = 0
    for ch in body or "":
        if ch == "(":
            depth += 1
            buf += ch
        elif ch == ")":
            depth = max(0, depth - 1)
            buf += ch
        elif ch == "," and depth == 0:
            if buf.strip():
                chunks.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        chunks.append(buf.strip())
    normalized: list[str] = []
    for chunk in chunks:
        if re.search(r"(?i)\band\b", chunk) and "(" not in chunk:
            parts = re.split(r"(?i)\s+and\s+", chunk)
            normalized.extend(p.strip(" .") for p in parts if p.strip())
        else:
            if re.match(r"(?i)^and\s+", chunk):
                chunk = re.sub(r"(?i)^and\s+", "", chunk).strip()
            # Still split "A and B (…)" when and is outside parens
            if re.search(r"(?i)\band\b", chunk):
                parts: list[str] = []
                part = ""
                d = 0
                i = 0
                low = chunk
                while i < len(low):
                    c = low[i]
                    if c == "(":
                        d += 1
                        part += c
                        i += 1
                    elif c == ")":
                        d = max(0, d - 1)
                        part += c
                        i += 1
                    elif (
                        d == 0
                        and low[i : i + 5].lower() == " and "
                    ):
                        if part.strip():
                            parts.append(part.strip())
                        part = ""
                        i += 5
                    else:
                        part += c
                        i += 1
                if part.strip():
                    parts.append(part.strip())
                if len(parts) > 1:
                    normalized.extend(parts)
                    continue
            normalized.append(chunk.strip(" ."))
    return [c for c in normalized if c]


def _expand_field_chunk(chunk: str) -> list[str]:
    """One add-list chunk → one or more field labels (date-range → start/end)."""
    raw = re.sub(r"\s+", " ", (chunk or "")).strip(" .")
    raw = _FIELD_CHUNK_NOISE_RE.sub("", raw).strip()
    raw = _TRAILING_AND_RE.sub("", raw).strip(" .")
    if not raw or len(raw) < 3:
        return []
    low = raw.lower()
    if low in _PRONOUN_LABELS or low in {
        "checkbox", "boolean", "text", "field", "a field", "the field"
    }:
        return []
    # Placement leftovers: "X under Delivery group" → X
    raw = re.split(r"(?i)\s+under\s+", raw, maxsplit=1)[0].strip()
    m = _DATE_RANGE_PAREN_RE.search(raw)
    if m:
        base = raw[: m.start()].strip(" .")
        base = re.sub(r"(?i)\s*\([^)]*\)\s*$", "", base).strip()
        base = _TRAILING_AND_RE.sub("", base).strip(" .")
        if not base or len(base) < 3:
            return []
        return [f"{base} start date", f"{base} end date"]
    # Drop non-range type parentheticals: Label (char) / Label (text)
    raw = re.sub(
        r"(?i)\s*\(\s*(?:char|text|html|boolean|checkbox|integer|int|float|"
        r"monetary|binary|image|date|datetime|many2one|selection)\s*\)\s*$",
        "",
        raw,
    ).strip(" .")
    if not raw or len(raw) < 3:
        return []
    return [raw]


def _iter_add_field_labels(text: str) -> list[str]:
    """All Prefer/field_pack labels after add — conjunction + date-range aware."""
    from app.ai_constraint_ast import iter_add_field_labels

    return iter_add_field_labels(text)


def _brief_ui_hint_constraints(text: str) -> list[str]:
    """Status hint / banner / alert prose → Must-do rows (not fields)."""
    rows: list[str] = []
    for m in _STATUS_HINT_RE.finditer(text or ""):
        cond = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        if cond and len(cond) >= 8:
            rows.append(f"Status hint when {cond}")
    return rows


def _brief_must_do_constraints(
    prompt: str,
    *,
    host: str | None,
    inherit: bool,
) -> list[str]:
    """Deterministic Must-do rows — AST floor (fields, host, placement, no new app)."""
    from app.ai_constraint_ast import ast_to_must_do, parse_det

    grain = "field_pack" if inherit else "full_app"
    return ast_to_must_do(parse_det(prompt, host=host, inherit=inherit, grain=grain))


_APP_NOUN_RE = re.compile(
    r"(?i)\b(?:build|create|make)\s+(?:an?\s+)?(?:(?:tiny|simple|small|new|mini)\s+)*"
    r"(.+?)\s+app\b"
    # "Dining Tables for our restaurant" / "Visitor Log: Name, …"
    r"|^([A-Z][\w][\w\s/-]{1,48}?)(?:\s+for\s+(?:our|the|a)\b|\s*[:—-])"
)
_MODEL_WITH_FIELDS_RE = re.compile(
    r"(?i)\bmodel\s+with\s+(.+?)(?:\.\s*(?:Simple|No\s+workflow|Menu)|;|\.|$)"
)
_MENU_UNDER_RE = re.compile(r"(?i)\bmenu\s+under\s+([A-Za-z][\w\s]{0,40})")
_CREATE_READ_ONLY_RE = re.compile(
    r"(?i)\b(?:no\s+workflow\s+beyond\s+)?create\s*/\s*read\b|create\s+and\s+read\s+only"
)
_LIST_FORM_RE = re.compile(r"(?i)\blist\s*(?:\+|and|&)\s*forms?\b")


# ORM field-type hints inside parentheticals — not Many2one targets.
_FIELD_TYPE_HINTS = frozenset(
    {
        "char",
        "text",
        "html",
        "boolean",
        "checkbox",
        "integer",
        "int",
        "float",
        "monetary",
        "binary",
        "image",
        "date",
        "datetime",
        "many2one",
        "many2many",
        "one2many",
        "selection",
    }
)


def _relation_target_display(target: str) -> str:
    """Display form for a stated Many2one target — no Contact/Employee special cases."""
    raw = (target or "").strip()
    if not raw:
        return raw
    if "." in raw:
        return raw  # technical model id (res.users, product.product)
    # Title-case words as declared; preserve existing internal caps (Employee).
    parts: list[str] = []
    for w in raw.split():
        if not w:
            continue
        if w.isupper() or (len(w) > 1 and any(c.islower() for c in w[1:])):
            parts.append(w[0].upper() + w[1:] if w[0].islower() else w)
        else:
            parts.append(w.title())
    return " ".join(parts) or raw


def _brief_full_app_must_do(prompt: str) -> list[str]:
    """Structural Must-do for residual full_app — AST floor (any similarly shaped brief)."""
    from app.ai_constraint_ast import ast_to_must_do, parse_det

    return ast_to_must_do(parse_det(prompt, host=None, inherit=False, grain="full_app"))




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
    # Prefer conjunction + date-range aware labels (same as Must-do seed).
    for label in _iter_add_field_labels(text):
        low = label.lower()
        if (
            label
            and low not in {"checkbox", "boolean", "text", "field", "a field"}
            and low not in _PRONOUN_LABELS
            and len(label) >= 3
        ):
            entities.append(label)
    # Status-hint / Documents conditions — score coverage for Prefer briefs.
    for row in _brief_ui_hint_constraints(text):
        entities.append(row)
        if re.search(r"(?i)\bdocuments?\b", row):
            entities.append("Documents")
        if re.search(r"(?i)\bconfirm", row):
            entities.append("confirm")
    gm = _UNDER_GROUP_RE.search(text)
    if gm:
        gtitle = _LEADING_ARTICLE_RE.sub("", gm.group(1).strip()).strip()
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
            if steal_pat.search(joined) and rival not in (prompt or "").lower():
                # Allow rival only if brief also named it
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
    """Union LLM Must-do with deterministic floor — never drop det seed bullets.

    Hardened via ``ai_constraint_ast.merge_must_do``: det floor always wins
    over the cap; LLM extras fill remaining slots only.
    """
    _ = (prompt, host, inherit, needs_module)
    from app.ai_constraint_ast import merge_must_do as _ast_merge

    return _ast_merge(det_rows, llm_rows)


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
    # Residual full_app: never inherit a stock form stolen from Purpose/Host fields.
    if (
        grain == "full_app"
        and plan.capability not in {"option_a_authored", "option_a_standalone", "refuse_clone"}
        and not needs
    ):
        host = None
        inherit = False
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
    elif inherit and host and grain in {"field_pack", "feature_slice"}:
        # Prefer/inherit packs (any host): Diagnosis Name from AST fields — not
        # thin «Sales field» / «Contacts field» host slugs.
        from app.ai_constraint_ast import parse_det, prefer_pack_title

        host_label = HOST_LABELS.get(host, host)
        ast = parse_det(text, host=host, inherit=True, grain=grain)
        title = title or prefer_pack_title(
            ast, host=host, host_label=host_label
        )
        summary = summary or (
            f"Extra fields on the existing {host_label} form. "
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
    elif inherit and host and grain in {"field_pack", "feature_slice"}:
        confidence = "high"

    if not constraints and inherit:
        constraints.extend(
            _brief_must_do_constraints(text, host=host, inherit=inherit)
        )
    if (
        not constraints
        and grain == "full_app"
        and not inherit
        and plan.capability == "residual_app"
    ):
        constraints.extend(_brief_full_app_must_do(text))

    # Prefer a short residual title for full_app (Visitor Log, not the whole brief).
    if grain == "full_app" and not inherit and not needs:
        app_m = _APP_NOUN_RE.search(text)
        if app_m:
            nice = re.sub(r"\s+", " ", (app_m.group(1) or app_m.group(2) or '')).strip(" .:,-")
            nice = re.sub(r"(?i)^(a|an|the)\s+", "", nice).strip()
            if nice and len(nice) <= 48:
                title = nice.title() if nice.islower() or nice.lower() == nice else nice

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
        "Reply JSON only. Prefer filling constraint_ast "
        "(fields[{label,ttype,relation?}], host, hints[], non_goals[], grain) "
        "plus operator-facing constraints bullets. Cover: (1) host/placement "
        "(model + form/group when named), (2) fields with types when stated, "
        "(3) workflows/states if implied, (4) live Install vs Option A module "
        "delivery when Python/QWeb/HTTP is needed, (5) non-goals, (6) Online "
        "honesty when Python cannot Install live (module zip → sandbox → human "
        "Promote). Prefer Date over Datetime unless time is stated/implied. "
        "Infer beyond literal copy when the brief implies it, but "
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
        "Fill title, summary, constraints (Must-do), out_of_scope, and when "
        "possible constraint_ast "
        "(fields[{label,ttype,relation?}], host, hints[], non_goals[], grain). "
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

    cache_key = _enrich_cache_key(prompt, det)

    def _call(*, repair_reasons: list[str] | None = None) -> dict[str, Any] | None:
        # Cache only the primary (non-repair) fill — repairs are one-shot.
        if not repair_reasons:
            hit = _enrich_cache_get(cache_key)
            if hit is not None:
                return hit
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
        parsed_local = _parse_enrich_payload(raw)
        if parsed_local and not repair_reasons:
            _enrich_cache_put(cache_key, parsed_local)
        return parsed_local

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
    # Residual full_app already cleared stock hosts (calendar.event / hr.employee…).
    # LLM must not re-inject alias noise into Contract host_model.
    residual_full = (
        det.grain == "full_app"
        and not det.inherit_existing
        and not det.needs_module
        and det.capability
        not in {"option_a_authored", "option_a_standalone", "refuse_clone"}
    )
    if coerced and not host and not residual_full:
        host = coerced
    if residual_full:
        host = None

    llm_constraints: list[str] = []
    extra = parsed.get("constraints")
    if isinstance(extra, list):
        llm_constraints = [str(x).strip() for x in extra if str(x).strip()]

    # Structured fill: optional constraint_ast → bullets on the LLM side only.
    # Expert gate rejects soft/empty fills; det floor stays ``det.constraints``.
    # Merge never shrinks that floor.
    try:
        from app.ai_constraint_ast import (
            ast_to_must_do,
            expert_gate_llm_ast,
            parse_det,
            parse_llm,
        )

        llm_ast = parse_llm(parsed)
        det_ast = parse_det(
            prompt,
            host=det.host_model,
            inherit=det.inherit_existing,
            grain=det.grain,
        )
        llm_ast = expert_gate_llm_ast(det_ast, llm_ast)
        if llm_ast is not None:
            llm_constraints = _dedupe(ast_to_must_do(llm_ast) + llm_constraints)
    except Exception:  # noqa: BLE001
        pass

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
            # Repair Flash may also emit constraint_ast — expert-gate + floor.
            try:
                from app.ai_constraint_ast import (
                    ast_to_must_do,
                    expert_gate_llm_ast,
                    parse_det,
                    parse_llm,
                )

                repair_ast = expert_gate_llm_ast(
                    parse_det(
                        prompt,
                        host=det.host_model,
                        inherit=det.inherit_existing,
                        grain=det.grain,
                    ),
                    parse_llm(repaired),
                )
                if repair_ast is not None:
                    repair_rows = _dedupe(ast_to_must_do(repair_ast) + repair_rows)
            except Exception:  # noqa: BLE001
                pass
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

    out = list(det.out_of_scope)
    extra_out = parsed.get("out_of_scope")
    if isinstance(extra_out, list):
        out.extend(str(x) for x in extra_out if str(x).strip())
    title = str(parsed.get("title") or "").strip()[:80] or det.title
    if title.lower().startswith("the client"):
        title = det.title
    # Prefer/inherit: keep AST-derived Diagnosis Name over thin host slugs
    # («Sales field», «Contacts field pack») from LLM paraphrases.
    if (
        det.inherit_existing
        and det.grain in {"field_pack", "feature_slice"}
        and det.title
        and re.search(r"(?i)^[\w.&/\s-]+ field(?:\s*pack)?$", title)
        and (
            "+" in det.title
            or not re.search(r"(?i)^[\w.&/\s-]+ fields?$", det.title)
        )
    ):
        title = det.title
    summary = str(parsed.get("summary") or "").strip()[:400] or det.summary
    inherit = det.inherit_existing or bool(parsed.get("inherit_existing"))
    # Option A only from det (capability/gold) or an explicit Option A brief — never
    # from LLM boolean noise or pack depends keywords.
    needs = det.needs_module
    if brief_implies_option_a(prompt) and bool(parsed.get("needs_module")):
        needs = True
    # Residual full_app Contract: app name title, no stock host, no inherit, Live fields.
    if residual_full:
        host = None
        inherit = False
        if not brief_implies_option_a(prompt):
            needs = False
        # Keep deterministic app title — reject "{model} field pack" LLM titles.
        if (
            re.search(r"(?i)\bfield\s*pack\b", title)
            or (coerced and coerced in title)
            or title.lower().endswith(" field")
        ):
            title = det.title
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
        understanding = _llm_enrich(prompt, det)
    else:
        scored = score_must_do_constraints(
            prompt,
            det.constraints,
            host=det.host_model,
            inherit=det.inherit_existing,
            needs_module=det.needs_module,
        )
        understanding = _stamp_must_do_score(det, scored)
    understanding = _force_live_fields_for_residual(understanding, prompt)
    return _attach_craft_proposals(prompt, understanding)


def diagnosis_clarification(understanding: Understanding) -> dict[str, Any]:
    understanding = _force_live_fields_for_residual(understanding, "")
    if not understanding.craft_proposals:
        _attach_craft_proposals("", understanding)
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
        "nice_to_have": [
            str(p.get("chip_label") or p.get("label") or "")
            for p in (understanding.craft_proposals or [])
            if isinstance(p, dict) and p.get("default_on", True)
        ],
        "craft_proposals": list(understanding.craft_proposals or []),
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
    # Contract ↔ draft identity: title/grain must match residual display_name.
    draft_title = str(draft.get("display_name") or "").strip()
    locked_title = str(understanding.title or "").strip()
    draft_grain = str(draft.get("grain") or understanding.grain or "full_app")
    if (
        draft_title
        and locked_title
        and draft_title.lower() != locked_title.lower()
        and not understanding.inherit_existing
        and draft_grain == "full_app"
    ):
        findings.append(
            f"Contract title «{locked_title}» does not match draft «{draft_title}»."
        )
    # Only flag residual↔inherit grain flips (Visitor full_app vs Prefer field_pack), not
    # benign defaults where one side still says full_app while the other is field_pack mid-stamp.
    if (
        understanding.grain
        and draft.get("grain")
        and str(understanding.grain) != str(draft.get("grain"))
        and {"full_app", "field_pack"} <= {str(understanding.grain), str(draft.get("grain"))}
        and (
            understanding.inherit_existing
            != any(
                isinstance(m, dict) and str(m.get("mode") or "") == "inherit"
                for m in (draft.get("models") or [])
            )
        )
    ):
        findings.append(
            f"Contract grain {understanding.grain} does not match draft grain {draft.get('grain')}."
        )
    return findings


def reconcile_contract_with_draft(
    draft: dict[str, Any],
    understanding: Understanding,
    *,
    prompt: str = "",
    prefer_locked: bool = False,
) -> Understanding:
    """Align Contract ↔ draft identity without letting pack bleed wipe Diagnosis.

    When ``prefer_locked`` (Diagnosis-confirmed session IR), keep Contract and let
    ``enforce_residual_draft_identity`` rebuild the draft. Otherwise a stale locked
    block left in the prompt under a new residual brief may follow draft.display_name.
    """
    draft_title = str(draft.get("display_name") or "").strip()
    draft_grain = str(draft.get("grain") or "full_app")
    locked_title = str(understanding.title or "").strip()
    if not draft_title and not locked_title:
        return understanding
    title_mismatch = bool(
        locked_title and draft_title and draft_title.lower() != locked_title.lower()
    )
    grain_mismatch = bool(
        understanding.grain and draft_grain and understanding.grain != draft_grain
    )
    residual_locked = (
        not understanding.inherit_existing
        and understanding.grain == "full_app"
        and not understanding.needs_module
    )
    # Diagnosis-confirmed residual Contract wins — do not stamp pack title onto Contract.
    if prefer_locked and residual_locked and locked_title:
        return understanding
    # Residual full_app with pack stamp / stale session IR in the prompt chrome.
    if (
        draft_grain == "full_app"
        and residual_locked
        and (title_mismatch or grain_mismatch)
        and draft_title
    ):
        rebuilt = Understanding(
            capability="residual_app",
            grain="full_app",
            host_model=None,
            inherit_existing=False,
            needs_module=False,
            gold_artifact_id=understanding.gold_artifact_id,
            title=draft_title[:80],
            summary=f"New app tile «{draft_title}» — rebuilt to match draft identity.",
            constraints=list(understanding.constraints or []),
            out_of_scope=list(understanding.out_of_scope or []),
            craft_proposals=list(understanding.craft_proposals or []),
            craft_smart_buttons=list(understanding.craft_smart_buttons or []),
            source="reconciled_draft",
            confidence="high",
        )
        return rebuilt
    # Prefer inherit field_pack: keep host, sync title from draft when empty.
    if understanding.inherit_existing and not locked_title and draft_title:
        understanding.title = draft_title[:80]
    return understanding


def attach_understanding(
    draft: dict[str, Any],
    prompt: str,
    *,
    locked: Understanding | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stamp `_understanding` and surface contradictions so Install stays off.

    Reconcile Contract ↔ draft identity before findings so stale Visitor Log IR
    cannot sit on a Restaurant (or other) residual draft.

    Session-IR continuity: when Diagnosis confirm dumped ``craft_smart_buttons``
    into session understanding, pass that as ``locked`` (or leave it on the draft)
    so Generate does not rebuild from prompt alone and zero craft. Preference order
    for the locked Contract: explicit ``locked`` → parse locked block → prior draft
    ``_understanding`` → deterministic. Craft list is taken from the first source
    that carries one (session wins over a craft-empty reparse).
    """
    session_u = locked if isinstance(locked, Understanding) else Understanding.from_dict(
        locked if isinstance(locked, dict) else None
    )
    parsed = parse_locked_diagnosis(prompt)
    prior_raw = draft.get("_understanding")
    prior = (
        Understanding.from_dict(prior_raw)
        if isinstance(prior_raw, dict)
        else None
    )

    if session_u is not None:
        u = session_u
    elif parsed is not None:
        u = parsed
    elif prior is not None:
        u = prior
    else:
        u = _deterministic_understanding(prompt)

    # Preserve Diagnosis-confirmed craft across rebuild/reconcile.
    # Session locked understanding is authoritative (empty list = chips removed).
    if session_u is not None:
        u.craft_smart_buttons = list(session_u.craft_smart_buttons or [])
    elif not list(u.craft_smart_buttons or []):
        for donor in (prior, parsed):
            if donor is not None and list(donor.craft_smart_buttons or []):
                u.craft_smart_buttons = list(donor.craft_smart_buttons or [])
                break

    prefer_locked = session_u is not None
    try:
        from app.ai_residual_identity import (
            enforce_residual_draft_identity,
            locked_contract_should_win,
        )

        if prefer_locked and locked_contract_should_win(u.to_dict()):
            enforce_residual_draft_identity(
                draft,
                prompt=prompt,
                locked=u.to_dict(),
                prefer_locked=True,
            )
        else:
            # Prompt residual noun wins over stale locked chrome in the prompt text.
            enforce_residual_draft_identity(
                draft,
                prompt=prompt,
                locked=u.to_dict(),
                prefer_locked=False,
            )
    except Exception:  # noqa: BLE001
        pass
    u = reconcile_contract_with_draft(
        draft, u, prompt=prompt, prefer_locked=prefer_locked
    )
    # Keep draft grain aligned with Contract for residual full_app.
    # Do not let LLM/pack overwrite locked full_app → feature_slice/field_pack.
    if u.grain == "full_app" and not u.inherit_existing:
        draft["grain"] = "full_app"
        engine = draft.get("_generation_engine")
        if isinstance(engine, dict) and str(engine.get("grain") or "") in {
            "field_pack",
            "feature_slice",
        }:
            engine = dict(engine)
            engine["grain"] = "full_app"
            draft["_generation_engine"] = engine
        if draft.get("_component") and any(
            isinstance(m, dict)
            and str(m.get("model") or "").startswith("x_")
            and str(m.get("mode") or "new") != "inherit"
            for m in (draft.get("models") or [])
        ):
            draft.pop("_component", None)
        if prefer_locked and u.title:
            draft["display_name"] = u.title
        elif u.title and not draft.get("display_name"):
            draft["display_name"] = u.title
        elif draft.get("display_name") and u.source == "reconciled_draft":
            u.title = str(draft.get("display_name"))[:80]
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
    "reconcile_contract_with_draft",
    "build_understanding",
    "clear_enrich_cache",
    "diagnosis_clarification",
    "diagnosis_confirmed",
    "dump_understanding",
    "load_understanding",
    "apply_understanding_edits",
    "brief_implies_option_a",
    "parse_locked_diagnosis",
    "score_must_do_constraints",
    "understanding_contradictions",
]
