# AI-2 prompt audit (2026-08-02)

| Step / prompt | Temp | Concrete example | Output ONLY JSON | Closed ttype vocab | Anti-pattern block | Protected guardrail |
|---|---:|---|---|---|---|---|
| pipeline.entities | 0.6 | yes | yes | yes | yes | yes (staged) |
| pipeline.fields | 0.15 | yes | yes | yes | yes | yes |
| pipeline.relationships | 0.15 | yes | yes | yes | yes | yes |
| pipeline.automations | 0.6 | yes | yes | yes | yes | yes |
| single_pipeline system | 0.3 | yes (schema block) | yes | via append | yes | yes |
| critique | 0.15 | yes | yes | yes | yes | yes |
| quality.scaffold_gap | 0.15 | yes | yes | yes | yes | no (repair pass) |
| quality.field_deepen | 0.15 | yes | yes | yes | yes | no |
| depth.expand | 0.15 | yes | yes | yes | yes | no |

Exemplar rule: `few_shot_exemplar_block()` skips when matched pack id equals `car_rental` (exemplar source pack).

Constants module: `apps/api/app/ai_prompt_constants.py` (`STEP_TEMPERATURES` table).
