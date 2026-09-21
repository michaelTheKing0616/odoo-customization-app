"""Domain-agnostic document shape — lock architecture before Flash and the closer.

Shapes (any industry can land on one):
  stock_reuse | field_pack | register | catalog | transactional_header | workspace | option_a

A visitor log, key log, or call log is ``register``. SLA-on-invoices is ``field_pack``. Residual-none POS is
``stock_reuse``. Matched vertical pack / explicit full app is ``workspace``.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from app.text_negation import has_positive_match, has_positive_needle

DocumentShape = Literal[
    "stock_reuse",
    "field_pack",
    "register",
    "catalog",
    "transactional_header",
    "workspace",
    "option_a",
]

THIN_SHAPES: frozenset[str] = frozenset(
    {"register", "field_pack", "stock_reuse", "catalog"}
)
ADDITIVE_BLOCKED: frozenset[str] = frozenset(
    {"register", "field_pack", "stock_reuse"}
)

SHAPE_BUDGET: dict[str, int] = {
    "stock_reuse": 0,
    "field_pack": 0,
    "register": 1,
    "catalog": 2,
    "option_a": 2,
    "transactional_header": 2,
}

_REGISTER_SHAPE_RE = re.compile(
    r"(?i)\b("
    r"[\w-]+\s+(?:log|register|ledger|book)\b|"
    r"(?:sign[- ]?in|attendance|call|incident)\s+"
    r"(?:log|book|register|sheet)|"
    r"paper\s+(?:book|log|register)|"
    r"guest\s*book|"
    r"entry\s+(?:log|book)|"
    r"checklist|"
    r"loyalty\s+punch\s*card|punch\s*card|loyalty\s+card"
    r")\b"
)
_CATALOG_SHAPE_RE = re.compile(
    r"(?i)\b(rate\s+card|equipment\s+types?|product\s+catalog|price\s+list)\b"
)
_WORKSPACE_RE = re.compile(
    r"(?i)\b("
    r"full\s+app|standalone|from\s+scratch|comprehensive|"
    r"practice\s+management|management\s+(?:system|app)|"
    r"\bpms\b|\berp\b"
    r")\b"
)
_LINE_NOUN_RE = re.compile(r"(?i)\b(lines?|items?|qty|quantity|hours?)\b")
_PARTY_NOUN_RE = re.compile(r"(?i)\b(roles?|parties|attendees|participants)\b")
_COLUMN_LIST_RE = re.compile(
    r"(?i)in odoo\s*:\s*(.+?)(?:\.(?:\s+[A-Z])|$)",
    re.S,
)
_PUNCH_CARD_RESIDUAL_RE = re.compile(
    r"(?i)\b(?:loyalty\s+)?punch\s*cards?|loyalty\s+cards?\b"
)
_TIED_TO_CUSTOMER_RE = re.compile(
    r"(?i)\btied to the customer|\bcustomer\s*\(\s*contacts\s*\)|"
    r"\blink(?:ed)?\s+to\s+(?:the\s+)?(?:customer|contact|partner)"
)
_BUY_N_FREE_RE = re.compile(
    r"(?i)buy\s+(\d+)\s+\w+.*?(?:get|and)\s+(?:the\s+)?(\d+)(?:th|st|nd|rd)?"
)
_DURATION_HOURS_RE = re.compile(
    r"(?i)more than\s+(\d+|one|two|three|four|five|six)\s+hours?"
)
_WORD_HOURS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
}
_FORBIDDEN_HOSTS: dict[str, tuple[str, ...]] = {
    "crm": ("crm.lead",),
    "account": ("account.move", "account.payment"),
    "sale": ("sale.order",),
    "calendar": ("calendar.event",),
    "project": ("project.task", "project.project"),
    "purchase": ("purchase.order",),
}

SHAPE_DEPTH_FLOORS: dict[str, dict[str, float]] = {
    "register": {
        "min_models": 1,
        "min_fields_avg": 4,
        "min_m2o": 1,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
    },
    "field_pack": {
        "min_models": 0,
        "min_fields_avg": 1,
        "min_m2o": 0,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
    },
    "stock_reuse": {
        "min_models": 0,
        "min_fields_avg": 0,
        "min_m2o": 0,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
    },
    "catalog": {
        "min_models": 1,
        "min_fields_avg": 3,
        "min_m2o": 0,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
    },
    "transactional_header": {
        "min_models": 1,
        "min_fields_avg": 4,
        "min_m2o": 1,
        "min_workflows": 0,
        "min_smart_buttons": 0,
        "min_automations": 0,
    },
}


def classify_document_shape(
    prompt: str,
    draft: dict[str, Any] | None = None,
) -> DocumentShape:
    """Infer shape from stated residual, grain, pack, and negations — not word count."""
    text = prompt or ""
    draft = draft if isinstance(draft, dict) else {}
    pack_id = str(draft.get("domain_pack") or "")
    stamped = draft.get("_document_shape")
    # Pack + Paystack/QR is still a workspace. Do not keep a prior option_a stamp.
    if pack_id and stamped == "option_a":
        stamped = None
    # Thin packs must not inherit a prior workspace stamp from pack-match.
    if pack_id and stamped == "workspace":
        try:
            from app.ai_domain_packs import load_domain_pack, pack_document_shape

            declared = pack_document_shape(load_domain_pack(pack_id))
            if declared != "workspace":
                stamped = None
        except Exception:  # noqa: BLE001
            pass
    if stamped in {
        "stock_reuse",
        "field_pack",
        "register",
        "catalog",
        "transactional_header",
        "workspace",
        "option_a",
    }:
        return stamped  # type: ignore[return-value]
    plan = draft.get("_architecture_plan") if isinstance(draft.get("_architecture_plan"), dict) else {}
    planned = plan.get("document_shape")
    if pack_id and planned == "option_a":
        planned = None
    if planned in {
        "stock_reuse",
        "field_pack",
        "register",
        "catalog",
        "transactional_header",
        "workspace",
        "option_a",
    }:
        return planned  # type: ignore[return-value]

    engine = draft.get("_generation_engine") if isinstance(draft.get("_generation_engine"), dict) else {}
    if (
        engine.get("capability") == "stock_reuse"
        or draft.get("_pipeline") == "generation_engine_stock_reuse"
        or str(draft.get("technical_name") or "") == "stock_reuse"
    ):
        return "stock_reuse"
    try:
        from app.ai_operator_brief import wants_stock_reuse

        if wants_stock_reuse(text):
            return "stock_reuse"
    except Exception:  # noqa: BLE001
        pass

    grain = str(draft.get("grain") or "")
    if grain == "field_pack" or draft.get("_component"):
        return "field_pack"
    option_a_gen = False
    try:
        from app.ai_generation_engine import classify_generation

        gen = classify_generation(text)
        if gen.capability == "stock_reuse":
            return "stock_reuse"
        if gen.grain == "field_pack":
            return "field_pack"
        if gen.capability == "refuse_clone":
            return "stock_reuse"
        option_a_gen = bool(
            gen.capability in {"option_a_standalone", "option_a", "option_a_authored"}
            or gen.gold_artifact_id
        )
    except Exception:  # noqa: BLE001
        pass

    if pack_id:
        try:
            from app.ai_domain_packs import load_domain_pack, pack_document_shape

            return pack_document_shape(load_domain_pack(pack_id))
        except Exception:  # noqa: BLE001
            return "workspace"
    try:
        from app.ai_domain_packs import match_domain_pack, pack_document_shape

        matched = match_domain_pack(text)
        if matched:
            return pack_document_shape(matched[1])
    except Exception:  # noqa: BLE001
        pass

    if option_a_gen or bool(draft.get("_capability_primary_option_a")):
        return "option_a"

    if has_positive_match(_REGISTER_SHAPE_RE, text):
        return "register"
    kind, residual = _named_residual(text)
    if kind == "named" and residual and has_positive_match(_REGISTER_SHAPE_RE, residual):
        return "register"
    if _CATALOG_SHAPE_RE.search(text):
        return "catalog"
    if has_positive_match(_WORKSPACE_RE, text):
        return "workspace"
    if str(draft.get("_ambition") or "") == "comprehensive":
        return "workspace"
    # Named residual plus two+ stock apps is a workspace (policy+quotes+invoices),
    # not a one-header register. Register regex already returned above.
    try:
        from app.ai_operator_brief import build_operator_brief

        brief = build_operator_brief(text)
        ops = {
            str(a).strip().lower()
            for a in brief.stock_reuse
            if str(a).strip().lower()
            in {
                "account",
                "sale",
                "crm",
                "calendar",
                "project",
                "purchase",
                "stock",
                "point_of_sale",
                "hr",
            }
        }
        if kind == "named" and residual and len(ops) >= 2:
            return "workspace"
    except Exception:  # noqa: BLE001
        pass
    return "transactional_header"


def document_shape_of(draft: dict[str, Any], *, prompt: str = "") -> DocumentShape:
    text = prompt or str(draft.get("_user_prompt") or "")
    return classify_document_shape(text, draft)


def additive_model_growth_blocked(draft: dict[str, Any], *, prompt: str = "") -> bool:
    return document_shape_of(draft, prompt=prompt) in ADDITIVE_BLOCKED


def shape_budget(shape: str, *, x_models: int = 0, pack_n: int = 0) -> int:
    if shape == "workspace":
        return max(x_models, pack_n, 8)
    if shape == "transactional_header":
        return max(1, x_models)
    if shape in SHAPE_BUDGET:
        return SHAPE_BUDGET[shape]
    return max(x_models, 1)


_WORKSPACE_BRIDGE_APPS = frozenset(
    {
        "sale",
        "account",
        "crm",
        "project",
        "purchase",
        "maintenance",
        "hr",
        "calendar",
        "stock",
    }
)


def allowed_bridge_modules(draft: dict[str, Any], *, prompt: str = "") -> set[str]:
    """Stock inherit bridges need a positively named reuse app and must not be forbidden.

    Workspace / pack drafts also inherit bridges from ``depends`` (oil/gas purchase,
    project, maintenance) minus ``forbidden_bridges``.
    """
    brief = draft.get("_operator_brief") if isinstance(draft.get("_operator_brief"), dict) else {}
    named = {str(x).strip().lower() for x in (brief.get("stock_reuse") or []) if x}
    forbidden = {str(x).strip().lower() for x in (brief.get("forbidden_bridges") or []) if x}
    text = prompt or str(draft.get("_user_prompt") or "") or str(brief.get("formatted") or "")
    if not named:
        if has_positive_needle(text, "employee") or has_positive_needle(text, "hr"):
            named.add("hr")
        if has_positive_match(re.compile(r"(?i)\binvoices?\b|\binvoicing\b"), text):
            named.add("account")
        if has_positive_match(re.compile(r"(?i)\bquotations?\b|\bsales orders?\b"), text):
            named.add("sale")
        if has_positive_match(re.compile(r"(?i)\bleads?\b|\bcrm\b"), text):
            named.add("crm")
    shape = str(draft.get("_document_shape") or "")
    if shape == "workspace" or draft.get("domain_pack"):
        for dep in draft.get("depends") or []:
            app = str(dep).strip().lower()
            if app in _WORKSPACE_BRIDGE_APPS:
                named.add(app)
    return named - forbidden


def forbidden_stock_hosts(draft: dict[str, Any]) -> set[str]:
    brief = draft.get("_operator_brief") if isinstance(draft.get("_operator_brief"), dict) else {}
    hosts: set[str] = set()
    for app in brief.get("forbidden_bridges") or []:
        for host in _FORBIDDEN_HOSTS.get(str(app).strip().lower(), ()):
            hosts.add(host)
    scope = " ".join(str(x) for x in (brief.get("out_of_scope") or [])).lower()
    if "crm" in scope:
        hosts.add("crm.lead")
    # Bare "invoicing" / don't-invent — not "new invoices app" / clone account.move
    if re.search(r"(?:^|\s)invoicing(?:\s|$)", scope) and "app" not in scope:
        hosts.add("account.move")
    return hosts


def may_add_line_satellite(draft: dict[str, Any], *, prompt: str = "") -> bool:
    shape = document_shape_of(draft, prompt=prompt)
    if shape in ADDITIVE_BLOCKED or shape == "catalog":
        return False
    text = prompt or str(draft.get("_user_prompt") or "")
    if shape == "transactional_header":
        return has_positive_match(_LINE_NOUN_RE, text)
    return True


def may_add_party_satellite(draft: dict[str, Any], *, prompt: str = "") -> bool:
    shape = document_shape_of(draft, prompt=prompt)
    if shape in ADDITIVE_BLOCKED or shape == "catalog":
        return False
    text = prompt or str(draft.get("_user_prompt") or "")
    if shape == "transactional_header":
        return has_positive_match(_PARTY_NOUN_RE, text)
    return True



_APP_NOUN_RE = re.compile(
    r"(?i)\b(?:build|create|make)\s+(?:an?\s+)?(?:(?:tiny|simple|small|new|mini|light(?:weight)?)\s+)*"
    r"(.+?)\s+apps?\b"
    r"|^\s*([A-Z][\w][\w\s/-]{1,48}?)(?=\s*:)"
)
_SIZE_ADJ_RE = re.compile(
    r"(?i)^(?:a|an|the|tiny|simple|small|new|mini|light(?:weight)?|basic|minimal)\s+"
)
_APP_CHROME_RE = re.compile(
    r"(?i)\s+apps?(?:\s*:\s*models?)?$|\s*:\s*models?$|\s+models?$"
)


def _scrub_residual_title(label: str) -> str:
    """Visitor Log — never «Tiny X App: Model» / «… Models»."""
    text = (label or "").strip()
    if not text:
        return ""
    # Prefer "Build a tiny Visitor Log app" noun over the whole clause.
    m = _APP_NOUN_RE.search(text)
    if m:
        text = (m.group(1) or m.group(2) or "").strip()
    # Strip leading size/articles repeatedly.
    while True:
        nxt = _SIZE_ADJ_RE.sub("", text).strip()
        if nxt == text:
            break
        text = nxt
    text = _APP_CHROME_RE.sub("", text).strip(" -:.,")
    # "Dining Tables for our restaurant" → Dining Tables
    text = re.sub(
        r"(?i)\s+for\s+(?:our|the|a|my|this)\s+[\w][\w\s-]{0,40}$",
        "",
        text,
    ).strip()
    # "Visitor Log: Name, Company" → noun before colon when short.
    if ":" in text:
        left, right = text.split(":", 1)
        if len(left.strip()) <= 40 and not re.search(r"(?i)\bmodel", left):
            text = left.strip()
    text = re.sub(r"\s+", " ", text).strip(" -:.,")
    return text


def naming_from_residual(prompt: str) -> tuple[str, str]:
    """(display_name, technical_name) from the residual noun — not the first sentence.

    Contract title, display_name, menu, and find-it share one residual app noun
    (Visitor Log) — never «Tiny X App: Model» / «… Models».
    """
    _kind, residual = _named_residual(prompt)
    label = _scrub_residual_title(residual or "")
    if not label:
        label = _scrub_residual_title(_title_from_operator_prompt(prompt))
    if not label:
        label = _scrub_residual_title(prompt or "")
    if not label:
        return "", ""
    label = re.split(r"[.(]", label, maxsplit=1)[0].strip()
    label = re.sub(r"(?i)^(a|an|the)\s+", "", label).strip()
    label = _scrub_residual_title(label)
    if not label or label.lower() in {"none", "app", "module", "system", "named in brief", "model", "models"}:
        return "", ""
    words = [w for w in re.split(r"[\s_]+", label) if w]
    # Preserve intentional internal caps (Visitor Log); otherwise title-case.
    if label != label.lower() and label != label.upper():
        display = " ".join(words)
        # Normalize size-adj leftovers that survived with odd caps.
        display = re.sub(
            r"(?i)^(tiny|simple|small|mini|new)\s+",
            "",
            display,
        ).strip()
        display = " ".join(
            w if (w[:1].isupper() and any(c.islower() for c in w[1:])) else w.capitalize()
            for w in display.split()
        )
    else:
        display = " ".join(w.capitalize() for w in words)
    slug = re.sub(r"[^a-z0-9]+", "_", display.lower()).strip("_")[:40]
    return display, slug or "custom_app"


_PLACEHOLDER_TITLE_RE = re.compile(
    r"(?i)^(named\s+in\s+brief|named\s+briefs?|custom\s+app|untitled|new\s+app)$"
)
_CLARIFY_CHROME_RE = re.compile(
    r"(?i)^(custom residual|capability path|out of scope|industry|##)\b"
)


def _title_from_operator_prompt(prompt: str) -> str:
    """Document title from the operator sentences — never IR/clarify jargon."""
    text = prompt or ""
    try:
        from app.ai_operator_brief import intent_corpus

        text = intent_corpus(text) or text
    except Exception:  # noqa: BLE001
        pass
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _CLARIFY_CHROME_RE.match(stripped):
            continue
        kept.append(stripped)
    blob = " ".join(kept).strip() or (prompt or "").strip()
    first = re.split(r"[.\n]", blob, maxsplit=1)[0].strip()
    first = re.split(
        r"(?i)\s+(?:with|that|which|where|including)\s+", first, maxsplit=1
    )[0].strip()
    first = re.sub(
        r"(?i)^(i need|i want|build|create|make|add)\s+",
        "",
        first,
    ).strip()
    first = re.sub(r"(?i)^(a|an|the)\s+", "", first).strip()
    if _PLACEHOLDER_TITLE_RE.match(first):
        return ""
    if len(first) > 48:
        first = first[:48].rsplit(" ", 1)[0]
    return first


def stamp_document_shape(
    draft: dict[str, Any],
    *,
    prompt: str = "",
) -> DocumentShape:
    text = prompt or str(draft.get("_user_prompt") or "")
    shape = classify_document_shape(text, draft)
    draft["_document_shape"] = shape
    return shape



def ensure_residual_must_do_fields(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Stamp Diagnosis Must-do fields onto the primary residual x_* model.

    Structural: any residual full_app with declared columns (char / M2O / date /
    selection) — not Visitor-only. Covers honesty seed when shape ≠ register
    (Asset Checkout → transactional_header) and pack-seed overlays (Dining Tables).
    """
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    if not text:
        return notes
    try:
        from app.ai_field_ir import fields_from_residual_brief
    except Exception:  # noqa: BLE001
        return notes
    must = fields_from_residual_brief(text)
    if len(must) <= 1:
        return notes
    display, slug = naming_from_residual(text)
    want_mid = f"x_{slug}" if slug and not slug.startswith("x_") else (slug or "")
    models = [m for m in (draft.get("models") or []) if isinstance(m, dict) and m.get("model")]
    header = next((m for m in models if want_mid and str(m.get("model")) == want_mid), None)
    freshly_seeded = False
    if header is None:
        mid = want_mid or "x_custom"
        header = {
            "model": mid,
            "description": display or mid,
            "mode": "new",
            "source": "must_do_fields",
            "fields": list(must),
        }
        draft.setdefault("models", []).insert(0, header)
        notes.append(f"must_do: seeded primary {mid} with {len(must)} fields")
        freshly_seeded = True
    if not freshly_seeded:
        fields = [f for f in (header.get("fields") or []) if isinstance(f, dict)]
        have = {str(f.get("name") or "") for f in fields}
        added = 0
        for row in must:
            name = str(row.get("name") or "")
            if not name:
                continue
            if name in have:
                for existing in fields:
                    if str(existing.get("name") or "") != name:
                        continue
                    have_t = str(existing.get("ttype") or "char").lower()
                    want_t = str(row.get("ttype") or "char").lower()
                    # Upgrade weak char/text, AND correct date↔datetime when Must-do knows.
                    if have_t != want_t and (
                        (have_t in {"char", "text", ""} and want_t not in {None, "char", ""})
                        or (have_t in {"date", "datetime"} and want_t in {"date", "datetime"})
                    ):
                        existing.update({k: v for k, v in row.items() if k != "name"})
                        notes.append(f"must_do: upgraded {name} to {row.get('ttype')}")
                    break
                continue
            fields.append(dict(row))
            have.add(name)
            added += 1
        header["fields"] = fields
        if added:
            notes.append(f"must_do: +{added} fields on {header.get('model')}")
    depends = [str(x) for x in (draft.get("depends") or []) if x]
    for field in header.get("fields") or []:
        if not isinstance(field, dict):
            continue
        rel = str(field.get("relation") or "")
        if rel == "res.partner" and "contacts" not in depends:
            depends.append("contacts")
        if rel == "hr.employee" and "hr" not in depends:
            depends.append("hr")
        if rel.startswith("product.") and "product" not in depends:
            depends.append("product")
    draft["depends"] = list(dict.fromkeys(depends))
    return notes



def seed_register_from_brief(
    draft: dict[str, Any],
    *,
    prompt: str = "",
) -> list[str]:
    """One header x_* with stated columns. No party/line/CRM/invoice clones."""
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    display, slug = naming_from_residual(text)
    if not slug:
        slug = "register"
        display = display or "Register"
    mid = f"x_{slug}" if not slug.startswith("x_") else slug
    tech = slug[2:] if slug.startswith("x_") else slug
    draft["technical_name"] = tech
    draft["display_name"] = display or tech.replace("_", " ").title()
    draft["_document_shape"] = "register"
    draft["_ambition"] = "thin"
    depends = ["base", "mail"]
    fields = _fields_from_column_list(text)
    # Always merge Must-do residual fields (char/M2O/date/selection). Column-list
    # alone often keeps only Name+Host and drops Visit date / Purpose.
    try:
        from app.ai_field_ir import fields_from_residual_brief

        must = fields_from_residual_brief(text)
        if must:
            by_name = {str(f.get("name") or ""): dict(f) for f in fields if f.get("name")}
            for row in must:
                name = str(row.get("name") or "")
                if not name:
                    continue
                if name not in by_name:
                    by_name[name] = dict(row)
                    continue
                have_t = str(by_name[name].get("ttype") or "char").lower()
                want_t = str(row.get("ttype") or "char").lower()
                if have_t != want_t and (
                    (have_t in {"char", "text", ""} and want_t not in {None, "char", ""})
                    or (have_t in {"date", "datetime"} and want_t in {"date", "datetime"})
                ):
                    by_name[name].update({k: v for k, v in row.items() if k != "name"})
            # Prefer Must-do order when it is richer; else keep column-list order + extras.
            if len(must) >= len(fields):
                ordered = []
                seen: set[str] = set()
                for row in must:
                    name = str(row.get("name") or "")
                    if name and name in by_name and name not in seen:
                        ordered.append(by_name[name])
                        seen.add(name)
                for name, row in by_name.items():
                    if name not in seen:
                        ordered.append(row)
                        seen.add(name)
                fields = ordered
            else:
                fields = list(by_name.values())
    except Exception:  # noqa: BLE001
        pass
    if any(f.get("relation") == "hr.employee" for f in fields):
        depends.append("hr")
    if any(f.get("relation") == "res.partner" for f in fields):
        depends.append("contacts")
    draft["depends"] = list(dict.fromkeys(depends))
    header = {
        "model": mid,
        "description": display or "Register",
        "mode": "new",
        "source": "honesty_ir",
        "mixins": ["mail.thread", "mail.activity.mixin"],
        "fields": fields,
    }
    draft["models"] = [header]
    draft["smart_buttons"] = []
    if _PUNCH_CARD_RESIDUAL_RE.search(text) and any(
        str(f.get("name")) == "x_partner_id" for f in fields
    ):
        draft["smart_buttons"] = [
            {
                "on_model": "res.partner",
                "label": f"{display or 'Punch Cards'}",
                "related_model": mid,
                "relation_field": "x_partner_id",
                "icon": "fa-ticket",
                "requires_inherit_view": True,
                "note": "Applied as inherit on Contacts button_box",
            }
        ]
        notes.append(f"document_shape: Contacts smart button on {mid}")
    notes.append(f"document_shape: seeded register {mid}")
    notes.extend(ensure_duration_activity(draft, prompt=text))
    return notes


def ensure_duration_activity(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """No-code on_time + next_activity when the brief asks for a duration alert."""
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    match = _DURATION_HOURS_RE.search(text)
    if not match:
        return notes
    raw = match.group(1).lower()
    hours = _WORD_HOURS.get(raw) or int(raw)
    if hours <= 0:
        return notes
    models = [m for m in (draft.get("models") or []) if isinstance(m, dict) and m.get("model")]
    if not models:
        return notes
    header = next(
        (m for m in models if str(m.get("model") or "").startswith("x_")),
        models[0],
    )
    mid = str(header.get("model"))
    date_field = None
    for f in header.get("fields") or []:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "")
        ttype = str(f.get("ttype") or "")
        if ttype in {"datetime", "date"} and ("in" in name or name.endswith("_start")):
            date_field = name
            break
    if not date_field:
        for f in header.get("fields") or []:
            if isinstance(f, dict) and str(f.get("ttype") or "") in {"datetime", "date"}:
                date_field = str(f.get("name"))
                break
    if not date_field:
        return notes
    out_field = next(
        (
            str(f.get("name"))
            for f in (header.get("fields") or [])
            if isinstance(f, dict)
            and "out" in str(f.get("name") or "")
            and str(f.get("ttype") or "") in {"datetime", "date"}
        ),
        None,
    )
    filt = f"[('{out_field}', '=', False)]" if out_field else "[]"
    autos = draft.setdefault("automations", [])
    name = f"{mid}_duration_alert"
    if not _duration_alert_present(autos, mid=mid, date_field=date_field, filt=filt):
        autos.append(
            {
                "name": name,
                "model": mid,
                "trigger": "on_time",
                "trg_date_field_name": date_field,
                "trg_date_range": hours,
                "trg_date_range_type": "hour",
                "trg_date_range_mode": "after",
                "filter_domain": filt,
                "description": f"No-code alert {hours}h after {date_field}",
                "safe_actions": [
                    {
                        "kind": "next_activity",
                        "summary": f"Still open after {hours} hours",
                        "activity_type_xml_id": "mail.mail_activity_data_todo",
                    }
                ],
                "source": "honesty_ir",
            }
        )
        notes.append(f"document_shape: duration activity {hours}h on {mid}.{date_field}")
    notes.extend(
        _keep_one_duration_on_time(
            draft, mid=mid, date_field=date_field, hours=hours
        )
    )
    mixins = {str(x) for x in (header.get("mixins") or [])}
    mixins.update({"mail.thread", "mail.activity.mixin"})
    header["mixins"] = sorted(mixins)
    return notes


def _duration_alert_present(
    autos: list[Any], *, mid: str, date_field: str, filt: str
) -> bool:
    """True if a no-code on_time alert already exists — names may have been humanized."""
    want_dom = re.sub(r"\s+", "", filt or "")
    want_name = f"{mid}_duration_alert"
    for auto in autos:
        if not isinstance(auto, dict):
            continue
        if str(auto.get("model") or "") != mid:
            continue
        if str(auto.get("trigger") or "") != "on_time":
            continue
        if str(auto.get("trg_date_field_name") or "") == date_field:
            return True
        slug = re.sub(r"[^a-z0-9]+", "_", str(auto.get("name") or "").lower()).strip("_")
        if slug == want_name:
            return True
        if want_dom and re.sub(r"\s+", "", str(auto.get("filter_domain") or "")) == want_dom:
            return True
    return False


_STOCK_CLOCK_FIELDS = frozenset({"create_date", "write_date", "__last_update"})


def _on_time_duration_rank(
    auto: dict[str, Any], *, date_field: str, hours: int
) -> tuple[int, int, int, int, int, str]:
    clock = str(auto.get("trg_date_field_name") or "")
    try:
        rng = int(auto.get("trg_date_range") or 0)
    except (TypeError, ValueError):
        rng = 0
    actions = auto.get("safe_actions") or []
    field_user = any(
        isinstance(a, dict) and str(a.get("user_id") or "").startswith("x_")
        for a in actions
    )
    return (
        0 if clock == date_field else 1,
        0 if rng == hours else 1,
        0 if str(auto.get("source") or "") == "honesty_ir" else 1,
        0 if clock not in _STOCK_CLOCK_FIELDS else 1,
        1 if field_user else 0,
        str(auto.get("name") or ""),
    )


def _keep_one_duration_on_time(
    draft: dict[str, Any], *, mid: str, date_field: str, hours: int
) -> list[str]:
    """One duration clock per header — drop Flash create_date / missing-range twins."""
    notes: list[str] = []
    autos = draft.get("automations")
    if not isinstance(autos, list):
        return notes
    timed = [
        a
        for a in autos
        if isinstance(a, dict)
        and str(a.get("model") or "") == mid
        and str(a.get("trigger") or "") == "on_time"
    ]
    if len(timed) <= 1:
        return notes
    timed.sort(key=lambda a: _on_time_duration_rank(a, date_field=date_field, hours=hours))
    keep = timed[0]
    kept: list[Any] = []
    dropped: list[str] = []
    for auto in autos:
        if (
            isinstance(auto, dict)
            and str(auto.get("model") or "") == mid
            and str(auto.get("trigger") or "") == "on_time"
            and auto is not keep
        ):
            dropped.append(str(auto.get("name") or ""))
            continue
        kept.append(auto)
    if dropped:
        draft["automations"] = kept
        notes.append(
            "document_shape: dropped competing on_time "
            + ", ".join(dropped)
        )
    return notes


def normalize_punch_card_fields(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Collapse Flash duplicates on loyalty punch-card registers.

    Keeps: Customer (x_partner_id), punches / remaining / next-free / reward threshold,
    and optional Last Transaction→pos.order (create-gated with no_create).
    Drops: second Customer M2O named like the model, total_punches twin, next-free as date.
    """
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    if not _PUNCH_CARD_RESIDUAL_RE.search(text):
        return notes
    try:
        from app.ai_model_quality import dedupe_redundant_partner_fields

        notes.extend(dedupe_redundant_partner_fields(draft))
    except Exception:  # noqa: BLE001
        pass

    notes.extend(strip_backend_unsafe_relations(draft))

    drop_always = frozenset(
        {
            "x_next_free_punch_date",
        }
    )
    # Prefer x_punches over x_total_punches (same meaning).
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or mid.endswith("_line"):
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        names = {str(f.get("name") or "") for f in fields}
        kept: list[dict[str, Any]] = []
        dropped: list[str] = []
        for field in fields:
            name = str(field.get("name") or "")
            if name in drop_always:
                dropped.append(name)
                continue
            if name == "x_total_punches":
                if "x_punches" in names:
                    dropped.append(name)
                    continue
                field = {**field, "name": "x_punches", "string": field.get("string") or "Punches"}
                name = "x_punches"
                notes.append(f"register: renamed x_total_punches → x_punches on {mid}")
            if name == "x_partner_id":
                field = {**field, "required": True}
            kept.append(field)
        if dropped:
            model["fields"] = kept
            notes.append(f"register: dropped punch-card noise {', '.join(dropped)} on {mid}")
            for v in draft.get("views") or []:
                if not isinstance(v, dict) or v.get("model") != mid:
                    continue
                arch = str(v.get("arch") or "")
                new_arch = arch
                for name in dropped:
                    new_arch = re.sub(
                        rf'<field name="{re.escape(name)}"(?:[^>]*)?/?>',
                        "",
                        new_arch,
                    )
                if "x_total_punches" in arch and "x_punches" in {str(f.get("name")) for f in kept}:
                    new_arch = new_arch.replace("x_total_punches", "x_punches")
                if new_arch != arch:
                    v["arch"] = new_arch
        else:
            model["fields"] = kept
    notes.extend(ensure_operator_field_help(draft, prompt=text))
    notes.extend(_clip_register_depends(draft))
    return notes


# Deprecated alias — use apply_odoo_create_gates. Kept for import stability.
_BACKEND_UNSAFE_RELATIONS = frozenset(
    {
        "pos.order",
        "pos.order.line",
        "pos.session",
        "pos.payment",
        "pos.payment.method",
        "pos.pack.operation.lot",
    }
)

_PUNCH_FIELD_HELP: dict[str, str] = {
    "x_name": "Label or code the cashier recognizes for this card.",
    "x_partner_id": "Customer this loyalty card belongs to (Contacts).",
    "x_punches": "Paid punches earned so far.",
    "x_remaining_punches": "Punches left until the next free item — show this to the cashier.",
    "x_next_free": "On when the next purchase should be free.",
    "x_punches_for_reward": "How many paid punches unlock a free one (e.g. buy 9 get the 10th free).",
    "x_last_punch_date": "When this card was last punched.",
    "x_next_punch_date": "Optional reminder for the next visit.",
    "x_last_transaction_id": (
        "Existing Point of Sale order for this punch (pick from PoS — do not create here)."
    ),
}


def strip_backend_unsafe_relations(draft: dict[str, Any]) -> list[str]:
    """Apply Odoo create-gates (no_create vs strip). Prefer ``apply_odoo_create_gates``."""
    from app.ai_odoo_create_gates import apply_odoo_create_gates

    return apply_odoo_create_gates(draft)


def ensure_operator_field_help(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Stamp short cashier/clerk tooltips on residual fields missing `help`."""
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    punch = bool(_PUNCH_CARD_RESIDUAL_RE.search(text))
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "")
            if str(field.get("help") or "").strip():
                continue
            help_txt = ""
            if punch and name in _PUNCH_FIELD_HELP:
                help_txt = _PUNCH_FIELD_HELP[name]
            elif field.get("relation") == "res.partner":
                help_txt = "Link to Contacts — do not invent a parallel customer model."
            elif field.get("relation") == "hr.employee":
                help_txt = "Link to Employees — do not invent a parallel staff model."
            elif str(field.get("ttype") or "") in {"integer", "float"} and "punch" in name:
                help_txt = "Numeric value cashiers use on this residual document."
            elif name == "x_name":
                label = str(model.get("description") or draft.get("display_name") or "record")
                help_txt = f"Display name for this {label}."
            if help_txt:
                field["help"] = help_txt
                notes.append(f"ux: added help tooltip on {mid}.{name}")
    return notes


def _clip_register_depends(draft: dict[str, Any]) -> list[str]:
    """Register residuals only depend on mixins + relations actually used."""
    notes: list[str] = []
    if document_shape_of(draft) != "register":
        return notes
    needed: list[str] = ["base", "mail"]
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            rel = str(field.get("relation") or "")
            if rel == "res.partner" and "contacts" not in needed:
                needed.append("contacts")
            if rel == "hr.employee" and "hr" not in needed:
                needed.append("hr")
            if rel.startswith("pos.") and "point_of_sale" not in needed:
                needed.append("point_of_sale")
        mixins = {str(x) for x in (model.get("mixins") or [])}
        if mixins & {"mail.thread", "mail.activity.mixin"} and "mail" not in needed:
            needed.append("mail")
    before = [str(x) for x in (draft.get("depends") or []) if x]
    after = [d for d in before if d in needed]
    for d in needed:
        if d not in after:
            after.append(d)
    # Stable preferred order
    order = ["base", "mail", "contacts", "hr", "point_of_sale"]
    after = [d for d in order if d in after] + [d for d in after if d not in order]
    if after != before:
        draft["depends"] = after
        notes.append(
            "register: clipped depends → " + ", ".join(after)
        )
    return notes


def _drop_forbidden_host_fields(draft: dict[str, Any], hosts: set[str]) -> list[str]:
    """Strip leftover M2Os / smart buttons that still point at a forbidden stock host."""
    if not hosts:
        return []
    notes: list[str] = []
    drop_by_model: dict[str, set[str]] = {}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        for field in list(model.get("fields") or []):
            if not isinstance(field, dict):
                continue
            rel = str(field.get("relation") or "")
            if rel in hosts:
                drop_by_model.setdefault(mid, set()).add(str(field.get("name") or ""))
    if drop_by_model:
        try:
            from app.ai_odoo_app_bar import _drop_named_fields

            for mid, names in drop_by_model.items():
                names.discard("")
                if names:
                    _drop_named_fields(draft, mid, names)
                    notes.append(
                        f"honesty: dropped {', '.join(sorted(names))} on {mid} (forbidden host)"
                    )
        except Exception:  # noqa: BLE001
            for model in draft.get("models") or []:
                if not isinstance(model, dict):
                    continue
                mid = str(model.get("model") or "")
                doomed = drop_by_model.get(mid) or set()
                if not doomed:
                    continue
                model["fields"] = [
                    f
                    for f in (model.get("fields") or [])
                    if not (isinstance(f, dict) and str(f.get("name") or "") in doomed)
                ]
    buttons = draft.get("smart_buttons")
    if isinstance(buttons, list):
        kept = [
            b
            for b in buttons
            if not (
                isinstance(b, dict)
                and (
                    str(b.get("on_model") or "") in hosts
                    or str(b.get("related_model") or "") in hosts
                )
            )
        ]
        if len(kept) != len(buttons):
            draft["smart_buttons"] = kept
            notes.append("honesty: dropped smart buttons on forbidden hosts")
    return notes


def honor_operator_brief(draft: dict[str, Any], *, user_prompt: str = "") -> list[str]:
    """Drop forbidden hosts/satellites. Closer and Expert must call this first."""
    notes: list[str] = []
    prompt = user_prompt or str(draft.get("_user_prompt") or "")
    try:
        from app.ai_operator_brief import attach_operator_brief

        attach_operator_brief(draft, user_prompt=prompt)
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_document_compiler import compile_document_grammar

        notes.extend(compile_document_grammar(draft, prompt=prompt))
    except Exception:  # noqa: BLE001
        pass
    shape = stamp_document_shape(draft, prompt=prompt)
    hosts = forbidden_stock_hosts(draft)
    removed: set[str] = set()
    keep_register = _register_model_id(draft, prompt) if shape == "register" else ""
    for model in list(draft.get("models") or []):
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        mode = str(model.get("mode") or "new")
        if mode == "inherit" and mid in hosts:
            removed.add(mid)
        if shape in ADDITIVE_BLOCKED and (
            mid.endswith("_party") or mid.endswith("_line")
        ):
            removed.add(mid)
    if shape == "register" and keep_register:
        for model in list(draft.get("models") or []):
            if not isinstance(model, dict):
                continue
            mid = str(model.get("model") or "")
            if mid.startswith("x_") and mid != keep_register:
                removed.add(mid)
    if removed:
        from app.ai_domain_packs import _purge_draft_artifacts_for_models

        try:
            from app.ai_odoo_app_bar import _retarget_removed_relations

            notes.extend(_retarget_removed_relations(draft, removed))
        except Exception:  # noqa: BLE001
            pass
        _purge_draft_artifacts_for_models(draft, removed)
        notes.append("honesty: dropped " + ", ".join(sorted(removed)))
    depends = [str(x) for x in (draft.get("depends") or []) if x]
    brief = draft.get("_operator_brief") if isinstance(draft.get("_operator_brief"), dict) else {}
    forbidden_apps = {str(x).strip().lower() for x in (brief.get("forbidden_bridges") or []) if x}
    dropped_deps = [d for d in depends if d.lower() in forbidden_apps]
    if dropped_deps:
        depends = [d for d in depends if d.lower() not in forbidden_apps]
        notes.append("honesty: dropped " + ", ".join(sorted(set(dropped_deps))) + " from depends")
    draft["depends"] = depends
    notes.extend(_drop_forbidden_host_fields(draft, hosts))
    notes.extend(clip_forbidden_reuse_surfaces(draft))
    try:
        from app.ai_domain_pack_helpdesk import scrub_helpdesk_prompt_fit

        notes.extend(scrub_helpdesk_prompt_fit(draft, prompt=prompt))
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_domain_pack_purchase_request import scrub_purchase_request_prompt_fit

        notes.extend(scrub_purchase_request_prompt_fit(draft, prompt=prompt))
    except Exception:  # noqa: BLE001
        pass
    notes.extend(ensure_residual_must_do_fields(draft, prompt=prompt))
    notes.extend(polish_register_surface(draft, prompt=prompt))
    notes.extend(strip_backend_unsafe_relations(draft))
    notes.extend(normalize_punch_card_fields(draft, prompt=prompt))
    notes.extend(ensure_operator_field_help(draft, prompt=prompt))
    try:
        from app.ai_stock_host_smart_buttons import apply_stock_host_smart_buttons

        notes.extend(apply_stock_host_smart_buttons(draft, prompt=prompt))
    except Exception:  # noqa: BLE001
        pass
    notes.extend(clip_thin_reuse_noise(draft))
    notes.extend(ensure_duration_activity(draft, prompt=prompt))
    try:
        from app.ai_apply_readiness import dedupe_automations_by_signature

        notes.extend(dedupe_automations_by_signature(draft))
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_rules import completeness_checklist

        draft["_completeness"] = completeness_checklist(draft, user_prompt=prompt)
    except Exception:  # noqa: BLE001
        pass
    return notes


def draft_needs_residual_recovery(draft: dict[str, Any], *, prompt: str = "") -> bool:
    """True when Create/Retry should complete residual fields without waiting on Flash."""
    status = draft.get("_llm_status") if isinstance(draft.get("_llm_status"), dict) else {}
    reason = str(status.get("reason") or "")
    mode = str(status.get("mode") or "")
    if reason in {"honesty_seed", "timeout", "unavailable"} or mode == "pack_fallback":
        return True
    text = prompt or str(draft.get("_user_prompt") or "")
    if classify_document_shape(text, draft) != "register":
        return False
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_") or mid.endswith("_line"):
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        names = {str(f.get("name") or "") for f in fields}
        if len(names) <= 1:
            return True
        if _PUNCH_CARD_RESIDUAL_RE.search(text) and "x_partner_id" not in names:
            return True
    return False


def draft_needs_hygiene_repair(draft: dict[str, Any], *, prompt: str = "") -> bool:
    """True when Expert/Retry should collapse Flash hygiene even if Completeness is 10.0.

    Scorecards can be green while the form still has two Customer M2Os or junk depends.
    """
    text = prompt or str(draft.get("_user_prompt") or "")
    try:
        from app.ai_domain_coherence import helpdesk_ticket_intent

        if helpdesk_ticket_intent(text) or str(draft.get("domain_pack") or "") == "helpdesk_tickets":
            depends = {str(d).lower() for d in (draft.get("depends") or [])}
            if depends & {"project", "purchase"}:
                return True
            for model in draft.get("models") or []:
                if not isinstance(model, dict):
                    continue
                mid = str(model.get("model") or "")
                if mid in {"project.task", "project.project", "purchase.order"}:
                    return True
                names = {
                    str(f.get("name") or "")
                    for f in (model.get("fields") or [])
                    if isinstance(f, dict)
                }
                if names & {"x_project_id", "x_purchase_order_id", "x_employee_id"} and (
                    "x_requester_id" in names or mid == "x_ticket"
                ):
                    return True
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_odoo_create_gates import draft_has_unguarded_create_gates

        if draft_has_unguarded_create_gates(draft):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ai_stock_host_smart_buttons import draft_missing_stock_host_smart_buttons

        if draft_missing_stock_host_smart_buttons(draft, prompt=text):
            return True
    except Exception:  # noqa: BLE001
        pass
    if document_shape_of(draft) != "register" and not _PUNCH_CARD_RESIDUAL_RE.search(text):
        return False
    depends = {str(d).lower() for d in (draft.get("depends") or [])}
    junk = depends & {"stock", "purchase", "mrp", "crm", "project"}
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        partner_links = [
            f
            for f in fields
            if f.get("relation") == "res.partner"
        ]
        if len(partner_links) > 1:
            return True
        if any(str(f.get("name") or "") == mid for f in partner_links):
            return True
        names = {str(f.get("name") or "") for f in fields}
        if _PUNCH_CARD_RESIDUAL_RE.search(text):
            if "x_total_punches" in names and "x_punches" in names:
                return True
            if "x_next_free_punch_date" in names:
                return True
            if junk:
                return True
    return bool(junk and _PUNCH_CARD_RESIDUAL_RE.search(text))


def recover_residual_draft(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Production self-serve recovery when Flash/local/cloud is down or timed out.

    Completes register residuals from the operator brief (Contacts, punches, visitor
    columns, …) and syncs form archs. Safe to call on every Retry — does not invent
    hotel/PMS satellites.
    """
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    if text and not draft.get("_user_prompt"):
        draft["_user_prompt"] = text
    notes.extend(honor_operator_brief(draft, user_prompt=text))
    # Ensure depends match stamped M2Os (Retry on hollow seeds often lacks contacts).
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for field in model.get("fields") or []:
            if not isinstance(field, dict):
                continue
            rel = str(field.get("relation") or "")
            depends = [str(x) for x in (draft.get("depends") or []) if x]
            if rel == "res.partner" and "contacts" not in depends:
                depends.append("contacts")
                draft["depends"] = depends
                notes.append("recover: added contacts depend for Customer link")
            if rel == "hr.employee" and "hr" not in depends:
                depends.append("hr")
                draft["depends"] = depends
                notes.append("recover: added hr depend for Employee link")
    try:
        from app.ai_enrich import sync_form_archs_to_models

        notes.extend(sync_form_archs_to_models(draft))
    except Exception:  # noqa: BLE001
        pass
    if any("register:" in n or "document_shape:" in n or "recover:" in n for n in notes):
        notes.append(
            "recover: residual completed from operator brief "
            "(works when Flash, local Ollama, or cloud API is down)"
        )
    return notes


_STATUS_PROMPT_RE = re.compile(
    r"(?i)\b(status|stage|kanban|signed in|signed out|check[- ]?in|check[- ]?out)\b"
)
_CODE_PROMPT_RE = re.compile(r"(?i)\b(reference code|entry code|sequence|x_code)\b")
_NOTES_PROMPT_RE = re.compile(r"(?i)\b(notes?|comments?|remarks?)\b")
_CHECKIN_LABEL_RE = re.compile(r"(?i)check[\s-]?in|check[\s-]?out")
_CHECKIN_PROMPT_RE = re.compile(r"(?i)\bcheck[\s-]?in\b|\bcheck[\s-]?out\b")
_REF_NAME_RE = re.compile(r"(?i)\b(reference|sequence|entry\s+code|log\s+entry)\b")
_REGISTER_NAME_LEAVES = frozenset(
    {"log", "book", "register", "ledger", "checklist", "guestbook"}
)


def _register_identity_label(prompt: str) -> str:
    """x_name on a register is the residual's name, not a sequence code."""
    _display, slug = naming_from_residual(prompt)
    parts = [p for p in (slug or "").split("_") if p]
    if parts and parts[-1] in _REGISTER_NAME_LEAVES:
        head = " ".join(parts[:-1]).strip()
        if head:
            return f"{head.replace('_', ' ').title()} Name"
    return "Name"


_ACRONYM_FIELD_WORDS = {"id": "ID", "qr": "QR", "sla": "SLA"}


def _title_register_field_string(raw: str) -> str:
    """Title-case all-lowercase identity labels (column-list leftovers), keep ID/QR/SLA."""
    text = str(raw or "").strip()
    if not text or any(ch.isupper() for ch in text):
        return text
    parts: list[str] = []
    for word in text.split():
        key = word.lower()
        if key in _ACRONYM_FIELD_WORDS:
            parts.append(_ACRONYM_FIELD_WORDS[key])
        else:
            parts.append(word[:1].upper() + word[1:].lower() if word else word)
    return " ".join(parts)


def _selection_grounded_in_prompt(field: dict[str, Any], prompt: str) -> bool:
    from app.ai_selection import parse_selection_literal

    blob = (prompt or "").lower()
    pairs = parse_selection_literal(field.get("selection")) or []
    for key, label in pairs:
        lab = str(label or "").strip().lower()
        if len(lab) >= 4 and lab in blob:
            return True
        key_s = str(key or "").strip().lower()
        if len(key_s) >= 4 and re.search(rf"\b{re.escape(key_s)}\b", blob):
            return True
    return False


def polish_register_surface(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """A register is a paper book: no document workflow, kanban, sequence codes, or Contacts back-ref."""
    notes: list[str] = []
    text = prompt or str(draft.get("_user_prompt") or "")
    shape = stamp_document_shape(draft, prompt=text)
    if shape != "register":
        return notes
    keep_status = bool(_STATUS_PROMPT_RE.search(text))
    keep_code = bool(_CODE_PROMPT_RE.search(text))
    keep_notes = bool(_NOTES_PROMPT_RE.search(text))
    keep_checkin_vocab = bool(_CHECKIN_PROMPT_RE.search(text))
    from app.multi_company_pack import prompt_asks_multi_company, strip_multi_company_record_rules

    keep_company = prompt_asks_multi_company(text)
    header_id = _register_model_id(draft, text)
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if header_id and mid != header_id:
            continue
        if not mid.startswith("x_"):
            continue
        if model.get("is_workflow") or model.get("state_field"):
            model["is_workflow"] = False
            model.pop("state_field", None)
            notes.append(f"register: demoted workflow on {mid}")
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        dropped: list[str] = []
        kept: list[dict[str, Any]] = []
        for field in fields:
            name = str(field.get("name") or "")
            if name == "x_status" and not keep_status:
                dropped.append(name)
                continue
            if name in {"x_code", "x_reference"} and not keep_code:
                dropped.append(name)
                continue
            if name == "x_notes" and not keep_notes:
                dropped.append(name)
                continue
            if name in {"x_company_id", "company_id"} and not keep_company:
                # Multi-company only — never drop Contact/Company M2Os (relation res.partner).
                rel = str(field.get("relation") or "")
                if rel in {"", "res.company"}:
                    dropped.append(name)
                    continue
            if name == "x_name" and _REF_NAME_RE.search(str(field.get("string") or "")):
                field["string"] = _register_identity_label(text)
                notes.append(f"register: x_name is identity, not a sequence on {mid}")
            if not keep_checkin_vocab and _CHECKIN_LABEL_RE.search(str(field.get("string") or "")):
                if name in {"x_time_in", "x_check_in"}:
                    field["string"] = "Time In"
                    notes.append(f"register: {name} is time in, not hotel check-in")
                elif name in {"x_time_out", "x_check_out"}:
                    field["string"] = "Time Out"
                    notes.append(f"register: {name} is time out, not hotel check-out")
            titled = _title_register_field_string(str(field.get("string") or ""))
            if titled and titled != str(field.get("string") or ""):
                field["string"] = titled
                notes.append(f"register: titled field string {name}")
            if (
                str(field.get("ttype") or "") == "selection"
                and name != "x_status"
                and not _selection_grounded_in_prompt(field, text)
            ):
                field["ttype"] = "char"
                field.pop("selection", None)
                notes.append(f"register: {name} is free text (prompt did not enumerate values)")
            kept.append(field)
        # Hollow honesty seeds (x_name only) — stamp Must-do / punch-card columns from the brief.
        have = {str(f.get("name") or "") for f in kept}
        if len(have) <= 1:
            try:
                from app.ai_field_ir import fields_from_residual_brief

                for row in fields_from_residual_brief(text):
                    name = str(row.get("name") or "")
                    if name and name not in have:
                        kept.append(row)
                        have.add(name)
                        notes.append(f"register: stamped must-do field {name}")
            except Exception:  # noqa: BLE001
                pass
        if _PUNCH_CARD_RESIDUAL_RE.search(text):
            for row in _fields_from_punch_card_brief(text):
                name = str(row.get("name") or "")
                if name and name not in have:
                    kept.append(row)
                    have.add(name)
                    notes.append(f"register: stamped punch-card field {name}")
        model["fields"] = kept
        if dropped:
            notes.append(f"register: dropped {', '.join(dropped)} on {mid}")
    if not keep_status:
        views = [
            v
            for v in (draft.get("views") or [])
            if not (
                isinstance(v, dict)
                and str(v.get("type") or "") == "kanban"
                and str(v.get("model") or "") == header_id
            )
        ]
        if len(views) != len(draft.get("views") or []):
            draft["views"] = views
            notes.append("register: dropped kanban (paper book is list+form)")
        for action in draft.get("actions") or []:
            if not isinstance(action, dict):
                continue
            if str(action.get("model") or "") != header_id:
                continue
            mode = str(action.get("view_mode") or "")
            if "kanban" in mode:
                parts = [p for p in mode.split(",") if p.strip() and p.strip() != "kanban"]
                action["view_mode"] = ",".join(parts) or "list,form"
                notes.append("register: action view_mode without kanban")
        for view in draft.get("views") or []:
            if not isinstance(view, dict) or str(view.get("type") or "") != "form":
                continue
            if str(view.get("model") or "") != header_id:
                continue
            arch = str(view.get("arch") or "")
            new_arch, n = re.subn(r"<header>.*?</header>", "", arch, count=1, flags=re.I | re.S)
            if n and new_arch != arch:
                view["arch"] = new_arch
                notes.append("register: stripped form header chrome")
    btns = list(draft.get("smart_buttons") or [])
    # Stock-host button policy (Contacts / Employees / related docs) — not visitor Contacts.
    try:
        from app.ai_stock_host_smart_buttons import apply_stock_host_smart_buttons

        notes.extend(apply_stock_host_smart_buttons(draft, prompt=text))
    except Exception:  # noqa: BLE001
        # Fallback: legacy punch-only Contacts restore.
        keep_partner_btn = bool(
            _PUNCH_CARD_RESIDUAL_RE.search(text) or _TIED_TO_CUSTOMER_RE.search(text)
        )
        if not keep_partner_btn:
            filtered = [
                b
                for b in btns
                if not (
                    isinstance(b, dict) and str(b.get("on_model") or "") == "res.partner"
                )
            ]
            if len(filtered) != len(btns):
                draft["smart_buttons"] = filtered
                notes.append("register: dropped Contacts smart button")
        elif header_id and not any(
            isinstance(b, dict)
            and str(b.get("on_model") or "") == "res.partner"
            and str(b.get("related_model") or "") == header_id
            for b in btns
        ):
            has_partner = any(
                isinstance(f, dict)
                and str(f.get("name") or "") == "x_partner_id"
                for m in (draft.get("models") or [])
                if isinstance(m, dict) and str(m.get("model") or "") == header_id
                for f in (m.get("fields") or [])
            )
            if has_partner:
                display = str(draft.get("display_name") or "Punch Cards")
                draft.setdefault("smart_buttons", []).append(
                    {
                        "on_model": "res.partner",
                        "label": display,
                        "related_model": header_id,
                        "relation_field": "x_partner_id",
                        "icon": "fa-ticket",
                        "requires_inherit_view": True,
                        "note": "Applied as inherit on Contacts button_box",
                    }
                )
                notes.append("register: restored Contacts smart button for punch card")
    notes.extend(align_root_menu_to_residual(draft, prompt=text))
    try:
        from app.ai_apply_readiness import scrub_unknown_arch_field_refs

        notes.extend(scrub_unknown_arch_field_refs(draft))
    except Exception:  # noqa: BLE001
        pass
    seqs = [
        s
        for s in (draft.get("sequences") or [])
        if not (
            isinstance(s, dict)
            and str(s.get("model") or "") == header_id
            and not keep_code
        )
    ]
    if len(seqs) != len(draft.get("sequences") or []):
        draft["sequences"] = seqs
        notes.append("register: dropped ir.sequence (not in brief)")
    notes.extend(
        _align_register_residual_labels(draft, prompt=text, header_id=header_id)
    )
    if not keep_company:
        notes.extend(strip_multi_company_record_rules(draft))
        if draft.get("multi_company"):
            draft["multi_company"] = False
            notes.append("register: multi-company is unknown — no x_company_id")
    return notes


def _align_register_residual_labels(
    draft: dict[str, Any],
    *,
    prompt: str,
    header_id: str,
) -> list[str]:
    """ACL/description follow the residual. Brief columns keep their required flags."""
    notes: list[str] = []
    display = str(draft.get("display_name") or "").strip()
    brief_rows = _fields_from_column_list(prompt)
    if len(brief_rows) <= 1:
        try:
            from app.ai_field_ir import fields_from_residual_brief

            must = fields_from_residual_brief(prompt)
            if len(must) > len(brief_rows):
                brief_rows = must
        except Exception:  # noqa: BLE001
            pass
    brief_by_name = {
        str(row.get("name") or ""): row
        for row in brief_rows
        if isinstance(row, dict) and row.get("name")
    }
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if header_id and mid != header_id:
            continue
        if not mid.startswith("x_"):
            continue
        if display and str(model.get("description") or "") != display:
            model["description"] = display
            notes.append(f"register: description is residual {display!r}")
        fields = [f for f in (model.get("fields") or []) if isinstance(f, dict)]
        have = {str(f.get("name") or "") for f in fields}
        for name, src in brief_by_name.items():
            if name == "x_partner_id":
                continue
            if name in have:
                for field in fields:
                    if str(field.get("name") or "") != name:
                        continue
                    want = bool(src.get("required"))
                    if bool(field.get("required")) != want:
                        field["required"] = want
                        notes.append(f"register: required {name}={want} from brief")
                    break
            else:
                fields.append(dict(src))
                have.add(name)
                notes.append(f"register: added {name} from brief")
        model["fields"] = fields
    if display:
        xml = "model_" + header_id.replace(".", "_")
        for rule in draft.get("access_rules") or []:
            if not isinstance(rule, dict):
                continue
            if str(rule.get("model") or "") not in {xml, header_id}:
                continue
            rid = str(rule.get("id") or "")
            rname = str(rule.get("name") or "").lower()
            if rid.endswith("_manager") or rname.endswith(" manager"):
                role = "manager"
            elif rid.endswith("_user") or rname.endswith(" user"):
                role = "user"
            else:
                continue
            want = f"{display} {role}"
            if str(rule.get("name") or "") != want:
                rule["name"] = want
                notes.append(f"register: access name → {want}")
    return notes


def align_root_menu_to_residual(draft: dict[str, Any], *, prompt: str = "") -> list[str]:
    """Root xml_id follows residual slug, not the first eight prompt words."""
    notes: list[str] = []
    display, slug = naming_from_residual(prompt or str(draft.get("_user_prompt") or ""))
    if not slug:
        return notes
    tech = slug[2:] if slug.startswith("x_") else slug
    if draft.get("technical_name") != tech:
        draft["technical_name"] = tech
    if display:
        draft["display_name"] = display
    want_xml = f"menu_root_{tech}"
    want_tech = f"root_{tech}"
    for menu in draft.get("menus") or []:
        if not isinstance(menu, dict):
            continue
        is_root = not menu.get("parent_xml_id") and not menu.get("action_xml_id")
        old_xml = str(menu.get("xml_id") or "")
        if is_root:
            if display:
                menu["name"] = display
            if old_xml != want_xml:
                menu["xml_id"] = want_xml
                menu["technical_name"] = want_tech
                notes.append(f"register: root menu xml_id → {want_xml}")
            for child in draft.get("menus") or []:
                if isinstance(child, dict) and child.get("parent_xml_id") == old_xml:
                    child["parent_xml_id"] = want_xml
    return notes


def clip_forbidden_reuse_surfaces(draft: dict[str, Any]) -> list[str]:
    """account.move / crm.* stay off plan hosts, hints, and catalog when forbidden."""
    notes: list[str] = []
    brief = draft.get("_operator_brief") if isinstance(draft.get("_operator_brief"), dict) else {}
    forbidden_apps = {str(x).strip().lower() for x in (brief.get("forbidden_bridges") or []) if x}
    skip_models: set[str] = set()
    if "crm" in forbidden_apps:
        skip_models.update({"crm.lead", "crm.team", "crm.tag"})
    if "account" in forbidden_apps:
        skip_models.update({"account.move", "account.move.line", "account.payment"})
    if "sale" in forbidden_apps:
        skip_models.update({"sale.order", "sale.order.line"})
    if "project" in forbidden_apps:
        skip_models.update({"project.task", "project.project"})
    if "purchase" in forbidden_apps:
        skip_models.update({"purchase.order", "purchase.order.line"})
    if not skip_models:
        return notes

    def _keep_model(mid: str) -> bool:
        return str(mid or "") not in skip_models

    reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    if reuse:
        before = list(reuse.get("models") or [])
        reuse["models"] = [m for m in before if _keep_model(str(m))]
        plan = reuse.get("plan") if isinstance(reuse.get("plan"), dict) else {}
        if plan:
            plan["models"] = [m for m in (plan.get("models") or []) if _keep_model(str(m))]
            plan["depends"] = [
                d
                for d in (plan.get("depends") or [])
                if str(d).lower() not in forbidden_apps
            ]
            plan["decisions"] = [
                d
                for d in (plan.get("decisions") or [])
                if isinstance(d, dict) and _keep_model(str(d.get("model") or ""))
            ]
            reuse["plan"] = plan
        sugg = [
            row
            for row in (reuse.get("catalog_suggestions") or [])
            if isinstance(row, dict)
            and _keep_model(str(row.get("model") or ""))
            and not (
                set(str(m).lower() for m in (row.get("modules") or [])) & forbidden_apps
            )
        ]
        if sugg != list(reuse.get("catalog_suggestions") or []):
            reuse["catalog_suggestions"] = sugg
        draft["reuse"] = reuse
        if before != reuse.get("models"):
            notes.append("honesty: clipped forbidden hosts from reuse")
    hints = [
        h
        for h in (draft.get("reuse_hints") or [])
        if isinstance(h, dict) and _keep_model(str(h.get("model") or ""))
    ]
    if len(hints) != len(draft.get("reuse_hints") or []):
        draft["reuse_hints"] = hints
        notes.append("honesty: clipped forbidden reuse_hints")
    arch = draft.get("_architecture_plan") if isinstance(draft.get("_architecture_plan"), dict) else {}
    if arch:
        hosts = [h for h in (arch.get("stock_hosts") or []) if _keep_model(str(h))]
        if hosts != list(arch.get("stock_hosts") or []):
            arch["stock_hosts"] = hosts
            draft["_architecture_plan"] = arch
            notes.append("honesty: clipped forbidden architecture hosts")
    depends = [d for d in (draft.get("depends") or []) if str(d).lower() not in forbidden_apps]
    if depends != list(draft.get("depends") or []):
        draft["depends"] = depends
    return notes


_NAMED_APP_HOSTS = {
    "hr": ("hr.employee",),
    "contacts": ("res.partner",),
    "mail": (),
}


def clip_thin_reuse_noise(draft: dict[str, Any]) -> list[str]:
    """Registers do not inherit unused CE19 hosts (currency/company/users) or catalog spam."""
    notes: list[str] = []
    if document_shape_of(draft) not in THIN_SHAPES:
        return notes
    used: set[str] = set()
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        for field in model.get("fields") or []:
            if isinstance(field, dict) and field.get("relation"):
                used.add(str(field["relation"]))
    brief = draft.get("_operator_brief") if isinstance(draft.get("_operator_brief"), dict) else {}
    keep = set(used)
    for app in brief.get("stock_reuse") or []:
        keep.update(_NAMED_APP_HOSTS.get(str(app).strip().lower(), ()))
    if not keep and not used:
        return notes

    def _keep(mid: str) -> bool:
        return str(mid or "") in keep

    reuse = draft.get("reuse") if isinstance(draft.get("reuse"), dict) else {}
    if reuse:
        before = list(reuse.get("models") or [])
        reuse["models"] = [m for m in before if _keep(str(m))]
        plan = reuse.get("plan") if isinstance(reuse.get("plan"), dict) else {}
        if plan:
            plan["models"] = [m for m in (plan.get("models") or []) if _keep(str(m))]
            plan["decisions"] = [
                d
                for d in (plan.get("decisions") or [])
                if isinstance(d, dict) and _keep(str(d.get("model") or ""))
            ]
            reuse["plan"] = plan
        sugg = [
            row
            for row in (reuse.get("catalog_suggestions") or [])
            if isinstance(row, dict) and _keep(str(row.get("model") or ""))
        ]
        if sugg != list(reuse.get("catalog_suggestions") or []):
            reuse["catalog_suggestions"] = sugg
        draft["reuse"] = reuse
        if before != reuse.get("models"):
            notes.append("honesty: clipped unused stock hosts from register reuse")
    hints = [
        h
        for h in (draft.get("reuse_hints") or [])
        if isinstance(h, dict) and _keep(str(h.get("model") or ""))
    ]
    if len(hints) != len(draft.get("reuse_hints") or []):
        draft["reuse_hints"] = hints
    arch = draft.get("_architecture_plan") if isinstance(draft.get("_architecture_plan"), dict) else {}
    if arch:
        hosts = [h for h in (arch.get("stock_hosts") or []) if _keep(str(h))]
        if hosts != list(arch.get("stock_hosts") or []):
            arch["stock_hosts"] = hosts
            draft["_architecture_plan"] = arch
    return notes


def clip_llm_models_to_plan(
    draft: dict[str, Any],
    plan: dict[str, Any] | None = None,
) -> list[str]:
    """Drop x_* the architecture plan did not lock. Extra models are invalid."""
    notes: list[str] = []
    plan = plan or (
        draft.get("_architecture_plan")
        if isinstance(draft.get("_architecture_plan"), dict)
        else {}
    )
    allowed = {
        str(x).strip()
        for x in (plan.get("new_x_models") or [])
        if str(x).strip()
    }
    budget = (plan.get("surface_budget") or {}).get("new_models") if isinstance(plan.get("surface_budget"), dict) else None
    shape = str(plan.get("document_shape") or draft.get("_document_shape") or "")
    if shape in ADDITIVE_BLOCKED and not allowed:
        allowed = {
            str(m.get("model"))
            for m in (draft.get("models") or [])
            if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
        }
    if not allowed and budget == 0:
        extra = [
            str(m.get("model"))
            for m in (draft.get("models") or [])
            if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
        ]
        if extra:
            from app.ai_domain_packs import _purge_draft_artifacts_for_models

            _purge_draft_artifacts_for_models(draft, set(extra))
            notes.append("plan: dropped x_* on zero-budget shape")
        return notes
    if not allowed:
        return notes
    extra = [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and str(m.get("mode") or "new") != "inherit"
        and str(m.get("model")) not in allowed
    ]
    if extra:
        from app.ai_domain_packs import _purge_draft_artifacts_for_models

        _purge_draft_artifacts_for_models(draft, set(extra))
        notes.append("plan: dropped models outside lock " + ", ".join(extra))
    return notes


def clip_missing_models_to_budget(
    draft: dict[str, Any],
    missing: list[Any],
) -> list[dict[str, Any]]:
    """Critique missing_models that expand past budget are dropped, not applied."""
    plan = draft.get("_architecture_plan") if isinstance(draft.get("_architecture_plan"), dict) else {}
    shape = str(plan.get("document_shape") or draft.get("_document_shape") or "")
    if shape in ADDITIVE_BLOCKED:
        return []
    allowed = {
        str(x).strip()
        for x in (plan.get("new_x_models") or [])
        if str(x).strip()
    }
    budget = None
    raw_budget = plan.get("surface_budget") if isinstance(plan.get("surface_budget"), dict) else {}
    if raw_budget.get("new_models") is not None:
        try:
            budget = int(raw_budget["new_models"])
        except (TypeError, ValueError):
            budget = None
    have = {
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
    }
    out: list[dict[str, Any]] = []
    for row in missing:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("model") or "")
        if not mid.startswith("x_"):
            continue
        if allowed and mid not in allowed:
            continue
        if budget is not None and len(have) + len(out) >= budget:
            continue
        out.append(row)
    return out


def llm_models_outside_plan(draft: dict[str, Any], plan: dict[str, Any] | None = None) -> list[str]:
    plan = plan or {}
    allowed = {str(x) for x in (plan.get("new_x_models") or []) if x}
    if not allowed:
        return []
    return [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict)
        and str(m.get("model") or "").startswith("x_")
        and str(m.get("mode") or "new") != "inherit"
        and str(m.get("model")) not in allowed
    ]


def merge_llm_fields_into_locked(
    seed: dict[str, Any],
    llm_draft: dict[str, Any],
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep locked models; copy fields/views/automations from Flash onto them."""
    out = dict(seed)
    allowed = {
        str(x)
        for x in ((plan or {}).get("new_x_models") or [])
        if x
    }
    if not allowed:
        allowed = {
            str(m.get("model"))
            for m in (seed.get("models") or [])
            if isinstance(m, dict) and str(m.get("model") or "").startswith("x_")
        }
    by_id = {
        str(m.get("model")): m
        for m in (out.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    for row in llm_draft.get("models") or []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("model") or "")
        if mid not in allowed or mid not in by_id:
            continue
        existing = by_id[mid]
        have = {
            str(f.get("name"))
            for f in (existing.get("fields") or [])
            if isinstance(f, dict)
        }
        for field in row.get("fields") or []:
            if not isinstance(field, dict) or not field.get("name"):
                continue
            if str(field["name"]) in have:
                continue
            existing.setdefault("fields", []).append(field)
            have.add(str(field["name"]))
    for key in ("views", "menus", "access_rules"):
        llm_rows = llm_draft.get(key)
        if isinstance(llm_rows, list) and llm_rows and not out.get(key):
            out[key] = [
                row
                for row in llm_rows
                if isinstance(row, dict)
                and (
                    not row.get("model")
                    or str(row.get("model")) in allowed
                    or not str(row.get("model") or "").startswith("x_")
                )
            ]
    llm_autos = llm_draft.get("automations")
    if isinstance(llm_autos, list):
        existing_names = {
            str(a.get("name"))
            for a in (out.get("automations") or [])
            if isinstance(a, dict)
        }
        existing_sigs = {
            (
                str(a.get("model") or ""),
                str(a.get("trigger") or ""),
                re.sub(r"\s+", "", str(a.get("filter_domain") or "")),
                str(a.get("trg_date_field_name") or ""),
            )
            for a in (out.get("automations") or [])
            if isinstance(a, dict)
        }
        for row in llm_autos:
            if not isinstance(row, dict):
                continue
            if str(row.get("name") or "") in existing_names:
                continue
            sig = (
                str(row.get("model") or ""),
                str(row.get("trigger") or ""),
                re.sub(r"\s+", "", str(row.get("filter_domain") or "")),
                str(row.get("trg_date_field_name") or ""),
            )
            if sig[0] and sig[1] and sig in existing_sigs:
                continue
            model = str(row.get("model") or "")
            if model in allowed or not model.startswith("x_"):
                out.setdefault("automations", []).append(row)
                existing_names.add(str(row.get("name") or ""))
                existing_sigs.add(sig)
    return out


def _named_residual(prompt: str) -> tuple[str, str]:
    try:
        from app.ai_operator_brief import stated_residual_kind

        return stated_residual_kind(prompt)
    except Exception:  # noqa: BLE001
        return "unstated", ""


def _register_model_id(draft: dict[str, Any], prompt: str) -> str:
    _disp, slug = naming_from_residual(prompt)
    if slug:
        return f"x_{slug}" if not slug.startswith("x_") else slug
    for m in draft.get("models") or []:
        if isinstance(m, dict) and str(m.get("model") or "").startswith("x_"):
            mid = str(m["model"])
            if not mid.endswith("_line") and not mid.endswith("_party"):
                return mid
    return "x_register"


def _fields_from_punch_card_brief(text: str) -> list[dict[str, Any]]:
    """Loyalty punch card residual — customer + remaining punches (no receipt/POS clone)."""
    fields: list[dict[str, Any]] = [
        {
            "name": "x_name",
            "ttype": "char",
            "string": "Name",
            "required": True,
        },
        {
            "name": "x_partner_id",
            "ttype": "many2one",
            "relation": "res.partner",
            "string": "Customer",
            "required": True,
            "help": "Loyalty card is tied to Contacts — do not invent x_customer.",
        },
        {
            "name": "x_punches",
            "ttype": "integer",
            "string": "Punches",
            "required": False,
            "default": 0,
        },
        {
            "name": "x_remaining_punches",
            "ttype": "integer",
            "string": "Remaining punches",
            "required": False,
            "help": "Cashier-visible remaining punches on the POS-adjacent back office.",
        },
        {
            "name": "x_next_free",
            "ttype": "boolean",
            "string": "Next free",
            "required": False,
        },
    ]
    buy = _BUY_N_FREE_RE.search(text or "")
    if buy:
        need = int(buy.group(1))
        fields.append(
            {
                "name": "x_punches_for_reward",
                "ttype": "integer",
                "string": "Punches for free",
                "required": False,
                "default": need,
                "help": f"Buy {need} get the next free (from the brief).",
            }
        )
    return fields


def _fields_from_column_list(text: str) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    names: set[str] = set()

    def add(row: dict[str, Any]) -> None:
        name = str(row.get("name") or "")
        if not name or name in names:
            return
        names.add(name)
        fields.append(row)

    blob = ""
    listed = _COLUMN_LIST_RE.search(text or "")
    if listed:
        blob = listed.group(1)
    chunks = [c.strip(" .") for c in re.split(r",", blob) if c.strip()] if blob else []
    if not chunks:
        if _PUNCH_CARD_RESIDUAL_RE.search(text or ""):
            return _fields_from_punch_card_brief(text or "")
        add({"name": "x_name", "ttype": "char", "string": "Name", "required": True})
        return fields

    for chunk in chunks:
        low = chunk.lower()
        optional = "optional" in low
        if "employee" in low or ("host" in low and "name" not in low):
            add(
                {
                    "name": "x_employee_id",
                    "ttype": "many2one",
                    "relation": "hr.employee",
                    "string": "Employee",
                    "required": not optional,
                }
            )
            continue
        if re.search(r"time\s+in|check[- ]?in", low):
            add(
                {
                    "name": "x_time_in",
                    "ttype": "datetime",
                    "string": "Time in",
                    "required": not optional,
                }
            )
            continue
        if re.search(r"time\s+out|check[- ]?out", low):
            add({"name": "x_time_out", "ttype": "datetime", "string": "Time out"})
            continue
        if "purpose" in low:
            add(
                {
                    "name": "x_purpose",
                    "ttype": "char",
                    "string": "Purpose",
                    "required": not optional,
                }
            )
            continue
        if re.search(r"\bid\b|id number", low):
            add(
                {
                    "name": "x_id_number",
                    "ttype": "char",
                    "string": "ID number",
                    "required": False,
                }
            )
            continue
        if "name" in low:
            label = re.sub(r"(?i)\boptional\b", "", chunk).strip(" .")
            add(
                {
                    "name": "x_name",
                    "ttype": "char",
                    "string": (label[:40].strip() or "Name"),
                    "required": not optional,
                }
            )
            continue
        # Temporal leftovers (Visit date / Due date / Check-in time) — root classifier.
        try:
            from app.ai_field_ir import field_spec, human_field_label, infer_date_or_datetime

            label = human_field_label(re.sub(r"(?i)\boptional\b", "", chunk))
            temporal = infer_date_or_datetime(label) if label else None
            if temporal and label:
                spec = field_spec(label, ttype=temporal)
                if spec:
                    if optional:
                        spec = {**spec, "required": False}
                    add(spec)
                    continue
        except Exception:  # noqa: BLE001
            pass
    if "x_name" not in names:
        fields.insert(
            0,
            {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
        )
        names.add("x_name")
    if re.search(
        r"(?i)(already|existing|optional).{0,48}contact|unless.{0,32}contact",
        text or "",
    ):
        add(
            {
                "name": "x_partner_id",
                "ttype": "many2one",
                "relation": "res.partner",
                "string": "Contact",
                "required": False,
            }
        )
    if _PUNCH_CARD_RESIDUAL_RE.search(text or ""):
        for row in _fields_from_punch_card_brief(text or ""):
            add(row)
    return fields


__all__ = [
    "ADDITIVE_BLOCKED",
    "DocumentShape",
    "SHAPE_DEPTH_FLOORS",
    "THIN_SHAPES",
    "additive_model_growth_blocked",
    "allowed_bridge_modules",
    "classify_document_shape",
    "clip_forbidden_reuse_surfaces",
    "clip_thin_reuse_noise",
    "clip_llm_models_to_plan",
    "clip_missing_models_to_budget",
    "document_shape_of",
    "ensure_duration_activity",
    "forbidden_stock_hosts",
    "honor_operator_brief",
    "llm_models_outside_plan",
    "may_add_line_satellite",
    "may_add_party_satellite",
    "merge_llm_fields_into_locked",
    "naming_from_residual",
    "polish_register_surface",
    "normalize_punch_card_fields",
    "strip_backend_unsafe_relations",
    "ensure_operator_field_help",
    "ensure_residual_must_do_fields",
    "recover_residual_draft",
    "draft_needs_residual_recovery",
    "draft_needs_hygiene_repair",
    "seed_register_from_brief",
    "shape_budget",
    "stamp_document_shape",
]
