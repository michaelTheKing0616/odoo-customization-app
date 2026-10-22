# CODE_MAP: App Studio (read 21 Oct 2026; line numbers drift, so search by symbol)

Workers read only the rows that their card's context pack names. `apps/api/` is abbreviated `api/`.

## Request path
| Step | File | Symbol (line) | Notes |
|---|---|---|---|
| Create session | `api/app/routers/ai_studio.py` | `create_session_route` (L581) | **RC1:** `prompt = expansion.expanded` (L637-639). Snapshot read pre-expansion (L630). Stock-app path `_create_stock_app_session` (L674). Inner `_create_session_inner` (L731) |
| Clarify / generate / apply | same | `/{id}/clarify` L821, `/{id}/generate` L957, `/{id}/install-apps` L1190, `/{id}/refine` L1450, `/{id}/apply` L1777 | 18 `except Exception` blocks in this file |
| Owner words | `api/app/ai_conversation/brief_checklist.py` | `set_original`, `source_brief` (L45), `expansion_context` (L49), `enabled` (L60, `INGENIUM_BRIEF_CHECKLIST`) | contextvar `_ORIGINAL` |
| Expansion | `api/app/ai_conversation/brief_expand.py` | `maybe_expand_brief` (L337), `not_vague_reason` (L103), `_enabled` (L86, `STUDIO_BRIEF_EXPAND` default on) | |
| Design orchestration | `api/app/ai_conversation/app_design.py` | `build_app_design` (L2685-2989) | adders: `_merge_outline` (L3056), `_cover_sections` (L3025), `strengthen_design` (design_quality). Returns `None` if fewer than `MIN_DESIGN_MODELS` |
| Contract call | same | `_call_intent_contract` (L836), `intent_contract_system_prompt` (L534), `_repair_model_roles` (L1238, `INGENIUM_ROLE_REASK`) | contract rows `{id, kind, subject, decision, origin, evidence:{quote,start,end}, role?}` |
| Design prompt | same | `design_system_prompt` (L1358), `design_user_prompt` (L1447; sends `Operator brief (full)` at L1504), `design_knobs` (L1335: `INGENIUM_DESIGN_RULES` v1, `_GAPFILL` keep, `_BUDGET` current, `_TEMPERATURE` 0.2), `model_budget_for` (L494) | |
| LLM call | same | `_call_llm` (L1537; catches only `LLMError`, `TimeoutError` at L1561), `_parse_json` (L1517), `design_timeout_for` (L1696), `_fallback_reason` (L2992) | |
| Data shapes | same | `DesignField` (L164), `DesignModel` (L178, has `evidence`, `suggested`, `requirement_ids`), `StockExtension` (L194), `AppDesign` (L219), `from_dict` | |
| Repair/validate | same | `validate_and_repair` (L1842), `_admission_repair` (L1803), `_model_name` (L1706), `_field_name` (L1712) | |
| Outline fallback | same | `outline_from_brief` (L2561) | must read owner words only under v3 |
| Quality adders | `api/app/ai_conversation/design_quality.py` | `strengthen_design`, `dedupe_fields`, `ensure_jobs`, `complete_from_brief`, `scope_and_limits`; authorizer hook at L740-794 (`INGENIUM_MODEL_AUTHORIZER` off/shadow/on; `INGENIUM_RECORD_DIR`; `INGENIUM_SHADOW_LOG`) | |
| Authorizer | `api/app/ai_conversation/model_authorizer.py` | `norm` (L27), `stems` (L32), `verbatim` (L38), `_gather` (L88), `_credit_each_owner_phrase_once` (L111), `_decide` (L142; rules 0-7), `authorize_models` (L179), `_keep_lines`, `apply_calls`, `authorize_python`, `apply_python_gate`, `orphan_requirements` | **RC3:** stem binding at L95-104 and L111-127 |
| Scope gate | `api/app/ai_conversation/design_scope.py` | `authorize`, `ensure_install_suggestions` | |
| Orphan repair | `api/app/ai_conversation/orphan_repair.py` | `mode` (L19, `INGENIUM_ORPHAN_REPAIR` off), `repair_step` | |
| Agent mode | `api/app/ai_conversation/studio_agent.py` | `mode` (L29, `INGENIUM_STUDIO_MODE` pipeline) | out of v3 scope |
| Grounding / exclusions | `api/app/ai_conversation/clause_grounding.py` | `enabled` (L48, off), `must_not_violations` | reuse the clause splitter |
| Stock routing | `api/app/ai_conversation/stock_routing.py` | `enforce_stock_first`, `align_checks_by_id` | |
| Automations | `api/app/ai_conversation/automation_records.py` | | rule → stock automation |
| Install | `api/app/ai_conversation/install_step.py` | | write gate unchanged (INV-14) |
| Snapshot | `api/app/odoo_snapshot.py` | `snapshot_for_connection`, `.digest`, `.fingerprint`, `.ok`, `.major`, `.models` | |

## Providers
| File | Symbol | Notes |
|---|---|---|
| `api/app/llm_provider.py` | `LLMError` (L142), `LLMProvider.generate_json` (L513), `OpenAICompatibleProvider` (L697; json_schema at L786), `GeminiProvider` (L1064; `generate_json` discards `format_schema`, L1222), `get_llm_provider_for_tier` | **RC5** |

## Eval harness (`api/evals/v2/`)
| File | Symbol |
|---|---|
| `score.py` | `run_case` (L61), `score` (L137), `s7_metrics` (L265), `config_fingerprint` (L321), `main` (L367); env `EVAL_CONNECTION`, `EVAL_FRESH`, `EVAL_UNSEAL` |
| `metrics.py` | `run_metrics` (L23), `hboot` (L53), `summarize` (L96), `paired` (L100) |
| `replay.py` | `downstream` (L36), `main` (L51) |
| others | `fold_audit.py`, `metamorphic.py`, `rescore.py`, `contract_experiment.py`, `design_experiment.py`, `FEWSHOT_MANIFEST.json` |
| sets | `dev/` (20), `dev2/` (8), `holdout/` (8, burnt → dev2 role), `holdout_fresh/` (13, **sealed**), `unseen/` (3). Gold: `<id>.gold.yaml` (needs, entities, relations, automations, access_rules, exclusions, context_only, ambiguity_points, routes). No `spans:` yet. `bakery_ng`, `event_hire`, `clinic_intake` are marked RECONSTRUCTED |
| fixture | `api/tests/fixtures/customer_health_brief.md` (1,664 words; headline brief, no eval file) |

## Web (App Studio UI, `apps/web/src/components/studio/`)
`StudioShell.tsx`, `StudioBriefScreen.tsx`, `StudioProgress.tsx`, `StudioGenerationStates.tsx`, `ClarifyInterstitial.tsx`, `AppDesignPanel.tsx`, `SuggestionChip.tsx`, `StudioHonestyBanners.tsx`, `ReviewRefineLayout.tsx`, `StudioPreviewPane.tsx`, `StudioStageRail.tsx`; hooks `use-studio-session.ts`, `use-studio-review.ts`, `use-studio-page.ts`. Tests sit next to their components (`*.test.tsx`).

## Not in the tree yet (v3 creates these)
`api/app/ai_conversation/studio_profile.py` (AS-PROFILE), `studio_outcome.py` + `brief_normalise.py` (AS-TOTAL), `schema_tools.py` (AS-DECODE), `retrieval.py` (AS-RETRIEVE), `brief_ledger.py` (AS-LEDGER-SCHEMA), `ledger_vote.py` (AS-STABILITY), `ledger_call.py` (AS-LEDGER-CALL), `ledger_compile.py` (AS-COMPILE), `ledger_questions.py` (AS-QUESTIONS), `conservation.py` (AS-CONSERVE), `ledger_polish.py` (AS-REPAIR), `host_fit.py` (AS-HOST-PREINSTALL), `v3_pipeline.py` (AS-V3-WIRE, the only orchestrator), `v3_shadow.py` (AS-SHADOW); tests `api/tests/test_<module>.py` per card, `test_studio_outcome_total.py` (AS-ROBUST-FUZZ); `api/evals/v2/tests/test_metrics_v3.py`.

Reused guards (read only): `api/app/ai_client/guards.py` — `fence_untrusted` (L43), `classify_injection` (L181), `Redactor` (L331). Existing contract call: `app_design._call_intent_contract` (L836; `verifier`, `parallel` keyword args; reads `source_brief` at L882). Validator: `validate_and_repair` (L1842; no `strict_refs` argument).
