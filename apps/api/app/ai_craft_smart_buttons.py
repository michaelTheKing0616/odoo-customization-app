"""Craft smart buttons — optional Diagnosis Nice-to-have chips (Propose→confirm→Apply).

Stock→residual navigation (e.g. «Visits» on Employees when Host→Employee) is never
silently invented. Instead we propose high-signal chips on Diagnosis for every grain
that has residual↔stock M2O signal; Generate stamps only chips the user kept.
Prefer/inherit without a residual register still proposes nothing (no spam).
Punch partner_tie stays on its own invent path when craft is empty.
"""

from __future__ import annotations

import re
from typing import Any

# High-signal stock hosts only — never selection chrome, never every M2O.
_CRAFT_HOST_PRIORITY: dict[str, int] = {
    "hr.employee": 2,
    "res.partner": 1,
}

_TARGET_ALIASES: dict[str, str] = {
    "employee": "hr.employee",
    "employees": "hr.employee",
    "staff": "hr.employee",
    "hr.employee": "hr.employee",
    "contact": "res.partner",
    "contacts": "res.partner",
    "partner": "res.partner",
    "company": "res.partner",
    "customer": "res.partner",
    "res.partner": "res.partner",
}

_ARROW_RE = re.compile(r"(?i)^(.+?)\s*(?:→|->|⟶)\s*(.+)$")
_NEW_MODEL_RE = re.compile(
    r"(?i)^New model\s+(x_[\w]+)\s*(?:\(([^)]+)\))?\s*$"
)
_HOST_LABELS = {
    "hr.employee": "Employees",
    "res.partner": "Contacts",
}


def _slug_field(label: str) -> str:
    leaf = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    if not leaf:
        leaf = "related"
    if leaf.endswith("_id"):
        return f"x_{leaf}" if not leaf.startswith("x_") else leaf
    return f"x_{leaf}_id"


def _residual_from_constraints(constraints: list[str]) -> tuple[str, str]:
    for row in constraints or []:
        m = _NEW_MODEL_RE.match(str(row).strip())
        if m:
            mid = m.group(1)
            title = (m.group(2) or mid.replace("x_", "").replace("_", " ")).strip()
            return mid, title
    return "", ""


def _button_label(*, title: str, prompt: str, on_model: str) -> str:
    blob = f"{title} {prompt}".lower()
    if re.search(r"\b(visitor|guest|visit)\b", blob):
        return "Visits"
    if on_model == "hr.employee" and re.search(r"\bhost\b", blob):
        return "Visits"
    name = (title or "Records").strip()
    if name.lower().endswith("y") and not name.lower().endswith(("ay", "ey", "oy", "uy")):
        return name[:-1] + "ies"
    if name.lower().endswith("s"):
        return name
    return f"{name}s"


def _chip_label(button_label: str, on_model: str) -> str:
    host = _HOST_LABELS.get(on_model, on_model)
    return f"«{button_label}» on {host}"


def _relations_from_constraints(constraints: list[str]) -> list[tuple[str, str, str]]:
    """Return (field_label, on_model, priority_key) from Must-do arrows."""
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for row in constraints or []:
        text = str(row).strip()
        m = _ARROW_RE.match(text)
        if not m:
            continue
        fname = m.group(1).strip()
        target_raw = m.group(2).strip().lower()
        # Skip selection chrome ("Purpose selection (…)") — already not arrow-shaped.
        if "selection" in target_raw:
            continue
        # Take last token / known alias
        target = target_raw
        for part in re.split(r"[/\s,]+", target_raw):
            if part in _TARGET_ALIASES:
                target = part
                break
        on_model = _TARGET_ALIASES.get(target)
        if not on_model or on_model not in _CRAFT_HOST_PRIORITY:
            continue
        if on_model in seen:
            continue
        seen.add(on_model)
        out.append((fname, on_model, on_model))
    return out


def propose_craft_smart_buttons(
    prompt: str,
    understanding: Any = None,
) -> list[dict[str, Any]]:
    """Deterministic stock→residual craft proposals for Diagnosis Nice-to-have chips.

    All grains (full_app / field_pack / feature_slice) may receive proposals when
    high-signal M2O→stock-host relations exist. Cap 2. Default ON only for the
    single highest-signal host (Employee if Host→Employee; else Contact if
    Company→Contact). Prefer/inherit without a residual register proposes nothing
    (no spam); never invent silent residual invent on Generate.
    """
    grain = "full_app"
    inherit = False
    constraints: list[str] = []
    title = ""
    if understanding is not None:
        grain = str(getattr(understanding, "grain", None) or "full_app")
        inherit = bool(getattr(understanding, "inherit_existing", False))
        constraints = list(getattr(understanding, "constraints", None) or [])
        title = str(getattr(understanding, "title", "") or "")
        if isinstance(understanding, dict):
            grain = str(understanding.get("grain") or grain)
            inherit = bool(understanding.get("inherit_existing"))
            constraints = list(understanding.get("constraints") or constraints)
            title = str(understanding.get("title") or title)

    residual_model, residual_title = _residual_from_constraints(constraints)
    rels = _relations_from_constraints(constraints)

    # Prefer/inherit field_pack without a residual x_ register: nothing useful to
    # button to — don't spam Nice-to-have chips on Contacts-only briefs.
    if inherit and not residual_model:
        return []

    if not residual_model:
        # Residual-shaped briefs (any grain) may omit an explicit "New model" line;
        # fall back to title slug so field_pack/feature_slice still get chips when
        # high-signal Host/Company arrows exist.
        if not rels:
            return []
        residual_title = title or "App"
        slug = re.sub(r"[^a-z0-9]+", "_", residual_title.lower()).strip("_")[:40] or "custom"
        residual_model = f"x_{slug}" if not slug.startswith("x_") else slug

    if not rels:
        return []

    rels.sort(key=lambda r: -_CRAFT_HOST_PRIORITY.get(r[1], 0))
    rels = rels[:2]
    proposals: list[dict[str, Any]] = []
    for idx, (field_label, on_model, _) in enumerate(rels):
        button = _button_label(title=residual_title or title, prompt=prompt or "", on_model=on_model)
        relation_field = _slug_field(field_label)
        chip = _chip_label(button, on_model)
        default_on = idx == 0  # highest-signal only
        proposals.append(
            {
                "id": f"craft:{on_model}:{relation_field}",
                "on_model": on_model,
                "label": button,
                "related_model": residual_model,
                "relation_field": relation_field,
                "rationale": (
                    f"{field_label}→{_HOST_LABELS.get(on_model, on_model)} "
                    f"is many residual rows per stock host — optional smart button"
                ),
                "default_on": default_on,
                "chip_label": chip,
                "source": "craft_proposal",
            }
        )
    return proposals


def _confirmed_craft_list(draft: dict[str, Any]) -> list[dict[str, Any]]:
    u = draft.get("_understanding")
    if not isinstance(u, dict):
        return []
    raw = u.get("craft_smart_buttons")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        on_model = str(row.get("on_model") or "").strip()
        related = str(row.get("related_model") or "").strip()
        if not on_model or not related:
            continue
        out.append(row)
    return out[:2]


def _match_relation_field(
    draft: dict[str, Any],
    *,
    related_model: str,
    on_model: str,
    preferred: str,
) -> str:
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        if str(model.get("model") or "") != related_model:
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        # Exact preferred name
        for f in fields:
            if str(f.get("name") or "") == preferred and str(f.get("ttype") or "") == "many2one":
                if str(f.get("relation") or "") in {"", on_model}:
                    return preferred
        # Any M2O to host
        for f in fields:
            if str(f.get("ttype") or "") != "many2one":
                continue
            if str(f.get("relation") or "") == on_model:
                return str(f.get("name") or preferred)
    return preferred


def craft_button_keys(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for row in rows:
        on_model = str(row.get("on_model") or row.get("host_model") or "")
        related = str(row.get("related_model") or row.get("residual_model") or "")
        if on_model and related:
            keys.add((on_model, related))
    return keys


def is_craft_confirmed_button(btn: dict[str, Any], confirmed: list[dict[str, Any]]) -> bool:
    """True only when the button's host↔residual pair is in confirmed craft.

    Source tags alone never authorize retention — illicit invent can be stamped
    ``craft_confirmed``; empty craft must drop all stock-host buttons.
    """
    if not confirmed:
        return False
    on_model = str(btn.get("on_model") or btn.get("host_model") or "")
    related = str(btn.get("related_model") or btn.get("residual_model") or "")
    return (on_model, related) in craft_button_keys(confirmed)


def apply_confirmed_craft_smart_buttons(
    draft: dict[str, Any], *, prompt: str = ""
) -> list[str]:
    """Stamp Diagnosis-confirmed craft smart buttons onto any grain that can host them."""
    notes: list[str] = []
    confirmed = _confirmed_craft_list(draft)
    if not confirmed:
        return notes
    existing = {
        (
            str(b.get("on_model") or ""),
            str(b.get("related_model") or ""),
            str(b.get("relation_field") or ""),
        )
        for b in (draft.get("smart_buttons") or [])
        if isinstance(b, dict)
    }
    added: list[str] = []
    for row in confirmed:
        on_model = str(row.get("on_model") or "")
        related = str(row.get("related_model") or "")
        preferred = str(row.get("relation_field") or "")
        label = str(row.get("label") or "").strip() or "Records"
        if not on_model or not related:
            continue
        fname = _match_relation_field(
            draft, related_model=related, on_model=on_model, preferred=preferred
        )
        key = (on_model, related, fname)
        if key in existing:
            # Ensure source + craft label (humanize must not leave «Visitor Logs»).
            for b in draft.get("smart_buttons") or []:
                if (
                    isinstance(b, dict)
                    and str(b.get("on_model") or "") == on_model
                    and str(b.get("related_model") or "") == related
                ):
                    b["source"] = "craft_confirmed"
                    if label:
                        b["label"] = label
                        if b.get("string"):
                            b["string"] = label
            continue
        if any(k[0] == on_model and k[1] == related for k in existing):
            continue
        icon = "fa-id-badge" if on_model == "hr.employee" else "fa-id-card-o"
        draft.setdefault("smart_buttons", []).append(
            {
                "on_model": on_model,
                "label": label,
                "related_model": related,
                "relation_field": fname,
                "icon": icon,
                "requires_inherit_view": True,
                "note": "Craft smart button confirmed on Diagnosis",
                "source": "craft_confirmed",
            }
        )
        existing.add(key)
        added.append(f"{on_model}←{related}.{fname}")
        dep = "hr" if on_model == "hr.employee" else "contacts"
        depends = [str(x) for x in (draft.get("depends") or []) if x]
        if dep not in depends:
            depends.append(dep)
            draft["depends"] = depends
    if added:
        notes.append(
            "craft_smart_btn: applied "
            + ", ".join(added[:4])
            + " (Diagnosis-confirmed Nice-to-have)"
        )
    return notes


def normalize_craft_rows(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        # Diagnosis lock lines / residual identity may use host_model / residual_model.
        on_model = str(row.get("on_model") or row.get("host_model") or "").strip()
        related = str(row.get("related_model") or row.get("residual_model") or "").strip()
        if not on_model or not related:
            continue
        label = str(row.get("label") or "Records").strip()[:80]
        relation_field = str(row.get("relation_field") or "").strip() or "x_related_id"
        chip = str(row.get("chip_label") or _chip_label(label, on_model))
        out.append(
            {
                "id": str(row.get("id") or f"craft:{on_model}:{relation_field}"),
                "on_model": on_model,
                "label": label,
                "related_model": related,
                "relation_field": relation_field,
                "rationale": str(row.get("rationale") or "")[:240],
                "default_on": bool(row.get("default_on", True)),
                "chip_label": chip,
                "source": "craft_confirmed",
            }
        )
        if len(out) >= 2:
            break
    return out


__all__ = [
    "apply_confirmed_craft_smart_buttons",
    "craft_button_keys",
    "is_craft_confirmed_button",
    "normalize_craft_rows",
    "propose_craft_smart_buttons",
]
