"""Compile LLM/pack drafts onto a senior Community document grammar.

LLM proposes. This module authors the models, fields, menus, and form surface
the operator will see in Odoo. Domain-agnostic — packs declare shape; slots
come from the original brief, not clarify jargon.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from app.ai_document_shape import (
    _PLACEHOLDER_TITLE_RE,
    document_shape_of,
    may_add_line_satellite,
    naming_from_residual,
    stamp_document_shape,
)
from app.ai_surface_invariants import (
    extract_brief_slots,
    findings_as_contract,
    is_ir_jargon_title,
    title_is_grounded,
)

_CONTACT_ASK_RE = re.compile(r"(?i)\b(contact|customer|partner|vendor|client)\b")
_COMPANY_ASK_RE = re.compile(r"(?i)\b(compan(?:y|ies)|multi[\s-]?compan)")
_LINE_MODEL_RE = re.compile(r"(?:_line|_lines)$")

_PLACEHOLDER_TECH = frozenset(
    {
        "named_in_brief",
        "custom_app",
        "untitled",
        "new_app",
        "named_briefs",
        "capability_path",
        "named_brief",
    }
)
_SPRAY_PARTNER = frozenset({"x_partner_id", "x_contact_id", "x_customer_id", "x_client_id"})
_SPRAY_COMPANY = frozenset({"x_company_id", "company_id"})
_SPRAY_EMPLOYEE = frozenset({"x_employee_id", "x_staff_id"})


def _prompt_text(draft: dict[str, Any], prompt: str) -> str:
    raw = prompt or str(draft.get("_user_prompt") or "")
    try:
        from app.ai_operator_brief import intent_corpus

        return intent_corpus(raw) or raw
    except Exception:  # noqa: BLE001
        return raw


def _custom_models(draft: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if mid.startswith("x_") and str(model.get("mode") or "new") != "inherit":
            out.append(model)
    return out


def _field_list(model: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in (model.get("fields") or []) if isinstance(f, dict) and f.get("name")]


def _field_names(model: dict[str, Any]) -> set[str]:
    return {str(f.get("name") or "") for f in _field_list(model)}


def _is_line_model(mid: str) -> bool:
    return bool(_LINE_MODEL_RE.search(str(mid or ""))) or str(mid or "").endswith("_party")


def _pack_header_id(draft: dict[str, Any]) -> str:
    existing = {str(m.get("model") or "") for m in _custom_models(draft)}
    for mid in draft.get("_pack_model_ids") or []:
        sid = str(mid or "")
        if sid in existing and sid.startswith("x_") and not _is_line_model(sid):
            return sid
    pack_id = str(draft.get("domain_pack") or "")
    if pack_id:
        try:
            from app.ai_domain_packs import load_domain_pack

            pack = load_domain_pack(pack_id) or {}
            for model in pack.get("models") or []:
                if not isinstance(model, dict):
                    continue
                mid = str(model.get("model") or "")
                if mid in existing and mid.startswith("x_") and not _is_line_model(mid):
                    return mid
        except Exception:  # noqa: BLE001
            pass
    return ""


def _pick_header_model(draft: dict[str, Any], prompt: str) -> dict[str, Any] | None:
    models = _custom_models(draft)
    if not models:
        return None
    # Residual noun wins over pack header (x_visitor_log over x_restaurant).
    _display, slug = naming_from_residual(prompt)
    want = f"x_{slug}" if slug and not slug.startswith("x_") else slug
    if want:
        hit = next((m for m in models if str(m.get("model")) == want), None)
        if hit:
            return hit
    pack_header = _pack_header_id(draft)
    pack_id = str(draft.get("domain_pack") or "")
    pack_display = ""
    if pack_id:
        try:
            from app.ai_domain_packs import load_domain_pack

            pack_display = str(load_domain_pack(pack_id).get("display_name") or "")
        except Exception:  # noqa: BLE001
            pack_display = ""
    residual_diverges = bool(
        _display and pack_display and _display.lower() not in pack_display.lower()
        and pack_display.lower() not in _display.lower()
    )
    if pack_header and not residual_diverges:
        hit = next((m for m in models if str(m.get("model")) == pack_header), None)
        if hit:
            return hit
    headers = [m for m in models if not _is_line_model(str(m.get("model") or ""))]
    pool = headers or models
    text = (prompt or "").lower()

    def _score(model: dict[str, Any]) -> tuple[int, int]:
        mid = str(model.get("model") or "").replace("x_", "").replace("_", " ")
        desc = str(model.get("description") or "").lower()
        tokens = [t for t in (mid.split() + desc.split()) if len(t) > 3]
        hit = 1 if any(t in text for t in tokens) else 0
        return (hit, len(_field_list(model)))

    return max(pool, key=_score)


def _purge(draft: dict[str, Any], removed: set[str]) -> None:
    if not removed:
        return
    from app.ai_domain_packs import _purge_draft_artifacts_for_models

    try:
        from app.ai_odoo_app_bar import _retarget_removed_relations

        _retarget_removed_relations(draft, removed)
    except Exception:  # noqa: BLE001
        pass
    _purge_draft_artifacts_for_models(draft, removed)


def _model_signature(model: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    mid = str(model.get("model") or "")
    for field in _field_list(model):
        name = str(field.get("name") or "")
        if name == "x_name":
            continue
        ttype = str(field.get("ttype") or "char")
        rel = str(field.get("relation") or "")
        if ttype == "many2one" and rel == mid:
            continue
        if ttype in {"one2many", "many2many"}:
            continue
        rows.append((ttype, rel or name))
    return tuple(sorted(rows))


def _o2m_column_signature(
    field: dict[str, Any], models_by_id: dict[str, dict[str, Any]]
) -> tuple[str, ...]:
    child = models_by_id.get(str(field.get("relation") or ""))
    if not child:
        return ("x_name",)
    names = []
    for f in _field_list(child):
        n = str(f.get("name") or "")
        ttype = str(f.get("ttype") or "")
        if ttype == "many2one" and str(f.get("relation") or "").startswith("x_"):
            continue
        names.append(n)
    return tuple(sorted(names)[:8]) or ("x_name",)


def _ensure_field(model: dict[str, Any], spec: dict[str, Any]) -> bool:
    names = _field_names(model)
    fname = str(spec.get("name") or "")
    if not fname or fname in names:
        existing = next((f for f in _field_list(model) if f.get("name") == fname), None)
        if existing and spec.get("relation") and existing.get("relation") != spec.get("relation"):
            existing["relation"] = spec["relation"]
            if spec.get("string"):
                existing["string"] = spec["string"]
            if spec.get("required"):
                existing["required"] = True
            return True
        if existing and spec.get("required") and not existing.get("required"):
            existing["required"] = True
            return True
        if existing and spec.get("ttype") == "monetary" and existing.get("ttype") != "monetary":
            existing["ttype"] = "monetary"
            if spec.get("currency_field"):
                existing["currency_field"] = spec["currency_field"]
            return True
        return False
    model.setdefault("fields", []).append(copy.deepcopy(spec))
    return True


def _drop_named_fields(model: dict[str, Any], drop: set[str]) -> int:
    if not drop:
        return 0
    before = _field_list(model)
    model["fields"] = [f for f in before if str(f.get("name") or "") not in drop]
    return len(before) - len(_field_list(model))


def _restore_naming(draft: dict[str, Any], prompt: str) -> list[str]:
    notes: list[str] = []
    display, slug = naming_from_residual(prompt)
    current = str(draft.get("display_name") or "").strip()
    tech = str(draft.get("technical_name") or "").strip()
    pack_display = ""
    pack_id = str(draft.get("domain_pack") or "")
    if pack_id:
        try:
            from app.ai_domain_packs import load_domain_pack

            pack_display = str(load_domain_pack(pack_id).get("display_name") or "")
        except Exception:  # noqa: BLE001
            pack_display = ""
    field_type_title = False
    try:
        from app.ai_residual_identity import is_field_type_display_name

        field_type_title = is_field_type_display_name(current)
    except Exception:  # noqa: BLE001
        field_type_title = False
    ungrounded = bool(current) and (
        is_ir_jargon_title(current)
        or field_type_title
        or not title_is_grounded(current, prompt, pack_display_name=pack_display)
    )
    # Pack title stamped under a divergent residual noun is not grounded.
    pack_diverges = bool(
        display
        and pack_display
        and display.lower() not in pack_display.lower()
        and pack_display.lower() not in display.lower()
        and current
        and current.lower() == pack_display.lower()
    )
    if display and (
        not current
        or ungrounded
        or pack_diverges
        or _PLACEHOLDER_TITLE_RE.match(current)
        or current.lower() in {"named briefs", "named brief"}
    ):
        draft["display_name"] = display
        notes.append(f"compiler: display_name → {display}")
    if slug and (not tech or tech in _PLACEHOLDER_TECH or ungrounded):
        draft["technical_name"] = slug
        notes.append(f"compiler: technical_name → {slug}")
    return notes


def _slot_fill(draft: dict[str, Any], header: dict[str, Any], prompt: str) -> list[str]:
    notes: list[str] = []
    text = _prompt_text(draft, prompt)
    slots = extract_brief_slots(text)
    names = _field_names(header)
    mid = str(header.get("model") or "")

    if slots.wants_money:
        if "x_currency_id" not in names:
            _ensure_field(
                header,
                {
                    "name": "x_currency_id",
                    "ttype": "many2one",
                    "string": "Currency",
                    "relation": "res.currency",
                    "required": True,
                },
            )
            notes.append("compiler: slotted currency")
        amount = next(
            (
                f
                for f in _field_list(header)
                if str(f.get("name") or "") in {"x_amount", "x_amount_total", "x_total"}
                or str(f.get("ttype") or "") == "monetary"
            ),
            None,
        )
        if amount is None:
            # Currency must precede monetary for live apply.
            fields = _field_list(header)
            cur_i = next(
                (i for i, f in enumerate(fields) if f.get("name") == "x_currency_id"),
                len(fields),
            )
            row = {
                "name": "x_amount",
                "ttype": "monetary",
                "string": "Amount",
                "required": True,
                "currency_field": "x_currency_id",
                "widget": "monetary",
            }
            fields.insert(cur_i + 1, row)
            header["fields"] = fields
            notes.append("compiler: slotted amount")
        else:
            amount["ttype"] = "monetary"
            amount["currency_field"] = "x_currency_id"
            amount["required"] = True
            fields = _field_list(header)
            names_order = [str(f.get("name") or "") for f in fields]
            amt_name = str(amount.get("name") or "x_amount")
            if "x_currency_id" in names_order and amt_name in names_order:
                ci, ai = names_order.index("x_currency_id"), names_order.index(amt_name)
                if ai <= ci:
                    cur = fields.pop(ci)
                    ai = [str(f.get("name") or "") for f in fields].index(amt_name)
                    fields.insert(ai, cur)
                    header["fields"] = fields

    for person in slots.people:
        if _ensure_field(
            header,
            {
                "name": person.field_name,
                "ttype": "many2one",
                "string": person.string,
                "relation": person.relation,
                "required": True,
            },
        ):
            notes.append(f"compiler: slotted {person.lemma} → {person.relation}")
    if slots.wants_approval and not any(
        str(f.get("relation")) == "res.users" for f in _field_list(header)
    ):
        if _ensure_field(
            header,
            {
                "name": "x_manager_id",
                "ttype": "many2one",
                "string": "Manager",
                "relation": "res.users",
                "required": True,
            },
        ):
            notes.append("compiler: slotted approval assignee → res.users")

    drop: set[str] = set()
    asked_rels = {p.relation for p in slots.people}
    if "res.partner" not in asked_rels and not _CONTACT_ASK_RE.search(text):
        drop |= _SPRAY_PARTNER & _field_names(header)
    if "res.company" not in asked_rels and not _COMPANY_ASK_RE.search(text):
        drop |= _SPRAY_COMPANY & _field_names(header)
    if "hr.employee" in asked_rels:
        drop |= _SPRAY_EMPLOYEE & _field_names(header)
    elif not re.search(r"(?i)\b(employee|staff)\b", text):
        drop |= _SPRAY_EMPLOYEE & _field_names(header)
    if drop:
        _drop_named_fields(header, drop)
        notes.append("compiler: dropped unasked identity spray " + ", ".join(sorted(drop)))

    depends = [str(d) for d in (draft.get("depends") or []) if d]
    if any(str(f.get("relation")) == "hr.employee" for f in _field_list(header)):
        if "hr" not in depends:
            depends.append("hr")
    if any(str(f.get("relation")) == "res.partner" for f in _field_list(header)):
        if "contacts" not in depends:
            depends.append("contacts")
    if "mail" not in depends:
        depends.append("mail")
    draft["depends"] = list(dict.fromkeys(depends or ["base"]))
    _ = mid
    return notes


def _drop_unmentioned_o2ms(header: dict[str, Any], prompt: str) -> list[str]:
    notes: list[str] = []
    keep_lines = may_add_line_satellite({"_document_shape": "transactional_header"}, prompt=prompt)
    drop: set[str] = set()
    for field in _field_list(header):
        ttype = str(field.get("ttype") or "")
        if ttype not in {"one2many", "many2many"}:
            continue
        if keep_lines and _is_line_model(str(field.get("relation") or "")):
            continue
        drop.add(str(field.get("name") or ""))
    if drop:
        _drop_named_fields(header, drop)
        notes.append("compiler: dropped unmentioned O2M " + ", ".join(sorted(drop)))
    return notes


def _compile_thin(
    draft: dict[str, Any], prompt: str, shape: str
) -> list[str]:
    notes: list[str] = []
    header = _pick_header_model(draft, prompt)
    if header is None:
        return notes
    _display, slug = naming_from_residual(prompt)
    pack_header = _pack_header_id(draft)
    want_id = pack_header or (
        f"x_{slug}" if slug and not str(slug).startswith("x_") else slug
    )
    old_id = str(header.get("model") or "")
    if want_id and old_id != want_id:
        header["model"] = want_id
        if _display and not str(header.get("description") or "").strip():
            header["description"] = _display.rstrip("s")
        notes.append(f"compiler: renamed header {old_id} → {want_id}")
    header_id = str(header.get("model") or "")
    keep = {header_id}
    if may_add_line_satellite(draft, prompt=prompt):
        for model in _custom_models(draft):
            mid = str(model.get("model") or "")
            if _is_line_model(mid):
                keep.add(mid)
    removed = {
        str(m.get("model") or "")
        for m in _custom_models(draft)
        if str(m.get("model") or "") not in keep
    }
    if removed:
        _purge(draft, removed)
        notes.append("compiler: thin shape dropped " + ", ".join(sorted(removed)))
    header = next(
        (m for m in _custom_models(draft) if str(m.get("model")) == header_id),
        header,
    )
    notes.extend(_drop_unmentioned_o2ms(header, prompt))
    notes.extend(_slot_fill(draft, header, prompt))
    slots = extract_brief_slots(_prompt_text(draft, prompt))
    if slots.wants_approval:
        try:
            from app.ai_approval_flow import apply_approval_flow

            notes.extend(apply_approval_flow(draft, prompt=prompt, force=True))
        except Exception:  # noqa: BLE001
            pass
    notes.extend(_rebuild_thin_menus(draft, header_id))
    return notes


def _rebuild_thin_menus(draft: dict[str, Any], header_id: str) -> list[str]:
    notes: list[str] = []
    tech = str(draft.get("technical_name") or "custom_app")
    display = str(draft.get("display_name") or tech.replace("_", " ").title())
    slug = re.sub(r"[^a-z0-9]+", "_", tech.lower()).strip("_") or "custom_app"
    action_tech = f"action_{header_id}"
    header_label = next(
        (
            str(m.get("description") or display)
            for m in _custom_models(draft)
            if str(m.get("model")) == header_id
        ),
        display,
    )
    actions = [
        a
        for a in (draft.get("actions") or [])
        if isinstance(a, dict) and str(a.get("model") or "") == header_id
    ]
    if not actions:
        actions = [
            {
                "name": header_label,
                "model": header_id,
                "view_mode": "list,form",
                "technical_name": action_tech,
            }
        ]
        notes.append("compiler: seeded header action")
    else:
        for action in actions:
            action["technical_name"] = action.get("technical_name") or action_tech
            action_tech = str(action.get("technical_name") or action_tech)
    draft["actions"] = actions
    root_xml = f"menu_root_{slug}"
    draft["menus"] = [
        {
            "name": display,
            "sequence": 10,
            "technical_name": f"root_{slug}",
            "xml_id": root_xml,
        },
        {
            "name": header_label if header_label != display else "Requests",
            "action_xml_id": action_tech,
            "parent_xml_id": root_xml,
            "sequence": 10,
            "technical_name": f"menu_{header_id}",
        },
    ]
    notes.append("compiler: rebuilt thin menus")
    return notes


def _collapse_isomorphic_siblings(draft: dict[str, Any], prompt: str) -> list[str]:
    """Workspace: drop custom models that are the same document twice."""
    notes: list[str] = []
    pack_allowed: set[str] = set()
    pack_id = str(draft.get("domain_pack") or "")
    for mid in draft.get("_pack_model_ids") or []:
        pack_allowed.add(str(mid))
    if pack_id and not pack_allowed:
        try:
            from app.ai_domain_packs import load_domain_pack, pack_allowed_model_ids

            pack = load_domain_pack(pack_id)
            if pack:
                pack_allowed = pack_allowed_model_ids(pack)
        except Exception:  # noqa: BLE001
            pack_allowed = set()
    header = _pick_header_model(draft, prompt)
    header_id = str(header.get("model") or "") if header else ""
    groups: dict[tuple[tuple[str, str], ...], list[str]] = {}
    for model in _custom_models(draft):
        mid = str(model.get("model") or "")
        if mid == header_id or _is_line_model(mid) or mid in pack_allowed:
            continue
        sig = _model_signature(model)
        if len(sig) < 1:
            continue
        groups.setdefault(sig, []).append(mid)
    text = _prompt_text(draft, prompt).lower()
    removed: set[str] = set()
    for _sig, mids in groups.items():
        if len(mids) < 2:
            continue
        ranked = sorted(
            mids,
            key=lambda m: (0 if m.replace("x_", "").replace("_", " ") in text else 1, m),
        )
        for extra in ranked[1:]:
            removed.add(extra)
    if removed:
        _purge(draft, removed)
        notes.append("compiler: collapsed isomorphic siblings " + ", ".join(sorted(removed)))
    return notes


def _drop_duplicate_notebook_o2ms(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    by_id = {str(m.get("model")): m for m in _custom_models(draft)}
    pack_allowed = {str(x) for x in (draft.get("_pack_model_ids") or [])}
    for model in _custom_models(draft):
        if _is_line_model(str(model.get("model") or "")):
            continue
        seen: dict[tuple[str, ...], str] = {}
        drop: set[str] = set()
        for field in _field_list(model):
            if str(field.get("ttype") or "") not in {"one2many", "many2many"}:
                continue
            rel = str(field.get("relation") or "")
            if rel in pack_allowed:
                continue
            sig = _o2m_column_signature(field, by_id)
            fname = str(field.get("name") or "")
            if sig in seen:
                drop.add(fname)
            else:
                seen[sig] = fname
        if drop:
            _drop_named_fields(model, drop)
            notes.append(
                f"compiler: dropped duplicate notebook O2M on {model.get('model')}: "
                + ", ".join(sorted(drop))
            )
    return notes


def _force_rebuild_forms(draft: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    views = draft.get("views")
    if isinstance(views, list):
        for view in views:
            if isinstance(view, dict) and view.get("type") == "form":
                view["arch"] = "<form><sheet/></form>"
    try:
        from app.ai_enrich import sync_form_archs_to_models

        notes.extend(sync_form_archs_to_models(draft))
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.preview_views import build_preview_views

        previews = build_preview_views(draft)
        ir = draft.get("_generation_engine")
        if not isinstance(ir, dict):
            ir = {}
            draft["_generation_engine"] = ir
        if previews.get("form"):
            ir["form_preview"] = previews["form"]
        if previews.get("list"):
            ir["list_preview"] = previews["list"]
    except Exception:  # noqa: BLE001
        pass
    return notes


def build_grammar_card(draft: dict[str, Any], *, prompt: str = "") -> dict[str, Any]:
    """Operator-facing contract shown in App Studio before Install."""
    text = _prompt_text(draft, prompt)
    shape = document_shape_of(draft, prompt=text)
    header = _pick_header_model(draft, text)
    display = str(draft.get("display_name") or "App")
    slots: list[str] = []
    states: list[str] = []
    extra = max(0, len(_custom_models(draft)) - 1)
    if header:
        names = _field_names(header)
        if "x_amount" in names or any(
            str(f.get("ttype")) == "monetary" for f in _field_list(header)
        ):
            slots.append("Amount + Currency" if "x_currency_id" in names else "Amount")
        if "x_requester_id" in names:
            slots.append("Requester = Employee")
        if "x_manager_id" in names:
            slots.append("Manager = User")
        # Prefer state_field.states (honors stated Done) over whichever selection
        # field happens to appear first.
        sf = header.get("state_field") if isinstance(header.get("state_field"), dict) else {}
        if sf.get("states"):
            states = [str(s) for s in (sf.get("states") or []) if s]
        else:
            state_f = next(
                (
                    f
                    for f in _field_list(header)
                    if str(f.get("name") or "") in {"x_state", "x_status"}
                ),
                None,
            )
            if state_f:
                keys = re.findall(r"\(\s*'([^']+)'\s*,", str(state_f.get("selection") or ""))
                states = keys
        extra = max(
            0,
            len(
                [
                    m
                    for m in _custom_models(draft)
                    if str(m.get("model")) != str(header.get("model"))
                    and not _is_line_model(str(m.get("model") or ""))
                ]
            ),
        )
    docs = 1 if header else 0
    bits = [f"{docs} document" + ("" if docs == 1 else "s"), display, *slots]
    if states:
        bits.append(f"{len(states)} states")
    bits.append(f"{extra} extra apps")
    return {
        "shape": shape,
        "display_name": display,
        "header_model": str(header.get("model") or "") if header else "",
        "document_count": docs,
        "slots": slots,
        "states": states,
        "extra_apps": extra,
        "summary": " · ".join(bits),
    }


def compile_document_grammar(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Author the draft to its Community document shape. Mutates draft."""
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    pack_id = str(draft.get("domain_pack") or "")
    locked_shapes = {
        "register",
        "field_pack",
        "stock_reuse",
        "catalog",
        "option_a",
    }
    current_shape = str(draft.get("_document_shape") or "")
    if pack_id and current_shape not in locked_shapes:
        try:
            from app.ai_domain_packs import load_domain_pack, pack_document_shape

            declared = pack_document_shape(load_domain_pack(pack_id))
            if declared:
                draft["_document_shape"] = declared
        except Exception:  # noqa: BLE001
            pass
    shape = stamp_document_shape(draft, prompt=text)
    notes.extend(_restore_naming(draft, text))
    if shape in {"transactional_header", "register"}:
        notes.extend(_compile_thin(draft, text, shape))
    elif shape == "workspace":
        notes.extend(_collapse_isomorphic_siblings(draft, text))
        notes.extend(_drop_duplicate_notebook_o2ms(draft))
    if shape in {"transactional_header", "register"}:
        notes.extend(_force_rebuild_forms(draft))
    slots = extract_brief_slots(text)
    draft["_brief_slots"] = {
        "wants_money": slots.wants_money,
        "wants_approval": slots.wants_approval,
        "wants_todo": slots.wants_todo,
        "people": [
            {
                "lemma": p.lemma,
                "relation": p.relation,
                "field": p.field_name,
            }
            for p in slots.people
        ],
    }
    draft["_document_grammar"] = build_grammar_card(draft, prompt=text)
    return notes


def premium_surface_findings(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Amateur surfaces that must block Install.

    Source of truth is ``ai_surface_invariants`` (properties), not named
    screenshots. Add a new invariant + mutant there — do not special-case
    a display_name string here.
    """
    return findings_as_contract(draft)


__all__ = [
    "build_grammar_card",
    "compile_document_grammar",
    "premium_surface_findings",
]
