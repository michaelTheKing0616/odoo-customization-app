# Wave 18 — ELITE: developer-grade AI module generation (2026-08-12)

North star: NL → review-ready ModuleSpec that scores ≥9/10, exports a zip with Python,
reports, mail, cron, tests, and i18n — sandbox-validated before promote. Eliminates the
need for developers on declarative + Option A Community apps (PCM boundaries unchanged).

Order: ELITE-1 → ELITE-7. Each card has pytest gate + fixture/scorecard floor.

---

## ELITE-1 — Generation reliability (staged default + budgets)

- [x] `AI_PIPELINE_MODE` default `staged` (override via env).
- [x] Configurable step budgets via settings (`ai_generation_step_budget_*` / shared ladder).
- [x] `AI_GENERATION_CLOUD_PREFERRED` flag documented — use `openai-compatible` for SLO.
- [x] `_llm_status.mode` must be `llm_full` or `llm_partial` (not `pack_fallback`) for
      `elite_promote_gate` on comprehensive ambition prompts.
- [x] Gate: `uv run pytest tests/test_wave18_elite.py -k reliability -q`

## ELITE-2 — NL → sandboxed Python (`custom_code_blocks`)

- [x] `run_elite_python_pass`: deterministic `@api.constrains`, compute methods, cron hooks
      on workflow/loan/line models; lint via `lint_custom_code_blocks`.
- [x] Optional LLM augmentation when provider available (constraints from field graph).
- [x] Never live-apply — export + sandbox only (Option A).
- [x] Gate: pytest `elite_python` — library/loan draft gets ≥1 lint-clean block.

## ELITE-3 — NL → reports / mail / cron artifacts

- [x] `run_elite_artifacts_pass`: mail_templates, cron_jobs, reports on document models.
- [x] `draft_dict_to_module_spec` maps mail + cron into `ModuleSpec`.
- [x] Gate: pytest `elite_artifacts` — zip render contains mail_templates.xml + reminders.

## ELITE-4 — Promote autopilot (scorecard-gated sandbox)

- [x] `elite_promote_gate(draft)` — score ≥ `ELITE_SCORECARD_FLOOR` (9.0), lint ok, shape ok.
- [x] `POST /connections/{id}/module-spec/elite-autopilot` — export zip → sandbox → validation_id.
- [x] Fix `export-sandbox` `record_sandbox_validation` kwargs (module_name + zip_bytes).
- [x] Wizard: **Validate module** + **Promote module** buttons with score chip gate.
- [x] Gate: pytest `elite_promote` + route test (mock sandbox ok path).

## ELITE-5 — PCM-safe integration patterns

- [x] `run_elite_integration_pass`: wire `account.move` / `stock.picking` link-only fields +
      smart buttons when prompt mentions billing/inventory (reuse apply-readiness helpers).
- [x] No tier-1 writes — link-only M2O + stat buttons only.
- [x] Gate: pytest `elite_integration` — billing prompt adds `x_invoice_id` link, no parallel x_invoice model.

## ELITE-6 — Library domain pack + vertical coverage

- [x] `library_management` pack registered (books, loans, fines, reservations, branches).
- [x] Tags: library, book, loan, member, reservation, fine, isbn, overdue.
- [x] Gate: pytest `library_pack` — match + merge yields ≥6 models.

## ELITE-7 — Generated tests + i18n in module zip

- [x] `run_elite_quality_pass`: emit `tests/test_smoke.py` + `i18n/<module>.pot` via
      `custom_code_blocks` source_file paths.
- [x] Gate: pytest `elite_quality` — zip contains tests + pot entries.

---

## Scorecard floors (Wave 18 regression)

Fixture: `apps/api/tests/fixtures/draft_library_elite_2026-08-12.json`

| Dimension   | Floor |
|-------------|-------|
| overall     | 9.0   |
| domain_fit  | 8.0   |
| structure   | 8.5   |
| semantics   | 8.5   |
| ux          | 8.0   |
| hygiene     | 8.0   |

Validators: no xml_findings; consistency_findings ≤ 2 for library fixture.

Full gate: `uv run pytest tests/test_wave18_elite.py -q`
