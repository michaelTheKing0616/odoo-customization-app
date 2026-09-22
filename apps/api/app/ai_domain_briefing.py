"""Pack-free domain briefing — industry vocabulary for THIS prompt.

Not a ModuleSpec pack. A briefing is computed per request: what this business
uses, which neighboring industry to avoid, and which stock apps are false friends
(``production`` ≠ MRP). Deterministic collocations are the source of truth;
an optional LLM pass may enrich unmatched prompts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.ai_selection import parse_selection_literal, serialize_selection
from app.text_negation import span_is_negated

_HAY_RE = re.compile(r"[^a-z0-9]+")

# Legal ops must never inherit restaurant/hotel kitchen vocab from a "not restaurant" clause.
_LEGAL_NONE_OF = (
    "law firm",
    "legal practice",
    "attorney",
    "litigation",
    "matter file",
    "billable hour",
)


def _hay(prompt: str) -> str:
    return f" {_HAY_RE.sub(' ', (prompt or '').lower())} "


def _has_any(hay: str, needles: tuple[str, ...]) -> bool:
    for raw in needles:
        needle = _HAY_RE.sub(" ", raw.lower()).strip()
        if not needle:
            continue
        if " " in needle:
            token = f" {needle} "
            start = 0
            while True:
                idx = hay.find(token, start)
                if idx < 0:
                    break
                if not span_is_negated(hay, idx + 1):
                    return True
                start = idx + 1
            continue
        if len(needle) <= 3:
            pat = re.compile(rf"\b{re.escape(needle)}\b")
        else:
            pat = re.compile(rf"\b{re.escape(needle)}[a-z]*\b")
        for match in pat.finditer(hay):
            if not span_is_negated(hay, match.start()):
                return True
    return False


def _pairs(*rows: tuple[str, str]) -> tuple[tuple[str, str], ...]:
    return rows


@dataclass(frozen=True)
class _Collocation:
    """Adjacent-industry confusion pair — not a vertical ModuleSpec."""

    id: str
    industry: str
    any_of: tuple[str, ...]
    all_of: tuple[str, ...] = ()
    none_of: tuple[str, ...] = ()
    not_industries: tuple[str, ...] = ()
    equipment_types: tuple[tuple[str, str], ...] = ()
    rate_uoms: tuple[tuple[str, str], ...] = ()
    specialty_types: tuple[tuple[str, str], ...] = ()
    banned_selection_keys: tuple[str, ...] = ()
    allow_mrp: bool = False


# Keep this list to confusion pairs (recording vs film, kitchen vs studio, …).
# Do not grow it into per-vertical packs.
_COLLOCATIONS: tuple[_Collocation, ...] = (
    _Collocation(
        id="film_studio",
        industry="film / video production",
        any_of=("film", "cinema", "video shoot", "videography"),
        all_of=("studio",),
        none_of=("recording", "music", "artiste", "song"),
        not_industries=("music recording", "manufacturing"),
        equipment_types=_pairs(
            ("camera", "Camera"),
            ("lens", "Lens"),
            ("lighting", "Lighting"),
            ("sound", "Sound"),
            ("rigging", "Rigging"),
            ("miscellaneous", "Miscellaneous"),
        ),
        rate_uoms=_pairs(("hour", "Hour"), ("day", "Day"), ("shoot", "Shoot")),
        banned_selection_keys=("console", "microphone", "outboard", "stem"),
    ),
    _Collocation(
        id="music_recording",
        industry="music recording",
        any_of=(
            "recording",
            "music",
            "artiste",
            "song",
            "mixing",
            "mastering",
            "audio",
        ),
        all_of=(),
        none_of=("film", "cinema", "camera", "videography"),
        not_industries=("film production", "manufacturing"),
        equipment_types=_pairs(
            ("console", "Console"),
            ("microphone", "Microphone"),
            ("monitor", "Monitor"),
            ("outboard", "Outboard"),
            ("instrument", "Instrument"),
            ("miscellaneous", "Miscellaneous"),
        ),
        rate_uoms=_pairs(
            ("hour", "Hour"),
            ("session", "Session"),
            ("stem", "Stem"),
            ("day", "Day"),
        ),
        specialty_types=_pairs(
            ("recording", "Recording"),
            ("mixing", "Mixing"),
            ("mastering", "Mastering"),
            ("sound_design", "Sound Design"),
        ),
        banned_selection_keys=("camera", "lens", "rigging"),
    ),
    _Collocation(
        id="manufacturing",
        industry="manufacturing",
        any_of=("manufactur", "factory", "bill of materials", "assembly line", "bom"),
        not_industries=("music recording", "film production"),
        allow_mrp=True,
        equipment_types=_pairs(
            ("cnc", "CNC"),
            ("press", "Press"),
            ("conveyor", "Conveyor"),
            ("tooling", "Tooling"),
            ("miscellaneous", "Miscellaneous"),
        ),
        rate_uoms=_pairs(("hour", "Hour"), ("job", "Job"), ("unit", "Unit")),
        banned_selection_keys=("camera", "microphone", "console"),
    ),
    _Collocation(
        id="restaurant",
        industry="restaurant / kitchen",
        any_of=("restaurant", "kitchen", "chef", "dining"),
        none_of=("recording", "film") + _LEGAL_NONE_OF,
        not_industries=("film production", "manufacturing"),
        equipment_types=_pairs(
            ("range", "Range"),
            ("oven", "Oven"),
            ("fridge", "Fridge"),
            ("fryer", "Fryer"),
            ("dishwasher", "Dishwasher"),
            ("miscellaneous", "Miscellaneous"),
        ),
        rate_uoms=_pairs(("cover", "Cover"), ("hour", "Hour"), ("service", "Service")),
        banned_selection_keys=("camera", "lens", "console", "microphone", "rigging"),
    ),
    _Collocation(
        id="clinic",
        industry="clinic / care",
        any_of=("clinic", "hospital", "patient", "ward", "physician"),
        none_of=("recording", "film", "manufactur"),
        not_industries=("manufacturing", "film production"),
        equipment_types=_pairs(
            ("diagnostic", "Diagnostic"),
            ("treatment", "Treatment"),
            ("monitoring", "Monitoring"),
            ("surgical", "Surgical"),
            ("miscellaneous", "Miscellaneous"),
        ),
        banned_selection_keys=("camera", "console", "fryer"),
    ),
    _Collocation(
        id="hotel",
        industry="hotel / lodging",
        any_of=("hotel", "check-in", "checkin", "lodging", "guest room"),
        all_of=(),
        none_of=("recording", "film") + _LEGAL_NONE_OF,
        equipment_types=_pairs(
            ("housekeeping", "Housekeeping"),
            ("f_and_b", "F&B"),
            ("front_office", "Front office"),
            ("engineering", "Engineering"),
            ("miscellaneous", "Miscellaneous"),
        ),
        rate_uoms=_pairs(("night", "Night"), ("hour", "Hour"), ("package", "Package")),
        banned_selection_keys=("camera", "console", "microphone"),
    ),
    _Collocation(
        id="vehicle_rental",
        industry="vehicle rental",
        any_of=(
            "car rental",
            "vehicle rental",
            "car hire",
            "auto hire",
            "fleet rental",
            "rental fleet",
            "rent a car",
            "rent cars",
        ),
        none_of=("recording", "film", "studio"),
        equipment_types=_pairs(
            ("economy", "Economy"),
            ("suv", "SUV"),
            ("van", "Van"),
            ("luxury", "Luxury"),
            ("miscellaneous", "Miscellaneous"),
        ),
        rate_uoms=_pairs(("day", "Day"), ("week", "Week"), ("hour", "Hour")),
        banned_selection_keys=("camera", "console", "microphone", "oven"),
    ),
    _Collocation(
        id="construction",
        industry="construction",
        any_of=("construction", "contractor", "jobsite", "job site"),
        none_of=("recording", "film"),
        equipment_types=_pairs(
            ("excavator", "Excavator"),
            ("crane", "Crane"),
            ("scaffold", "Scaffold"),
            ("tools", "Tools"),
            ("miscellaneous", "Miscellaneous"),
        ),
        rate_uoms=_pairs(("hour", "Hour"), ("day", "Day"), ("job", "Job")),
        banned_selection_keys=("camera", "console", "microphone"),
    ),
    _Collocation(
        id="gym",
        industry="gym / fitness",
        any_of=("gym", "fitness", "workout"),
        none_of=("recording", "film"),
        equipment_types=_pairs(
            ("cardio", "Cardio"),
            ("weights", "Weights"),
            ("bench", "Bench"),
            ("floor", "Floor"),
            ("miscellaneous", "Miscellaneous"),
        ),
        banned_selection_keys=("camera", "console", "oven"),
    ),
    _Collocation(
        id="salon",
        industry="salon / spa",
        any_of=("salon", "spa", "barber", "stylist"),
        none_of=("recording", "film"),
        equipment_types=_pairs(
            ("chair", "Chair"),
            ("station", "Station"),
            ("wet", "Wet"),
            ("treatment", "Treatment"),
            ("miscellaneous", "Miscellaneous"),
        ),
        banned_selection_keys=("camera", "console", "microphone", "rigging"),
    ),
    _Collocation(
        id="farm",
        industry="farm / agriculture",
        any_of=("farm", "crop", "livestock", "agriculture"),
        none_of=("recording", "film") + _LEGAL_NONE_OF,
        equipment_types=_pairs(
            ("tractor", "Tractor"),
            ("implement", "Implement"),
            ("irrigation", "Irrigation"),
            ("storage", "Storage"),
            ("miscellaneous", "Miscellaneous"),
        ),
        banned_selection_keys=("camera", "console", "microphone"),
    ),
    _Collocation(
        id="oil_gas",
        industry="oil and gas operations",
        any_of=("oil", "gas", "wellsite", "well site", "drilling", "refinery"),
        none_of=("recording", "film", "kitchen"),
        not_industries=("music recording", "film production", "manufacturing"),
        equipment_types=_pairs(
            ("pump", "Pump"),
            ("separator", "Separator"),
            ("compressor", "Compressor"),
            ("tank", "Tank"),
            ("miscellaneous", "Miscellaneous"),
        ),
        rate_uoms=_pairs(("hour", "Hour"), ("day", "Day"), ("well", "Well")),
        banned_selection_keys=("camera", "console", "microphone", "oven"),
    ),
)

_MRP_MODELS = frozenset(
    {
        "mrp.production",
        "mrp.production.group",
        "mrp.bom",
        "mrp.workorder",
        "mrp.routing.workcenter",
        "mrp.unbuild",
    }
)
_PROJECT_TASK_MODELS = frozenset({"project.task", "project.project"})

_EQUIPMENT_MODEL_TOKENS = (
    "equipment",
    "asset",
    "gear",
    "instrument",
    "vehicle",
    "tool",
)
_RATE_MODEL_TOKENS = ("rate", "tariff", "pricelist", "price_list")
_TYPE_FIELD_TOKENS = ("type", "category", "class", "kind")
_UOM_FIELD_TOKENS = ("uom", "unit", "rate_type")
_SPECIALTY_FIELD_TOKENS = ("specialty", "speciality", "discipline")


@dataclass
class DomainBriefing:
    industry: str
    not_industries: list[str] = field(default_factory=list)
    collocation_id: str | None = None
    equipment_types: list[tuple[str, str]] = field(default_factory=list)
    rate_uoms: list[tuple[str, str]] = field(default_factory=list)
    specialty_types: list[tuple[str, str]] = field(default_factory=list)
    banned_selection_keys: set[str] = field(default_factory=set)
    banned_stock_models: set[str] = field(default_factory=set)
    banned_stock_apps: set[str] = field(default_factory=set)
    source: str = "default"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "industry": self.industry,
            "not_industries": list(self.not_industries),
            "collocation_id": self.collocation_id,
            "equipment_types": [list(p) for p in self.equipment_types],
            "rate_uoms": [list(p) for p in self.rate_uoms],
            "specialty_types": [list(p) for p in self.specialty_types],
            "banned_selection_keys": sorted(self.banned_selection_keys),
            "banned_stock_models": sorted(self.banned_stock_models),
            "banned_stock_apps": sorted(self.banned_stock_apps),
            "source": self.source,
            "notes": list(self.notes),
        }

    def bans_stock(self, model: str) -> bool:
        mid = str(model or "")
        if mid in self.banned_stock_models:
            return True
        app = mid.split(".", 1)[0]
        return app in self.banned_stock_apps

    def prompt_block(self) -> str:
        lines = [
            "DOMAIN BRIEFING (this request only — not a vertical pack):",
            f"- Industry: {self.industry}",
        ]
        if self.not_industries:
            lines.append(f"- Not: {', '.join(self.not_industries)}")
        if self.equipment_types:
            labels = ", ".join(lbl for _k, lbl in self.equipment_types)
            lines.append(f"- Equipment / asset types: {labels}")
        if self.rate_uoms:
            labels = ", ".join(lbl for _k, lbl in self.rate_uoms)
            lines.append(f"- Rate units: {labels}")
        if self.specialty_types:
            labels = ", ".join(lbl for _k, lbl in self.specialty_types)
            lines.append(f"- Site specialties: {labels}")
        if self.banned_selection_keys:
            lines.append(
                "- Do NOT use selection keys: "
                + ", ".join(sorted(self.banned_selection_keys))
            )
        if self.banned_stock_models:
            lines.append(
                "- Do NOT reuse stock models: "
                + ", ".join(sorted(self.banned_stock_models))
            )
        lines.append(
            "- Selection keys must be words from THIS business, not a neighboring industry."
        )
        return "\n".join(lines)


def briefing_from_dict(raw: dict[str, Any] | None) -> DomainBriefing | None:
    if not isinstance(raw, dict) or not raw.get("industry"):
        return None
    return DomainBriefing(
        industry=str(raw.get("industry") or "unspecified"),
        not_industries=[str(x) for x in (raw.get("not_industries") or []) if x],
        collocation_id=str(raw["collocation_id"]) if raw.get("collocation_id") else None,
        equipment_types=[
            (str(a), str(b)) for a, b in (raw.get("equipment_types") or []) if a and b
        ],
        rate_uoms=[(str(a), str(b)) for a, b in (raw.get("rate_uoms") or []) if a and b],
        specialty_types=[
            (str(a), str(b)) for a, b in (raw.get("specialty_types") or []) if a and b
        ],
        banned_selection_keys={
            str(x) for x in (raw.get("banned_selection_keys") or []) if x
        },
        banned_stock_models={str(x) for x in (raw.get("banned_stock_models") or []) if x},
        banned_stock_apps={str(x) for x in (raw.get("banned_stock_apps") or []) if x},
        source=str(raw.get("source") or "stored"),
        notes=[str(x) for x in (raw.get("notes") or []) if x],
    )


_PACK_REJECTS_COLLOCATION: dict[str, frozenset[str]] = {
    "law_firm": frozenset(
        {
            "farm",
            "restaurant",
            "hotel",
            "salon",
            "clinic",
            "film_studio",
            "music_recording",
            "manufacturing",
        }
    ),
}


def _briefing_conflicts_with_pack(briefing: DomainBriefing, pack_id: str) -> bool:
    rejected = _PACK_REJECTS_COLLOCATION.get(pack_id)
    if not rejected:
        return False
    return briefing.collocation_id in rejected


def _match_collocation(prompt: str) -> _Collocation | None:
    hay = _hay(prompt)
    for row in _COLLOCATIONS:
        if row.all_of and not all(_has_any(hay, (tok,)) for tok in row.all_of):
            continue
        if row.any_of and not _has_any(hay, row.any_of):
            continue
        if row.none_of and _has_any(hay, row.none_of):
            continue
        return row
    return None


def build_domain_briefing(
    prompt: str,
    *,
    provider: Any | None = None,
) -> DomainBriefing:
    """Deterministic briefing; optional LLM enrich when no collocation matches."""
    hit = _match_collocation(prompt)
    if hit:
        briefing = DomainBriefing(
            industry=hit.industry,
            not_industries=list(hit.not_industries),
            collocation_id=hit.id,
            equipment_types=list(hit.equipment_types),
            rate_uoms=list(hit.rate_uoms),
            specialty_types=list(hit.specialty_types),
            banned_selection_keys=set(hit.banned_selection_keys),
            banned_stock_models=set() if hit.allow_mrp else set(_MRP_MODELS),
            banned_stock_apps=set() if hit.allow_mrp else {"mrp"},
            source="collocation",
            notes=[f"collocation:{hit.id}"],
        )
        if not hit.allow_mrp and not _has_any(_hay(prompt), ("project management", "kanban")):
            briefing.banned_stock_models |= set(_PROJECT_TASK_MODELS)
        return briefing

    hay = _hay(prompt)
    allow_mrp = _has_any(hay, ("manufactur", "factory", "bom", "assembly"))
    briefing = DomainBriefing(
        industry="prompt-derived",
        not_industries=[] if allow_mrp else ["manufacturing"],
        banned_stock_models=set() if allow_mrp else set(_MRP_MODELS),
        banned_stock_apps=set() if allow_mrp else {"mrp"},
        source="default",
        notes=["no collocation — default catalog gates"],
    )
    if provider is not None:
        briefing = _enrich_briefing_with_llm(briefing, prompt, provider)
    return briefing


def _enrich_briefing_with_llm(
    briefing: DomainBriefing, prompt: str, provider: Any
) -> DomainBriefing:
    try:
        from app.ai_llm_budget import llm_json_with_budget
        from app.ai_prompt_constants import STEP_TEMPERATURES

        raw, _ = llm_json_with_budget(
            provider,
            "domain_briefing",
            (
                "User business:\n"
                f"{prompt}\n\n"
                "Return JSON with keys industry, not_industries (list), "
                "equipment_types (list of [key,label]), rate_uoms (list of [key,label]), "
                "banned_selection_keys (list of neighboring-industry keys). "
                "4-8 equipment types. No manufacturing unless they make goods in a factory."
            ),
            system=(
                "You name THIS business's vocabulary for an Odoo app. "
                "Reply ONLY JSON. Do not invent a neighboring industry's gear."
            ),
            reasoning=False,
            temperature=STEP_TEMPERATURES.get("pipeline.fields", 0.15),
        )
    except Exception:  # noqa: BLE001
        briefing.notes.append("llm briefing skipped")
        return briefing
    if not isinstance(raw, dict):
        return briefing
    industry = str(raw.get("industry") or "").strip()
    if industry:
        briefing.industry = industry
    extra_not = [str(x) for x in (raw.get("not_industries") or []) if x]
    for item in extra_not:
        if item not in briefing.not_industries:
            briefing.not_industries.append(item)
    types = [
        (str(a), str(b))
        for row in (raw.get("equipment_types") or [])
        if isinstance(row, (list, tuple)) and len(row) >= 2
        for a, b in (row[:2],)
        if a and b
    ]
    if 2 <= len(types) <= 10 and not briefing.equipment_types:
        briefing.equipment_types = types
    uoms = [
        (str(a), str(b))
        for row in (raw.get("rate_uoms") or [])
        if isinstance(row, (list, tuple)) and len(row) >= 2
        for a, b in (row[:2],)
        if a and b
    ]
    if 2 <= len(uoms) <= 8 and not briefing.rate_uoms:
        briefing.rate_uoms = uoms
    for key in raw.get("banned_selection_keys") or []:
        if key:
            briefing.banned_selection_keys.add(str(key))
    briefing.source = "default+llm"
    briefing.notes.append("llm enrich")
    return briefing


def attach_domain_briefing(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    provider: Any | None = None,
) -> DomainBriefing:
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    existing = briefing_from_dict(
        draft.get("_domain_briefing") if isinstance(draft.get("_domain_briefing"), dict) else None
    )
    pack = str(draft.get("domain_pack") or "")
    if existing and existing.source in {"collocation", "default+llm"}:
        if not _briefing_conflicts_with_pack(existing, pack):
            return existing
    briefing = build_domain_briefing(prompt, provider=provider)
    if pack == "law_firm" or _briefing_conflicts_with_pack(briefing, pack):
        briefing = DomainBriefing(
            industry="legal practice" if pack == "law_firm" else "prompt-derived",
            collocation_id=None,
            banned_stock_models=set(_MRP_MODELS),
            banned_stock_apps={"mrp"},
            source="pack",
            notes=[f"domain_pack:{pack or 'none'} — ignored neighboring collocation"],
        )
    draft["_domain_briefing"] = briefing.to_dict()
    return briefing


def _model_matches(mid: str, tokens: tuple[str, ...]) -> bool:
    hay = mid.replace("x_", "").replace(".", "_")
    return any(tok in hay for tok in tokens)


def _field_matches(name: str, tokens: tuple[str, ...]) -> bool:
    leaf = name.replace("x_", "")
    return any(tok in leaf for tok in tokens)


_GENERIC_SELECTION_KEYS = frozenset({"a", "b", "other", "option_a", "option_b"})


def _rewrite_selection(field: dict[str, Any], pairs: list[tuple[str, str]]) -> bool:
    new = serialize_selection(pairs)
    if str(field.get("selection") or "") == new:
        return False
    field["selection"] = new
    field["ttype"] = "selection"
    return True


def _should_rewrite_types(
    keys: set[str],
    wanted: list[tuple[str, str]],
    banned: set[str],
    *,
    other_tables: tuple[tuple[tuple[str, str], ...], ...] = (),
    labels: set[str] | None = None,
) -> bool:
    if not wanted:
        return False
    from app.ai_selection import snake_selection_key

    wanted_keys = {k for k, _ in wanted}
    label_keys = {snake_selection_key(lbl) for lbl in (labels or set()) if lbl}
    if keys and keys <= wanted_keys:
        # One leftover briefing key (or a 2-tuple collapsed to one pair) is truncated.
        if len(keys) == 1 and len(wanted_keys) >= 2:
            return True
        return False
    if label_keys & wanted_keys:
        return True
    if not keys or keys <= _GENERIC_SELECTION_KEYS:
        return True
    if keys & banned:
        return True
    for table in other_tables:
        other = {k for k, _ in table}
        if other and other != wanted_keys and len(keys & other) >= 2:
            return True
    return False


def apply_briefing_to_draft(
    draft: dict[str, Any],
    *,
    user_prompt: str = "",
    briefing: DomainBriefing | None = None,
) -> list[str]:
    """Rewrite foreign-industry selections and drop false-friend catalog rows."""
    notes: list[str] = []
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    brief = briefing or attach_domain_briefing(draft, user_prompt=prompt)
    draft["_domain_briefing"] = brief.to_dict()

    reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    suggestions = reuse.get("catalog_suggestions")
    if isinstance(suggestions, list):
        kept: list[dict[str, Any]] = []
        dropped = 0
        for row in suggestions:
            if not isinstance(row, dict):
                continue
            model = str(row.get("model") or "")
            if brief.bans_stock(model):
                dropped += 1
                continue
            kept.append(row)
        if dropped:
            reuse["catalog_suggestions"] = kept
            draft["reuse"] = reuse
            notes.append(f"briefing: dropped {dropped} false-friend catalog suggestion(s)")

    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        fields = list(model.get("fields") or [])
        names = {
            str(f.get("name") or "")
            for f in fields
            if isinstance(f, dict)
        }
        try:
            from app.ai_brief_cues import model_is_equipment_roster

            is_equipment = model_is_equipment_roster(mid)
        except Exception:  # noqa: BLE001
            is_equipment = _model_matches(mid, _EQUIPMENT_MODEL_TOKENS)
        is_rate = _model_matches(mid, _RATE_MODEL_TOKENS)
        is_site = any(
            tok in mid for tok in ("studio", "facility", "branch", "clinic", "hotel")
        )
        for field in fields:
            if not isinstance(field, dict) or field.get("ttype") != "selection":
                continue
            fname = str(field.get("name") or "")
            pairs = parse_selection_literal(field.get("selection")) or []
            keys = {k for k, _ in pairs}
            labels = {lbl for _, lbl in pairs}
            if (
                brief.equipment_types
                and is_equipment
                and _field_matches(fname, _TYPE_FIELD_TOKENS)
                and _should_rewrite_types(
                    keys,
                    brief.equipment_types,
                    brief.banned_selection_keys,
                    other_tables=tuple(c.equipment_types for c in _COLLOCATIONS),
                    labels=labels,
                )
            ):
                if _rewrite_selection(field, brief.equipment_types):
                    notes.append(f"briefing: equipment types on {mid}.{fname}")
            if (
                brief.rate_uoms
                and is_rate
                and _field_matches(fname, _UOM_FIELD_TOKENS)
                and _should_rewrite_types(
                    keys,
                    brief.rate_uoms,
                    brief.banned_selection_keys,
                    other_tables=tuple(c.rate_uoms for c in _COLLOCATIONS if c.rate_uoms),
                    labels=labels,
                )
            ):
                if _rewrite_selection(field, brief.rate_uoms):
                    notes.append(f"briefing: rate UOMs on {mid}.{fname}")
            if (
                brief.specialty_types
                and is_site
                and _field_matches(fname, _SPECIALTY_FIELD_TOKENS)
                and _should_rewrite_types(
                    keys,
                    brief.specialty_types,
                    brief.banned_selection_keys,
                    other_tables=tuple(c.specialty_types for c in _COLLOCATIONS if c.specialty_types),
                    labels=labels,
                )
            ):
                if _rewrite_selection(field, brief.specialty_types):
                    notes.append(f"briefing: specialties on {mid}.{fname}")
            # Rewrite only existing Type fields with placeholder keys.
            # Do NOT invent x_type here — invent stays behind is_equipment / roster gate.
            if (
                brief.equipment_types
                and _field_matches(fname, _TYPE_FIELD_TOKENS)
                and keys <= _GENERIC_SELECTION_KEYS
                and _rewrite_selection(field, brief.equipment_types)
            ):
                notes.append(f"briefing: placeholder types on {mid}.{fname}")
        if (
            brief.equipment_types
            and is_equipment
            and not any(_field_matches(n, _TYPE_FIELD_TOKENS) for n in names)
        ):
            fields.append(
                {
                    "name": "x_type",
                    "ttype": "selection",
                    "string": "Type",
                    "selection": serialize_selection(brief.equipment_types),
                    "source": "domain_briefing",
                }
            )
            model["fields"] = fields
            notes.append(f"briefing: added x_type on {mid}")
        if (
            brief.rate_uoms
            and is_rate
            and not any(_field_matches(n, _UOM_FIELD_TOKENS) for n in names)
        ):
            fields.append(
                {
                    "name": "x_uom",
                    "ttype": "selection",
                    "string": "Unit",
                    "selection": serialize_selection(brief.rate_uoms),
                    "source": "domain_briefing",
                }
            )
            model["fields"] = fields
            notes.append(f"briefing: added x_uom on {mid}")
    return notes


def briefing_prompt_block(briefing: DomainBriefing | None) -> str:
    if briefing is None:
        return ""
    return briefing.prompt_block()


__all__ = [
    "DomainBriefing",
    "apply_briefing_to_draft",
    "attach_domain_briefing",
    "briefing_from_dict",
    "briefing_prompt_block",
    "build_domain_briefing",
]
