"""Shared operator-brief cues — stated states, stock menu parent, invent gates.

Prompt understanding floor for residual full_app (Flash-off deterministic):
when the brief enumerates workflow states, names a stock menu parent, or omits
Type/category cues, Contract + Generate must honor those cues end-to-end.
Not Vehicle-only — any residual with the same cue shape.
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


def honor_stated_brief_cues(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Materialize stated states, stock menu parent, and no-invent Type — class-wide."""
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    if not text or not isinstance(draft, dict):
        return notes
    notes.extend(_honor_stated_states(draft, text))
    notes.extend(_honor_menu_parent(draft, text))
    notes.extend(_drop_uncued_type_fields(draft, text))
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
            is_type = (
                name in {"x_type", "x_category", "x_kind", "x_class"}
                or string in {"type", "category", "kind", "class"}
            )
            if is_type and (
                source in {"domain_briefing", "density", "pack_default", ""}
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


__all__ = [
    "brief_has_type_cue",
    "honor_stated_brief_cues",
    "model_is_equipment_roster",
    "selection_literal_from_keys",
    "stated_menu_parent",
    "stated_workflow_states",
    "transitions_for_states",
]
