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
from app.ai_model_quality import MODEL_CREATION_RULES, min_fields_for_ambition, seed_missing_core_scaffold_models, seed_missing_core_scaffold_models
from app.ai_rules import validate_and_enrich_draft
from app.ai_workflow import step4_workflow_models
from app.ai_workflow import step4_workflow_models
from app.ai_prompt_constants import (
    STEP_TEMPERATURES,
    append_prompt_blocks,
)
from app.ai_prompt_constants import (
    STEP_TEMPERATURES,
    append_prompt_blocks,
)
from app.llm_provider import (
    FORMAT_SCHEMA_ENTITIES,
    FORMAT_SCHEMA_FIELDS,
    FORMAT_SCHEMA_RELATIONSHIPS,
    LLMError,
    LLMProvider,
    get_llm_provider,
)


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


def _llm_json(
    provider: LLMProvider,
    *,
    system: str,
    prompt: str,
    reasoning: bool = False,
    format_schema: dict[str, Any] | None = None,
    temperature: float | None = None,
) -> Any:
    raw = provider.generate_json(
        prompt,
        system=system,
        reasoning=reasoning,
        format_schema=format_schema,
        temperature=temperature,
    )
    return _extract_json(raw)


def step1_entities(
    provider: LLMProvider,
    prompt: str,
    scaffold: dict[str, Any] | None,
    *,
    max_entities: int = 12,
    guardrail: str = "",
) -> list[dict[str, Any]]:
    from app.ai_domain_pack_law_firm import scaffold_teaching_blob

    scaffold_hint = ""
    if scaffold:
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
        "Reply ONLY with a JSON array of SUBSTANTIVE entities for a serious ops app. "
        "Example output:\n"
        '[{"name":"matter","purpose":"open legal matter with client and counsel",'
        '"is_workflow":true,"loop_role":"transaction"}]\n'
        "loop_role one of: master|transaction|line|event|billing|compliance. "
        "Cover the full operational loop (staff, transaction, lines, events, tasks, "
        "expenses, deposits/holds, party links, documents, billing). "
        "FORBIDDEN as entities: type, category, tag, stage, priority, status, kind "
        "(those are selection fields on parents, not models). "
        f"Aim for {max_entities} entities (≥60% for comprehensive). "
        "Custom Odoo models will be prefixed x_. Prefer too many rich entities over "
        "lookup tables.\n"
        + MODEL_CREATION_RULES,
        guardrail=guardrail,
    )
    data = _llm_json(
        provider,
        system=system,
        prompt=f"User app request:\n{prompt}\n\n{scaffold_hint}",
        reasoning=False,
        format_schema=FORMAT_SCHEMA_ENTITIES,
        temperature=STEP_TEMPERATURES["pipeline.entities"],
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
                "is_workflow": bool(row.get("is_workflow")),
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
) -> list[dict[str, Any]]:
    hint = ""
    if scaffold_fields:
        hint = "Baseline fields (adapt/extend): " + json.dumps(scaffold_fields)[:2000]
    need = min_fields + (2 if entity.get("is_workflow") else 0)
    system = (
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
    prompt = (
        f"Entity: {entity['name']}\nPurpose: {entity['purpose']}\n"
        f"Workflow: {entity.get('is_workflow')}\nLoop role: {entity.get('loop_role')}\n"
        f"Minimum fields: {need}\n{hint}"
    )
    data = _llm_json(
        provider,
        system=system,
        prompt=prompt,
        reasoning=False,
        format_schema=FORMAT_SCHEMA_FIELDS,
        temperature=STEP_TEMPERATURES["pipeline.fields"],
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
) -> list[dict[str, Any]]:
    summary = [
        {
            "model": m.get("model"),
            "fields": [f.get("name") for f in (m.get("fields") or [])[:20]],
        }
        for m in models
    ]
    data = _llm_json(
        provider,
        system=(
            "Reply ONLY with JSON array of relationship fixes: "
            '[{"model":"x_a","field":"x_b_id","ttype":"many2one","relation":"x_b",'
            '"string":"B"}]. Only additions/corrections.'
        ),
        prompt=f"Models so far:\n{json.dumps(summary)}",
    )
    if isinstance(data, dict):
        data = data.get("relationships") or []
    return [r for r in (data or []) if isinstance(r, dict)]


def step5_automations(
    provider: LLMProvider,
    draft: dict[str, Any],
) -> list[dict[str, Any]]:
    data = _llm_json(
        provider,
        system=(
            "Reply ONLY with JSON array of automations: "
            '[{"name":"...","model":"x_...","trigger":"on_write|on_time",'
            '"description":"...","filter_domain":"[]",'
            '"safe_actions":[{"kind":"object_write","field":"x_status","value":"..."}]}]. '
            "No Python code. Prefer object_write / next_activity / mail_post."
        ),
        prompt=f"ModuleSpec models/workflows:\n{json.dumps(draft.get('models'), default=str)[:4000]}",
    )
    if isinstance(data, dict):
        data = data.get("automations") or []
    return [a for a in (data or []) if isinstance(a, dict)]


def run_staged_pipeline(
    prompt: str,
    *,
    provider: LLMProvider | None = None,
    reuse_models: list[str] | None = None,
) -> tuple[dict[str, Any], str, list[str]]:
    """Full Step 0–6 (+ rules). Returns (draft, raw_trace, warnings)."""
    warnings: list[str] = []
    trace: list[str] = []
    provider = provider if provider is not None else get_llm_provider()

    # Step 0 — retrieval
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
        draft = scaffold
        warnings.append("step1-5 skipped (no LLM) — using domain pack")
    else:
        try:
            ambition = classify_ambition(prompt)
            max_ent = int(AMBITION_TARGETS[ambition]["max_entities_staged"])
            warnings.append(f"step1: ambition={ambition} max_entities={max_ent}")
            entities = step1_entities(
                provider, prompt, scaffold, max_entities=max_ent, guardrail=guard
            )
            # Drop excess only after generation; keep up to max_ent
            if len(entities) > max_ent:
                entities = entities[:max_ent]
            trace.append(f"step1:entities={len(entities)}")
            if not entities and scaffold:
                warnings.append("step1 empty — falling back to pack models")
                draft = copy_pack(scaffold)
            else:
                scaffold_by_model = {
                    m["model"]: m
                    for m in (scaffold or {}).get("models") or []
                    if isinstance(m, dict) and m.get("model")
                }
                models: list[dict[str, Any]] = []
                for ent in entities:
                    mid = _slug_model(ent["name"])
                    # Prefer scaffold model with similar leaf name
                    sc = None
                    for sm, smdef in scaffold_by_model.items():
                        if sm.endswith(mid.removeprefix("x_")) or mid in sm:
                            sc = smdef
                            mid = sm
                            break
                    fields = step2_fields(
                        provider,
                        ent,
                        (sc or {}).get("fields") if sc else None,
                        min_fields=min_fields_for_ambition(ambition),
                    )
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

                # Step 3 relationships
                try:
                    rels = step3_relationships(provider, models)
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
                            f.get("name") for f in (m.get("fields") or []) if isinstance(f, dict)
                        }
                        if fname in existing:
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

                # Step 4 — workflow states + transitions
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
                }
                if scaffold:
                    draft, seed_notes = seed_missing_core_scaffold_models(draft, scaffold)
                    warnings.extend(seed_notes)
                    draft, pack_w = merge_domain_pack(draft, scaffold)
                    warnings.extend(pack_w)

                # Step 5 automations
                try:
                    autos = step5_automations(provider, draft)
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
                draft = scaffold
            else:
                raise

    if pack_id:
        draft["domain_pack"] = pack_id
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
