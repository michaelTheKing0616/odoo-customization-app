"""Builders stage 2d: pure helpers (no Odoo calls) for the 20 approved ideas.

Plain-language output; AI only proposes (translation, picture reading), code
checks everything; sample values are labelled; nothing is made up from data.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from app import view_engine_2c as v2
from app.view_engine import LAYER_PREFIX, EngineError

TRUE_WORDS = {"1", "True", "true"}


# 2. What changed: before/after of a screen ------------------------------------

def _flat(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n, _p, _h in v2.walk(tree)}


def tree_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    a, b = _flat(before), _flat(after)
    lab = lambda n: str(n.get("label") or n.get("name") or n.get("tag") or "item")  # noqa: E731
    out: list[dict[str, str]] = []
    for nid in b.keys() - a.keys():
        out.append({"kind": "added", "node": nid, "text": f"Added: {lab(b[nid])}"})
    for nid in a.keys() - b.keys():
        out.append({"kind": "removed", "node": nid, "text": f"Removed: {lab(a[nid])}"})
    for nid in a.keys() & b.keys():
        x, y = a[nid].get("attrs") or {}, b[nid].get("attrs") or {}
        for k in sorted(set(x) | set(y)):
            if str(x.get(k) or "") != str(y.get(k) or ""):
                was, now = x.get(k), y.get(k)
                out.append({"kind": "changed", "node": nid,
                            "text": f"{lab(b[nid])}: {k} {'set to ' + repr(now) if now not in (None, '') else 'cleared'}" + (f" (was {was!r})" if was not in (None, "") else "")})
    pa = {nid: i for i, nid in enumerate(a)}
    moved = [nid for nid in b if nid in pa and b[nid].get("tag") == "field"]
    order_a = [nid for nid in a if nid in set(moved)]
    if moved != order_a:
        out.append({"kind": "moved", "node": "", "text": "Some fields are in a different order."})
    rank = {"added": 0, "removed": 1, "changed": 2, "moved": 3}
    return sorted(out, key=lambda d: (rank[d["kind"]], d["text"]))[:200]



_CHATTER_FIELDS = {"message_follower_ids", "activity_ids", "message_ids", "website_message_ids"}
_RULE_ATTRS = ("invisible", "readonly", "required")
_SEEN_ATTRS = (*_RULE_ATTRS, "groups", "optional")


def _norm_word(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(v or "").lower())


def _norm_attr(at: str, v: Any) -> str:
    """Rules compare as always / sometimes / never: the condition wording changes between versions."""
    t = str(v or "").strip()
    if at in _RULE_ATTRS:
        return "always" if t in TRUE_WORDS else "" if t in {"", "0", "False", "false"} else "sometimes"
    return ",".join(sorted(p.strip() for p in t.split(",") if p.strip())) if at == "groups" else t


def _semantic(tree: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Items keyed by what they are (field by technical name, button/tab/group by wording), not by
    node id, so two Odoo versions line up. Unnamed, unlabelled containers and always-hidden helpers are skipped."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for n, _p, hidden in v2.walk(tree):
        tag = n.get("tag")
        if tag not in {"page", "group", "field", "button"} or hidden:  # never shown, so never a visible difference
            continue
        # fields by technical name; buttons and tabs by wording (button names are action ids that change per version)
        ident = n.get("name") if tag == "field" else (n.get("label") or n.get("name"))
        key = (str(tag), _norm_word(ident))
        if tag == "field" and str(n.get("name") or "") in _CHATTER_FIELDS:
            continue  # 17-18 write the chatter as fields, 19+ as <chatter/>: same thing, different naming
        if key[1] and key not in out:
            out[key] = n
    return out


def cross_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    """Real differences between screens on different Odoo versions. Items that differ only in version
    naming (node ids, wording of the same field, how a yes/no is spelled, layout-only attributes) are left out."""
    a, b = _semantic(before), _semantic(after)
    lab = lambda n: str(n.get("label") or n.get("name") or n.get("tag") or "item")  # noqa: E731
    out: list[dict[str, str]] = []
    for k in b.keys() - a.keys():
        out.append({"kind": "added", "node": b[k]["id"], "text": f"Only there: {lab(b[k])}"})
    for k in a.keys() - b.keys():
        out.append({"kind": "removed", "node": a[k]["id"], "text": f"Not there: {lab(a[k])}"})
    for k in a.keys() & b.keys():
        x, y = a[k].get("attrs") or {}, b[k].get("attrs") or {}
        for at in _SEEN_ATTRS:
            was, now = _norm_attr(at, x.get(at)), _norm_attr(at, y.get(at))
            if was != now:
                out.append({"kind": "changed", "node": b[k]["id"],
                            "text": f"{lab(b[k])}: {at} {'set to ' + repr(now) if now else 'cleared'}" + (f" (here {was!r})" if was else "")})
    common = [k for k in b if k in a and k[0] == "field"]
    if common != [k for k in a if k in b and k[0] == "field"]:
        out.append({"kind": "moved", "node": "", "text": "Some fields are in a different order."})
    rank = {"added": 0, "removed": 1, "changed": 2, "moved": 3}
    return sorted(out, key=lambda d: (rank[d["kind"]], d["text"]))[:200]

# 3. Approvers per record type ----------------------------------------------------

def approver_check(approvers: dict[str, list[str]], model: str, email: str | None, verified: bool) -> str | None:
    """None when this person may approve; otherwise the plain reason."""
    allowed = [e.lower() for e in (approvers.get(model) or approvers.get("*") or [])]
    if not allowed:
        return None
    if not verified or not email:
        return "Only named approvers can approve here, and sign-in is off, so Ingenium can't tell who you are."
    if email.lower() not in allowed:
        return f"Only {', '.join(allowed[:5])} can approve changes to this record type."
    return None


def clean_approvers(raw: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for model, emails in (raw or {}).items():
        if model != "*" and not re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)+", str(model)):
            raise EngineError(f"'{model}' isn't a record type.")
        good = [str(e).strip().lower() for e in emails or [] if str(e).strip()]
        bad = [e for e in good if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e)]
        if bad:
            raise EngineError(f"'{bad[0]}' isn't an email address.")
        if good:
            out[str(model)] = sorted(set(good))[:20]
    return out


# 4. Pause scheduled publishing during an upgrade ---------------------------------

def active_pause(pauses: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    for p in pauses:
        try:
            if datetime.fromisoformat(p["start"]) <= now < datetime.fromisoformat(p["end"]):
                return p
        except (KeyError, ValueError):
            continue
    return None


def check_pause(start: datetime, end: datetime, now: datetime) -> None:
    if end <= start:
        raise EngineError("The pause has to end after it starts.")
    if end <= now:
        raise EngineError("That pause is already over.")
    if end - start > timedelta(days=14):
        raise EngineError("Pause for 14 days at most.")


# 5. After-publish save problems ---------------------------------------------------

def static_required(tree: dict[str, Any]) -> list[str]:
    return sorted({n["name"] for n, _h in v2.screen_field_nodes(tree)
                   if n.get("name") and str((n.get("attrs") or {}).get("required") or "") in TRUE_WORDS})


# 6. Number tiles with a comparison ------------------------------------------------

def period_bounds(period: str, today: date) -> tuple[date, date, date, date]:
    if period == "week":
        cur = today - timedelta(days=today.weekday())
        return cur, cur + timedelta(days=7), cur - timedelta(days=7), cur
    if period == "quarter":
        q = (today.month - 1) // 3
        cur = date(today.year, 3 * q + 1, 1)
        nxt = date(cur.year + (cur.month + 3 > 12), (cur.month + 2) % 12 + 1, 1)
        prev = date(cur.year - (cur.month == 1), (cur.month - 4) % 12 + 1, 1)
        return cur, nxt, prev, cur
    if period == "month":
        cur = today.replace(day=1)
        nxt = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        prev = date(cur.year - (cur.month == 1), (cur.month - 2) % 12 + 1, 1)
        return cur, nxt, prev, cur
    raise EngineError("Pick week, month or quarter.")


def change_text(cur: float, prev: float, period: str) -> str:
    if not prev:
        return f"Nothing to compare with last {period}." if not cur else f"New this {period} (none last {period})."
    pct = round(100 * (cur - prev) / abs(prev))
    if pct == 0:
        return f"Same as last {period}."
    return f"{'Up' if pct > 0 else 'Down'} {abs(pct)}% on last {period}."


# 7. Hide fields nobody fills in ---------------------------------------------------

def unused_field_ops(tree: dict[str, Any], fields: dict[str, Any], counts: dict[str, int], total: int) -> list[dict[str, Any]]:
    """Fields filled on no record at all (needs at least 20 records), not required,
    not read by any show/hide rule on the screen."""
    if total < 20:
        return []
    out = []
    for n, hidden in v2.screen_field_nodes(tree):
        name = n.get("name") or ""
        meta = fields.get(name) or {}
        if hidden or name not in counts or counts[name] or meta.get("required") or not n.get("anchor"):
            continue
        if str((n.get("attrs") or {}).get("required") or "").strip() not in {"", "0", "False", "false"} or v2.uses_in_screen(tree, name):
            continue
        out.append({"op": "set_attr", "node": n["id"], "attr": "invisible", "value": "1", "label": str(meta.get("string") or name)})
    return out[:40]


# 8. Stage checklist on the record --------------------------------------------------

CHECKLIST_PREFIX = f"{LAYER_PREFIX}_checklist"


def checklist_arch(stage_field: str, stages: list[dict[str, Any]], fields: dict[str, Any]) -> str:
    """A note at the top of the sheet listing what is still empty before the next
    stage. Odoo hides each line itself once the field is filled (show/hide rule),
    so the list is always about the record on screen."""
    data = ET.Element("data")
    spec = ET.SubElement(data, "xpath", {"expr": "//sheet/*[1]", "position": "before"})  # first thing on the sheet
    box = ET.Element("div", {"name": f"{CHECKLIST_PREFIX}_box", "class": "alert alert-info", "role": "status"})
    lines = 0
    for st in stages[:12]:
        val = st.get("value")
        if val is None:
            continue
        need = [x for x in (st.get("at_stage") or []) + (st.get("always") or []) if (fields.get(x["field"]) or {}).get("store", True) is not False]
        for x in need[:8]:
            f = x["field"]
            if not re.fullmatch(r"[a-z_][a-z0-9_]*", f):
                continue
            cond = f"{stage_field} != {val!r}" if not isinstance(val, int) else f"{stage_field} != {val}"
            div = ET.SubElement(box, "div", {"invisible": f"{f} or {cond}"})
            div.text = f"Before moving on from {st.get('label')}: fill in {x.get('label') or f}."
            lines += 1
    if not lines:
        raise EngineError("No stage on this screen needs extra fields, so there's nothing to list.")
    spec.append(box)
    return ET.tostring(data, encoding="unicode")


# 9. Step-by-step progress (kept on the record: it is the record's own data) -------

def steps_progress_arch(steps_arch: str, steps: list[dict[str, Any]], fields: dict[str, Any], screen_arch: str | None = None) -> str:
    root = ET.fromstring(steps_arch)
    nb_spec = root.find("xpath")
    nb = nb_spec.find("notebook") if nb_spec is not None else None
    if nb is None:
        return steps_arch
    bar = ET.Element("div", {"name": f"{v2.STEPS_PREFIX}_progress", "class": "d-flex gap-2 mb-2"})
    # Fields shown only to some groups can't drive a badge everyone may see (Odoo 17 refuses that).
    limited: set[str] = set()

    def _walk_groups(el: ET.Element, inherited: bool) -> None:
        g = inherited or bool(el.get("groups"))
        if el.tag == "field" and g and el.get("name"):
            limited.add(el.get("name"))
        for ch in el:
            _walk_groups(ch, g)

    _walk_groups(nb, False)
    if screen_arch:
        _walk_groups(ET.fromstring(screen_arch), False)
    for i, st in enumerate(steps, start=1):
        names = [n for n in st.get("field_names") or [] if n not in limited and (fields.get(n) or {}).get("store", True) is not False
                 and (fields.get(n) or {}).get("type") not in {"boolean", "one2many", "many2many"}][:8]
        if not names:
            continue
        done = ET.SubElement(bar, "span", {"class": "badge text-bg-success", "invisible": " or ".join(f"not {n}" for n in names)})
        done.text = f"Step {i} done"
        todo = ET.SubElement(bar, "span", {"class": "badge text-bg-light", "invisible": " and ".join(names)})
        todo.text = f"Step {i} to do"
    if len(bar):
        idx = list(nb_spec).index(nb)
        nb_spec.insert(idx, bar)
    return ET.tostring(root, encoding="unicode")


# 10. Accessibility fixes -----------------------------------------------------------

def button_words(arch: str) -> dict[str, str]:
    """Tooltip or spoken label each button already has in Odoo's own screen."""
    out: dict[str, str] = {}
    for b in ET.fromstring(arch).iter("button"):
        words = b.get("title") or b.get("aria-label")
        if b.get("name") and words:
            out.setdefault(b.get("name"), words)
    return out


def a11y_fix_ops(tree: dict[str, Any], fields: dict[str, Any], words_by_button: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Fixes that come from the database itself: a field's own label where the screen
    hides it, a button's own tooltip or action name where it has no words."""
    out = []
    for n, _p, hidden in v2.walk(tree):
        if hidden or not n.get("anchor"):
            continue
        attrs = n.get("attrs") or {}
        if n.get("tag") == "field" and str(attrs.get("nolabel") or "") in TRUE_WORDS and not attrs.get("string"):
            label = (fields.get(n.get("name") or "") or {}).get("string")
            if label and attrs.get("placeholder") and not attrs.get("aria-label"):
                out.append({"op": "set_attr", "node": n["id"], "attr": "aria-label", "value": str(label), "why": f"Screen readers will say '{label}'."})
        if n.get("tag") == "button" and not attrs.get("string") and attrs.get("icon"):
            words = (words_by_button or {}).get(n.get("name") or "")
            if words:
                out.append({"op": "set_attr", "node": n["id"], "attr": "string", "value": str(words), "why": f"The button now says '{words}'."})
    return out[:60]


# 11. Sample data per industry -------------------------------------------------------

INDUSTRY_WORDS: dict[str, dict[str, list[str]]] = {
    "retail": {"name": ["Corner Shop order", "Weekend sale", "Online basket"], "partner": ["Ada's Boutique", "Market Street Store", "City Kiosk"],
               "product": ["Cotton T-shirt", "Water bottle", "Phone case"]},
    "distribution": {"name": ["Pallet order", "Restock run", "Route delivery"], "partner": ["Northern Wholesale", "Harbour Depot", "Prime Logistics"],
                     "product": ["Carton of rice 25 kg", "Cooking oil 20 L", "Detergent pack"]},
    "services": {"name": ["Website retainer", "Audit engagement", "Training day"], "partner": ["Bright Legal", "Okoro & Co", "Lakeside Clinic"],
                 "product": ["Consulting hour", "Support plan", "Workshop seat"]},
    "manufacturing": {"name": ["Batch 42", "Line maintenance", "Custom order"], "partner": ["Steelworks Ltd", "Precision Parts", "Eastern Mills"],
                      "product": ["Steel bracket", "Gear housing", "Assembly kit"]},
    "hospitality": {"name": ["Room booking", "Event package", "Group stay"], "partner": ["Seaside Hotel", "Palm Guest House", "Grand Events"],
                    "product": ["Deluxe room night", "Breakfast", "Conference hall"]},
    "healthcare": {"name": ["Clinic supply order", "Lab request", "Equipment service"], "partner": ["Hope Clinic", "Unity Pharmacy", "CarePoint Lab"],
                   "product": ["Gloves box", "Blood test kit", "Thermometer"]},
    "nonprofit": {"name": ["Donation pledge", "Grant report", "Volunteer drive"], "partner": ["Green Earth Fund", "Community Trust", "Youth Aid"],
                  "product": ["Monthly donation", "School kit", "Food parcel"]},
}


def industry_sample_records(names: list[str], fields: dict[str, Any], industry: str, count: int = 3) -> list[dict[str, Any]]:
    words = INDUSTRY_WORDS.get(industry)
    if not words:
        raise EngineError("Pick one of the listed industries.")
    recs = v2.sample_records(names, fields, count)
    for i, rec in enumerate(recs):
        rec["display_name"] = f"Sample: {words['name'][i % 3]}"
        for n in names:
            meta = fields.get(n) or {}
            rel = str(meta.get("relation") or "")
            if n in {"name", "display_name"} and meta.get("type") in {"char", "text"}:
                rec[n] = f"Sample: {words['name'][i % 3]}"
            elif meta.get("type") == "many2one" and rel == "res.partner":
                rec[n] = f"Sample: {words['partner'][i % 3]}"
            elif meta.get("type") == "many2one" and rel.startswith("product."):
                rec[n] = f"Sample: {words['product'][i % 3]}"
        rec["__industry"] = industry
    return recs


# 15. More starters (stock fields only; missing ones are listed, not made) -----------

EXTRA_STARTERS: dict[str, dict[str, Any]] = {
    "hospitality": {"label": "Hotel & events", "models": {
        "res.partner": [("Guest", ["name", "phone", "email", "lang"]), ("Stay", ["category_id", "comment", "property_product_pricelist"])],
        "sale.order": [("Booking", ["partner_id", "date_order", "validity_date", "pricelist_id"]), ("Notes", ["note", "client_order_ref"])]}},
    "healthcare": {"label": "Clinic", "models": {
        "res.partner": [("Patient contact", ["name", "phone", "email", "street", "city"]), ("Notes", ["comment", "category_id"])],
        "product.template": [("Item", ["name", "default_code", "barcode", "categ_id"]), ("Stock", ["uom_id", "list_price", "standard_price"])]}},
    "nonprofit": {"label": "Non-profit", "models": {
        "res.partner": [("Donor", ["name", "email", "phone", "category_id"]), ("Address", ["street", "city", "country_id"])],
        "crm.lead": [("Pledge", ["name", "partner_id", "expected_revenue", "date_deadline"]), ("Follow-up", ["user_id", "tag_ids", "description"])]}},
}


def register_extra_starters() -> None:
    for k, s in EXTRA_STARTERS.items():
        v2.STARTERS.setdefault(k, s)


# 12. Brand presets --------------------------------------------------------------------

def preset_from_company(row: dict[str, Any], layout_xmlid: str | None) -> dict[str, Any]:
    return {"primary_color": row.get("primary_color") or None, "secondary_color": row.get("secondary_color") or None,
            "font": row.get("font") or None, "layout_xmlid": layout_xmlid}


# 16. Slack / Teams ---------------------------------------------------------------------

def check_webhook(url: str) -> str:
    u = urlparse(url.strip())
    host = (u.hostname or "").lower()
    if u.scheme != "https":
        raise EngineError("The link has to start with https://.")
    if host == "hooks.slack.com":
        return "slack"
    if host.endswith(".logic.azure.com") or host.endswith(".powerplatform.com"):
        return "teams_workflow"  # Teams Workflows (Power Automate) "when a webhook request is received"
    if host.endswith(".webhook.office.com") or host == "outlook.office.com":
        return "teams"
    raise EngineError("Use a Slack incoming-webhook link, a Microsoft Teams webhook link, or a Teams Workflows (Power Automate) link.")


def mask_url(url: str) -> str:
    u = urlparse(url)
    return f"{u.scheme}://{u.hostname}/…{url[-4:]}" if url else ""


def chat_payload(kind: str, title: str, text: str) -> dict[str, Any]:
    """Slack text; Teams webhooks and Teams Workflows both take an Adaptive Card message."""
    if kind == "slack":
        return {"text": f"*{title}*\n{text}"}
    return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
        "type": "AdaptiveCard", "version": "1.4", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "body": [{"type": "TextBlock", "size": "Medium", "weight": "Bolder", "text": title}, {"type": "TextBlock", "wrap": True, "text": text}]}}]}


# 19. Layout test ends itself -------------------------------------------------------------

def test_should_end(result: dict[str, Any], started: datetime, now: datetime) -> tuple[bool, str]:
    if result.get("verdict") in {"A", "B"}:
        return True, f"Ended by itself: {result.get('text')}" + (" Layout B won; publish it for everyone from the Roles tab if you want it." if result["verdict"] == "B" else "")
    if now - started > timedelta(days=60):
        return True, "Ended by itself after 60 days without a clear result. Everyone has the normal layout again."
    return False, ""


# 20. Explain sheet ---------------------------------------------------------------------------

def explain_html(title: str, steps: list[dict[str, Any]], lang_note: str) -> str:
    esc = lambda t: (str(t or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    items = "".join(f"<li><h3>{esc(s.get('title'))}</h3><p>{esc(s.get('text'))}</p></li>" for s in steps)
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title>"
            "<style>body{font-family:Arial,sans-serif;margin:32px;color:#1f2937}h1{font-size:22px}h3{font-size:15px;margin:12px 0 4px}"
            "li{margin-bottom:8px}p{margin:0;line-height:1.45}.note{color:#6b7280;font-size:12px}@media print{a{display:none}}</style></head>"
            f"<body><h1>{esc(title)}</h1><p class='note'>{esc(lang_note)}</p><ol>{items}</ol></body></html>")


TRANSLATE_SYSTEM = ("Translate each 'title' and 'text' into the target language. Keep field names and numbers exactly. "
                    "Reply with the same number of steps in the same order.")
TRANSLATE_SCHEMA = {"type": "object", "properties": {"steps": {"type": "array", "items": {"type": "object", "properties": {
    "title": {"type": "string"}, "text": {"type": "string"}}, "required": ["title", "text"]}}}, "required": ["steps"]}


def check_translation(src: list[dict[str, Any]], got: Any) -> list[dict[str, Any]] | None:
    steps = (got or {}).get("steps") if isinstance(got, dict) else None
    if not isinstance(steps, list) or len(steps) != len(src):
        return None
    out = []
    for a, b in zip(src, steps, strict=True):
        nums_a, nums_b = re.findall(r"\d+", a["text"]), re.findall(r"\d+", str(b.get("text") or ""))
        if sorted(nums_a) != sorted(nums_b) or not str(b.get("title") or "").strip():
            return None
        out.append({**a, "title": str(b["title"])[:200], "text": str(b["text"])[:2000]})
    return out


# 2e. Scanned PDFs: page pictures for picture reading -----------------------------------

def pdf_page_pngs(raw: bytes, max_pages: int = 2, scale: float = 2.0) -> list[bytes]:
    import io

    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(raw)
    out: list[bytes] = []
    try:
        for i in range(min(len(doc), max_pages)):
            img = doc[i].render(scale=scale).to_pil()
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG", optimize=True)
            out.append(buf.getvalue())
    finally:
        doc.close()
    return out


def outline(tree: dict[str, Any], limit: int = 300) -> list[dict[str, Any]]:
    """Visible items in order, for a side-by-side list: tabs, groups, fields, buttons."""
    out: list[dict[str, Any]] = []
    for n, _p, hidden in v2.walk(tree):
        if n.get("tag") in {"page", "group", "field", "button"} and len(out) < limit:
            out.append({"node": n["id"], "tag": n["tag"], "label": str(n.get("label") or n.get("name") or n["tag"]), "hidden": bool(hidden)})
    return out


def chat_accepted(url: str, status: int, body: str) -> bool:
    """Slack answers 200 'ok'; Teams connectors answer 200 '1' (anything else, even an empty 200, isn't a confirmation); Teams workflows answer 200/202."""
    host = (urlparse(url).hostname or "").lower()
    if host == "hooks.slack.com":
        return status == 200 and body == "ok"
    if host.endswith(".logic.azure.com") or host.endswith(".powerplatform.com"):
        return status in {200, 202}
    return status == 200 and body == "1"
