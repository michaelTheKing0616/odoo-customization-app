"""Shared operator-brief cues — stated states, stock menu parent, invent gates.

Prompt understanding floor for residual full_app (Flash-off deterministic):
when the brief enumerates workflow states, names a stock menu parent, or omits
Type/category cues, Contract + Generate must honor those cues end-to-end.
Not Vehicle-only — any residual with the same cue shape.

Also: one materialization per named notes cue. When the brief names Assignment
Note / Remarks / … (or implies a single notes field), emit exactly one field —
prefer Multiline text on the primary for optional note text, or a single M2O
when clearly a link-to-record — never both with the same label/stem. Drop generic
Notes/Description siblings from packs or padding.

Same invent family as Type: never invent Priority/Urgency/Importance Selection
without a clear brief cue.

Same invent family for Rate/Unit/UOM Selection compounds (Rate Unit, UoM, …) —
rental/pricing domain bleed must not land on a request doc with no pricing language.

Type gate covers compound labels («Vehicle Type», «Request Category», …) — not only
bare Type/Category/Kind/Class.
"""

from __future__ import annotations

import re
from typing import Any

# Document / workflow nouns — not equipment rosters even if "vehicle" appears.
_DOCUMENT_MODEL_TOKENS = (
    "request",
    "order",
    "ticket",
    "booking",
    "reservation",
    "loan",
    "checkout",
    "check_out",
    "assignment",
    "application",
    "claim",
    "expense",
    "leave",
    "approval",
    "submission",
    "requisition",
    "inquiry",
    "enquiry",
    "complaint",
    "incident",
    "case",
    "task",
    "job",
    "workorder",
    "work_order",
)

_EQUIPMENT_ROSTER_TOKENS = (
    "equipment",
    "asset",
    "gear",
    "instrument",
    "vehicle",
    "tool",
    "fleet_vehicle",
)

# Brief Type/category cue — invent only when clearly asked.
_TYPE_CUE_RE = re.compile(
    r"(?i)\b("
    r"type\s*(?:selection|field|dropdown|column)?"
    r"|category\s*(?:selection|field|dropdown|column)?"
    r"|vehicle\s+type"
    r"|equipment\s+type"
    r"|asset\s+(?:type|class|category)"
    r"|class(?:ification)?"
    r"|kind\s+of\b"
    r")\b"
)

# Brief Priority/Urgency/Importance cue — invent only when clearly asked (Type family).
_PRIORITY_CUE_RE = re.compile(
    r"(?i)\b("
    r"priority\s*(?:selection|field|dropdown|column|level)?"
    r"|urgency\s*(?:selection|field|dropdown|column)?"
    r"|importance\s*(?:selection|field|dropdown|column)?"
    r"|priority\s+level"
    r"|set\s+(?:a\s+)?priority"
    r")\b"
)

# Brief Rate/pricing/UOM cue — invent Rate Unit only when clearly asked.
_RATE_CUE_RE = re.compile(
    r"(?i)\b("
    r"rate\s*unit"
    r"|rate\s*(?:selection|field|dropdown|column|card|plan)?"
    r"|pricing"
    r"|price\s*list|pricelist"
    r"|tariff"
    r"|hourly\s+rate|daily\s+rate"
    r"|per\s+(?:hour|day|week|night|session)"
    r"|\buom\b|unit\s+of\s+measure"
    r"|billing\s+unit"
    r")\b"
)

# Compound Type-family label/name tokens (Vehicle Type, Request Category, …).
_TYPE_INVENT_NAME_RE = re.compile(
    r"(?i)^x_(?:\w+_)?(?:type|category|kind|class)$"
    r"|^x_(?:type|category|kind|class)_\w+$"
)
_TYPE_INVENT_STRING_RE = re.compile(
    r"(?i)^(?:[\w/&-]+\s+)*(?:type|category|kind|class)$"
    r"|^(?:type|category|kind|class)$"
)

# Compound Rate/Unit/UOM invent family.
_RATE_INVENT_NAME_RE = re.compile(
    r"(?i)^x_(?:\w+_)?(?:rate_unit|rate_uom|rate_type|uom|unit)$"
    r"|^x_(?:rate_unit|rate_uom|uom|unit)_\w+$"
)
_RATE_INVENT_STRING_RE = re.compile(
    r"(?i)^(?:[\w/&-]+\s+)*(?:rate\s*unit|rate\s*uom|rate\s*type|uom|"
    r"unit\s+of\s+measure|billing\s+unit)$"
    r"|^(?:rate\s*unit|unit|uom)$"
)


# Stock app label → (module, preferred parent menu xml id).
_STOCK_MENU_PARENTS: dict[str, tuple[str, str]] = {
    "fleet": ("fleet", "fleet.menu_root"),
    "fleet management": ("fleet", "fleet.menu_root"),
    "vehicles": ("fleet", "fleet.menu_root"),
    "hr": ("hr", "hr.menu_hr_root"),
    "human resources": ("hr", "hr.menu_hr_root"),
    "employees": ("hr", "hr.menu_hr_root"),
    "employee": ("hr", "hr.menu_hr_root"),
    "time off": ("hr_holidays", "hr_holidays.menu_hr_holidays_root"),
    "time-off": ("hr_holidays", "hr_holidays.menu_hr_holidays_root"),
    "sales": ("sale", "sale.sale_menu_root"),
    "sale": ("sale", "sale.sale_menu_root"),
    "crm": ("crm", "crm.crm_menu_root"),
    "project": ("project", "project.menu_main_pm"),
    "projects": ("project", "project.menu_main_pm"),
    "inventory": ("stock", "stock.menu_stock_root"),
    "stock": ("stock", "stock.menu_stock_root"),
    "purchase": ("purchase", "purchase.menu_purchase_root"),
    "purchases": ("purchase", "purchase.menu_purchase_root"),
    "accounting": ("account", "account.menu_finance"),
    "invoicing": ("account", "account.menu_finance"),
    "contacts": ("contacts", "contacts.menu_contacts"),
    "calendar": ("calendar", "calendar.mail_menu_calendar"),
}

_STATE_CHAIN_RE = re.compile(
    r"(?i)(?:\bstate\b|\bstatus\b|\bworkflow\b|\blist\s*/\s*kanban\b|\bby\s+state\b)"
    r"[^.\n]{0,40}?"
    r"(?:\(|:)?\s*"
    r"("
    r"[A-Za-z][A-Za-z0-9_ /\-–→>]+?"
    r"(?:Done|Cancelled|Canceled|Closed|Completed|Refused|Rejected|Approved)"
    r")"
    r"\s*\)?"
)
_STATE_SELECTION_RE = re.compile(
    r"(?i)\bstate\s+selection\s*\(\s*([^)]+?)\s*\)"
)
_ARROW_SPLIT_RE = re.compile(r"\s*(?:→|->|—|–|/)\s*")

# Named note phrases — stripping these leaves only bare «notes» cues.
_NAMED_NOTE_PHRASE_RE = re.compile(
    r"(?i)\b(?:"
    r"assignment\s+notes?"
    r"|delivery\s+notes?"
    r"|clinical\s+notes?"
    r"|pharmacy\s+notes?"
    r"|operative\s+notes?"
    r"|internal\s+notes?"
    r"|manager\s+(?:notes?|comments?|remarks?)"
    r"|doctor\s+notes?"
    r"|patient\s+notes?"
    r"|visit\s+notes?"
    r"|special\s+instructions?"
    r"|block\s+notes?"
    r"|remarks?"
    r"|comments?"
    r")\b"
)
_BARE_NOTES_CUE_RE = re.compile(r"(?i)\bnotes?\b")
_BARE_DESCRIPTION_CUE_RE = re.compile(r"(?i)\bdescriptions?\b")

_GENERIC_NOTE_NAMES = frozenset(
    {
        "x_notes",
        "x_note",
        "x_description",
        "x_comment",
        "x_comments",
        "x_remark",
        "x_remarks",
    }
)
_GENERIC_NOTE_LABELS = frozenset(
    {
        "notes",
        "note",
        "description",
        "comment",
        "comments",
        "remark",
        "remarks",
    }
)
_NOTES_SURFACE_TOKEN_RE = re.compile(
    r"(?i)\b(notes?|remarks?|comments?|description|instructions?)\b"
)


def _snake_state(label: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    aliases = {
        "canceled": "cancelled",
        "complete": "done",
        "completed": "done",
        "rejected": "refused",
        "reject": "refused",
        "ok": "done",
    }
    return aliases.get(text, text)


def stated_workflow_states(prompt: str) -> list[str]:
    """Ordered workflow keys when the brief enumerates them (incl. terminal Done)."""
    text = prompt or ""
    raw = ""
    # Prefer constraint AST machine (handles Approved/Refused → Done).
    try:
        from app.ai_constraint_ast import _STATE_MACHINE_RE, _normalize_state_options

        sm = _STATE_MACHINE_RE.search(text)
        if sm:
            raw = _normalize_state_options(sm.group(1))
    except Exception:  # noqa: BLE001
        raw = ""
    if not raw:
        m = _STATE_SELECTION_RE.search(text)
        if m:
            raw = m.group(1)
    if not raw:
        # Parenthetical chain after "state" / "by state"
        m = re.search(
            r"(?i)\(\s*(Draft\b[^)]{3,120})\)",
            text,
        )
        if m:
            raw = m.group(1)
    if not raw:
        return []
    # Approved/Refused → two states; arrows → separators
    chunk = re.sub(r"(?i)\b([A-Za-z]+)/([A-Za-z]+)\b", r"\1 / \2", raw)
    chunk = re.sub(r"\s*[→\-–>]+\s*", " / ", chunk)
    parts = [p.strip(" .") for p in re.split(r"\s*/\s*", chunk) if p.strip(" .")]
    keys: list[str] = []
    for part in parts:
        key = _snake_state(part)
        if key and key not in keys:
            keys.append(key)
    return keys


def brief_has_type_cue(prompt: str) -> bool:
    """True when the brief clearly asks for a Type/category selection."""
    return bool(_TYPE_CUE_RE.search(prompt or ""))


def brief_has_priority_cue(prompt: str) -> bool:
    """True when the brief clearly asks for Priority/Urgency/Importance."""
    return bool(_PRIORITY_CUE_RE.search(prompt or ""))


def brief_has_rate_cue(prompt: str) -> bool:
    """True when the brief clearly asks for Rate/pricing/UOM Selection."""
    return bool(_RATE_CUE_RE.search(prompt or ""))


def model_is_equipment_roster(mid: str) -> bool:
    """Equipment/asset roster models may carry Type; request/order docs must not."""
    hay = (mid or "").replace("x_", "").replace(".", "_").lower()
    if any(tok in hay for tok in _DOCUMENT_MODEL_TOKENS):
        return False
    return any(tok in hay for tok in _EQUIPMENT_ROSTER_TOKENS)


def stated_menu_parent(prompt: str) -> tuple[str, str, str] | None:
    """Return (label, module, parent_xml_id) when the brief names a stock menu parent."""
    try:
        from app.ai_constraint_ast import _resolve_menu_parent
    except Exception:  # noqa: BLE001
        _resolve_menu_parent = None  # type: ignore[assignment]
    label = ""
    if _resolve_menu_parent is not None:
        try:
            label = str(_resolve_menu_parent(prompt or "") or "").strip()
        except Exception:  # noqa: BLE001
            label = ""
    if not label:
        m = re.search(
            r"(?i)\bmenu\s+under\s+([A-Za-z][A-Za-z0-9 &\-/]+?)(?:\s+or\s+|\s*[—–\-.|]|$)",
            prompt or "",
        )
        if m:
            label = m.group(1).strip(" .,—–-")
            or_m = re.match(r"(?i)^(.+?)\s+or\s+(.+)$", label)
            if or_m and _resolve_menu_parent is not None:
                try:
                    label = str(_resolve_menu_parent(prompt or "") or label)
                except Exception:  # noqa: BLE001
                    label = or_m.group(1).strip()
    if not label:
        return None
    key = re.sub(r"\s+", " ", label).strip().lower()
    if key in _STOCK_MENU_PARENTS:
        mod, xml = _STOCK_MENU_PARENTS[key]
        return (label.strip(), mod, xml)
    # Soft match first token
    first = key.split()[0] if key else ""
    if first in _STOCK_MENU_PARENTS:
        mod, xml = _STOCK_MENU_PARENTS[first]
        return (label.strip(), mod, xml)
    # Unknown stock label — still expose module guess via grain helper
    try:
        from app.ai_grain import parent_menu_xml_id_for_module

        mod = first.replace(" ", "_")
        xml = parent_menu_xml_id_for_module(mod)
        if xml:
            return (label.strip(), mod, xml)
    except Exception:  # noqa: BLE001
        pass
    return None


def selection_literal_from_keys(keys: list[str]) -> str:
    pairs = []
    for key in keys:
        label = key.replace("_", " ").title()
        if key == "done":
            label = "Done"
        pairs.append(f"('{key}','{label}')")
    return "[" + ",".join(pairs) + "]"


def transitions_for_states(keys: list[str]) -> list[list[str]]:
    """Linear + approve/refuse branch; Done follows approved when present."""
    if not keys:
        return []
    keyset = set(keys)
    edges: list[list[str]] = []
    # Prefer explicit approval branch when both approved and refused exist.
    if "draft" in keyset and "submitted" in keyset:
        edges.append(["draft", "submitted"])
    if "submitted" in keyset and "approved" in keyset:
        edges.append(["submitted", "approved"])
    if "submitted" in keyset and "refused" in keyset:
        edges.append(["submitted", "refused"])
    if "approved" in keyset and "done" in keyset:
        edges.append(["approved", "done"])
    # Fallback chain for non-approval workflows
    if not edges:
        for a, b in zip(keys, keys[1:]):
            edges.append([a, b])
    return edges


def brief_asks_generic_notes(prompt: str) -> bool:
    """True when the brief asks for a bare Notes field (not Assignment Note / Remarks)."""
    stripped = _NAMED_NOTE_PHRASE_RE.sub(" ", prompt or "")
    return bool(_BARE_NOTES_CUE_RE.search(stripped))


def brief_asks_description(prompt: str) -> bool:
    """True when the brief explicitly cues a Description free-text field."""
    return bool(_BARE_DESCRIPTION_CUE_RE.search(prompt or ""))


def brief_has_named_notes_cue(prompt: str) -> bool:
    """True when the brief names a specific notes/comments/remarks surface."""
    return bool(_NAMED_NOTE_PHRASE_RE.search(prompt or ""))


def is_bare_generic_notes_field(field: dict[str, Any]) -> bool:
    """Pack/pad Notes|Description chrome — not «Assignment Note» / «Remarks»."""
    if not isinstance(field, dict):
        return False
    ttype = str(field.get("ttype") or "").lower()
    if ttype and ttype not in {"text", "html", "char"}:
        return False
    name = str(field.get("name") or "").strip().lower()
    label = str(field.get("string") or "").strip().lower()
    # Only bare Notes / Description are generic siblings worth dropping.
    if name in {"x_notes", "x_note"} and (not label or label in {"notes", "note"}):
        return True
    if name == "x_description" and (not label or label == "description"):
        return True
    if label in {"notes", "note", "description"} and name.startswith("x_") and ttype in {
        "text",
        "html",
        "",
    }:
        return True
    return False


def is_named_notes_field(field: dict[str, Any]) -> bool:
    """Brief-named free-text note surface (Assignment Note, Remarks, Clinical Notes, …)."""
    if not isinstance(field, dict):
        return False
    ttype = str(field.get("ttype") or "").lower()
    if ttype not in {"text", "html", "char", ""}:
        return False
    if is_bare_generic_notes_field(field):
        return False
    name = str(field.get("name") or "")
    label = str(field.get("string") or "").strip()
    low_label = label.lower()
    low_name = name.lower()
    # Remarks / Comments as the field label are the named surface (not generic Notes).
    if low_label in {"remarks", "remark", "comments", "comment"}:
        return True
    if low_name in {"x_remarks", "x_remark", "x_comments", "x_comment"}:
        return True
    blob = f"{name} {label}".lower()
    if not _NOTES_SURFACE_TOKEN_RE.search(blob):
        return False
    if label and low_label not in {"notes", "note", "description"}:
        return True
    if low_name not in _GENERIC_NOTE_NAMES and _NOTES_SURFACE_TOKEN_RE.search(low_name):
        return True
    return False


def model_has_notes_surface(fields: list[dict[str, Any]] | None) -> bool:
    """True when the model already carries any notes-like free-text field."""
    for field in fields or []:
        if not isinstance(field, dict):
            continue
        if is_named_notes_field(field) or is_bare_generic_notes_field(field):
            return True
        ttype = str(field.get("ttype") or "").lower()
        if ttype in {"text", "html"} and _NOTES_SURFACE_TOKEN_RE.search(
            f"{field.get('name') or ''} {field.get('string') or ''}"
        ):
            return True
    return False


def should_skip_generic_notes_pad(
    fields: list[dict[str, Any]] | None,
    *,
    prompt: str = "",
) -> bool:
    """Pads must not invent Notes when a named note exists or the brief named one."""
    named_present = any(
        isinstance(f, dict) and is_named_notes_field(f) for f in (fields or [])
    )
    if named_present:
        return True
    if brief_has_named_notes_cue(prompt):
        return True
    generics = [
        f for f in (fields or []) if isinstance(f, dict) and is_bare_generic_notes_field(f)
    ]
    if generics:
        return True
    return False


def honor_stated_brief_cues(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Materialize stated states, stock menu parent, no-invent Type/Priority/Rate, one notes surface."""
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    if not text or not isinstance(draft, dict):
        return notes
    notes.extend(_honor_stated_states(draft, text))
    notes.extend(_honor_menu_parent(draft, text))
    notes.extend(_drop_uncued_type_fields(draft, text))
    notes.extend(_drop_uncued_priority_fields(draft, text))
    notes.extend(_drop_uncued_rate_unit_fields(draft, text))
    notes.extend(dedupe_notes_surfaces(draft, prompt=text))
    return notes



def _notes_cue_stem(field: dict[str, Any]) -> str | None:
    """Stem for same-cue notes materializations (text or M2O link).

    «Assignment Note» text and «Assignment Note» M2O share stem ``assignment note``.
    """
    if not isinstance(field, dict):
        return None
    ttype = str(field.get("ttype") or "").lower()
    if ttype and ttype not in {"text", "html", "char", "many2one", ""}:
        return None
    name = str(field.get("name") or "").strip().lower()
    label = str(field.get("string") or "").strip().lower()
    stem = name
    if stem.startswith("x_"):
        stem = stem[2:]
    if stem.endswith("_id"):
        stem = stem[:-3]
    stem = stem.replace("_", " ").strip()
    blob = f"{name} {label} {stem}"
    if not _NOTES_SURFACE_TOKEN_RE.search(blob):
        return None
    key = label if label and label not in {"notes", "note", "description"} else stem
    if not key:
        key = label or stem
    key = re.sub(r"\s+", " ", key).strip()
    key = re.sub(r"\bnotes\b", "note", key)
    key = re.sub(r"\bcomments\b", "comment", key)
    key = re.sub(r"\bremarks\b", "remark", key)
    return key or None


def _collapse_cross_ttype_notes(
    fields: list[dict[str, Any]], mid: str
) -> tuple[set[str], list[str]]:
    """One materialization per named notes cue across ttypes (text vs M2O).

    Prefer free-text Multiline when both a note-text and a same-stem M2O exist.
    """
    drop_names: set[str] = set()
    notes: list[str] = []
    by_stem: dict[str, list[dict[str, Any]]] = {}
    for field in fields:
        stem = _notes_cue_stem(field)
        if not stem:
            continue
        by_stem.setdefault(stem, []).append(field)
    for stem, group in by_stem.items():
        if len(group) < 2:
            continue
        texts = [
            f
            for f in group
            if str(f.get("ttype") or "").lower() in {"text", "html", "char", ""}
        ]
        m2os = [f for f in group if str(f.get("ttype") or "").lower() == "many2one"]
        if texts and m2os:
            for m in m2os:
                n = str(m.get("name") or "")
                if n:
                    drop_names.add(n)
            keep = str(texts[0].get("name") or texts[0].get("string") or "")
            notes.append(
                f"brief_cues: collapsed cross-ttype notes cue «{stem}» on {mid} "
                f"— kept text {keep}, dropped M2O"
            )
        elif len(texts) > 1:
            keep_name = str(texts[0].get("name") or "")
            for t in texts[1:]:
                n = str(t.get("name") or "")
                if n and n != keep_name:
                    drop_names.add(n)
            if drop_names:
                notes.append(
                    f"brief_cues: collapsed duplicate notes text «{stem}» on {mid} "
                    f"(kept {keep_name})"
                )
        elif len(m2os) > 1:
            keep_name = str(m2os[0].get("name") or "")
            for m in m2os[1:]:
                n = str(m.get("name") or "")
                if n and n != keep_name:
                    drop_names.add(n)
            if any(str(m.get("name") or "") != keep_name for m in m2os[1:]):
                notes.append(
                    f"brief_cues: collapsed duplicate notes M2O «{stem}» on {mid} "
                    f"(kept {keep_name})"
                )
    return drop_names, notes

def dedupe_notes_surfaces(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """One notes surface per cue — prefer brief-named; drop generic Notes/Description siblings.

    Class-wide (not Vehicle-only):
    - Named note (Assignment Note, Remarks, …) → drop bare Notes/Description on same model
    - Single bare «notes» cue → keep one Notes; drop uncued Description sibling
    - No two free-text note siblings without two distinct cues
    - Cross-ttype same-label / same-stem (text + M2O «Assignment Note») → keep one
      (prefer Multiline text for optional note cues)
    """
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    if not isinstance(draft, dict):
        return notes
    wants_generic_notes = brief_asks_generic_notes(text)
    wants_description = brief_asks_description(text)
    has_named_cue = brief_has_named_notes_cue(text)
    dropped_any = False
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        if not fields:
            continue
        named = [f for f in fields if is_named_notes_field(f)]
        generics = [f for f in fields if is_bare_generic_notes_field(f)]
        drop_names: set[str] = set()
        cross_drop, cross_notes = _collapse_cross_ttype_notes(fields, mid)
        if cross_drop:
            drop_names |= cross_drop
            notes.extend(cross_notes)

        if named and generics:
            for g in generics:
                n = str(g.get("name") or "")
                if n:
                    drop_names.add(n)
            if drop_names:
                prefer = str(named[0].get("string") or named[0].get("name") or "")
                notes.append(
                    f"brief_cues: dropped generic notes on {mid} "
                    f"({', '.join(sorted(drop_names))}) — prefer named {prefer}"
                )
        elif len(generics) > 1 and wants_generic_notes and wants_description:
            pass  # two cues → keep Notes + Description
        elif len(generics) > 1:
            keep_name: str | None = None
            if wants_generic_notes and not wants_description:
                keep_name = next(
                    (
                        str(g.get("name"))
                        for g in generics
                        if str(g.get("name") or "") in {"x_notes", "x_note"}
                        or str(g.get("string") or "").lower() in {"notes", "note"}
                    ),
                    None,
                )
            elif wants_description and not wants_generic_notes:
                keep_name = next(
                    (
                        str(g.get("name"))
                        for g in generics
                        if str(g.get("name") or "") == "x_description"
                        or str(g.get("string") or "").lower() == "description"
                    ),
                    None,
                )
            else:
                keep_name = next(
                    (
                        str(g.get("name"))
                        for g in generics
                        if str(g.get("name") or "") in {"x_notes", "x_note"}
                        or str(g.get("string") or "").lower() in {"notes", "note"}
                    ),
                    str(generics[0].get("name") or "") or None,
                )
            if keep_name is None and generics:
                keep_name = str(generics[0].get("name") or "")
            for g in generics:
                n = str(g.get("name") or "")
                if n and n != keep_name:
                    drop_names.add(n)
            if drop_names:
                notes.append(
                    f"brief_cues: collapsed notes surfaces on {mid} "
                    f"(kept {keep_name}, dropped {', '.join(sorted(drop_names))})"
                )
        elif generics and has_named_cue and not wants_generic_notes and not named:
            # Named cue but only generic chrome — drop Description siblings of Notes.
            notes_only = [
                g
                for g in generics
                if str(g.get("name") or "") in {"x_notes", "x_note"}
                or str(g.get("string") or "").lower() in {"notes", "note"}
            ]
            desc = [
                g
                for g in generics
                if str(g.get("name") or "") == "x_description"
                or str(g.get("string") or "").lower() == "description"
            ]
            if notes_only and desc:
                for g in desc:
                    n = str(g.get("name") or "")
                    if n:
                        drop_names.add(n)
                if drop_names:
                    notes.append(
                        f"brief_cues: dropped Description sibling on {mid} "
                        f"(named notes cue; kept Notes)"
                    )
        elif generics and not wants_generic_notes and not wants_description and not has_named_cue:
            for g in generics:
                src = str(g.get("source") or "")
                if src in {"apply_readiness", "senior_shape", "domain_density", "pad"}:
                    n = str(g.get("name") or "")
                    if n:
                        drop_names.add(n)
            if drop_names:
                notes.append(
                    f"brief_cues: dropped unsolicited notes pad on {mid} "
                    f"({', '.join(sorted(drop_names))})"
                )

        if drop_names:
            dropped_any = True
            model["fields"] = [
                f for f in fields if str(f.get("name") or "") not in drop_names
            ]

    if dropped_any:
        try:
            from app.ai_apply_readiness import scrub_unknown_arch_field_refs

            notes.extend(scrub_unknown_arch_field_refs(draft))
        except Exception:  # noqa: BLE001
            pass
    return notes


def _header_models(draft: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        if mid.endswith("_line") or mid.endswith("_party"):
            continue
        if str(model.get("mode") or "new") == "inherit":
            continue
        out.append(model)
    return out


def _honor_stated_states(draft: dict[str, Any], text: str) -> list[str]:
    notes: list[str] = []
    stated = stated_workflow_states(text)
    if not stated:
        return notes
    draft["_stated_states"] = list(stated)
    for model in _header_models(draft):
        mid = str(model.get("model") or "")
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        state_rows = [
            f
            for f in fields
            if str(f.get("name") or "") in {"x_state", "x_status"}
            or str(f.get("string") or "").lower() in {"state", "status"}
        ]
        # Prefer richer stated field (x_state with Done) over truncated x_status.
        primary = None
        for prefer in ("x_state", "x_status"):
            hit = next((f for f in state_rows if f.get("name") == prefer), None)
            if hit is not None:
                primary = hit
                break
        if primary is None and state_rows:
            primary = state_rows[0]
        if primary is None:
            primary = {
                "name": "x_state",
                "ttype": "selection",
                "string": "State",
                "required": True,
                "tracking": True,
                "default": stated[0],
            }
            fields.append(primary)
            model["fields"] = fields
            notes.append(f"brief_cues: added x_state on {mid}")
        fname = str(primary.get("name") or "x_state")
        primary["ttype"] = "selection"
        primary["selection"] = selection_literal_from_keys(stated)
        primary.setdefault("string", "State" if "state" in fname else "Status")
        primary.setdefault("default", stated[0])
        # Drop sibling status/state that would fight the canvas statusbar.
        drop = {
            str(f.get("name") or "")
            for f in fields
            if str(f.get("name") or "") in {"x_state", "x_status"}
            and str(f.get("name") or "") != fname
        }
        if drop:
            model["fields"] = [
                f for f in fields if str(f.get("name") or "") not in drop
            ]
            notes.append(
                f"brief_cues: dropped duplicate {', '.join(sorted(drop))} on {mid}"
            )
        transitions = transitions_for_states(stated)
        model["is_workflow"] = True
        model["state_field"] = {
            "field": fname,
            "states": list(stated),
            "transitions": transitions,
            "statusbar_visible": list(stated),
            "approval": bool({"approved", "refused"} & set(stated)),
        }
        notes.append(
            f"brief_cues: {mid}.{fname} → {len(stated)} stated states "
            f"({', '.join(stated)})"
        )
    # Keep grammar / contract chrome aligned.
    grammar = draft.get("_document_grammar")
    if isinstance(grammar, dict):
        grammar["states"] = list(stated)
        summary = str(grammar.get("summary") or "")
        summary = re.sub(r"\b\d+\s+states\b", f"{len(stated)} states", summary)
        if "states" not in summary and stated:
            summary = (summary + f" · {len(stated)} states").strip(" ·")
        grammar["summary"] = summary
    return notes


def _honor_menu_parent(draft: dict[str, Any], text: str) -> list[str]:
    notes: list[str] = []
    parent = stated_menu_parent(text)
    if not parent:
        return notes
    label, module, xml_id = parent
    draft["_stated_menu_parent"] = {
        "label": label,
        "module": module,
        "xml_id": xml_id,
    }
    depends = [str(d) for d in (draft.get("depends") or []) if d]
    if module and module not in depends:
        depends.append(module)
        draft["depends"] = list(dict.fromkeys(depends))
        notes.append(f"brief_cues: depends += {module}")
    menus = [m for m in (draft.get("menus") or []) if isinstance(m, dict)]
    if not menus:
        return notes
    roots = [
        m
        for m in menus
        if not m.get("parent_xml_id") and not m.get("parent_id") and not m.get("action_xml_id")
    ]
    if not roots:
        # Action menus with no parent — attach the first under stock parent.
        roots = [m for m in menus if not m.get("parent_xml_id") and not m.get("parent_id")]
    if not roots:
        roots = [menus[0]]
    for root in roots:
        old = str(root.get("parent_xml_id") or "")
        if old == xml_id:
            continue
        root["parent_xml_id"] = xml_id
        notes.append(f"brief_cues: menu «{root.get('name')}» under {xml_id} ({label})")
    return notes


def _is_type_invent_field(field: dict[str, Any]) -> bool:
    """True for bare or compound Type/Category/Kind/Class Selection invent."""
    name = str(field.get("name") or "").strip()
    string = str(field.get("string") or "").strip()
    if name in {"x_type", "x_category", "x_kind", "x_class"}:
        return True
    if string.lower() in {"type", "category", "kind", "class"}:
        return True
    if _TYPE_INVENT_NAME_RE.match(name):
        return True
    if string and _TYPE_INVENT_STRING_RE.match(string):
        return True
    return False


def _is_rate_invent_field(field: dict[str, Any]) -> bool:
    """True for Rate Unit / UOM / Unit Selection invent (pricing domain bleed)."""
    name = str(field.get("name") or "").strip()
    string = str(field.get("string") or "").strip()
    if name in {"x_rate_unit", "x_rate_uom", "x_rate_type", "x_uom", "x_unit"}:
        return True
    if string.lower() in {"rate unit", "rate uom", "rate type", "unit", "uom"}:
        return True
    if _RATE_INVENT_NAME_RE.match(name):
        return True
    if string and _RATE_INVENT_STRING_RE.match(string):
        return True
    return False


def _drop_uncued_type_fields(draft: dict[str, Any], text: str) -> list[str]:
    notes: list[str] = []
    if brief_has_type_cue(text):
        return notes
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        # Roster equipment may keep Type only when the model truly is a roster.
        if model_is_equipment_roster(mid):
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        keep: list[dict[str, Any]] = []
        dropped: list[str] = []
        for field in fields:
            name = str(field.get("name") or "")
            string = str(field.get("string") or "").strip().lower()
            source = str(field.get("source") or "")
            is_type = _is_type_invent_field(field)
            if is_type and (
                source
                in {
                    "domain_briefing",
                    "density",
                    "pack_default",
                    "domain_density",
                    "pad",
                    "senior_shape",
                    "apply_readiness",
                    "",
                }
                or str(field.get("ttype") or "") == "selection"
            ):
                dropped.append(name or string)
                continue
            keep.append(field)
        if dropped:
            model["fields"] = keep
            notes.append(
                f"brief_cues: dropped unsolicited Type on {mid} "
                f"({', '.join(dropped)}) — no Type cue in brief"
            )
    return notes


def _drop_uncued_priority_fields(draft: dict[str, Any], text: str) -> list[str]:
    """Drop Priority/Urgency/Importance Selection when the brief has no such cue.

    Same invent family as Type — packs/density/pads must not invent without a cue.
    """
    notes: list[str] = []
    if brief_has_priority_cue(text):
        return notes
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        keep: list[dict[str, Any]] = []
        dropped: list[str] = []
        for field in fields:
            name = str(field.get("name") or "")
            string = str(field.get("string") or "").strip().lower()
            source = str(field.get("source") or "")
            is_priority = (
                name in {"x_priority", "x_urgency", "x_importance"}
                or string in {"priority", "urgency", "importance"}
                or bool(re.match(r"(?i)^x_(?:\w+_)?(?:priority|urgency|importance)$", name))
                or bool(
                    re.match(
                        r"(?i)^(?:[\w/&-]+\s+)*(?:priority|urgency|importance)$",
                        string,
                    )
                )
            )
            if is_priority and (
                source in {"domain_briefing", "density", "pack_default", ""}
                or str(field.get("ttype") or "") == "selection"
            ):
                dropped.append(name or string)
                continue
            keep.append(field)
        if dropped:
            model["fields"] = keep
            notes.append(
                f"brief_cues: dropped unsolicited Priority on {mid} "
                f"({', '.join(dropped)}) — no Priority cue in brief"
            )
    return notes


def _drop_uncued_rate_unit_fields(draft: dict[str, Any], text: str) -> list[str]:
    """Drop Rate Unit / UOM / Unit Selection when the brief has no pricing cue.

    Same invent family as Type/Priority — rental/density/pads must not invent
    Rate Unit on a vehicle request (or any residual) without rate/pricing language.
    """
    notes: list[str] = []
    if brief_has_rate_cue(text):
        return notes
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        # Dedicated rate-card / tariff models may keep UOM when the model is a rate.
        hay = mid.replace("x_", "").replace(".", "_").lower()
        if any(tok in hay for tok in ("rate", "tariff", "pricelist", "price_list")):
            if not any(tok in hay for tok in _DOCUMENT_MODEL_TOKENS):
                continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        keep: list[dict[str, Any]] = []
        dropped: list[str] = []
        for field in fields:
            name = str(field.get("name") or "")
            string = str(field.get("string") or "").strip().lower()
            source = str(field.get("source") or "")
            is_rate = _is_rate_invent_field(field)
            if is_rate and (
                source
                in {
                    "domain_briefing",
                    "density",
                    "pack_default",
                    "domain_density",
                    "pad",
                    "senior_shape",
                    "apply_readiness",
                    "",
                }
                or str(field.get("ttype") or "") == "selection"
            ):
                dropped.append(name or string)
                continue
            keep.append(field)
        if dropped:
            model["fields"] = keep
            notes.append(
                f"brief_cues: dropped unsolicited Rate/Unit on {mid} "
                f"({', '.join(dropped)}) — no Rate cue in brief"
            )
    return notes



__all__ = [
    "brief_asks_description",
    "brief_asks_generic_notes",
    "brief_has_named_notes_cue",
    "brief_has_type_cue",
    "brief_has_priority_cue",
    "brief_has_rate_cue",
    "dedupe_notes_surfaces",
    "honor_stated_brief_cues",
    "is_bare_generic_notes_field",
    "is_named_notes_field",
    "model_has_notes_surface",
    "model_is_equipment_roster",
    "selection_literal_from_keys",
    "should_skip_generic_notes_pad",
    "stated_menu_parent",
    "stated_workflow_states",
    "transitions_for_states",
]
