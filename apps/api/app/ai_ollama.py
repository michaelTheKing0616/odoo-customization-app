"""NL → ModuleSpec draft. Uses LLMProvider + domain packs + rules. Never applies."""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Callable

from app.ai_critique import run_self_critique
from app.ai_depth import run_depth_pass
from app.ai_domain_packs import list_domain_packs, merge_domain_pack, retrieve_domain_pack
from app.ai_domain_pack_law_firm import scaffold_teaching_blob
from app.ai_enrich import enrich_draft_module_spec
from app.ai_prompt_constants import (
    STEP_TEMPERATURES,
    append_prompt_blocks,
    few_shot_exemplar_block,
)
from app.ai_model_quality import (
    MODEL_CREATION_RULES,
    llm_emit_missing_scaffold_models,
    repair_draft_integrity,
    run_model_quality_pass,
    seed_missing_core_scaffold_models,
)
from app.ai_pipeline import run_staged_pipeline
from app.ai_reuse_planner import ReusePlan, apply_reuse_plan, plan_reuse
from app.ai_rules import validate_and_enrich_draft
from app.llm_provider import (
    LLMError,
    ai_provider_enabled,
    get_llm_provider,
)
from app.llm_json import parse_llm_json_object
from app.settings import settings
_TECHNICAL_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_MODEL_RE = re.compile(r"^x_[a-z0-9_]+$")
_FIELD_RE = re.compile(r"^x_[A-Za-z0-9_]+$")


def normalize_technical_name(raw: Any, *, fallback: str = "custom_app") -> str:
    """Coerce LLM/user labels into Odoo module technical names."""
    source = raw if isinstance(raw, str) and raw.strip() else fallback
    s = source.strip().lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "custom_app"
    if not s[0].isalpha():
        s = f"x_{s}"
    if not _TECHNICAL_RE.fullmatch(s):
        s = "custom_app"
    return s


def derive_draft_naming_from_prompt(
    data: dict[str, Any], user_prompt: str
) -> list[str]:
    """Fill technical_name, display_name, and root menu label from the user prompt."""
    warnings: list[str] = []
    if not user_prompt.strip():
        return warnings
    if data.get("domain_pack"):
        return warnings
    from app.ai_document_shape import naming_from_residual

    residual_display, residual_tech = naming_from_residual(user_prompt)
    if residual_display and residual_tech:
        data["display_name"] = residual_display
        data["technical_name"] = residual_tech
        from app.ai_document_shape import align_root_menu_to_residual

        warnings.extend(align_root_menu_to_residual(data, prompt=user_prompt))
        warnings.append(f"naming from residual → {residual_display!r} / {residual_tech!r}")
        return warnings
    tokens = re.findall(r"[a-zA-Z]+", user_prompt.lower())
    skip = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "with",
        "for",
        "to",
        "of",
        "in",
        "on",
        "around",
        "world",
        "across",
        "large",
        "mega",
        "multiple",
        "full",
        "simple",
        "app",
        "system",
        "management",
        "build",
        "create",
        "company",
        "companies",
    }
    words = [t for t in tokens if t not in skip and len(t) > 2][:4]
    slug_source = "_".join(words) if words else user_prompt
    slug = normalize_technical_name(slug_source, fallback="custom_app")
    raw_tech = str(data.get("technical_name") or "")
    truncated = bool(
        raw_tech
        and len(raw_tech) <= 24
        and slug.startswith(raw_tech.rstrip("_"))
        and slug != raw_tech
    )
    if (
        not raw_tech
        or raw_tech == "custom_app"
        or raw_tech.startswith("a_")
        or truncated
    ):
        if slug == "custom_app":
            warnings.append(
                "technical_name defaulted to custom_app — could not slugify prompt"
            )
        else:
            data["technical_name"] = slug
            warnings.append(f"technical_name derived from prompt → {slug!r}")
    nice = " ".join(w.title() for w in words) if words else ""
    display = str(data.get("display_name") or "")
    if nice and (
        not display
        or display.startswith("A ")
        or display.lower().startswith("x ")
        or (warnings and any("technical_name derived" in w for w in warnings) and len(display) <= 32)
    ):
        data["display_name"] = nice
        warnings.append(f"display_name derived from prompt → {nice!r}")
        for menu in data.get("menus") or []:
            if isinstance(menu, dict) and not menu.get("parent_xml_id"):
                menu["name"] = nice
    return warnings


def sanitize_draft_module_spec(data: dict[str, Any]) -> list[str]:
    """Fix common LLM identifier mistakes in-place; return warnings."""
    warnings: list[str] = []
    raw_tech = data.get("technical_name")
    display = data.get("display_name")
    fallback = display if isinstance(display, str) else "custom_app"
    fixed = normalize_technical_name(raw_tech, fallback=str(fallback))
    if raw_tech != fixed:
        if raw_tech:
            warnings.append(f"technical_name normalized {raw_tech!r} → {fixed!r}")
        else:
            warnings.append(f"technical_name defaulted to {fixed!r}")
    data["technical_name"] = fixed
    return warnings

_SYSTEM_PROMPT = f"""You are a ModuleSpec JSON generator for Odoo Community 19 customizations
(public ORM/RPC only — never Studio Enterprise). Your #1 job is to honor the operator
brief: stated residual only, unknowns omitted, out-of-scope never inherited.

Reply with ONLY a JSON object.

{MODEL_CREATION_RULES}

Ambition floors apply to workspace / transactional_header only
(register / field_pack / stock_reuse ignore these):
- thin / "simple" workspace → ≥2 substantive models
- normal management / system / app → ≥5 substantive models, ≥1 workflow (x_status)
- comprehensive / world-class / end-to-end → ≥10 substantive models, ≥3 workflows,
  rich many2one graph, smart buttons, safe automations

Operational loop (workspace only — adapt roles to the domain):
  master data → transactional documents → line/support/events → billing/compliance stubs

Field & apply-ready rules:
- Custom models/fields start with x_; workflows need x_status only when the brief named a lifecycle
- many2one to res.partner when the brief named a contact; res.users only for login/assignee;
  res.company / res.currency only when the brief named multi-company or a currency
- many2one to pos.order / pos.session: include options no_create + no_create_edit
  (pick existing PoS records only — do not invent backend create)
- Every operator-facing field SHOULD include a short `help` tooltip (cashier/clerk guidance)
- smart_buttons: useful host↔residual links (Punch Cards on Contacts, residual on
  Employees / Orders / Invoices when an x_* M2O points there);
  relation_field MUST be x_* many2one on related_model pointing at on_model;
  skip Contacts buttons on visitor/key/call logs
- automations: triggers on_create|on_write|on_create_or_write|on_time|… only;
  safe_actions only (object_write, related_write, next_activity). Never Python / email_send.
  Duration alerts: header datetime + trg_date_range, not create_date.
- reuse_hints + depends: only hosts the brief uses (hr when an employee is named)

Schema (required keys):
{{
  "technical_name": "snake_case",
  "display_name": "Label",
  "depends": ["base", "mail"],
  "models": [{{
    "model": "x_thing",
    "description": "Thing",
    "mode": "new",
    "fields": [
      {{"name": "x_name", "ttype": "char", "string": "Name", "required": true}}
    ]
  }}],
  "smart_buttons": [],
  "automations": [],
  "reuse_hints": [{{"model": "res.partner", "reason": "..."}}]
}}

No markdown. Prefer fewer rich models over many hollow catalogs.
"""


def module_spec_system_prompt(user_prompt: str = "") -> str:
    """System prompt plus the operator-brief contract for this request."""
    if not (user_prompt or "").strip():
        return _SYSTEM_PROMPT
    from app.ai_operator_brief import brief_llm_contract

    return _SYSTEM_PROMPT + "\n\n" + brief_llm_contract(user_prompt)


class AiAssistUnavailable(Exception):
    """Raised when AI assist is off or provider is unreachable."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


def ai_assist_enabled() -> bool:
    return ai_provider_enabled()


def ollama_reachable(*, timeout_s: float = 2.0) -> tuple[bool, str]:
    provider = get_llm_provider()
    if provider is None:
        return False, "AI_ASSIST is off"
    return provider.reachable(timeout_s=timeout_s)


def _extract_json_object(text: str) -> dict[str, Any]:
    return parse_llm_json_object(text)


def call_ollama_generate(prompt: str, *, timeout_s: float = 120.0) -> str:
    """Back-compat wrapper — prefer get_llm_provider().generate_json."""
    provider = get_llm_provider()
    if provider is None:
        raise AiAssistUnavailable(
            "AI assist is disabled. Set AI_ASSIST=auto (or ollama|openai|claude|gemini) "
            "and provide the matching API key, or use a domain-matched prompt."
        )
    try:
        return provider.generate_json(
            prompt,
            system=module_spec_system_prompt(prompt),
            timeout_s=timeout_s,
            reasoning=True,
            temperature=STEP_TEMPERATURES["single_pipeline"],
        )
    except LLMError as exc:
        raise AiAssistUnavailable(str(exc), status_code=exc.status_code) from exc


def validate_draft_module_spec(data: dict[str, Any]) -> list[str]:
    """Return warnings; raise ValueError on hard invalid technical names."""
    warnings: list[str] = sanitize_draft_module_spec(data)
    tech = data.get("technical_name")
    if not isinstance(tech, str) or not _TECHNICAL_RE.fullmatch(tech):
        raise ValueError(
            "draft.technical_name must be lowercase python-module style (a-z0-9_)"
        )
    if not data.get("display_name"):
        warnings.append("display_name missing — defaulting may be required")
    models = data.get("models")
    ir = data.get("_generation_engine") if isinstance(data.get("_generation_engine"), dict) else {}
    empty_ok = ir.get("capability") in {"stock_reuse", "refuse_clone"}
    if not isinstance(models, list) or (not models and not empty_ok):
        raise ValueError("draft.models must be a non-empty list")
    for i, model in enumerate(models):
        if not isinstance(model, dict):
            raise ValueError(f"models[{i}] must be an object")
        mname = model.get("model")
        mode = model.get("mode") or "new"
        if mode == "inherit":
            if not isinstance(mname, str) or not mname:
                raise ValueError(f"models[{i}].model required for inherit")
        elif not isinstance(mname, str) or not _MODEL_RE.fullmatch(mname):
            raise ValueError(
                f"models[{i}].model must match x_[a-z0-9_]+ (got {mname!r})"
            )
        fields = model.get("fields") or []
        if not isinstance(fields, list):
            raise ValueError(f"models[{i}].fields must be a list")
        for j, field in enumerate(fields):
            if not isinstance(field, dict):
                raise ValueError(f"models[{i}].fields[{j}] must be an object")
            fname = field.get("name")
            if not isinstance(fname, str) or not _FIELD_RE.fullmatch(fname):
                raise ValueError(
                    f"models[{i}].fields[{j}].name must match x_* (got {fname!r})"
                )
    depends = data.get("depends")
    if depends is not None and not isinstance(depends, list):
        warnings.append("depends should be a list of module names")
    return warnings


def _build_prompt_with_context(
    prompt: str,
    *,
    available_models: list[str] | None = None,
    stock_catalog: list[dict[str, Any]] | None = None,
    reuse_models: list[str] | None = None,
    reuse_views: list[dict[str, Any]] | None = None,
    reuse_actions: list[dict[str, Any]] | None = None,
    reuse_plan: ReusePlan | None = None,
    scaffold: dict[str, Any] | None = None,
    matched_pack_id: str | None = None,
    architecture_plan: dict[str, Any] | None = None,
    document_shape: str | None = None,
    operator_brief: str | None = None,
) -> str:
    from app.ai_domain_briefing import build_domain_briefing
    from app.ai_operator_brief import brief_llm_contract, build_operator_brief

    # Prefer raw operator text. If a labeled prompt_for_generators blob was passed,
    # strip our section headers so contract/shape classify on the original.
    raw = (prompt or "").strip()
    if raw.startswith("## Original operator message"):
        parts_raw = raw.split(
            "## Upstream operator brief IR (may be wrong — verify against original)",
            1,
        )
        head = parts_raw[0]
        raw = head.replace(
            "## Original operator message (verbatim — authoritative)", "", 1
        ).strip()
        if len(parts_raw) > 1 and not (operator_brief or "").strip():
            operator_brief = parts_raw[1].strip()

    brief_text = (operator_brief or "").strip()
    if not brief_text:
        brief_text = build_operator_brief(raw).formatted

    parts = [
        brief_llm_contract(raw),
        "## Original operator message (verbatim — authoritative)\n" + raw,
        "## Upstream operator brief IR (may be wrong — verify against original)\n"
        + brief_text,
    ]
    parts.append(build_domain_briefing(raw).prompt_block())
    if architecture_plan:
        parts.append(
            "LOCKED architecture_plan (emit fields/views/automations ONLY for new_x_models; "
            "adding any other x_* model is invalid JSON):\n"
            + json.dumps(architecture_plan, default=str)
        )
        if str(architecture_plan.get("document_shape") or document_shape) == "register":
            parts.append(
                "This is a register: one header model, no party/line satellites, "
                "no CRM or invoice inherits. Do not invent an ERP."
            )
    parts.append(
        "Follow these model-creation rules exactly:\n" + MODEL_CREATION_RULES
    )
    exemplar = few_shot_exemplar_block(
        matched_pack_id, document_shape=document_shape
    )
    if exemplar:
        parts.append(
            "Quality exemplar (adapt roles to THIS domain; do not invent hollow type/tag models):\n"
            + exemplar
        )
    if reuse_plan is not None:
        parts.append(reuse_plan.prompt_block())
    if scaffold:
        teach = scaffold_teaching_blob(scaffold)
        parts.append(
            "World-class domain scaffold (study then adapt — match or exceed depth):\n"
            + teach
        )
    if reuse_models:
        parts.append(
            "Prefer linking these existing Odoo models (do not recreate them): "
            + ", ".join(reuse_models)
        )
    if reuse_views:
        labels = [
            f"{v.get('id')}:{v.get('name') or v.get('model')}"
            for v in reuse_views
            if isinstance(v, dict)
        ]
        if labels:
            parts.append(
                "Operator wants to reuse these existing views: " + "; ".join(labels[:30])
            )
    if reuse_actions:
        labels = [
            f"{a.get('id')}:{a.get('name')}"
            for a in reuse_actions
            if isinstance(a, dict)
        ]
        if labels:
            parts.append(
                "Operator wants to reuse these existing actions: " + "; ".join(labels[:30])
            )
    if stock_catalog:
        from app.ai_stock_catalog import format_stock_models_for_llm

        block = format_stock_models_for_llm(stock_catalog, raw)
        if block:
            parts.append(block)
    elif available_models:
        parts.append(
            "Sample models already on the instance: "
            + ", ".join(available_models[:80])
        )
    return "\n\n".join(parts)


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for w in warnings:
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def _infer_llm_mode(
    draft: dict[str, Any],
    warnings: list[str],
    *,
    llm_initial_failed: bool = False,
    provider: Any | None = None,
    matched: tuple[str, dict[str, Any]] | None = None,
) -> str:
    """Map pipeline warnings to structured _llm_status.mode."""
    failed_steps = [
        w.split(":")[0]
        for w in warnings
        if "LLM failed" in w or "timed out" in w.lower() or "staged LLM failed" in w
    ]
    pack_markers = (
        "falling back to pack",
        "using domain pack",
        "step1-5 skipped",
    )
    if llm_initial_failed or (provider is None and matched):
        return "pack_fallback"
    if any(any(marker in w.lower() for marker in pack_markers) for w in warnings):
        return "pack_fallback"
    if failed_steps:
        return "llm_partial"
    depth_meta = draft.get("_depth") if isinstance(draft.get("_depth"), dict) else {}
    if depth_meta.get("seeded"):
        return "seed_fallback"
    return "llm_full"


def _emit_partial_progress(
    progress_callback: Callable[[int, str, dict[str, Any] | None], None] | None,
    step: int,
    draft: dict[str, Any],
) -> None:
    """Surface in-progress ModuleSpec JSON to async job pollers.

    Tagged incomplete so the wizard never treats a mid-pipeline snapshot as the app.
    """
    if progress_callback is None:
        return
    from app.ai_llm_status import STEP_LABELS, sanitize_draft_payload

    payload = sanitize_draft_payload(draft)
    payload["_generation_incomplete"] = True
    idx = max(0, min(step, len(STEP_LABELS) - 1))
    progress_callback(idx, STEP_LABELS[idx], payload)


def _finalize_draft_generation(
    draft: dict[str, Any],
    prompt: str,
    warnings: list[str],
    *,
    llm_mode: str,
    progress_callback: Callable[[int, str, dict[str, Any] | None], None] | None = None,
) -> list[str]:
    """Post-LLM finisher shared by single and staged pipelines."""
    from app.ai_critique import finalize_critique_block
    from app.ai_domain_briefing import attach_domain_briefing
    from app.ai_draft_scorecard import attach_scorecard, scorecard_required_repairs
    from app.ai_elite import run_elite_passes
    from app.ai_llm_status import STEP_LABELS, attach_llm_status, finalize_llm_status, sanitize_draft_payload
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass

    draft["_user_prompt"] = prompt
    from app.ai_operator_brief import attach_operator_brief

    attach_operator_brief(draft, user_prompt=prompt)
    attach_domain_briefing(draft, user_prompt=prompt)
    draft.pop("_generation_incomplete", None)
    sanitized = sanitize_draft_payload(draft)
    if sanitized is not draft:
        draft.clear()
        draft.update(sanitized)
    warnings.extend(derive_draft_naming_from_prompt(draft, prompt))
    warnings.extend(finalize_critique_block(draft))
    failed_steps = [
        w.split(":")[0]
        for w in warnings
        if "LLM failed" in w or "timed out" in w.lower() or "staged LLM failed" in w
    ]
    attach_llm_status(
        draft,
        mode=llm_mode,  # type: ignore[arg-type]
        failed_steps=failed_steps,
        reason="timeout" if failed_steps else None,
    )
    finalize_llm_status(draft, mode=llm_mode)  # type: ignore[arg-type]
    warnings.extend(run_post_critique_pipeline(draft, user_prompt=prompt))
    from app.ai_odoo_app_bar import (
        apply_senior_sequence_prefixes,
        humanize_app_surface,
        inject_chatter_on_forms,
        run_odoo_app_bar_pass,
    )

    warnings.extend(run_odoo_app_bar_pass(draft, user_prompt=prompt))
    warnings.extend(run_production_shape_pass(draft))
    warnings.extend(apply_senior_sequence_prefixes(draft))
    warnings.extend(run_elite_passes(draft, user_prompt=prompt))
    warnings.extend(inject_chatter_on_forms(draft))
    warnings.extend(humanize_app_surface(draft))
    from app.ai_odoo_app_bar import close_odoo_architecture

    warnings.extend(close_odoo_architecture(draft, user_prompt=prompt))
    from app.ai_apply_readiness import filter_stale_enrich_warnings

    warnings = filter_stale_enrich_warnings(warnings, draft)
    attach_scorecard(draft, user_prompt=prompt)
    sc = draft.get("_scorecard") if isinstance(draft.get("_scorecard"), dict) else {}
    if float(sc.get("score_0_10") or 0) < 9:
        crit = draft.get("_critique") if isinstance(draft.get("_critique"), dict) else {}
        sug = list(crit.get("suggestions") or [])
        sug.extend(scorecard_required_repairs(sc))
        crit["suggestions"] = sug
        draft["_critique"] = crit
    draft["_meta"] = {
        **(draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}),
        "model_count": len(draft.get("models") or []),
        "view_count": len(draft.get("views") or []),
        "menu_count": len(draft.get("menus") or []),
        "smart_button_count": len(draft.get("smart_buttons") or []),
        "automation_count": len(draft.get("automations") or []),
        "domain_pack": draft.get("domain_pack"),
        "score_0_10": (draft.get("_scorecard") or {}).get("score_0_10"),
    }
    if progress_callback:
        progress_callback(len(STEP_LABELS) - 1, STEP_LABELS[-1], draft)
    return warnings


def _apply_pcm_strip(
    draft: dict[str, Any],
    *,
    protected_manifest: dict[str, Any] | None,
    odoo_version: str | None,
    client: Any | None,
    warnings: list[str],
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    from app.ai_rules import strip_protected_module_effects
    from app.protected_modules import refresh_connection_protected_manifest

    manifest = protected_manifest or refresh_connection_protected_manifest(
        server_version=odoo_version,
        client=client,
    )
    cleaned, refusals, pcm_w = strip_protected_module_effects(draft, manifest=manifest)
    warnings.extend(pcm_w)
    return cleaned, _dedupe_warnings(warnings), refusals


def draft_module_from_prompt(
    prompt: str,
    *,
    available_models: list[str] | None = None,
    installed_modules: list[str] | None = None,
    reuse_models: list[str] | None = None,
    rejected_reuse_models: list[str] | None = None,
    stock_catalog: list[dict[str, Any]] | None = None,
    reuse_views: list[dict[str, Any]] | None = None,
    reuse_actions: list[dict[str, Any]] | None = None,
    expand: bool = True,
    pipeline: str | None = None,
    protected_manifest: dict[str, Any] | None = None,
    odoo_version: str | None = None,
    grain_override: str | None = None,
    gallery_id: str | None = None,
    host_model_override: str | None = None,
    connect_points_override: dict[str, Any] | None = None,
    client: Any | None = None,
    progress_callback: Callable[[int, str, dict[str, Any] | None], None] | None = None,
) -> tuple[dict[str, Any], str, list[str], list[dict[str, Any]]]:
    """Return (draft_dict, raw_response, warnings, refusals). Never mutates Odoo."""
    from app.ai_component_builder import draft_component_from_prompt
    from app.ai_generation_engine import maybe_seed_from_capability
    from app.ai_grain import classify_grain
    from app.ai_operator_brief import intent_corpus
    from app.ai_rules import strip_protected_module_effects
    from app.protected_modules import refresh_connection_protected_manifest

    capability_seed = maybe_seed_from_capability(prompt)
    if capability_seed:
        from app.ai_draft_scorecard import attach_scorecard
        from app.ai_live_apply_contract import attach_live_apply_contract
        from app.ai_llm_status import finalize_llm_status, sanitize_draft_payload

        warnings: list[str] = []
        try:
            warnings.extend(attach_live_apply_contract(capability_seed))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Live-apply stamp skipped: {exc}")
        attach_scorecard(capability_seed, user_prompt=prompt)
        finalize_llm_status(capability_seed, mode="seed_fallback")
        draft = sanitize_draft_payload(capability_seed)
        warnings = _dedupe_warnings(warnings + validate_draft_module_spec(draft))
        raw = json.dumps(
            {
                "grain": draft.get("grain"),
                "capability": (draft.get("_generation_engine") or {}).get("capability"),
            }
        )
        return draft, raw, warnings, []

    grain = grain_override or classify_grain(intent_corpus(prompt) or prompt)
    if grain != "full_app":
        draft, _hosts, comp_warnings = draft_component_from_prompt(
            prompt,
            grain=grain,  # type: ignore[arg-type]
            available_models=available_models,
            connect_points_override=connect_points_override,
            gallery_id=gallery_id,
            host_model_override=host_model_override,
            client=client,
        )
        manifest = protected_manifest or refresh_connection_protected_manifest(
            server_version=odoo_version,
            client=client,
        )
        draft, late_refusals, late_w = strip_protected_module_effects(draft, manifest=manifest)
        refusals = list(late_refusals)
        from app.ai_draft_scorecard import attach_scorecard
        from app.ai_live_apply_contract import attach_live_apply_contract
        from app.ai_llm_status import attach_llm_status, finalize_llm_status, sanitize_draft_payload

        try:
            comp_warnings = list(comp_warnings) + attach_live_apply_contract(draft)
        except Exception as exc:  # noqa: BLE001
            comp_warnings = list(comp_warnings) + [f"Live-apply stamp skipped: {exc}"]
        attach_scorecard(draft, user_prompt=prompt)
        attach_llm_status(draft, mode="llm_full", reason="component_grain")
        finalize_llm_status(draft, mode="llm_full")
        draft = sanitize_draft_payload(draft)
        warnings = _dedupe_warnings(comp_warnings + late_w + validate_draft_module_spec(draft))
        raw = json.dumps(
            {"grain": grain, "component": True, "connect_points": draft.get("connect_points")}
        )
        return draft, raw, warnings, refusals

    from app.ai_domain_packs import match_domain_pack
    from app.ollama_warm import warm_ollama_models

    warm_ollama_models()
    if progress_callback:
        from app.ai_llm_status import STEP_LABELS

        progress_callback(0, STEP_LABELS[0], None)

    early_pack = match_domain_pack(prompt)
    pack_stock: list[dict[str, Any]] | None = None
    if early_pack:
        raw_stock = early_pack[1].get("reuse_stock")
        if isinstance(raw_stock, list):
            pack_stock = raw_stock

    reuse_plan = plan_reuse(
        prompt,
        available_models=available_models,
        installed_modules=installed_modules,
        operator_reuse=reuse_models,
        pack_reuse_stock=pack_stock,
        rejected_reuse_models=rejected_reuse_models,
        stock_catalog=stock_catalog,
    )
    effective_reuse = list(
        dict.fromkeys(
            [
                *(reuse_models or []),
                *[d.model for d in reuse_plan.decisions if d.confirmed],
            ]
        )
    )

    warnings: list[str] = []
    from app.ai_depth import classify_ambition_with_notes

    scaled_amb, amb_notes = classify_ambition_with_notes(prompt)
    warnings.extend(amb_notes)

    mode = (pipeline or settings.ai_pipeline_mode or "single").strip().lower()
    if mode == "staged":
        from app.ai_pipeline import seed_unpacked_draft

        try:
            draft, raw, staged_warnings = run_staged_pipeline(
                prompt,
                reuse_models=effective_reuse,
                protected_manifest=protected_manifest,
                odoo_version=odoo_version,
            )
            warnings = list(amb_notes) + staged_warnings
        except LLMError as exc:
            warnings.append(f"staged LLM failed ({exc}); seeding unpacked draft")
            from app.ai_domain_briefing import build_domain_briefing

            draft = seed_unpacked_draft(
                prompt,
                briefing=build_domain_briefing(prompt),
                ambition=scaled_amb,
            )
            raw = ""
        _emit_partial_progress(progress_callback, 2, draft)
        draft.setdefault("_ambition", scaled_amb)
        warnings.extend(apply_reuse_plan(draft, reuse_plan))
        if expand:
            prov = get_llm_provider()
            draft, q_w = run_model_quality_pass(
                draft,
                user_prompt=prompt,
                ambition=str(draft.get("_ambition") or "standard"),
                provider=prov,
                expand_llm=True,
            )
            warnings.extend(q_w)
            draft, depth_w = run_depth_pass(
                draft,
                user_prompt=prompt,
                provider=prov,
                expand_llm=True,
            )
            warnings.extend(depth_w)
            draft, critique_w = run_self_critique(
                draft, user_prompt=prompt, repair=True
            )
            warnings.extend(critique_w)
            draft, q_w2 = run_model_quality_pass(
                draft,
                user_prompt=prompt,
                ambition=str(draft.get("_ambition") or "standard"),
                provider=None,
                expand_llm=False,
            )
            warnings.extend(q_w2)
            warnings.extend(apply_reuse_plan(draft, reuse_plan))
            draft, depth_w2 = run_depth_pass(
                draft,
                user_prompt=prompt,
                provider=None,
                expand_llm=False,
            )
            warnings.extend(depth_w2)
        warnings.extend(validate_draft_module_spec(draft))
        draft, warnings, refusals = _apply_pcm_strip(
            draft,
            protected_manifest=protected_manifest,
            odoo_version=odoo_version,
            client=client,
            warnings=warnings,
        )
        from app.ai_enrich import sync_form_archs_to_models

        warnings.extend(sync_form_archs_to_models(draft))
        staged_provider = get_llm_provider()
        staged_matched = (
            (str(draft.get("domain_pack")), {})
            if draft.get("domain_pack")
            else early_pack
        )
        llm_mode = _infer_llm_mode(
            draft,
            warnings,
            provider=staged_provider,
            matched=staged_matched,  # type: ignore[arg-type]
        )
        warnings = _finalize_draft_generation(
            draft,
            prompt,
            warnings,
            llm_mode=llm_mode,
            progress_callback=progress_callback,
        )
        return draft, raw, warnings, refusals

    provider = get_llm_provider()
    from app.ai_domain_packs import match_domain_pack

    retrieved = retrieve_domain_pack(prompt, provider=provider)
    matched = (retrieved[0], retrieved[1]) if retrieved else early_pack
    scaffold = matched[1] if matched else None

    from app.ai_architecture_plan import stamp_architecture_plan
    from app.ai_document_shape import (
        classify_document_shape,
        clip_llm_models_to_plan,
        honor_operator_brief,
        llm_models_outside_plan,
        merge_llm_fields_into_locked,
    )
    from app.ai_pipeline import seed_unpacked_draft
    from app.llm_provider import generate_json_with_timeout_retry

    locked_seed: dict[str, Any] | None = None
    doc_shape = classify_document_shape(prompt)
    if doc_shape == "register" and not matched:
        from app.ai_domain_briefing import build_domain_briefing

        locked_seed = seed_unpacked_draft(
            prompt,
            briefing=build_domain_briefing(prompt),
            ambition="thin",
        )
        stamp_architecture_plan(locked_seed, prompt=prompt, rebuild=True)

    plan_blob = None
    if locked_seed and isinstance(locked_seed.get("_architecture_plan"), dict):
        plan_blob = dict(locked_seed["_architecture_plan"])

    brief_fmt = ""
    if locked_seed and isinstance(locked_seed.get("_operator_brief"), dict):
        brief_fmt = str(locked_seed["_operator_brief"].get("formatted") or "")

    enriched_prompt = _build_prompt_with_context(
        prompt,
        available_models=available_models,
        stock_catalog=stock_catalog,
        reuse_models=effective_reuse,
        reuse_views=reuse_views,
        reuse_actions=reuse_actions,
        reuse_plan=reuse_plan,
        scaffold=scaffold,
        matched_pack_id=matched[0] if matched else None,
        architecture_plan=plan_blob,
        document_shape=doc_shape,
        operator_brief=brief_fmt or None,
    )

    raw = ""
    draft: dict[str, Any] | None = None
    llm_initial_failed = False

    if provider is not None:
        parse_exc: Exception | None = None
        for attempt in range(2):
            try:
                raw = generate_json_with_timeout_retry(
                    provider,
                    enriched_prompt,
                    system=module_spec_system_prompt(prompt),
                    reasoning=False,
                    temperature=0.15 if attempt else None,
                    log_step="draft_json",
                )
                draft = _extract_json_object(raw)
                if (
                    locked_seed
                    and plan_blob
                    and llm_models_outside_plan(draft, plan_blob)
                    and attempt == 0
                ):
                    parse_exc = ValueError("LLM emitted models outside architecture_plan")
                    continue
                parse_exc = None
                break
            except (LLMError, ValueError, json.JSONDecodeError) as exc:
                parse_exc = exc
                if isinstance(exc, LLMError) and attempt == 0:
                    continue
                break
        if draft is None and parse_exc is not None:
            llm_initial_failed = isinstance(parse_exc, LLMError)
            if locked_seed is not None:
                warnings.append(
                    f"LLM draft failed ({parse_exc}); honesty-IR register seed (no density pad)"
                )
                draft = locked_seed
                raw = raw or json.dumps(draft)
            else:
                pack_fallback = matched
                if pack_fallback is None:
                    lexical = match_domain_pack(prompt)
                    if lexical:
                        pack_fallback = lexical
                        warnings.append(
                            f"LLM JSON failed; falling back to domain pack '{lexical[0]}'"
                        )
                if pack_fallback:
                    warnings.append(f"LLM draft failed ({parse_exc}); using domain pack")
                    draft = copy.deepcopy(pack_fallback[1])
                    raw = raw or json.dumps(draft)
                    if matched is None:
                        matched = pack_fallback
                else:
                    msg = str(parse_exc)
                    if isinstance(parse_exc, json.JSONDecodeError) or "malformed JSON" in msg:
                        msg = (
                            "AI returned malformed JSON. Click Create draft again, shorten the "
                            "prompt, or use a ready-made template at the bottom of Draft Studio."
                        )
                    raise AiAssistUnavailable(msg, status_code=422) from parse_exc
    elif matched:
        draft = matched[1]
        raw = json.dumps(draft)
        score = retrieved[2] if retrieved else 0.0
        warnings.append(
            f"AI assist off — used curated domain pack '{matched[0]}' "
            f"(retrieval score={score:.2f})"
        )
    else:
        if locked_seed is not None:
            draft = locked_seed
            raw = json.dumps(draft)
            warnings.append(
                "AI assist off — honesty-IR unlocked residual (not a padded workspace)"
            )
        else:
            raise AiAssistUnavailable(
                "AI assist is disabled and no domain pack matched this prompt with sufficient "
                "confidence. Enable AI assist (Ollama) to generate drafts for arbitrary domains, "
                "or use a prompt that clearly matches a curated vertical (car rental, hospital, "
                "law firm, clinic, field service, retail, oil & gas, …)."
            )

    assert draft is not None
    if locked_seed is not None and draft is not locked_seed:
        draft = merge_llm_fields_into_locked(locked_seed, draft, plan_blob)
        warnings.extend(clip_llm_models_to_plan(draft, plan_blob))
    draft["_user_prompt"] = prompt
    draft["_ambition"] = "thin" if doc_shape in {"register", "field_pack", "stock_reuse"} else scaled_amb
    _emit_partial_progress(progress_callback, 1, draft)
    warnings.extend(sanitize_draft_module_spec(draft))
    warnings.extend(derive_draft_naming_from_prompt(draft, prompt))

    # Pure-AI repair: emit omitted scaffold models before pack merge fills them
    if matched and provider is not None and doc_shape != "register":
        draft, gap_notes = llm_emit_missing_scaffold_models(
            provider, draft, matched[1], user_prompt=prompt
        )
        warnings.extend(gap_notes)
        draft, seed_notes = seed_missing_core_scaffold_models(draft, matched[1])
        warnings.extend(seed_notes)

    if matched and doc_shape != "register":
        coherence_notes = list((matched[1] or {}).get("_coherence_warnings") or [])
        if coherence_notes:
            warnings.extend(coherence_notes)
        draft, pack_warnings = merge_domain_pack(draft, matched[1])
        warnings.extend(pack_warnings)
        _emit_partial_progress(progress_callback, 3, draft)
        pack_stock = matched[1].get("reuse_stock") or draft.get("_pack_reuse_stock")
        if pack_stock:
            reuse_plan = plan_reuse(
                prompt,
                available_models=available_models,
                installed_modules=installed_modules,
                operator_reuse=reuse_models,
                pack_reuse_stock=pack_stock if isinstance(pack_stock, list) else None,
                rejected_reuse_models=rejected_reuse_models,
                stock_catalog=stock_catalog,
            )
            effective_reuse = list(
                dict.fromkeys(
                    [
                        *(reuse_models or []),
                        *[d.model for d in reuse_plan.decisions if d.confirmed],
                    ]
                )
            )

    if expand:
        draft, enrich_warnings = enrich_draft_module_spec(
            draft,
            reuse_models=effective_reuse,
            reuse_views=reuse_views,
            reuse_actions=reuse_actions,
        )
        warnings.extend(enrich_warnings)
        warnings.extend(apply_reuse_plan(draft, reuse_plan))
        draft, rule_warnings, _errs = validate_and_enrich_draft(draft)
        warnings.extend(rule_warnings)
        draft, q_w = run_model_quality_pass(
            draft,
            user_prompt=prompt,
            ambition=str(draft.get("_ambition") or scaled_amb),
            provider=provider,
            expand_llm=doc_shape not in {"register", "field_pack", "stock_reuse"},
        )
        warnings.extend(q_w)
        draft, depth_w = run_depth_pass(
            draft,
            user_prompt=prompt,
            provider=provider,
            expand_llm=doc_shape not in {"register", "field_pack", "stock_reuse"},
        )
        warnings.extend(depth_w)
        draft, critique_w = run_self_critique(
            draft,
            user_prompt=prompt,
            repair=doc_shape not in {"register", "field_pack", "stock_reuse"},
        )
        warnings.extend(critique_w)
        draft, q_w2 = run_model_quality_pass(
            draft,
            user_prompt=prompt,
            ambition=str(draft.get("_ambition") or "standard"),
            provider=None,
            expand_llm=False,
        )
        warnings.extend(q_w2)
        # Collapse any parallels critique re-added
        warnings.extend(apply_reuse_plan(draft, reuse_plan))
        # Re-enrich views if critique/depth added models/fields
        if any(
            ("critique: added" in w)
            or ("LLM expand" in w)
            or ("synthesized" in w)
            or ("quality:" in w)
            or ("field-deepen" in w)
            or ("reuse: collapsed" in w)
            or ("seeded" in w)
            for w in (*critique_w, *depth_w, *q_w, *q_w2, *warnings[-12:])
        ):
            draft, enrich2 = enrich_draft_module_spec(
                draft,
                reuse_models=effective_reuse,
                reuse_views=reuse_views,
                reuse_actions=reuse_actions,
            )
            warnings.extend(enrich2)
            draft, rule_w2, _errs2 = validate_and_enrich_draft(draft)
            warnings.extend(rule_w2)
            draft, depth_w2 = run_depth_pass(
                draft,
                user_prompt=prompt,
                provider=None,
                expand_llm=False,
            )
            warnings.extend(depth_w2)
            notes_final = repair_draft_integrity(
                draft, ambition=str(draft.get("_ambition") or "standard")
            )
            warnings.extend(notes_final)
    else:
        warnings.extend(apply_reuse_plan(draft, reuse_plan))

    warnings.extend(honor_operator_brief(draft, user_prompt=prompt))
    if plan_blob:
        warnings.extend(clip_llm_models_to_plan(draft, plan_blob))
    warnings.extend(validate_draft_module_spec(draft))
    from app.ai_model_quality import strip_internal_scaffold

    warnings.extend(strip_internal_scaffold(draft))
    draft, warnings, refusals = _apply_pcm_strip(
        draft,
        protected_manifest=protected_manifest,
        odoo_version=odoo_version,
        client=client,
        warnings=warnings,
    )
    llm_mode = _infer_llm_mode(
        draft,
        warnings,
        llm_initial_failed=llm_initial_failed,
        provider=provider,
        matched=matched,
    )
    warnings = _finalize_draft_generation(
        draft,
        prompt,
        warnings,
        llm_mode=llm_mode,
        progress_callback=progress_callback,
    )
    return draft, raw, warnings, refusals


# Re-export for status endpoint
__all__ = [
    "AiAssistUnavailable",
    "ai_assist_enabled",
    "call_ollama_generate",
    "draft_module_from_prompt",
    "list_domain_packs",
    "ollama_reachable",
    "validate_draft_module_spec",
]
