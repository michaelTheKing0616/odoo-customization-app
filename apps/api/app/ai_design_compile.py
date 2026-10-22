"""Compile a validated step-2A App design into a App plan draft (step 3).

Input: the ``app_design`` dict carried by the locked Diagnosis (already
validated/repaired). Output: a draft the existing preview + Apply executor
(``apply_module_spec_ui``) understand:

* ``models``: every new x_* model (mode new) with fields, selections, relations
  and one2many inverses, plus stock extensions (mode inherit, flagged
  ``stock_extension`` so the app is never treated as a Prefer/inherit job);
* ``groups`` (with ``implied``) and ``access_rules`` per group x model;
* ``actions`` + ``menus`` (root, Configuration, one leaf per model) and basic
  ``views`` (form/list + kanban/graph/pivot when the design asks);
* ``_architecture_plan`` locking every design model, so clipping keeps them;
* ``_option_a_batch``: all Python pieces batched into ONE Custom-code module draft
  (author -> sandbox -> single Promote click). Online: blocked with an honest note.

Deferred integrations (apps not installed) stay out; validate_and_repair already
held their dependent fields back. Side effects: none.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any
from xml.sax.saxutils import quoteattr

_NUMERIC = {"integer", "float", "monetary"}


def _snake(text: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(text or "").lower())).strip("_")


def _plural(label: str) -> str:
    if re.search(r"(?i)[^aeiou]y$", label):
        return label[:-1] + "ies"
    return label if label.lower().endswith("s") else label + "s"


def design_model_names(draft: dict[str, Any] | None) -> set[str]:
    design = (draft or {}).get("_app_design") if isinstance(draft, dict) else None
    if not isinstance(design, dict):
        return set()
    return {str(m.get("name")) for m in design.get("new_models") or [] if isinstance(m, dict) and m.get("name")}


def design_applies(design: Any) -> bool:
    return isinstance(design, dict) and len([m for m in design.get("new_models") or [] if isinstance(m, dict)]) >= 2


def _spec_field(f: dict[str, Any]) -> dict[str, Any]:
    ttype = str(f.get("ttype") or "char")
    row: dict[str, Any] = {
        "name": str(f.get("name")),
        "ttype": ttype,
        "string": str(f.get("string") or f.get("name")),
        "required": bool(f.get("required")),
        "source": "app_design",
    }
    if f.get("help"):
        row["help"] = str(f["help"])
    if ttype == "selection":
        pairs = [p for p in f.get("selection") or [] if isinstance(p, (list, tuple)) and len(p) == 2]
        inner = ", ".join("(%r, %r)" % (str(k), str(v)) for k, v in pairs)
        row["selection"] = f"[{inner}]"
    if ttype in {"many2one", "one2many", "many2many"} and f.get("relation"):
        row["relation"] = str(f["relation"])
        if ttype == "one2many" and f.get("inverse_name"):
            row["relation_field"] = str(f["inverse_name"])
    return row


_CANCEL_KEYS = re.compile(r"(?i)^(cancel\w*|void|abort\w*)$")


def _arch(model: dict[str, Any], vtype: str) -> str | None:
    fields = [f for f in model.get("fields") or [] if isinstance(f, dict) and f.get("name")]
    hidden: dict[str, str] = model.get("_hidden_fields") or {}  # field -> group xml id that may see it
    cancel_group = str(model.get("_cancel_group") or "")
    scalars = [f for f in fields if f.get("ttype") not in {"one2many", "many2many"}]
    lists = [f for f in fields if f.get("ttype") in {"one2many", "many2many"}]
    name = "x_name" if any(f["name"] == "x_name" for f in fields) else (scalars[0]["name"] if scalars else None)
    if not name:
        return None
    def fld(f: dict[str, Any], extra: str = "") -> str:
        grp = hidden.get(str(f["name"]))
        if grp and grp.startswith("edit:"):
            g = grp[5:]  # editable for the role, read-only for everyone else (works on Odoo 17-20)
            return (f'<field name="{f["name"]}"{extra} groups="{g}"/>'
                    f'<field name="{f["name"]}"{extra} readonly="1" groups="!{g}"/>')
        return f'<field name="{f["name"]}"{extra}' + (f' groups="{grp}"' if grp else "") + "/>"

    if vtype == "form":
        header = ""
        state = next((f for f in scalars if f.get("ttype") == "selection"
                      and any(_CANCEL_KEYS.match(str(k[0] if isinstance(k, list) else k)) for k in f.get("selection") or [])), None)
        if cancel_group and state:
            keys = [str(k[0] if isinstance(k, list) else k) for k in state.get("selection") or []]
            visible = ",".join(k for k in keys if not _CANCEL_KEYS.match(k))
            # Everyone moves the record along; only the cancel group sees and can pick the Cancel stage.
            header = (f'<header><field name="{state["name"]}" widget="statusbar" options="{{\'clickable\': \'1\'}}" '
                      f'groups="{cancel_group}"/><field name="{state["name"]}" widget="statusbar" '
                      f'statusbar_visible="{visible}" options="{{\'clickable\': \'1\'}}" groups="!{cancel_group}"/></header>')
            scalars = [f for f in scalars if f is not state]
        left = scalars[: (len(scalars) + 1) // 2]
        right = scalars[(len(scalars) + 1) // 2:]
        pages = "".join(
            f'<page string={quoteattr(str(f.get("string") or f["name"]))}>{fld(f)}</page>' for f in lists
        )
        return (
            "<form>" + header + "<sheet><group>"
            f"<group>{''.join(fld(f) for f in left)}</group>"
            f"<group>{''.join(fld(f) for f in right)}</group>"
            "</group>" + (f"<notebook>{pages}</notebook>" if pages else "") + "</sheet></form>"
        )
    if vtype == "list":
        return "<list>" + "".join(fld(f) for f in scalars[:7] if f.get("ttype") not in {"text", "html", "binary"}) + "</list>"
    if vtype == "kanban":
        state = next((f for f in scalars if f.get("ttype") == "selection"), None)
        extra = f'<div>{fld(state)}</div>' if state else ""
        return (
            (f'<kanban default_group_by="{state["name"]}">' if state else "<kanban>")
            + f'<templates><t t-name="card"><field name="{name}" class="fw-bold"/>{extra}</t></templates></kanban>'
        )
    if vtype in {"graph", "pivot"}:
        measure = next((f for f in scalars if f.get("ttype") in _NUMERIC), None)
        group = next((f for f in scalars if f.get("ttype") in {"many2one", "selection", "date"}), None)
        if not group:
            return None
        row = ' type="row"' if vtype == "pivot" else ""
        measure_attr = ' type="measure"'
        body = fld(group, row) + (fld(measure, measure_attr) if measure else "")  # no measure: counts records
        return f"<{vtype}>{body}</{vtype}>"
    if vtype == "calendar":
        dates = [f for f in scalars if f.get("ttype") in {"date", "datetime"}]
        if not dates:
            return None
        start = next((f for f in dates if re.search(r"start|begin|from|due|next", f["name"])), dates[0])
        stop = next((f for f in dates if f is not start and re.search(r"end|stop|until|to_", f["name"])), None)
        color = next((f for f in scalars if f.get("ttype") == "many2one" and f.get("relation") == "res.partner"), None)
        attrs = f'date_start="{start["name"]}"' + (f' date_stop="{stop["name"]}"' if stop else "")
        attrs += f' color="{color["name"]}"' if color else ""
        return f"<calendar {attrs}>{fld({'name': name})}</calendar>"
    return None


def _record_rules(design: dict[str, Any], gid: dict[str, str], names: set[str] | list[str]) -> list[dict[str, Any]]:
    """Design visibility rules -> ir.rule rows. 'cancel' restrictions are shown on the diagnosis and
    applied as a group-only cancel button, not as a record rule."""
    out = []
    for r in design.get("record_rules") or []:
        if not isinstance(r, dict) or r.get("model") not in names or r.get("group") not in gid:
            continue
        if r.get("scope") == "own" and r.get("field"):
            domain = f"[('{r['field']}', '=', user.id)]"
        elif r.get("scope") == "all":
            domain = "[(1, '=', 1)]"
        else:
            continue
        out.append({"name": str(r.get("label") or "Rule")[:120], "model": r["model"],
                    "model_xml_id": f"model_{r['model'].replace('.', '_')}",
                    "group_xml_ids": [gid[r["group"]]], "domain_force": domain})
    return out


def _option_a_batch(design: dict[str, Any], tech: str, app: str, models: list[str]) -> dict[str, Any] | None:
    # Scheduled actions run on Odoo Online without a module; only module-level Python is batched.
    pieces = [p for p in design.get("python_needed") or [] if isinstance(p, dict) and p.get("label")
              and p.get("delivery_lane") != "online_scheduled_action"]
    if not pieces:
        return None
    blocked = any(str(p.get("online_blocked")) == "true" for p in pieces)
    lane_note = next((str(p.get("lane_note")) for p in pieces if p.get("lane_note")), "")
    lines = []
    for i, p in enumerate(pieces, 1):
        on = ", ".join(p.get("models") or []) or "the app models"
        lines.append(f"{i}. {p['label']} (on {on})" + (f": {p['reason']}" if p.get("reason") else ""))
    prompt = (
        f"Custom-code module for the {app} app. Implement these Python pieces as one installable module "
        f"on the existing custom models {', '.join(models)}:\n" + "\n".join(lines)
    )
    tech_logic = f"{tech[:58]}_logic"
    companion = {
        "technical_name": tech_logic,
        "display_name": f"{app} logic",
        "depends": ["base", "mail"],
        "models": [],
        "grain": "full_app",
        "_user_prompt": prompt,
        "_parent_app": tech,
        "_option_a_pieces": pieces,
        "_generation_engine": {
            "capability": "option_a_authored",
            "grain": "full_app",
            "promote_human": True,
            "delivery_lane": "module_sh_or_self",
        },
    }
    return {
        "technical_name": tech_logic,
        "pieces": pieces,
        "piece_keys": [str(p.get("key") or "") for p in pieces],
        "delivery_lane": "module_sh_or_self",
        "online_blocked": blocked,
        "status": "blocked_online" if blocked else "ready_to_author",
        "note": lane_note,
        # One module for every piece: author -> sandbox prove -> ONE Promote click.
        "promote": {"mode": "single_button", "label": "Promote", "config_required": False},
        "draft": companion,
    }


def _user_fields(target: str, models: list[dict[str, Any]]) -> list[str]:
    """many2one -> res.users fields on ``target``: design fields first, then the live snapshot."""
    out: list[str] = []
    for spec_m in models:
        if spec_m.get("model") != target:
            continue
        for f in spec_m.get("fields") or []:
            if isinstance(f, dict) and f.get("ttype") == "many2one" and f.get("relation") == "res.users":
                out.append(str(f.get("name")))
    try:
        from app.odoo_snapshot import current_snapshot

        snap = current_snapshot()
    except Exception:  # noqa: BLE001 - no snapshot just means design fields only
        snap = None
    info = (getattr(snap, "models", {}) or {}).get(target) if snap is not None else None
    for name, fi in (getattr(info, "fields", {}) or {}).items():
        # create_uid / write_uid are Odoo's audit columns, not the person responsible
        if (fi.type == "many2one" and fi.relation == "res.users" and getattr(fi, "stored", True)
                and name not in {"create_uid", "write_uid"}):
            out.append(str(name))
    return list(dict.fromkeys(n for n in out if n))


def pick_user_field(users: list[tuple[str, str]], wording: str) -> str:
    """The responsible-user field whose label the brief names; the first one otherwise."""
    return rank_user_field(users, wording)[0]


def rank_user_field(users: list[tuple[str, str]], wording: str) -> tuple[str, bool]:
    """(field, named): ``named`` is False when the brief's words match no user field's label."""
    words = set(re.findall(r"[a-z0-9]{3,}", (wording or "").lower()))
    scored = [(len(words & set(re.findall(r"[a-z0-9]{3,}", f"{n} {l}".lower()))), i, n)
              for i, (n, l) in enumerate(users)]
    best = sorted(scored, key=lambda t: (-t[0], t[1]))
    return (best[0][2], best[0][0] > 0) if best else ("", False)


def compile_design_draft(design: dict[str, Any], *, prompt: str = "", title: str = "") -> dict[str, Any]:
    app = str(design.get("app_name") or title or "Custom App")[:80]
    tech = _snake(app)[:64] or "custom_app"
    new_models = [m for m in design.get("new_models") or [] if isinstance(m, dict) and m.get("name")]
    names = [str(m["name"]) for m in new_models]
    models: list[dict[str, Any]] = []
    for m in new_models:
        models.append(
            {
                "model": m["name"],
                "name": m.get("label") or m["name"],
                "description": m.get("label") or m["name"],
                "mode": "new",
                "fields": [_spec_field(f) for f in m.get("fields") or [] if isinstance(f, dict) and f.get("name")],
                "_why": m.get("why") or "",
                "_is_config": bool(m.get("is_config")),
                **({"suggested": True, "source": "ai_suggested"} if m.get("suggested") else {}),
            }
        )
    for e in design.get("stock_extensions") or []:
        if not isinstance(e, dict) or not e.get("model"):
            continue
        models.append(
            {
                "model": e["model"],
                "description": e.get("reason") or e["model"],
                "mode": "inherit",
                "inherit": e["model"],
                "stock_extension": True,
                "fields": [_spec_field(f) for f in e.get("fields") or [] if isinstance(f, dict) and f.get("name")],
            }
        )

    gid = {str(g.get("name")): f"group_{tech[:24]}_{_snake(g.get('name'))}" for g in design.get("security_groups") or [] if isinstance(g, dict) and g.get("name")}
    groups, access = [], []
    for g in design.get("security_groups") or []:
        if not isinstance(g, dict) or str(g.get("name")) not in gid:
            continue
        ref = gid[str(g["name"])]
        groups.append({"id": ref, "name": str(g["name"]), "implied": [gid[x] for x in g.get("implied") or [] if x in gid]})
        for model, perms in (g.get("access") or {}).items():
            if model not in names:
                continue
            perms = str(perms)
            access.append(
                {
                    "model": model,
                    "name": f"access_{model}_{ref}"[:120],
                    "group": ref,
                    "perm_read": "r" in perms,
                    "perm_write": "w" in perms,
                    "perm_create": "c" in perms,
                    "perm_unlink": "d" in perms,
                }
            )

    views, actions, menus = [], [], []
    root = f"menu_{tech}_root"
    if new_models:  # extension-only designs live on the stock app's own menus
        menus.append({"xml_id": root, "name": app, "sequence": 10})
    if any(m.get("is_config") for m in new_models):
        menus.append({"xml_id": f"menu_{tech}_config", "name": "Configuration", "parent_xml_id": root, "sequence": 90})
    hidden: dict[str, dict[str, str]] = {}
    cancel_by: dict[str, str] = {}
    for r in design.get("record_rules") or []:
        if not isinstance(r, dict) or r.get("model") not in names or r.get("group") not in gid:
            continue
        if r.get("scope") == "hide_field" and r.get("field"):
            hidden.setdefault(r["model"], {})[str(r["field"])] = ("!" if r.get("negate") else "") + gid[r["group"]]
        elif r.get("scope") == "edit_field" and r.get("field"):
            hidden.setdefault(r["model"], {})[str(r["field"])] = "edit:" + gid[r["group"]]
        elif r.get("scope") == "cancel":
            cancel_by[r["model"]] = gid[r["group"]]
    for seq, (m, spec_m) in enumerate(zip(new_models, models), start=1):
        view_m = {**spec_m, "_hidden_fields": hidden.get(m["name"], {}), "_cancel_group": cancel_by.get(m["name"], "")}
        vtypes = [v for v in m.get("views") or ["list", "form"] if v in {"form", "list", "kanban", "graph", "pivot", "calendar"}]
        for v in ("list", "form"):
            if v not in vtypes:
                vtypes.append(v)
        made = []
        for v in vtypes:
            arch = _arch(view_m, v)
            if arch:
                views.append({"model": m["name"], "type": v, "name": f"{m['name']}.{v}", "arch": arch})
                made.append(v)
        mode = ",".join(["list", "form"] + [v for v in made if v not in {"list", "form"}])
        action = f"action_{m['name']}"
        label = _plural(str(m.get("label") or m["name"]))
        actions.append({"xml_id": action, "technical_name": action, "name": label, "res_model": m["name"], "view_mode": mode})
        menus.append(
            {
                "xml_id": f"menu_{m['name']}",
                "name": label,
                "parent_xml_id": f"menu_{tech}_config" if m.get("is_config") else root,
                "action_xml_id": action,
                "sequence": seq * 10,
            }
        )

    automations: list[dict[str, Any]] = []
    auto_notes: list[str] = []
    for a in design.get("automations") or []:
        if not isinstance(a, dict):
            continue
        spec = a.get("automation") or {}
        target = str(a.get("target_model") or "")
        when = str(spec.get("when") or "")
        label = str(a.get("label") or "Automation")[:80]
        action = str(spec.get("action") or "")
        if not target or when not in {"on_time", "on_create", "on_write", "untouched"} or action not in {"activity", "notify", "set_fields"}:
            auto_notes.append(
                f"Left out the automation '{label}': App Studio can create to-dos, notices and "
                "field updates when a record is created or changed, around a date, or when it sits untouched."
            )
            continue
        known = {str(f.get("name")): f for sm in models if sm.get("model") == target
                 for f in sm.get("fields") or [] if isinstance(f, dict)}
        is_new = any(sm.get("model") == target and sm.get("mode") == "new" for sm in models)
        bad = [t[0] for t in spec.get("condition") or [] if is_new and t[0] not in known and t[0] not in {"write_date", "create_date"}]
        bad += [k for k in (spec.get("values") or {}) if is_new and k not in known]
        if bad:
            auto_notes.append(f"Left out the automation '{label}': it uses fields this app does not have ({', '.join(bad[:3])}).")
            continue
        bad_vals = [k for k, v in (spec.get("values") or {}).items() if known.get(k, {}).get("ttype") == "selection"
                    and str(v) not in {str(x[0] if isinstance(x, list) else x) for x in known[k].get("selection") or []}]
        if bad_vals:
            auto_notes.append(f"Left out the automation '{label}': it sets a choice that does not exist ({bad_vals[0]}).")
            continue
        if action == "set_fields":
            safe = [{"kind": "object_write", "field": k, "value": v} for k, v in spec["values"].items()]
            row = {"name": label, "model": target, "trigger": "on_time" if when == "untouched" else when,
                   "filter_domain": repr(spec.get("condition") or []),
                   "description": f"From the brief: {str((a.get('evidence') or {}).get('quote') or '')[:160]}",
                   "source": "app_design", "safe_actions": safe}
            if when == "untouched":
                row.update(trg_date_field_name="write_date", trg_date_range=int(spec.get("offset_days") or 0),
                           trg_date_range_type="day", trg_date_range_mode="after")
            automations.append(row)
            continue
        if action == "notify" and spec.get("group"):
            # Everyone in the role gets a to-do; members are looked up when the app is installed.
            automations.append({
                "name": label, "model": target, "trigger": "on_time" if when == "untouched" else when,
                "filter_domain": repr(spec.get("condition") or []),
                "description": f"From the brief: {str((a.get('evidence') or {}).get('quote') or '')[:160]}",
                "source": "app_design",
                "safe_actions": [{"kind": "notify_group", "group": spec["group"],
                                  "summary": str(spec.get("summary") or label)[:120],
                                  "activity_type_xml_id": "mail.mail_activity_data_todo"}],
                **({"trg_date_field_name": "write_date", "trg_date_range": int(spec.get("offset_days") or 0),
                    "trg_date_range_type": "day", "trg_date_range_mode": "after"} if when == "untouched" else {}),
            })
            for spec_m in models:
                if spec_m.get("model") == target and spec_m.get("mode") == "new":
                    spec_m["mixins"] = ["mail.thread", "mail.activity.mixin"]
            continue
        users = _user_fields(target, models)
        wanted = str(spec.get("user_field") or "")
        # A user field pinned at design time was checked against the live database then; the build
        # job has no snapshot, so it is trusted unless the fields known here say otherwise.
        pinned_ok = wanted in users or (bool(wanted) and not is_new and not users)
        user_field = wanted if pinned_ok else (users[0] if users else "")
        if not user_field:
            auto_notes.append(
                f"Left out the automation '{label}': {target} has no responsible-user field "
                "to assign the to-do to. Add a user field (for example Owner) and refine."
            )
            continue
        row: dict[str, Any] = {
            # Stable id from the requirement, so re-applying finds the same automation.
            "external_id": f"ingenium_req_{a['requirement_id']}" if a.get("requirement_id") else "",
            "name": str(a.get("label") or "Automation")[:80],
            "model": target,
            "trigger": "on_time" if when == "untouched" else when,
            "filter_domain": repr(spec.get("condition") or []),
            "description": f"From the brief: {str((a.get('evidence') or {}).get('quote') or '')[:160]}",
            "source": "app_design",
            "safe_actions": [
                {
                    "kind": "next_activity",
                    "summary": str(spec.get("summary") or a.get("label") or "Follow up")[:120],
                    "activity_type_xml_id": "mail.mail_activity_data_todo",
                    "user_type": "generic",
                    "user_field_name": user_field,
                }
            ],
        }
        if when == "untouched":
            # Nobody touched the record for N days: count from its last change.
            row.update(trg_date_field_name="write_date", trg_date_range=int(spec.get("offset_days") or 0),
                       trg_date_range_type="day", trg_date_range_mode="after")
        elif when == "on_time":
            date_field = str(spec.get("date_field") or "")
            if not date_field:
                auto_notes.append(
                    f"Left out the automation '{label}': it has no date field to count from."
                )
                continue
            offset = int(spec.get("offset_days") or 0)
            row.update(
                trg_date_field_name=date_field,
                trg_date_range=abs(offset),
                trg_date_range_type="day",
                trg_date_range_mode="before" if offset < 0 else "after",
            )
        automations.append(row)
        for spec_m in models:
            if spec_m.get("model") == target and spec_m.get("mode") == "new":
                spec_m["mixins"] = ["mail.thread", "mail.activity.mixin"]

    deferred = [i for i in design.get("integrations") or [] if isinstance(i, dict) and i.get("status") == "deferred"]
    depends = ["base", "mail", "contacts"] + [
        str(i.get("module")) for i in design.get("integrations") or []
        if isinstance(i, dict) and i.get("status") == "available" and i.get("module")
    ]
    draft: dict[str, Any] = {
        "technical_name": tech,
        "display_name": app,
        "summary": str(design.get("purpose") or "")[:300],
        "depends": list(dict.fromkeys(depends)),
        "grain": "full_app",
        "document_shape": "workspace",
        "_document_shape": "workspace",
        "models": models,
        "groups": groups,
        "access_rules": access,
        "actions": actions,
        "menus": menus,
        "views": views,
        "automations": automations,
        "record_rules": _record_rules(design, gid, names),
        "_user_prompt": prompt,
        "_pipeline": "app_design",
        "_app_design": design,
        "_architecture_plan": {
            "strategy": "app_design",
            "document_shape": "workspace",
            "new_x_models": names,
            "surface_budget": {"new_models": len(names)},
            "ambiguities": [],
        },
        "_deferred_integrations": [
            {"app": i.get("app"), "module": i.get("module"), "models": i.get("models"), "note": i.get("note")}
            for i in deferred
        ],
        "_design_notes": [str(i.get("note")) for i in deferred if i.get("note")] + list(design.get("notes") or []) + auto_notes,
    }
    batch = _option_a_batch(design, tech, app, names)
    if batch:
        draft["_option_a_batch"] = batch
    return draft


__all__ = ["compile_design_draft", "design_applies", "design_model_names"]


def attach_suggested_models(draft: dict[str, Any], prompt: str, *, locked: dict[str, Any] | None = None) -> list[str]:
    """AI-off finish: suggested supporting models for one named residual record.

    Deterministic (brief must imply lines/parties/documents). Each model is admitted
    as ``suggested`` (allowed-but-flagged), never as brief-named Must-do.
    """
    import os

    from app.ai_conversation.app_design import DesignModel, deterministic_support
    from app.ai_document_shape import _named_residual

    if os.environ.get("STUDIO_SUGGEST_MODELS", "on").strip().lower() in {"0", "off", "false", "no"}:
        return []
    if isinstance(locked, dict) and (
        locked.get("app_design") or locked.get("inherit_existing") or locked.get("needs_module")
        or str(locked.get("capability") or "residual_app") != "residual_app"
    ):
        return []
    engine = draft.get("_generation_engine") if isinstance(draft.get("_generation_engine"), dict) else {}
    if draft.get("domain_pack") or draft.get("_app_design") or str(draft.get("grain") or "full_app") != "full_app":
        return []
    if str(engine.get("capability") or "residual_app") != "residual_app":
        return []
    news = [
        m for m in draft.get("models") or []
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_") and str(m.get("mode") or "new") == "new"
    ]
    if len(news) != 1 or any(m.get("mode") == "inherit" for m in draft.get("models") or [] if isinstance(m, dict)):
        return []
    kind, residual = _named_residual(prompt)
    if kind != "named" or not residual:
        return []
    main_row = news[0]
    main = DesignModel(name=str(main_row["model"]), label=str(main_row.get("description") or ""))
    support = deterministic_support(prompt, main)
    if not support:
        return []
    from app.ai_generate_ir import Proposal, admit_and_apply

    proposals = [
        Proposal(
            kind="model",
            name=sm.name,
            payload={
                "description": sm.label,
                "mode": "new",
                "source": "ai_suggested",
                "suggested": True,
                "fields": [_spec_field(asdict(f)) for f in sm.fields],
            },
            source_cue="suggested_support",
            rationale=sm.why,
            proposer="ai_design.suggest",
            confidence=0.6,
        )
        for sm in support
    ]
    _, notes = admit_and_apply(draft, proposals)
    by_id = {str(m.get("model")): m for m in draft.get("models") or [] if isinstance(m, dict)}
    added: list[str] = []
    for sm in support:
        row = by_id.get(sm.name)
        if row is None:
            continue
        row.update({"suggested": True, "source": "ai_suggested", "_why": sm.why})
        link = next(f for f in sm.fields if f.ttype == "many2one" and f.relation == main.name)
        fields = main_row.setdefault("fields", [])
        o2m = f"x_{sm.name.rsplit('_', 1)[-1]}_ids"
        if not any(isinstance(f, dict) and f.get("name") == o2m for f in fields):
            fields.append({"name": o2m, "ttype": "one2many", "string": sm.label + "s",
                           "relation": sm.name, "relation_field": link.name})
        added.append(sm.name)
    if added:
        draft["_suggested_models"] = added
        notes.append(f"suggested supporting models (remove any you don't need): {', '.join(added)}")
    return notes
