"""Staged ModuleSpec generation pipeline (design §3).

Steps 0 + 6 are deterministic. Steps 1–5 call the LLM with small JSON tasks
when a provider is available; otherwise the retrieved pack is used as the draft.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai_domain_packs import merge_domain_pack, retrieve_domain_pack
from app.ai_depth import AMBITION_TARGETS, classify_ambition
from app.ai_enrich import enrich_draft_module_spec
from app.ai_model_quality import MODEL_CREATION_RULES, min_fields_for_ambition, seed_missing_core_scaffold_models
from app.ai_rules import validate_and_enrich_draft
from app.ai_workflow import step4_workflow_models
from app.ai_prompt_constants import (
    STEP_TEMPERATURES,
    append_prompt_blocks,
)
from app.llm_provider import (
    FORMAT_SCHEMA_AUTOMATIONS,
    FORMAT_SCHEMA_ENTITIES,
    FORMAT_SCHEMA_FIELDS,
    FORMAT_SCHEMA_RELATIONSHIPS,
    LLMError,
    LLMProvider,
    _is_timeout_error,
    get_llm_provider,
)
from app.protected_modules import guardrail_prompt, refresh_connection_protected_manifest


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start_obj, end_obj = text.find("{"), text.rfind("}")
        start_arr, end_arr = text.find("["), text.rfind("]")
        if start_arr >= 0 and end_arr > start_arr and (
            start_obj < 0 or start_arr < start_obj
        ):
            return json.loads(text[start_arr : end_arr + 1])
        if start_obj >= 0 and end_obj > start_obj:
            return json.loads(text[start_obj : end_obj + 1])
        raise


def _slug_model(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
    if not slug.startswith("x_"):
        slug = f"x_{slug}"
    return slug[:64]


def _minimal_entity_fields(entity: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = [
        {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
        {"name": "x_notes", "ttype": "text", "string": "Notes"},
    ]
    if entity.get("is_workflow"):
        fields.append(
            {
                "name": "x_status",
                "ttype": "selection",
                "string": "Status",
                "selection": (
                    "[('draft','Draft'),('open','Open'),"
                    "('done','Done'),('cancelled','Cancelled')]"
                ),
            }
        )
    return fields


def seed_unpacked_draft(
    prompt: str,
    *,
    briefing: Any,
    ambition: str,
) -> dict[str, Any]:
    """Deterministic stub so app-bar density can finish when the LLM times out."""
    from app.ai_document_shape import (
        naming_from_residual,
        seed_register_from_brief,
        stamp_document_shape,
    )
    from app.ai_operator_brief import attach_operator_brief

    display, slug = naming_from_residual(prompt)
    tech = slug or (re.sub(r"[^a-z0-9_]+", "_", prompt.lower())[:40].strip("_") or "custom_app")
    brief = briefing.to_dict() if hasattr(briefing, "to_dict") else {}
    draft = {
        "technical_name": tech,
        "display_name": display or tech.replace("_", " ").title(),
        "depends": ["base", "mail"],
        "models": [],
        "smart_buttons": [],
        "automations": [],
        "_ambition": ambition,
        "_user_prompt": prompt,
        "_domain_briefing": brief,
    }
    attach_operator_brief(draft, user_prompt=prompt)
    shape = stamp_document_shape(draft, prompt=prompt)
    if shape == "register":
        seed_register_from_brief(draft, prompt=prompt)
        return draft

    from app.ai_domain_density import ensure_domain_density
    from app.ai_odoo_app_bar import ensure_residual_satellites, ensure_stock_inherit_bridges
    from app.ai_stock_first import attach_reuse_plan_to_draft

    attach_reuse_plan_to_draft(draft, user_prompt=prompt)
    if shape not in {"field_pack", "stock_reuse", "catalog"}:
        ensure_domain_density(draft, user_prompt=prompt, ambition=ambition)
        ensure_residual_satellites(draft)
        ensure_stock_inherit_bridges(draft)
    return draft


_STUDIO_SPEC_KEYS: tuple[str, ...] = (
    "technical_name",
    "display_name",
    "depends",
    "models",
    "views",
    "menus",
    "actions",
    "access_rules",
    "smart_buttons",
    "automations",
    "sequences",
    "reuse",
    "reuse_stock",
    "reuse_hints",
    "anti_patterns",
    "grain",
    "groups",
    "custom_code_blocks",
    "_pack_model_ids",
)


def seed_studio_draft(prompt: str) -> dict[str, Any]:
    """Durable Draft Studio start: capability gold/refuse, pack, else unpacked seed.

    This is the fallback when the staged LLM cannot finish inside the job budget.
    """
    import copy

    from app.ai_depth import classify_ambition
    from app.ai_domain_briefing import build_domain_briefing
    from app.ai_domain_packs import match_domain_pack
    from app.ai_generation_engine import (
        attach_generation_engine,
        classify_generation,
        maybe_seed_from_capability,
    )
    from app.ai_llm_status import attach_llm_status
    from app.ai_operator_brief import attach_operator_brief

    capability_seed = maybe_seed_from_capability(prompt)
    if capability_seed:
        return capability_seed

    plan = classify_generation(prompt)
    if plan.grain == "field_pack":
        from app.ai_component_builder import draft_component_from_prompt

        draft, _hosts, _warnings = draft_component_from_prompt(prompt, grain=plan.grain)
        draft["_user_prompt"] = prompt
        draft["_pipeline"] = "component_grain"
        attach_operator_brief(draft, user_prompt=prompt)
        attach_llm_status(draft, mode="seed_fallback", reason="component_grain")
        attach_generation_engine(draft, prompt, user_phase="review")
        return draft

    matched = match_domain_pack(prompt)
    if matched:
        pack_id, pack = matched
        draft: dict[str, Any] = {
            key: copy.deepcopy(pack[key]) for key in _STUDIO_SPEC_KEYS if key in pack
        }
        draft.setdefault("technical_name", re.sub(r"[^a-z0-9_]+", "_", pack_id)[:64])
        draft.setdefault("display_name", str(pack.get("display_name") or pack_id))
        draft.setdefault("depends", ["mail", "contacts"])
        draft.setdefault("models", [])
        draft["domain_pack"] = pack_id
        draft["grain"] = "full_app"
        draft["_user_prompt"] = prompt
        attach_operator_brief(draft, user_prompt=prompt)
        draft["_pipeline"] = "pack_seed"
        attach_llm_status(draft, mode="pack_fallback")
        attach_generation_engine(draft, prompt, user_phase="building")
        if not draft.get("_pack_model_ids"):
            draft["_pack_model_ids"] = [
                str(m.get("model"))
                for m in (draft.get("models") or [])
                if isinstance(m, dict) and m.get("model")
            ]
        if draft.get("models"):
            return draft
    ambition = classify_ambition(prompt)
    draft = seed_unpacked_draft(
        prompt,
        briefing=build_domain_briefing(prompt),
        ambition=ambition,
    )
    draft["_pipeline"] = "honesty_seed"
    attach_llm_status(draft, mode="pack_fallback", reason="honesty_seed")
    attach_operator_brief(draft, user_prompt=prompt)
    attach_generation_engine(draft, prompt, user_phase="building")
    return draft


def _llm_json(
    provider: LLMProvider,
    *,
    system: str,
    prompt: str,
    reasoning: bool = False,
    format_schema: dict[str, Any] | None = None,
    temperature: float | None = None,
    timeout_s: float = 120.0,
    step: str = "draft_json",
) -> Any:
    from app.ai_llm_budget import llm_json_with_budget

    raw, _down = llm_json_with_budget(
        provider,
        step,
        prompt,
        system=system,
        reasoning=reasoning,
        format_schema=format_schema,
        temperature=temperature,
    )
    return _extract_json(raw)


def _step1_instruction(shape: str, max_entities: int) -> str:
    """Entity-list instruction. Workspace asks for a vertical; thin shapes do not."""
    if shape == "register":
        return (
            "Reply ONLY with a JSON array of ONE entity — the paper-register residual "
            "named in the operator brief (Custom residual). name = residual slug; "
            "purpose = residual display name. Do not copy placeholder wording into "
            "the live description. Example output:\n"
            '[{"name":"named_residual","purpose":"Named residual",'
            '"is_workflow":false,"loop_role":"transaction"}]\n'
            "Do NOT invent a FULL vertical (no sites, parties, billing, compliance, "
            "rate cards, satellites). Do NOT set is_workflow. Aim for 1 entity. "
            "Custom Odoo models will be prefixed x_.\n"
            + MODEL_CREATION_RULES
        )
    if shape == "field_pack":
        return (
            "Reply ONLY with a JSON array. This brief is a field pack: return []. "
            "Do not invent new x_* entities or a FULL vertical.\n"
            + MODEL_CREATION_RULES
        )
    if shape == "stock_reuse":
        return (
            "Reply ONLY with a JSON array. This brief is stock reuse: return []. "
            "Do not invent x_* entities.\n"
            + MODEL_CREATION_RULES
        )
    if shape == "catalog":
        return (
            "Reply ONLY with a JSON array of catalog/master entities named in the brief. "
            "Do not invent billing, workflow, or a FULL operational vertical. "
            f"Aim for at most {max_entities} entities.\n"
            + MODEL_CREATION_RULES
        )
    return (
        "Reply ONLY with a JSON array of SUBSTANTIVE entities for a serious ops app. "
        "Example output:\n"
        '[{"name":"matter","purpose":"open legal matter with client and counsel",'
        '"is_workflow":true,"loop_role":"transaction"}]\n'
        "loop_role one of: master|transaction|line|event|billing|compliance. "
        "Cover a FULL vertical named from the prompt nouns: sites/facilities, "
        "parties, engagements/projects, booking documents + lines, deliverables, "
        "equipment, rate cards, agreements, unavailability, revisions, job-cost "
        "expenses. Crew is hr.employee (not x_staff). Invoices are account.move "
        "(not a parallel x_bill). "
        "FORBIDDEN filler entities: deposit, party_link, generic task/event/"
        "document/staff, type, category, tag, stage, priority, status, kind. "
        f"Aim for {max_entities} entities (≥60% for comprehensive). "
        "Custom Odoo models will be prefixed x_. Prefer too many rich entities over "
        "lookup tables.\n"
        + MODEL_CREATION_RULES
    )


def step1_entities(
    provider: LLMProvider,
    prompt: str,
    scaffold: dict[str, Any] | None,
    *,
    max_entities: int = 12,
    guardrail: str = "",
    briefing_block: str = "",
    document_shape: str = "",
) -> list[dict[str, Any]]:
    from app.ai_domain_pack_law_firm import scaffold_teaching_blob

    scaffold_hint = ""
    if scaffold and document_shape not in {"register", "field_pack", "stock_reuse", "catalog"}:
        # Prefer rich teaching blob; fall back to names if truncated empty
        teach = scaffold_teaching_blob(scaffold, max_chars=3500)
        scaffold_hint = (
            "World-class scaffold to match or exceed (adapt names):\n" + teach
            if teach
            else "Scaffold models to adapt: "
            + str(
                [
                    m.get("model")
                    for m in (scaffold.get("models") or [])
                    if isinstance(m, dict)
                ]
            )
        )
    system = append_prompt_blocks(
        _step1_instruction(document_shape, max_entities),
        guardrail=guardrail,
        user_prompt=prompt,
    )
    user = (
        "## Original operator message (verbatim — authoritative)\n"
        f"{prompt}\n\n{scaffold_hint}"
    )
    if briefing_block:
        user = f"{briefing_block}\n\n{user}"
    data = _llm_json(
        provider,
        system=system,
        prompt=user,
        reasoning=False,
        format_schema=FORMAT_SCHEMA_ENTITIES,
        temperature=STEP_TEMPERATURES["pipeline.entities"],
        step="entities",
    )
    if not isinstance(data, list):
        data = data.get("entities") if isinstance(data, dict) else []
    out = []
    for row in data or []:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        name = str(row["name"]).strip().lower().replace(" ", "_")
        # Drop catalog-only entity proposals early
        leaf = name.replace("x_", "").split("_")[-1]
        if leaf in {
            "type",
            "types",
            "category",
            "categories",
            "tag",
            "tags",
            "stage",
            "stages",
            "priority",
            "priorities",
            "status",
            "kind",
        }:
            continue
        out.append(
            {
                "name": name,
                "purpose": str(row.get("purpose") or row["name"]),
                "is_workflow": False
                if document_shape == "register"
                else bool(row.get("is_workflow")),
                "loop_role": str(row.get("loop_role") or ""),
            }
        )
    return out


def step2_fields(
    provider: LLMProvider,
    entity: dict[str, Any],
    scaffold_fields: list[dict[str, Any]] | None,
    *,
    min_fields: int = 6,
    guardrail: str = "",
    user_prompt: str = "",
    briefing_block: str = "",
    document_shape: str = "",
) -> list[dict[str, Any]]:
    hint = ""
    if scaffold_fields:
        hint = "Baseline fields (adapt/extend): " + json.dumps(scaffold_fields)[:2000]
    thin = document_shape in {"register", "field_pack", "stock_reuse", "catalog"}
    need = 1 if thin else min_fields + (2 if entity.get("is_workflow") else 0)
    if thin:
        field_rules = (
            "Reply ONLY with JSON array of fields for one Odoo custom model. "
            'Each: {"name":"x_field","ttype":"char|selection|many2one|date|datetime|text|float|boolean",'
            '"string":"Label","required":false,"selection":"[(\'a\',\'A\')]",'
            '"relation":"x_other|res.partner|hr.employee"}. '
            "Always include x_name. Emit ONLY columns the operator brief named — do not pad "
            "to a field floor with x_notes, x_status, x_code, x_company_id, or x_currency_id. "
            "Labels copy the brief (time in ≠ check-in unless the brief said check-in). "
            "Do not add res.company / res.currency / res.users unless the brief named them. "
            "Selection as Odoo python-literal string.\n"
            + MODEL_CREATION_RULES
        )
    else:
        field_rules = (
            "Reply ONLY with JSON array of fields for one Odoo custom model. "
            'Each: {"name":"x_field","ttype":"char|selection|many2one|date|datetime|text|float|boolean",'
            '"string":"Label","required":false,"selection":"[(\'a\',\'A\')]",'
            '"relation":"x_other|res.partner|res.users|res.company|res.currency"}. '
            f"Always include x_name. Return AT LEAST {need} fields. "
            "Include ≥1 many2one when the entity participates in an ops graph. "
            "If workflow: include x_status (+ rich selection) and x_code. "
            "Put type/priority/stage as selection fields — never imply a separate catalog model. "
            "Selection as Odoo python-literal string.\n"
            + MODEL_CREATION_RULES
        )
    system = append_prompt_blocks(
        field_rules,
        guardrail=guardrail,
        user_prompt=user_prompt,
    )
    prompt = (
        f"Entity: {entity['name']}\nPurpose: {entity['purpose']}\n"
        f"Workflow: {entity.get('is_workflow')}\nLoop role: {entity.get('loop_role')}\n"
        f"Minimum fields: {need}\n{hint}"
    )
    if user_prompt:
        prompt = f"User app request:\n{user_prompt}\n\n{prompt}"
    if briefing_block:
        prompt = f"{briefing_block}\n\n{prompt}"
    data = _llm_json(
        provider,
        system=system,
        prompt=prompt,
        reasoning=False,
        format_schema=FORMAT_SCHEMA_FIELDS,
        temperature=STEP_TEMPERATURES["pipeline.fields"],
        step="fields",
    )
    if isinstance(data, dict):
        data = data.get("fields") or []
    fields: list[dict[str, Any]] = []
    for f in data or []:
        if not isinstance(f, dict) or not f.get("name"):
            continue
        name = str(f["name"])
        if not name.startswith("x_"):
            name = f"x_{name}"
        fields.append({**f, "name": name})
    if not any(f.get("name") == "x_name" for f in fields):
        fields.insert(
            0,
            {
                "name": "x_name",
                "ttype": "char",
                "string": "Name",
                "required": True,
            },
        )
    # One retry if the model returned a thin field list
    if len(fields) < need:
        retry = _llm_json(
            provider,
            system=system,
            prompt=(
                prompt
                + f"\n\nPrevious attempt only had {len(fields)} fields — TOO THIN. "
                f"Return ≥{need} substantive fields now."
            ),
            reasoning=False,
            format_schema=FORMAT_SCHEMA_FIELDS,
            temperature=STEP_TEMPERATURES["pipeline.fields"],
        )
        if isinstance(retry, dict):
            retry = retry.get("fields") or []
        for f in retry or []:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            name = str(f["name"])
            if not name.startswith("x_"):
                name = f"x_{name}"
            if any(existing.get("name") == name for existing in fields):
                continue
            fields.append({**f, "name": name})
    return fields


def step3_relationships(
    provider: LLMProvider,
    models: list[dict[str, Any]],
    *,
    guardrail: str = "",
    user_prompt: str = "",
    document_shape: str = "",
) -> list[dict[str, Any]]:
    summary = [
        {
            "model": m.get("model"),
            "fields": [f.get("name") for f in (m.get("fields") or [])[:20]],
        }
        for m in models
    ]
    extra = ""
    if document_shape in {"register", "field_pack", "stock_reuse", "catalog"}:
        extra = (
            " Thin shape: do not add x_company_id, x_currency_id, or res.users "
            "unless the brief named them."
        )
    system = append_prompt_blocks(
        "Reply ONLY with JSON array of relationship fixes: "
        '[{"model":"x_a","field":"x_b_id","ttype":"many2one","relation":"x_b",'
        '"string":"B"}]. Only additions/corrections.'
        + extra,
        guardrail=guardrail,
        user_prompt=user_prompt,
    )
    data = _llm_json(
        provider,
        system=system,
        prompt=f"Models so far:\n{json.dumps(summary)}",
        reasoning=True,
        format_schema=FORMAT_SCHEMA_RELATIONSHIPS,
        temperature=STEP_TEMPERATURES["pipeline.relationships"],
        step="relationships",
    )
    if isinstance(data, dict):
        data = data.get("relationships") or []
    return [r for r in (data or []) if isinstance(r, dict)]


def step5_automations(
    provider: LLMProvider,
    draft: dict[str, Any],
    *,
    guardrail: str = "",
    user_prompt: str = "",
    document_shape: str = "",
) -> list[dict[str, Any]]:
    extra = ""
    if document_shape == "register":
        extra = (
            " Register: at most one on_time duration alert if the brief asked; "
            "clock the header datetime (not create_date). No x_status writes."
        )
    system = append_prompt_blocks(
        "Reply ONLY with JSON array of automations: "
        '[{"name":"...","model":"x_...","trigger":"on_write|on_time",'
        '"description":"...","filter_domain":"[]",'
        '"safe_actions":[{"kind":"object_write","field":"x_status","value":"..."}]}]. '
        "No Python code. Prefer object_write / next_activity / mail_post."
        + extra,
        guardrail=guardrail,
        user_prompt=user_prompt,
    )
    data = _llm_json(
        provider,
        system=system,
        prompt=f"ModuleSpec models/workflows:\n{json.dumps(draft.get('models'), default=str)[:4000]}",
        reasoning=True,
        format_schema=FORMAT_SCHEMA_AUTOMATIONS,
        temperature=STEP_TEMPERATURES["pipeline.automations"],
        step="automations",
    )
    if isinstance(data, dict):
        data = data.get("automations") or []
    return [a for a in (data or []) if isinstance(a, dict)]


def run_staged_pipeline(
    prompt: str,
    *,
    provider: LLMProvider | None = None,
    reuse_models: list[str] | None = None,
    protected_manifest: dict[str, Any] | None = None,
    odoo_version: str | None = None,
) -> tuple[dict[str, Any], str, list[str]]:
    """Full Step 0–6 (+ rules). Returns (draft, raw_trace, warnings)."""
    warnings: list[str] = []
    trace: list[str] = []
    provider = provider if provider is not None else get_llm_provider()

    manifest = protected_manifest or refresh_connection_protected_manifest(
        server_version=odoo_version,
        client=None,
    )
    guard = guardrail_prompt(manifest)

    from app.ai_domain_briefing import build_domain_briefing
    from app.ai_document_shape import classify_document_shape, naming_from_residual

    briefing = build_domain_briefing(prompt)
    brief_block = briefing.prompt_block()
    shape = classify_document_shape(prompt)

    # Step 0 — retrieval (workspace / transactional_header only)
    retrieved = None
    if shape not in {"register", "field_pack", "stock_reuse", "catalog"}:
        retrieved = retrieve_domain_pack(prompt, provider=provider)
    scaffold: dict[str, Any] | None = None
    pack_id: str | None = None
    if retrieved:
        pack_id, scaffold, score = retrieved
        warnings.append(f"step0: retrieved domain pack '{pack_id}' (score={score:.2f})")
        trace.append(f"step0:{pack_id}:{score:.2f}")

    draft: dict[str, Any]

    if provider is None:
        if scaffold is None:
            raise LLMError(
                "Staged pipeline needs AI_ASSIST provider or a matching domain pack",
                status_code=503,
            )
        draft = copy_pack(scaffold)
        draft["_ambition"] = classify_ambition(prompt)
        draft["_user_prompt"] = prompt
        draft["_domain_briefing"] = briefing.to_dict()
        warnings.append("step1-5 skipped (no LLM) — using domain pack + Odoo app bar")
    else:
        try:
            ambition = classify_ambition(prompt)
            if shape in {"field_pack", "stock_reuse"}:
                draft = seed_unpacked_draft(
                    prompt, briefing=briefing, ambition=ambition
                )
                warnings.append(f"step1-5 skipped — document_shape={shape}")
                trace.append(f"step1:skipped_shape={shape}")
            else:
                max_ent = (
                    1
                    if shape == "register"
                    else int(AMBITION_TARGETS[ambition]["max_entities_staged"])
                )
                warnings.append(
                    f"step1: ambition={ambition} shape={shape} max_entities={max_ent}"
                )
                step1_was_timeout = False
                try:
                    entities = step1_entities(
                        provider,
                        prompt,
                        scaffold,
                        max_entities=max_ent,
                        guardrail=guard,
                        briefing_block=brief_block,
                        document_shape=shape,
                    )
                except (LLMError, ValueError, json.JSONDecodeError) as exc:
                    warnings.append(f"step1 LLM failed ({exc})")
                    entities = []
                    step1_was_timeout = isinstance(exc, LLMError) and _is_timeout_error(
                        exc
                    )
                if shape == "register" and entities:
                    _display, slug = naming_from_residual(prompt)
                    leaf = (slug or "").replace("x_", "")
                    preferred = [
                        e
                        for e in entities
                        if leaf and leaf in str(e.get("name") or "")
                    ]
                    entities = (preferred or entities)[:1]
                elif len(entities) > max_ent:
                    entities = entities[:max_ent]
                trace.append(f"step1:entities={len(entities)}")
                if not entities and scaffold:
                    warnings.append("step1 empty — falling back to pack models")
                    draft = copy_pack(scaffold)
                elif not entities:
                    why = "timed out" if step1_was_timeout else "empty"
                    warnings.append(f"step1 {why} — seeding unpacked draft")
                    draft = seed_unpacked_draft(
                        prompt, briefing=briefing, ambition=ambition
                    )
                else:
                    scaffold_by_model = {
                        m["model"]: m
                        for m in (scaffold or {}).get("models") or []
                        if isinstance(m, dict) and m.get("model")
                    }
                    models: list[dict[str, Any]] = []
                    for ent in entities:
                        mid = _slug_model(ent["name"])
                        sc = None
                        for sm, smdef in scaffold_by_model.items():
                            if sm.endswith(mid.removeprefix("x_")) or mid in sm:
                                sc = smdef
                                mid = sm
                                break
                        try:
                            fields = step2_fields(
                                provider,
                                ent,
                                (sc or {}).get("fields") if sc else None,
                                min_fields=min_fields_for_ambition(ambition),
                                guardrail=guard,
                                user_prompt=prompt,
                                briefing_block=brief_block,
                                document_shape=shape,
                            )
                        except (LLMError, ValueError, json.JSONDecodeError) as exc:
                            warnings.append(f"step2 skipped for {ent['name']}: {exc}")
                            if shape == "register":
                                tmp: dict[str, Any] = {"models": []}
                                from app.ai_document_shape import seed_register_from_brief

                                seed_register_from_brief(tmp, prompt=prompt)
                                fields = list(
                                    (tmp.get("models") or [{}])[0].get("fields") or []
                                ) or _minimal_entity_fields(ent)
                            else:
                                fields = _minimal_entity_fields(ent)
                        models.append(
                            {
                                "model": mid,
                                "description": ent["purpose"].title()
                                if len(ent["purpose"]) < 40
                                else ent["name"].replace("_", " ").title(),
                                "mode": "new",
                                "is_workflow": ent.get("is_workflow"),
                                "fields": fields,
                            }
                        )
                    trace.append(f"step2:models={len(models)}")

                    try:
                        rels = step3_relationships(
                            provider,
                            models,
                            guardrail=guard,
                            user_prompt=prompt,
                            document_shape=shape,
                        )
                        by_model = {m["model"]: m for m in models}
                        for rel in rels:
                            m = by_model.get(rel.get("model"))
                            if not m:
                                continue
                            fname = rel.get("field") or rel.get("name")
                            if not fname:
                                continue
                            fname = str(fname)
                            if not fname.startswith("x_"):
                                fname = f"x_{fname}"
                            existing = {
                                f.get("name")
                                for f in (m.get("fields") or [])
                                if isinstance(f, dict)
                            }
                            if fname in existing:
                                continue
                            if shape == "register" and fname in {
                                "x_company_id",
                                "x_currency_id",
                                "x_user_id",
                            }:
                                continue
                            m.setdefault("fields", []).append(
                                {
                                    "name": fname,
                                    "ttype": rel.get("ttype") or "many2one",
                                    "string": rel.get("string") or fname,
                                    "relation": rel.get("relation"),
                                }
                            )
                        trace.append(f"step3:rels={len(rels)}")
                    except (LLMError, ValueError, json.JSONDecodeError) as exc:
                        warnings.append(f"step3 skipped: {exc}")

                    try:
                        models, step4_w = step4_workflow_models(
                            provider, models, user_prompt=prompt, guardrail=guard
                        )
                        warnings.extend(step4_w)
                        trace.append("step4:workflows")
                    except (LLMError, ValueError, json.JSONDecodeError) as exc:
                        warnings.append(f"step4 skipped: {exc}")

                    tech = re.sub(r"[^a-z0-9_]+", "_", prompt.lower())[:24].strip("_") or "custom_app"
                    draft = {
                        "technical_name": (scaffold or {}).get("technical_name") or tech,
                        "display_name": (scaffold or {}).get("display_name")
                        or tech.replace("_", " ").title(),
                        "depends": list((scaffold or {}).get("depends") or ["base"]),
                        "models": models,
                        "smart_buttons": list((scaffold or {}).get("smart_buttons") or []),
                        "automations": [],
                        "_ambition": ambition,
                        "_user_prompt": prompt,
                        "_domain_briefing": briefing.to_dict(),
                    }
                    if scaffold and shape not in {"register", "catalog"}:
                        draft, seed_notes = seed_missing_core_scaffold_models(draft, scaffold)
                        warnings.extend(seed_notes)
                        draft, pack_w = merge_domain_pack(draft, scaffold)
                        warnings.extend(pack_w)

                    try:
                        autos = step5_automations(
                            provider,
                            draft,
                            guardrail=guard,
                            user_prompt=prompt,
                            document_shape=shape,
                        )
                        if autos:
                            draft["automations"] = autos
                        elif scaffold and scaffold.get("automations"):
                            draft["automations"] = list(scaffold["automations"])
                        trace.append(f"step5:autos={len(draft.get('automations') or [])}")
                    except (LLMError, ValueError, json.JSONDecodeError) as exc:
                        warnings.append(f"step5 skipped: {exc}")
                        if scaffold and scaffold.get("automations"):
                            draft["automations"] = list(scaffold["automations"])
        except (LLMError, ValueError, json.JSONDecodeError) as exc:
            if scaffold is not None:
                warnings.append(f"staged LLM failed ({exc}); using pack")
                draft = copy_pack(scaffold)
            else:
                warnings.append(f"staged LLM failed ({exc}); seeding unpacked draft")
                draft = seed_unpacked_draft(
                    prompt,
                    briefing=briefing,
                    ambition=classify_ambition(prompt),
                )

    if pack_id:
        draft["domain_pack"] = pack_id
    draft["_user_prompt"] = prompt
    draft["_domain_briefing"] = briefing.to_dict()
    if reuse_models:
        draft.setdefault("reuse", {})["models"] = list(reuse_models)

    # Step 6 — deterministic views/menus
    draft, enrich_w = enrich_draft_module_spec(
        draft, reuse_models=reuse_models
    )
    warnings.extend(enrich_w)
    trace.append("step6:views")

    # Rules engine
    draft, rule_w, _errs = validate_and_enrich_draft(draft)
    warnings.extend(rule_w)
    trace.append("rules")

    draft["_pipeline"] = {"mode": "staged", "trace": trace}
    return draft, "\n".join(trace), warnings


def copy_pack(scaffold: dict[str, Any]) -> dict[str, Any]:
    import copy

    return copy.deepcopy(scaffold)
