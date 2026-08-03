"""NL → ModuleSpec draft. Uses LLMProvider + domain packs + rules. Never applies."""

from __future__ import annotations

import json
import re
from typing import Any

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
from app.settings import settings
_TECHNICAL_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_MODEL_RE = re.compile(r"^x_[a-z0-9_]+$")
_FIELD_RE = re.compile(r"^x_[A-Za-z0-9_]+$")

_SYSTEM_PROMPT = f"""You are a ModuleSpec JSON generator for Odoo Community 19 customizations
(public ORM/RPC only — never Studio Enterprise). Your #1 job is MODEL CREATION QUALITY:
rich, apply-ready models that mirror real operations — not thin CRUD or lookup-table padding.

Reply with ONLY a JSON object.

{MODEL_CREATION_RULES}

Ambition floors (meet or exceed):
- thin / "simple" → ≥2 substantive models
- normal management / system / app → ≥5 substantive models, ≥1 workflow (x_status)
- comprehensive / world-class / end-to-end → ≥10 substantive models, ≥3 workflows,
  rich many2one graph, smart buttons, safe automations

Operational loop (adapt roles to the domain):
  master data → transactional documents → line/support/events → billing/compliance stubs

Field & apply-ready rules:
- Custom models/fields start with x_; workflows need x_status (+ x_code with domain-specific help)
- many2one to res.partner / res.users / res.company when contacts, assignees, multi-company matter
- Amounts → x_currency_id (res.currency)
- smart_buttons: relation_field MUST be x_* many2one on related_model pointing at on_model
- automations: triggers on_create|on_write|on_create_or_write|on_time|… only;
  safe_actions only (object_write, related_write, next_activity). Never Python / email_send.
- reuse_hints + depends: include contacts + mail when relevant

Schema (required keys):
{{
  "technical_name": "snake_case",
  "display_name": "Label",
  "depends": ["base", "contacts", "mail"],
  "models": [{{
    "model": "x_thing",
    "description": "Thing",
    "mode": "new",
    "fields": [
      {{"name": "x_name", "ttype": "char", "string": "Name", "required": true}},
      {{"name": "x_status", "ttype": "selection", "string": "Status",
       "selection": "[('draft','Draft'),('done','Done')]"}},
      {{"name": "x_partner_id", "ttype": "many2one", "relation": "res.partner", "string": "Contact"}}
    ]
  }}],
  "smart_buttons": [],
  "automations": [],
  "reuse_hints": [{{"model": "res.partner", "reason": "..."}}]
}}

No markdown. Prefer fewer rich models over many hollow catalogs.
"""


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
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(text[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("LLM response did not contain a JSON object")


def call_ollama_generate(prompt: str, *, timeout_s: float = 120.0) -> str:
    """Back-compat wrapper — prefer get_llm_provider().generate_json."""
    provider = get_llm_provider()
    if provider is None:
        raise AiAssistUnavailable(
            "AI assist is disabled. Set AI_ASSIST=ollama (or openai-compatible) "
            "and pull qwen2.5:7b-instruct-q4_K_M, or use a domain-matched prompt."
        )
    try:
        return provider.generate_json(
            prompt,
            system=_SYSTEM_PROMPT,
            timeout_s=timeout_s,
            reasoning=True,
            temperature=STEP_TEMPERATURES["single_pipeline"],
        )
    except LLMError as exc:
        raise AiAssistUnavailable(str(exc), status_code=exc.status_code) from exc


def validate_draft_module_spec(data: dict[str, Any]) -> list[str]:
    """Return warnings; raise ValueError on hard invalid technical names."""
    warnings: list[str] = []
    tech = data.get("technical_name")
    if not isinstance(tech, str) or not _TECHNICAL_RE.fullmatch(tech):
        raise ValueError(
            "draft.technical_name must be lowercase python-module style (a-z0-9_)"
        )
    if not data.get("display_name"):
        warnings.append("display_name missing — defaulting may be required")
    models = data.get("models")
    if not isinstance(models, list) or not models:
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
    reuse_models: list[str] | None = None,
    reuse_views: list[dict[str, Any]] | None = None,
    reuse_actions: list[dict[str, Any]] | None = None,
    reuse_plan: ReusePlan | None = None,
    scaffold: dict[str, Any] | None = None,
    matched_pack_id: str | None = None,
) -> str:
    parts = [prompt.strip()]
    parts.append(
        "Follow these model-creation rules exactly:\n" + MODEL_CREATION_RULES
    )
    exemplar = few_shot_exemplar_block(matched_pack_id)
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
    if available_models:
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
) -> tuple[dict[str, Any], str, list[str], list[dict[str, Any]]]:
    """Return (draft_dict, raw_response, warnings, refusals). Never mutates Odoo."""
    from app.ai_component_builder import draft_component_from_prompt
    from app.ai_grain import classify_grain
    from app.ai_rules import strip_protected_module_effects
    from app.protected_modules import refresh_connection_protected_manifest

    grain = grain_override or classify_grain(prompt)
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
        warnings = _dedupe_warnings(comp_warnings + late_w + validate_draft_module_spec(draft))
        raw = json.dumps(
            {"grain": grain, "component": True, "connect_points": draft.get("connect_points")}
        )
        return draft, raw, warnings, refusals

    reuse_plan = plan_reuse(
        prompt,
        available_models=available_models,
        installed_modules=installed_modules,
        operator_reuse=reuse_models,
    )
    effective_reuse = list(
        dict.fromkeys([*(reuse_models or []), *reuse_plan.models])
    )

    mode = (pipeline or settings.ai_pipeline_mode or "single").strip().lower()
    if mode == "staged":
        try:
            draft, raw, warnings = run_staged_pipeline(
                prompt,
                reuse_models=effective_reuse,
                protected_manifest=protected_manifest,
                odoo_version=odoo_version,
            )
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
            return draft, raw, warnings, refusals
        except LLMError as exc:
            raise AiAssistUnavailable(str(exc), status_code=exc.status_code) from exc

    warnings: list[str] = []
    provider = get_llm_provider()
    retrieved = retrieve_domain_pack(prompt, provider=provider)
    matched = (retrieved[0], retrieved[1]) if retrieved else None
    scaffold = matched[1] if matched else None

    enriched_prompt = _build_prompt_with_context(
        prompt,
        available_models=available_models,
        reuse_models=effective_reuse,
        reuse_views=reuse_views,
        reuse_actions=reuse_actions,
        reuse_plan=reuse_plan,
        scaffold=scaffold,
        matched_pack_id=matched[0] if matched else None,
    )

    raw = ""
    draft: dict[str, Any] | None = None

    if provider is not None:
        try:
            raw = provider.generate_json(enriched_prompt, system=_SYSTEM_PROMPT)
            draft = _extract_json_object(raw)
        except (LLMError, ValueError, json.JSONDecodeError) as exc:
            if matched:
                warnings.append(f"LLM draft failed ({exc}); using domain pack")
                draft = matched[1]
                raw = raw or json.dumps(draft)
            else:
                raise AiAssistUnavailable(str(exc), status_code=getattr(exc, "status_code", 503)) from exc
    elif matched:
        draft = matched[1]
        raw = json.dumps(draft)
        score = retrieved[2] if retrieved else 0.0
        warnings.append(
            f"AI assist off — used curated domain pack '{matched[0]}' "
            f"(retrieval score={score:.2f})"
        )
    else:
        raise AiAssistUnavailable(
            "AI assist is disabled and no domain pack matched. "
            "Set AI_ASSIST=ollama (depth floors still apply when the LLM is on), "
            "or prompt a known domain pack as offline fallback "
            "(car rental, hospital, law firm, clinic, field service)."
        )

    assert draft is not None

    # Pure-AI repair: emit omitted scaffold models before pack merge fills them
    if matched and provider is not None:
        draft, gap_notes = llm_emit_missing_scaffold_models(
            provider, draft, matched[1], user_prompt=prompt
        )
        warnings.extend(gap_notes)
        draft, seed_notes = seed_missing_core_scaffold_models(draft, matched[1])
        warnings.extend(seed_notes)

    if matched:
        draft, pack_warnings = merge_domain_pack(draft, matched[1])
        warnings.extend(pack_warnings)

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
            ambition=str(draft.get("_ambition") or "standard"),
            provider=provider,
            expand_llm=True,
        )
        warnings.extend(q_w)
        draft, depth_w = run_depth_pass(
            draft,
            user_prompt=prompt,
            provider=provider,
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

    warnings.extend(validate_draft_module_spec(draft))
    draft, warnings, refusals = _apply_pcm_strip(
        draft,
        protected_manifest=protected_manifest,
        odoo_version=odoo_version,
        client=client,
        warnings=warnings,
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
