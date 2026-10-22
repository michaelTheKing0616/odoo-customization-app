"""Stock-first checks, outside-service routing and the decision register (flag INGENIUM_BRIEF_CHECKLIST).

The checklist call (brief_checklist) proposes, per build item: candidate stock apps/models, any
outside service it touches, and the item TYPE with a decision. Everything here is deterministic
verification of those proposals against THIS database's stage-2 snapshot (installed/installable
modules, model index, edition, version, server-action kinds, hosting). No word lists decide meaning.

Route ladder for an outside service:
  1 stock   - a stock connector module installed or installable on this DB
  2 webhook - Odoo's built-in webhook automation (send: server action 'webhook'; receive: automation
              trigger 'on_webhook'), when the service needs no signed API calls
  3 bridge  - an Ingenium Bridge connector exists for it today (BRIDGE_CONNECTORS)
  4 decline - with a plain reason naming what is needed
"""

from __future__ import annotations

import re
from typing import Any

# What app/bridge implements today (inspected: connector.ShopifyConnector + Odoo probe).
BRIDGE_CONNECTORS = frozenset({"shopify"})
ITEM_TYPES = ("money", "approval", "person_ref", "relation", "multi_company", "status", "other")
# Risk is a property of the item TYPE / declared effect, never of the wording.
RISKY_TYPES = frozenset({"money", "approval"})
RISKY_EFFECTS = ("deletes_records", "emails_customers", "needs_code")
MAX_BLOCKING = 3

CHECKLIST_EXTRA = (
    ' For each build item also give: "stock_options": [{"module": technical module name, "model": '
    'stock model or "", "name": plain app name}] (stock Odoo ways to do it, best first; [] if none), '
    '"plan": "stock" or "custom", "custom_reason": why stock does not fit (required when plan is '
    'custom and a stock option exists), "service": name of any outside service it talks to (e.g. '
    'Paystack, an SMS gateway, a courier, WhatsApp) or "", "service_direction": "send|receive|sync|" '
    '("sync" = two-way API calls), "service_needs_api": true when it needs signed/authenticated API '
    'calls, "service_modules": [technical Odoo connector modules that would do it, e.g. payment_x], '
    '"service_type": "sms|whatsapp|email|voip|livechat|payment|shipping|other|" (what kind of channel), '
    '"type": "money|approval|person_ref|relation|multi_company|status|other", "deletes_records": bool, '
    '"emails_customers": bool, "needs_code": bool, and "decision": {"value": the choice, "source": '
    '"quoted" (the brief states it) | "default" (a safe common default) | "ask", "quote": exact brief '
    'words when quoted, "question": one plain question when ask, "options": [2-4 short answers]}. '
    "Decisions by type: money -> currency and tax; approval -> who approves and the stages; "
    "person_ref -> customer/contact (res.partner) vs employee (hr.employee) vs app user (res.users); "
    "relation -> one or many and to what; multi_company -> shared or per company; status -> the stages."
    ' Also "delivery_shape": one of record_workflow|record_automation|stock_extension|integration|'
    'analysis_prediction|custom_runtime|unsupported (what kind of thing this is; code decides whether '
    "to build it). analysis_prediction = forecasts/NPV/scoring that is not a records app; "
    "unsupported = cannot be delivered here."
    ' Also "facts": {"keeps_records": bool (people enter or track records of something), '
    '"output_is_derived": bool (the result is a number/date computed from many records or from the future, '
    'e.g. a projection, not a value someone enters), "needs_custom_code": bool}. Describe the item only.'
)


def _mod_state(snap: Any, module: str) -> str:
    if not module or snap is None:
        return "unknown"
    if module in (getattr(snap, "modules", None) or {}):
        return "installed"
    if module in (getattr(snap, "installable", None) or {}):
        return "installable"
    return "absent"


def _online(grounding: Any) -> bool:
    return bool(getattr(grounding, "online", False)) or getattr(grounding, "hosting", "") == "online"


def stock_check(item: dict[str, Any], snap: Any) -> dict[str, Any]:
    """Code decides stock vs custom from the live snapshot. The AI's custom_reason is display text
    only, never authorization. Nothing is called missing without snapshot proof."""
    options = []
    for o in (item.get("stock_options") or [])[:4]:
        if not isinstance(o, dict):
            continue
        mod, model = str(o.get("module") or "").strip(), str(o.get("model") or "").strip()
        state = _mod_state(snap, mod) if mod else "unknown"
        if model and snap is not None and model in (getattr(snap, "index", None) or {}):
            state = "installed"
        options.append({"module": mod, "model": model, "name": str(o.get("name") or mod or model)[:60], "state": state})
    usable = [o for o in options if o["state"] in {"installed", "installable"}]
    ai_reason = str(item.get("custom_reason") or "").strip()[:200]
    base = {"item": item.get("item"), "options": options, "ai_reason": ai_reason}
    if usable:
        best = sorted(usable, key=lambda o: o["state"] != "installed")[0]
        verb = "Using Odoo's" if best["state"] == "installed" else "Install Odoo's"
        return dict(base, choice="stock", use=best, label=f"{verb} {best['name']}",
                    install=best["module"] if best["state"] == "installable" else "",
                    overrode_custom=item.get("plan") == "custom")
    proven_absent = [o for o in options if o["state"] == "absent"]
    why = (f"Odoo's {proven_absent[0]['name']} is not available on this database" if proven_absent and len(proven_absent) == len(options)
           else "no stock Odoo app does this here" if not options else "")
    return dict(base, choice="custom", verified_reason=why,
                label=f"Custom: {why}" if why else "Custom")


# Main record model of each Odoo domain app (Odoo structure, not brief wording).
DOMAIN_APPS = {
    "helpdesk": ("Helpdesk", "helpdesk.ticket"), "repair": ("Repairs", "repair.order"),
    "project": ("Project", "project.task"), "crm": ("CRM", "crm.lead"), "sale": ("Sales", "sale.order"),
    "purchase": ("Purchase", "purchase.order"), "maintenance": ("Maintenance", "maintenance.request"),
    "sale_renting": ("Rental", "sale.order"), "event": ("Events", "event.event"),
    "hr_holidays": ("Time Off", "hr.leave"), "hr_expense": ("Expenses", "hr.expense"),
    "fleet": ("Fleet", "fleet.vehicle"), "mrp": ("Manufacturing", "mrp.production"),
    "stock": ("Inventory", "stock.picking"), "appointment": ("Appointments", "appointment.type"),
    "industry_fsm": ("Field Service", "project.task"), "planning": ("Planning", "planning.slot"),
}


def stock_catalog(snap: Any) -> str:
    """Code-supplied list of domain apps on this database (installed or installable) for the checklist."""
    if snap is None:
        return ""
    rows = []
    for mod, (name, model) in DOMAIN_APPS.items():
        st = _mod_state(snap, mod)
        if st in {"installed", "installable"}:
            rows.append(f"- {name}: module {mod}, model {model} ({st})")
    return ("\n\nOdoo apps on this database (data). When an item is a kind of record one of these "
            "apps already keeps, list it in stock_options:\n" + "\n".join(rows)) if rows else ""


GENERIC_HOSTS = frozenset({
    "res.partner", "res.users", "res.company", "res.country", "res.currency",
    "calendar.event", "mail.activity", "mail.message", "mail.followers",
})
DOMAIN_HINT = re.compile(
    r"^(sale\.|purchase\.|project\.|helpdesk\.|repair\.|crm\.|stock\.|mrp\.|hr\.|fleet\.|account\.move|account\.payment)"
)


def _is_generic(host: str) -> bool:
    return host in GENERIC_HOSTS or host.startswith("mail.")


def _is_domain(host: str) -> bool:
    return bool(DOMAIN_HINT.match(host or "")) and not _is_generic(host)


def align_checks_by_id(design: Any, checks: list[dict[str, Any]], snap: Any) -> int:
    """A check the AI left custom ("no stock app") is set to stock when the design itself puts that
    requirement (by id) on a domain app's model that is on the database or installable (code
    catalog DOMAIN_APPS / compat). Deterministic: same ids -> same decision."""
    from app.compat.odoo_versions import module_for_model

    index = getattr(snap, "index", None) or {}
    hosts: dict[str, set[str]] = {}
    for e in getattr(design, "stock_extensions", None) or []:
        for f in e.fields:
            for rid in [getattr(f, "requirement_id", "") or ""] + list(getattr(f, "requirement_ids", None) or []):
                if rid:
                    hosts.setdefault(rid, set()).add(e.model)
    n = 0
    for c in checks:
        if c.get("choice") == "stock":
            continue
        ids = {str(x) for x in c.get("requirement_ids") or []}
        cand = sorted({h for rid in ids for h in hosts.get(rid, ()) if _is_domain(h)})
        for h in cand:
            mod = module_for_model(h, getattr(snap, "major", None))
            state = "installed" if h in index else _mod_state(snap, mod)
            if state in {"installed", "installable"}:
                c.update(choice="stock", use={"model": h, "module": mod, "name": mod},
                         install=mod if state == "installable" else "", matched_by="requirement_id",
                         verified_reason="", label=f"Using Odoo's {mod} ({h})")
                n += 1
                break
    return n


def enforce_stock_first(design: Any, checks: list[dict[str, Any]], snap: Any,
                        protected: Any = lambda m: m.startswith("account.")) -> list[str]:
    """Rewrite custom models onto the verified stock host (fields -> stock_extensions, automations,
    relations, rules and links retargeted). Match by requirement_id first; name-token fallback only
    for legacy rows without an id. Generic hosts (res.partner, calendar.event, mail.*) are never
    used as the host for a new record type (they become a relation). Installable domain hosts
    convert with an install suggestion. Custom stays only with a code-verified reason."""
    from app.ai_conversation.app_design import DesignField, Integration, StockExtension

    notes: list[str] = []
    index = getattr(snap, "index", None) or {}
    toks = lambda t: {w[:5] for w in re.findall(r"[a-z]{4,}", str(t or "").casefold())}  # noqa: E731  legacy
    taken: set[str] = set()

    def find_model(c: dict[str, Any]):
        rids = {str(c.get("id") or "")} | {str(x) for x in (c.get("requirement_ids") or [])}
        rids.discard("")
        by_id = [m for m in design.new_models if m.name not in taken and rids & (
            {getattr(m, "requirement_id", "") or ""} | set(getattr(m, "requirement_ids", None) or []))]
        if by_id:
            return by_id[0], "id"
        want = toks(c.get("item"))
        cand = [m for m in design.new_models if m.name not in taken and want & toks(m.label or m.name)]
        if not cand:
            return None, ""
        return max(cand, key=lambda x: len(want & toks(x.label or x.name))), "legacy_stem"

    def convert(m, host, c, *, to_install: str = ""):
        have = snap.fields_of(host) if host in index else set()
        add = [f for f in m.fields if f.name not in have and f.name != "x_currency_id"
               and not (f.ttype == "many2one" and f.relation == host)]
        ext = next((e for e in design.stock_extensions if e.model == host), None)
        if ext is None:
            ext = StockExtension(model=host, fields=[], reason=f"Holds {m.label or m.name} (stock-first)")
            design.stock_extensions.append(ext)
        seen = {f.name for f in ext.fields}
        for f in add:
            if f.name in seen:
                continue
            nf = DesignField(**{k: getattr(f, k) for k in DesignField.__dataclass_fields__})
            if not getattr(nf, "requirement_ids", None) and c.get("id"):
                try:
                    nf.requirement_ids = list(c.get("requirement_ids") or [c["id"]])  # type: ignore[attr-defined]
                except Exception:
                    pass
            ext.fields.append(nf)
            seen.add(f.name)
        if to_install:
            mod = to_install
            if not any(i.module == mod for i in design.integrations):
                design.integrations.append(Integration(
                    app=str(c["use"].get("name") or mod), module=mod, models=[host], required=False,
                    installed=False, status="available",
                    note="Install this Odoo app; the design builds on it."))
            c["install_suggested"] = mod
        old = m.name
        design.new_models = [x for x in design.new_models if x.name != old]
        for x in design.new_models + design.stock_extensions:
            for f in x.fields:
                if f.relation == old:
                    f.relation = host
        for a in design.automations:
            if a.get("target_model") == old:
                a["target_model"] = host
        for r in design.record_rules:
            if r.get("model") == old:
                r["model"] = host
        design.relations = [{k: (host if v == old else v) for k, v in r.items()} for r in design.relations]
        c["converted"] = m.label or old
        notes.append(f"Built {m.label or old} on Odoo's {c['use'].get('name') or host} instead of a custom copy.")

    for c in checks:
        if c.get("choice") != "stock":
            continue
        host = str((c.get("use") or {}).get("model") or "")
        m, how = find_model(c)
        if m is None:
            continue
        if how == "legacy_stem":
            c["matched_by"] = "legacy_stem"  # visible: no requirement_id on the design node
        to_install = str(c.get("install") or "")
        # Generic hosts must not swallow a new record type: keep custom, link to the generic model.
        if host and _is_generic(host):
            if not any(f.ttype == "many2one" and f.relation == host for f in m.fields):
                m.fields.append(DesignField(name="x_" + host.split(".")[-1] + "_id", ttype="many2one",
                                            string=host.split(".")[-1].replace("_", " ").title(), relation=host))
            c["verified_reason"] = f"{host} is a shared Odoo record; this stays its own list and links to it"
            taken.add(m.name); c["custom_kept"] = m.label or m.name; continue
        if protected(host):
            c["verified_reason"] = f"{host} is protected; App Studio does not change it"
            taken.add(m.name); c["custom_kept"] = m.label or m.name; continue
        if any(f.ttype == "many2one" and f.relation == host for f in m.fields) and not to_install:
            # Lines belonging to an installed domain host stay as child models.
            c["verified_reason"] = f"it is a list of lines that belong to {host}"
            taken.add(m.name); c["custom_kept"] = m.label or m.name; continue
        if not host:
            c["verified_reason"] = "no stock model named"
            taken.add(m.name); c["custom_kept"] = m.label or m.name; continue
        if host not in index and not to_install:
            c["verified_reason"] = ""  # no snapshot proof either way
            taken.add(m.name); c["custom_kept"] = m.label or m.name; continue
        # Domain host installed OR installable: convert (installable gets an install suggestion).
        convert(m, host, c, to_install=to_install)
    return notes



# Messaging channels by structured type -> Odoo modules (17-20) and the edition that ships them.
CHANNELS: dict[str, dict[str, Any]] = {
    "sms": {"modules": ("sms",), "edition": "any", "label": "SMS"},
    "email": {"modules": ("mail",), "edition": "any", "label": "email"},
    "livechat": {"modules": ("im_livechat",), "edition": "any", "label": "live chat"},
    "whatsapp": {"modules": ("whatsapp",), "edition": "enterprise", "label": "WhatsApp"},
    "voip": {"modules": ("voip",), "edition": "enterprise", "label": "phone calls (VoIP)"},
}


def channel_route(item: dict[str, Any], snap: Any) -> dict[str, Any] | None:
    """Code decides the stock module for a messaging channel from its type, version and edition."""
    ch = CHANNELS.get(str(item.get("service_type") or "").strip().lower())
    service = str(item.get("service") or "").strip()
    if ch is None or snap is None:
        return None
    edition = str(getattr(snap, "edition", "") or "").lower()
    if ch["edition"] == "enterprise" and edition == "community":
        return {"service": service, "route": "decline", "item": str(item.get("item") or "")[:120],
                "reason": f"Odoo's {ch['label']} app comes with Odoo Enterprise, and this database is Community",
                "label": f"{service}: not available here. Odoo's {ch['label']} app needs Odoo Enterprise; this database is Community."}
    for mod in ch["modules"]:
        state = _mod_state(snap, mod)
        if state in {"installed", "installable"}:
            return {"service": service, "route": "stock", "module": mod,
                    "label": f"{service}: {'uses' if state == 'installed' else 'install'} Odoo's {mod} app"}
    return None


def route_service(item: dict[str, Any], snap: Any, grounding: Any = None) -> dict[str, Any] | None:
    service = str(item.get("service") or "").strip()
    if not service:
        return None
    online = _online(grounding)
    by_type = channel_route(item, snap)
    if by_type is not None and by_type["route"] == "stock":
        return by_type
    for mod in (item.get("service_modules") or [])[:4]:
        state = _mod_state(snap, str(mod))
        if state in {"installed", "installable"}:
            return {"service": service, "route": "stock", "module": mod,
                    "label": f"{service}: {'uses' if state == 'installed' else 'install'} Odoo's {mod} connector"}
    direction = str(item.get("service_direction") or "").lower()
    needs_api = item.get("service_needs_api") is True or direction == "sync"
    kinds = set(snap.selection_of("ir.actions.server", "state")) if snap is not None else set()
    triggers = set(snap.selection_of("base.automation", "trigger")) if snap is not None else set()
    if not needs_api and ((direction == "send" and "webhook" in kinds) or (direction == "receive" and "on_webhook" in triggers)):
        return {"service": service, "route": "webhook",
                "label": f"{service}: Odoo {'sends' if direction == 'send' else 'receives'} it with a built-in webhook automation"}
    key = re.sub(r"[^a-z0-9]", "", service.lower())
    if key in BRIDGE_CONNECTORS:
        return {"service": service, "route": "bridge", "label": f"{service}: connected through Ingenium Bridge"}
    if by_type is not None:
        return by_type  # edition decline, with its plain reason
    need = ("an Ingenium Bridge connector for it (not built yet)" if online else
            "an Ingenium Bridge connector or custom code on Odoo.sh or self-hosted")
    return {"service": service, "route": "decline", "reason": f"needs {need}", "item": str(item.get("item") or "")[:120],
            "label": f"{service}: not connected. This needs {need}."}


def register(items: list[dict[str, Any]], brief_has: Any) -> dict[str, Any]:
    """Decision register by item TYPE. quoted (quote found) | default (editable) | question.
    Only risky types/effects may block, at most MAX_BLOCKING; the rest become shown defaults."""
    quoted, defaults, asks = [], [], []
    for i in items:
        d = i.get("decision") if isinstance(i.get("decision"), dict) else {}
        typ = i.get("type") if i.get("type") in ITEM_TYPES else "other"
        if not d or typ == "other" and not any(i.get(e) is True for e in RISKY_EFFECTS):
            continue
        value = str(d.get("value") or "").strip()[:160]
        src = str(d.get("source") or "").lower()
        row = {"item": i.get("item"), "type": typ, "value": value, "id": i.get("id"),
               "options": [str(o)[:60] for o in (d.get("options") or [])[:4]]}
        if src == "quoted" and brief_has(str(d.get("quote") or "")):
            quoted.append(dict(row, quote=str(d.get("quote"))[:200]))
            continue
        risky = typ in RISKY_TYPES or any(i.get(e) is True for e in RISKY_EFFECTS)
        if src == "ask" and risky and d.get("question"):
            rec = value or (row["options"][0] if row["options"] else "")
            asks.append(dict(row, question=str(d["question"])[:200], recommended=rec,
                             options=([rec] + [o for o in row["options"] if o != rec]) if rec else row["options"]))
        else:
            defaults.append(row)
    blocking, extra = asks[:MAX_BLOCKING], asks[MAX_BLOCKING:]
    # Over the cap: not asked; the recommended answer becomes a shown, editable default.
    defaults += [dict({k: v for k, v in a.items() if k not in {"question", "recommended"}}, value=a.get("value") or a.get("recommended", ""))
                 for a in extra]
    return {"quoted": quoted, "defaults": [d for d in defaults if d["value"]], "questions": blocking}
