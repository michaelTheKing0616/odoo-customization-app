"""Deterministic quality repair for an app design (AI or outline).

The AI proposes; this pass only *repairs* shapes a senior Odoo designer would
reject. It never replaces the design: list-like requirements stop being free
text, explainability gets factor lines, proactive actions / alert rules get
their own records, subscription references become real links, counts become
computed, and a "section on the customer form" extends res.partner.
"""

from __future__ import annotations

import re
from typing import Any

from app.ai_conversation.app_design import (
    AppDesign,
    DesignField,
    DesignModel,
    StockExtension,
    _model_name,
    _snake,
)

OPERATORS = [
    ["gt", "Greater than"],
    ["gte", "At least"],
    ["lt", "Less than"],
    ["lte", "At most"],
    ["eq", "Equal to"],
    ["change_pct", "Changes by more than (%)"],
]
_SIGNAL_CUES = (
    ("open_tickets", "Open support tickets", r"tickets?"),
    ("critical_tickets", "Critical tickets", r"critical (issues|tickets)|severity"),
    ("revenue_change", "Revenue change (%)", r"revenue"),
    ("days_since_interaction", "Days since last interaction", r"interact"),
    ("days_to_renewal", "Days to renewal", r"renewal"),
    ("overdue_invoices", "Overdue invoices", r"invoice|payment"),
    ("nps", "Satisfaction / NPS", r"\bnps\b|satisfaction"),
    ("recent_purchases", "Recent purchases", r"purchas|sales activity"),
    ("open_opportunities", "Open opportunities", r"opportunit"),
)
_LIST_TEXT = re.compile(
    r"(?i)^(conditions?|operators?|time windows?|owners?|assignees?|milestones?|tasks?|"
    r"positive or negative scoring|health score rules|alert rules|risk types|customer segments|"
    r"score thresholds?|thresholds|default action templates|contributing factors|"
    r"major contributing factors|factors|risks)$"
)


def _f(string: str, ttype: str, **kw: Any) -> DesignField:
    suffix = "_ids" if ttype in {"one2many", "many2many"} else "_id" if ttype == "many2one" else ""
    name = kw.pop("name", "") or f"x_{_snake(string)[:40]}{suffix}"
    return DesignField(name=name, string=string, ttype=ttype, **kw)


def _find(design: AppDesign, pat: str) -> DesignModel | None:
    return next((m for m in design.new_models if re.search(pat, f"{m.name} {m.label}", re.I)), None)


def _has(m: DesignModel, pat: str) -> bool:
    return any(re.search(pat, f"{f.name} {f.string}", re.I) for f in m.fields)


def _child(design: AppDesign, parent: DesignModel, label: str, fields: list[DesignField], why: str,
           o2m_label: str) -> DesignModel | None:
    if len(design.new_models) >= design.model_budget:
        design.notes.append(f"'{label}' lines were not added: the model limit for this brief is reached.")
        return None
    name = _model_name(label)
    if any(m.name == name for m in design.new_models):
        return next(m for m in design.new_models if m.name == name)
    link = _f(parent.label or "Parent", "many2one", relation=parent.name, required=True,
              name=f"x_{parent.name[2:]}_id")
    child = DesignModel(name=name, label=label, fields=[_f("Name", "char", name="x_name"), link, *fields],
                        views=["list", "form"], why=why)
    design.new_models.append(child)
    parent.fields.append(_f(o2m_label, "one2many", relation=name, inverse_name=link.name,
                            name=f"x_{_snake(o2m_label)[:40]}_ids"))
    return child


def strengthen_design(design: AppDesign, prompt: str, *, sales_ok: bool = True) -> list[str]:
    """Repair in place; return plain notes describing what changed."""
    text = prompt or ""
    # Repairs that ADD records or fields need the owner's own words as evidence. A terse brief is
    # expanded by the AI first; words the expansion introduced ("alerts", "customer form") must not
    # create templated models (root cause of unauthorised inventions on terse/voice briefs).
    from app.ai_conversation.brief_checklist import source_brief

    owner = source_brief(text)
    done: list[str] = authorize_step(design, owner)
    design.model_budget = max(design.model_budget, min(12, len(design.new_models) + 4))
    signals = [[k, lbl] for k, lbl, pat in _SIGNAL_CUES if re.search(pat, text, re.I)] or [
        ["value", "Value"]
    ]
    computed: list[str] = []
    rule_m = _find(design, r"rule(?!.*alert)") 
    risk_m = _find(design, r"\brisk\b|_risk$")
    alert_m = _find(design, r"alert")
    for m in list(design.new_models):
        new_fields: list[DesignField] = []
        for f in m.fields:
            low = (f.string or f.name).lower().strip()
            low = re.sub(r"^x_", "", low).replace("_", " ") if not f.string else low
            if f.ttype in {"text", "char"} and _LIST_TEXT.match(low):
                if low.startswith("condition"):
                    new_fields.append(_f("Signal", "selection", selection=signals))
                elif low.startswith("operator"):
                    new_fields.append(_f("Operator", "selection", selection=OPERATORS))
                elif low.startswith("time window"):
                    new_fields.append(_f("Time window (days)", "integer", name="x_window_days"))
                elif low.startswith(("owner", "assignee")):
                    new_fields.append(_f("Owners", "many2many", relation="res.users", name="x_owner_ids"))
                elif low.startswith("positive or negative"):
                    new_fields.append(_f("Effect", "selection", name="x_effect",
                                         selection=[["add", "Add points"], ["subtract", "Subtract points"]]))
                elif low.startswith(("milestone", "task")):
                    if not any(x.name == _model_name(f"{m.label} Step") for x in design.new_models):
                        _child(design, m, f"{m.label} Step", [
                            _f("Kind", "selection", selection=[["milestone", "Milestone"], ["task", "Task"]]),
                            _f("Target date", "date", name="x_target_date"),
                            _f("Owner", "many2one", relation="res.users", name="x_owner_id"),
                            _f("Done", "boolean", name="x_done"),
                        ], "Milestones and tasks are separate lines, each with an owner and date.",
                            "Milestones and tasks")
                elif "factor" in low:
                    _child(design, m, "Health Score Factor" if "health" in text.lower() else f"{m.label} Factor", [
                        _f("Signal", "selection", selection=signals),
                        _f("Points", "float", name="x_points"),
                    ], "Explains a score: each line is one factor and the points it added or removed.",
                        "Contributing factors")
                elif low == "risks" and risk_m and risk_m is not m:
                    new_fields.append(_f("Risks", "many2many", relation=risk_m.name, name="x_risk_ids"))
                elif re.match(r"score thresholds?|thresholds", low) and m.fields and re.search("config|setting", m.name):
                    new_fields += [_f("Healthy from", "integer", name="x_healthy_from"),
                                   _f("Stable from", "integer", name="x_stable_from"),
                                   _f("At risk from", "integer", name="x_at_risk_from")]
                elif low == "health score rules" and rule_m:
                    pass  # rules are their own records; config should not duplicate them
                elif low == "alert rules":
                    pass  # becomes the Alert Rule model below
                elif low == "customer segments":
                    new_fields.append(_f("Customer segments", "many2many", relation="res.partner.category",
                                         name="x_segment_ids"))
                elif low == "risk types":
                    pass  # risk type is a selection on the risk record
                elif low == "default action templates":
                    pass  # templates live on the recommended action record
                else:
                    new_fields.append(f)
                    continue
                done.append(f"{m.label}: '{f.string or f.name}' is no longer free text.")
                continue
            if re.match(r"score thresholds?$", low) and re.search("config|setting", m.name):
                new_fields += [_f("Healthy from", "integer", name="x_healthy_from"),
                               _f("Stable from", "integer", name="x_stable_from"),
                               _f("At risk from", "integer", name="x_at_risk_from")]
                done.append(f"{m.label}: score thresholds are one number per status.")
                continue
            if low == "thresholds" and f.ttype == "float":
                f.string, f.name = "Threshold", "x_threshold"
            if re.search(r"contract|subscription", low) and f.ttype in {"char", "text"}:
                if sales_ok:
                    new_fields.append(_f("Subscription / order", "many2one", relation="sale.order",
                                         name="x_sale_order_id"))
                    done.append(f"{m.label}: the contract is now a link to the sales order.")
                    continue
            if f.ttype in {"integer", "float"} and re.match(r"(open|number of|current) ", low):
                f.help = (f.help + " Calculated automatically (custom code), not typed in.").strip()
                computed.append(f"{m.label}: {f.string}")
            new_fields.append(f)
        m.fields = new_fields
    # Rule model gets a threshold/points pair if the repair left none.
    if rule_m and not _has(rule_m, r"threshold"):
        rule_m.fields.append(_f("Threshold", "float", name="x_threshold"))
    # Recommended actions with a "why".
    if re.search(r"(?i)recommended actions?|proactive|next best action", owner) and not _find(design, r"recommended|action"):
        if len(design.new_models) < design.model_budget:
            fields = [_f("Name", "char", name="x_name"),
                      _f("Customer", "many2one", relation="res.partner", name="x_customer_id"),
                      _f("Why", "text", name="x_why", help="The reason this action is recommended."),
                      _f("Priority", "selection", selection=[["low", "Low"], ["normal", "Normal"], ["high", "High"]]),
                      _f("Owner", "many2one", relation="res.users", name="x_owner_id"),
                      _f("Due date", "date", name="x_due_date"),
                      _f("Status", "selection", selection=[["open", "Open"], ["done", "Done"], ["dismissed", "Dismissed"]])]
            if risk_m:
                fields.append(_f("Risk", "many2one", relation=risk_m.name, name="x_risk_id"))
            design.new_models.append(DesignModel(name=_model_name("Recommended Action"), label="Recommended Action",
                                                 fields=fields, views=["list", "form", "kanban"],
                                                 why="The brief asks for proactive actions with the reason behind each."))
            done.append("Added Recommended Action, with the reason for each action.")
    if re.search(r"(?i)\balerts?\b", owner) and not alert_m and len(design.new_models) < design.model_budget:
        design.new_models.append(DesignModel(name=_model_name("Alert Rule"), label="Alert Rule", is_config=True,
                                             views=["list", "form"],
                                             why="The brief asks for configurable alerts.",
                                             fields=[_f("Name", "char", name="x_name"),
                                                     _f("Trigger", "selection", selection=[
                                                         ["score_below", "Score falls below"],
                                                         ["status_change", "Status changes"],
                                                         ["renewal_near", "Renewal is near"],
                                                         ["critical_ticket", "Critical ticket opened"]]),
                                                     _f("Threshold", "float", name="x_threshold"),
                                                     _f("Notify", "many2many", relation="res.users", name="x_notify_user_ids"),
                                                     _f("Active", "boolean", name="x_active")]))
        done.append("Added Alert Rule so alerts are set up as records, not text.")
    # A section on the customer form extends Contacts with summary fields.
    if re.search(r"(?i)(customer|contact|partner) (form|360)|section to the customer", owner):
        ext = next((e for e in design.stock_extensions if e.model == "res.partner"), None)
        if ext is None:
            ext = StockExtension(model="res.partner", reason="Summary on the customer form.")
            design.stock_extensions.append(ext)
        have = {f.name for f in ext.fields}
        score = "health" if re.search(r"(?i)health score", text) else "score"
        wanted = [_f("Current score", "float", name=f"x_{score}_score",
                     help="Calculated automatically (custom code)."),
                  _f("Previous score", "float", name=f"x_{score}_previous_score"),
                  _f("Status", "selection", name=f"x_{score}_status", selection=next(
                      (f.selection for m in design.new_models for f in m.fields
                       if f.ttype == "selection" and "status" in f.name and f.selection), [])),
                  _f("Renewal date", "date", name="x_renewal_date")]
        if re.search(r"(?i)success manager", text):
            wanted.append(_f("Customer success manager", "many2one", relation="res.users",
                             name="x_success_manager_id"))
        have_m = {(_meaning(f.name), f.ttype) for f in ext.fields} | {(_meaning(f.string), f.ttype) for f in ext.fields}
        added = [f for f in wanted if f.name not in have and (_meaning(f.name), f.ttype) not in have_m]
        ext.fields = added + ext.fields
        if added:
            done.append("Contacts gets the summary fields its form section needs.")
    if computed:
        design.python_needed.append({
            "key": "computed_counts", "label": "Calculated counts", "kind": "computed",
            "models": [], "reason": "Calculated, not typed: " + "; ".join(computed)[:180],
            "requirement_id": "", "evidence": ""})
    done += ensure_jobs(design, owner)
    done += dedupe_fields(design)
    design.notes = list(dict.fromkeys(design.notes + done))
    return done


_SYN = {"csm": "success manager", "salesperson": "user", "owner": "user", "manager": "manager"}
_DROP = {"x", "id", "ids", "next", "current", "the", "of", "customer", "user", "value"}


def _meaning(text: str) -> frozenset[str]:
    t = re.sub(r"[^a-z0-9]+", " ", (text or "").lower().replace("_", " "))
    words: list[str] = []
    for w in t.split():
        words += _SYN.get(w, w).split()
    return frozenset(w for w in words if w not in _DROP)


def dedupe_fields(design: AppDesign) -> list[str]:
    """Same meaning + type + relation on one model -> keep the first, drop the rest."""
    done: list[str] = []
    holders = [(m.label or m.name, m) for m in design.new_models] + [
        (e.model, e) for e in design.stock_extensions]
    for label, h in holders:
        seen: dict[tuple, Any] = {}
        keep: list[DesignField] = []
        for f in h.fields:
            num = f.ttype in {"float", "integer", "monetary"}
            kind = ("number" if num else f.ttype, f.relation or "")
            keys = {(_meaning(f.name), *kind), (_meaning(f.string), *kind)}
            keys = {k for k in keys if k[0]}
            hit = next((seen[k] for k in keys if k in seen), None)
            if hit is not None and f.name != "x_name":
                done.append(f"{label}: dropped '{f.string or f.name}', same as '{hit.string or hit.name}'.")
                continue
            for k in keys:
                seen.setdefault(k, f)
            keep.append(f)
        h.fields = keep
    return done

def ensure_jobs(design: AppDesign, text: str) -> list[str]:
    from app.ai_conversation.brief_checklist import source_brief

    text = source_brief(text)
    """Scheduled jobs the brief names must appear; add missing ones, marked as added by checks."""
    done: list[str] = []
    before = len(design.python_needed)
    keys = ("delivery_lane", "delivery_lane_copy", "artifact_kind", "artifact_kind_copy", "online_blocked", "lane_note")
    src = next((p for p in design.python_needed if p.get("delivery_lane")), None)
    if src is None:
        from app.brief_integrations import python_pieces

        src = (python_pieces("rules engine", "unknown") or [{}])[0]
    lane = {k: src[k] for k in keys if k in src}
    jobs = [lbl for lbl, pat in (("Scheduled score recalculation", r"(?i)recalculat|recompute|frequency|daily|nightly"),
                                 ("Scheduled alert check", r"(?i)\balerts?\b"),
                                 ("Renewal warnings", r"(?i)renewal warning|approaching renewal"))
            if re.search(pat, text)
            # A score job needs a score in the brief: 'daily' or 'every N months' alone is not one.
            and (not lbl.startswith("Scheduled score") or re.search(r"(?i)\bscor(e|es|ing)\b[^.]{0,80}\b(recalculat|recompute|daily|nightly|frequen)|\b(recalculat|recompute)\w*[^.]{0,40}\bscor", text))]
    have_py = {p.get("label", "").lower() for p in design.python_needed}
    for j in jobs:
        if j.startswith("Scheduled score") and any(re.search("recompute|recalc", h) for h in have_py):
            continue
        if j.lower() not in have_py:
            design.python_needed.append({"key": _snake(j)[:40], "label": j, "kind": "cron", "models": [],
                                         "reason": "Named in the brief as something that runs on a schedule.",
                                         "requirement_id": "", "evidence": "", "added_by_checks": True, **lane})
    if re.search(r"(?i)score history|history snapshot|score snapshot", text) and not any(
        re.search(r"(?i)history|snapshot", p.get("label", "")) for p in design.python_needed
    ):
        design.python_needed.append({"key": "history_snapshot", "label": "Scheduled score history snapshot",
                                     "kind": "cron", "models": [],
                                     "reason": "Named in the brief as something that runs on a schedule.",
                                     "requirement_id": "", "evidence": "", "added_by_checks": True, **lane})
    if len(design.python_needed) > before:
        done.append("Added scheduled jobs the brief names: " + ", ".join(
            p["label"] for p in design.python_needed[before:]) + " (by checks).")
    return done


# ---------------------------------------------------------------- brief-driven completeness
_ROLE_RE = re.compile(
    r"\b((?:[A-Z][a-z]+ ){0,3}(?:User|Manager|Administrator|Admin|Supervisor|Officer|Agent|Clerk|Lead|Director))s?\b"
)
_ROLE_WORDS = re.compile(r"(?i)\b(managers?|supervisors?|front desk|receptionists?|technicians?|cleaners?|staff|admins?|bosse?s?)\b")


def brief_roles(text: str) -> list[tuple[str, list[str]]]:
    """Roles the brief names, with 'includes X' nesting. Capitalised names first, then plain words."""
    out: dict[str, list[str]] = {}
    for m in _ROLE_RE.finditer(text or ""):
        name = m.group(1).strip()
        if len(name.split()) == 1 and name in {"User", "Lead", "Agent"}:
            continue
        if name.lower().startswith(("the ", "a ", "each ", "responsible ")):
            continue
        tail = text[m.end(): m.end() + 80]
        inc = re.match(r"\s*\*{0,2}\s*\((?:includes?|inherits?)\s+([^)]+)\)", tail)
        out.setdefault(name, [])
        if inc:
            out[name] += [x.strip(" *") for x in re.split(r",|\band\b", inc.group(1)) if x.strip(" *")]
    if len(out) < 2:
        plain = {"boss": "Manager", "bosses": "Manager", "admin": "Administrator", "admins": "Administrator",
                 "front desk": "Front Desk", "cleaner": "Staff", "cleaners": "Staff", "staff": "Staff",
                 "receptionist": "Front Desk", "receptionists": "Front Desk"}
        seen = {k.lower().rstrip("s") for k in out}
        for m in _ROLE_WORDS.finditer(text or ""):
            w = m.group(1).lower()
            label = plain.get(w) or w.rstrip("s").title()
            if label.lower().rstrip("s") not in seen:
                out.setdefault(label, [])
                seen.add(label.lower().rstrip("s"))
    return list(out.items())


def _role_key(name: str) -> str:
    """'Customer Success Manager' and 'CS Manager' -> 'cs manager'; 'Administrator' -> 'admin'."""
    words = re.sub(r"(?i)administrator", "admin", name or "").lower().split()
    if len(words) >= 3:
        words = ["".join(w[0] for w in words[:-1]), words[-1]]
    return " ".join(words)


def ensure_roles(design: AppDesign, text: str) -> list[str]:
    from app.ai_conversation.app_design import SecurityGroup

    done: list[str] = []
    roles = brief_roles(text)
    named = [n for n, _ in roles if len(n.split()) > 1]
    if named:
        # The brief names its roles: drop generic '<App name> User/Manager' placeholders it never named.
        app = (design.app_name or "").lower()
        keep = []
        for g in design.security_groups:
            generic = app and g.name.lower().startswith(app) and not any(_role_key(n) == _role_key(g.name) for n in named)
            if generic:
                done.append(f"Replaced the placeholder role '{g.name}' with the roles the brief names.")
                continue
            keep.append(g)
        for g in keep:
            g.implied = [x for x in g.implied if any(k.name == x for k in keep)]
        design.security_groups = keep
    have = {_role_key(g.name): g for g in design.security_groups}
    last = {_role_key(g.name).split()[-1] for g in design.security_groups if _role_key(g.name)}
    for name, implied in roles:
        if len(name.split()) == 1 and _role_key(name) in last and _role_key(name) not in have:
            continue  # 'Manager' / 'Administrator' already covered by e.g. 'Rental Operations / Manager'
        if len(name.split()) == 1 and any(_role_key(g.name).endswith(" " + _role_key(name)) for g in design.security_groups):
            continue
        g = have.get(_role_key(name))
        if g is None:
            g = SecurityGroup(name=name[:60])
            design.security_groups.append(g)
            have[_role_key(name)] = g
            done.append(f"Added the '{name}' role the brief names.")
        for x in implied:
            hit = have.get(_role_key(x))
            if hit is not None and hit.name not in g.implied and hit is not g:
                g.implied.append(hit.name)
    # Managers include the matching user role when the brief did not say.
    for g in design.security_groups:
        if re.search(r"(?i)manager", g.name) and not g.implied:
            base = re.sub(r"(?i)\s*manager$", "", g.name).strip()
            user = have.get(_role_key(f"{base} User"))
            if user is not None:
                g.implied.append(user.name)
    return done


_OWN_RE = re.compile(
    r"(?i)(only|just)\s+(see|sees|view)s?\b[^.]{0,60}\b(where they are|assigned to them|their own|they are (the )?responsible)"
    r"|sees? only [^.]{0,60}\b(where they|assigned|their own|responsible)"
    r"|sees? (their )?assigned|(own|assigned) (records|customers|bookings|tickets|complaints)"
)
_CANCEL_RE = re.compile(r"(?i)\b(only )?(managers?|supervisors?)\b[^.]{0,30}\b(can|should be able to|may)\b[^.]{0,20}\bcancel\b|\bcan cancel\b")


def _user_field(m: DesignModel) -> DesignField | None:
    return next((f for f in m.fields if f.ttype == "many2one" and f.relation == "res.users"), None)


def ensure_rules(design: AppDesign, text: str) -> list[str]:
    """Record rules for 'own/assigned' visibility; manager-only cancel; decided here, never asked."""
    done: list[str] = []
    rules: list[dict[str, Any]] = list(getattr(design, "record_rules", []) or [])
    users = [g for g in design.security_groups if re.search(r"(?i)user|staff|agent|desk", g.name)]
    mgrs = [g for g in design.security_groups if re.search(r"(?i)manager|supervisor|admin", g.name)]
    if _OWN_RE.search(text or "") and users:
        for m in design.new_models:
            uf = _user_field(m)
            if uf is None or m.is_config:
                continue
            if any(r.get("model") == m.name and r.get("group") == users[0].name for r in rules):
                continue
            rules.append({"model": m.name, "group": users[0].name, "scope": "own", "field": uf.name,
                          "label": f"{users[0].name} sees only {m.label.lower()} records where they are {uf.string.lower()}"})
            if mgrs:
                rules.append({"model": m.name, "group": mgrs[0].name, "scope": "all", "field": "",
                              "label": f"{mgrs[0].name} sees all {m.label.lower()} records"})
            done.append(f"{users[0].name} only sees {m.label} records assigned to them.")
            break
    if _CANCEL_RE.search(text or "") and mgrs:
        target = next((m for m in design.new_models if any(
            f.ttype == "selection" and any("cancel" in o[0] for o in f.selection) for f in m.fields)), None) or next(
            (m for m in design.new_models if re.search(r"(?i)booking|order|request|ticket|complaint", m.label)), None)
        if target is not None:
            state = next((f for f in target.fields if f.ttype == "selection" and re.search(r"(?i)state|status|stage", f"{f.name} {f.string}")), None)
            if state is None:
                target.fields.append(_f("Status", "selection", name="x_state", selection=[
                    ["draft", "Draft"], ["confirmed", "Confirmed"], ["done", "Done"], ["cancelled", "Cancelled"]]))
            elif not any("cancel" in str(o[0]) for o in state.selection):
                state.selection.append(["cancelled", "Cancelled"])
            rules.append({"model": target.name, "group": mgrs[0].name, "scope": "cancel", "field": "",
                          "label": f"Only {mgrs[0].name} can cancel a {target.label.lower()}"})
            done.append(f"Only {mgrs[0].name} can cancel {target.label} records (cancel button shown to that role only).")
    for m_ in _HIDE_RE.finditer(text or ""):
        who, what = m_.group(1), m_.group(2)
        grp = next((g for g in design.security_groups if _role_key(who).rstrip("s") in _role_key(g.name)), None) or (
            mgrs[0] if mgrs and re.search(r"(?i)manag|boss|admin", who) else None)
        words = {w for w in re.findall(r"[a-z]{4,}", what.lower())} - {"their", "these", "those", "field", "fields"}
        for model in design.new_models:
            for f in model.fields:
                if grp is None or not words or not words & set(re.findall(r"[a-z]{4,}", f.string.lower())):
                    continue
                if any(r.get("scope") == "hide_field" and r.get("field") == f.name and r.get("model") == model.name for r in rules):
                    continue
                rules.append({"model": model.name, "group": grp.name, "scope": "hide_field", "field": f.name,
                              "label": f"Only {grp.name} can see {f.string} on {model.label.lower()} records"})
                done.append(f"Only {grp.name} can see {f.string}.")
    done += _field_group_rules(design, text, rules)
    design.record_rules = rules
    return done


_PRONOUN = {"they", "them", "he", "she", "these", "those"}
_HIDE_NEG_RE = re.compile(r"(?i)\b([a-z][a-z ]{1,30}?) (?:shouldn'?t|should not|must not|mustn'?t|can'?t|cannot|may not|don'?t|do not) (?:be able to )?see (?:the |their |a |an |any )?([a-z ,]{3,60})")
_EDIT_ONLY_RE = re.compile(r"(?i)\bonly (?:the )?([a-z][a-z ]{2,30}?) (?:can |should |may |will )?(?:edit|change|update|enter|fill in) (?:the |their )?([a-z ,]{3,60})")
_GENERIC_W = {"total", "amount", "number", "name", "date", "value", "statu"}  # compared after a trailing "s" is dropped
_STOP_W = {"the", "and", "any", "all", "but", "not", "see", "can", "only", "their", "these", "those", "field", "fields", "records", "record"}


def _who(text: str, m: re.Match[str]) -> str:
    """The role a rule names; a pronoun ('they') means the sentence's subject ('Ushers record ... but they ...')."""
    who = m.group(1).strip()
    last = who.split()[-1].lower() if who.split() else ""
    if last in _PRONOUN:
        start = max(text.rfind(".", 0, m.start()), text.rfind("\n", 0, m.start())) + 1
        first = re.match(r"\s*(?:the |our |all )?([A-Za-z]+)", (text[start:m.start()] + " " + who).strip())
        who = first.group(1) if first else ""
    who = re.sub(r"(?i)^(?:the|our|all|so|and|but)\s+", "", who).strip()
    return who if 2 < len(who) <= 30 and who.split()[-1].lower() not in _PRONOUN else ""


def _role_group(design: AppDesign, who: str) -> Any:
    from app.ai_conversation.app_design import SecurityGroup

    key = _role_key(who).rstrip("s")
    grp = next((g for g in design.security_groups if key and (key in _role_key(g.name) or _role_key(g.name).rstrip("s") in key)), None)
    if grp is None:
        grp = SecurityGroup(name=re.sub(r"s$", "", who.strip().title())[:60])
        design.security_groups.append(grp)
    return grp


def _best_fields(design: AppDesign, what: str) -> list[tuple[Any, Any]]:
    words = {w.rstrip("s") for w in re.findall(r"[a-z]{3,}", what.lower()) if w not in _STOP_W}
    scored = []
    for model in design.new_models:
        for f in model.fields:
            fw = {w.rstrip("s") for w in re.findall(r"[a-z]{3,}", (f.string or "").lower())}
            sc = sum(0.5 if w in _GENERIC_W else 1.0 for w in words & fw)
            if sc >= 1.0:
                scored.append((sc, model, f))
    top = max((x[0] for x in scored), default=0)
    return [(m, f) for sc, m, f in scored if sc == top]


def _field_group_rules(design: AppDesign, text: str, rules: list[dict[str, Any]]) -> list[str]:
    """'Riders shouldn't see the fee' -> hidden from that role; 'only lab staff edit results' ->
    read-only for everyone else. Code decides from the brief's own words; never asked."""
    done: list[str] = []
    for rx, scope in ((_HIDE_NEG_RE, "hide_field"), (_EDIT_ONLY_RE, "edit_field")):
        for m_ in rx.finditer(text or ""):
            who = _who(text, m_)
            if not who:
                continue
            hits = _best_fields(design, m_.group(2))
            if not hits:
                continue
            grp = _role_group(design, who)
            for model, f in hits:
                if any(r.get("scope") in {"hide_field", "edit_field"} and r.get("field") == f.name and r.get("model") == model.name for r in rules):
                    continue
                if scope == "hide_field":
                    rules.append({"model": model.name, "group": grp.name, "scope": "hide_field", "field": f.name, "negate": True,
                                  "label": f"{grp.name} can't see {f.string} on {model.label.lower()} records"})
                    done.append(f"{f.string} is hidden from {grp.name}.")
                else:
                    rules.append({"model": model.name, "group": grp.name, "scope": "edit_field", "field": f.name,
                                  "label": f"Only {grp.name} can edit {f.string}; others see it read-only"})
                    done.append(f"Only {grp.name} can edit {f.string}.")
    return done


_HIDE_RE = re.compile(r"(?i)\bonly ((?:the )?[a-z ]{3,30}?)s? (?:can|should|may) see (?:the |their |a |an )?([a-z ,]{3,60})")


def ensure_company(design: AppDesign, text: str) -> list[str]:
    if not re.search(r"(?i)multi[- ]?compan|several companies|each company|per company|belongs? to one company|subsidiar", text or ""):
        return []
    added = []
    for m in design.new_models:
        if m.is_config or any(f.relation == "res.company" for f in m.fields):
            continue
        m.fields.append(_f("Company", "many2one", relation="res.company", name="x_company_id", required=True,
                           help="Each record belongs to one company; users only see their companies' records."))
        added.append(m.label)
    return [f"Each record belongs to one company: {', '.join(added)}."] if added else []


_VIEW_CUES = (
    ("graph", r"(?i)\b(graph|chart|dashboard|report|trend|how much|which customers|most|per month|by month|kpis?)\b"),
    ("pivot", r"(?i)\b(pivot|dashboard|report|how much|which customers|most|per (customer|month)|by (customer|manager|segment|month))\b"),
    ("calendar", r"(?i)\bcalendar\b|\bwhen (it'?s|its|they'?re) (coming|due) back\b|\bschedule\b"),
    ("kanban", r"(?i)\bkanban|pipeline|stages?\b"),
)


def ensure_views(design: AppDesign, text: str) -> list[str]:
    """Views the brief asks for go on the record the asking sentence names (else the main record)."""
    models = [m for m in design.new_models if not m.is_config]
    if not models:
        return []
    main = max(models, key=lambda m: len(m.fields))
    sentences = [x for x in re.split(r"(?<=[.!?])\s+|\n", text or "") if x.strip()]
    key = lambda m: m.label.split()[-1].lower().rstrip("s")  # noqa: E731
    done = []
    for view, pat in _VIEW_CUES:
        targets: list[DesignModel] = []
        for sent in sentences:
            if not re.search(pat, sent):
                continue
            named = [m for m in models if re.search(rf"(?i)\b{re.escape(key(m))}", sent)]
            targets += named[:1] if view != "calendar" else named[:2]
            if not named and view in {"graph", "pivot"}:
                targets.append(main)
        if view == "kanban":
            targets = [m for m in targets or models if any(
                f.ttype == "selection" and re.search(r"(?i)stage|status|state", f.string or f.name) for f in m.fields)]
        if view == "calendar":
            targets = [m for m in targets if any(f.ttype in {"date", "datetime"} for f in m.fields)]
        for m in {id(t): t for t in targets}.values():
            if view not in m.views:
                m.views.append(view)
                done.append(f"{m.label} gets a {view} view (the brief asks for it).")
    return done


_ALERT_SENT = re.compile(
    r"(?i)\b(remind|alert|notify|warn|warning|let \w+ know|should know|flag|overdue|expir\w*|nobody touched|"
    r"no (activity|update)|schedule (a|an) [\w\"' -]+ activity|activity for)\b"
)


def ensure_alert_jobs(design: AppDesign, text: str) -> list[str]:
    """Every alert the brief names exists as an automation or a scheduled action (never silently dropped)."""
    from app.ai_conversation.intent_contract import _stems

    covered = [_stems(f"{a.get('label', '')} {a.get('mechanism', '')}") for a in design.automations] + [
        _stems(p.get("label", "")) for p in design.python_needed]
    added = []
    for sent in re.split(r"(?<=[.!?])\s+|\n", text or ""):
        sent = sent.strip(" -*#0123456789.")
        if (len(sent) < 12 or len(sent.split()) < 5 or not _ALERT_SENT.search(sent)
                or re.match(r"(?i)(alerts can|include|show|display|asset kanban|booking kanban|[a-z ]+ (kanban|list|calendar|view)s?\b)", sent)):
            continue
        st = _stems(sent)
        if any(len(st & c) >= 2 for c in covered):
            continue
        label = re.sub(r"\s+", " ", sent)[:90].rstrip(",;:")
        design.python_needed.append({
            "key": _snake(label)[:40], "label": label, "kind": "cron", "models": [],
            "reason": "Named in the brief: runs on a schedule or when a record changes.",
            "requirement_id": "", "evidence": "", "added_by_checks": True})
        covered.append(st)
        added.append(label)
    return [f"Added {len(added)} alert(s) the brief names, so none is dropped."] if added else []


_ONLINE_SCHEDULED = re.compile(r"(?i)schedul|cron|daily|nightly|alert|remind|warn|snapshot|history|overdue|expir|recompute|recalc|flag")


def route_scheduled_jobs(design: AppDesign) -> list[str]:
    """Scheduled jobs run on Odoo Online as scheduled actions (server actions with code are allowed
    without a module). Only model-level Python (new compute methods, constraints) needs custom code."""
    moved = []
    for p in design.python_needed:
        if p.get("kind") == "computed" or not (p.get("kind") == "cron" or _ONLINE_SCHEDULED.search(p.get("label", ""))):
            continue
        if re.search(r"(?i)comput|weighted|rules engine|constraint|onchange", p.get("label", "")) and p.get("kind") != "cron":
            continue
        p.update({"kind": "cron", "delivery_lane": "online_scheduled_action", "online_blocked": False,
                  "delivery_lane_copy": "Built here as a scheduled action (allowed on Odoo Online, no module needed).",
                  "lane_note": "Runs in Odoo's safe server-action editor; no custom module."})
        moved.append(p.get("label", ""))
    return [f"{len(moved)} scheduled job(s) are built here as scheduled actions, not custom code."] if moved else []


_RECURRING = re.compile(
    r"(?i)\b(servic\w*|maintenance|maintain\w*|calibrat\w*|inspect\w*)\b[^.]{0,60}\bevery\s+(few|couple of|\d+|other)?\s*"
    r"(days?|weeks?|months?|years?)|\bevery\s+(few|couple of|\d+)?\s*(days?|weeks?|months?)\b[^.]{0,40}\b(servic\w*|maintenance|inspect\w*)")
_RETURN_DAMAGE = re.compile(r"(?i)\b(comes? back|returned?|returns?)\b[^.]{0,30}\b(broken|damaged?|faulty)")


def ensure_brief_duties(design: AppDesign, text: str) -> list[str]:
    """Plain-language duties the brief names but the design missed: recurring servicing becomes a
    maintenance log with a next-due date and a reminder; 'comes back broken' becomes a return check."""
    done: list[str] = []
    main = design.new_models[0] if design.new_models else None
    asset = _find(design, r"equipment|asset|item|machine|vehicle|tool") or main
    if asset is not None and _RECURRING.search(text or "") and not _find(design, r"servic|mainten|calibrat|inspect"):
        log = _child(design, asset, "Maintenance Log",
                     [_f("Service Date", "date", required=True), _f("Next Due Date", "date"),
                      _f("Done By", "many2one", relation="res.users"), _f("Notes", "text")],
                     "The brief says this needs servicing on a regular cycle.", "Maintenance History")
        if log is not None:
            if not _has(asset, r"next.?(service|due)"):
                asset.fields.append(_f("Next Service Date", "date"))
            done.append("Added a maintenance log so regular servicing is recorded.")
            design.python_needed.append({
                "key": "service_due_reminder", "label": "Remind the team when servicing is due",
                "kind": "cron", "models": [asset.name], "reason": "The brief says servicing gets forgotten.",
                "requirement_id": "", "evidence": "", "added_by_checks": True})
    booking = _find(design, r"booking|rental|order|loan|checkout")
    if booking is not None and _RETURN_DAMAGE.search(text or "") and not _has(booking, r"damag|condition|broken") \
            and not _find(design, r"inspect|damag|return"):
        booking.fields += [_f("Return Condition", "selection",
                              selection=[["good", "Good"], ["damaged", "Damaged"], ["missing_parts", "Missing parts"]]),
                           _f("Damage Notes", "text")]
        m = _RETURN_DAMAGE.search(text or "")
        design.automations.append({
            "requirement_id": "", "label": "When equipment comes back damaged, schedule a repair check",
            "trigger": "event", "target_model": booking.name,
            "mechanism": "Automation rule on save when Return Condition is Damaged",
            "automation": {"when": "on_write", "action": "activity", "date_field": "", "offset_days": 0,
                           "summary": "Repair check"},
            "evidence": {"quote": m.group(0), "start": m.start(), "end": m.end()}, "added_by_checks": True})
        done.append("Added a return check so damaged equipment is flagged when it comes back.")
    return done


_OUT_OF_SCOPE = (
    (r"\b(payroll|salar(y|ies) payments?)\b", "Payroll"),
    (r"\b(e-?commerce|online shop|web ?shop|website)\b", "A website or online shop"),
    (r"\b(mobile app|ios app|android app)\b", "A separate phone app (Odoo works in the phone browser)"),
    (r"\b(whatsapp|sms) (integration|messages?|bot)\b", "WhatsApp or SMS messaging"),
    (r"\b(bank feeds?|bank sync|payment gateway|card payments?)\b", "Bank or card payment links"),
    (r"\b(machine learning|ai predict\w*|forecast\w* model)\b", "Prediction models"),
)
MAX_AUTOMATIONS = 8
MAX_JOBS = 6


def scope_and_limits(design: AppDesign, text: str) -> list[str]:
    """Out-of-scope asks are named, not silently built; the app stays simple (caps on automations and jobs)."""
    out = []
    for pat, label in _OUT_OF_SCOPE:
        m = re.search(pat, text or "", re.I)
        if m and not span_negated(text, m.start()) and label not in design.out_of_scope:
            design.out_of_scope.append(label)
    if design.out_of_scope:
        out.append("Not part of this app: " + "; ".join(design.out_of_scope) + ".")
    if len(design.automations) > MAX_AUTOMATIONS:
        extra = design.automations[MAX_AUTOMATIONS:]
        design.automations = design.automations[:MAX_AUTOMATIONS]
        out.append(f"Kept it simple: {len(extra)} more automation(s) left for later (ask in a refine).")
    jobs = [p for p in design.python_needed if p.get("kind") == "cron"]
    if len(jobs) > MAX_JOBS:
        drop = {id(p) for p in jobs[MAX_JOBS:]}
        design.python_needed = [p for p in design.python_needed if id(p) not in drop]
        out.append(f"Kept it simple: {len(drop)} more scheduled job(s) left for later (ask in a refine).")
    return out


def span_negated(text: str, pos: int) -> bool:
    from app.ai_conversation.intent_contract import span_is_negated

    return span_is_negated(text, pos)


def complete_from_brief(design: AppDesign, text: str) -> list[str]:
    from app.ai_conversation.brief_checklist import source_brief

    text = source_brief(text)  # additive repairs: owner's words only, never the AI expansion
    return (ensure_brief_duties(design, text) + ensure_roles(design, text) + ensure_company(design, text)
            + ensure_rules(design, text) + ensure_views(design, text) + ensure_alert_jobs(design, text)
            + route_scheduled_jobs(design))


def authorize_step(design: AppDesign, owner: str) -> list[str]:
    """Record the pre-authorizer design (eval replay) and run the model authorizer.

    INGENIUM_RECORD_DIR=<dir>: write {brief, design} JSON before any repair (record & replay).
    INGENIUM_MODEL_AUTHORIZER=off|shadow|on (default off): shadow logs verdicts only; on applies them.
    """
    import hashlib
    import json
    import logging
    import os
    import time
    from dataclasses import asdict

    rec = os.environ.get("INGENIUM_RECORD_DIR")
    if rec:
        try:
            os.makedirs(rec, exist_ok=True)
            key = hashlib.sha256(owner.encode()).hexdigest()[:12]
            path = os.path.join(rec, f"{key}-{time.time_ns()}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"brief": owner, "design": asdict(design)}, fh, default=str)
        except OSError:
            logging.getLogger(__name__).warning("design recording failed", exc_info=True)
    mode = os.environ.get("INGENIUM_MODEL_AUTHORIZER", "off")
    if mode not in {"shadow", "on"}:
        return []
    from app.ai_conversation.model_authorizer import apply_calls, authorize_models

    from app.ai_conversation.app_design import design_knobs

    result = authorize_models(design, brief=owner, suggested_not_built=design_knobs()["rules"] == "v2")
    shadow = os.environ.get("INGENIUM_SHADOW_LOG")
    if shadow:
        try:
            with open(shadow, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": time.time(), "brief_hash": hashlib.sha256(owner.encode()).hexdigest()[:12],
                                     "mode": mode, "calls": result.to_list()}) + "\n")
        except OSError:
            pass
    from app.ai_conversation.model_authorizer import apply_python_gate, authorize_python, orphan_requirements

    declined = authorize_python(design)
    if shadow:
        try:
            with open(shadow, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": time.time(), "brief_hash": hashlib.sha256(owner.encode()).hexdigest()[:12],
                                     "python_declined": [d["item"] for d in declined],
                                     "orphans": [r.get("id") for r in orphan_requirements(design)]}) + "\n")
        except OSError:
            pass
    if mode != "on":
        return []
    apply_python_gate(design, declined)
    notes = apply_calls(design, result)
    for c, n in zip([c for c in sorted(result.calls, key=lambda c: c.model) if c.verdict in {"fold", "suggest"}], notes):
        design.left_out.append({"id": f"model:{c.model}", "item": c.label, "quote": "", "message": n,
                                "put_back": c.verdict, "status": "folded" if c.verdict == "fold" else "later"})
    return notes

