"""Named inherit slots — place extra fields on the stock form, not in EXTENSION.

Field packs inherit Community hosts. A nested ``<group string="EXTENSION">`` in
``header_right_group`` looks bolted on (whitespace island under Journal). Slots
are xpaths a senior implementer would pick:

- next_to_partner — after vendor/customer
- next_to_dates — inside the dates column, fields only
- other_info — Other Info notebook page
- new_tab — a named page (Compliance / Inspection / …), never EXTENSION

Operator override lives on ``draft["_form_slots"]["fields"]``. View Designer
remains the power editor; Open in Odoo is the proof.
"""

from __future__ import annotations

import re
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from app.ai_grain import INHERIT_FORM_XML, INHERIT_FORM_XPATH

SLOT_IDS = ("next_to_partner", "next_to_dates", "other_info", "new_tab")

_FILLER_ACTIVE = re.compile(
    r"(?i)\b(?:an?\s+)?active\s+field\b|\bx_active\b|\badd(?:ing)?\s+active\b"
)
_FILLER_NOTES = re.compile(r"(?i)\bnotes?\b|\bremarks?\b|\bcomments?\b")
_FILLER_REF = re.compile(r"(?i)\breference\b|\bx_ref\b")
_TIN_RE = re.compile(r"(?i)\b(tin|vat|tax\s*id|rc\s*number|tax\s*number)\b")
_DATEISH_RE = re.compile(r"(?i)\b(due|sla|deadline|expir|start|end|date)\b")
_CLUSTER_RE = re.compile(r"(?i)\b(warranty|inspection|compliance|checklist)\b")

# expr, position, wrap: fields | group | page
# XPaths must match exactly one node. Bare //field[@name='partner_id'] hits
# the header plus every list column inside invoice_line_ids / order_line.
_PARTNER_HEADER = "//field[@name='partner_id'][not(ancestor::field)]"
_NAME_HEADER = "//field[@name='name'][not(ancestor::field)]"

_HOST_SLOTS: dict[str, dict[str, tuple[str, str, str]]] = {
    "account.move": {
        "next_to_partner": (
            "//group[@id='header_left_group']/div[@class='o_col']",
            "after",
            "fields",
        ),
        "next_to_dates": ("//group[@id='header_right_group']", "inside", "fields"),
        "other_info": ("//page[@id='other_tab']", "inside", "group"),
        "new_tab": ("//sheet/notebook", "inside", "page"),
    },
    "sale.order": {
        "next_to_partner": (_PARTNER_HEADER, "after", "fields"),
        "next_to_dates": ("//field[@name='date_order'][not(ancestor::field)]", "after", "fields"),
        "other_info": ("//page[@name='other_information']", "inside", "group"),
        "new_tab": ("//notebook", "inside", "page"),
    },
    "purchase.order": {
        "next_to_partner": (_PARTNER_HEADER, "after", "fields"),
        "next_to_dates": ("//field[@name='date_order'][not(ancestor::field)]", "after", "fields"),
        "other_info": ("//page[@name='other_info']", "inside", "group"),
        "new_tab": ("//notebook", "inside", "page"),
    },
    "res.partner": {
        "next_to_partner": (_NAME_HEADER, "after", "fields"),
        "next_to_dates": ("//sheet/group[1]", "inside", "fields"),
        "other_info": ("//page[@name='internal_notes']", "inside", "group"),
        "new_tab": ("//notebook", "inside", "page"),
    },
    "crm.lead": {
        "next_to_partner": (_PARTNER_HEADER, "after", "fields"),
        "next_to_dates": ("//field[@name='date_deadline'][not(ancestor::field)]", "after", "fields"),
        "other_info": ("//page[@name='lead']", "inside", "group"),
        "new_tab": ("//notebook", "inside", "page"),
    },
    "project.task": {
        "next_to_partner": (_PARTNER_HEADER, "after", "fields"),
        "next_to_dates": ("//field[@name='date_deadline'][not(ancestor::field)]", "after", "fields"),
        "other_info": ("//page[@name='description_page']", "inside", "group"),
        "new_tab": ("//notebook", "inside", "page"),
    },
    "hr.employee": {
        "next_to_partner": (_NAME_HEADER, "after", "fields"),
        "next_to_dates": ("//sheet/group[1]", "inside", "fields"),
        "other_info": ("//notebook/page[last()]", "inside", "group"),
        "new_tab": ("//notebook", "inside", "page"),
    },
    "calendar.event": {
        "next_to_partner": ("//field[@name='partner_ids'][not(ancestor::field)]", "after", "fields"),
        "next_to_dates": ("//field[@name='start'][not(ancestor::field)]", "after", "fields"),
        "other_info": ("//notebook/page[last()]", "inside", "group"),
        "new_tab": ("//notebook", "inside", "page"),
    },
    "stock.picking": {
        "next_to_partner": (_PARTNER_HEADER, "after", "fields"),
        "next_to_dates": ("//field[@name='scheduled_date'][not(ancestor::field)]", "after", "fields"),
        "other_info": ("//notebook/page[last()]", "inside", "group"),
        "new_tab": ("//notebook", "inside", "page"),
    },
}


def partner_slot_label(host: str) -> str:
    if host in {"sale.order", "crm.lead"}:
        return "Next to customer"
    if host in {"res.partner", "hr.employee"}:
        return "Next to name"
    return "Next to vendor"


def partner_place_phrase(host: str) -> str:
    if host in {"sale.order", "crm.lead"}:
        return "next to customer"
    if host in {"res.partner", "hr.employee"}:
        return "next to name"
    return "next to vendor"


def slot_catalog(host: str) -> list[dict[str, str]]:
    return [
        {
            "id": "next_to_partner",
            "label": partner_slot_label(host),
            "phrase": partner_place_phrase(host),
        },
        {"id": "next_to_dates", "label": "Next to dates", "phrase": "next to dates"},
        {"id": "other_info", "label": "Other Info tab", "phrase": "in other info"},
        {"id": "new_tab", "label": "New tab", "phrase": "on a new tab"},
    ]


def slot_from_location(text: str) -> str | None:
    """Map a location phrase to a slot id.

    Prefer the clause after next to/in/on so ‘put Vendor TIN next to dates’
    does not match vendor in the field label.
    """
    n = re.sub(r"\s+", " ", (text or "").strip().lower())
    loc_match = re.search(
        r"(?:next\s+to|beside|after|under|in(?:to)?|on(?:to)?)\s+(?:the\s+|a\s+|its\s+own\s+)?(.+)$",
        n,
    )
    loc = loc_match.group(1) if loc_match else n
    if re.search(r"\b(vendor|supplier|customer|partner|client|name)\b", loc):
        return "next_to_partner"
    if re.search(r"\bdates?\b|\bjournal\b|\bheader\b", loc):
        return "next_to_dates"
    if re.search(r"\bother\b", loc):
        return "other_info"
    if re.search(r"\bgroup\b", loc) or named_group_title(text):
        return "new_tab"
    if re.search(r"\b(tab|compliance|inspection|warranty|details)\b", loc):
        return "new_tab"
    return None


_UNDER_GROUP_RE = re.compile(
    r"(?i)\bunder\s+(?:(?:the|a|an)\s+)?([A-Za-z][\w /&-]{0,40}?)\s+group\b"
)
_LEADING_ARTICLE_RE = re.compile(r"(?i)^(a|an|the)\s+")


def _normalize_group_title(raw: str) -> str | None:
    title = re.sub(r"\s+", " ", (raw or "")).strip(" .")
    title = _LEADING_ARTICLE_RE.sub("", title).strip()
    if not title or title.lower() in {"the", "a", "an", "new", "other", "group", "tab"}:
        return None
    if " " not in title:
        return title[:1].upper() + title[1:].lower()
    return " ".join(w[:1].upper() + w[1:] if w else w for w in title.split(" "))


def named_group_title(prompt: str) -> str | None:
    """Operator-named sheet group (e.g. Delivery) — never a selection field.

    «under a Delivery group» → Delivery (never «A Delivery» / «A DELIVERY»).
    """
    match = _UNDER_GROUP_RE.search(prompt or "")
    if not match:
        return None
    return _normalize_group_title(match.group(1))


def tab_title(prompt: str) -> str:
    named = named_group_title(prompt)
    if named:
        return named
    low = (prompt or "").lower()
    if "compliance" in low:
        return "Compliance"
    if "inspection" in low or "checklist" in low:
        return "Inspection"
    if "warranty" in low:
        return "Warranty"
    if re.search(r"\bsla\b", low):
        return "SLA"
    return "Details"


def _inherit_row(draft: dict[str, Any]) -> dict[str, Any] | None:
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        if str(model.get("mode") or "new") != "inherit":
            continue
        mid = str(model.get("model") or "")
        if mid and not mid.startswith("x_"):
            return model
    return None


def _visible_fields(inherit: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for field in inherit.get("fields") or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "")
        if not name or field.get("ttype") == "one2many":
            continue
        if field.get("invisible") is True:
            continue
        out.append(field)
    return out[:12]


def strip_inherit_filler(inherit: dict[str, Any], prompt: str) -> list[str]:
    """Drop Active/Notes/Reference padding unless the brief asked for them."""
    notes: list[str] = []
    fields = [f for f in (inherit.get("fields") or []) if isinstance(f, dict)]
    kept: list[dict[str, Any]] = []
    for field in fields:
        name = str(field.get("name") or "")
        if name == "x_active" and not _FILLER_ACTIVE.search(prompt or ""):
            notes.append("slots: dropped padding x_active")
            continue
        if name == "x_notes" and not _FILLER_NOTES.search(prompt or ""):
            notes.append("slots: dropped padding x_notes")
            continue
        if name == "x_ref" and not _FILLER_REF.search(prompt or ""):
            notes.append("slots: dropped padding x_ref")
            continue
        kept.append(field)
    inherit["fields"] = kept
    return notes


def infer_slot(
    field: dict[str, Any],
    *,
    host: str,
    prompt: str,
) -> str:
    # Explicit "under Delivery group" (etc.) → named sheet group / new_tab, not Other Info.
    prompt_slot = slot_from_location(prompt or "")
    if prompt_slot == "new_tab" or named_group_title(prompt or ""):
        return "new_tab"
    blob = f"{field.get('name') or ''} {field.get('string') or ''} {prompt or ''}"
    ttype = str(field.get("ttype") or field.get("type") or "char")
    if _TIN_RE.search(str(field.get("name") or "") + " " + str(field.get("string") or "")):
        return "next_to_partner"
    if ttype in {"date", "datetime"} or _DATEISH_RE.search(str(field.get("name") or "") + " " + str(field.get("string") or "")):
        return "next_to_dates"
    if ttype in {"text", "html"} or re.search(r"(?i)\bnotes?\b", str(field.get("string") or "")):
        return "other_info"
    if _CLUSTER_RE.search(blob):
        return "new_tab"
    if ttype == "boolean":
        return "other_info"
    if host == "account.move":
        return "next_to_dates"
    return "other_info"


def assign_slots(draft: dict[str, Any], *, prompt: str = "") -> dict[str, str]:
    inherit = _inherit_row(draft)
    if inherit is None:
        return {}
    host = str(inherit.get("model") or "")
    stored = (draft.get("_form_slots") or {}).get("fields") if isinstance(draft.get("_form_slots"), dict) else {}
    stored = stored if isinstance(stored, dict) else {}
    mapping: dict[str, str] = {}
    for field in _visible_fields(inherit):
        name = str(field.get("name") or "")
        override = str(stored.get(name) or "").strip()
        if override in SLOT_IDS:
            mapping[name] = override
        else:
            mapping[name] = infer_slot(field, host=host, prompt=prompt)
    return mapping


def _slot_spec(host: str, slot: str) -> tuple[str, str, str]:
    table = _HOST_SLOTS.get(host) or {}
    if slot in table:
        return table[slot]
    if slot == "next_to_partner":
        return (_PARTNER_HEADER, "after", "fields")
    if slot == "next_to_dates":
        return (INHERIT_FORM_XPATH.get(host, "//sheet"), "inside", "fields")
    if slot == "other_info":
        return ("//notebook/page[last()]", "inside", "group")
    return ("//notebook", "inside", "page")


def _field_tag(field: dict[str, Any]) -> str:
    name = escape(str(field.get("name") or ""), {'"': "&quot;"})
    bits = [f'name="{name}"']
    label = str(field.get("string") or "").strip()
    if label:
        bits.append(f"string={quoteattr(label)}")
    if field.get("required"):
        bits.append('required="1"')
    return "<field " + " ".join(bits) + "/>"


def _wrap_inner(fields: list[dict[str, Any]], wrap: str, *, page_title: str) -> str:
    tags = "\n".join(f"      {_field_tag(f)}" for f in fields)
    if wrap == "fields":
        return tags
    if wrap == "group":
        return f"      <group>\n{tags}\n      </group>"
    page_name = "x_slot_" + re.sub(r"[^a-z0-9]+", "_", page_title.lower()).strip("_")[:32]
    return (
        f"      <page string={quoteattr(page_title)} name={quoteattr(page_name)}>\n"
        f"        <group>\n{tags}\n        </group>\n"
        "      </page>"
    )


def render_slotted_arch(
    inherit: dict[str, Any],
    mapping: dict[str, str],
    *,
    prompt: str = "",
) -> str:
    host = str(inherit.get("model") or "")
    by_name = {
        str(f.get("name") or ""): f
        for f in _visible_fields(inherit)
        if str(f.get("name") or "")
    }
    buckets: dict[str, list[dict[str, Any]]] = {sid: [] for sid in SLOT_IDS}
    for name, slot in mapping.items():
        field = by_name.get(name)
        if field is None:
            continue
        buckets.setdefault(slot, []).append(field)
    page = tab_title(prompt)
    group_title = named_group_title(prompt)
    xpaths: list[str] = []
    for slot in SLOT_IDS:
        fields = buckets.get(slot) or []
        if not fields:
            continue
        # Named sheet group (Contacts Delivery): group title, never a selection field.
        if slot == "new_tab" and group_title:
            expr, position, wrap = ("//sheet", "inside", "group")
            tags = "\n".join(f"      {_field_tag(f)}" for f in fields)
            inner = (
                f'      <group string={quoteattr(group_title)}>\n{tags}\n      </group>'
            )
        else:
            expr, position, wrap = _slot_spec(host, slot)
            inner = _wrap_inner(fields, wrap, page_title=page)
        xpaths.append(
            f'  <xpath expr="{expr}" position="{position}">\n{inner}\n  </xpath>'
        )
    if not xpaths:
        return ""
    return "<data>\n" + "\n".join(xpaths) + "\n</data>"


def _rewrite_studio_field_names(inherit: dict[str, Any]) -> list[str]:
    """Forbid x_studio_* — rewrite to Ingenium x_* with human labels kept."""
    notes: list[str] = []
    for field in inherit.get("fields") or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "")
        if not name.lower().startswith("x_studio_"):
            continue
        new_name = "x_" + name[len("x_studio_") :]
        field["name"] = new_name[:40]
        label = str(field.get("string") or "").strip()
        if not label or label.lower().startswith("x_studio"):
            leaf = new_name[2:].replace("_", " ").strip()
            field["string"] = leaf[:1].upper() + leaf[1:] if leaf else new_name
        notes.append(f"slots: renamed {name} → {field['name']}")
    return notes


def apply_form_slots(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Stamp slots and rebuild the inherit extension view. Never string=EXTENSION."""
    if draft.get("_capability_primary_option_a"):
        return []
    inherit = _inherit_row(draft)
    if inherit is None:
        return []
    user_prompt = prompt or str(draft.get("_user_prompt") or "")
    notes = _rewrite_studio_field_names(inherit)
    notes.extend(strip_inherit_filler(inherit, user_prompt))
    host = str(inherit.get("model") or "")
    mapping = assign_slots(draft, prompt=user_prompt)
    catalog = slot_catalog(host)
    draft["_form_slots"] = {
        "host": host,
        "fields": mapping,
        "catalog": catalog,
        "tab_title": tab_title(user_prompt),
        "group_title": named_group_title(user_prompt),
    }
    views = [v for v in (draft.get("views") or []) if isinstance(v, dict)]
    draft["views"] = [
        v
        for v in views
        if not (
            str(v.get("model") or "") == host
            and str(v.get("mode") or "") == "extension"
            and str(v.get("type") or "form") == "form"
        )
    ]
    arch = render_slotted_arch(inherit, mapping, prompt=user_prompt)
    if not arch:
        notes.append("slots: no form chrome")
        return notes
    draft.setdefault("views", []).append(
        {
            "name": f"{host}.form.extension",
            "model": host,
            "type": "form",
            "mode": "extension",
            "inherit_xml_id": INHERIT_FORM_XML.get(host),
            "arch": arch,
            "source": "form_slots",
        }
    )
    notes.append(f"slots: placed {len(mapping)} field(s) on {host}")
    return notes


__all__ = [
    "SLOT_IDS",
    "apply_form_slots",
    "assign_slots",
    "infer_slot",
    "named_group_title",
    "partner_place_phrase",
    "slot_catalog",
    "slot_from_location",
    "strip_inherit_filler",
    "tab_title",
]
