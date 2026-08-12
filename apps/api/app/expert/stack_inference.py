"""Infer Odoo Community module stacks for setup questions without a curated playbook."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.expert.vertical_catalog import VerticalEntry, catalog_by_id, match_verticals

_SETUP_QUESTION_RE = re.compile(
    r"(?i)\b("
    r"what do i need|what do we need|what should i install|which modules|which apps|"
    r"what modules|what apps|modules do i need|apps do i need|module stack|"
    r"setup|set up|build an odoo|build a odoo|odoo db for|database for|"
    r"internal management|operations odoo"
    r")\b"
)

_BASE_MODULES: tuple[str, ...] = ("base", "web", "mail", "contacts")

_MODULE_SIGNALS: tuple[tuple[re.Pattern[str], str, int], ...] = (
    (re.compile(r"(?i)\b(maintenance|cmms|preventive|breakdown|work order|asset integrity)\b"), "maintenance", 12),
    (re.compile(r"(?i)\b(inventory|warehouse|spare part|mro|stock|consumable|parts)\b"), "stock", 11),
    (re.compile(r"(?i)\b(purchase|procurement|vendor|rfq|supplier)\b"), "purchase", 10),
    (re.compile(r"(?i)\b(project|turnaround|shutdown|engineering job|milestone)\b"), "project", 10),
    (re.compile(r"(?i)\b(manufactur|mrp|production|bom|assembly|factory)\b"), "mrp", 11),
    (re.compile(r"(?i)\b(fleet|vehicle|truck|dispatch)\b"), "fleet", 9),
    (re.compile(r"(?i)\b(hr|employee|crew|payroll stub|timesheet)\b"), "hr", 8),
    (re.compile(r"(?i)\b(timesheet|time entry)\b"), "hr_timesheet", 9),
    (re.compile(r"(?i)\b(sale|quote|order|invoic|billing|revenue)\b"), "sale", 8),
    (re.compile(r"(?i)\b(account|accounting|finance|cost center|analytic)\b"), "account", 9),
    (re.compile(r"(?i)\b(product|sku|catalog)\b"), "product", 7),
    (re.compile(r"(?i)\b(crm|lead|pipeline|opportunity)\b"), "crm", 6),
    (re.compile(r"(?i)\b(website|portal|public|ecommerce|webshop)\b"), "website", 5),
    (re.compile(r"(?i)\b(pos|point of sale|retail shop)\b"), "point_of_sale", 7),
    (re.compile(r"(?i)\b(event|ticket|registration)\b"), "event", 5),
    (re.compile(r"(?i)\b(calendar|scheduling|appointment)\b"), "calendar", 6),
    (re.compile(r"(?i)\b(mining|oil|gas|petroleum|refinery|pipeline|well site|field ops)\b"), "maintenance", 8),
    (re.compile(r"(?i)\b(mining|oil|gas|petroleum|refinery|pipeline|well site|field ops)\b"), "project", 6),
    (re.compile(r"(?i)\b(delivery|logistics|shipping|carrier|3pl)\b"), "delivery", 8),
    (re.compile(r"(?i)\b(quality|inspection|qc)\b"), "quality", 6),
)

_INDUSTRY_LABEL_RE = re.compile(
    r"(?i)(?:for\s+(?:a|an|my)\s+|setup\s+(?:a|an)\s+)?"
    r"([a-z][a-z0-9\s&/-]{3,60}?)(?:\s+company|\s+operations|\s+odoo|\s+db|\s+database|$)"
)


@dataclass(frozen=True)
class InferredStack:
    domain_label: str
    model_prefix: str
    stock_modules: tuple[str, ...]
    custom_models: tuple[str, ...]
    reuse_stock: tuple[str, ...]
    phase_1: str
    phase_2: str
    phase_3: str
    honesty: tuple[str, ...]
    source: str
    catalog_id: str | None = None
    pack_id: str | None = None
    playbook_title: str | None = None


def is_setup_stack_question(question: str) -> bool:
    return bool(_SETUP_QUESTION_RE.search(question or ""))


def _domain_label_from_question(question: str) -> str:
    m = _INDUSTRY_LABEL_RE.search(question or "")
    if m:
        label = re.sub(r"\s+", " ", m.group(1)).strip(" .,-")
        if len(label) >= 4:
            return label.title()
    return "your operations"


def _catalog_model_prefix(entry: VerticalEntry) -> str | None:
    for kw in entry.keywords:
        if kw.startswith("x_") and "_" in kw[2:]:
            return f"x_{kw.split('_')[1]}"
    return None


def _catalog_custom_models(entry: VerticalEntry, prefix: str, mod_set: set[str]) -> tuple[str, ...]:
    models = tuple(kw for kw in entry.keywords if kw.startswith("x_") and "." not in kw)
    if models:
        return models[:8]
    return _suggest_custom_models(prefix, mod_set, entry.title)


def _model_prefix(question: str, *, pack_id: str | None = None) -> str:
    if pack_id:
        slug = pack_id.split("_")[0][:8]
        return f"x_{slug}"
    q = (question or "").lower()
    if re.search(r"\b(oil|gas|petroleum)\b", q):
        return "x_og"
    if re.search(r"\b(mining|mineral)\b", q):
        return "x_min"
    if re.search(r"\b(agri|farm|crop)\b", q):
        return "x_ag"
    tokens = [
        t
        for t in re.findall(r"[a-z]{4,}", q)
        if t
        not in {
            "odoo",
            "what",
            "need",
            "setup",
            "build",
            "database",
            "company",
            "internal",
            "management",
            "operations",
        }
    ]
    if tokens:
        return f"x_{tokens[0][:10]}"
    return "x_ops"


def _suggest_custom_models(prefix: str, modules: set[str], question: str) -> tuple[str, ...]:
    q = question.lower()
    base = prefix if prefix.startswith("x_") else f"x_{prefix}"
    base = base.rstrip("_")
    models: list[str] = []
    if "maintenance" in modules or re.search(r"\b(asset|equipment|facility|well|plant|pipeline)\b", q):
        models.extend([f"{base}_facility", f"{base}_asset", f"{base}_work_order"])
    elif re.search(r"\b(facility|site|branch|location)\b", q):
        models.append(f"{base}_facility")
    if not models:
        models.append(f"{base}_record")
    if "project" in modules and f"{base}_work_order" not in models:
        models.append(f"{base}_job")
    seen: set[str] = set()
    out: list[str] = []
    for model in models:
        if model not in seen:
            seen.add(model)
            out.append(model)
    return tuple(out[:5])


def _reuse_stock_lines(pack: dict[str, Any] | None) -> tuple[str, ...]:
    if not pack:
        return ("res.partner — people, contractors, members (link-only; no parallel x_* member model)",)
    lines: list[str] = []
    for hint in pack.get("reuse_stock") or []:
        if isinstance(hint, dict):
            model = hint.get("model") or "res.partner"
            reason = hint.get("reason") or "link-only"
            lines.append(f"{model} — {reason}")
    return tuple(lines) or ("res.partner — contacts (link-only)",)


def _stack_from_catalog(entry: VerticalEntry, pack: dict[str, Any] | None) -> InferredStack:
    modules = list(_BASE_MODULES)
    for mod in entry.stock_modules:
        if mod not in modules and mod != "web":
            modules.append(mod)
    if pack:
        for dep in pack.get("depends") or []:
            if dep not in modules:
                modules.append(dep)
    mod_set = set(modules)
    prefix = _catalog_model_prefix(entry) or _model_prefix(entry.title, pack_id=entry.domain_pack_id)
    if pack and pack.get("models"):
        custom = tuple(
            str(m.get("model"))
            for m in pack.get("models") or []
            if isinstance(m, dict) and m.get("model")
        )[:8]
    else:
        custom = _catalog_custom_models(entry, prefix, mod_set)
    return InferredStack(
        domain_label=entry.title,
        model_prefix=prefix,
        stock_modules=tuple(modules),
        custom_models=custom,
        reuse_stock=_reuse_stock_lines(pack),
        phase_1=f"Contacts structure, security groups, core `{custom[0] if custom else prefix + '_record'}` model, menus.",
        phase_2="Automations (base.automation), mail templates, scheduled actions where needed.",
        phase_3="Bulk import, reporting, optional module export for repeat deployments.",
        honesty=(
            "Targets Odoo Community via public ORM/RPC only.",
            "No Enterprise-only apps assumed unless installed on the instance.",
        ),
        source="catalog",
        catalog_id=entry.id,
        pack_id=entry.domain_pack_id,
        playbook_title=entry.title,
    )


def _stack_from_domain_pack(pack_id: str, pack: dict[str, Any], question: str) -> InferredStack:
    modules = list(_BASE_MODULES)
    for dep in pack.get("depends") or []:
        if dep not in modules:
            modules.append(dep)
    mod_set = set(modules)
    prefix = _model_prefix(question, pack_id=pack_id)
    custom = tuple(
        str(m.get("model"))
        for m in pack.get("models") or []
        if isinstance(m, dict) and m.get("model")
    )[:8] or _suggest_custom_models(prefix, mod_set, question)
    title = str(pack.get("display_name") or pack_id.replace("_", " ").title())
    return InferredStack(
        domain_label=title,
        model_prefix=prefix,
        stock_modules=tuple(modules),
        custom_models=custom,
        reuse_stock=_reuse_stock_lines(pack),
        phase_1=f"Scaffold pack models ({', '.join(custom[:3])}) and Contacts security.",
        phase_2="Automations from the domain pack; mail templates; sandbox-test.",
        phase_3="Export module zip; promote after sandbox gate.",
        honesty=(
            f"Uses the `{pack_id}` domain pack scaffold — verify on your Odoo version.",
            "Protected tier-1 models remain link-only.",
        ),
        source="domain_pack",
        pack_id=pack_id,
        playbook_title=title,
    )


def _stack_from_keywords(question: str) -> InferredStack:
    scores: dict[str, int] = {}
    for pattern, module, weight in _MODULE_SIGNALS:
        if pattern.search(question):
            scores[module] = scores.get(module, 0) + weight
    picked = list(_BASE_MODULES)
    if "stock" in scores or "purchase" in scores:
        picked.append("product")
    for mod, score in sorted(scores.items(), key=lambda kv: -kv[1]):
        if score >= 6 and mod not in picked:
            picked.append(mod)
    if "sale" in picked and "account" not in picked:
        picked.append("account")
    if "mrp" in picked and "stock" not in picked:
        picked.append("stock")
    mod_set = set(picked)
    prefix = _model_prefix(question)
    custom = _suggest_custom_models(prefix, mod_set, question)
    label = _domain_label_from_question(question)
    return InferredStack(
        domain_label=label,
        model_prefix=prefix,
        stock_modules=tuple(dict.fromkeys(picked)),
        custom_models=custom,
        reuse_stock=_reuse_stock_lines(None),
        phase_1=f"Contacts + `{custom[0]}` (and related `{prefix}_*` models), security, menus.",
        phase_2="Automations, mail templates, stock/purchase/project flows as needed.",
        phase_3="Reporting, bulk import, module export after sandbox validation.",
        honesty=(
            "No curated vertical playbook matched — stack inferred from your question keywords.",
            "Sandbox-test before production; adjust modules to what you actually operate.",
            "Do not substitute unrelated verticals (real estate, hotel, library, etc.).",
        ),
        source="inferred",
    )


def infer_odoo_stack(question: str) -> InferredStack | None:
    if not is_setup_stack_question(question):
        return None
    hits = match_verticals(question, limit=1)
    if hits:
        pack: dict[str, Any] | None = None
        if hits[0].domain_pack_id:
            from app.ai_domain_packs import match_domain_pack

            matched = match_domain_pack(question)
            if matched and matched[0] == hits[0].domain_pack_id:
                pack = matched[1]
        return _stack_from_catalog(hits[0], pack)
    from app.ai_domain_packs import match_domain_pack

    matched = match_domain_pack(question)
    if matched:
        pack_id, pack = matched
        entry = catalog_by_id(pack_id)
        if entry:
            return _stack_from_catalog(entry, pack)
        return _stack_from_domain_pack(pack_id, pack, question)
    return _stack_from_keywords(question)


def render_inferred_stack_markdown(stack: InferredStack) -> str:
    mods = ", ".join(f"`{m}`" for m in stack.stock_modules)
    models = ", ".join(f"`{m}`" for m in stack.custom_models) if stack.custom_models else "(minimal custom)"
    reuse = "; ".join(stack.reuse_stock)
    lines = [
        f"Domain: {stack.domain_label} (source: {stack.source}).",
        f"Recommended depends: {mods}.",
        f"Suggested custom models: {models}.",
        f"Reuse stock models: {reuse}.",
        f"Phase 1: {stack.phase_1}",
        f"Phase 2: {stack.phase_2}",
        f"Phase 3: {stack.phase_3}",
    ]
    lines.extend(stack.honesty)
    lines.append(
        "Path: Connect → App Wizard or Models & Fields → sandbox-test → promote. "
        "Never invent parallel member/customer models when res.partner suffices."
    )
    if stack.playbook_title:
        lines.append(f"Curated playbook available: {stack.playbook_title}.")
    return " ".join(lines)


def compose_setup_stack_answer(stack: InferredStack) -> str:
    mods = ", ".join(f"**{m}**" for m in stack.stock_modules)
    models = ", ".join(f"**{m}**" for m in stack.custom_models)
    reuse_inline = "; ".join(stack.reuse_stock)
    honesty = " ".join(stack.honesty)
    intro = (
        f"For **{stack.domain_label}** on Odoo Community, start with this module stack and scaffold:"
        if stack.source != "inferred"
        else f"For **{stack.domain_label}** (inferred stack — no exact playbook match), use:"
    )
    wizard = (
        "Open **App Wizard** (`/connections/{{connection_id}}/wizard`) or **Models & Fields** "
        "to scaffold custom models, then **sandbox-test** before production."
    )
    return (
        f"{intro} [1]\n\n"
        f"1. **Install / depends:** {mods}. [1]\n"
        f"2. **Custom models:** {models or 'one primary `x_*` model'} — via Wizard or Draft Studio. [1]\n"
        f"3. **Reuse stock (link-only):** {reuse_inline} [1]\n"
        f"4. **Phase 1:** {stack.phase_1} [1]\n"
        f"5. **Phase 2:** {stack.phase_2} [1]\n"
        f"6. **Phase 3:** {stack.phase_3} [1]\n"
        f"7. **Operator path:** {wizard} [1]\n"
        f"8. **Honesty:** {honesty} [1]"
    )


def try_rule_based_stack_guidance(question: str) -> dict[str, Any] | None:
    stack = infer_odoo_stack(question)
    if not stack:
        return None
    body = compose_setup_stack_answer(stack)
    flags = ["rule_based_stack_guidance"]
    if stack.source == "inferred":
        flags.append("inferred_stack")
    return {
        "answer_markdown": body,
        "grounded": True,
        "caution_flags": flags,
        "inferred_stack": stack,
    }


__all__ = [
    "InferredStack",
    "compose_setup_stack_answer",
    "infer_odoo_stack",
    "is_setup_stack_question",
    "render_inferred_stack_markdown",
    "try_rule_based_stack_guidance",
]
