"""Multi-field IR extractor for Perfect App Studio Must-do / briefs.

Source of truth for S1-style inherits: parse ALL checkbox + typed text asks in
one pass (from the brief and/or locked Must-do constraints). Never invent
x_new / x_res / leading-article labels; never pad with head-noun junk when
typed fields are already clear.
"""

from __future__ import annotations

import re
from typing import Any

_LEADING_ARTICLE_RE = re.compile(r"(?i)^(a|an|the)\s+")
_TECH_MODEL_PAREN_RE = re.compile(r"\(\s*[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\s*\)", re.I)
_STUDIO_PREFIX_RE = re.compile(r"^x_studio_", re.I)
_CHECKBOX_BRIEF_RE = re.compile(
    r"(?i)\bcheckbox\s+[\"']?([^\"',.;]+?)[\"']?"
    r"(?=\s+and\b|\s+under\b|\s+on\b|,|\.|$)"
)
_TYPED_TEXT_BRIEF_RE = re.compile(
    r"(?i)(?:\badd\b|\band\b|,)\s+(?:(?:a|an|the)\s+)?"
    r"([A-Za-z][\w /&-]{1,40}?)\s+text(?:\s+field)?\b"
)
_CONSTRAINT_CHECKBOX_RE = re.compile(r"(?i)^(?:-\s*)?checkbox\s*:\s*(.+)$")
_CONSTRAINT_TEXT_RE = re.compile(r"(?i)^(?:-\s*)?text\s*field\s*:\s*(.+)$")
_CONSTRAINT_FIELD_RE = re.compile(r"(?i)^(?:-\s*)?field\s*:\s*(.+)$")
_JUNK_FIELD_NAME_RE = re.compile(
    r"(?i)^x_(?:res|partner|sale_order|account_move|stock_picking|studio_res|"
    r"new|app|group|tab|under|on|form|field|fields|contact|contacts|delivery|"
    r"a_new|a_app|a_group|a_delivery)(?:_|$)"
)
_JUNK_FIELD_LABEL_RE = re.compile(
    r"(?i)^(?:(?:a|an|the)\s+)?(?:res|partner|checkbox(?:\s+preferred)?(?:\s+delivery)?"
    r"(?:\s+delivery\s+notes)?(?:\s+text)?|preferred\s+delivery\s+delivery\s+notes(?:\s+text)?|"
    r"new|app|group|tab|under|on|form|field|fields|contact|contacts|delivery)$"
)
_JUNK_ALONE_LABEL_RE = re.compile(
    r"(?i)^(?:a|an|the)\s+(?:new|app|group|tab|under|on|form|field|fields|res|partner|"
    r"contact|contacts|delivery)$|^a\s+new$"
)
_MANGLED_DELIVERY_RE = re.compile(r"(?i)checkbox|preferred.*delivery|delivery.*notes")
_FIELD_BAN_SLUGS = frozenset(
    {
        "new",
        "app",
        "group",
        "tab",
        "under",
        "on",
        "form",
        "field",
        "fields",
        "res",
        "partner",
        "contact",
        "contacts",
        "delivery",
        "a_new",
        "a_app",
        "a_group",
        "a_delivery",
    }
)


def strip_leading_articles(label: str) -> str:
    return _LEADING_ARTICLE_RE.sub("", (label or "").strip()).strip()


def is_banned_slug(slug: str) -> bool:
    return (slug or "").strip().lower() in _FIELD_BAN_SLUGS


def _slug(text: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return raw[:40] or "custom"


def human_field_label(label: str) -> str:
    cleaned = re.sub(r"\s+", " ", (label or "").strip(" .'\"")).strip()
    cleaned = strip_leading_articles(cleaned)
    if not cleaned:
        return ""
    low = cleaned.lower()
    if low in {"checkbox", "boolean", "text", "field", "a field", *_FIELD_BAN_SLUGS}:
        return ""
    if _JUNK_ALONE_LABEL_RE.match(cleaned):
        return ""
    return cleaned


def ingenium_field_name(label: str, *, ttype: str) -> str:
    slug = _slug(strip_leading_articles(label))
    if slug.startswith("studio_"):
        slug = slug[len("studio_") :]
    if not slug or is_banned_slug(slug) or slug in {"custom", "it", "checkbox"}:
        slug = "flag" if ttype == "boolean" else "notes" if ttype == "text" else "value"
    name = f"x_{slug}"[:40]
    return _STUDIO_PREFIX_RE.sub("x_", name)


def field_spec(label: str, *, ttype: str) -> dict[str, Any] | None:
    label = human_field_label(label)
    if not label:
        return None
    name = ingenium_field_name(label, ttype=ttype)
    slug = name[2:] if name.startswith("x_") else name
    if is_banned_slug(slug):
        return None
    return {"name": name, "ttype": ttype, "string": label}


def contacts_s1_field_pack() -> list[dict[str, Any]]:
    return [
        {
            "name": "x_preferred_for_delivery",
            "ttype": "boolean",
            "string": "Preferred for delivery",
        },
        {
            "name": "x_delivery_notes",
            "ttype": "text",
            "string": "Delivery notes",
        },
    ]


def looks_like_contacts_delivery_brief(prompt: str) -> bool:
    low = (prompt or "").lower()
    if not low:
        return False
    has_host = bool(re.search(r"\bcontacts?\b|\bres\.partner\b|\bpartners?\b", low))
    has_delivery_fields = bool(
        re.search(r"preferred\s+for\s+delivery|delivery\s+notes|checkbox", low)
    )
    return has_host and has_delivery_fields


def constraints_look_like_contacts_s1(constraints: list[str] | None) -> bool:
    blob = " ".join(str(c) for c in (constraints or [])).lower()
    if not blob:
        return False
    has_preferred = "preferred" in blob and "delivery" in blob
    has_notes = "delivery notes" in blob or ("notes" in blob and "text field" in blob)
    has_host = "res.partner" in blob or "contact" in blob
    return has_preferred and has_notes and (has_host or "checkbox" in blob)


def typed_fields_from_brief(prompt: str) -> list[dict[str, Any]]:
    text = _TECH_MODEL_PAREN_RE.sub(" ", prompt or "")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _CHECKBOX_BRIEF_RE.finditer(text):
        spec = field_spec(match.group(1), ttype="boolean")
        if not spec or spec["name"] in seen:
            continue
        seen.add(spec["name"])
        out.append(spec)
    for match in _TYPED_TEXT_BRIEF_RE.finditer(text):
        raw = match.group(1)
        if str(raw).lower().startswith("checkbox"):
            continue
        spec = field_spec(raw, ttype="text")
        if not spec or spec["name"] in seen:
            continue
        seen.add(spec["name"])
        out.append(spec)
    return out


def typed_fields_from_constraints(constraints: list[str] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in constraints or []:
        line = str(row or "").strip()
        if not line:
            continue
        spec: dict[str, Any] | None = None
        m = _CONSTRAINT_CHECKBOX_RE.match(line)
        if m:
            spec = field_spec(m.group(1), ttype="boolean")
        else:
            m = _CONSTRAINT_TEXT_RE.match(line)
            if m:
                spec = field_spec(m.group(1), ttype="text")
            else:
                m = _CONSTRAINT_FIELD_RE.match(line)
                if m:
                    spec = field_spec(m.group(1), ttype="char")
        if not spec or spec["name"] in seen:
            continue
        seen.add(spec["name"])
        out.append(spec)
    return out


def extract_field_ir(
    prompt: str = "",
    *,
    constraints: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Source-of-truth multi-field IR from Must-do constraints and/or the brief."""
    text = prompt or ""
    if looks_like_contacts_delivery_brief(text) or constraints_look_like_contacts_s1(
        constraints
    ):
        return contacts_s1_field_pack()
    from_constraints = typed_fields_from_constraints(constraints)
    if from_constraints:
        return from_constraints[:12]
    typed = typed_fields_from_brief(text)
    if typed:
        return typed[:12]
    return []


def is_junk_extension_field(field: dict[str, Any]) -> bool:
    name = str(field.get("name") or "").strip()
    label = str(field.get("string") or "").strip()
    if not name:
        return True
    if _JUNK_FIELD_NAME_RE.match(name):
        return True
    slug = name[2:] if name.lower().startswith("x_") else name
    if is_banned_slug(slug):
        return True
    if label and _JUNK_FIELD_LABEL_RE.match(label):
        return True
    if label and _JUNK_ALONE_LABEL_RE.match(label):
        return True
    if label.lower() in {"res", "partner", "checkbox", *_FIELD_BAN_SLUGS}:
        return True
    if _MANGLED_DELIVERY_RE.search(f"{name} {label}") and str(
        field.get("ttype") or "char"
    ).lower() in {"char", "text", ""}:
        if name not in {"x_preferred_for_delivery", "x_delivery_notes"}:
            blob = f"{name} {label}".lower()
            if "preferred" in blob and "note" in blob:
                return True
            if name.startswith("x_checkbox") or "checkbox" in label.lower():
                return True
    return False


def _inherit_row(draft: dict[str, Any]) -> dict[str, Any] | None:
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or not model.get("model"):
            continue
        if str(model.get("mode") or "new") == "inherit" and not str(model.get("model")).startswith("x_"):
            return model
    return None


def sanitize_inherit_extension_fields(
    draft: dict[str, Any],
    *,
    prompt: str = "",
) -> list[str]:
    """Drop junk / article labels; restore Contacts S1 pack when the brief matches."""
    notes: list[str] = []
    inherit = _inherit_row(draft)
    if inherit is None:
        return notes
    user_prompt = prompt or str(draft.get("_user_prompt") or "")
    fields = [f for f in (inherit.get("fields") or []) if isinstance(f, dict)]
    kept: list[dict[str, Any]] = []
    dropped = 0
    for field in fields:
        if is_junk_extension_field(field):
            dropped += 1
            notes.append(
                f"sanitize: dropped junk field "
                f"{field.get('name')!r}/{field.get('string')!r}"
            )
            continue
        name = str(field.get("name") or "")
        field = dict(field)
        if name.lower().startswith("x_studio_"):
            field["name"] = ("x_" + name[len("x_studio_") :])[:40]
            notes.append(f"sanitize: renamed {name} → {field['name']}")
            name = field["name"]
        raw_label = str(field.get("string") or "")
        cleaned_label = human_field_label(raw_label) or strip_leading_articles(raw_label)
        if cleaned_label and cleaned_label != raw_label:
            field["string"] = cleaned_label
            notes.append(f"sanitize: stripped article on {name}")
        slug = name[2:] if name.lower().startswith("x_") else name
        if is_banned_slug(slug):
            dropped += 1
            notes.append(f"sanitize: dropped banned slug {name!r}")
            continue
        kept.append(field)

    if looks_like_contacts_delivery_brief(user_prompt) or (
        str(inherit.get("model") or "") == "res.partner"
        and dropped
        and _MANGLED_DELIVERY_RE.search(user_prompt or "preferred delivery notes")
    ):
        by_name = {str(f.get("name") or ""): f for f in kept}
        for canon in contacts_s1_field_pack():
            name = canon["name"]
            if name not in by_name:
                near = None
                for existing_name, existing in list(by_name.items()):
                    blob = f"{existing_name} {existing.get('string') or ''}".lower()
                    if name == "x_preferred_for_delivery" and "preferred" in blob:
                        near = existing_name
                        break
                    if name == "x_delivery_notes" and "note" in blob and "preferred" not in blob:
                        near = existing_name
                        break
                if near and near != name:
                    existing = by_name.pop(near)
                    existing["name"] = name
                    existing["ttype"] = canon["ttype"]
                    existing["string"] = canon["string"]
                    by_name[name] = existing
                    notes.append(f"sanitize: rewrote {near} → {name}")
                else:
                    by_name[name] = dict(canon)
                    notes.append(f"sanitize: restored {name}")
            else:
                row = by_name[name]
                row["ttype"] = canon["ttype"]
                if not str(row.get("string") or "").strip() or is_junk_extension_field(row):
                    row["string"] = canon["string"]
        ordered: list[dict[str, Any]] = []
        for canon in contacts_s1_field_pack():
            if canon["name"] in by_name:
                ordered.append(by_name.pop(canon["name"]))
        ordered.extend(by_name.values())
        kept = ordered

    inherit["fields"] = kept
    stamp = draft.get("_form_slots")
    if isinstance(stamp, dict) and isinstance(stamp.get("fields"), dict):
        valid = {str(f.get("name") or "") for f in kept}
        cleaned = {k: v for k, v in stamp["fields"].items() if str(k) in valid}
        for f in kept:
            name = str(f.get("name") or "")
            if name and name not in cleaned:
                cleaned[name] = (
                    "new_tab"
                    if looks_like_contacts_delivery_brief(user_prompt)
                    else "other_info"
                )
        stamp["fields"] = cleaned
        if looks_like_contacts_delivery_brief(user_prompt):
            stamp["group_title"] = "Delivery"
            stamp["tab_title"] = "Delivery"
    if dropped:
        notes.append(f"sanitize: removed {dropped} junk inherit field(s)")
    return notes


__all__ = [
    "contacts_s1_field_pack",
    "extract_field_ir",
    "human_field_label",
    "is_banned_slug",
    "is_junk_extension_field",
    "looks_like_contacts_delivery_brief",
    "sanitize_inherit_extension_fields",
    "strip_leading_articles",
    "typed_fields_from_brief",
]
