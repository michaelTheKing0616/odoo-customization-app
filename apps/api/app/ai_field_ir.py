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



def infer_date_or_datetime(label: str) -> str | None:
    """Prefer Date unless time is stated or reasonably implied.

    Returns ``"date"``, ``"datetime"``, or ``None`` when the label is not
    temporal. Shared by Must-do / constraints / column-list / refine / preview
    so residual full_app, field_pack, and feature_slice share one rule.
    """
    low = re.sub(r"\s+", " ", (label or "").lower()).strip(" .:'\"")
    if not low:
        return None

    # Explicit datetime / timestamp / date+time
    if re.search(
        r"(?i)\bdate\s*time\b|\bdatetime\b|\btimestamp\b|"
        r"\bdate\s+and\s+time\b|\bat\s+\d{1,2}\s*(?:[:.]\d{2})?\s*(?:am|pm)?\b",
        low,
    ):
        return "datetime"

    # Time-of-day / schedule nouns (datetime even without the word "date")
    if re.search(
        r"(?i)\b("
        r"check[- ]?in(?:\s+time)?|check[- ]?out(?:\s+time)?|"
        r"clock[- ]?in|clock[- ]?out|"
        r"time\s+in|time\s+out|time\s+of\s+day|"
        r"(?:start|end|arrival|departure|appointment)\s+time|"
        r"appointment\s+(?:start|end)|"
        r"scheduled?\s+(?:start|end)|"
        r"meeting\s+(?:start|end)"
        r")\b",
        low,
    ):
        return "datetime"

    # Bare start/end with schedule semantics (not "start date" / "end date")
    if re.fullmatch(r"(?i)(?:start|end|begins?|ends?)", low):
        return "datetime"
    if re.search(r"(?i)\b(?:from|between).{0,24}\b(?:to|and)\b.{0,24}\b(?:time|am|pm)\b", low):
        return "datetime"

    # Calendar-day labels — date wins when only a date is named
    if re.search(
        r"(?i)\b("
        r"visit\s+date|birth\s*date|birthday|due\s+date|expiry\s+date|"
        r"expiration\s+date|start\s+date|end\s+date|open(?:ed)?\s+date|"
        r"close(?:d)?\s+date|deadline|dob|d\.o\.b\.?"
        r")\b",
        low,
    ):
        return "date"

    # Trailing / bare "date" without time cues
    if re.search(r"(?i)\bdate\b", low) and not re.search(r"(?i)\btime\b", low):
        return "date"

    # Due / deadline / expiry without an explicit "date" word
    if re.search(r"(?i)\b(due|deadline|expir(?:y|es|ation))\b", low) and not re.search(
        r"(?i)\btime\b", low
    ):
        return "date"

    return None


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


_CONSTRAINT_META_RE = re.compile(
    r"(?i)^(?:new\s+model\b|menu\s+under\b|list\s*\+\s*form\b|"
    r"create\s*/\s*read\b|create\s+and\s+read\b|on\s+\w|"
    r"do\s+not\b|don't\b|never\s+create\b|place\s+under\b)"
)
_CONSTRAINT_SELECTION_RE = re.compile(
    r"(?i)^(.+?)\s+(?:selection\s*)?\(\s*selection\s*:\s*(.+?)\)\s*(?:\.|$)"
)
_CONSTRAINT_SELECTION_BARE_RE = re.compile(
    r"(?i)^(.+?)\s+selection\s*\((.+)\)\s*$"
)
_CONSTRAINT_ARROW_RE = re.compile(r"^(.+?)\s*(?:→|->)\s*(.+)$")
_CONSTRAINT_DATE_RE = re.compile(r"(?i)\bdate(?:\s*time)?\b|\bdatetime\b")


def _resolve_relation_model(target: str) -> str | None:
    """Map Must-do display targets (Contact, Employee, Product) to ORM models."""
    raw = (target or "").strip()
    if not raw:
        return None
    if "." in raw and re.match(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$", raw):
        return raw
    try:
        from app.ai_grain import HOST_ALIASES
    except Exception:  # noqa: BLE001
        HOST_ALIASES = {}
    low = raw.lower().strip()
    if low in HOST_ALIASES:
        return HOST_ALIASES[low]
    # singular/plural soft match
    for phrase, model in sorted(HOST_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if phrase == low or phrase.rstrip("s") == low.rstrip("s"):
            return model
    # product.product is common but not always in HOST_ALIASES
    if low in {"product", "products", "product.product"}:
        return "product.product"
    if low in {"user", "users", "res.users"}:
        return "res.users"
    return None


def _selection_literal(opts: str) -> str:
    parts = [p.strip(" .") for p in re.split(r"[/,|;]", opts or "") if p.strip(" .")]
    pairs: list[str] = []
    for part in parts[:12]:
        label = re.sub(r"\s+", " ", part).strip()
        if not label:
            continue
        key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40] or "value"
        safe_label = label.replace("'", "\'")
        pairs.append(f"('{key}','{safe_label}')")
    return "[" + ",".join(pairs) + "]" if pairs else "[('other','Other')]"


def _m2o_field(label: str, relation: str) -> dict[str, Any] | None:
    label = human_field_label(label)
    if not label or not relation:
        return None
    base = ingenium_field_name(label, ttype="many2one")
    name = base if base.endswith("_id") else (base[:37] + "_id")
    return {
        "name": name[:40],
        "ttype": "many2one",
        "relation": relation,
        "string": label,
    }


def _constraint_field_spec(line: str) -> dict[str, Any] | None:
    """One Must-do / constraint row → field dict (inherit + residual full_app)."""
    text = str(line or "").strip().lstrip("- ").strip()
    if not text or _CONSTRAINT_META_RE.match(text):
        return None

    m = _CONSTRAINT_CHECKBOX_RE.match(text)
    if m:
        return field_spec(m.group(1), ttype="boolean")
    m = _CONSTRAINT_TEXT_RE.match(text)
    if m:
        return field_spec(m.group(1), ttype="text")
    m = _CONSTRAINT_FIELD_RE.match(text)
    if m:
        return field_spec(m.group(1), ttype="char")

    # Purpose selection (A / B)  OR  Status (selection: A / B)
    m = _CONSTRAINT_SELECTION_BARE_RE.match(text) or _CONSTRAINT_SELECTION_RE.match(text)
    if m:
        label = human_field_label(m.group(1))
        if not label:
            return None
        name = ingenium_field_name(label, ttype="selection")
        return {
            "name": name,
            "ttype": "selection",
            "string": label,
            "selection": _selection_literal(m.group(2)),
        }

    m = _CONSTRAINT_ARROW_RE.match(text)
    if m:
        relation = _resolve_relation_model(m.group(2))
        if relation:
            return _m2o_field(m.group(1), relation)
        # Unknown target — still emit char so Must-do is not silently dropped
        return field_spec(m.group(1), ttype="char")

    # Bare label: date / name / char
    label = human_field_label(text)
    if not label:
        return None
    # Sentence leftovers ("Dining Tables for our restaurant. Name") → last Name token
    if "." in label and re.search(r"(?i)\bname\b", label):
        label = "Name"
    low = label.lower()
    # Strip trailing explicit type tokens ("Visit datetime", "Due date")
    temporal = infer_date_or_datetime(label)
    if temporal is None and _CONSTRAINT_DATE_RE.search(low):
        temporal = "datetime" if re.search(r"(?i)\b(?:date\s*time|datetime|timestamp)\b", low) else "date"
    if temporal:
        return field_spec(label, ttype=temporal)
    if low == "name" or low.endswith(" name"):
        return {
            "name": "x_name",
            "ttype": "char",
            "string": label if low != "name" else "Name",
            "required": True,
        }
    if low in {"capacity", "qty", "quantity", "seats", "covers"}:
        return field_spec(label, ttype="integer")
    return field_spec(label, ttype="char")


def typed_fields_from_constraints(constraints: list[str] | None) -> list[dict[str, Any]]:
    """Parse inherit Checkbox:/Text field: rows AND residual full_app Must-do rows.

    Residual shapes (structural, not Visitor-only):
      Name | Company→Contact | Visit date | Purpose selection (A / B) | Host→Employee
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in constraints or []:
        spec = _constraint_field_spec(str(row or ""))
        if not spec:
            continue
        name = str(spec.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(spec)
    return out


def fields_from_residual_brief(
    prompt: str = "",
    *,
    constraints: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Materialize primary residual model fields from Must-do / brief.

    Used by register honesty seed so Live Generate is not Name-only when Diagnosis
    already listed Company / Visit date / Purpose / Host (or any similar residual).
    """
    rows = [str(c) for c in (constraints or []) if str(c or "").strip()]
    if not rows and prompt:
        try:
            from app.ai_conversation.understand import _brief_full_app_must_do

            rows = [str(c) for c in _brief_full_app_must_do(prompt) if str(c or "").strip()]
        except Exception:  # noqa: BLE001
            rows = []
    fields = typed_fields_from_constraints(rows)
    if not fields and prompt:
        # Inherit-style typed briefs still win when Must-do is empty.
        fields = typed_fields_from_brief(prompt)
    if not fields:
        return []
    names = {str(f.get("name") or "") for f in fields}
    if "x_name" not in names:
        fields.insert(
            0,
            {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
        )
    return fields[:16]


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
    # Residual full_app: Diagnosis Must-do rows are the field source of truth.
    residual = fields_from_residual_brief(text, constraints=constraints)
    if residual and len(residual) > 1:
        return residual[:12]
    typed = typed_fields_from_brief(text)
    if typed:
        return typed[:12]
    # Single x_name honesty stub is not inherit field IR.
    return residual[:12] if residual and len(residual) > 1 else []


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
    "fields_from_residual_brief",
    "human_field_label",
    "infer_date_or_datetime",
    "is_banned_slug",
    "is_junk_extension_field",
    "looks_like_contacts_delivery_brief",
    "sanitize_inherit_extension_fields",
    "strip_leading_articles",
    "typed_fields_from_brief",
    "typed_fields_from_constraints",
]
