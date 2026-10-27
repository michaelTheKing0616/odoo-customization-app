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

import contextvars
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from app.ai_conversation.intent_llm import (
    _coerce_host_model,
    admit_host_from_packet,
    current_schema_packet,
    intent_llm_enabled,
)
from app.live_schema_context import (
    SchemaPacket,
    drop_unknown_technical_names,
    field_in_packet,
    prepend_schema_packet,
    resolve_form_anchor,
)

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
    """Test helper — wipe Flash enrich + app design caches."""
    _ENRICH_CACHE.clear()
    from app.ai_conversation.app_design import clear_design_cache

    clear_design_cache()


def _coerce_craft_list(raw) -> list[dict]:
    try:
        from app.ai_craft_smart_buttons import normalize_craft_rows

        return normalize_craft_rows(raw)
    except Exception:  # noqa: BLE001
        if not isinstance(raw, list):
            return []
        return [x for x in raw if isinstance(x, dict)][:2]


# Operator-visible craft opt-ins (handoff §3.3 / live-schema PR-C). Defaults off.
APPROVED_CRAFT_KEYS: tuple[str, ...] = (
    "company_scoping",
    "money_slots",
    "date_slots",
    "purchase_link",
    "partner_links",
    "datetime_over_date",
    "depth_seeds",
)


def default_approved_craft() -> dict[str, bool]:
    return {key: False for key in APPROVED_CRAFT_KEYS}


def coerce_approved_craft(raw: Any) -> dict[str, bool]:
    """Normalize approved_craft — unknown keys dropped; missing keys default False."""
    out = default_approved_craft()
    if isinstance(raw, dict):
        for key in APPROVED_CRAFT_KEYS:
            if key in raw:
                out[key] = bool(raw[key])
    return out


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
    """Residual full_app create/read/list/form → Live fields; never custom code from pack/LLM noise."""
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
    approved_craft: dict[str, bool] = field(default_factory=default_approved_craft)
    source: str = "deterministic"
    confidence: str = "high"
    # Internal engine policy (plan.honesty). Never shown as the user summary.
    policy_note: str = ""
    # AI step outcome: called / skipped(reason) / failed / timed_out, model, latency.
    llm_outcome: dict[str, Any] | None = None
    # Full-app design (new models, stock extensions, integrations, groups) — step 2A.
    app_design: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        from app.ai_grain import HOST_LABELS
        from app.ai_class_stamp import apply_class_stamp, resolve_class_stamp

        data["host_label"] = HOST_LABELS.get(self.host_model or "", self.host_model)
        score = getattr(self, "_must_do_score", None)
        if isinstance(score, dict):
            data["_must_do_score"] = score
        anchor = getattr(self, "_placement_anchor", None)
        if anchor:
            data["placement_anchor"] = anchor
        stamp = resolve_class_stamp(
            prompt=str(getattr(self, "_source_prompt", "") or ""),
            capability=self.capability,
            grain=self.grain,
            needs_module=self.needs_module,
            gold_artifact_id=self.gold_artifact_id,
            module_delivery=self.needs_module,
            inherit_only=self.inherit_existing,
        )
        apply_class_stamp(data, stamp)
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
            approved_craft=coerce_approved_craft(raw.get("approved_craft")),
            source=str(raw.get("source") or "deterministic"),
            confidence="low" if raw.get("confidence") == "low" else "high",
            policy_note=str(raw.get("policy_note") or ""),
            llm_outcome=raw.get("llm_outcome") if isinstance(raw.get("llm_outcome"), dict) else None,
            app_design=raw.get("app_design") if isinstance(raw.get("app_design"), dict) else None,
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

    approved = coerce_approved_craft(base.approved_craft)
    if "approved_craft" in edits:
        approved = coerce_approved_craft(edits.get("approved_craft"))
    elif any(key in edits for key in APPROVED_CRAFT_KEYS):
        merged = dict(approved)
        for key in APPROVED_CRAFT_KEYS:
            if key in edits:
                merged[key] = bool(edits[key])
        approved = coerce_approved_craft(merged)

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
        approved_craft=approved,
        source="operator",
        confidence="high",
        # An "add to an existing app" design (checklist flag) is the build plan: keep it.
        app_design=(_edited_design(base.app_design, edits)
                    if not inherit or (base.app_design or {}).get("_extension_flow") else None),
    )


def _edited_design(base: dict[str, Any] | None, edits: dict[str, Any]) -> dict[str, Any] | None:
    """Operator-edited app design from the diagnosis screen, re-validated."""
    if not isinstance(edits.get("app_design"), dict) or not isinstance(base, dict):
        return base
    try:
        from app.ai_conversation.app_design import apply_design_edits
        from app.ai_conversation.grounding import current_grounding

        edited = apply_design_edits(base, edits["app_design"], current_grounding())
        if isinstance(edited, dict) and base.get("_extension_flow"):
            edited["_extension_flow"] = True
        return edited
    except Exception:  # noqa: BLE001 - a bad edit never loses the confirmed design
        return base


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
    approved_raw: dict[str, bool] = {}
    craft_line = re.search(r"(?im)^-\s*Approved craft:\s*(.+)$", block)
    if craft_line:
        for token in re.split(r"[,;\s]+", craft_line.group(1).strip()):
            key = token.strip().lower()
            if key in APPROVED_CRAFT_KEYS:
                approved_raw[key] = True
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
        approved_craft=coerce_approved_craft(approved_raw),
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
    craft = coerce_approved_craft(understanding.approved_craft)
    on_keys = [key for key, enabled in craft.items() if enabled]
    if on_keys:
        lines.append(f"- Approved craft: {', '.join(on_keys)}")
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
    r"(?i)\b(?:build|create|make)\s+(?:an?\s+)?(?:(?:tiny|simple|small|new|mini|full)\s+)*"
    r"(.+?)\s+app\b"
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
            reasons.append("custom code honesty missing (module/sandbox/Promote)")

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


def _stamp_source_prompt(understanding: Understanding, prompt: str) -> Understanding:
    """Keep the brief on the IR so class-wide stamps stay class-aware."""
    object.__setattr__(understanding, "_source_prompt", prompt or "")
    return understanding


def _design_allow(understanding: Understanding) -> frozenset[str]:
    """Names the same app design creates (x_* models/fields) or extends (stock models)."""
    design = getattr(understanding, "app_design", None)
    if not isinstance(design, dict):
        return frozenset()
    from app.ai_conversation.app_design import design_technical_names

    names = design_technical_names(design)
    names.update(str(e.get("model") or "") for e in design.get("stock_extensions") or [])
    names.discard("")
    return frozenset(names)


def _drop_unknown(text: str, packet: SchemaPacket | None, allow: frozenset[str] = frozenset()) -> str:
    if not allow or packet is None or not text:
        return drop_unknown_technical_names(text, packet)
    from app.live_schema_context import _TECH_NAME_RE

    kept: dict[str, str] = {}

    def _mask(match: re.Match[str]) -> str:
        token = match.group(0)
        if token not in allow:
            return token
        key = f"\u00a7{len(kept)}\u00a7"
        kept[key] = token
        return key

    out = drop_unknown_technical_names(_TECH_NAME_RE.sub(_mask, text), packet)
    for key, token in kept.items():
        out = out.replace(key, token)
    return out


def _constraint_row_admits_packet(
    row: str, packet: SchemaPacket | None, allow: frozenset[str] = frozenset()
) -> bool:
    if packet is None:
        return True
    cleaned = _drop_unknown(row, packet, allow)
    if re.search(r"\bx_[a-z0-9_]+\b", (row or "").lower()) and "x_" not in cleaned:
        return False
    return True


def _ground_understanding_to_packet(
    understanding: Understanding,
    prompt: str,
    packet: SchemaPacket | None,
) -> Understanding:
    """Drop packet-unknown names; resolve form anchors. Does not flip grain."""
    if packet is None or packet.is_empty():
        return understanding
    if understanding.host_model and not admit_host_from_packet(
        understanding.host_model, packet
    ):
        understanding.host_model = None
    understanding.title = drop_unknown_technical_names(understanding.title, packet) or understanding.title
    understanding.summary = drop_unknown_technical_names(understanding.summary, packet)
    allow = _design_allow(understanding)
    understanding.constraints = [
        _drop_unknown(row, packet, allow)
        for row in understanding.constraints
        if _constraint_row_admits_packet(row, packet, allow)
    ]
    understanding.constraints = [row for row in understanding.constraints if row]
    understanding.out_of_scope = [
        drop_unknown_technical_names(row, packet)
        for row in understanding.out_of_scope
        if row
    ]
    host = understanding.host_model
    anchor = resolve_form_anchor(packet, prompt, model=host)
    if anchor:
        object.__setattr__(understanding, "_placement_anchor", anchor)
        rewritten: list[str] = []
        for row in understanding.constraints:
            rewritten.append(
                re.sub(r"(?i)after the customer", f"after {anchor}", row)
            )
        understanding.constraints = rewritten
        if re.search(r"(?i)after the customer", prompt or "") and not any(
            anchor in row for row in understanding.constraints
        ):
            understanding.constraints.append(f"Place after {anchor}")
    return understanding



_PURPOSE_RES = (
    re.compile(r"(?i)\bgoal of (?:this|the) (?:app|application|module|system|tool)\s+is\s+to\s+([^.\n]{8,220})"),
    re.compile(r"(?i)\b(?:so that|in order to)\s+([^.\n]{8,160})"),
)


def _brief_purpose(text: str) -> str:
    for rx in _PURPOSE_RES:
        m = rx.search(text or "")
        if m:
            clause = re.sub(r"[*_`]+", "", m.group(1)).strip(" ,;:")
            return re.sub(r"\s+", " ", clause)
    return ""


def _join_names(names: Any) -> str:
    items = [str(n) for n in names if str(n).strip()]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _plain_summary(text: str, *, title: str, host: str | None, inherit: bool, needs: bool) -> str:
    """User-facing diagnosis summary: what App Studio understood, in plain words."""
    from app.ai_conversation.grounding import current_grounding
    from app.ai_grain import HOST_LABELS

    label = HOST_LABELS.get(host or "", host or "")
    if needs:
        first = f"{title}: an installable module" + (f" for {label}" if label else "") + "."
    elif inherit and label:
        first = f"Adds {title} to the {label} form people already use."
    else:
        first = f"{title}: a new app people open from the Odoo home screen."
    bits = [first]
    purpose = _brief_purpose(text)
    if purpose:
        bits.append(f"It is meant to {purpose.rstrip('.')}.")
    g = current_grounding()
    if g is not None and g.apps_installed:
        bits.append(f"Links to {_join_names(g.apps_installed)}.")
    if g is not None and g.apps_missing:
        verb = "is" if len(g.apps_missing) == 1 else "are"
        bits.append(f"{_join_names(g.apps_missing)} {verb} not installed yet, so those links wait.")
    out = " ".join(bits).replace("\u2014", ",")
    return out[:400]


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
    policy_note = (plan.honesty or "").strip()
    summary = ""
    confidence = "high"

    if plan.gold_artifact_id == "currency_rate_cbn":
        title = "CBN currency rates"
        out_of_scope.extend(["new app tile", "x_fx model", "live Install of Python"])
        constraints.append("Module zip → sandbox prove → you publish")
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
                "until the authoring gate passes. Publishing stays a step you confirm."
            )
    elif plan.capability == "stock_reuse":
        title = "Stock Community apps"
        inherit = False
        needs = False
        summary = summary or "No custom code. Job Autopilot is the done-bar."
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
        # Never seed Diagnosis/canvas title from «Build …» imperative crumbs.
        raw_slice = (text.split(".")[0].strip()[:48] or "Custom draft")
        raw_slice = re.sub(
            r"(?i)^(build|create|make|add|implement|develop|generate)\s+",
            "",
            raw_slice,
        ).strip() or "Custom draft"
        title = title or raw_slice
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

    # Prefer a short residual title for full_app (Visitor Log / Vehicle Request —
    # never leading Build/Create/Make imperatives glued into the noun).
    if grain == "full_app" and not inherit and not needs:
        try:
            from app.ai_document_shape import naming_from_residual

            nice, _slug = naming_from_residual(text)
        except Exception:  # noqa: BLE001
            nice = ""
        if not nice:
            app_m = _APP_NOUN_RE.search(text)
            if app_m:
                nice = re.sub(
                    r"\s+", " ", (app_m.group(1) or "")
                ).strip(" .:,-")
                nice = re.sub(r"(?i)^(a|an|the)\s+", "", nice).strip()
                nice = re.sub(
                    r"(?i)^(build|create|make|add|implement|develop|generate)\s+",
                    "",
                    nice,
                ).strip()
        if nice and len(nice) <= 48:
            nice = re.sub(
                r"(?i)\s+(?:management|system|module|platform|suite|solution|application)s?$",
                "",
                nice,
            ).strip()
            # Drop accidental stock-parent prefix when primary noun already stands alone
            # («Fleet Vehicle Request» → Vehicle Request when brief noun is Vehicle Request).
            nice = re.sub(
                r"(?i)^(fleet|hr|sales|crm|inventory|stock|project|purchase|"
                r"accounting|contacts|calendar)\s+"
                r"(?=(?:[\w-]+\s+)*(?:request|log|checkout|check[- ]?out|"
                r"ticket|application|claim|booking|reservation|inquiry|"
                r"enquiry|complaint|incident|case|requisition)\b)",
                "",
                nice,
            ).strip() or nice
            # Never title a Studio grain word (Full / Prefer / Extend → x_full).
            if re.fullmatch(
                r"(?i)full|new|prefer|extend|full_app|residual|app|field_pack|feature_slice",
                nice.strip(),
            ):
                nice = ""
            if nice:
                title = nice.title() if nice.islower() or nice.lower() == nice else nice

    if summary in {
        "",
        policy_note,
        f"{title}.",
        "A custom record people will open from the home screen.",
    }:
        summary = _plain_summary(text, title=title, host=host, inherit=inherit, needs=needs)
    result = Understanding(
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
        policy_note=policy_note,
    )
    return _stamp_source_prompt(result, text)


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
    from app.ai_conversation.grounding import ONLINE_LIMITS, current_grounding, odoo_phrase

    g = current_grounding()
    online = (" " + ONLINE_LIMITS) if g is not None and g.online else ""
    return (
        f"You diagnose an {odoo_phrase(g)} customization brief for App Studio. "
        "Reply JSON only. Prefer filling constraint_ast "
        "(fields[{label,ttype,relation?}], host, hints[], non_goals[], grain) "
        "plus operator-facing constraints bullets. Cover: (1) host/placement "
        "(model + form/group when named), (2) fields with types when stated, "
        "(3) workflows/states if implied, (4) live Install vs Custom-code module "
        "delivery when Python/QWeb/HTTP is needed, (5) non-goals, (6) Online "
        "honesty when Python cannot Install live (module zip → sandbox → human "
        "Promote). Prefer Date over Datetime unless time is stated/implied. "
        "Infer beyond literal copy when the brief implies it, but "
        "never invent account.tax, never invent a fake x_* app when inheriting, "
        "never contradict inherit vs new home-screen tile. "
        "host_model must be an Odoo model like sale.order / res.partner when "
        "inheriting. Do not override gold or refuse_clone."
        + online
    )


def _must_do_user_prompt(
    prompt: str,
    det: Understanding,
    *,
    repair_reasons: list[str] | None = None,
    schema_packet: SchemaPacket | None = None,
) -> str:
    seed = det.constraints[: (30 if det.app_design else 8)]
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
        "You may set host_model only if missing. Do not change gold or refuse. "
        + (
            "New x_* models and fields from the App design in the Must-do seed are "
            "allowed; any other model or field must be in the live schema packet."
            if det.app_design
            else "Do not name a model or field that is not in the live schema packet."
        )
    )
    if repair_reasons:
        base += (
            "\n\nREPAIR PASS — previous Must-do scored low for: "
            + "; ".join(repair_reasons[:6])
            + ". Rewrite constraints to fix those gaps. Keep host consistent "
            "with the deterministic host when set. Stay compact (≤10 bullets)."
        )
    from app.ai_conversation.grounding import grounding_prompt_block

    block = grounding_prompt_block()
    if block:
        base = block + "\n\n" + base
    return prepend_schema_packet(base, schema_packet)


_LLM_OUTCOME: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "understand_llm_outcome", default=None
)


def _provider_model(provider: Any) -> str | None:
    for attr in ("model", "model_name", "name"):
        val = getattr(provider, attr, None)
        if isinstance(val, str) and val:
            return val
    return None


def _record_llm_outcome(payload: dict[str, Any], *, repair: bool = False) -> None:
    if repair:
        cur = dict(_LLM_OUTCOME.get() or {})
        cur["repair_status"] = payload.get("status")
        _LLM_OUTCOME.set(cur)
        return
    _LLM_OUTCOME.set(payload)
    level = logging.INFO if payload.get("status") == "called" else logging.WARNING
    logger.log(level, "Understanding LLM outcome: %s", payload)


def _llm_enrich(
    prompt: str,
    det: Understanding,
    *,
    schema_packet: SchemaPacket | None = None,
) -> Understanding:
    from app.llm_provider import LLMError, get_llm_provider_for_tier

    packet = schema_packet if schema_packet is not None else current_schema_packet()
    provider = get_llm_provider_for_tier("fast")
    if provider is None:
        _record_llm_outcome({"status": "skipped", "reason": "no_provider"})
        scored = score_must_do_constraints(
            prompt,
            det.constraints,
            host=det.host_model,
            inherit=det.inherit_existing,
            needs_module=det.needs_module,
        )
        return _stamp_must_do_score(det, scored)

    cache_key = _enrich_cache_key(prompt, det)

    def _call(*, repair_reasons: list[str] | None = None, timeout_scale: float = 1.0) -> dict[str, Any] | None:
        # Cache only the primary (non-repair) fill — repairs are one-shot.
        if not repair_reasons:
            hit = _enrich_cache_get(cache_key)
            if hit is not None:
                _record_llm_outcome(
                    {"status": "called", "cached": True, "model": _provider_model(provider)}
                )
                return hit
        from app.ai_conversation.grounding import llm_timeout_for

        user_text = _must_do_user_prompt(
            prompt, det, repair_reasons=repair_reasons, schema_packet=packet
        )
        timeout_s = llm_timeout_for(prompt) * timeout_scale
        meta: dict[str, Any] = {
            "model": _provider_model(provider),
            "prompt_chars": len(user_text),
            "timeout_s": timeout_s,
        }
        started = time.monotonic()
        try:
            raw = provider.generate_json(
                user_text,
                system=_must_do_system_prompt(),
                timeout_s=timeout_s,
                temperature=0.0,
                format_schema=_UNDERSTAND_SCHEMA,
            )
        except (LLMError, TimeoutError) as exc:
            msg = str(exc)
            status = (
                "timed_out"
                if isinstance(exc, TimeoutError) or re.search(r"(?i)time[sd]?\s*out|timeout|deadline", msg)
                else "failed"
            )
            _record_llm_outcome(
                {
                    **meta,
                    "status": status,
                    "error": msg[:200],
                    "latency_ms": int((time.monotonic() - started) * 1000),
                },
                repair=bool(repair_reasons),
            )
            return None
        parsed_local = _parse_enrich_payload(raw)
        _record_llm_outcome(
            {
                **meta,
                "status": "called" if parsed_local else "failed",
                **({} if parsed_local else {"error": "unparseable JSON"}),
                "latency_ms": int((time.monotonic() - started) * 1000),
            },
            repair=bool(repair_reasons),
        )
        if parsed_local and not repair_reasons:
            _enrich_cache_put(cache_key, parsed_local)
        return parsed_local

    parsed = _call(timeout_scale=0.7)  # tighter first attempt; the retry keeps total near 1.4x
    if not parsed:
        parsed = _call(timeout_scale=0.7)  # one retry: a transient timeout must not lose the app design
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
    coerced = admit_host_from_packet(str(parsed.get("host_model") or ""), packet)
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
        # A full-app design that extends stock models keeps its stock host.
        host = det.host_model if det.app_design else None

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
            from app.ai_brief_cues import scrub_uncued_invent_from_llm_ast

            llm_ast = scrub_uncued_invent_from_llm_ast(llm_ast, prompt=prompt)
            if packet is not None:
                kept = []
                design_names = _design_allow(det)
                for field in llm_ast.fields or []:
                    label = str(getattr(field, "label", "") or "")
                    token = label.strip()
                    if (
                        token.startswith("x_")
                        and not field_in_packet(packet, token)
                        and token not in design_names
                    ):
                        continue
                    kept.append(field)
                llm_ast.fields = kept
                if llm_ast.host and not admit_host_from_packet(str(llm_ast.host), packet):
                    llm_ast.host = None
            llm_constraints = _dedupe(ast_to_must_do(llm_ast) + llm_constraints)
            from app.ai_brief_cues import scrub_uncued_invent_must_do_rows

            llm_constraints = scrub_uncued_invent_must_do_rows(
                llm_constraints, prompt=prompt
            )
    except AssertionError:
        raise
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
                    from app.ai_brief_cues import scrub_uncued_invent_from_llm_ast

                    repair_ast = scrub_uncued_invent_from_llm_ast(
                        repair_ast, prompt=prompt
                    )
                    repair_rows = _dedupe(ast_to_must_do(repair_ast) + repair_rows)
                    from app.ai_brief_cues import scrub_uncued_invent_must_do_rows

                    repair_rows = scrub_uncued_invent_must_do_rows(
                        repair_rows, prompt=prompt
                    )
            except AssertionError:
                raise
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
    try:
        from app.ai_operator_brief import stated_app_name

        if stated_app_name(prompt) and det.title:
            title = det.title  # operator-stated app name wins over the model's retitle
    except Exception:  # noqa: BLE001
        pass
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
    # custom code only from det (capability/gold) or an explicit custom code brief — never
    # from LLM boolean noise or pack depends keywords.
    needs = det.needs_module
    if brief_implies_option_a(prompt) and bool(parsed.get("needs_module")):
        needs = True
    # Residual full_app Contract: app name title, no stock host, no inherit, Live fields.
    if residual_full:
        host = det.host_model if det.app_design else None
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

    if det.app_design:
        # Design rows (every new model + stock extension) lead; LLM extras follow.
        constraints = list(det.constraints) + list(constraints)
    result = Understanding(
        capability=det.capability,
        grain=det.grain,
        host_model=host,
        inherit_existing=inherit,
        needs_module=needs,
        gold_artifact_id=det.gold_artifact_id,
        title=title,
        summary=summary,
        constraints=_dedupe(constraints)[: (24 if det.app_design else 12)],
        out_of_scope=_dedupe(out)[:8],
        source="mixed" if (coerced or llm_constraints or det.source == "mixed") else "deterministic",
        confidence=confidence,
        app_design=det.app_design,
    )
    result = _ground_understanding_to_packet(result, prompt, packet)
    return _stamp_source_prompt(_stamp_must_do_score(result, score), prompt)


def _design_applies(prompt: str, det: Understanding) -> bool:
    """Residual full_app long / structured briefs only; short and Prefer briefs unchanged."""
    import os

    from app.ai_conversation.grounding import brief_wants_llm

    if os.environ.get("STUDIO_APP_DESIGN", "on").strip().lower() in {"0", "off", "false", "no"}:
        return False
    from app.ai_conversation import studio_agent as _agent

    if _agent.mode() == "agent" and not det.gold_artifact_id:
        # Agent mode: single-model and extend-existing briefs also go through the agent, which
        # decides reuse / extend / new with a playback (the same code gates authorize it).
        return True
    if _extension_flow(prompt, det):
        return True
    return (
        det.grain == "full_app"
        and not det.inherit_existing
        and not det.needs_module
        and (det.capability == "residual_app" or (det.capability == "mixed" and _multi_record_brief(prompt)))
        and not det.gold_artifact_id
        and (intent_llm_enabled() or brief_wants_llm(prompt))
    )


def _extension_flow(prompt: str, det: Understanding) -> bool:
    """Checklist flag: "add to an existing app" briefs go through the authorized design.

    Fields and automations then trace to approved requirements (no sentence-shaped fields),
    and after a planned app is installed the design is refreshed on its real models."""
    from app.ai_conversation import brief_checklist as bc
    from app.ai_conversation.grounding import brief_wants_llm

    return (
        bc.enabled()
        and bool(det.inherit_existing)
        and bool(det.host_model)
        and not det.needs_module
        and not det.gold_artifact_id
        and (intent_llm_enabled() or brief_wants_llm(prompt))
    )


def _multi_record_brief(prompt: str) -> bool:
    """A brief that names two or more new records is a full app, even if it also extends stock apps."""
    try:
        from app.ai_conversation.app_design import outline_from_brief

        return len(outline_from_brief(prompt).new_models) >= 2
    except Exception:  # noqa: BLE001
        return False


def _suggest_applies(prompt: str, det: Understanding) -> bool:
    """Named-residual brief (one main record): AI may suggest supporting models.

    Prefer / inherit, built-in apps only, gold and custom code briefs never get suggestions.
    """
    import os

    if os.environ.get("STUDIO_SUGGEST_MODELS", "on").strip().lower() in {"0", "off", "false", "no"}:
        return False
    if not (
        det.grain == "full_app"
        and det.capability == "residual_app"
        and not det.inherit_existing
        and not det.needs_module
        and not det.gold_artifact_id
        and not det.host_model
    ):
        return False
    try:
        from app.ai_document_shape import _named_residual

        kind, residual = _named_residual(prompt)
    except Exception:  # noqa: BLE001
        return False
    return kind == "named" and bool(residual)


def _apply_suggested_design(prompt: str, det: Understanding) -> Understanding:
    """Main record + suggested supporting models. Must-do stays brief-named only."""
    if not _suggest_applies(prompt, det):
        return det
    try:
        from app.ai_conversation.app_design import named_residual_design
        from app.ai_conversation.grounding import current_grounding

        design = named_residual_design(
            prompt, title=det.title, grounding=current_grounding(), use_llm=intent_llm_enabled()
        )
    except Exception:  # noqa: BLE001 — suggestions are optional
        logger.exception("Supporting-model suggestions failed")
        return det
    if design is not None:
        det.app_design = design.to_dict()
    return det


def _apply_app_design(
    prompt: str,
    det: Understanding,
    packet: SchemaPacket | None,
    *,
    resolved_answers: dict[str, str] | None = None,
) -> Understanding:
    """LLM designs the full app (guardrails repair; outline fallback) → Must-do + host."""
    if not _design_applies(prompt, det):
        return _apply_suggested_design(prompt, det)
    try:
        from app.ai_conversation.app_design import build_app_design, design_must_do
        from app.ai_conversation.grounding import current_grounding
        from app.odoo_snapshot import current_snapshot

        design = build_app_design(
            prompt,
            grounding=current_grounding(),
            schema_packet=packet,
            use_llm=intent_llm_enabled(),
            title=det.title,
            purpose=det.summary,
            resolved_answers=resolved_answers,
            snapshot=current_snapshot(),
        )
    except Exception:  # noqa: BLE001 — design is additive; never break understand
        logger.exception("App design failed; keeping deterministic Must-do")
        return det
    if design is None:
        # One-model brief: fall back to the named-residual suggestion path.
        return _apply_suggested_design(prompt, det)
    det.app_design = design.to_dict()
    agent_extend = bool(design.playback) and bool(design.stock_extensions) and not design.new_models
    if _extension_flow(prompt, det) or agent_extend:
        # Built from the design (stock extensions + automations), not the field-pack grammar.
        det.app_design["_extension_flow"] = True
    det.constraints = _dedupe(design_must_do(design))
    if design.stock_extensions:
        det.host_model = max(design.stock_extensions, key=lambda e: len(e.fields)).model
    if design.source.startswith("llm"):
        det.source = "mixed"
    return det


_NEG_CUE = re.compile(r"(?i)\b(without|don'?t|do not|no|never|not|avoid|exclud\w*|out of scope)\b")
_COND_CLAUSE = re.compile(r"(?i)\b(?:when|whenever|if|unless|until|once|where)\b")
_EXCL_ROW = re.compile(r"(?i)^\s*(no|without|don'?t|do not|avoid|never|exclude[ds]?)\b|\bbefore\b.*\binstall")


def drop_exclusions(rows: list[str], prompt: str) -> list[str]:
    """'Don't do X' in the brief must never become a Must-do row."""
    from app.ai_conversation.intent_contract import _stems

    negated: list[set[str]] = []
    for sent in re.split(r"(?<=[.!?])\s+|\n", prompt or ""):
        # A negation inside a condition ("show a hint when ... no document is attached")
        # describes when something happens; it is not the owner saying "don't build it".
        sent = _COND_CLAUSE.split(sent, maxsplit=1)[0]
        m = _NEG_CUE.search(sent)
        if m:
            negated.append(_stems(re.split(r"[:;,]", sent[m.end():])[0][:120]))
    out = []
    for row in rows or []:
        text = str(row)
        st = _stems(text)
        if _EXCL_ROW.search(text) or any(len(st & n) >= 2 and len(st & n) * 3 >= len(st) for n in negated):
            continue
        out.append(row)
    return out


def _host_from_approved_decision(resolved_answers: dict[str, str] | None) -> str:
    """The stock record the approved checklist built on, once its app is installed ('' otherwise).

    Checklist flag only. Every stock choice in the stored decision must name the same model, and
    the live database must have it, so code (not wording) authorizes the host."""
    from app.ai_conversation import brief_checklist as bc
    from app.odoo_snapshot import current_snapshot

    if not bc.enabled() or not resolved_answers:
        return ""
    try:
        decision = json.loads(resolved_answers.get("_diagnosis_decision_json") or "null") or {}
    except (TypeError, ValueError):
        return ""
    models = {
        str((c.get("use") or {}).get("model") or "")
        for c in decision.get("stock_checks") or []
        if isinstance(c, dict) and c.get("choice") == "stock" and isinstance(c.get("use"), dict)
    }
    models.discard("")
    snap = current_snapshot()
    if len(models) != 1 or snap is None or not getattr(snap, "ok", False):
        return ""
    model = next(iter(models))
    return model if model in (getattr(snap, "index", None) or {}) else ""


def build_understanding(
    prompt: str,
    *,
    schema_packet: SchemaPacket | None = None,
    resolved_answers: dict[str, str] | None = None,
) -> Understanding:
    packet = schema_packet if schema_packet is not None else current_schema_packet()
    det = _deterministic_understanding(prompt)
    if det.inherit_existing and not det.host_model and not det.needs_module:
        det.host_model = _host_from_approved_decision(resolved_answers) or None
    det = _apply_app_design(prompt, det, packet, resolved_answers=resolved_answers)
    det = _ground_understanding_to_packet(det, prompt, packet)
    _LLM_OUTCOME.set(None)
    if _should_llm_enrich(prompt, det):
        understanding = _llm_enrich(prompt, det, schema_packet=packet)
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
    if isinstance(understanding.app_design, dict) and understanding.app_design.get("new_models"):
        # The app design is the source of truth for Must do: no raw AI implementation lines,
        # no single-field rows repeating an extension, no exclusions.
        from app.ai_conversation.app_design import AppDesign, design_must_do

        raw = dict(understanding.app_design)
        extra = {m.get("name") for m in raw.get("new_models") or [] if isinstance(m, dict) and m.get("suggested")}
        raw["new_models"] = [
            dict(m, fields=[f for f in m.get("fields") or [] if not (isinstance(f, dict) and f.get("relation") in extra)])
            for m in raw.get("new_models") or [] if isinstance(m, dict) and m.get("name") not in extra
        ]
        understanding.constraints = _dedupe(design_must_do(AppDesign.from_dict(raw)))
    understanding.constraints = drop_exclusions(understanding.constraints, prompt)
    understanding = _attach_craft_proposals(prompt, understanding)
    understanding = _ground_understanding_to_packet(understanding, prompt, packet)
    outcome = _LLM_OUTCOME.get()
    if outcome is None:
        if not intent_llm_enabled():
            reason = "ai_step_off"
        elif det.capability == "refuse_clone":
            reason = "refuse_clone"
        else:
            reason = "not_needed"
        outcome = {"status": "skipped", "reason": reason}
    understanding.llm_outcome = dict(outcome)
    if isinstance(understanding.app_design, dict):
        understanding.llm_outcome["design"] = understanding.app_design.get("llm_outcome")
    if not understanding.policy_note:
        understanding.policy_note = det.policy_note
    return _stamp_source_prompt(understanding, prompt)


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
        help_bits.append("This is a custom-code module, not Install this app.")
    elif understanding.inherit_existing:
        help_bits.append("Extra fields on a form people already use, not a new Apps tile.")
    stamp_lane = getattr(understanding, "delivery_lane", None)
    u_dict = understanding.to_dict()
    from app.ai_conversation.grounding import current_grounding, plain_lane_copy

    grounding = current_grounding()
    if u_dict.get("delivery_lane_copy") or u_dict.get("delivery_lane"):
        help_bits.append(plain_lane_copy(u_dict.get("delivery_lane"), grounding))
    _ = stamp_lane
    return {
        "id": "diagnosis",
        "kind": "diagnosis",
        "merge_key": "diagnosis",
        "question": f"We'll build: {understanding.title}",
        "help": " ".join(bit for bit in help_bits if bit).strip(),
        "understanding": u_dict,
        "grounding": grounding.as_dict() if grounding is not None else None,
        "llm_outcome": u_dict.get("llm_outcome"),
        "app_design": u_dict.get("app_design"),
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
            f"Locked as custom code ({understanding.capability}); draft capability is {cap or 'empty'}."
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
            approved_craft=coerce_approved_craft(understanding.approved_craft),
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
    / ``approved_craft`` into session understanding, pass that as ``locked``
    (or leave it on the draft) so Generate does not rebuild from prompt alone
    and zero craft. Preference order for the locked Contract: explicit ``locked``
    → parse locked block → prior draft ``_understanding`` → deterministic.
    Craft list / approved_craft are taken from the first source that carries
    them (session wins over a craft-empty reparse).
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
        u.approved_craft = coerce_approved_craft(session_u.approved_craft)
    elif not list(u.craft_smart_buttons or []):
        for donor in (prior, parsed):
            if donor is not None and list(donor.craft_smart_buttons or []):
                u.craft_smart_buttons = list(donor.craft_smart_buttons or [])
                break
    if session_u is None and not any(coerce_approved_craft(u.approved_craft).values()):
        for donor in (prior, parsed):
            if donor is not None and any(
                coerce_approved_craft(donor.approved_craft).values()
            ):
                u.approved_craft = coerce_approved_craft(donor.approved_craft)
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
    craft = coerce_approved_craft(u.approved_craft)
    payload["approved_craft"] = craft
    # Operator craft toggles land on the draft before invent gates run.
    draft["_approved_craft"] = craft
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
    "APPROVED_CRAFT_KEYS",
    "DIAGNOSIS_KEY",
    "UNDERSTANDING_KEY",
    "Understanding",
    "append_locked_diagnosis",
    "attach_understanding",
    "coerce_approved_craft",
    "default_approved_craft",
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
