"""Surface invariants — properties of a premium Odoo app, not screenshot denylists.

A cloned sibling menu or an IR-jargon app title is a *symptom*. The property
is: isomorphic siblings, ungrounded titles, stale preview, missing brief slots.
New operator failures must add a property here (and a mutant), never
``if display_name == "…"``.

We cannot enumerate every Odoo failure. We keep a closed set of *classes*
and attack them with mutants that never mention yesterday's bug.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from app.ai_domain_nouns import extract_prompt_nouns
from app.ai_post_critique import NOUN_STOPWORDS

# IR / pipeline chrome — never a product name. Class, not yesterday's string.
_IR_TITLE_RE = re.compile(
    r"named\s+in\s+brief|in\s+brief|custom\s+residual|capability\s+path|"
    r"clarification|simple\s+document|document\s+shape|operator\s+brief|"
    r"transactional\s+header",
    re.I,
)

_APPROVED_HOST_RE = re.compile(r"(?i)\b(approved host|connect points?|approval_requests template)\b")

_MONEY_RE = re.compile(
    r"\b(amount|currency|price|fee|cost|rate|charge|fare|salary|wage|"
    r"budget|spend|total|monetary|money)\b",
    re.I,
)
# Bare "submit" is too broad (any form). Approval is a decision verb.
_APPROVAL_RE = re.compile(r"\b(approv|refuse|reject)\w*", re.I)
_TODO_RE = re.compile(r"\b(to-?do|activit(?:y|ies)|notif(?:y|ication))\b", re.I)

# Brief person → stock relation. First match wins per relation.
_PERSON_SLOTS: tuple[tuple[str, str, str, str], ...] = (
    ("requester", "hr.employee", "x_requester_id", "Requester"),
    ("submitter", "hr.employee", "x_requester_id", "Requester"),
    ("applicant", "hr.employee", "x_requester_id", "Requester"),
    ("manager", "res.users", "x_manager_id", "Manager"),
    ("approver", "res.users", "x_manager_id", "Manager"),
    ("supervisor", "res.users", "x_manager_id", "Manager"),
    ("reviewer", "res.users", "x_manager_id", "Manager"),
)

_TITLE_STOP = NOUN_STOPWORDS | frozenset(
    {
        "app",
        "apps",
        "module",
        "system",
        "management",
        "new",
        "custom",
        "document",
        "records",
        "record",
        "studio",
    }
)

_SPRAY_RELATIONS = frozenset({"res.partner", "hr.employee", "res.company"})


@dataclass(frozen=True)
class PersonSlot:
    lemma: str
    relation: str
    field_name: str
    string: str


@dataclass
class BriefSlots:
    """What the operator asked for — source of truth for compiler and gate."""

    wants_money: bool = False
    wants_approval: bool = False
    wants_todo: bool = False
    people: list[PersonSlot] = field(default_factory=list)
    prompt_lemmas: frozenset[str] = field(default_factory=frozenset)


def extract_brief_slots(prompt: str) -> BriefSlots:
    from app.ai_operator_brief import intent_corpus

    blob = intent_corpus(prompt or "")
    if _APPROVED_HOST_RE.search(blob):
        blob = _APPROVED_HOST_RE.sub(" ", blob)
    people: list[PersonSlot] = []
    seen_rel: set[str] = set()
    lower = blob.lower()
    for lemma, relation, fname, string in _PERSON_SLOTS:
        if not re.search(rf"\b{re.escape(lemma)}\b", lower):
            continue
        if relation in seen_rel:
            continue
        seen_rel.add(relation)
        people.append(PersonSlot(lemma, relation, fname, string))
    return BriefSlots(
        wants_money=bool(_MONEY_RE.search(blob)),
        wants_approval=bool(_APPROVAL_RE.search(blob)),
        wants_todo=bool(_TODO_RE.search(blob)),
        people=people,
        prompt_lemmas=frozenset(extract_prompt_nouns(blob)),
    )


def is_ir_jargon_title(title: str) -> bool:
    return bool(_IR_TITLE_RE.search(title or ""))


def title_is_grounded(display: str, prompt: str, *, pack_display_name: str = "") -> bool:
    """Product title must come from the brief, a pack fixture, or residual naming."""
    text = (display or "").strip()
    if not text:
        return False
    if pack_display_name and _norm(text) == _norm(pack_display_name):
        return True
    if is_ir_jargon_title(text):
        return False
    try:
        from app.ai_document_shape import naming_from_residual

        named_display, _slug = naming_from_residual(prompt or "")
        if named_display and _norm(named_display) == _norm(text):
            return True
    except Exception:  # noqa: BLE001
        pass
    from app.ai_operator_brief import intent_corpus

    blob = intent_corpus(prompt or "").lower()
    disp = set(extract_prompt_nouns(text)) - _TITLE_STOP
    if not disp:
        return False
    prompt_lemmas = set(extract_prompt_nouns(blob)) - _TITLE_STOP
    if disp & prompt_lemmas:
        return True
    compact = re.sub(r"[^a-z0-9]+", "", blob)
    return any(d in blob or d in compact for d in disp if len(d) > 3)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _as_draft(draft: Any) -> dict[str, Any]:
    if isinstance(draft, dict):
        return draft
    if hasattr(draft, "model_dump"):
        return draft.model_dump(mode="python")
    return {}


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


def _is_line_model(mid: str) -> bool:
    return bool(re.search(r"(?:_line|_lines)$", str(mid or ""))) or str(mid or "").endswith(
        "_party"
    )


def _model_signature(model: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Must stay aligned with ai_document_compiler._model_signature."""
    rows: list[tuple[str, str]] = []
    mid = str(model.get("model") or "")
    for fld in _field_list(model):
        name = str(fld.get("name") or "")
        if name == "x_name":
            continue
        ttype = str(fld.get("ttype") or "char")
        rel = str(fld.get("relation") or "")
        if ttype == "many2one" and rel == mid:
            continue
        if ttype in {"one2many", "many2many"}:
            continue
        rows.append((ttype, rel or name))
    return tuple(sorted(rows))


def isomorphic_sibling_groups(
    models: list[dict[str, Any]], *, skip: set[str] | None = None
) -> list[list[str]]:
    skip = skip or set()
    groups: dict[tuple[tuple[str, str], ...], list[str]] = {}
    for model in models:
        mid = str(model.get("model") or "")
        if mid in skip or _is_line_model(mid):
            continue
        sig = _model_signature(model)
        if len(sig) < 1:
            continue
        groups.setdefault(sig, []).append(mid)
    return [ids for ids in groups.values() if len(ids) > 1]


def preview_notebook_page_count(draft: dict[str, Any]) -> int:
    ir = draft.get("_generation_engine")
    if not isinstance(ir, dict):
        return 0
    fp = ir.get("form_preview") if isinstance(ir.get("form_preview"), dict) else {}
    pages = 0
    for nb in fp.get("notebooks") or []:
        if isinstance(nb, dict):
            pages += len(nb.get("pages") or [])
    return pages


def form_arch_page_count(draft: dict[str, Any], header_id: str) -> int:
    pages = 0
    for view in draft.get("views") or []:
        if not isinstance(view, dict):
            continue
        vtype = str(view.get("type") or view.get("view_type") or "")
        if vtype != "form":
            continue
        model = str(view.get("model") or "")
        if model and model != header_id:
            continue
        pages = max(
            pages, len(re.findall(r"<page\b", str(view.get("arch") or ""), flags=re.I))
        )
    for model in draft.get("models") or []:
        if not isinstance(model, dict) or str(model.get("model") or "") != header_id:
            continue
        for view in model.get("views") or []:
            if not isinstance(view, dict):
                continue
            if str(view.get("type") or view.get("view_type") or "") != "form":
                continue
            pages = max(
                pages, len(re.findall(r"<page\b", str(view.get("arch") or ""), flags=re.I))
            )
    return pages


def header_o2m_count(header: dict[str, Any]) -> int:
    return sum(
        1
        for f in _field_list(header)
        if str(f.get("ttype") or "") in {"one2many", "many2many"}
    )


def _pack_display_name(draft: dict[str, Any]) -> str:
    pack_id = str(draft.get("domain_pack") or "")
    if not pack_id:
        return ""
    try:
        from app.ai_domain_packs import load_domain_pack

        return str(load_domain_pack(pack_id).get("display_name") or "")
    except Exception:  # noqa: BLE001
        return ""


def _pack_allowed(draft: dict[str, Any]) -> set[str]:
    allowed = {str(x) for x in (draft.get("_pack_model_ids") or [])}
    if allowed:
        return allowed
    pack_id = str(draft.get("domain_pack") or "")
    if not pack_id:
        return set()
    try:
        from app.ai_domain_packs import load_domain_pack, pack_allowed_model_ids

        pack = load_domain_pack(pack_id)
        return pack_allowed_model_ids(pack) if pack else set()
    except Exception:  # noqa: BLE001
        return set()


def _has_next_activity(draft: dict[str, Any], header_id: str) -> bool:
    for auto in draft.get("automations") or []:
        if not isinstance(auto, dict):
            continue
        if str(auto.get("model") or "") not in {"", header_id}:
            continue
        actions = auto.get("safe_actions") or []
        if any(isinstance(s, dict) and s.get("kind") == "next_activity" for s in actions):
            return True
        if str(auto.get("kind") or "") == "next_activity":
            return True
    for sa in draft.get("server_actions") or []:
        if not isinstance(sa, dict):
            continue
        if str(sa.get("binding_model") or sa.get("model") or "") != header_id:
            continue
        if sa.get("next_activity") or str(sa.get("kind") or "") == "next_activity":
            return True
    return False


def _o2m_column_signature(
    field: dict[str, Any], models_by_id: dict[str, dict[str, Any]]
) -> tuple[str, ...]:
    child = models_by_id.get(str(field.get("relation") or ""))
    if not child:
        return ("x_name",)
    names = []
    for f in _field_list(child):
        n = str(f.get("name") or "")
        if n in {"x_name", "display_name", "id"}:
            continue
        names.append(f"{f.get('ttype')}:{f.get('relation') or n}")
    return tuple(sorted(names)) or ("x_name",)


def surface_invariant_findings(draft: Any) -> list[str]:
    """Fail closed on property violations. Safe for any prompt, not one vertical."""
    from app.ai_document_shape import document_shape_of

    data = _as_draft(draft)
    findings: list[str] = []
    prompt = str(data.get("_user_prompt") or data.get("prompt") or "")
    shape = document_shape_of(data, prompt=prompt)
    slots = extract_brief_slots(prompt)
    custom = _custom_models(data)
    pack_display = _pack_display_name(data)
    pack_allowed = _pack_allowed(data)

    display = str(data.get("display_name") or "")
    if is_ir_jargon_title(display) or (
        prompt.strip()
        and not title_is_grounded(display, prompt, pack_display_name=pack_display)
    ):
        findings.append(
            "App title is not grounded in the operator brief "
            f"(got {display!r}). Titles must come from the prompt or the pack fixture."
        )

    for group in isomorphic_sibling_groups(custom, skip=pack_allowed):
        findings.append(
            "Isomorphic sibling models (same field types, different names) are not a "
            f"premium surface: {', '.join(group)}."
        )

    by_id = {str(m.get("model")): m for m in custom}
    headers = [m for m in custom if not _is_line_model(str(m.get("model") or ""))]
    header = headers[0] if headers else None
    if header:
        col_sigs: dict[tuple[str, ...], list[tuple[str, str]]] = {}
        for fld in _field_list(header):
            if str(fld.get("ttype") or "") not in {"one2many", "many2many"}:
                continue
            rel = str(fld.get("relation") or "")
            if rel in pack_allowed:
                continue
            sig = _o2m_column_signature(fld, by_id)
            col_sigs.setdefault(sig, []).append((str(fld.get("name") or ""), rel))
        for _sig, pairs in col_sigs.items():
            rels = {rel for _n, rel in pairs}
            if len(pairs) >= 2 and len(rels) >= 2:
                findings.append(
                    "Duplicate notebook pages (different relations, same columns): "
                    + ", ".join(n for n, _r in pairs)
                )

    if shape in {"transactional_header", "register"}:
        extra = [
            m
            for m in custom
            if not _is_line_model(str(m.get("model") or ""))
            and str(m.get("model") or "") not in pack_allowed
        ]
        if len(extra) > 1:
            findings.append(
                f"Thin document shape {shape} allows one header model; found "
                f"{[m.get('model') for m in extra]}."
            )
        leaves = [
            mn
            for mn in (data.get("menus") or [])
            if isinstance(mn, dict) and mn.get("action_xml_id") and mn.get("parent_xml_id")
        ]
        if len(leaves) > 1:
            findings.append(
                f"Thin shape must ship one document menu, not {len(leaves)} sibling apps."
            )
        if header is not None:
            header_id = str(header.get("model") or "")
            o2m = header_o2m_count(header)
            arch_pages = form_arch_page_count(data, header_id)
            preview_pages = preview_notebook_page_count(data)
            if arch_pages > o2m:
                findings.append(
                    f"Form arch has {arch_pages} notebook page(s) but the header has "
                    f"{o2m} one2many field(s) — preview/Odoo would show empty clone tabs."
                )
            if preview_pages > o2m:
                findings.append(
                    f"form_preview still lists {preview_pages} notebook page(s) after "
                    f"compile; header has {o2m} one2many field(s)."
                )
            if slots.wants_money:
                has_amt = any(str(f.get("ttype")) == "monetary" for f in _field_list(header))
                has_cur = any(
                    str(f.get("ttype")) == "many2one"
                    and str(f.get("relation")) == "res.currency"
                    for f in _field_list(header)
                )
                if not (has_amt and has_cur):
                    findings.append(
                        "Brief asks for money; header must have monetary amount and "
                        "res.currency (currency_field)."
                    )
            if slots.wants_approval:
                has_mgr = any(
                    str(f.get("ttype")) == "many2one" and str(f.get("relation")) == "res.users"
                    for f in _field_list(header)
                )
                if not has_mgr:
                    findings.append(
                        "Brief asks for approval; header must have a res.users assignee "
                        "(manager/approver), not a decorative identity field."
                    )
                if slots.wants_todo and not _has_next_activity(data, header_id):
                    findings.append(
                        "Brief asks to notify the assignee; need a next_activity "
                        "automation on the header."
                    )
            asked_rels = {p.relation for p in slots.people}
            lemmas = slots.prompt_lemmas
            for f in _field_list(header):
                if str(f.get("ttype")) != "many2one" or str(f.get("relation")) not in _SPRAY_RELATIONS:
                    continue
                if str(f.get("relation")) in asked_rels:
                    continue
                blob = f"{f.get('name')} {f.get('string')} {f.get('relation')}".lower()
                if not any(lem in blob for lem in lemmas if len(lem) > 3):
                    findings.append(
                        f"Unmentioned identity field {f.get('name')} ({f.get('relation')}) "
                        "is identity spray — not a brief slot."
                    )
            for person in slots.people:
                if not any(
                    str(f.get("ttype")) == "many2one" and str(f.get("relation")) == person.relation
                    for f in _field_list(header)
                ):
                    findings.append(
                        f"Brief names {person.lemma!r}; header needs a {person.relation} field."
                    )

    return findings


def findings_as_contract(draft: Any) -> list[dict[str, Any]]:
    """Shape used by live-apply / Install blocking."""
    rows: list[dict[str, Any]] = []
    for detail in surface_invariant_findings(draft):
        rows.append(
            {
                "dimension": "surface",
                "element": "invariants",
                "detail": f"surface: {detail}",
            }
        )
    return rows


# --- mutants: attack the *class*, not a screenshot ---------------------------------


def mutate_isomorphic_siblings(
    draft: dict[str, Any], names: tuple[str, str] = ("Folio", "Docket")
) -> dict[str, Any]:
    """Clone the header under two new labels. Compiler must collapse them."""
    out = copy.deepcopy(draft)
    headers = [
        m
        for m in (out.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and not _is_line_model(str(m.get("model") or ""))
    ]
    if not headers:
        return out
    src = headers[0]
    root = next(
        (
            mn
            for mn in (out.get("menus") or [])
            if isinstance(mn, dict) and not mn.get("parent_xml_id")
        ),
        None,
    )
    root_xml = str((root or {}).get("xml_id") or "menu_root")
    menus = [m for m in (out.get("menus") or []) if isinstance(m, dict)]
    models = [m for m in (out.get("models") or []) if isinstance(m, dict)]
    for label in names:
        slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        clone = copy.deepcopy(src)
        clone["model"] = f"x_{slug}"
        clone["description"] = label
        models.append(clone)
        menus.append(
            {
                "name": f"{label}s",
                "action_xml_id": f"action_x_{slug}",
                "parent_xml_id": root_xml,
                "technical_name": f"menu_{slug}",
            }
        )
    out["models"] = models
    out["menus"] = menus
    return out


def mutate_ungrounded_title(draft: dict[str, Any], title: str = "Capability Path") -> dict[str, Any]:
    out = copy.deepcopy(draft)
    out["display_name"] = title
    out["technical_name"] = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    models = out.get("models") or []
    if models and isinstance(models[0], dict):
        models[0]["description"] = title
    return out


def mutate_identity_spray(draft: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(draft)
    headers = [
        m
        for m in (out.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and not _is_line_model(str(m.get("model") or ""))
    ]
    if not headers:
        return out
    h = headers[0]
    existing = {str(f.get("name")) for f in _field_list(h)}
    spray = [
        {"name": "x_contact_id", "string": "Contact", "ttype": "many2one", "relation": "res.partner"},
        {
            "name": "x_employee_id",
            "string": "Employee",
            "ttype": "many2one",
            "relation": "hr.employee",
        },
        {
            "name": "x_company_id",
            "string": "Company",
            "ttype": "many2one",
            "relation": "res.company",
        },
    ]
    fields = list(_field_list(h))
    for f in spray:
        if f["name"] not in existing:
            fields.append(f)
    h["fields"] = fields
    return out


def mutate_stale_preview_tabs(draft: dict[str, Any]) -> dict[str, Any]:
    """Notebook pages in form_preview with no matching O2M — compile must rebuild."""
    out = copy.deepcopy(draft)
    ge = dict(out.get("_generation_engine") or {})
    ge["form_preview"] = {
        "notebooks": [
            {
                "pages": [
                    {"string": "Clone A", "fields": ["x_name"]},
                    {"string": "Clone B", "fields": ["x_name"]},
                ]
            }
        ]
    }
    out["_generation_engine"] = ge
    views = [
        {
            "type": "form",
            "model": str((out.get("models") or [{}])[0].get("model") or ""),
            "arch": (
                '<form><sheet><notebook>'
                '<page string="Clone A"/><page string="Clone B"/>'
                "</notebook></sheet></form>"
            ),
        }
    ]
    out["views"] = views
    return out
