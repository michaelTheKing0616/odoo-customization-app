# Ingenium next phase — progress log

Build spec: `docs/plans/next-phase/00_INDEX.md` (the single-file spec remains, with a redirect header).

## 2026-10-02 — ingestion and plan

Track: planning only. No product code.
Intent: Ingest `/Users/temitopeolaitanmichael/Downloads/ingenium new phase` and write one build spec that keeps every source gate.
Escalation pressure: not scored. The deliverable is a synthesis with a clear done condition and an easy revert (a markdown file).
Files:
- `docs/plans/INGENIUM_NEXT_PHASE_CONSOLIDATED_BUILD_SPEC.md` created
- `.cursor/rules/adaptive-agent.mdc` created
- Personal Agent Store skills installed (339 Prime, 8 workflow, 16 adaptive). Escalation-pressure heuristic appended to adaptive `02-model-routing`.
Gates claimed: none of the product gates. Planning gate only: the spec exists and lists source checksums, closed decisions, and open decisions.
Evidence: checksums recorded in the spec §2.2. Skill counts recorded at install time: PRIME_SKILLS=339, WORKFLOW_SKILLS=8, ADAPTIVE_SKILLS=16, linked=361.
Negative tests: not applicable.
Not done: §5 baseline against the tree. Implementation of every track. Mac §9 operator paste.

## 2026-10-02 — decisions and client approver grant
Track: 6B.1 auth slice
Intent: Lock D3, D6, D7, D9. Keep self-hosted login. Add Microsoft OAuth config. Enforce Client Approver as a one-connection grant.
Files: `account_models.py`, `account_service.py`, `client_access.py`, `workspace_auth.py`, `routers/accounts.py`, `oauth_service.py`, `settings.py`, alembic `m3n4o5p6q7r8`, `OAuthProviderButtons.tsx`, tests.
Gates claimed: D9 negative API test — approver for client A gets 404 on client B, 403 on consultant routes.
Evidence: `.venv` pytest `tests/test_client_approver_isolation.py` + `tests/test_accounts.py` — 10 passed.
Negative tests: `test_client_approver_cannot_reach_a_second_client`, `test_client_path_policy_hides_other_connections`.
Not done: full approval inbox UI, hash-chained audit shared with Track 5, SAML, D7 compilers.
Risks introduced: none in product code. Risk of treating the master spec's open D1/D2 as still open is called out; MEMORY wins.

## 2026-10-02 — build pack
Track: planning only. No product code.
Intent: Replace the summary spec with `docs/plans/next-phase/` so every source gate is in the pack, plus D10, D11, and D12.
Model / band: not scored. Documentation, easy to revert.
Files: `docs/plans/next-phase/*.md` (23 files), redirect header on the old spec, `AGENTS.md`, `.cursor/rules/session-defaults.mdc`, `MEMORY.md`, `STATE.md`.
Commands and results: ID-count script VERIFIED (INV 20, RT 48, C 20, GATE-P* complete, GATE-L4 12, YAML 47, version rows 32, DoD 1–40). Independent checker [Check pack ID coverage](c6791225-3987-4adb-9a98-5baecdeff139) PASS on those families plus 188 skills.
Gates passed: coverage-matrix count check. No product gate.
Negative tests: not applicable.
Not done: BL-01 against a fresh tree, every track, Mac §9 operator paste, pen-test, L4 eligibility evidence.
Risks introduced: GATE-L4 thresholds are authored, not copied. They stay flagged for confirm before L4 is enabled.

## 2026-10-02 — baseline cards BL-02 through BL-06
Track: BL
Intent: First implementation slice. Orchestrator, Composer 2.5 workers, separate tester and reviewer.
Model / band: workers and tester and reviewer on Composer 2.5. Pressure 3–6.
Files: `apps/api/app/request_id.py`, `apps/api/app/logging_config.py`, `apps/api/app/main.py`, `apps/api/tests/test_request_id.py`, `apps/api/tests/test_logging_config.py`, `apps/api/pyproject.toml`, `apps/api/scripts/lint_new_modules.sh`, `.github/workflows/ci.yml`, `docs/adr/ADR-01.md`–`ADR-14.md`, `docs/verified-facts.md`, `docs/recon.md`, `docs/plans/next-phase/BL04_LINT_SLOT.md`.
Commands and results: VERIFIED. pytest `tests/test_request_id.py` + `tests/test_logging_config.py` — 9 passed. ruff on those two modules clean. First tester run missed the venv path; the re-run from the repo root passed.
Gates passed: BL-02, BL-03, BL-04 (tsc not in CI: 13 pre-existing errors), BL-05, BL-06. BL-01 was the earlier baseline doc.
Negative tests: unsafe `X-Request-Id` is not echoed; a log line containing `password` is dropped; a broken format string does not raise.
Not done: L4, D8 gateway, Odoo 20 compose, hash-chained audit, Mac §9.
Risks introduced: JSON logging is an extra handler, not a replacement of every existing handler. A bad format is dropped rather than emitted.
Follow-ups closed this pass: `view_has_field` is live on Live/Fake and stubbed on Catalog/Deny (recorded in T1 and verified-facts). L4 thresholds unchanged and L4 cards not started. D8 stays open (ADR-02).

## 2026-10-02 — Track 5A kernel
Track: 5A
Intent: Risk classification, plan fingerprint, hash-chained audit, power-ops forbidden gate, Odoo 20 compose file, PR-F.0 test.
Model / band: Composer 2.5 workers. Reviewer: Claude Sonnet on the security modules. Pressure 14 on classify and audit.
Files: `apps/api/app/rpc_classify.py`, `plan_fingerprint.py`, `audit_chain.py`, `db_models.py` (AuditChainEntry), `power_ops_recipes.py` (`_exec_step` only), alembic `n4o5p6q7r8s9` and `o5p6q7r8s9t0`, tests listed below, `docker/docker-compose.odoo20.yml`, `docker/run-odoo20-smoke.sh`, CI pytest list.
Commands and results: VERIFIED. pytest of the new modules — 22 passed after the review fix, then power-ops and MCP scan included (worker reported 15 passed on the combined classify/power/mcp run).
Gates passed: 5A-01, 5A-03 (fingerprint helper), 5A-04 (never-allowed, including apikeys reads and config key shape), 5A-05 (chain and tamper, canonical_ts), 5A-07 (static scan, zero MCP write hits), 5A-08 and 5A-09 (`policy_allows`). O20-01 file only (image not pulled). PR-F.0 asserted in a test, generate behavior unchanged.
Negative tests: approved=True does not clear forbidden; database.secret as a `key` value is forbidden; tuple payloads redact password; power-ops unlink of res.users does not call execute_kw.
Not done: dry-run hash on every write tool in Tracks 1, 3, and 4 (only power-ops `_exec_step`). Snapshot-before-destructive. YAML config-as-code. Bridge. UI migration. Bot engine. L4. Odoo 20 image boot.
Review: first pass FAIL on config-parameter shape and tuple redaction ([Review classify and audit](47ce04b2-4384-4ccf-9c40-7304a2f3933e)). Fix [Fix classify and redaction gaps](57f5bcc7-4094-46c2-ae6a-9694605ef822). Re-review PASS ([Re-review classify fixes](d22935dc-012a-43c7-bee2-eadfb0efcf82)).
Risks introduced: READ methods other than on apikeys are still auto-allowed, including read of ir.config_parameter. The chain is a new table, not yet written by the HTTP middleware.

## 2026-10-02 — write guard and production snapshot
Track: 5A
Intent: Forbidden RPC cannot leave the API client. Production destructive routes require a snapshot id.
Files: `packages/odoo-client/src/odoo_client/client.py` (`rpc_guard`), `apps/api/app/rpc_guard.py`, `odoo_service.py`, `script_runner/child_main.py`, `snapshot_gate.py`, `safety_gate.py`, `safety_dependency.py`, tests `test_rpc_guard.py`, `test_snapshot_gate.py`.
Commands and results: VERIFIED. pytest those tests plus `test_safety_gate.py` and `test_power_ops_forbidden.py` — 16 passed.
Gates: never-allowed is checked inside `execute_kw` for clients built by `client_from_connection` and the script runner. Standard and observer connections are unchanged. Production `destructive` and `code` routes refuse without header `X-Snapshot-Id` pointing at a `metadata_snapshots` row for that connection.
Negative: unlink `res.users`, any `res.users.apikeys` call, and `database.secret` in kwargs raise before transport. A partner `search_read` is not marked forbidden.
Not done: dry-run hash on every write tool. HTTP middleware still does not append to the hash chain. DESTRUCTIVE calls that are not forbidden (module install on Community) still proceed on standard write mode.
Risks: clients constructed without `rpc_guard` bypass the check. Package unit tests do that on purpose.

## 2026-10-02 — close the three bypasses
Track: 5A
Intent: Forbidden RPC is in the client itself. Every JSON live write with dry_run false needs a matching dry-run. Mutating HTTP requests append to the hash chain.
Files: `packages/odoo-client/src/odoo_client/rpc_policy.py`, `client.py` (`builtin_forbidden` always, then scrub), `apps/api/app/dry_run_ledger.py`, `dry_run_middleware.py`, `main.py`, `audit.py`, `power_ops_recipes.py`, `rpc_classify.py` (sets now come from the package), tests `test_rpc_policy.py`, `test_dry_run_ledger.py`, `test_audit.py`.
Commands and results: VERIFIED. Combined pytest of the guard, dry-run, audit, classify, power-ops, and trust receipt tests — 46 passed. Audit test asserts an `http_mutation` chain row. Write-mode package tests — 9 passed including that re-run.
What this closes:
- A client with `rpc_guard` left unset still cannot unlink users, touch API keys, or send a protected parameter.
- `search_read` of `ir.config_parameter` drops rows whose key is a protected parameter, so the value is not returned.
- Any JSON request with `dry_run: false` is refused with `dry_run_receipt_required` until the same parameters were posted with `dry_run: true`. Confirmation fields are not part of the hash. `run_recipe` enforces the same rule for direct calls.
- The HTTP audit middleware writes the hash-chained row in the same transaction as `audit_logs`.
Not this slice: Bridge, the bot engine, the UI migration, booting the Odoo 20 image, and L4. Those are later cards, not unfinished pieces of this gate.

## 2026-10-02 — Bridge Tier I, config spec, Odoo 20 access
Track: 3, 5B, 9
Intent: The next unfinished product surfaces, fail closed, with tests.
Files: `apps/api/app/bridge/contract.py`, `routers/bridge.py`, `config_as_code/loader.py`, `odoo20/access_compiler.py`, `tests/test_bridge_and_config_spec.py`, `safety_registry.py`, `main.py`, `pyproject.toml` (PyYAML declared).
Commands and results: VERIFIED. pytest `test_bridge_and_config_spec.py` and `test_safety_gate.py` — 19 passed.
Gates: Tier I rejects a missing conflict rule, a money entity without money_policy, an inline api_key, and an inlined odoo_target block. Config spec has all 47 sections in apply order, rejects a literal password and an `x_studio_` field, and compiles a stable plan fingerprint. Odoo 20 access compiles to `ir.access` and refuses a group `ir.rule` and a written `kind`. Odoo 19 still compiles a domain right to `ir.model.access` plus `ir.rule`.
Not done: Shopify connector, queue tables, applying the YAML plan to a live database, the Odoo 20 Docker image boot, the bot engine, and the UI migration.

## 2026-10-02 — Protected registry RT-10–RT-16
Track: T8 Phase 3, GATE-P3-05
Intent: A core registry blocks composite expansion, `$ref`, widened batches, lock-date and module side effects, stored computes, server-action tricks, and journal-sequence aliases before any journal write. Tenants can add targets and cannot remove core ones.
Files: `apps/api/app/changeset/protected_registry.py`, `protected_core.yaml`, `policy.py`, `handlers.py`, `validate.py`, `executor.py`, `dispatch.py`, `plan_card.py`, `tests/test_protected_registry.py`.
Commands and results: VERIFIED. pytest of the registry plus the changeset, dispatch, runtime, and plan-card tests — 64 passed.
Review: [Review protected registry](f4788622-4392-45e7-afa4-76d343af4fa8) PASS after the bypass fixes. Plan-card and dispatch now receive the changeset, so a resolvable ref to `sale.order` stays R2.
Not done: the other Phase 3 engine suites (round-trip on a live database, crash injection against a killed process, policy mutation score, plan-card goldens reviewed by a person). This registry does not install the bridge or write a customer database.


## 2026-10-02 — Build pack v2 (docs only)
Files: `docs/plans/next-phase/cards/*.md` (15 files), `13`, `14` (generated index, 330 cards), `00`, `03` §B, `17`, `18`; `AGENTS.md`, `MEMORY.md`, `STATE.md`.
Commands and results: `len(OP_CATALOG)` = 62, which equals the family tables (script diff); `len(all_skills())` = 188; oracle names = 129; the relative links in the cards all resolve.
Not done: an independent checker subagent on v2. BL-07 and BL-08 are open. T8 statuses must be re-measured because of the concurrent edits.

CLAIM BL-07 2026-10-03T06:23:18Z files: apps/api/tests/test_no_mcp_write.py

## 2026-10-03 — BL-07
Track: BL
Intent: The MCP write scan ignores tool caches and still fails on a planted write.
Model / band: composer-2.5-fast worker (bbe3d61c-6b90-474a-8ceb-c3400ead8e12); composer-2.5-fast tester (af586d2c-061d-42e3-93f8-342ffa196be6). Pressure 2. No reviewer (pressure under 14, tester passed once).
Files: `apps/api/tests/test_no_mcp_write.py`
Commands and results: VERIFIED. `pytest -q tests/test_no_mcp_write.py` — 2 passed in 5.94s (cache present). `pytest -q -p no:cacheprovider tests/test_no_mcp_write.py` — 2 passed in 6.00s. No `planted_mcp_write_probe.py` left under `apps/api/app/`.
Gates passed: BL-07 acceptance — scan passes with `.pytest_cache` populated; planted `mcp.execute_kw("res.partner", "write", ...)` is still detected.
Negative tests: `test_mcp_scan_detects_planted_write_in_app_tree`.
Not done: BL-08 commit hygiene. Needs an explicit yes from Tope. Not started.
Risks introduced: paths outside the repo root are scanned when a test passes them in. Cache directory names are skipped. `_line_allowed` was not widened. `apps/api/app/` is still scanned.

CLAIM BL-08 2026-10-03T06:30:45Z files: product modules by track (no .cache, no .pnpm-store, no 0001-*.patch). Tope said yes to start and to commit. Do not push.

## 2026-10-03 — BL-08
Track: BL
Intent: Commit the uncommitted product slices by track. Do not push.
Model / band: composer-2.5-fast worker (e7db649d-ab31-4d1d-8699-6f8ae9bc71ba); composer-2.5-fast tester (4d94aad5-f0b7-4580-bf4d-55c72a440d7d). Pressure 6. No reviewer.
Files: 26 commits on `premium-local-tip` from `139ddf3` through `473fbcf`. Not pushed.
Commands and results: VERIFIED. `git status -sb` shows ahead 44 of `origin/premium-local-tip`. Product paths under apps/, packages/, docker/, docs/, odoo_addons/, and skills/ are clean. Worker-reported pytest per slice is in that worker's return; the tester did not re-run the suite. One slice (`807a62e`) failed two understand tests until `473fbcf` (must-do AST). After that fix the worker reported 284 passed.
Gates passed: BL-08 — no untracked product module; forbidden paths (`.cache/`, `.pnpm-store/`, `0001-*.patch`, `APPLY_INVENT_FAMILIES_ARC3_ON_MAC.sh`, secrets) are not in `f155e2b..HEAD`. `.env.example` only.
Negative tests: none named. Push was not done.
Not done: push. Needs a separate yes.
Risks introduced: `473fbcf` changes `ai_constraint_ast.py` so a wave test would pass. It is a product fix, not only a commit split.

CLAIM UI-F00 2026-10-03T06:49:17Z files: the 13 tsc errors (e2e/overlay-editor.spec.ts, DesignerAdvancedFieldsAside.test.tsx, InstanceIdentity.test.tsx, ClarifyInterstitial.test.tsx, StudioHonestyBanners.tsx, capabilities.test.ts, studio-session.ts) and .github/workflows/ci.yml web job.

## 2026-10-03 — UI-F00
Track: T7
Intent: Clear the 13 web type errors and run typecheck in CI.
Model / band: composer-2.5-fast worker (68f26cc8-817e-4bdd-812a-93bc5d5ff887); composer-2.5-fast tester (2da0ff9d-1e4e-4ed4-a509-78074f05305c). Pressure 5. No reviewer.
Files: `apps/web/e2e/overlay-editor.spec.ts`, `DesignerAdvancedFieldsAside.test.tsx`, `InstanceIdentity.test.tsx`, `ClarifyInterstitial.test.tsx`, `StudioHonestyBanners.tsx`, `capabilities.test.ts`, `studio-session.ts`, `.github/workflows/ci.yml`.
Commands and results: VERIFIED. `pnpm --filter @odoo-custom/web typecheck` exit 0. CI job `web-unit` runs that command with no `continue-on-error`.
Gates passed: UI-F00 — typecheck exits 0; CI runs it.
Negative tests: no `@ts-ignore`, `@ts-expect-error`, or `: any` in the changed files.
Not done: this slice is uncommitted. Kit, axe, and screenshots are not in this card's acceptance boxes.
Risks introduced: `studio-session.ts` no longer reads `understanding.grain`. `StudioBusyLabel` now renders the text `Repairing…`.

CLAIM T1-PF 2026-10-03T07:03:19Z files: docs/plans/INGENIUM_NEXT_PHASE_PROGRESS.md only.

CLAIM T1-F0 2026-10-03T07:05:19Z files: apps/api/tests/test_pr_f0_entrypoint.py and the progress log. Seeded tests already 24 passed. Count-equality assertion is missing.

CLAIM T1-INST 2026-10-03T07:07:37Z files: docs/plans/INGENIUM_NEXT_PHASE_PROGRESS.md only. Do not commit .cache.

CLAIM T1-A1 2026-10-03T07:09:09Z files: apps/api/tests/test_ai_schema_client.py only. fields_get pass and fail are missing.

## 2026-10-03 — T1-A1
Track: T1
Intent: fields_get has a pass and a fail, matching model_exists and relation_ok.
Model / band: composer-2.5-fast worker (4aea71ca-8a2d-4269-961c-2fa15a5b268b); composer-2.5-fast tester (560ba7d6-fd89-4114-8afc-f59d29031874). Pressure 4.
Files: `apps/api/tests/test_ai_schema_client.py` (`test_fields_get_known_and_unknown`).
Commands and results: VERIFIED. pytest `tests/test_ai_schema_client.py` — 10 passed in 0.02s.
Gates passed: six assertions (pass and fail for model_exists, fields_get, relation_ok).
Negative tests: unknown model `fields_get` returns `{}`.
Not done: T1-A2 stale admit_and_apply.
Risks introduced: none. Product client code was not edited.

CLAIM T1-A2 2026-10-03T07:15:00Z files: apps/api/tests/test_ai_schema_client.py and, only if the admit path cannot be asserted from the test, the smallest call site the test must reach. Do not lengthen SCHEMA_CATALOG_TTL_S.

## 2026-10-03 — T1-A2
Track: T1
Intent: A stale catalog denies the client and does not admit a field through admit_and_apply.
Model / band: composer-2.5-fast worker (20f2072c-5528-4ee9-b0d3-fa3b5fb12b80); composer-2.5-fast tester (e445b82b-2902-4b0b-8743-a41049866dee). Pressure 4.
Files: `apps/api/tests/test_ai_schema_client.py` (`test_admit_and_apply_stale_catalog_never_admits_stock_m2o_field`); `apps/api/app/ai_generate_ir.py` (`_stale_catalog_rejects_stock_field`).
Commands and results: VERIFIED. pytest schema client + entrypoint + spine — 37 passed in 1.73s. `SCHEMA_CATALOG_TTL_S = 15 * 60` unchanged.
Gates passed: stale factory deny; admit_and_apply rejects with `stale_or_missing_catalog_ts`.
Negative tests: the new admit test is the rejection case.
Not done: none on this card.
Risks introduced: stock many2one invent is refused when the schema client is deny-on-stale, even if a cue would otherwise match.

CLAIM T1-A3 2026-10-03T07:20:00Z files: progress log only. Re-measure, do not rebuild.

## 2026-10-03 — T1-A3
Track: T1
Intent: Record that field_is_writable is already implemented and tested.
Model / band: no worker. Deterministic re-measure. Pressure 4.
Files: none. Test already in `apps/api/tests/test_ai_schema_client.py`.
Commands and results: VERIFIED. `test_field_is_writable_rejects_readonly_related` — 1 passed in 0.02s.
Gates passed: T1-A3 implemented and tested.
Negative tests: the same test rejects a readonly related field.
Not done: none.
Risks introduced: none.







## 2026-10-03 — T1-PF (PF-1 through PF-6 re-verify)
Track: T1
Intent: Pre-flight answers with path or command evidence only. Progress log append; no product edits.
Model / band: composer-2.5-fast worker (T1-PF card). Pressure 5. No commit.

### PF-1 — `GenerateIR` / `build_ir` landed?
**Yes.** Command: `rg -n "def build_ir|class GenerateIR" apps/api/app/ai_generate_ir.py` → `33:class GenerateIR:` and `148:def build_ir(`.

### PF-2 — PR-A→F work landed (SEEDED cards only)?
**Partial — multiple SEEDED cards in** `docs/plans/next-phase/cards/T1_SCHEMA_GROUNDING.md` **with tests/code already present (not rebuilt this run):**
| Card | SEEDED evidence |
|------|-----------------|
| T1-F0 | `apps/api/tests/test_pr_f0_entrypoint.py` (`test_studio_generate_offline_finish_calls_seed_and_locked_craft`, `test_studio_generate_offline_finish_docstring_golden_entrypoint`) |
| T1-A1 | `apps/api/tests/test_ai_schema_client.py` (`test_model_exists_known_and_unknown`, `test_relation_ok_positive_and_negative`) |
| T1-A2 | same file: `test_factory_ttl_denies_stale_catalog`, `test_factory_missing_loaded_at_denies`; TTL `SCHEMA_CATALOG_TTL_S` in `apps/api/app/ai_schema_client.py` |
| T1-A3 | `test_field_is_writable_rejects_readonly_related` in `tests/test_ai_schema_client.py` |
| T1-B1 | `merge_proposals` in `apps/api/app/ai_generate_ir.py` + `ai_generate_ir_enforce.py`; `tests/test_generate_ir_closed_class.py` |
| T1-B2 | `tests/test_generate_ir_closed_class.py`: `test_maintenance_closed_ir_no_uncued_spray`, `test_maintenance_o2ms_subseteq_generate_ir` |
| T1-B3 | `test_service_cards_sibling_closed` (same closed-class module) |
| T1-C1 | `approved_craft` in `apps/api/app/ai_generate_ir.py`, `ai_enrich.py`, `ai_depth.py` (default-off test not named — card still SEEDED) |
| T1-D1 | `MAX_REPAIR` in `apps/api/app/ai_repair_loop.py`; `tests/test_option_a_prove_bar.py` (`test_three_install_fails_stamps_failed`, `test_fail_repair_then_ok_with_tests_stamps_proved`) |
| T1-D2 | `tests/test_option_a_prove_bar.py`: `test_smoke_only_success_leaves_prove_pending`, `test_run_tests_true_stamps_proved`, `test_sandbox_verify_and_repair_defaults_run_tests_true` |
| T1-E2 | Closed via T1-D2 (card says cite code path — same prove tests) |
| T1-F1 | `test_maintenance_closed_ir_no_uncued_spray` in `tests/test_generate_ir_closed_class.py` |
| T1-F2 | `test_service_cards_sibling_closed` in same file |
**Not SEEDED / still OPEN:** T1-INST, T1-C2, T1-D3, T1-E1, T1-F3 PARTIAL, T1-RET, etc. (per card file).

### PF-3 — `AI_IR_TRACE` on Maintenance; scrub-key hypothesis
**Script (card command) failed:** `AI_IR_TRACE=1 bash apps/api/scripts/dump_maintenance_ir_trace.sh` → exit 1: `apps/api/scripts/dump_maintenance_ir_trace.sh: line 5: cd: …/apps/apps/api: No such file or directory` (script `ROOT` resolves to `apps/`, not repo root).
**Equivalent trace produced manually from repo:** `cd apps/api && AI_IR_TRACE=1 AI_INTENT_LLM=off DATABASE_URL=sqlite+pysqlite:///:memory: AI_IR_TRACE_DIR=$REPO/.cache/ai_ir_trace ../../.venv/bin/python` (inline body from the script). Stamp **`20261003T080355`**; dumps under `.cache/ai_ir_trace/20261003T080355_*.json` (not committed).
**Scrub-key hypothesis (did scrub remove cued IR nodes?): refuted for GenerateIR closure scrub.** Pass `enforce_closed_generate_ir`: `"scrub_hits": []` in `.cache/ai_ir_trace/20261003T080355_enforce_closed_generate_ir.json`. Cued checklist/parts graph **appears** in pass `admit_and_apply` — quote from same stamp file `field_names`: `"x_maintenance_tickets.x_maintenance_tickets_checklist_line_ids"`, `"x_maintenance_tickets.x_maintenance_tickets_parts_line_ids"`, child models `x_maintenance_tickets_checklist_line.*`, `x_maintenance_tickets_parts_line.*`. **Separate apply-phase arch scrub did run** (stale view refs, not IR node deletion): `close_odoo_architecture:end` notes include `"apply: scrubbed 4 stale arch field ref(s) on x_maintenance_tickets"`. Closure note: `"generate_ir: purged unadmitted seed/generic models x_maintenance_tickets_line"`.

### PF-4 — Live RPC schema vs static only?
**Both paths; factory chooses.** `apps/api/app/ai_schema_client.py` → **`schema_client_for_draft`**: live RPC when `client is not None` → `LiveSchemaClient(client)`; else injected `draft["_schema_client"]`; else fresh catalog → `CatalogSchemaClient`; stale/missing catalog → `DenySchemaClient`. Static/deterministic: `FakeSchemaClient`, `CatalogSchemaClient`, `DenySchemaClient` in the same file.

### PF-5 — Sandbox `-i <module> --test-enable` non-interactive, parseable failures?
**Yes (unit-tested with fake compose).** Command: `cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_sandbox_test_enable.py` → **6 passed in 0.88s**. Cited test: `apps/api/tests/test_sandbox_test_enable.py::test_run_module_tests_failing_module_is_parseable` — asserts `ok is False` and `FAIL: test_ingenium_smoke.test_always_false` appears in `failures` and log; happy path asserts compose argv includes `--test-enable`, `--stop-after-init`, module name.

### PF-6 — PR-J1 landed (transport)?
**Transport: yes.** `packages/odoo-client/src/odoo_client/transport/json2.py` (`Json2Transport`, `POST /json/2/<model>/<method>`); wired in `packages/odoo-client/src/odoo_client/client.py` (`_connect_json2`, `_should_use_json2`, `execute_kw` on json2). Tests: `packages/odoo-client/tests/test_json2_transport.py`. **Live `/doc` parity smoke: no** — operator card **T2-J1** (`docs/plans/next-phase/cards/T2_JSON2.md`); this worker did not open a live Odoo instance.

## 2026-10-03 — T1-F0 (PR-F.0 entrypoint trace)
Track: T1
Intent: Document Studio Generate → `_finish_seed_draft` call chain; lock T1 invariant 2 (field / one2many / menu counts vs stamped `GenerateIR`) in tests.
Model / band: composer-2.5-fast worker (T1-F0 card). Pressure 9. No commit.

### PR-F.0 call chain (file:line)
1. `apps/web/src/app/connections/[id]/studio/page.tsx:347` — `api.generateStudioSession(session.id)` (also `:484`, `:661`, `:705`).
2. `apps/web/src/lib/api.ts:1554-1560` — `POST /api/ai/sessions/${sessionId}/generate`.
3. `apps/api/app/routers/ai_studio.py:384-385` — `generate_session_route` (`@router.post("/{session_id}/generate")`).
4. `apps/api/app/routers/ai_studio.py:474-496` — `enqueue_draft_job(..., build_draft_job_kwargs(...))`.
5. `apps/api/app/ai_draft_jobs.py:967-981` — `enqueue_draft_job` background worker → `run_draft_job_body`.
6. `apps/api/app/ai_draft_jobs.py:745` — `run_draft_job_body` (full_app residual path).
7. `apps/api/app/ai_draft_jobs.py:864-874` — `_finish_seed_draft(...)`.
8. Inside `_finish_seed_draft`: `apps/api/app/ai_draft_jobs.py:549` — `close_odoo_architecture`; `:554` — `stamp_generate_ir` (presumed GenerateIR entrypoint / closure stamp); `:558-570` — live-apply contract, scorecard, generation engine metadata, `sanitize_draft_payload`.
9. Live job tail (AI assist off): `apps/api/app/ai_draft_jobs.py:932-941` — `_apply_locked_craft_and_surface` after `_finish_seed_draft`.
10. Offline golden harness (PR-F.0): `apps/api/app/ai_draft_jobs.py:356-402` — `studio_generate_offline_finish` = `_finish_seed_draft` + `_apply_locked_craft_and_surface`.

**Post-entrypoint invent check:** On Maintenance harness, field / O2M / menu counts on the returned draft still equal `_generate_ir` after steps 8–10 (no retarget needed).

### Provisional labels (pre–F.0 write-up)
Any green **rubric battery** or **`_finish_seed_draft`-only** harness result recorded before this entry (including `DOCKET.md` PR-F.0 note and PF-2 SEEDED rows) is **provisional** until this call chain and invariant-2 assertion landed.

### Tests added
- `test_finish_seed_draft_invent_counts_match_generate_ir` — invariant 2 count equality after `_finish_seed_draft`.
- `test_finish_seed_draft_post_entrypoint_invent_fails_count_invariant` — unit double injects a field after `stamp_generate_ir`; assertion fails.

Commands and results: VERIFIED (this card). `cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_pr_f0_entrypoint.py tests/test_generate_ir_spine.py` → **26 passed in 1.86s**.
Gates passed: T1-F0 acceptance — call chain logged; count-equality assertion exists and passes.
Negative tests: post-entrypoint invent double in `test_pr_f0_entrypoint.py`.
Not done: no product/router edits; commit/push out of scope for this card.

## 2026-10-03 — T1-INST (AI_IR_TRACE on Maintenance; PF-3)
Track: T1
Intent: Run Maintenance `AI_IR_TRACE` dump; per-pass model/field node deltas; scrub-key hypothesis from dump evidence only.
Model / band: composer-2.5-fast worker (T1-INST card). Pressure 6. Change: this file only. No commit; `.cache` not committed.

### Command
From repo root: `AI_IR_TRACE=1 bash apps/api/scripts/dump_maintenance_ir_trace.sh` → **exit 1**: `line 5: cd: …/Odoo_Customization_App/apps/apps/api: No such file or directory` (`ROOT` in script resolves to `apps/`, not repo root).

### Dump path (newest stamp under `.cache/ai_ir_trace/`)
**Stamp:** `20261003T080355`  
**Directory:** `.cache/ai_ir_trace/`  
**Files:** `20261003T080355_*.json` (15 passes; pre-existing manual/offline run — not regenerated this worker turn).

### Scrub-key hypothesis (did closure scrub remove cued IR nodes?)
**Refuted for GenerateIR closure scrub.** Pass `enforce_closed_generate_ir` → `extra.closure.scrub_hits: []` in `.cache/ai_ir_trace/20261003T080355_enforce_closed_generate_ir.json`. Cued checklist/parts models and O2M fields remain in that pass’s `model_ids` / `field_names` (same file).  
**Related but not IR-node scrub:** notes `"generate_ir: purged unadmitted seed/generic models x_maintenance_tickets_line"` (generic seed line model, not checklist/parts). Apply-phase **view arch** scrub: `"apply: scrubbed 4 stale arch field ref(s) on x_maintenance_tickets"` on `close_odoo_architecture:end` and `finish_seed_draft:after_close` — no matching `model_ids` / `field_names` delta in those passes.

### Per-pass nodes added / removed (`model_ids` + `field_names` vs previous pass in pipeline order)
| Pass | Models added | Models removed | Fields added | Fields removed |
|------|--------------|----------------|--------------|----------------|
| `seed_studio_draft:honesty` | *(baseline)* `x_maintenance_tickets` | — | `x_maintenance_tickets.x_name`, `x_maintenance_tickets.x_state` | — |
| `after_deterministic_depth` | — | — | `x_maintenance_tickets.x_code` | — |
| `ensure_residual_must_do:before_admit` | — | `x_maintenance_tickets` | — | `x_maintenance_tickets.x_code`, `x_maintenance_tickets.x_name`, `x_maintenance_tickets.x_state` |
| `admit_and_apply` | `x_maintenance_tickets`, `x_maintenance_tickets_checklist_line`, `x_maintenance_tickets_parts_line` | — | cued O2M graph (12 fields: parent O2Ms + checklist/parts child fields) | — |
| `ensure_residual_must_do:after_admit` | — | `x_maintenance_tickets_checklist_line`, `x_maintenance_tickets_parts_line` | — | same 10 checklist/parts fields + 2 parent O2M fields |
| `compiler:rebuild_thin_menus:before_admit` | checklist + parts models | — | same 10 checklist/parts fields + 2 parent O2M fields | — |
| `compiler:rebuild_thin_menus:after_admit` | — | — | — | — |
| `enforce_closed_generate_ir` | — | — | — | — |
| `honor_operator_brief:start` | — | — | `x_maintenance_tickets.x_partner_id` | — |
| `honor_operator_brief:end` | — | — | — | `x_maintenance_tickets.x_partner_id` |
| `close_odoo_architecture:start` | — | checklist + parts models | — | same 10 + 2 O2M fields |
| `close_odoo_architecture:end` | checklist + parts models | — | same 10 + 2 O2M fields | — |
| `attach_operator_surface:start` | — | — | — | — |
| `attach_operator_surface:end` | — | — | — | — |
| `finish_seed_draft:after_close` | — | — | — | — |

Pass names listed (15): `seed_studio_draft:honesty`, `after_deterministic_depth`, `ensure_residual_must_do:before_admit`, `admit_and_apply`, `ensure_residual_must_do:after_admit`, `compiler:rebuild_thin_menus:before_admit`, `compiler:rebuild_thin_menus:after_admit`, `enforce_closed_generate_ir`, `honor_operator_brief:start`, `honor_operator_brief:end`, `close_odoo_architecture:start`, `close_odoo_architecture:end`, `attach_operator_surface:start`, `attach_operator_surface:end`, `finish_seed_draft:after_close`.

Gates passed: PF-3 answered with dump path under `.cache/ai_ir_trace/`; scrub-key refuted on `scrub_hits`; per-pass deltas from dump JSON only.
Not done: shell script fix (out of Change); fresh trace re-run blocked by script `cd` bug.

## 2026-10-03 — T1-B1
Track: T1
Intent: `merge_proposals` admits only (a) cued, (b) `STRUCTURAL_ALLOWLIST`, or (c) schema-verified reuse.
Files: `apps/api/app/ai_generate_ir.py` (`STRUCTURAL_ALLOWLIST`, 8 entries); `apps/api/tests/test_generate_ir_closed_class.py` (`test_uncued_not_allowlisted_not_schema_verified_rejected`).
Deleted leak paths: `source_cue==structural_default` tag, `quality_scaffold`, `pack_adopted`, `density_role`, `settings_craft`. Stale-catalog gate kept. TTL unchanged.
Commands and results: VERIFIED. pytest closed-class + spine + invent-leak + wave0 — 38 passed in 2.31s.
Negative tests: `test_uncued_not_allowlisted_not_schema_verified_rejected` (generic `res.partner` m2o tagged `structural_default`, and quality-scaffold `x_pad_field`).
Not done: T1-B2 named Rate Line case (already in spine; card still SEEDED).
Model / band: cursor-grok-4.6-high-fast worker (ce418616-0f22-45ad-8cfe-347633ad0500); composer-2.5-fast tester (c91a45ee-8b3c-4fc3-b165-03c911c27584). Pressure 10. Tester re-run: 38 passed in 2.24s. TTL still 15 * 60.

## 2026-10-03 — T1-B2 and T1-B3
Track: T1
Intent: Re-measure the seeded Rate Line, uncued partner, and sibling golden tests. Do not rebuild them.
Model / band: no worker. Deterministic re-measure.
Files: none.
Commands and results: VERIFIED. `test_named_rate_line_invent_rejected_without_o2m_cue`, `test_schema_verified_reuse_rejects_without_cue`, `test_service_cards_sibling_closed` — 3 passed in 0.67s. Service-cards and Maintenance live in `tests/test_generate_ir_closed_class.py`. `rg` on `ai_generate_ir.py` hits two comments (depend-module cue note; Rate-Line class note), not a branch on those names.
Gates passed: T1-B2 both negatives; T1-B3 shared module and no brief-name branch.
Negative tests: the three tests above.
Not done: T1-C1 default-off craft is not proven by a named test.
Risks introduced: none.

CLAIM T1-C1 2026-10-03T07:25:35Z files: tests that prove approved_craft defaults off, plus the API or web checklist only if the default is not already off.

## 2026-10-03 — T1-C1
Track: T1
Intent: Prove `approved_craft` defaults off (API checklist + web diagnosis toggles); one craft toggle changes generated views XML.
Files: `apps/api/tests/test_approved_craft_default_off.py` (new); `apps/web/src/components/studio/ClarifyInterstitial.test.tsx` (all toggles default off).
Product code: none — defaults already off in `understand.py` / `ClarifyInterstitial.tsx`.
Commands and results: VERIFIED. `pytest tests/test_approved_craft_default_off.py` — 4 passed in 1.19s; `vitest run ClarifyInterstitial.test.tsx` — 5 passed in 632ms.
Gates: default-off negatives; `money_slots` on adds `x_currency_id` to views.xml vs off.
Model / band: composer-2.5-fast worker (6b237b82-d850-47e9-8ae4-9b0e858dbd18); composer-2.5-fast tester (5d662418-b523-419f-a685-db84f76da155). Tester re-run: API 4 passed in 0.90s; web 5 passed.

CLAIM T1-C2 2026-10-03T07:32:00Z files: apps/web/src/components/studio/ClarifyInterstitial.tsx labels, its test if assertions name the old labels, and the progress log.

## 2026-10-03 — T1-C2
Track: T1
Intent: Replace jargon craft checklist labels/help with operator-plain “what it adds” copy; keys and testids unchanged; default off unchanged.
Files: `apps/web/src/components/studio/ClarifyInterstitial.tsx` (`CRAFT_TOGGLE_DEFS` only). Test file unchanged (no old-label assertions).
Model / band: composer-2.5-fast worker (T1-C2 card). Pressure 5. No commit.

### Copy critique (craft toggle rows + section lead)
Quoted surface: section “Optional craft (off by default)” + six row labels and help strings in `CRAFT_TOGGLE_DEFS`.

| Dimension | Score |
|-----------|-------|
| Clarity | 5 |
| Task fit | 5 |
| Actionability | 5 |
| Accuracy and proof | 5 |
| Tone fit | 5 |
| Concision | 3 |
| Accessibility | 5 |
| Ethics | 5 |
| Slop-free | 5 |

Biggest problem: `depth_seeds` help is longer than the others because honesty about padding needs a full sentence.
Revision applied: labels name the artifact (company field, currency field, PO link, contact link, date-and-time, extra models); help lines start with “Adds…” / “Uses…” and match API keys (`company_scoping`, `money_slots`, etc.) without Odoo internals in the primary line.
Confidence: high — wording tied to T1-C1 pytest/XML behavior and card “do not invent” list.
Would settle it: operator UAT on one diagnosis screen; optional snapshot test on label text if regressions recur.

Commands and results: VERIFIED. `pnpm --filter @odoo-custom/web exec vitest run src/components/studio/ClarifyInterstitial.test.tsx` — 5 passed in 36ms (1 file).
Gates passed: no 1 on Accuracy or Ethics; each row states what gets added in plain words.
Not done: API copy unchanged (out of Change).

## 2026-10-03 — T1-D1 and T1-D2
Track: T1
Intent: Re-measure the repair cap and the prove stamp. Do not rebuild them.
Model / band: no worker. Deterministic re-measure.
Files: none. Tests already in `apps/api/tests/test_option_a_prove_bar.py`. `DEFAULT_MAX_REPAIR = 3` in `apps/api/app/ai_repair_loop.py`.
Commands and results: VERIFIED. pytest `tests/test_option_a_prove_bar.py` — 5 passed in 0.78s.
Gates passed: three failing installs stop at 3 and stamp `failed` with `promote_eligible` false (`test_three_install_fails_stamps_failed`). A first passing install with tests stamps `proved` (`test_run_tests_true_stamps_proved`). There is no `install_ready` string in `apps/api`; the live stamp is `prove_status`. Smoke-only success leaves `prove_pending` (`test_smoke_only_success_leaves_prove_pending`). The string `proved_smoke_only` is not in the code.
Negative tests: the three-fail test; the smoke-only test.
Not done: T1-D3 verbatim sandbox error text is still open.
Risks introduced: none.

CLAIM T1-D3 2026-10-03T07:40:00Z files: a test that stores a known traceback, and the store path only if the text is summarized today.

## 2026-10-03 — T1-D3 verbatim sandbox log
Track: T1
Intent: Store Odoo install fault text on sandbox background jobs without summarizing (secrets redacted).
Model / band: worker (cheap).
Files: `apps/api/app/sandbox.py` (`verbatim_sandbox_error_text`, `sandbox_job_error_from_result`), `apps/api/app/job_runner.py` (stamp `BackgroundJob.error` on sandbox `ok=false`), `apps/api/tests/test_verbatim_sandbox_job_log.py`.
Commands: pytest `tests/test_option_a_prove_bar.py` + `tests/test_verbatim_sandbox_job_log.py`.
Gates: known traceback present on job row; password/api_key absent after redaction.

CLAIM T1-E1 2026-10-03T07:43:59Z files: .github/workflows/ci.yml, apps/api/pyproject.toml, apps/api/pytest.ini if that is where markers are registered, apps/api/tests/test_sandbox_prove_slow.py, and a fast test if schema-invalid output is not already rejected.

## 2026-10-03 — T1-E1 CI split (PR-E)
Track: T1
Intent: Tier 1/2 schema grounding in blocking API unit; tier 3 sandbox prove in a separate slow job.
Model / band: worker (Grok standard). Pressure 6. No commit.
Files: `.github/workflows/ci.yml` (`api-unit` adds `test_ai_schema_client.py`, `test_generate_ir_closed_class.py`, `test_schema_invalid_module_output.py`; new job `api-sandbox-prove-slow`), `apps/api/pyproject.toml` + `apps/api/pytest.ini` (`slow` marker), `apps/api/tests/test_sandbox_prove_slow.py` (`slow` mark), `apps/api/tests/test_schema_invalid_module_output.py`.
Commands: `cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_schema_invalid_module_output.py` (plus tier 1/2 files locally if needed).
Gates: fast suite excludes `test_sandbox_prove_slow.py`; slow job runs `pytest -m "sandbox and slow"`; `validate_draft_module_spec` rejects invalid model names in CI.
Not done: Docker sandbox prove on GHA (slow job may skip when Docker unavailable).

## 2026-10-03 — T1-E2
Track: T1
Intent: Record how D2 is encoded. Do not reopen the decision.
Model / band: no worker. Citation only. Pressure 3.
Files: none.
Commands and results: VERIFIED by reading the code. `prove_option_a_in_sandbox` in `apps/api/app/ai_option_a_quality.py` states `prove_status=proved` requires `run_tests=True` plus tests ran. Smoke-only leaves `prove_pending` (`test_smoke_only_success_leaves_prove_pending`). MEMORY.md line 9: D2 (`proved` requires `run_tests=True`) stays closed by the 2026-09-23 entries. The string `proved_smoke_only` is not used.
Gates passed: T1-E2.
Negative tests: the smoke-only test in the D1/D2 re-measure (5 passed).
Not done: none on this card.
Risks introduced: none.

## 2026-10-03 — T1-F1
Track: T1
Intent: Re-measure the Maintenance golden. No new brief-specific product code.
Model / band: no worker. Deterministic re-measure. Pressure 8.
Files: none.
Commands and results: VERIFIED. `test_maintenance_closed_ir_no_uncued_spray` — passed (2 passed in 0.45s with the sibling test). This card did not edit `apps/api/app/`.
Gates passed: Maintenance golden, no new brief-name literal in this change.
Negative tests: the closed-IR spray test.
Not done: T1-F2 still needs a test that fails if `if "maintenance" in brief` is added.
Risks introduced: none.

CLAIM T1-F2 2026-10-03T07:50:00Z files: a test that fails if a maintenance brief branch is added. Do not add that branch to product code.

CLAIM T1-F3 2026-10-03T07:55:00Z files: the sandbox log path in the progress log. Do not promote. Do not commit .cache.


## 2026-10-03 — T1-F2
Track: T1
Intent: Service-cards golden sibling plus AST source lock against brief-name branches in GenerateIR.
Model / band: worker. Pressure 8. No commit.
Files: `apps/api/tests/test_generate_ir_closed_class.py` (`test_generate_ir_sources_forbid_brief_maintenance_or_service_card_branch`).
Commands and results: VERIFIED. `pytest -q -p no:cacheprovider tests/test_generate_ir_closed_class.py::test_service_cards_sibling_closed tests/test_generate_ir_closed_class.py::test_generate_ir_sources_forbid_brief_maintenance_or_service_card_branch`.
Gates passed: T1-F2 acceptance — sibling closed IR; adding `if "maintenance" in brief` (or service-card brief branch) in `ai_generate_ir*.py` fails the new test.
Negative tests: AST scan of `ai_generate_ir.py` and `ai_generate_ir_enforce.py` (comments allowed; real `if`/`elif` conditions not).
Not done: T1-F3 sandbox install_ready evidence on this card.
Risks introduced: none in product code.

## 2026-10-03 — T1-F3 (sandbox major gate 19)
Track: T1
Intent: Run the real Docker sandbox gate for Odoo 19 and record evidence. Do not promote. Do not commit `.cache`.
Model / band: worker (Grok standard). Pressure 8.
Files: `docs/plans/INGENIUM_NEXT_PHASE_PROGRESS.md` (this entry). One-line gate unblock: `docker/run-sandbox-major-gate.sh` (zip-build step uses `uv run --directory apps/api python` instead of bare `python3`, which lacked `pydantic` on `PYTHONPATH`).
Commands and results:
- `./docker/run-sandbox-major-gate.sh 19` → **exit 1** (Docker available; compose up + DB init succeeded; RPC install failed).
- First attempt (before script fix): **exit 1** — `ModuleNotFoundError: No module named 'pydantic'` in zip-build inline Python (`build_module_zip` → `odoo_client`).
- After script fix: zip written `docker/sandbox-addons/_smoke_m19.zip` (4541 bytes). `SandboxResult(ok=False, module='sandbox_smoke_m19', odoo_major=19, tests_ran=False, test_failures=[])`. Install fault: Odoo 19 rejects root menu `web_icon="fa-th-large,#714B67"` (`ParseError` on `views/menus.xml` — `ValueError: Unsupported file: fa-th-large/#714B67`). Not Option A (`option_a_authored` / gold template); script does not call `prove_option_a_in_sandbox` or pass `run_tests=True`.
- **Log path:** no file sink in the gate script. Evidence: this entry; artifact `docker/sandbox-addons/_smoke_m19.zip`; `SandboxResult.log_tail` prefix: `extracted sandbox_smoke_m19 into …/docker/sandbox-addons (target major=19, image=odoo:19)` then `http ready` / `db initialized (major=19)` before RPC fault (full traceback on stdout).
Gates passed: none for T1-F3 acceptance (install + prove bar not met).
Negative tests: n/a (live gate run).
Not done: T1-F3 acceptance — one Option A module with `run_tests=True` and live `prove_status=proved` (card wording `install_ready`; repo stamp is `prove_status` per T1-D1/D2). Fix menu `web_icon` for Odoo 19 smoke modules or run Option A prove path separately.
Risks introduced: gate script now depends on `uv` for both inline Python blocks (consistent with install block).

## 2026-10-03 — T1-GATE
Track: T1
Intent: Re-check the gates that stay even if the code already exists.
Model / band: no worker. Deterministic re-measure. Pressure 4.
Files: none.
Commands and results: VERIFIED. `test_maintenance_closed_ir_no_uncued_spray`, `test_generate_ir_sources_forbid_brief_maintenance_or_service_card_branch`, and `test_admit_and_apply_stale_catalog_never_admits_stock_m2o_field` — 3 passed in 0.45s. `git diff f155e2b..HEAD -- apps/api/app` has no `display_name ==` denylist.
Gates passed: T1-GATE.
Negative tests: the brief-branch scan and the stale-catalog admit test.
Not done: T1-F3 sandbox install still fails on Odoo 19 menu web_icon. T1-RET waits on two recorded zero-scrub runs.
Risks introduced: none.

## 2026-10-03 — T1-F3 (sandbox major gate 19, web_icon repair)
Track: T1
Intent: Make the smoke zip install on Odoo 19 Community. Do not promote. Do not commit `.cache`.
Model / band: worker (Grok standard). Pressure 8.
Files: `packages/module-generator/src/module_generator/__init__.py` (default + emit-time `web_icon` is `base,static/description/icon.png`; Font Awesome `fa-*,#hex` coerced). `packages/module-generator/tests/test_generator.py` (`test_zip_safe_web_icon_coerces_font_awesome` + default-menus assertion). This entry.
Commands and results:
- `uv run --directory apps/api python -m pytest -q -p no:cacheprovider ../../packages/module-generator/tests/test_generator.py::test_menus_and_actions_for_models ../../packages/module-generator/tests/test_generator.py::test_zip_safe_web_icon_coerces_font_awesome` → **2 passed in 0.14s**.
- `./docker/run-sandbox-major-gate.sh 19` → **exit 0**. `SandboxResult(ok=True, module='sandbox_smoke_m19', message='Sandbox (Odoo 19) installed sandbox_smoke_m19 successfully', odoo_major=19, test_failures=[], tests_ran=False)`. Zip written 4539 bytes then cleaned (`keep_alive=False`).
- Script still calls `run_sandbox_install` without `run_tests=True`. Smoke zip is not Option A (`option_a_authored` / gold template); it does not call `prove_option_a_in_sandbox`.
Gates passed: Odoo 19 Community install of `sandbox_smoke_m19` (RPC install only).
Negative tests: FA `fa-th-large,#714B67` is coerced; rendered `menus.xml` has no `fa-th-large`.
Not done: T1-F3 acceptance — one Option A module with `run_tests=True` and live `prove_status=proved` (card wording `install_ready`). This gate script is smoke-install only; `tests_ran` stayed false.
Risks introduced: generated zips lose distinctive FA home-grid icons and share the stock `base` icon. Live Apply already did this.

CLAIM T1-F3 2026-10-03T08:15:07Z files: a live Option A prove with run_tests=True. Do not promote. Do not commit .cache. Smoke install already exited 0.

CLAIM T1-RET 2026-10-03T08:25:00Z files: trace script only if its cd is still wrong, then the progress log. Do not delete scrub unless two recorded runs have zero removals.


## 2026-10-03 — T1-F3 (option_a_authored prove with tests)
Track: T1
Intent: One Option A module reaches live `prove_status=proved` on the Odoo 19 sandbox with `run_tests=True`. Do not promote. Do not commit `.cache`.
Model / band: worker (Grok standard). Pressure 8.
Files: `apps/api/scripts/prove_option_a_sandbox.py` (minimal `option_a_authored` draft, depends `base` only, trivial `x_prove_note` + passing TransactionCase). `apps/api/app/sandbox.py` (`build_test_enable_argv` adds `--http-port 8070` so compose-exec test-enable does not collide with the already-running HTTP server on 8069). `apps/api/tests/test_sandbox_test_enable.py` (asserts the port flag). This entry.
Commands and results:
- First live prove (`run_tests=True`, default auto_repair): **install ok**, then test-enable **exit 1** — `Address already in use` / `Port 8069 is in use`. `tests_ran=True`, `prove_status=failed`. Not stamped proved.
- After argv fix: `uv run --directory apps/api python -m pytest -q -p no:cacheprovider tests/test_sandbox_test_enable.py tests/test_option_a_prove_bar.py` → **11 passed in 1.20s**.
- `uv run --directory apps/api python scripts/prove_option_a_sandbox.py` (`prove_option_a_in_sandbox(..., odoo_major=19, run_tests=True, auto_repair=False)`) → **ok=True, prove_status=proved, tests_ran=True, test_failures=[], install_attempts=1, repairs_used=0, promoted=False**. Module `option_a_prove_note`. Log: `Starting TestProveNote.test_note_create_and_mark_seen` then `0 failed, 0 error(s) of 1 tests` then `test-enable ok for option_a_prove_note`.
- **Log path:** `.cache/t1_f3_option_a_prove_19.log` (summary JSON beside it). Do not commit `.cache`.
Gates passed: T1-F3 live Option A prove bar (`prove_status=proved` via `run_tests=True` + tests actually ran). Card wording `install_ready` is this stamp.
Negative tests: unit argv still requires `--test-enable` + `--stop-after-init`; prove-bar mocks still refuse `proved` without `tests_ran`.
Not done: promote (human). Do not treat `promote_eligible=True` as a promote.
Risks introduced: test-enable HTTP binds 8070 inside the sandbox container only; host `:18069` unchanged.

## 2026-10-03 — T1-RET (retire scrub gate + assert-only)
Track: T1
Intent: Record two consecutive Maintenance `AI_IR_TRACE` dumps with zero GenerateIR `scrub_hits`; then replace `scrub_uncued_*` with assert-only and move Date/Datetime/money gating into `approved_craft`. Do not commit. Do not commit `.cache`.
Model / band: worker. Pressure 9.
Files: `apps/api/scripts/dump_maintenance_ir_trace.sh` (`ROOT` three levels up to repo root). `apps/api/app/ai_brief_cues.py`, `ai_conversation/understand.py`, `ai_generate_ir_enforce.py`, `ai_enrich.py`, `settings.py`, `tests/test_generate_ir_closed_class.py`. This entry.
Commands and results:
- Fixed dump script `ROOT` (`../../..`); `AI_IR_TRACE=1 bash apps/api/scripts/dump_maintenance_ir_trace.sh` from repo root ×2.
- **Run 1 stamp:** `20261003T092128` — **scrub removal count:** `0` (`enforce_closed_generate_ir` → `extra.closure.scrub_hits: []`). Apply-phase view arch note only: `apply: scrubbed 4 stale arch field ref(s)` (not counted as closure scrub_hits; same as PF-3).
- **Run 2 stamp:** `20261003T092133` — **scrub removal count:** `0` (same `scrub_hits: []`).
- Both gates passed → continued card (did **not** stop before scrub retirement): `scrub_uncued_invent_*` now `assert removed == []`; added `date_slots` to `APPROVED_CRAFT_KEYS` + `ai_craft_date_slots`; `_date_allowed` / `coerce_uncued_date_fields`; Datetime/money remain on `datetime_over_date` / `money_slots`.
- `uv run --directory apps/api python -m pytest -q -p no:cacheprovider tests/test_generate_ir_closed_class.py tests/test_generate_ir_spine.py tests/test_approved_craft_default_off.py` → **36 passed in 2.34s**.
Gates passed: two recorded zero-`scrub_hits` Maintenance traces; assert-only scrub; craft date slots; GenerateIR battery green.
Negative tests: `test_scrub_uncued_must_do_asserts_on_uncued_date` (uncued `Date` Must-do trips assert).
Not done: delete `scrub_uncued_*` symbols entirely (one release assert-only per card); full battery / Mac §9 live grade; `test_continuous_invent_class` not re-run this card.
Risks introduced: LLM paths that still emit uncued invent labels will raise at scrub assert until upstream gates catch them.

## 2026-10-03 — T2-J1 live JSON-2
Track: T2
Intent: Check `/doc` and the three JSON-2 methods on the operator tip and mirror. Do not store the API key.
Model / band: no worker. Live calls from gitignored `.env.json2`.
Files: `docs/verified-facts.md`.
Commands and results: PARTIALLY VERIFIED. Both hosts answered. `search_read`, `fields_get`, and `create` match `execute_kw_map.py` (`domain` plus kwargs, `attributes`, `vals_list`). Bad key is 401. A string domain is 500, not 400. `GET /doc` is the public website, so the `/doc` match is not verified. Server traceback path is `odoo/20.0`.
Gates passed: live call shapes on tip and mirror. 4xx/5xx unit tests were already present and were not re-run.
Negative tests: bad key 401; empty create 422; string domain 500.
Not done: `/doc` does not document the methods on this website. T2-J2 is recorded later on a local Odoo 19 sandbox, not on the operator Online database.
Risks introduced: one probe contact was created on the tip and removed in the same check. The key file stayed gitignored.

CLAIM 5A-06 2026-10-03T08:25:35Z files: apps/api/app/snapshot_gate.py and its tests. Freshness window 10 minutes. Cover BILLABLE. Do not create a second audit table.

## 2026-10-03 — 5A-06 snapshot freshness + BILLABLE
Track: 5A. Worker only. No commit.
Intent: Production DESTRUCTIVE or BILLABLE refuses unless a connection-scoped metadata snapshot was recorded immediately before (≤10 min and newer than the last audited write). Odoo 20 accepts metadata; no `/web/database` backup.
Files: `apps/api/app/snapshot_gate.py`, `apps/api/tests/test_snapshot_gate.py`, this entry.
Commands and results: `cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_snapshot_gate.py` → **20 passed in 1.82s**.
Gates passed: freshness window; BILLABLE risk + method patterns reuse `rpc_classify._is_billable_method` (no second taxonomy); Odoo 20 metadata accepted.
Negative tests: `test_production_destructive_two_hour_old_snapshot_refused`, `test_production_snapshot_from_other_connection_refused`.
Not done: `safety_gate.preflight` still only passes `snapshot_exists` — wire `created_at` / last write / BILLABLE risk on the caller (changeset executor not touched).
Risks introduced: fail-closed when `created_at` is omitted on a gated production apply.

## 2026-10-03 — 5A-07
Track: 5A
Intent: Re-measure the MCP write scan after BL-07.
Model / band: no worker. Deterministic re-measure. Pressure 4.
Files: none.
Commands and results: VERIFIED. pytest `tests/test_no_mcp_write.py` and `tests/test_mcp_guard.py` — 5 passed in 6.31s.
Gates passed: DoD 27 / 5A-07.
Negative tests: planted MCP write still detected; `test_mcp_write_is_refused`.
Not done: 5A-11 rollback tiers.
Risks introduced: none.

CLAIM 5A-11 2026-10-03T08:40:00Z files: compensating plan from change rows through the change-set pipeline. Do not raw-RPC the undo. Do not create a second audit table.

## 2026-10-03 — 5A-11 rollback tiers wired
Track: 5A. Worker only. No commit.
Intent: Name three rollback tiers. Build a compensating change-set from audit `change` rows and send it through validate / policy / apply. Do not live-restore `/web/database`.
Files: `apps/api/app/rollback_tiers.py`, `apps/api/app/changeset/ops.py` (`data.unlink`), `apps/api/app/changeset/handlers.py`, `apps/api/tests/test_rollback_tiers.py`, `apps/api/scripts/lint_new_modules.sh`, this entry.
Commands and results: `cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_rollback_tiers.py tests/test_snapshot_gate.py` → **24 passed in 1.84s**. `scripts/lint_new_modules.sh` clean.
Gates passed: compensating plan from change rows through the change-set pipeline; module install and posted entries listed as not reversible by this tier.
Negative tests: `test_compensating_plan_unlink_res_users_refused_by_never_allowed`.
Not done: live `/web/database` restore (named as tier 1 only; not for Online, Odoo.sh, or Odoo 20).
Risks introduced: `data.unlink` is a catalog op for compensating created rows only; never-allowed still refuses `res.users` unlink via `classify_rpc`.

## 2026-10-03 — JSON-2 production probe
Track: T2
Intent: Learn method parameters from the connected database on Online, Odoo.sh, Enterprise, and on-prem. A website at `/doc` is ignored. Live calls win.
Model / band: implementation in this session. Pressure matches T2-J1 (10) for the live contract.
Files: `packages/odoo-client/src/odoo_client/transport/json2.py`, `json2_probe.py`, `client.py`, `packages/odoo-client/tests/test_json2_transport.py`, `docs/verified-facts.md`.
Commands and results: VERIFIED. pytest `packages/odoo-client/tests/test_json2_transport.py` — 29 passed in 0.16s.
Gates passed: website `/doc` does not supply parameters; live `domain` / `attributes` / `vals_list` are kept; a 500 `Domain()` TypeError is a caller error and is not retryable; a pasted `/odoo` URL calls the host root.
Negative tests: `test_domain_typeerror_500_is_a_caller_error_and_is_not_retryable`, `test_probe_live_parameters_win_when_doc_disagrees`.
Not done: the operator Online database was not used for install timing. T2-J2 is the following local Odoo 19 entry.

CLAIM T2-J2 2026-10-03T09:19:00Z files: a local Odoo 19 sandbox timing of button_immediate_install via the frozen client, XML-RPC and JSON-2. Do not change the sandbox default. Do not call aonb.odoo.com. Do not promote.

## 2026-10-03 — production probe for 17–19
Track: T2
Intent: The same production probe runs on XML-RPC and JSON-RPC connections for 17, 18, and self-hosted 19.
Model / band: this session.
Files: `packages/odoo-client/src/odoo_client/transport/production_probe.py`, `client.py`, `tests/test_json2_transport.py`.
Commands and results: VERIFIED. pytest `packages/odoo-client/tests/test_json2_transport.py` — 31 passed.
Gates passed: a 17 XML-RPC connect stores `production_probe` with major 17 and create shape `vals`. The probe calls `search_read` and `fields_get` only.
Negative tests: `test_legacy_probe_learns_17_and_does_not_call_create`.
Not done: none for this probe. T2-J2 timings are in the following entry.
Risks introduced: a legacy connect adds two read RPCs.

Risks introduced: every JSON-2 connect runs the probe (one GET and three POSTs). `create` is an empty body and must stay that way so the probe does not insert a row.

## 2026-10-03 — T2-J2 install port timing
Track: T2. Worker only. No commit. No promote. Local ephemeral Odoo 19 Docker only (`:18069`, `sandbox_test`).
Intent: Time `OdooClient.ensure_module_installed` (`button_immediate_install`) on the same stock module over XML-RPC and JSON-2. Do not change `_sandbox_client` (`rpc_protocol="xmlrpc"`).
Model / band: implementation. Pressure 8.
Files: this entry only. `apps/api/app/sandbox.py` not edited.
Commands and results: VERIFIED on two sequential ephemeral sandboxes, module **board**.
- XML-RPC (sandbox A, `_sandbox_client` + `ensure_module_installed`): **6.151 s**, state `installed`.
- JSON-2 (sandbox B, second `OdooClient(rpc_protocol="json2")` + same frozen method): **4.053 s**, state `installed`.
XML-RPC cannot mint the first admin API key: `res.users.apikeys._generate` → Fault 4 private method; `generate` → Fault 3 needs an existing key; `res.users.apikeys.description.make_key` → Fault 2 "This method can only be accessed over HTTP". Key was created on each sandbox via `/web/session/authenticate` + `identitycheck.run_check` (not printed). JSON-2 connect still runs the production probe (422 `res.partner/create` missing `vals_list` on this 19 image; connect still succeeded).
Gates passed: install through the frozen interface on both transports; both durations recorded; sandbox default still XML-RPC.
Negative tests: none new.
Not done: Online / aonb not called. Sandbox default not moved to JSON-2.
Risks introduced: none in product code.

CLAIM T2-J3 2026-10-03T09:25:00Z files: apps/api/tests/test_no_direct_xmlrpc.py. Grep ServerProxy / xmlrpc.client outside packages/odoo-client and the sandbox. Cache skip like test_no_mcp_write.py. client.execute_kw is not a finding. Do not change the sandbox default. Do not call aonb.odoo.com.

## 2026-10-03 — T2-J3 direct-transport grep
Track: T2. Card: T2-J3. Worker only. No commit. No promote. No aonb.
Intent: Guardrail test mirroring `test_no_mcp_write.py`; product `apps` + `packages` scan skips BL-07 cache dirs, `docs`, and `tests` (same scope as card `rg --glob '!**/tests/**'`).
Model / band: cheap (pressure 5).
Files: `apps/api/tests/test_no_direct_xmlrpc.py` (new); `apps/api/app/rpc_resilience.py` (removed stdlib xmlrpc import — exception types via `odoo_client.rpc_transport_errors`); `packages/odoo-client/src/odoo_client/rpc_transport_errors.py` (new bridge in allowed adapter).
Commands and results:
- `rg -n "import xmlrpc|xmlrpc\.client|ServerProxy" apps packages --glob '!**/tests/**'` — hits only `packages/odoo-client/**` (incl. new bridge) and `apps/api/app/sandbox.py:435` (docstring mention of ServerProxy; allowed).
- `pytest -q -p no:cacheprovider apps/api/tests/test_no_direct_xmlrpc.py` — **2 passed**.
- `pytest -q apps/api/tests/test_no_direct_xmlrpc.py` (with `.pytest_cache` etc. present) — **2 passed**.
Findings (pre-remediation, from first `rg`): `apps/api/app/rpc_resilience.py` lines 5, 24, 26 (`import xmlrpc.client` / `Fault` / `ProtocolError` for TRUST-5 retry classification only — not ServerProxy transport). Remediated in this card via adapter-local bridge; no follow-up card.
Gates passed: planted `ServerProxy(` under `apps/api/app` detected by scanner; repo grep empty outside allowed adapter + sandbox; sandbox default untouched.
Negative tests: `test_direct_xmlrpc_scan_detects_planted_server_proxy_in_app_tree`.
Not done: `docker/*` scripts still use raw xmlrpc (outside `apps`/`packages` scan roots). `apps/api/tests/test_wave16_gen2.py` still uses `ServerProxy` in tests (excluded from scan, same as card `rg`).
Risks introduced: none.

CLAIM T2-J4 2026-10-03T09:30:00Z files: STATE.md and the progress log. Honest done vs operator-only. Do not write JSON-2 complete.

## 2026-10-03 — T2-J4 honest docs (PR-J4)
Track: T2. Card: T2-J4. Worker only. Docs only. No commit. No push. No product code. No live Odoo calls.
Intent: `STATE.md` and this log state what is done vs still open. T2-SMOKE's three Online methods are recorded. T2-J1 `/doc` text match is not verified, so the JSON-2 track stays open.
Model / band: docs. Pressure 3.

**Done (verified in repo / recorded facts):**
- JSON-2 transport, mapper, and production probe in `packages/odoo-client` — commits **a67877a**, **603523c**. Odoo **19 Online** and **20** use JSON-2; Odoo **17**, **18**, and **self-hosted 19** use XML-RPC or JSON-RPC. Production probe confirms `search_read` and `fields_get` live and does not insert a row. JSON-2 create shape is `vals_list`; legacy create is positional `vals`.
- Live calls on **https://aonb.odoo.com** (db `aonb`) and **https://aonb-mirror.odoo.com** (db `aonb-mirror`), build path **odoo/20.0**, documented in `docs/verified-facts.md`: `search_read`, `fields_get`, and create matched the mapper; bad key **401**; empty create **422** missing `vals_list`; string domain **500** `Domain()` TypeError. **GET `/doc`** is the public website, so `/doc` parameter match is **not** verified.
- **T2-J2** (commit **f626a00**): stock module `board` installed through `OdooClient.ensure_module_installed` on two local ephemeral Odoo 19 sandboxes — XML-RPC **6.151 s**, JSON-2 **4.053 s**, both state `installed`. Sandbox default stayed **xmlrpc**. Online was not installed to. First admin API key cannot be minted over XML-RPC on Odoo 19.
- **T2-J3** (commit **1cf4417**): `apps/api/tests/test_no_direct_xmlrpc.py` — **2 passed**. Direct `xmlrpc.client` / `ServerProxy` outside `packages/odoo-client` and `apps/api/app/sandbox.py` fails the test. `rpc_resilience` imports `Fault`/`ProtocolError` from `odoo_client.rpc_transport_errors`. `docker/*` raw xmlrpc and `test_wave16_gen2.py` `ServerProxy` are outside scan roots (tests/docker).
- **T2-SMOKE:** the three Online methods are recorded on aonb (20.0) in `docs/verified-facts.md`. That is the card's acceptance. No new live call. An Online module install was not part of this card and was not run.

**Still open:**
- **T2-J1:** `/doc` text match is not verified. The website owns that route. Do not guess signatures. The JSON-2 track stays open for that reason.
- Sandbox default remains **XML-RPC**. **Promote stays human.**

Files touched: `STATE.md` (Last run + Next + Docket); this entry.
Gates passed: no sentence claims the JSON-2 track is finished; T2-SMOKE methods are cited from verified-facts; Mac §9 UI paste remains operator; L4 stays unconfirmed.
Not done: T2-J1 `/doc` text match, Mac §9 UI paste. Sandbox default stays XML-RPC. Promote stays human.
Risks introduced: none (docs only).

CLAIM 5A-12 2026-10-03T09:35:00Z files: production budget caps and apps/api/tests/test_production_budgets.py. Do not enable L4. Do not call aonb.odoo.com.

Track: 5A. Card: 5A-12. Worker only. No commit. No push. L4 stays off.
Intent: Production budgets from blueprint §5.6 — 40 LLM steps, 120 tool calls, 200-record production apply (L4 50 inactive), plus pointers for windows / R3 / kill switch.
Command: `.venv/bin/python -m pytest -q -p no:cacheprovider apps/api/tests/test_production_budgets.py` — **6 passed**.
Tests: (1) 41st LLM step raises BudgetExceeded, MAX_STEPS stays 40. (2) 121st call_tool raises BudgetExceeded, MAX_TOOL_CALLS=120. (3) production apply of 201 records refused; L4_MAX_BLAST stays 50 and WorkerBot("L4") still raises.
Pointers: (4) change windows → T6-04 freeze-on-approve and T6-06 allowed time window. (5) two-person R3 → T6-06 and self_approval_allowed (R3 still False). (6) kill switch → test_kill_switch_protocol_and_escalation_refuse_before_work and test_reader_and_kill_switch_do_not_touch_the_port_or_journal.
Files: `runtime.py` (MAX_TOOL_CALLS), `blast_radius.py` (PRODUCTION_APPLY_RECORD_CAP), `executor.py` (production record gate), `test_production_budgets.py`.
Not done: L4 remains unconfirmed and inactive. No aonb.odoo.com call.

CLAIM 5B-02 2026-10-03T09:40:00Z files: config_as_code apply through the change-set executor. Fake port only. Do not enable L4. Do not call aonb.odoo.com.

Track: 5B. Card: 5B-02. Worker only. No commit. No push. Fake port only. L4 stays off.
Intent: Compile each spec section to a closed catalog op; upsert by xmlid with read-before-write; apply through `changeset.executor.apply` (Mode C) against a fake port.
Closest existing catalog ops (no new names): languages/currencies/mail_servers/tax+product+HR/POS/project master data → `config_record.upsert`; crm_stages/task_stages → `stage.upsert`; views → `view.inherit.create`.
Command: `.venv/bin/python -m pytest -q -p no:cacheprovider apps/api/tests/test_config_apply.py apps/api/tests/test_bridge_and_config_spec.py` — **18 passed**.
Acceptance: `test_plan_apply_idempotent` second apply `port.call_count == 0` after `reset_journal`; `test_adopt_example_compiles`; `test_errors_block_apply` type mismatch writes nothing; `test_second_apply_writes_nothing` still 1 MemoryDb write. `write_mode=production` refused. No aonb call.
Files: `config_as_code/loader.py`, `config_as_code/apply.py`, `changeset/dispatch.py` (`setting.set`, `config_record.upsert`), `tests/test_config_apply.py`.
Not done: durable WAL (T8-EXEC). Production acknowledgement is gated but 5B-09 oracle names are not this card. L4 off.

CLAIM 5B-03 2026-10-03T09:45:00Z files: config apply aborts on fake-db fingerprint drift. Do not enable L4. Do not call aonb.odoo.com.

Track: 5B. Card: 5B-03. Worker only. No commit. No push. Fake port only. L4 stays off.
Intent: Abort config apply when fake-port rows change between compile and apply. Reuse `plan_fingerprint` (same 16-hex hash). Caller-facing error is `ApplyError.name == plan_drift`. No expected fingerprint keeps today's apply.
Command: `.venv/bin/python -m pytest -q -p no:cacheprovider apps/api/tests/test_config_apply.py apps/api/tests/test_plan_fingerprint.py apps/api/tests/test_bridge_and_config_spec.py` — **22 passed**.
Acceptance: `test_fingerprint_drift_detected` mutates `FakeConfigPort.rows` after the plan exists; apply raises `plan_drift` with `call_count == 0`. Matching fingerprint still applies. Existing idempotent tests stay green. `write_mode=production` refused. No aonb call.
Files: `config_as_code/apply.py` (`port_fingerprint`, `expected_fingerprint` → `plan_drift`), `tests/test_config_apply.py`.
Not done: durable WAL (T8-EXEC). T1/T3/T4 drift oracles (5A-03 open delta). L4 off.

CLAIM 5B-06 2026-10-03T09:50:00Z files: config importers load batch and fields_get validation. Fake port only. Do not enable L4. Do not call aonb.odoo.com.

Track: 5B. Card: 5B-06. Worker only. No commit. No push. Fake port only. L4 stays off.
Intent: CSV import validates every row against a caller-supplied `fields_get` before `port.load()`. Batch size 500. Context `tracking_disable`, `mail_create_nolog`, `mail_notrack`. Prefer `field/id`. Dates YYYY-MM-DD. NG phones → `+234…`. Blank cells are not dedupe keys. Partner merge, opening balances, and posting refused (destructive). `write_mode=production` refused.
Command: `.venv/bin/python -m pytest -q -p no:cacheprovider apps/api/tests/test_importers.py apps/api/tests/test_config_apply.py` — **18 passed**.
Acceptance: oracle names `test_phone_normalisation`, `test_duplicates_in_sample`, `test_template_from_fields`, `test_validate_bad_file`, `test_validate_good_file_and_load`, `test_selection_and_numeric_validation`, `test_blank_values_are_not_duplicates`. EV-DATA-03: 30 bad rows report all 30 and load none. 501 rows → two `load()` calls (500 + 1) with the three context flags on each.
Files: `config_as_code/importers.py`, `tests/test_importers.py`.
Not done: 5B-04 / O20-06 (not this card). Live Odoo import. L4 off. No aonb.odoo.com call.

CLAIM 5B-07 2026-10-03T09:55:00Z files: oracle test_custom_field_requires_x_prefix. Do not enable L4. Do not call aonb.odoo.com.

Track: 5B. Card: 5B-07. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Document config-as-code custom field naming — `x_` required, `x_studio_` forbidden — via oracle test; loader already enforces in `CustomField.x_prefix`.
Command: `.venv/bin/python -m pytest -q -p no:cacheprovider apps/api/tests/test_bridge_and_config_spec.py` — **15 passed**.
Acceptance: `test_custom_field_requires_x_prefix` rejects `note` and `x_studio_note`; `x_note` loads. `test_studio_field_prefix_is_rejected` unchanged. No product change.
Files: `apps/api/tests/test_bridge_and_config_spec.py`.

CLAIM 5B-08a 2026-10-03T10:00:00Z files: remaining spec oracle names. Do not enable L4. Do not call aonb.odoo.com.

Track: 5B. Card: 5B-08a. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Port oracle `test_spec.py` names (spec slice only): `test_example_spec_is_valid`, `test_schema_errors`, `test_duplicate_keys_rejected`, `test_key_field_reference_and_placeholders` against `config_as_code/loader.py`. Leave 5B-09 approval/version oracles and 5B-08c profiles out of scope.
Command: `.venv/bin/python -m pytest -q -p no:cacheprovider apps/api/tests/test_bridge_and_config_spec.py apps/api/tests/test_config_apply.py` — **24 passed**.
Loader checks added: duplicate `key` per section (`_reject_duplicate_keys`); required `key:` references must resolve to a key defined in the spec (`_validate_key_references`; `?key:` optional). Existing literal-secret and unknown-section guards unchanged.
Files: `apps/api/app/config_as_code/loader.py`, `apps/api/tests/test_bridge_and_config_spec.py`.
Not done: 5B-08b importers / 5B-08c version profiles / 5B-09 approval oracles. No aonb.odoo.com call.

CLAIM 5B-09 2026-10-03T10:05:00Z files: destructive config requires approval. Do not enable L4. Do not call aonb.odoo.com.

Track: 5B. Card: 5B-09. Worker only. No commit. No push. Fake port only. L4 stays off.
Intent: Destructive config ops (`data.delete`, uninstall, partner merge, posting) need `approve_destructive` before any port call. `environment=production` needs `acknowledge_production` even for `setting.set`. `write_mode=production` still raises `write_mode_production_refused`; neither acknowledgement flag bypasses it. Fake-port read-back marks dropped writes IGNORED, never VERIFIED. Plan card comes from existing `render_plan_card` (`plan_hash`, `risk`, `environment`). Version compile reuses `compile_access` (19=`ir.model.access`+`ir.rule`, 20=`ir.access`).
Command: `.venv/bin/python -m pytest -q -p no:cacheprovider apps/api/tests/test_config_apply.py apps/api/tests/test_bridge_and_config_spec.py` — **28 passed**.
Files: `config_as_code/apply.py` (`approve_destructive`, `ApplyResult`, read-back), `tests/test_config_apply.py`.
Not done: L4 remains off. No aonb.odoo.com call. `write_mode=production` still refused. Approved destructive ops are recorded only on `FakeConfigPort` or `MemoryDb`; any other port raises `destructive_fake_port_only`.

CLAIM O20-02 2026-10-03T10:10:00Z files: VersionAwarenessBanner says Odoo 20 is supported. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-02. Worker only. No commit. No push. No Odoo RPC.
Intent: Registry already lists Odoo 20 as GA; web banner should say so for probed major 20 (non-experimental). Experimental and Enterprise callouts unchanged.
Result: Vitest `VersionAwarenessBanner.test.tsx` — 2 passed. Pytest `packages/odoo-client/tests/test_registry_odoo20.py` — 5 passed.
Files: `apps/web/src/components/VersionAwarenessBanner.tsx`, `apps/web/src/components/VersionAwarenessBanner.test.tsx`.

CLAIM O20-03 2026-10-03T10:15:00Z files: automation_v20 and security_v20. Major 20 only. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-03. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Add `automation_v20` (v19 encoder + V12 no `numbercall`; V11 still a nested `ir.actions.server`) and `security_v20` (`access_model`=`ir.access`; `ir.rule` create raises `IrRuleNotSupportedOnOdoo20`). Register both for major 20 only. Thin wrapper in the package (same field names as `access_compiler.py`); cannot import `apps.api` without a cycle.
Result: pytest `test_views_adapters_multimajor.py` + `test_automation_encoders_multimajor.py` + `test_odoo20_automation_security_adapters.py` — **63 passed**.
Negative: `security_v20.create_record_rule` and client `create_record_rule` on major 20 raise `IrRuleNotSupportedOnOdoo20` before `execute_kw`. Cron vals omit `numbercall`. 16–19 pickers unchanged. Major 20 views use `views_v20` (`list`, not `tree`); major 19 stays on `views_v19`.
Files: `automation_v20.py`, `security_v20.py`, `adapters/__init__.py`, `client.py` picker + `create_record_rule` / `create_cron`, new test file.
Not done: O20-04 write-path wiring for all `ir.model.access` creates. L4 off. No aonb.odoo.com call.

CLAIM O20-04 2026-10-03T10:20:00Z files: route major-20 access writes through the ir.access compiler. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-04. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Major 20 access writes use the existing `compile_access` (`ir.access`, operation, optional domain). A record rule that names a group fails with "rewrite as an access right with a domain". ≤19 domain rights still compile to `ir.model.access` plus `ir.rule`. `rpc_classify` keeps `ir.access`, `ir.model.access`, `ir.rule`, and `res.groups` DESTRUCTIVE. No second compiler. The package cannot import `apps.api`; `OdooClient.create_access_right` on major 20 calls the O20-03 `security_v20.compile_access` wrapper (same field names). API paths call `app.odoo20.access_compiler`.
Result: pytest compiler + access router + new write-path + `test_odoo20_automation_security_adapters.py` — **79 passed**.
Write paths (`rg` creates, not mentions):
- `OdooClient.create_access_right` — major 20 creates `ir.access` only. Refuses `ir.rule`.
- `OdooClient.create_record_rule` — major 20 raises `IrRuleNotSupportedOnOdoo20` before `execute_kw`, including a group-named rule. No `ir.rule` create.
- `OdooClient.ensure_default_model_access` — major 20 searches `ir.access`, then `create_access_right`. No `ir.rule` create.
- `routers/access.py` `create_right` — delegates to `create_access_right`. No `ir.rule` create.
- `routers/access.py` `create_rule` — delegates to `create_record_rule`. HTTP 400 with the rewrite message. No `ir.rule` create.
- `spec_apply_ui._apply_access_rules` — major 20 compiles the right (domain stays on `ir.access`). ≤19 domain path still calls `create_record_rule`.
- `spec_apply_ui._apply_draft_record_rules` — group rule on 20 raises `AccessCompileError` and creates nothing. Group-less rule creates nothing. ≤19 still calls `create_record_rule`.
- `multi_company_pack.apply_multi_company_live` — major 20 compiles; the global rule has no group, so no `ir.rule` create.
- `app_templates._maybe_multi_company_rules` — same as the live pack. No `ir.rule` create.
- `changeset/dispatch.py` `access.create` — `port.major` or `capabilities.major` ≥ 20 compiles to `ir.access` (optional domain). Missing major stays `ir.model.access`. `kind` is refused. No `ir.rule` create.
- `changeset` `rule.create` — still has no dispatcher (raises). It does not create `ir.rule` on 20.
Not creates (left as they were): snapshot restore writes/unlinks `ir.model.access` and `ir.rule`; list/update/delete still name those models. `rpc_classify` was not lowered.
Not done: O20-05 access screen. L4 off. No aonb.odoo.com call.

REPAIR O20-04 2026-10-03T10:30:00Z reviewer FAIL. Do not enable L4. Do not call aonb.odoo.com.
1. fixed: `compile_access` on major >= 20 raises `AccessCompileError` with the rewrite message for every record rule, with or without a group, and does not turn that rule into an `ir.access` grant. A domain-bearing access right still compiles to `ir.access` with operation and optional domain.
2. fixed: on major 20, `apply_multi_company_live` and `_maybe_multi_company_rules` do not create `ir.rule`. `rules_created` stays 0. The live pack sets `ok` false. The warning says the company field may exist but row isolation was not applied because Odoo 20 has no `ir.rule`.
3. fixed: `_apply_access_rules` and `_apply_draft_record_rules` record `AccessCompileError` on warnings and continue, so models and fields already applied are kept. A group record rule on 20 creates nothing and is not converted into `ir.access` rows for `base.group_user`. An access right may still become `ir.access`.
4. fixed: `_apply_one_access_rule_v20` skips an operation only when an `ir.access` row with that name and that operation already exists.
5. fixed: on major >= 20, `delete_access` and `update_access` affect every `ir.access` row with the same name and model. List, update, and delete do not use `ir.model.access` on major 20. A test removes all four operations under one name.
6. fixed: `_security_adapter` uses major >= 20, matching `create_access_right`, so a future major does not fall through to `execute_kw("ir.rule", "create")`.
7. fixed: the `rule.create` test asserts `DispatchError` "no dispatcher for rule.create" and that the fake port was not called. That is the existing missing dispatcher, not a new branch.
8. fixed when `ModuleSpec.odoo_major` >= 20: module render raises the rewrite message and does not emit `record_rules.xml`. Residual: when `odoo_major` is unset, `record_rules.xml.j2` still emits `model="ir.rule"` because the generator does not invent a major. It is not a live RPC create.
Pytest: `.venv/bin/python -m pytest -q -p no:cacheprovider` on the O20-04 write-path set — 86 passed. L4 stays off. No Odoo host call.

CLAIM O20-05 2026-10-03T10:50:00Z files: access screen branches on major 20. Do not enable L4. Do not call aonb.odoo.com. Do not migrate dialogs.
Vitest: `pnpm exec vitest run src/components/access/Odoo20AccessNote.test.tsx` from `apps/web` — **2 passed**.

Track: O20. Card: O20-05. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Access screen data branch on major 20 reads/writes `ir.access` (existing rights endpoints; API already compiles operation + domain). It does not fetch `ir.rule` or offer a create-record-rule action. ≤19 keeps the current list + New rule path. One inline note: "Odoo 20 combines access rights and record rules." No Studio / Enterprise copy. ConfirmDialogV2 left as-is (UI-F04).
Files: `accessMajor.ts`, `Odoo20AccessNote.tsx`, `Odoo20AccessNote.test.tsx`, `access/page.tsx` (data branch + note only).
Not done: L4 off. No aonb.odoo.com call. No dialog migration. No access-page restyle.

CLAIM O20-06 2026-10-03T11:00:00Z files: version table rows and fake tests. No live probe. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-06. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Encode all 32 card rows (V01–V32) in `compat/version_table.py`. Fake test per row asserts the 20 value and one older value. `difference()` returns the 20 `removed`/`absent` fact; it does not fall back to 19. `require_present("company_type", 20)` raises `VersionFactUnavailable` (named message, not KeyError).
Result: `.venv/bin/python -m pytest -q -p no:cacheprovider packages/odoo-client/tests/test_odoo20_version_table.py` — **38 passed, 32 skipped**. 32 V-rows encoded. Live half skipped: "live N/A until ODOO20_URL is set." Do not mark a live probe as passed.
Still verify (card wording kept, not upgraded): V06 18–19 `verify override`; V24 17 and 19 `verify`; V26 19 `verify`; V28 19 `verify`; V29 19 `verify`; V30 19 `verify`.
Files: `packages/odoo-client/src/odoo_client/compat/version_table.py`, `packages/odoo-client/tests/test_odoo20_version_table.py`.
Not done: live 20 probes. L4 off. No aonb.odoo.com call. No Docker.

CLAIM O20-07 2026-10-03T11:05:00Z files: JSON-2 password error on major 20. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-07. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: On major ≥ 20, `_connect_json2` auth failure explains that JSON-2 needs an API key and points password users to `rpc_protocol=xmlrpc` — not “leave auto on non-Online hosts” (auto on 20 is JSON-2). Major 19 keeps the existing Online/local auto hint.
Files: `packages/odoo-client/src/odoo_client/client.py`, `packages/odoo-client/tests/test_odoo20_version_table.py`.
Pytest: `.venv/bin/python -m pytest -q -p no:cacheprovider packages/odoo-client/tests/test_odoo20_version_table.py packages/odoo-client/tests/test_json2_transport.py` — **70 passed, 32 skipped**.
Major-20 hint sentence: `JSON-2 requires an API key (Settings → Users → Account Security → New API Key). To use a login password instead, set rpc_protocol=xmlrpc.`
Not done: L4 off. No aonb.odoo.com call.

CLAIM O20-08 2026-10-03T11:10:00Z files: no db-service backup on Odoo 20. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-08. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Metadata snapshots stay on the existing RPC read path. A database-level backup on major 20 does not call `/web/database` or `dump_db`. The operator takes that backup on the host (Odoo Online, Odoo.sh, or the server). Odoo.sh and Odoo Online do not get a dump on any major. No new dump protocol.
Pytest: `.venv/bin/python -m pytest -q -p no:cacheprovider apps/api/tests/test_snapshot_db_service.py apps/api/tests/test_snapshot_gate.py apps/api/tests/test_snapshots_scope.py apps/api/tests/test_snapshots_m4_remainders.py` — **37 passed**.
Files: `apps/api/app/database_backup.py`, `apps/api/app/snapshots.py` (`snapshot_flow`), `apps/api/tests/test_snapshot_db_service.py`, `apps/api/tests/test_snapshot_gate.py` (freshness on 20 still 10 minutes).

Former db-service mentions (`rg "/web/database|db\.dump|dump_db|ServerProxy"` in `apps/api/app` and `packages/odoo-client/src`). None of them called the removed service. On major 20:

1. `packages/odoo-client/src/odoo_client/client.py` `OdooClient.__init__` — `ServerProxy` for `xmlrpc/2/common` and `xmlrpc/2/object` only. No `xmlrpc/2/db` and no `dump_db`. Unchanged on major 20.
2. `apps/api/app/sandbox.py` `_sandbox_rpc` — comment that the return shape matches the old ServerProxy pair. It routes `execute_kw` through the object service. It does not open the db service on major 20.
3. `apps/api/app/snapshot_gate.py` `require_production_snapshot` — a caller can set `require_web_database_backup`. On major 20 that flag is forced off and a metadata snapshot id is accepted. The gate never HTTP-calls `/web/database`. The 10-minute freshness window and the last-write check still apply (`test_odoo20_metadata_snapshot_keeps_ten_minute_freshness_window`).
4. `apps/api/app/rollback_tiers.py` tier `database_snapshot` — records `requires: /web/database` with `live_restore: False` and `not_for` `odoo_20`, `odoo_online`, `odoo_sh`. It does not restore. Unchanged. On major 20 it still does not call the endpoint.
5. No `dump_db` function and no `/web/database` HTTP client existed. `request_database_backup` (via `snapshot_flow(kind="database")`) is the database-level backup entry. On major 20 it returns the host-backup message and does not call the client. Odoo.sh and Odoo Online get that refusal on any major (`test_snapshot_refuses_on_odoo_sh_and_online`). A 20 fake that raises on `/web/database` is used for metadata `snapshot_view` and is never hit. ≤19 self-host also gets no new dump client.

Not done: live production callers do not pass `odoo_major` into `require_production_snapshot`, so the major-20 branch is unreached there; the dump stays impossible because there is no dump client. `database_backup.py` uses `>= 20` and `snapshot_gate.py` uses `== 20`. L4 off. No aonb.odoo.com call. No Docker.

CLAIM O20-09 2026-10-03T11:15:00Z files: Community 20 does not claim native MCP. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-09. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Product UI must never say native/MCP is *available* on Community 20 (no ai* modules). Connect copy that Odoo RPC keys are *not* Cursor MCP stays unchanged.
UI audit (`rg MCP apps/web/src`): only connect-checklist.ts, ConnectApiKeyGuide.tsx, connect/page.tsx — all negate Cursor MCP / RPC-vs-MCP guidance. No “MCP available”, “native MCP available”, or similar positive availability strings.
Files: `apps/web/src/lib/odoo-native-mcp.ts`, `apps/web/src/lib/odoo-native-mcp.test.ts` (helper mirrors `native_mcp_present`; vitest scans `src/` for positive MCP availability copy).
Pytest: `.venv/bin/python -m pytest -q -p no:cacheprovider packages/odoo-client/tests/test_odoo20_version_table.py::test_community_without_ai_modules_has_no_native_mcp` — **1 passed**.
Vitest: `pnpm --filter @odoo-custom/web exec vitest run src/lib/odoo-native-mcp.test.ts` — **3 passed**.
Not done: L4 off. No aonb.odoo.com call. No UI banner for MCP absence (silence is correct).

CLAIM O20-10 2026-10-03T11:20:00Z files: sandbox major gate includes 20. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-10. Worker only. No commit. No push. No customer DB. L4 stays off.
Intent: `./docker/run-sandbox-major-gate.sh` accepts major **20** and uses existing `docker/docker-compose.odoo20.yml` (project `odoo20-custom-dev`, host **8073**). Major **15** still rejected before Docker.
Commands:
- `./docker/run-sandbox-major-gate.sh 15` → **exit 2** (`Unsupported major: 15 (allowed: 16 17 18 19 20)`).
- `./docker/run-sandbox-major-gate.sh 20` → **exit 0**. `SandboxResult(ok=True, module='sandbox_smoke_m20', odoo_major=20)` after first-run blockers were fixed (Odoo 20 loopback-only HTTP on published port; Postgres 16 for `db20`; smoke zip `security/ir_access.xml` with `operation=crud` not per-perm `read`).
Files: `docker/run-sandbox-major-gate.sh`, `docker/docker-compose.odoo20.yml`, `apps/api/app/sandbox.py` (`sandbox_stack_for_major(20)` → odoo20 compose; XML-RPC default unchanged), `packages/module-generator` (major ≥20 ACL XML), `apps/api/app/ai_structural_zip_gate.py` (accept `ir_access.xml`).
Not done: L4 off. No aonb.odoo.com. No commit.

CLAIM O20-11 2026-10-03T11:40:00Z files: Odoo 20 sandbox flow checks. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-11. Worker only. No commit. No push. No customer DB. L4 stays off.
Intent: Quote-to-cash, procure-to-pay, and manufacture on the local Community 20 sandbox (`docker/docker-compose.odoo20.yml`, project `odoo20-custom-dev`, http://127.0.0.1:8073, XML-RPC admin/admin, db `sandbox_test`). No existing 7/6/2 flow runner; Autopilot `job_autopilot/smoke.py` is a different done-bar. Added `apps/api/scripts/run_odoo20_flow_checks.py` (`rpc_protocol=xmlrpc`, records prefixed `ingenium_o20_`). Stack was down on fresh volumes; started compose and `odoo db init sandbox_test` (same path as `sandbox._init_db`). First pass installed stock apps `sale_management`, `purchase`, `mrp` on this sandbox only after `state='uninstalled'`.
Counts (second run, apps already installed):
- quote-to-cash **7/7** (customer, product, quotation, confirm, delivery, invoice, invoice_post)
- procure-to-pay **6/6** (vendor, product, rfq, confirm, receipt, vendor_bill posted)
- manufacture **2/2** (mfg.order mo=2 bom=2, mfg.produce done)
Command: `uv run --directory apps/api python scripts/run_odoo20_flow_checks.py` → exit 0. First-run bill post needed `invoice_date` on 20; script writes today's date then posts. Cleanup cancels/unlinks drafts; posted/done rows stay prefixed. Sandbox XML-RPC default unchanged.
Not done: L4 off. No aonb.odoo.com. No commit.

CLAIM O20-12 2026-10-03T11:45:00Z files: designer list arch is list on Odoo 20. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-12. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Designer form/list writers on major 20 emit `<form>` and `<list>`; list root is never `<tree>`. Major 16 listing views stay `<tree>`.
Change: `render_list_arch` uses `views_v20.list_arch_root` (18+ `list`, ≤17 `tree`). Designer preview/save already go through `render_arch` + connection major.
Tests: `.venv/bin/python -m pytest -q -p no:cacheprovider packages/odoo-client/tests/test_view_arch.py packages/odoo-client/tests/test_view_parse.py packages/odoo-client/tests/test_view_arch_reporting.py` — **56 passed** (2 new: `test_render_list_arch_major20_root_is_list_never_tree`, `test_render_list_arch_major16_root_stays_tree`).
Not done: L4 off. No aonb.odoo.com. No Playwright 20 fixture (unit test sees the arch). No designer restyle.

CLAIM O20-13 2026-10-03T11:50:00Z files: docs/runbooks/odoo20-production-checklist.md. Do not enable L4. Do not call aonb.odoo.com.

Operator checklist only — not a completed production run on a customer database.

Track: O20. Card: O20-13. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: `docs/runbooks/odoo20-production-checklist.md` — bot user + expiring RPC API key, `ODOO_PROTOCOL=auto` / JSON-2 vs explicit `rpc_protocol=xmlrpc`, version-table verify rows (V06, V24, V26, V28–V30), 20 deltas (`company_type`, registry, pricelist discount, `ir.access`), duplicate-DB flow tests vs local 7/7·6/6·2/2 sandbox, invoice print check, Community no native MCP, operator-owned DB dumps + 10‑min metadata snapshot, sandbox-before-promote.
Not done: L4 off. No aonb.odoo.com. Checklist does not assert JSON-2 `/doc` text match verified. No customer DB execution.

CLAIM O20-14 2026-10-03T12:00:00Z files: name_search keyword from the version table. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-14. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: ``name_search`` filter keyword is ``args`` on 16–18 and ``domain`` on 19–20 via ``difference("name_search_kw", major)`` — not hardcoded at API call sites.
Change: `packages/odoo-client/src/odoo_client/compat/name_search.py` (`build_name_search_execute_kw`); JSON-2 mapper + `Json2Transport.odoo_major`; `apps/api/app/data_import.py` `_resolve_m2o`.
Call sites in `apps/api/app`: `data_import.py` only (``rpc_classify.py`` lists the method name, no RPC).
Tests: `.venv/bin/python -m pytest -q -p no:cacheprovider packages/odoo-client/tests/test_name_search_compat.py` — **4 passed**.
Not done: L4 off. No aonb.odoo.com. No commit.

CLAIM O20-15 2026-10-03T12:10:00Z files: formatted_read_group on 19 and 20. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-15. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: grouped aggregate RPC uses ``read_group`` on 16–18 and ``formatted_read_group`` on 19–20 via ``difference("read_group", major)`` — legacy ``read_group`` is not sent on major 20.
Change: `packages/odoo-client/src/odoo_client/compat/read_group.py` (`aggregate_rpc_method`, `build_aggregate_execute_kw`); `resolve_aggregate_rpc_method` in `client.py` `_dispatch_execute` and `Json2Transport.execute_kw`; JSON-2 mapper `_read_group_body` in `execute_kw_map.py`.
Call sites in `apps/api/app`: none (allowlists only in `rpc_classify.py`, `mcp_guard.py`). Transport/client rewrite covers callers that still pass ``read_group`` on 19+.
Tests: `.venv/bin/python -m pytest -q -p no:cacheprovider packages/odoo-client/tests/test_read_group_compat.py` — **6 passed**.
Not done: L4 off. No aonb.odoo.com. No commit.

CLAIM O20-16 2026-10-03T12:15:00Z files: 19-to-20 spec replay fails closed. Do not enable L4. Do not call aonb.odoo.com.

Track: O20. Card: O20-16. Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: A 19 config spec replayed as major 20 either applies through the existing `compile_access` translator (`ir.access`) or fails with a named migration note. The first refused op leaves the fake port at `call_count == 0`.
Command: `.venv/bin/python -m pytest -q -p no:cacheprovider apps/api/tests/test_odoo20_spec_replay.py` — **8 passed**.
Known refusals: `company_type` removed; group record rules must become `ir.access` with a domain; percentage pricelist is discount; `company_registry` is additional identifiers. Verify rows V06, V24, V26, V28–V30 are named as not translated, not guessed into a field name.
Files: `apps/api/app/odoo20/spec_replay.py`, `apps/api/tests/test_odoo20_spec_replay.py`, `docs/runbooks/odoo20-spec-that-will-not-translate.md`.
Not done: L4 off. No aonb.odoo.com. No commit. JSON-2 track stays open.

CLAIM UI-F03-A 2026-10-03T12:20:00Z files: first five operate empty states. Do not enable L4. Do not do the other 65 pages.

Track: T7 UI-F03 (batch A). Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: First five connection operate pages that could show ad-hoc loading or empty lists use kit Skeleton + EmptyState; list routes avoid treating an unloaded fetch as an empty list.
Pages (5):
- `apps/web/src/app/connections/[id]/builder/page.tsx` — `listHydrated` + skeleton via `BuilderModelsList`
- `apps/web/src/app/connections/[id]/menus/page.tsx` — same for `MenusTree`
- `apps/web/src/app/connections/[id]/automations/page.tsx` — same for `AutomationsList`
- `apps/web/src/app/connections/[id]/access/page.tsx` — same for rights/rules lists
- `apps/web/src/app/connections/[id]/import/page.tsx` — seed pack picker skeleton + empty `EmptyState` (removed “Loading packs…”)
Tests: `pnpm exec vitest run src/components/automations/AutomationsList.test.tsx` — **3 passed** (empty list + loading skeleton; no `Loading...` string).
Not done: remaining ~65 operate routes (UI-F03 continues). L4 off. No commit.

CLAIM UI-F03-B 2026-10-03T12:25:00Z files: next five operate empty states. Do not redo batch A. Do not enable L4.

Track: T7 UI-F03 (batch B). Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Next five connection operate pages replace ad-hoc Suspense/empty list copy with kit Skeleton + EmptyState; list areas use a hydrated flag cleared before fetch and set in `finally`.
Pages (5):
- `apps/web/src/app/connections/[id]/projects/page.tsx` — Suspense fallback skeleton; `ProjectsPageInner` `listHydrated` + board loading gate
- `apps/web/src/app/connections/[id]/modulespec/page.tsx` — Suspense fallback skeleton
- `apps/web/src/app/connections/[id]/reports/page.tsx` — report list skeleton + `EmptyState`
- `apps/web/src/app/connections/[id]/approvals/page.tsx` — rules/entries skeleton + `EmptyState`
- `apps/web/src/app/connections/[id]/script-runner/page.tsx` — library/history skeleton + `EmptyState`
Tests: `pnpm exec vitest run src/components/projects/ProjectBoard.test.tsx` — **3 passed** (empty list + loading skeleton; no `Loading...` string).
Not done: remaining operate routes (UI-F03 continues). L4 off. No commit.

CLAIM UI-F03-C 2026-10-03T12:30:00Z files: next five operate empty states. Do not redo batches A or B. Do not enable L4.

Track: T7 UI-F03 (batch C). Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Next five connection operate pages use kit Skeleton + EmptyState; list/feed areas use a hydrated flag cleared before fetch and set in `finally`.
Pages (5):
- `apps/web/src/app/connections/[id]/journal/page.tsx` — timeline `listHydrated` + skeleton + empty action
- `apps/web/src/app/connections/[id]/bulk-suite/page.tsx` — `pageHydrated` hero skeleton + empty action
- `apps/web/src/app/connections/[id]/cron-manager/page.tsx` — `CronJobsList` + `listHydrated`
- `apps/web/src/app/connections/[id]/housekeeping/page.tsx` — attachment scan `EmptyState`
- `apps/web/src/app/connections/[id]/live-demo-copilot/page.tsx` — answers/transcript `feedHydrated` + `EmptyState`
Tests: `pnpm exec vitest run src/components/cron/CronJobsList.test.tsx` — **3 passed** (empty list + loading skeleton; no `Loading...` string).
Not done: remaining operate routes (UI-F03 continues). L4 off. No commit.

CLAIM UI-F03-D 2026-10-03T12:35:00Z files: next operate empty states. Do not redo batches A–C. Do not enable L4.

Track: T7 UI-F03 (batch D). Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Next five operate routes replace ad-hoc empty list copy or in-flight-as-empty with kit Skeleton + EmptyState; hydrated flags set in `finally`.
Pages (5):
- `apps/web/src/app/connections/[id]/power-ops/page.tsx` — recipe grid `listHydrated` + skeleton + empty re-probe action
- `apps/web/src/app/connections/[id]/website/page.tsx` + `apps/web/src/components/website/WebsiteEditor.tsx` — page list `listHydrated` / `pagesLoading`
- `apps/web/src/app/connect/page.tsx` — saved connections `listHydrated` + empty scroll-to-form action
- `apps/web/src/app/approvals/page.tsx` — plan inbox `inboxHydrated` + Skeleton + empty refresh action
- `apps/web/src/app/connections/[id]/page.tsx` — promoted modules empty + loading skeleton on overview develop tab
Tests: `pnpm exec vitest run src/components/website/WebsiteEditor.test.tsx` — **4 passed** (empty + loading skeleton; no `Loading...` string).
Remaining: `rg -n 'Loading\.\.\.' apps/web/src/app` → **0** literal hits; operate routes without kit empty/loading (e.g. designer, studio, wizard, job, ingest, config, id-generator, reminders, expert) still open for UI-F03. L4 off. No commit.

CLAIM UI-F03-E 2026-10-03T12:40:00Z files: designer studio wizard job ingest empty states. Do not redo batches A–D. Do not enable L4.

Track: T7 UI-F03 (batch E). Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Five named operate routes use kit Skeleton + EmptyState on real list/feed areas; hydrated flags set in `finally` where fetches apply.
Pages (5):
- `apps/web/src/app/connections/[id]/designer/page.tsx` + `DesignerAdvancedMetaAside` — published checkpoint list `snapshotsHydrated` via `useDesignerPageBootstrap`
- `apps/web/src/app/connections/[id]/studio/page.tsx` + `StudioChatThread` — empty refine feed + composer focus action
- `apps/web/src/app/connections/[id]/wizard/page.tsx` + `DraftStudioReusePanel` — stock reuse catalog skeleton + empty retry/clear-search
- `apps/web/src/app/connections/[id]/job/page.tsx` + `JobAutopilotHandoffBar` — promote-target connections `targetsHydrated` in `finally`
- `apps/web/src/app/connections/[id]/ingest/page.tsx` — **skipped** (upload/interview forms only until a job exists; no page-level empty collection)
Tests: `pnpm exec vitest run src/components/draft-studio/DraftStudioReusePanel.test.tsx` (batch E primary); extended `JobAutopilotHandoffBar.test.tsx` for job promote targets.
Not done: config, id-generator, reminders, expert, etc. L4 off. No commit.

CLAIM UI-F03-F 2026-10-03T12:45:00Z files: config id-generator reminders expert empty states. Do not redo batches A–E. Do not enable L4.

Track: T7 UI-F03 (batch F). Worker only. No commit. No push. No Odoo host. L4 stays off.
Intent: Named operate routes use kit Skeleton + EmptyState on real list/feed areas; hydrated flags set in `finally` where fetches apply.
Pages (4):
- `apps/web/src/app/connections/[id]/config/page.tsx` + `ConfigAtlasBrowser` — atlas/recipes hydrate + expert sequences list
- `apps/web/src/app/connections/[id]/id-generator/page.tsx` — preview assignments panel skeleton + empty preview action
- `apps/web/src/app/connections/[id]/reminders/page.tsx` — **skipped** (create wizard form only; success card is not an empty collection)
- `apps/web/src/app/connections/[id]/expert/page.tsx` + `IntentRouterPanel` — route matches feed skeleton + empty re-route action
Tests: `pnpm exec vitest run src/components/config/ConfigAtlasBrowser.test.tsx` (batch F primary); extended `IntentRouterPanel.test.tsx` for empty matches.
L4 off. No commit.

CLAIM UI-F03-G 2026-10-03T12:50:00Z files: remaining connection empty lists, or none. Do not redo A–F. Do not enable L4.

Track: T7 UI-F03 (batch G). Worker only. No commit. No push. No Odoo host. L4 stays off.
Scan: connection operate `page.tsx` files with `.map(` and no `EmptyState` import → builder, wizard, cron-manager, modulespec inner, ingest, operations, reminders, code-studio (A–F already cover builder/wizard/cron via child lists; ingest/reminders/operations skipped as non-fetch or form-only lists).
Pages (1):
- `apps/web/src/app/connections/[id]/code-studio/page.tsx` — safe_eval symbols `contextHydrated` in `refresh` `finally` + skeleton + empty re-probe action
Tests: none (page-only; no component file changed).
Remaining without page-level EmptyState import: operations (static hub), ingest (job-gated lists), reminders (post-submit warnings), cron-manager/wizard/builder/modulespec (handled in child components or excluded). L4 off. No commit.

## 2026-10-03 — UI-F04 Dialog and Sheet on Base UI
Track: T7 UI-F04. Worker [Move dialogs onto Base UI](0ce4a7e3-a16a-4b8b-9902-bf6925974e76). No push. L4 stays off.
Intent: Rewrite Dialog and Sheet internals onto `@base-ui/react` 1.8.0. Exported props unchanged. Direct `@radix-ui/react-dialog` removed. `cmdk` still pulls that package transitively.
Tests: `pnpm exec vitest run src/components/ui/Dialog.test.tsx` — 4 passed (name, Escape, focus trap, focus returns). `e2e/confirm-dialog.spec.ts` — 4 passed against the dev server on :3010 (`next build` still fails on pre-existing eslint errors, so Playwright reused `next dev`). Kit page: dialog and sheet open, Escape closes, focus returns to the trigger.
Not done: UI-F05 Tabs. ConfirmDialogV2 is still its own overlay, not DialogPanel. L4 off.

## 2026-10-03 — UI-F05 Tabs on Base UI
Track: T7 UI-F05. Worker [Move tabs onto Base UI](0a71bb1c-34be-453c-9543-17eb4a676c4d). No push. L4 stays off.
Intent: Rewrite Tabs onto `@base-ui/react/tabs`. Exported `Tabs` and `TabItem` unchanged. `@radix-ui/react-tabs` removed from package.json and pnpm-lock.yaml.
Tests: `pnpm exec vitest run src/components/ui/Tabs.test.tsx` — 4 passed (testid, aria-selected, roving tabindex, arrow keys). Kit page: click and ArrowRight select Tab B and show its panel. Arrow keys moved focus without selecting until a follow-up activated the focused tab.
Not done: UI-F06 Tooltip. Slot and tooltip Radix packages remain. L4 off.

## 2026-10-03 — UI-F06 Tooltip on Base UI
Track: T7 UI-F06. Worker [Move tooltips onto Base UI](579cd3ce-b19d-454f-8a5e-172cb7d18d0d). No push. L4 stays off.
Intent: Rewrite Tooltip onto `@base-ui/react/tooltip`. `Tooltip` and `TooltipProvider` props unchanged. Open delay 200 ms. `@radix-ui/react-tooltip` removed from package.json and pnpm-lock.yaml.
Tests: `pnpm exec vitest run src/components/ui/Tooltip.test.tsx` — 4 passed (keyboard focus, Escape, 200 ms hover delay, child onClick kept). Trigger uses Base UI `render` so the child's click handler is merged, not replaced.
Not done: UI-F07 Slot. `@radix-ui/react-slot` remains. Live hover was not opened in the browser. L4 off.

## 2026-10-03 — UI-F07 Button asChild without Radix Slot
Track: T7 UI-F07. Worker [Replace Radix Slot on Button](f07ca7ce-e481-40a7-9c8c-0e8b7d28aedd). No push. L4 stays off.
Intent: `Button` `asChild` merges with `@base-ui/react/merge-props` (button props first, child props second). `@radix-ui/react-slot` removed as a direct dependency. No `@radix-ui` import remains under `apps/web/src`. `cmdk` still pulls Radix dialog and slot transitively.
Tests: `pnpm exec vitest run src/components/ui/Button.test.ts src/components/ui/Button.asChild.test.tsx` — 6 passed (anchor keeps href and classes, child click runs, default button click). jsdom logs “Not implemented: navigation to another Document” on the anchor click; the assertion still passed.
Not done: UI-F08 Sonner. Live asChild link was not opened in the browser. L4 off.

## 2026-10-03 — UI-F08 remaining toasts on Sonner
Track: T7 UI-F08. Worker [Move remaining toasts to Sonner](ae7db3f1-7015-431b-b71c-0f1ba455fe0c). No push. L4 stays off.
Intent: Remove the unused `Toast.tsx` and the connection-layout `ToastProvider`. Success toasts last 4000 ms. Error toasts use `duration: Infinity` until dismissed. Sonner region is `aria-live=polite`.
Tests: `pnpm exec vitest run src/components/ui/kit.test.tsx` — 16 passed, including success auto-dismiss and an error toast still present after 10 s.
Not done: UI-F09 motion primitives. A live toast was not opened in the browser. L4 off.

## 2026-10-03 — UI-F09 motion primitives
Track: T7 UI-F09. Worker [Add motion primitives](e38e14c1-5a72-4071-b250-b9bc1e1d0c20), then a follow-up on the four unproven gaps. No push. L4 stays off.
Intent: One constants module, interruptible Drawer and SheetMotion, ListLayout on the approvals inbox and diff panes. Reduced motion fades in place.
Tests: `pnpm exec vitest run src/components/ui/motion/motion.test.tsx` — 6 passed, twice. The interrupt test starts closed, opens, samples x between 5 and 95, then closes and requires x to increase. The rendered reduced-motion case sets `data-motion-keys` to `opacity x` with `x: 0`.
Browser on `/e2e/kit`: open samples moved translateX 448 → 287 → 102. Close started at 62, then 384 → 433, so the reverse continued from the in-progress offset. With reduced motion on, the open drawer’s transform was `none` while opacity faded (0.76). Approvals renders one `motion-list-layout`. The kit diff renders one. Drawer and SheetMotion are on the kit page.
Not done: UI-F10 TOTP input. Expert and billing still use the existing Sheet. L4 off.

## 2026-10-03 — UI-F10 TOTP one-time-code input
Track: T7 UI-F10. Worker [Add TOTP one-time-code input](84f8cc05-2ce9-4ddb-a7b3-d18acf617532). No push. L4 stays off.
Intent: Login 2FA uses `input-otp` 1.5.0. Paste of 6 digits sets the code. `autocomplete="one-time-code"`. No enrol page exists.
Tests: `pnpm exec vitest run src/components/auth/TotpCodeInput.test.tsx` — 1 passed. Login page: the field is named “2FA code (if enabled)” and typing `123456` set the value to `123456`.
Not done: UI-F11 virtualized tables. L4 off.

## 2026-10-03 — UI-F11 virtualized tables
Track: T7 UI-F11. Worker [Virtualize large data tables](c387e48a-5b29-4963-892a-68ae4f869e63). No push. L4 stays off.
Intent: `react-virtuoso` 4.18.16 when a table has more than 50 rows. 50 or fewer stay a normal table. ArrowUp/ArrowDown moves the active row. Sort and filter of 5,000 rows stay under 100 ms.
Tests: `pnpm exec vitest run src/components/ui/DataTable.test.tsx` — 7 passed. Measured sort+filter 0.403 ms. Keyboard navigation did not exist before this card.
Not done: UI-F12 axe. A 51-row table was not opened in the browser. L4 off.

## 2026-10-03 — UI-F12 axe on operate routes
Track: T7 UI-F12. Worker [Extend axe coverage on operate routes](c32c15e5-7ee1-4651-aaa6-0d37ece1acae). No push. L4 stays off.
Intent: Extend the existing axe spec from 8 to 39 operate and govern routes. Disabled rules stay document-title, html-has-lang, and label. The top bar stays excluded.
Tests: Playwright `e2e/a11y-primary.spec.ts` on the dev server — 38 passed, Projects failed on list text fading through contrast 1.59. List items now stay at full opacity and only translate. Projects then passed.
Not run: `/connections` (redirect), `/bots`, `/bots/rooms/[id]`, `/bots/[id]`, `/studio/dashboards`, `/bridge/connections`, `/onboarding`. Marketing and auth routes are outside this card.
Not done: UI-F13 reorder primitive. L4 off.

## 2026-10-03 — UI-F13 canvas reorder
Track: T7 UI-F13. Worker [Add one canvas reorder primitive](5d1d48fe-0394-4c4d-b5c4-3c5ad0e46076). No push. L4 stays off.
Intent: One `ReorderableBlocks` for pointer drag and keyboard arrows. A pointer-up outside the list does not reorder. Five canvas callers use it. Saved XML and QWeb unchanged.
Tests: vitest `ReorderableBlocks.test.tsx` + `FormCanvas.test.tsx` — 7 passed. Playwright `e2e/designer-keyboard.spec.ts` — 1 passed (arrow keys swap Name and Customer, then swap back).
Not done: UI-SP-API. L4 off.

## 2026-10-03 — UI-SP-API client split
Track: T7 UI-SP-API. Worker [Split the web API client by domain](fbd5e735-aba5-409e-ac3a-038218b4974d). No push. L4 stays off.
Intent: Move `api.ts` into domain modules. `api.ts` is a 57-line re-export. No method name is defined twice. URLs and bodies were not rewritten.
Tests: `pnpm exec vitest run src/lib/api.test.ts src/lib/capabilities.test.ts src/lib/jobs.test.ts src/lib/draft-job-outcome.test.ts` — 78 passed. No file under `src/lib/api/` is over 400 lines.
Not done: UI-SP-WIZARD. L4 off.

## 2026-10-03 — UI-SP-WIZARD page split
Track: T7 UI-SP-WIZARD. Worker [Split the wizard page into components](540caf38-b9f0-486e-8810-0f758c42bb72). No push. L4 stays off.
Intent: Move the wizard page into `components/wizard/` without changing the route. The page is 13 lines and still default-exports `AppWizardPage`. No new file is over 400 lines.
Tests: draft-studio vitest — 7 passed. Playwright `e2e/wizard-scaffold.spec.ts`, `wizard-scorecard.spec.ts`, `wizard-component.spec.ts` — 4 passed.
Not done: UI-SP-STUDIO. L4 off.

## 2026-10-03 — UI-SP-STUDIO page split
Track: T7 UI-SP-STUDIO. Worker [Split the studio page into components](b2d457ed-2664-4fd6-a1ad-98f991f07e4c). No push. L4 stays off.
Intent: Move the App Studio page into `components/studio/` without changing the route. The page is 13 lines and still default-exports `AppStudioPage`. No new file is over 400 lines. Existing studio components were reused.
Tests: `pnpm exec vitest run src/components/studio` — 22 passed. `e2e/studio-preview.spec.ts` targets the designer harness, not this page, and was not run.
Not done: UI-SP-DESIGNER. L4 off.

## 2026-10-03 — UI-SP-DESIGNER page split
Track: T7 UI-SP-DESIGNER. Worker [Split the designer page into components](70ea16c2-f9c2-4f42-9247-6618678588fe). No push. L4 stays off.
Intent: Move the designer page into `components/designer/` without changing the route or styles. The page is 105 lines and still default-exports `DesignerPage`. No new file is over 400 lines.
Tests: `pnpm exec vitest run src/components/designer` — 55 passed. `e2e/designer-*.spec.ts` open `/e2e/designer` harnesses, not this route, and were not run.
Not done: UI-SP-BULK. L4 off.

## 2026-10-03 — UI-SP-BULK page split
Track: T7 UI-SP-BULK. Worker [Split the bulk suite page](0d243f91-0c1a-4ed9-9407-2676f3c6d66d). No push. L4 stays off.
Intent: Move the bulk suite page into `components/bulk/` without changing the route. The page is 67 lines and still default-exports `BulkSuitePage`. No new file is over 400 lines. Section headings stay on the page so the characterization test still matches.
Tests: `uif-regression.test.ts`, `kit.test.tsx`, `DataTable.test.tsx` — 25 passed.
Not done: UI-SP-OVERVIEW. L4 off.

## 2026-10-03 — UI-SP-OVERVIEW page split
Track: T7 UI-SP-OVERVIEW. Worker [Split the connection overview page](8264c376-2eac-4d90-8ae6-34c651576676). No push. L4 stays off.
Intent: Move the connection overview into `components/overview/` without changing the route. The page is 31 lines and still default-exports `BrowserPage`. No new file is over 400 lines. FirstRunCard, InstanceFingerprintCard, and OverviewViewsPanel were reused.
Tests: those three overview vitest files — 6 passed.
Not done: UI-SP-CONFIG. L4 off.

## 2026-10-03 — UI-SP-CONFIG page split
Track: T7 UI-SP-CONFIG. Worker [Split the config page into components](fd34a138-8715-4c28-934b-d2e6345537ec). No push. L4 stays off.
Intent: Move the config page into `components/config/` without changing the route. The page is 109 lines and still default-exports `ConfigPage`. No new file is over 400 lines. ConfigCommandCenter, ConfigAtlasBrowser, and InstanceFingerprintCard were reused.
Tests: `ConfigAtlasBrowser.test.tsx` and `ConfigCommandCenter.test.tsx` — 4 passed.
Not done: UI-SP-CSS. L4 off.

## 2026-10-03 — UI-SP-CSS stylesheet split
Track: T7 UI-SP-CSS. Worker [Split stylesheets by area](6c478512-4324-4f29-a24f-5ceb24ad58c6). No push. L4 stays off.
Intent: Split `studio-refinement.css` and `globals.css` into area files. Import order matches the original source. No selector, property, or declaration changed. Concatenating the pieces matches the committed CSS byte for byte (studio 37259 bytes, globals 30858 bytes including the Tailwind import).
Tests: Playwright `/e2e/tokens` on next dev — 3 passed (light capture, dark capture, harness render). Those tests do not pixel-diff. The recaptured PNGs differ in size and were left unstaged.
Not done: ADR-01. L4 off.

## 2026-10-03 — ADR-04 tool-call emulation ladder
Track: T8 ADR-04. Worker [Record the tool-call emulation ADR](91042cc3-9f72-4acd-a61c-007b702c86d6). No push. L4 stays off.
Intent: Record native, then `emulated_json`, then `emulated_text`. Emulated modes stay at Tier B until an eval. Partial and ambiguous actions are not tool calls. Matches ADR-03 and `parse_emulated_json`.
Not done: ADR-05. ADR-02 stays open until Tope accepts D8. L4 off.

## 2026-10-03 — ADR-05 tool list shape
Track: T8 ADR-05. Worker [Record the open tools-shape ADR](1e741b7b-264c-4cee-a3df-a3ab6f7411ed). No push. L4 stays off.
Intent: Leave union tools versus family tools undecided. GATE-P6-04 has not been run. The model still has no apply tool. Calls stay on the ADR-03 shape and the ADR-04 ladder.
Not done: ADR-06. ADR-02 stays open until Tope accepts D8. L4 off.

## 2026-10-03 — ADR-06 executor modes
Track: T8 ADR-06. Worker [Record executor Mode T and Mode C](3c014fe0-ccd8-4496-a0ba-beda76e8bc43). No push. L4 stays off.
Intent: Both modes exist. Mode T is one transaction, dry-run for non-DDL, native rollback then inverse, default 50 ops. Mode C is per-op, no dry-run, compensate in reverse, only reversible E or S and idempotent, default 15 ops, risk +1.
Not done: ADR-07. ADR-02 stays open until Tope accepts D8. L4 off.

## 2026-10-03 — ADR-07 staging clones
Track: T8 ADR-07. Worker [Record the open staging ADR](a6b4170f-081c-424d-a875-e95e06902b20). No push. L4 stays off.
Intent: Leave the clone provider unchosen. Production R3 stays blocked. Above R1 the path is review-only until staging exists.
Not done: ADR-08. ADR-02 stays open until Tope accepts D8. L4 off.

## 2026-10-03 — ADR-08 who approves
Track: T8 ADR-08. Worker [Record the approval-flow ADR](d2b51a8d-e316-4176-9d48-eadeaaeba49d). No push. L4 stays off.
Intent: Follow `02_APPROVAL_FLOW.md`. Production R3 needs two approvers who are not the requester, plus the domain owner when the target is elevated, plus simulation, backup, and an allowed window. Chat may only link to the approval page. Production expiry is 24 hours for R at or above 2. Staging expiry is 7 days. L4 stays off.
Not done: ADR-09. ADR-02 stays open until Tope accepts D8. L4 off.

## Open residuals — close these before the phase ends

Older "Not done" lines that only name the next card are closed when that card has its own later entry. This section is the list that still has to be finished. A line is removed only when that leftover is done.

### Waiting on you
- Mac §9 operator paste. Only a paste in the product UI closes this. A sandbox scorecard does not.

### Decided 2026-10-03
- D8 / ADR-02: in-house gateway. LiteLLM stays out.
- L4 thresholds confirmed. L4 stays off until GATE-L4-08 evidence exists.
- ADR-07: operator-owned neutralized clone. Production R3 stays blocked until that clone exists for the tenant. Above R1 stays review-only.
- ADR-05: family tool lists. No apply tool. GATE-P6-04 is later evidence.
- BL-08: later, as a directory split, after a second yes on the commit plan.
- Push: local only until a later explicit yes.

### Product leftovers

Execution queue. A line leaves this list only when that item is finished. Items that need a live system or a decision already made stay blocked instead of being faked.

In progress, code that can be finished without a live Odoo or a live model:
1. T4-PROG is claimed. Named stages on generation, Dashboard Studio, Expert, and bulk operations.

Closed this turn:
- Plan cards use the policy expiry. Production R0 and R1, and staging, expire in 7 days. Production R2 and above expire in 24 hours.
- `parse_tool_args` has a dedicated test for payloads over 256 KB.
- An unset module major does not emit `ir.rule`. Community 19 emits it when the major is 19, including the library and multi-company templates. Odoo 20 still refuses it.
- Confirmed tenant and database facts are in the prompt memory layer, capped at 5% of the window. Pending items, role notes, episodic memory, and global knowledge stay out.
- Apply refuses a frozen change-set and an elevate change-set with no domain owner before any write. When an observation is supplied, verify runs after the in-memory apply: R2 and above rolls back, and below R2 the result is NEEDS_HUMAN. An apply with no observation still records the journal result.
- Snapshot preflight passes the connection major from `server_version`. Major 20 and later accept a metadata snapshot. Major 19 still requires a `/web/database` backup when the caller asks. A missing major stays off the Odoo 20 path. Freshness and BILLABLE stay gated.
- The executor calls undo through validate, policy, and approval. `apply` does not call it. A refused undo does not write. An approved undo with a matching snapshot applies the inverse. A mismatch stays NEEDS_HUMAN. A field that still has rows is hidden, and the rows stay.
- Recorded prompt exchanges travel in the exported run dict and come back on restore. A payload that omits `transcript` restores an empty transcript. Tools are not replayed. A process kill still drops the run unless the caller kept that dict. GATE-P4-07 and GATE-P4-08 stay open.
- A two-hop `$ref` that lands on `account.move` is RT-11 and is not journaled. A cycle or an unresolved hop is denied. A scaffold of `account.move` spelled with Greek omicron (U+03BF) is RT-10 and is not applied. GATE-P3-05 stays open. The gate asks for RT-10 through RT-16 at 100%, and there is no corpus beyond the named cases.
- The validator folds model names with the protected registry's confusable map. A Greek omicron lookalike of a known model passes grounding as that Latin name. An `account.move` lookalike stays denied and is not applied. An unknown name that does not fold to either stays rejected.
- A missing tool-call id is `call_` plus a 26-character Crockford ULID. A provider-supplied id stays as sent. Two mints in the same millisecond do not collide. No ulid package was added.
- The XML-RPC and JSON-2 sends go through the transport contract. Plain HTTP still sends for `127.0.0.1` and `localhost`. Any other host must be HTTPS with certificate checks on. A write does not follow a redirect.
- Audit retention decides in process. A raw LLM side copy expires after 7 days. An accounting kind stays 7 years. Every other kind stays 24 months. The sweeper drops only the side copy. The chain row and `entry_hash` stay. No live database row was deleted.
- The skill router loads at most three catalog skills. Executable code and a `SKILL.md` over 2500 tokens are refused. The returned grant is the overlap with the caller and is not a superset. `skill_load` uses that router. The recall eval is not run. No score was invented.
- The expert panel and the billing upgrade sheet open through `SheetMotion`. Escape and the backdrop dismiss them. Titles and the existing actions stay.
- `ConfirmDialogV2` renders through `DialogPanel`. Confirm stays disabled until the phrase matches. Cancel, Escape, and the backdrop dismiss unless the dialog is busy. The danger confirm style stays.
- Version-table rows V01 through V32 matched the Odoo 20 tip at `aonb.odoo.com`. The live test reads `.env.json2` and skips only when that file is absent. No key was written into the test.

Blocked until something outside this repo exists. The product behavior stays the refuse or the off switch:
- T2-J1 `/doc` text match. Sandbox default stays XML-RPC. Promote stays human.
- L4 stays off until GATE-L4-08 evidence exists. The thresholds are confirmed.
- Production R3 stays blocked until an operator-owned neutralized clone exists. A customer production database is not cloned.
- GATE-P6-04 has not been run.
- BL-08 commit plan still needs the second yes before those commits.
- GATE-P1-02 live cassettes. GATE-P1-04 and GATE-P1-06 live 200-call recordings.
- T8-P4-TIERA needs a live model. Nightly only.
- The KMS vendor stays unchosen. Fernet remains the envelope.
- GATE-P3-06 needs mutmut or cosmic-ray, which are not installed.

Still to finish in code:
- T2-J1 `/doc` text match is not verified. Do not say JSON-2 is complete. Sandbox default stays XML-RPC. Promote stays human.
- L4 stays off until GATE-L4-08 evidence exists. Thresholds are confirmed.
- Production R3 stays blocked until an operator-owned neutralized clone exists for that tenant. Above R1 stays review-only.
- GATE-P6-04 has not been run. The tool shape is family lists.
- BL-08 commit plan is not written yet. A second yes is required before those commits.
- UI-F03 was not re-checked against every route in screen spec 13 marked "can be empty".
- `cmdk` still depends on `@radix-ui/react-dialog`. No source file imports it.
- Axe was not run for `/bots`, `/bots/rooms/[id]`, `/bots/[id]`, `/studio/dashboards`, `/bridge/connections`, or `/onboarding`. `/connections` only redirects.
- Durable WAL is still in memory. `apps/api/alembic/versions/s9t0u1v2w3x4_journal_wal.py` declares `journal_entry`, `before_image`, and `apply_database_lock` and has not been applied. A process kill still loses the journal. GATE-P3-03 is not closed.
- The KMS vendor is unchosen. ADR-12 keeps secrets on the existing `fernet_key`. No cloud KMS client.
- The eval harness is not built. ADR-13 records the A/B/C bars. GATE-P4-04 and GATE-P6 are still open. The skill recall eval is not run. No recall or precision score was invented.
- GATE-P0-03 is still open. The eight seed names exist only as catalog definitions in `apps/api/app/changeset/fixture_catalog.py`. Live fixtures on Odoo 17, 18, 19, and 20 were not brought up. The stand-in reset is not a live database reset.
- GATE-P0-05 stays open. `apps/api/tests/test_import_boundary.py` locks 22 Odoo-version branches outside `compat/` in `apps/api/app`. A new hit fails the test. Those branches were not moved.
- GATE-P1-02 is not fully passed. Replay fixtures under `apps/api/tests/fixtures/llm_gateway/` are synthetic. Still needs an operator recording: C07, C08, C10, C11, C13, C14, C16, C17, C18, C19, and OpenAI C20.
- The model registry stores no product model ids yet. The outside-file scan passes because that list is empty. An unknown id stays untiered with read-only caps.
- GATE-P1-04 and GATE-P1-06 are proven with 200 scripted calls, not a live cassette. A recorded live 200-call cassette is still open.
- GATE-P2-08 and GATE-P2-09 are not fully passed. The seven bridge methods are proven on an in-memory fake. Apply, rollback, a real savepoint, the live kill switch, and staging neutralization have not run on Odoo.
- Odoo 20 tip reads are recorded in `packages/odoo-client/tests/test_odoo20_drift_cells.py`. Kanban is a view type and the partner arch uses `t-name="card"`. `name_get` is missing and `display_name` is set. Company-dependent fields use a stored boolean, and `ir.property` is absent. Selection is a char plus `selection_ids`. Mail templates use `t-out` and `{{ object. }}`. `ir.translation` is absent and only `en_US` is installed, so a changed translation string was not observed. The fake drift table still says unknown for those cells. Nightly rows on 17, 18, and 19 were not run.
- Engine suite 1 and suite 2 were not run for the schema family. `model.create`, `model.scaffold`, `field.deprecate`, `selection.update`, and `constraint.sql` still have no inverse in the handler.
- Simulation staging is an in-memory clone. It is not an operator-owned neutralized database.
- GATE-P3-06 was not run. Neither mutmut nor cosmic-ray is installed. No mutation score was invented.
- Engine suite 2 round-trips 18 of 63 catalog ops. The other 45 have no handler inverse and were not stubbed.
- A second apply is proven only for the eight ops the executor can apply. The rest of the catalog is not claimed.
- GATE-P3-10 is not fully passed. Six plan-card snapshots exist, one op per family. The rest of the catalog has no snapshot.
- Changeset coverage is under the bar: 89.59% line and 79.46% branch, measured on the changeset tests, not the full suite. No CI floor was added.
- A process kill still loses a run. Resume restores an exported in-memory dict only. GATE-P4-08 is not a durable restart.
- Three tool names sit beside the card list: `changeset_validate`, `changeset_simulate`, and `changeset_render`. The registered card set is 42 names and does not include an apply tool.
- GATE-P4-07 is not closed. Compaction was not run against a live model.
- EV-AMB-01 through EV-AMB-08 have no YAML scenario bodies. The clarification rules were tested without scoring those ids.
- T8-P4-TIERA needs a live model. It is nightly only and is not a pull-request card. It has not been started.
- Op conformance is not complete. 3 of 63 catalog ops have all twelve parts: `field.create`, `field.update`, and `field.delete`. 41 reversible ops have no inverse. 55 ops have no params schema. The suite locks that gap and does not stub the missing parts.
- `docker/*` and `apps/api/tests/test_wave16_gen2.py` still use `ServerProxy` outside the XML-RPC product scan.
- Recaptured token screenshots in `docs/vision-verify/tokens-light.png` and `tokens-dark.png` are unstaged. The CSS text did not change.

### Checked in a test, not in the browser
- Tooltip hover.
- An `asChild` link after a connection is saved.
- A toast on a live page.
- A table with 51 rows.

## 2026-10-03 — ADR-09 memory model
Track: T8 ADR-09. Worker [Record the memory-model ADR](4167b26b-b1e4-4455-a875-2e1ca15eae95). No push. L4 stays off.
Intent: Four classes. Working memory is engine-trusted. Tenant or database memory is human-confirmed. Global knowledge is a pull request plus eval. Episodic memory is never auto-injected. `memory_propose` stays pending until a human confirms. Memory is at most 5% of the window. RT-47 is refused. T8-MEM is still the implementation card.
Not done: ADR-10. ADR-02 stays open until Tope accepts D8. L4 off.

## 2026-10-03 — ADR-10 skill package
Track: T8 ADR-10. Worker [Record the skill-package ADR](4215d4ff-f5b6-46c4-836f-d4210bb4ffb7). No push. L4 stays off.
Intent: No executable code in a skill. A skill can only narrow a grant. At most 3 skills load by default. `SKILL.md` is at most 2500 tokens. Router bars are recall@3 at least 0.95 and precision@3 at least 0.6 on at least 300 labeled phrasings. CI is at least 5 evals per skill and at least 12 for Tier-1. The router is not built.
Not done: ADR-11. ADR-02 stays open until Tope accepts D8. L4 off.

## 2026-10-03 — ADR-11 audit hash chain
Track: T8 ADR-11. Worker [Record the audit-chain ADR](88d5f186-340a-4ef4-9ff0-3ac4ac29425b). No push. L4 stays off.
Intent: One append-only chain. Genesis previous hash is 64 zeros. Each entry hash is SHA-256 of the canonical JSON without the hash field. Append and verify already exist in `apps/api/app/audit_chain.py`. Retention windows are still open.
Not done: ADR-12. L4 stays off.

## 2026-10-03 — ADR-12 Fernet envelope
Track: T8 ADR-12. Worker [Record the secrets ADR](594a9770-91f0-41f7-9dc8-9ee5e894e33f). No push. L4 stays off.
Intent: Fernet with the existing `fernet_key`. BYO provider keys stay under that envelope. Display the last 4 characters only. Prefer API keys over passwords. No secrets in prompts. The sandbox API-key helper is never an agent tool. The KMS vendor stays unchosen.
Not done: ADR-13. L4 stays off.

## 2026-10-03 — ADR-13 eval tiers
Track: T8 ADR-13. Worker [Record the eval-tier ADR](09e789ba-39eb-4724-9d79-f1040453c4bb). No push. L4 stays off.
Intent: A/B/C is model trust. Below A, submitted risk caps at R2. Tier C cannot submit a change-set. Emulated adapters stay at Tier B until an eval lifts that cap. Tier A is at least 80% on 60 scenarios. The suite is at least 150 scenarios, with at least one Tier A model. Local models stay honestly B or C. The harness is not built.
Not done: ADR-14. L4 stays off.

## 2026-10-03 — ADR-14 supported versions
Track: T8 ADR-14. Worker [Correct the version ADR](661f85d0-4687-4928-b753-b727039b09b6). No push. L4 stays off.
Intent: Community 20, 19, 18, and 17 stay GA. 16 stays experimental. Majors at or below 15 stay refused. `docker/docker-compose.odoo20.yml` publishes host Odoo on port 8073. `docker/run-odoo20-smoke.sh` prints the command and does not start containers. Live version-table probes stay skipped until `ODOO20_URL` is set.
Not done: T8-P0-FIX. L4 stays off.

## 2026-10-03 — T8-P0-FIX fixture catalog (partial)
Track: T8 T8-P0-FIX. Worker [Add named fixture seeds](47369d57-dde6-406f-a67a-7b96ad3df8b4). No push. L4 stays off.
Intent: Offline catalog with the eight seed names, 150 `messy_client` field definitions, nightly-only `huge`, and a stand-in reset under 60 seconds that refuses a customer URL. Re-ran `tests/test_fixture_catalog.py`: 6 passed. Live fixtures on 17, 18, 19, and 20 were not brought up. GATE-P0-03 stays open.
Not done: T8-P0-LINT. The live fixture gate stays open. L4 stays off.

## 2026-10-03 — T8-P0-LINT import boundaries (partial)
Track: T8 T8-P0-LINT. Worker [Add import-boundary lint tests](46dec7bc-ef95-45d8-be27-6b6a6cb09c31). No push. L4 stays off.
Intent: Changeset does not import `llm_gateway` or `agent_runtime`. Provider SDK imports stay out of the tree outside `llm_gateway/adapters/`. A planted version branch outside `compat/` fails. Re-ran `tests/test_import_boundary.py`: 10 passed. The real tree still has 22 version branches outside `compat/`. GATE-P0-05 stays open.
Not done: T8-GW-TYPES. GATE-P0-03 and GATE-P0-05 stay open. L4 stays off.

## 2026-10-03 — T8-GW-TYPES tool limits
Track: T8 T8-GW-TYPES. Worker [Add canonical tool limits](88508d36-f23c-4f2f-9105-1e5ab2f802cd). No push. L4 stays off.
Intent: Tool names match `[a-z][a-z0-9_]{2,40}`. Descriptions are at most 1024 characters. The three adapter bodies reject a bad name before building a request. Re-ran gateway and adapter tests: 19 passed.
Not done: T8-GW-NORM. GATE-P0-03 and GATE-P0-05 stay open. L4 stays off.

## 2026-10-03 — T8-GW-NORM normalization rules
Track: T8 T8-GW-NORM. Worker [Cover the missing gateway rules](193bbc9f-2f7c-444f-ad60-6f0692a0c648). No push. L4 stays off.
Intent: Rules 3, 4, 6, 7, 8, and 9 now have a test. Parallel reads share a batch and writes stay sequential. Roles are repaired. Stop reasons and usage are recorded. Reasoning drops on a provider switch. Text is NFC. Re-ran gateway, adapter, phase-1, and import-boundary tests: 47 passed. Call ids stay `call_{index:04d}`. The ulid form is still open.
Not done: T8-GW-C. GATE-P0-03 and GATE-P0-05 stay open. L4 stays off.

## 2026-10-03 — T8-GW-C conformance replay (partial)
Track: T8 T8-GW-C. Worker [Replay the conformance cases](ad0e5490-f995-4204-9893-72ae7f6d68de). No push. L4 stays off.
Intent: Synthetic replay for Anthropic, OpenAI, and Gemini covers C01, C02, C03, C04, C05, C06, C09, C12, and C15. C20 is replayed for Anthropic and Gemini. C11, C18, and C19 are scored and do not fail the suite. Re-ran the gateway and replay tests: 42 passed. The fixtures are not live recordings. GATE-P1-02 stays open.
Not done: T8-GW-REG. GATE-P0-03, GATE-P0-05, and GATE-P1-02 stay open. L4 stays off.

## 2026-10-03 — T8-GW-REG model registry
Track: T8 T8-GW-REG. Worker [Lock the model registry](0559f9ca-3265-4955-903e-993aa6e46730). No push. L4 stays off.
Intent: An unknown model id stays untiered and uses read-only caps. It cannot submit a change-set. A planted model id outside the registry file fails the scan. Re-ran the registry tests: 3 passed. The registry stores no product model ids yet, so the live scan has an empty list.
Not done: T8-GW-REST. GATE-P0-03, GATE-P0-05, and GATE-P1-02 stay open. L4 stays off.

## 2026-10-03 — T8-GW-REST remaining gateway gates
Track: T8 T8-GW-REST. Worker [Close the remaining gateway gates](478aa352-b0d4-4e78-99aa-4e170fd82da7). No push. L4 stays off.
Intent: The provider map in `docs/verified-facts.md` lists OpenAI, Anthropic, and Gemini only. Two hundred scripted calls match stream to complete, and 190 of 200 emulated calls are accepted. Retry stops at 4. Argument repair stops at 2. The call budget defaults to 40. Raw keys are dropped before the adapter stores the request. Re-ran gateway and import-boundary tests: 53 passed. The loops are scripted. A live cassette is still open. GATE-P1-02 stays open.
Not done: T8-OD-TRANSPORT. GATE-P0-03, GATE-P0-05, and GATE-P1-02 stay open. L4 stays off.

## 2026-10-03 — T8-OD-TRANSPORT transport contract
Track: T8 T8-OD-TRANSPORT. Worker [Prove the transport contracts](4ff81ddc-bfd0-4eb7-a602-88b11aea9d12). No push. L4 stays off.
Intent: A fake send function enforces two calls per database, a 30-second read timeout, a 120-second write timeout, TLS with `verify=false` refused, no write redirects, and bounded retries. Re-ran `tests/test_transport_contract.py`: 24 passed. The gate is not wrapped around XML-RPC or JSON-2. No live Odoo transport was used.
Not done: T8-OD-ENV. GATE-P0-03, GATE-P0-05, and GATE-P1-02 stay open. The transport gate is not on the live adapters. L4 stays off.

## 2026-10-03 — T8-OD-ENV environment profile
Track: T8 T8-OD-ENV. Worker [Complete the environment profile](31979eb9-5eae-452e-81c5-829f345e01ea). No push. L4 stays off.
Intent: The profile builds from an in-memory payload. Majors at or below 15 are refused. An unsupported major is read-only Q&A. An unavailable API is Guided Mode only. Re-ran `tests/test_env_profile.py` and `tests/test_read_plane.py`: 18 passed. No socket was opened.
Not done: T8-OD-GRAPH. GATE-P0-03, GATE-P0-05, and GATE-P1-02 stay open. The transport gate is not on the live adapters. L4 stays off.

## 2026-10-03 — T8-OD-GRAPH schema graph
Track: T8 T8-OD-GRAPH. Worker [Prove the schema graph bars](87906f5a-7896-48b3-8676-4f3b3ee696c8) timed out after adding the sample cap. The labeled checks were finished in the follow-up. No push. L4 stays off.
Intent: `messy_client` builds from 150 in-memory field names. Search stops at 200 rows. A sample returns 5. `find_usages` on the labeled set is at least 0.98 precision and 0.95 recall. Two reads of the same payload keep the same fingerprint. Re-ran `tests/test_schema_graph.py`: 6 passed. No live database was read.
Not done: T8-OD-BRIDGE. GATE-P0-03, GATE-P0-05, and GATE-P1-02 stay open. The transport gate is not on the live adapters. L4 stays off.

## 2026-10-03 — T8-OD-BRIDGE in-memory protocol
Track: T8 T8-OD-BRIDGE. Worker [Prove the bridge protocol](c9222a36-3958-43ef-8602-f7133f5bb35f). No push. L4 stays off.
Intent: The seven methods are proven on an in-memory fake. Unknown ops fail closed. DDL does not dry-run in place. The kill switch stops apply. A stolen key is refused. Promotion replays a change-set and does not copy a database. Re-ran the bridge tests: 16 passed. No addon was installed. GATE-P2-08 and GATE-P2-09 stay open.
Not done: T8-OD-DRIFT. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, and GATE-P2-09 stay open. L4 stays off.

## 2026-10-03 — T8-OD-DRIFT version table
Track: T8 T8-OD-DRIFT. Worker [Record version drift with fakes](693df5c9-eb6f-487e-8f41-adcce98e227f). No push. L4 stays off.
Intent: Fake answers cover the checklist rows the existing version tests did not already lock. Known cells cite code already in the repo. Unstated cells stay unknown. Re-ran `tests/test_t8_od_drift.py`: 93 passed, 44 skipped. The skips are the live nightly rows. No major was probed.
Not done: T8-OP-SCHEMA. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, and GATE-P2-09 stay open. Live drift nightly stays unrun. L4 stays off.

## 2026-10-03 — T8-OP-SCHEMA risk rules
Track: T8 T8-OP-SCHEMA. Worker [Prove schema operation risk rules](4cb0ebb5-ee0c-4378-8524-d9fdef7ad48c). No push. L4 stays off.
Intent: A compute field is R3. A type change is refused. A non-empty financial, HR, or stock delete is R4. `constraint.sql` is allowed on `x_` models only. Cascade and protected scaffolding were already refused. Re-ran schema and import-boundary tests: 15 passed. The version-branch count stayed 22. Engine suite 1 and suite 2 were not run.
Not done: T8-OP-UI. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, and GATE-P2-09 stay open. L4 stays off.

## 2026-10-03 — T8-OP-UI risk rules
Track: T8 T8-OP-UI. Worker [Prove UI operation risk rules](59c4dc29-43da-4da5-9fa6-f965f07297df). No push. L4 stays off.
Intent: UI ops stay R1. The three report ops stay R2. A view inherit already required one anchor. `report.inherit` now does too. An XPath that replaces the root or a large subtree is refused. Re-ran UI, handler, and import-boundary tests: 101 passed. The version-branch count stayed 22. Engine suites were not run.
Not done: T8-OP-LOGIC. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, and GATE-P2-09 stay open. L4 stays off.

## 2026-10-03 — T8-OP-LOGIC risk rules
Track: T8 T8-OP-LOGIC. Worker [Prove logic operation risk rules](76259126-ba68-46a4-b79a-1058e693fd62). No push. L4 stays off.
Intent: Code, email, SMS, and webhook server actions are R3. Outbound or mass automation is R3. Cron stays R3. An accounting, journal, or legal sequence is R4. The safe_eval checker rejects the named RT-25 patterns and does not run the snippet. Re-ran logic, schema, handler, and import-boundary tests: 52 passed. The version-branch count stayed 22. The full engine suite was not run.
Not done: T8-OP-SEC. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, and GATE-P2-09 stay open. L4 stays off.

## 2026-10-03 — T8-OP-SEC risk rules
Track: T8 T8-OP-SEC. Worker [Prove security operation risk rules](ae3e8883-ba64-4571-9d51-0a10bf9f1705). No push. L4 stays off.
Intent: A group that would imply admin is R4 and is not written. A group-less ACL is R4. Assigning admin, system, or service is R4. `user.unlink` stays out of the catalog. On Odoo 20, rule create and update compile to `ir.access` through the existing compiler. Re-ran security, Odoo 20 access, and import-boundary tests: 32 passed. The version-branch count stayed 22. The full engine suites were not run.
Not done: T8-OP-SET. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, and GATE-P2-09 stay open. L4 stays off.

## 2026-10-03 — T8-OP-SET risk rules
Track: T8 T8-OP-SET. Worker [Prove settings and module risk rules](93004747-6c26-4262-b069-f08e5a8b0df1). No push. L4 stays off.
Intent: Module install and upgrade stay R3 and may be billable on paid editions. Uninstall stays R4 and is refused before any port call. Protected keys, lock dates, fiscal year, currency, and the chart of accounts are R4. Install warns that reversal is uninstall. Re-ran settings and import-boundary tests: 18 passed. The version-branch count stayed 22. No live module was installed.
Not done: T8-OP-DATA. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, and GATE-P2-09 stay open. L4 stays off.

## 2026-10-03 — T8-OP-DATA risk rules
Track: T8 T8-OP-DATA. Worker [Prove data operation risk rules](228dae57-1c5f-4236-b6d6-01527c49ac34). No push. L4 stays off.
Intent: A sample is at most 20 rows. The cap is 1000. Batches are 200. Merge stays R3 and is not reversible. Delete stays R4, needs two approvers who are not the requester plus an allow-list, and defaults to deny. `stock.quant` is refused. Re-ran data and import-boundary tests: 14 passed. The version-branch count stayed 22. No live write.
Not done: T8-PROT. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, and GATE-P2-09 stay open. L4 stays off.

## 2026-10-03 — T8-PROT protected registry
Track: T8 T8-PROT. Worker [Prove the protected registry](08b36e8b-c703-46b2-9266-cfd6b6e4fba8). No push. L4 stays off.
Intent: RT-10 through RT-16 each have a named test for `protected_deny`, `policy_denied`, and R4. A tenant `remove_models` list does not shrink the core set. Elevate is risk +1 and sets `domain_owner`. Re-ran protected-registry and import-boundary tests: 25 passed. The version-branch count stayed 22.
Reviewer: what could be wrong is that `domain_owner` is a flag on the policy decision and apply does not yet refuse when that person has not approved. The named RT tests cover the known shapes, not every confusable or nested `$ref`.
Not done: T8-RISK. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, and GATE-P2-09 stay open. L4 stays off.

## 2026-10-03 — T8-RISK escalations
Track: T8 T8-RISK. Worker [Prove risk only goes up](b6758ea2-9bcf-4c10-8705-7a2d050ebd0c). No push. L4 stays off.
Intent: Rows over 1000 or users over 10, outbound, production with no simulation, and Mode C each add one risk level. A raise stops at R4. Final risk stays at least the catalog risk. A caller-supplied risk does not lower it. Re-ran risk and import-boundary tests: 15 passed. The version-branch count stayed 22.
Not done: T8-POLICY. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, and GATE-P2-09 stay open. L4 stays off.

## 2026-10-03 — T8-POLICY approval matrix
Track: T8 T8-POLICY. Worker [Prove the approval policy matrix](3e4b52b1-75e3-4af5-95e6-45c2aedc1481). No push. L4 stays off.
Intent: The ten risk and environment cells are covered, plus freeze and expiry. Production R3 needs two approvers, a passed simulation, a backup, and an allowed window. The requester cannot approve their own R3. R4 is denied. L4 does not lower a production count. Re-ran the matrix and import-boundary tests: 22 passed. The version-branch count stayed 22. GATE-P3-06 was not run.
Reviewer: expiry and freeze live on the policy decision. The executor does not call `apply_blocked`, and plan cards still use 24 hours for every production risk.
Not done: T8-VALID. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, and GATE-P3-06 stay open. L4 stays off.

## 2026-10-03 — T8-VALID nine stages
Track: T8 T8-VALID. Worker [Prove the nine validation stages](a629db01-4116-43dc-adf3-86e3a64fb448). No push. L4 stays off.
Intent: All nine stages stay on the report even when shape fails. Params over 64 KB, nesting past depth 12, and the three prototype-pollution keys are refused. Repair stops after four rounds. Re-ran the engine and import-boundary tests: 34 passed. The version-branch count stayed 22.
Not done: T8-SIM. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, and GATE-P3-06 stay open. L4 stays off.

## 2026-10-03 — T8-SIM simulation modes
Track: T8 T8-SIM. Worker [Prove the simulation modes](585d9931-4695-42a6-8077-28d1ff290d64). No push. L4 stays off.
Intent: Static, Bridge dry-run, staging, and synthetic modes run in process. A failed simulation returns the plan to planning. Production apply without a recorded simulation is refused unless policy allows an R1 direct apply. A DDL op stays off the in-place path. The runtime `changeset_simulate` tool now calls that module. Re-ran simulation, runtime, and import-boundary tests: 30 passed. The version-branch count stayed 22. No live Odoo call.
Not done: T8-EXEC. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, and GATE-P3-06 stay open. L4 stays off.

## 2026-10-03 — T8-EXEC journal schema
Track: T8 T8-EXEC. Worker [Add a durable executor journal](6645bf27-b6c6-45e4-a6c2-ba6fef57c1fd). No push. L4 stays off.
Intent: The migration declares the journal, before-image, and per-database lock tables. It was not applied. Recovery of a stale APPLYING run that has INTENT and no RESULT compensates and is not verified. An unknown outcome is not retried and becomes NEEDS_HUMAN. Re-ran WAL and import-boundary tests: 15 passed. The version-branch count stayed 22. The journal rows are still in memory. GATE-P3-03 stays open.
Not done: T8-VERIFY. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, and GATE-P3-06 stay open. L4 stays off.

## 2026-10-03 — T8-VERIFY checks
Track: T8 T8-VERIFY. Worker [Prove verification checks](ca31c2b8-57c3-41f7-9964-69d8945629e4). No push. L4 stays off.
Intent: Nine fake checks. A failure rolls back at R2 and above. Below that the outcome is NEEDS_HUMAN and links to `docs/runbooks/4-failed-rollback.md`. A model success flag cannot turn a failure into verified. Re-ran verify and import-boundary tests: 29 passed. The version-branch count stayed 22. No live view was rendered. The executor does not call `verify` yet.
Not done: T8-ROLLBACK. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, and GATE-P3-06 stay open. L4 stays off.

## 2026-10-03 — T8-ROLLBACK undo
Track: T8 T8-ROLLBACK. Worker [Prove undo as a change-set](f7543fc4-55e4-42d9-84ae-860038fef6a1). No push. L4 stays off.
Intent: Undo runs through validate, policy, and approval. A MetaSnapshot mismatch is NEEDS_HUMAN. When a new field still has rows, undo hides the field and reports the remaining count. Deleting those rows is a separate higher-risk approval. Re-ran rollback and import-boundary tests: 22 passed. The version-branch count stayed 22. No live undo. The executor does not call undo yet.
Not done: T8-META. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, and GATE-P3-06 stay open. L4 stays off.

## 2026-10-03 — T8-META snapshot
Track: T8 T8-META. Worker [Add an order-independent snapshot](827aebfa-c7fb-435d-8996-d238b942d7f9). No push. L4 stays off.
Intent: MetaSnapshot is an in-memory export. `metadata_snapshots` stays the per-resource restore table because that shape is different. Equality ignores key order and list order. Allowlisted config keys stay. Secret-shaped keys are dropped. Ingenium xmlids stay. Re-ran snapshot and import-boundary tests: 18 passed. The version-branch count stayed 22. Full engine suite 2 was not run.
Not done: T8-CARD. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, and GATE-P3-06 stay open. L4 stays off.

## 2026-10-03 — T8-CARD plan goldens
Track: T8 T8-CARD. Worker [Add plan card golden files](4a40cde0-b79f-4031-9704-5c988555107e). No push. L4 stays off.
Intent: One snapshot for schema, UI, logic, security, settings, and data. Changing an assumption changes the hash. Production cards still expire at 24 hours for every risk. Re-ran golden and import-boundary tests: 24 passed. The version-branch count stayed 22. GATE-P3-10 stays open because the other catalog ops have no snapshot.
Not done: T8-CLI. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, GATE-P3-06, and GATE-P3-10 stay open. L4 stays off.

## 2026-10-03 — T8-CLI change-set commands
Track: T8 T8-CLI. Worker [Add an LLM-free change-set CLI](54b146a0-5db4-47e9-8a88-2dd4a4a7bd66). No push. L4 stays off.
Intent: plan, validate, simulate, apply, and rollback run a two-op file on an in-memory port. Apply returns verified. Rollback leaves the port empty. The module does not import an LLM package and does not open a socket. Re-ran CLI and import-boundary tests: 13 passed. The version-branch count stayed 22.
Not done: T8-P3-COV. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, GATE-P3-06, and GATE-P3-10 stay open. L4 stays off.

## 2026-10-03 — T8-P3-COV changeset coverage
Track: T8 T8-P3-COV. Worker [Measure changeset test coverage](0f980822-f72d-4d42-8f6e-03cdaff2168b). No push. L4 stays off.
Intent: Line coverage is 89.59%. Branch coverage is 79.46%. The bar is 90% and 80%. No CI floor was added. The run was the changeset tests, not the full suite. That run also failed three approval tests that used a group-less ACL. A group-less ACL is R4, so those tests now use `sales.group_sale_user` and pass.
Not done: T8-RUN. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, GATE-P3-06, GATE-P3-08, and GATE-P3-10 stay open. L4 stays off.

## 2026-10-03 — T8-RUN phase machine
Track: T8 T8-RUN. Worker [Prove the phase machine](c1f72282-ac2a-42ef-8980-9b263bea1052). No push. L4 stays off.
Intent: A scripted run walks INTAKE through REPORT with no LLM. No phase exposes an apply tool. The third identical call returns LOOP_DETECTED. The fourth aborts. That matches the source: three times is the warning, and the next identical call aborts. Resume restores an exported in-memory dict. A process kill still loses the run. Re-ran runtime and import-boundary tests: 23 passed. The version-branch count stayed 22.
Not done: T8-TOOLS. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, GATE-P3-06, GATE-P3-08, GATE-P3-10, and GATE-P4-08 stay open. L4 stays off.

## 2026-10-03 — T8-TOOLS tool names
Track: T8 T8-TOOLS. Worker [Match the registered tool names](7db910dd-fa4d-424c-98d6-f0e66cf3879e). No push. L4 stays off.
Intent: The registered names equal the 42-name card list. Tool payloads stay inside `wrap_untrusted`. `data_sample` returns at most 5 rows. `ask_user` returns at most 3 questions. `memory_propose` stays pending. Re-ran tool, runtime, and import-boundary tests: 30 passed. The version-branch count stayed 22. No apply tool was added.
Not done: T8-PROMPT. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, GATE-P3-06, GATE-P3-08, GATE-P3-10, and GATE-P4-08 stay open. L4 stays off.

## 2026-10-03 — T8-PROMPT budgets
Track: T8 T8-PROMPT. Worker [Prove prompt compaction and scrubbing](40519cbd-47b8-4700-94a6-4a3cf70bef27). No push. L4 stays off.
Intent: A 30-turn transcript compacts without splitting tool-call pairs. The cached prefix is scrubbed. System and tools stay at or under 15 percent, skills 15, memory 5, history 40, and tool results 25. The result stays at or under 90 percent. Re-ran prompt and import-boundary tests: 14 passed. The version-branch count stayed 22. No live model was called. GATE-P4-07 stays open.
Not done: T8-CLARIFY. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, GATE-P3-06, GATE-P3-08, GATE-P3-10, GATE-P4-07, and GATE-P4-08 stay open. L4 stays off.

## 2026-10-03 — T8-CLARIFY rules
Track: T8 T8-CLARIFY. Worker [Prove the clarification rules](01cfc562-371b-4216-a43a-0c0cc39f1560). No push. L4 stays off.
Intent: The runtime asks when targets conflict, a safe default is missing, an R3 request is underspecified, sources conflict, or the topic is financial, HR, or legal. R0 and R1 proceed when assumptions are stated. A fact already answered is not asked again. Re-ran clarify and import-boundary tests: 38 passed. The version-branch count stayed 22. EV-AMB-01 through EV-AMB-08 were not scored.
Not done: T8-CRITIC. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, GATE-P3-06, GATE-P3-08, GATE-P3-10, GATE-P4-07, and GATE-P4-08 stay open. L4 stays off.

## 2026-10-03 — T8-CRITIC cannot waive policy
Track: T8 T8-CRITIC. Worker [Prove the critic cannot waive policy](18c01d2d-8b51-4b1b-90c3-ee88c4e35ecd). No push. L4 stays off.
Intent: The checklist runs for Tier A when risk is R2 or higher, or when there are at least 5 ops. An approve verdict does not change the policy decision. R4 stays denied. The critic cannot lower risk, skip approval, or mark a plan verified. Re-ran critic and import-boundary tests: 37 passed. The version-branch count stayed 22. No live model was called.
Not done: T8-MEM. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, GATE-P3-06, GATE-P3-08, GATE-P3-10, GATE-P4-07, and GATE-P4-08 stay open. L4 stays off.

## 2026-10-03 — T8-MEM pending confirmation
Track: T8 T8-MEM. Worker [Prove pending memory confirmation](5014f649-fec8-417f-92a4-b987c2f336d1). No push. L4 stays off.
Intent: `memory_propose` stores a pending tenant or database item until `confirm_memory`. A role note is refused and does not become a tenant fact. A tool call cannot write global knowledge. Episodic memory is not injected. Re-ran memory, tool, runtime, and import-boundary tests: 35 passed in the worker run; this follow-up re-ran memory, tools, runtime, and import-boundary: 22 plus 13 passed. The version-branch count stayed 22. Confirmed text is not fed into the live prompt.
Not done: T8-S01. T8-P4-TIERA waits on a live model and is nightly only. GATE-P0-03, GATE-P0-05, GATE-P1-02, GATE-P2-08, GATE-P2-09, GATE-P3-03, GATE-P3-06, GATE-P3-08, GATE-P3-10, GATE-P4-07, and GATE-P4-08 stay open. L4 stays off.

## 2026-10-03 — T8-S01 op conformance
Track: T8 T8-S01. Worker [Check every op for twelve parts](3ee9bfbd-a2cd-48b7-9b9f-75fa6493770a). No push. L4 stays off.
Intent: The catalog has 63 ops. Three pass every part: `field.create`, `field.update`, and `field.delete`. Forty-one reversible ops have no inverse. Fifty-five ops have no params schema. An unknown op type fails closed. The suite locks that gap so a new hole fails the test. No inverse was stubbed. Re-ran the suite and import-boundary tests: 12 passed. The version-branch count stayed 22.
Not done: T8-S02. The twelve-part gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S02 round trip
Track: T8 T8-S02. Worker [Round-trip ops that already invert](e6ef9194-4659-4a30-88eb-314ac0b8b589). No push. L4 stays off.
Intent: Apply, verify, inverse, then MetaSnapshot equality for the 18 ops whose handlers already return an inverse. The other 45 are listed and not stubbed. A snapshot mismatch is not success. Re-ran the suite and import-boundary tests: 30 passed. The version-branch count stayed 22. This is not a green result for the whole catalog.
Not done: T8-S03. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S03 idempotency
Track: T8 T8-S03. Worker [Prove a second apply writes nothing](2b53a71a-5910-42ce-8125-7568780aac27). No push. L4 stays off.
Intent: A second apply of the same plan does not call create or write again. That covers eight ops the executor can apply. The other catalog ops are listed and not claimed. A repeat that would write fails closed. Re-ran the suite, the existing idempotency test, and import-boundary tests: 22 passed. The version-branch count stayed 22.
Not done: T8-S04. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S04 atomicity
Track: T8 T8-S04. Worker [Prove mode T and mode C atomicity](09f32556-9909-461b-8994-590943605629). No push. L4 stays off.
Intent: A Mode T failure clears the in-memory plan and is not verified. Mode C compensates from the last applied step backward. A partial apply is not reported as verified. An irreversible Mode C op fails closed. Re-ran the suite and import-boundary tests: 16 passed. The version-branch count stayed 22. The journal is still in memory. GATE-P3-03 stays open.
Not done: T8-S05. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S05 state machine
Track: T8 T8-S05. Worker [Prove only legal phase transitions](ac15a162-50fa-4eb2-ab87-af2cb4b2518f). No push. L4 stays off.
Intent: All 26 legal phase edges are allowed. A skip from INTAKE to EXECUTE is refused. The phase table was not changed. Re-ran the suite, the existing skip test, and import-boundary tests: 38 passed. The version-branch count stayed 22.
Not done: T8-S06. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S06 approval binding
Track: T8 T8-S06. Worker [Prove approval is bound to the hash](f75781b1-2049-40f4-8db4-e35b2aff36e1). No push. L4 stays off.
Intent: Apply refuses a changed plan hash or a changed schema fingerprint before a write. A matching pair may apply on the fake port. A bound fingerprint with no live schema fails closed. Re-ran the suite and import-boundary tests: 14 passed. The version-branch count stayed 22. No live approval ran.
Not done: T8-S07. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S07 stale schema
Track: T8 T8-S07. Worker [Prove a stale plan cannot apply](101fd5cf-6357-46b9-9027-6ffcea8b5ac8). No push. L4 stays off.
Intent: An out-of-band schema change after approval is STALE. Apply does not run. The run is not verified. A missing live slice fails closed and is not treated as current. Re-ran the drift suite and import-boundary tests: 12 passed. The version-branch count stayed 22. No live database was probed.
Not done: T8-S08. The inverse gap stays open. T8-P4-TIERA waits on a live model. GATE-P3-06 stays open. L4 stays off.

## 2026-10-04 — T8-S08 policy suite
Track: T8 T8-S08. Worker [Point the policy suite at the matrix](0be6677d-b5e7-46ba-a805-551a86bbf151). No push. L4 stays off.
Intent: The suite calls the existing approval matrix. Production R4 is deny. Production R3 asks for two approvers. Freeze and expiry are checked. GATE-P3-06 is skipped because mutmut and cosmic-ray are not installed. No mutation score was recorded. Re-ran the suite with the memory, prompt, and import-boundary tests: 24 passed, 1 skipped. The version-branch count stayed 22.
Not done: T8-S09. GATE-P3-06 stays open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S09 protected registry
Track: T8 T8-S09. Worker [Point the protected-registry suite at RT-10–16](7e22ace5-6ea8-481d-920a-cdd8583bc921). No push. L4 stays off.
Intent: The suite points at the existing RT-10 through RT-16 tests. A protected scaffold or stored-compute field op is denied before a journal write. GATE-P3-05 stays open. A two-hop `$ref` on a field relation is still unclassified. A scaffold of `account.move` spelled with Greek omicron (U+03BF) is still applied. Re-ran the suite, the registry tests, and import-boundary tests: 28 passed. The version-branch count stayed 22.
Not done: T8-S10. GATE-P3-05 stays open. GATE-P3-06 stays open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — protected registry holes
Track: T8 T8-S09 follow-up. Worker [Deny the two-hop ref and Greek omicron scaffold](226f3b6a-7c96-403f-9407-510ae5a8b0bf). No push. L4 stays off.
Intent: A two-hop `$ref` that lands on `account.move` is RT-11 and is not journaled. A cycle or an unresolved hop is denied. A chain that ends on `sale.order` stays allowed. Greek omicron (U+03BF) folds to Latin o, so that scaffold is RT-10 and is not applied. GATE-P3-05 stays open. Re-ran the suite, the registry tests, and import-boundary tests: 28 passed. The version-branch count stayed 22.
Not done: T8-S10. GATE-P3-05 stays open. GATE-P3-06 stays open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S10 validator fuzz
Track: T8 T8-S10. Worker [Point the validator fuzz suite at existing checks](1aa166c2-690c-4d2b-b4fe-104a2b6217f4). No push. L4 stays off.
Intent: The suite calls the existing validator for oversized params, depth past the limit, and prototype-pollution keys, and it runs the existing NaN and duplicate-key test. A mail-template payload deeper than the limit is rejected and is not applied. Greek omicron in a model name is not folded. That stays an open hole. Re-ran the suite, the changeset engine tests, and import-boundary tests: 38 passed. The version-branch count stayed 22.
Not done: T8-S11. The validator still does not fold Greek omicron. GATE-P3-05 stays open. GATE-P3-06 stays open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — validator model fold
Track: T8 T8-S10 follow-up. Worker [Fold Greek omicron model names in the validator](50e38b8a-e552-47a4-a579-7cb41e60b5c4). No push. L4 stays off.
Intent: Grounding folds model names with the protected registry's existing confusable map. A Greek omicron lookalike of a known model passes as that Latin name. An `account.move` lookalike stays denied and is not journaled. An unknown name that does not fold to either stays rejected. Re-ran the validator suite, the protected suite, the engine tests, the registry tests, and import-boundary tests: 58 passed. The version-branch count stayed 22.
Not done: T8-S11. GATE-P3-03 stays open. GATE-P3-05 stays open. GATE-P3-06 stays open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S11 crash injection
Track: T8 T8-S11. Worker [Inject crashes at journal boundaries](29cc6661-c7f3-4cfe-b82e-cef93d50f841). No push. L4 stays off.
Intent: A crash after INTENT and BEFORE, and a crash after a partial RESULT, are not verified. Mode T drops RESULT rows. Mode C compensates reversible ops backward. An irreversible Mode C op is refused before a journal row. The journal is still the in-process list. GATE-P3-03 stays open. Re-ran the crash suite, the atomicity suite, the WAL tests, and import-boundary tests: 28 passed. The version-branch count stayed 22.
Not done: T8-S12. GATE-P3-03 stays open. GATE-P3-05 stays open. GATE-P3-06 stays open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S12 unknown outcome
Track: T8 T8-S12. Worker [Prove an unknown write is not retried](65a48524-4dfb-4855-9d17-426fcf1fb1fc). No push. L4 stays off.
Intent: An unknown write is NEEDS_HUMAN and is not verified. A second apply returns that decision and does not call the port again. There is no live read-back. GATE-P3-07 stays open. Re-ran the unknown suite, the WAL tests, the crash suite, and import-boundary tests: 28 passed. The version-branch count stayed 22.
Not done: T8-S13. GATE-P3-03 stays open. GATE-P3-07 stays open. GATE-P3-05 stays open. GATE-P3-06 stays open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S13 database lock
Track: T8 T8-S13. Worker [Prove one apply holds the database lock](1bd9d415-3787-4439-8e59-f76e1c26041f). No push. L4 stays off.
Intent: While one apply holds a database, a second apply on that database does not write. A different database can proceed. Releasing the lock lets the next apply write. The lock is in memory. The declared `apply_database_lock` table is not applied. Re-ran the lock suite, the WAL tests, and import-boundary tests: 22 passed. The version-branch count stayed 22.
Not done: T8-S14. GATE-P3-03 stays open. GATE-P3-07 stays open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S14 bridge
Track: T8 T8-S14. Worker [Point the bridge suite at the existing refusals](f7715ae7-73db-4493-b8b8-45e0fae0971a). No push. L4 stays off.
Intent: A non-DDL dry-run leaves the in-memory checksum unchanged. An in-place DDL apply does not write. A killed bridge does not write. A live savepoint and a live kill switch have not run on Odoo. GATE-P2-08 and GATE-P2-09 stay open. Re-ran the bridge suite, the protocol tests, and import-boundary tests: 15 passed. The version-branch count stayed 22.
Not done: T8-S15. GATE-P2-08 and GATE-P2-09 stay open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S15 data ops
Track: T8 T8-S15. Worker [Point the data-op suite at the existing caps](f7d88273-46b6-479f-99bf-947a411a8e3b). No push. L4 stays off.
Intent: The suite calls the existing sample, row, and batch caps, and the R4 delete and uninstall refusals. A `data.delete` does not reach the port. A sample over 20 is refused. No live rows were deleted. Re-ran the data suite, the data-op tests, and import-boundary tests: 16 passed. The version-branch count stayed 22.
Not done: T8-S16. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S16 redaction
Track: T8 T8-S16. Worker [Point the redaction suite at the existing scrub](41ef2e5d-bbec-4b97-85e6-903403a0a514). No push. L4 stays off.
Intent: The suite calls the existing chain and scrub tests. A log line, a chain payload, and a trace that contain the fake secret `sk-test-redaction-marker` are stored only after scrubbing. The raw marker is absent. Storing the raw line is refused. Re-ran the redaction suite, the audit-chain tests, the gateway phase-1 tests, and import-boundary tests: 31 passed. The version-branch count stayed 22.
Not done: T8-S17. GATE-P1-02 stays open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S17 provider conformance
Track: T8 T8-S17. Worker [Point the conformance suite at the existing gate cases](43cb465a-af56-4c53-b0f4-dc95e51d3767). No push. L4 stays off.
Intent: The suite calls the existing C01 through C20 gate test. It passes on synthetic fixtures. Live recordings are still missing for C07, C08, C10, C11, C13, C14, C16, C17, C18, C19, and OpenAI C20. Those ids are not marked passed. GATE-P1-02 stays open. Re-ran the conformance suite, the gateway phase-1 tests, and import-boundary tests: 28 passed. The version-branch count stayed 22.
Not done: T8-S18. GATE-P1-02 stays open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T8-S18 boundaries
Track: T8 T8-S18. Worker [Point the last suite at SSRF and IDOR blocks](f71addde-f92d-4c54-9bf1-ad3d63a9d679). No push. L4 stays off.
Intent: The suite calls the existing SSRF and cross-connection tests. A link-local URL is rejected before any request. Another connection's card is not found. A fake scrubber secret is absent from the stored text. GATE-P3-01 stays open. Eighteen suite files on disk are not that gate. Re-ran the boundary suite, the gateway phase-1 tests, the inbox tests, and import-boundary tests: 32 passed. The version-branch count stayed 22.
Not done: the product leftovers that still need a live system or a decision stay open. The inverse gap stays open. T8-P4-TIERA waits on a live model. L4 stays off.

## 2026-10-04 — T1 cards already meeting acceptance
Track: T1. No new product code. No commit. L4 stays off.
Intent: Re-ran the named tests. Cards whose acceptance boxes were already true are marked DONE in `14_WORK_CARDS.md`.
Commands and results: `tests/test_sandbox_test_enable.py` and `tests/test_ai_schema_client.py` — 17 passed. `tests/test_pr_f0_entrypoint.py`, `tests/test_generate_ir_spine.py`, `tests/test_generate_ir_closed_class.py`, `tests/test_invent_leak_closure.py`, `tests/test_invent_outside_admit_wave0.py` — 44 passed. `tests/test_approved_craft_default_off.py` and `tests/test_option_a_prove_bar.py` — 9 passed. `bash apps/api/scripts/dump_maintenance_ir_trace.sh` with `AI_INTENT_LLM=off` exited 0. Stamp `20261004T045007`. `scrub_hits` is empty. Checklist and parts models appear at `admit_and_apply` and remain at the end. `rg` on `ai_generate_ir*.py` finds the words maintenance and service only in comments, not in an `if` branch. `STRUCTURAL_ALLOWLIST` is the named allowlist. `test_uncued_not_allowlisted_not_schema_verified_rejected`, `test_named_rate_line_invent_rejected_without_o2m_cue`, and `test_schema_verified_reuse_rejects_without_cue` are present.
Gates passed: T1-PF, T1-F0, T1-A1, T1-A2, T1-A3, T1-B1, T1-B2, T1-B3, T1-C1, T1-D1, T1-D2, T1-E2.
Not done: T1-F2 still needs a test that fails if `if "maintenance" in brief` is added. That card is already claimed. T1-GATE is the next unclaimed card.

CLAIM T1-GATE 2026-10-04T04:52:00Z files: a test that fails if Maintenance is special-cased, plus the progress log. Do not add a display_name denylist. Do not edit apps/api/app/changeset or agent_runtime.

## 2026-10-04 — T1-GATE
Track: T1 T1-GATE. Worker [Add the Maintenance special-case gate test](53375afe-b8e4-4553-845b-7b7a579e158a). Tester [Re-run the Maintenance special-case test](7edad533-68c3-4161-a154-72ba59386c3e). No commit. L4 stays off.
Intent: A source scan fails if an if or elif condition mentions maintenance or a service card. Comments may mention those words.
Files: `apps/api/tests/test_generate_ir_closed_class.py`.
Commands and results: VERIFIED. pytest `tests/test_generate_ir_closed_class.py` — 10 passed in 0.78s.
Gates passed: T1-GATE. Stale-catalog deny tests remain in `tests/test_ai_schema_client.py`.
Negative tests: the AST scan is the negative.
Not done: none on this card.
Risks introduced: none. Product code was not edited.

CLAIM T4-PROG 2026-10-04T04:55:00Z files: the four surfaces that still show a generic spinner, plus a shared StageProgress component if it is missing. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit.

## 2026-10-04 — T4-PROG
Track: T4 T4-PROG. Worker [Replace generic spinners with named stages](b9708403-c91d-4e13-b0c2-95201de45cb6). Tester [Re-run the live-progress acceptance checks](e1e10f5a-48e5-467f-afc4-9cf25fb7df64). No commit. L4 stays off.
Intent: Named stages on generation, bulk operations, Expert, and Dashboard Studio. Detail is closed until Show details. A tool-call limit waits for Continue or Stop.
Files: `apps/api/app/progress/`, `apps/api/app/routers/progress.py`, `apps/web/src/components/progress/StageProgress.tsx`, studio, bulk-suite, expert, and `apps/web/src/app/studio/dashboards/page.tsx`.
Commands and results: VERIFIED. pytest `tests/test_stage_bus.py` and `tests/test_progress_router.py` — 4 passed. vitest `StageProgress.test.tsx` and `IntentRouterPanel.test.tsx` — 5 passed. `rg animate-spin` on the four surface files returned nothing.
Gates passed: T4-PROG. Unknown stage names fail `test_unknown_stage_is_rejected`.
Negative tests: that unknown-stage test.
Not done: saving dashboards and charts stays on T4-DASH. This card is the progress shell.
Risks introduced: generation, expert, and bulk routes now emit stage events.

CLAIM 5A-02 2026-10-04T05:05:00Z files: dry-run ledger and the write routes in T1, T3, and T4 that are not already covered. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit.

## 2026-10-04 — 5A-02
Track: T5A 5A-02.
Intent: A live Odoo write is refused until the same arguments were dry-run, and two workers share that receipt for one hour.
Model / band: grok-4.7-high. Pressure 14. Worker [Cover every T1 T3 T4 write with a dry-run](6bc75a75-2da1-4e8f-b214-852e0ddb694a). Tester [Re-run the dry-run acceptance checks](b7a18d31-769b-4940-9d53-2025d4b716a2). Reviewer [What could be wrong with the dry-run](d61ecf1d-bf98-4c28-914e-12a7bccbcb02).
Files: `apps/api/app/dry_run_ledger.py`, `apps/api/app/dry_run_middleware.py`, `apps/api/app/db_models.py`, `apps/api/alembic/versions/t0u1v2w3x4y5_dry_run_seen.py` (untracked, revises `s9t0u1v2w3x4`, not applied), `apps/api/tests/test_dry_run_ledger.py`.
Commands and results: VERIFIED. `pytest tests/test_dry_run_ledger.py` — 15 passed. The nine-file set named by the tester — 75 passed.
Gates passed: 5A-2, DoD 22.
Negative tests: a live write with no prior receipt returns `dry_run_receipt_required`; an omitted `dry_run` key is refused the same way; a receipt written through one store authorizes the matching write through another store on the shared `dry_run_seen` table; TTL is 1 hour.
Route table (`METHOD:path`, hash is tool plus args minus dry_run):
- POST `/api/ai/sessions/{session_id}/apply` — gated
- POST `/api/connections/{connection_id}/module-spec/apply` — gated
- POST `/api/connections/{connection_id}/module-spec/seed-walkthrough` — gated
- POST `/api/ai/sessions/{session_id}/generate` — not an Odoo write
- POST `/api/connections/{connection_id}/modules/install-community` — gated
- POST `/api/connections/{connection_id}/modules/promote` — gated
- POST `/api/connections/{connection_id}/modules/uninstall` — gated
- POST `/api/connections/{connection_id}/sandbox/run` — not an Odoo write
- POST `/api/bridge/contracts/validate` — not an Odoo write
- `bridge.queue.enqueue` — not an Odoo write
- POST `/api/dashboard-studio/preview` — not an Odoo write
- offline `claim_db` — not an Odoo write
- GET `/api/connections/{connection_id}/automations/triggers` — read
- `skills route_skills` / `mcp_call` — not an Odoo write
Not done: `t0u1v2w3x4y5` is not applied. Hosts with `DB_MIGRATIONS=auto` need that revision before two processes share receipts. The web client must send `dry_run: true` before a live apply, install, promote, or uninstall. No commit.
Risks introduced: those six gated routes now refuse a body that omits `dry_run`.

CLAIM T4-OFF 2026-10-04T04:32:00Z files: apps/web/src/lib/offline/queue.ts, the API routes that must claim a key through claim_db, and tests for a dropped ack, reload, a second tab, and a queued promote. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit. Do not auto-flush a promote.

## 2026-10-04 — T4-OFF
Track: T4 T4-OFF.
Intent: A client queue survives reload and a second tab, a dropped ack does not double-apply, and a queued promote waits for a person.
Model / band: cursor-grok-4.6-high-fast. Pressure 13. Worker [Add the client offline queue](9d1c3125-0c6e-41e8-a90b-f08139078a11). Repair [Fix the offline queue reload order](3289969b-32db-45fe-b369-6ce99d83e085). Tester fail [Re-run the offline-queue acceptance checks](01d988f3-846e-47af-8d4c-02e33e29e952). Tester pass [Re-check the offline queue after the repair](62af82b8-17d0-4f95-b3d7-2f1f5d5fdeec). No reviewer. Pressure is 13.
Files: `apps/web/src/lib/offline/queue.ts`, `apps/web/src/lib/offline/queue.test.ts`, `apps/api/app/routers/offline.py`, `apps/api/app/offline/flush.py`, `apps/api/app/offline/idempotency.py`, `apps/api/app/main.py`, `apps/api/tests/test_offline_flush.py`.
Commands and results: VERIFIED. vitest `src/lib/offline/queue.test.ts` — 6 passed. pytest `tests/test_idempotency_store.py` and `tests/test_offline_flush.py` — 9 passed. Line 272 of the queue test is unchanged and passing.
Gates passed: T4-OFF, master DoD 10.
Negative tests: two tabs flushing the same item produce one server effect. A promote without the confirm phrase is refused.
Not done: `:8001` does not reload, so the flush route is not live until that process is restarted. Studio screens are not wired to enqueue. No commit. L4 stays off.
Risks introduced: `enqueue` assigns a strictly increasing `createdAt` when the clock does not move.

CLAIM T4-ISPEC 2026-10-04T04:40:00Z files: a serializer for the existing ModuleSpec in packages/module-generator, plus a property test over the existing complex fixtures. Do not add a second module IR. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit.

## 2026-10-04 — T4-ISPEC
Track: T4 T4-ISPEC.
Intent: ModuleSpec serializes to ISPEC and parses back into the same type, including nested fields.
Model / band: grok-4.7-high. Pressure 14. Worker [Add a lossless ModuleSpec ISPEC round-trip](42ab15c5-f1cc-4173-aa33-6f907090f219). Tester [Re-run the ISPEC round-trip checks](360e79d3-8082-4071-861b-b71890d2379e). Reviewer [What could be wrong with the ISPEC round-trip](3de2d00b-f16d-4697-9929-a3a85754cd1e): no blocking finding. An earlier tester, [Re-run the ISPEC round-trip checks](710dbe0d-9828-486c-ab9f-8d5f70126d4c), stalled and was not used.
Files: `packages/module-generator/src/module_generator/ispec.py`, `packages/module-generator/src/module_generator/__init__.py`, `packages/module-generator/tests/test_ispec_roundtrip.py`.
Commands and results: VERIFIED. `pytest --rootdir=. tests/test_ispec_roundtrip.py -q` — 7 passed.
Gates passed: compiler DoD 1–2.
Negative tests: a dropped field and an unknown field are refused. A non-ModuleSpec input is refused. `ispec.py` defines no second spec type.
Not done: Recompile, Sync, and the browser agent. No commit. L4 stays off.
Risks introduced: none beyond a new serializer on the existing type.

CLAIM T4-SYNC 2026-10-04T12:40:00Z files: a versioned recompile store next to ModuleSpec, plus drift blocking for Sync. Do not overwrite an artifact in place. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit. Do not start the browser agent.

## 2026-10-04 — T4-SYNC
Track: T4 T4-SYNC.
Intent: Recompile writes a new version and leaves the previous one. Drift blocks Sync. An identical spec into an existing version path is refused.
Model / band: grok-4.7-high. Pressure 15. Worker [Add versioned recompile and drift blocking](d82b3b15-b709-4842-b9ba-5d33852af752). Tester [Re-run the recompile and sync checks](8b46cd38-c6ff-4880-88aa-586818a7a47a). Reviewer [What could be wrong with recompile and sync](ff557834-e2ee-4456-9d54-8db496063db3) blocked a failed log append. Repair [Keep a failed recompile log from blocking the next version](9cf2303a-d5e2-47c5-867c-3c521cfbbee1). Tester [Re-check recompile after the log-failure repair](2ea4cc26-06a1-40a8-b199-37c8119baf72). Reviewer [What could be wrong after the log-failure repair](33046df9-b16c-4c66-97f9-9b0d373b5e03) blocked a swallowed removal and a partial log line. Last repair [Close the recompile log and disk mismatch](f053c892-5897-4c59-bb91-15a4ce312e65). Tester [Re-check recompile after the last log repair](ebf3e318-d31b-42a9-84be-b8131e0c6e7c). Reviewer [What could be wrong with the final recompile log](ecba8f05-ce15-45a3-b39d-ea2874692f54): no blocking finding.
Files: `packages/module-generator/src/module_generator/sync.py`, `packages/module-generator/src/module_generator/__init__.py`, `packages/module-generator/tests/test_recompile_sync.py`.
Commands and results: VERIFIED. `pytest --rootdir=. tests/test_recompile_sync.py tests/test_ispec_roundtrip.py -q` — 20 passed.
Gates passed: compiler DoD 3–5, master DoD 11.
Negative tests: an identical spec into an existing version path is refused. A failed log append does not block a changed spec. A failed removal is not swallowed. A write that persists bytes before raising does not leave a partial line.
Not done: the browser agent. No commit. L4 stays off. Drift fixtures are not a live Odoo database.
Risks introduced: the log is published by replacing `recompile.log` with a complete temp file.

CLAIM T4-BROWSER 2026-10-04T13:30:00Z files: the Stage F structural zip gate and a browser-testing check that runs inside it. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit. Do not claim the gate without a caught defect.

## 2026-10-04 — T4-BROWSER
Track: T4 T4-BROWSER.
Intent: Stage F runs a browser check that catches a view-arch defect the Python syntax and ACL checks miss, and a clean fixture measures the false-positive rate.
Model / band: cursor-grok-4.6-high-fast. Pressure 11. Worker [Run a browser check inside Stage F](ea7e83ae-de82-4eba-a14d-2529f9d3cc9e). Tester [Re-run the Stage F browser-check acceptance](629f5bb1-4f9f-4c6e-9dfd-f93b298f175d). No reviewer. Pressure is 11.
Files: `apps/api/app/ai_structural_zip_gate.py`, `apps/api/app/ai_browser_agent.py`, `apps/api/tests/test_ai_structural_zip_gate_browser.py`, `apps/web/src/testing/browserAgent/`.
Commands and results: VERIFIED. pytest the structural zip gate tests plus `tests/test_ai_structural_zip_gate_browser.py` — 15 passed. vitest `src/testing/browserAgent/inspect.test.ts` — 2 passed.
Gates passed: compiler DoD 6–7, master DoD 12.
Negative tests: the clean fixture of `x_ticket_browser` is not reported as `view_arch_unparseable`. False-positive rate is 0 / 1 views = 0.0.
Not done: this is a static tour of the zip, not a live Odoo browser. No commit. L4 stays off.
Risks introduced: every `structural_zip_gate` call now also runs the arch tour.

CLAIM T4-WIRE 2026-10-04T13:42:00Z files: the path from a sketch to ModuleSpec, including the clarify step and Stage H. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit. Do not call a live model in a test.

## 2026-10-04 — T4-WIRE
Track: T4 T4-WIRE.
Intent: A checked-in sketch becomes a ModuleSpec through Stage H. An unlabeled region asks and does not apply.
Model / band: cursor-grok-4.6-high-fast. Pressure 11. Worker [Turn a sketch into a spec through Stage H](5d204385-6a04-48f1-a019-ffa7e2623f03). Tester [Re-run the wireframe Stage H checks](d5158fad-4542-4469-bedc-5b451312c280). No reviewer. Pressure is 11.
Files: `apps/api/app/wireframe/`, `apps/api/app/ai_apply_readiness.py`, `apps/api/app/spec_apply_ui.py`, `apps/api/tests/test_wireframe.py`, `apps/api/tests/test_wireframe_stage_h_gate.py`, `apps/web/src/lib/wireframe-stage-h.test.ts`.
Commands and results: VERIFIED. pytest `tests/test_wireframe.py` and `tests/test_wireframe_stage_h_gate.py` — 9 passed. vitest `src/lib/wireframe-stage-h.test.ts` — 1 passed.
Gates passed: compiler DoD 12, master DoD 13.
Negative tests: an unlabeled region and a vision misread do not apply. The wireframe package does not call a live model. There is one sketch-to-spec path and it runs Stage H.
Not done: no upload screen. Live vision is not wired. No commit. L4 stays off.
Risks introduced: live apply refuses a wireframe spec that has not passed Stage H.

CLAIM T4-LLM3 2026-10-04T13:56:00Z files: the existing in-house gateway under apps/api/app/llm_gateway. Do not add LiteLLM. Do not change the gateway decision. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit. Do not call a live model in a test.

## 2026-10-04 — T4-LLM3
Track: T4 T4-LLM3.
Intent: The in-house gateway switches provider without a change above it. The Anthropic adapter stays inactive unless a test opts in.
Model / band: composer-2.5-fast. Pressure 9. Worker [Prove the gateway can switch providers](1674edb4-930c-45b0-9d19-2b12cd9f5b85). Tester [Re-run the three-tier gateway checks](75d4df4e-e85e-411c-979a-fc5cdc598f8f). No reviewer. Pressure is 9.
Files: `apps/api/app/llm_gateway/providers.py`, `apps/api/tests/test_llm_gateway_providers.py`.
Commands and results: VERIFIED. pytest the five gateway test modules — 56 passed.
Gates passed: master DoD 14.
Negative tests: the frontier adapter is inactive by default. Registry model-id strings do not leak. LiteLLM was not added. No live model call.
Not done: ADR-02 was not reopened. No commit. L4 stays off.
Risks introduced: selecting Anthropic now requires an explicit opt-in.

CLAIM T6-01 2026-10-04T14:05:00Z files: apps/api/app/client_access.py, apps/api/app/workspace_auth.py, and a role-matrix test. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit. Do not replace the login stack.

## 2026-10-04 — T6-01
Track: T6 T6-01.
Intent: Each role can reach only its route groups. A Client Viewer cannot approve, and another client’s connection stays hidden.
Model / band: composer-2.5-fast. Pressure 9. Worker [Enforce the four-role route matrix](32f2ed15-074a-4d4f-aabf-78236d968bc9). Tester [Re-run the four-role route matrix](ecbd3382-928b-4c3a-a437-74372804c951). Reviewer [What could be wrong with the role matrix](83101edc-f163-45f3-b9dc-59c989c8ce8c): no blocking finding. Reviewed because the card is access control.
Files: `apps/api/app/client_access.py`, `apps/api/app/workspace_auth.py`, `apps/api/app/routers/inbox.py`, `apps/api/app/main.py`, `apps/api/tests/test_t6_01_role_matrix.py`.
Commands and results: VERIFIED. pytest the role matrix plus the existing account and inbox suites — 83 passed. The matrix was 40 passed.
Gates passed: T6-01.
Negative tests: Client Viewer `POST /api/inbox/plans/{hash}/decide` returns 403. An out-of-scope connection returns 404.
Not done: no commit. L4 stays off. The login stack was not replaced.
Risks introduced: inbox routes now require an authenticated session.

CLAIM T4-WIRE-UPLOAD 2026-10-04T14:16:00Z files: a sketch upload screen on the existing studio look, Gemini as the live vision provider, and a single switch that selects Claude later. Do not change the Gemini default. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit. Do not call a live model in a test.

## 2026-10-04 — T4-WIRE-UPLOAD
Track: T4 wireframe upload.
Intent: A photographed sketch is read by free Gemini. Claude is one setting later. The screen does not apply.
Model / band: cursor-grok-4.6-high-fast. Worker [Add a sketch upload that stays on Gemini](2af96fb2-54b9-4dd5-8018-da122467b657). Tester [Re-check the Gemini sketch upload](3f421253-2b38-4503-a81a-a91f991e0481).
Files: `apps/web/src/app/connections/[id]/wireframe/page.tsx`, `apps/web/src/components/wireframe/WireframeUploadView.tsx`, `apps/api/app/wireframe_live.py`, `apps/api/app/routers/wireframe.py`, `apps/api/app/llm_gateway/providers.py`, `apps/api/app/llm_provider.py`, `apps/api/app/settings.py`.
Commands and results: VERIFIED. pytest the wireframe, gateway, and vision tests — 23 passed. vitest the upload view, nav, and Stage H helper — 11 passed. Browser: the page at `/connections/d41fa8a5-bcc5-4f30-a46e-0a618fef9894/wireframe` shows Sketch upload, a Photograph file input, Read sketch disabled until a file is chosen, and the line that Claude can be selected later. Live status: provider gemini, connected true. A 1-pixel PNG read returned no regions, spec null, apply_ready false.
Gates passed: Stage H still required. Gemini remains the default.
Negative tests: a missing Gemini key does not invent regions or call Claude. The upload view does not apply. AI sidebar ids are unchanged.
Not done: no commit. L4 stays off. Claude stays off until `AI_VISION_PROVIDER=anthropic`.
Risks introduced: a real photo now calls Gemini when the key is set.

CLAIM T6-02 2026-10-04T14:38:00Z files: mocked Google and Microsoft account linking, plus email password TOTP enrol and login. Do not call a live provider. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit. Do not replace the login stack.

## 2026-10-04 — T6-02
Track: T6 T6-02.
Intent: A verified provider email links with no manual step. An unverified email does not. Microsoft user info with no email_verified claim still links.
Model / band: cursor-grok-4.6-high-fast. Pressure 11. Worker [Cover Microsoft linking and TOTP enrol](99dff52e-3840-4f9f-add4-db34c4265d75). Tester [Re-run the account-linking checks](2625b41e-5ce5-42f0-b3e5-8ccf825648dd). Reviewer [What could be wrong with account linking](f2992b62-d5e6-4370-ac2f-2a80c0b913c1) blocked the live Microsoft path. Repair [Accept Microsoft mail when the claim is absent](db4a7a65-7ef6-4879-b33b-c75f6ced96e3). Tester [Re-check Microsoft linking after the claim fix](08e516d9-1dbb-4440-8e4c-020614f8ec70). Reviewer [What could be wrong with the Microsoft email claim](b65abfad-2056-4ac4-a820-21e6703667d4): no blocking finding. Reviewed because the card is account linking.
Files: `apps/api/app/oauth_service.py`, `apps/api/tests/test_oauth.py`.
Commands and results: VERIFIED. pytest `tests/test_oauth.py` — 15 passed.
Gates passed: T6-02, gate 6-1 for the mocked paths.
Negative tests: an unverified provider email does not link. An explicit email_verified false refuses create and link. Google still requires email_verified true.
Not done: a live sign-in with Google and with Microsoft is still for you. No commit. L4 stays off.
Risks introduced: a missing email_verified claim is accepted only for Microsoft.

CLAIM T6-03 2026-10-04T14:52:00Z files: typed audit rows for login, logout, grant, revoke, TOTP, and role change on the existing audit chain. Do not add a second audit table. Do not log passwords or tokens. Do not edit apps/api/app/changeset or agent_runtime. Do not enable L4. Do not commit.

## 2026-10-04 — T6-03
Track: T6 T6-03.
Intent: Login, logout, grant, revoke, authenticator, and role change each write one typed row on the existing audit chain. A failed login does not keep the password.
Model / band: cursor-grok-4.6-high-fast. Pressure 11. Worker [Write auth events into the one audit chain](0bfa967b-5115-48fa-8375-722286fe83fd). Tester [Re-run the auth audit-chain checks](9091efc2-7af3-472c-8e01-2c921b8a1390). Reviewer [What could be wrong with the auth audit rows](73e30214-4b57-4f55-be0d-015d36757b3c): no blocking finding. Reviewed because the card writes the audit chain.
Files: `apps/api/app/auth_audit.py`, `apps/api/app/audit_chain.py`, `apps/api/app/account_service.py`, `apps/api/app/routers/accounts.py`, `apps/api/app/oauth_service.py`, `apps/api/tests/test_t6_03_auth_audit.py`.
Commands and results: VERIFIED. pytest `tests/test_audit_chain.py`, `tests/test_t6_03_auth_audit.py`, and `tests/test_oauth.py` — 33 passed.
Gates passed: T6-03, DoD 31 for these events.
Negative tests: a failed login writes a row without the attempted password. `verify_db` stays green. No second audit table.
Not done: no commit. L4 stays off.
Risks introduced: those auth routes now append a chain row on success and on failure.

CLAIM T6-04 2026-10-04T15:04:00Z files: the inbox decide path, plus apps/api/app/changeset/store.py and apps/api/app/changeset/plan_card.py only if the fingerprint check lives there. Do not edit agent_runtime. Do not enable L4. Do not commit. Do not revert the T6-01 inbox scope checks.

## 2026-10-04 — T6-04
Track: T6 T6-04.
Intent: A decision carries the plan hash and schema fingerprint. A mismatch, an expiry, a freeze, or a replay onto a changed plan does not apply.
Model / band: grok-4.7-high. Pressure 14. Worker [Bind inbox decisions to the plan fingerprint](e2028ea3-cc5c-41fb-ac7d-164b0e2c72ad). Tester [Re-run the inbox fingerprint checks](a9a66314-ff4c-4d43-82f1-bb58da7be045). Reviewer [What could be wrong with the inbox fingerprint](b8989cdf-3af8-4788-a3a8-9ca415d12064): no blocking finding.
Files: `apps/api/app/routers/inbox.py`, `apps/api/app/changeset/plan_card.py`, `apps/api/app/changeset/store.py`, `apps/api/tests/test_t6_04_inbox_binding.py`.
Commands and results: VERIFIED. pytest `tests/test_changeset_inbox.py`, `tests/test_plan_card_store.py`, `tests/test_t6_04_inbox_binding.py`, and `tests/test_t6_01_role_matrix.py` — 53 passed.
Gates passed: T6-04, RT-17, RT-19, RT-20.
Negative tests: a fingerprint mismatch returns 409 `plan_stale`. Replaying an approval on a modified plan is refused. Client Viewer decide stays 403.
Not done: no commit. L4 stays off. Freeze windows are process-local.
Risks introduced: decide now requires both fingerprints.

CLAIM T6-05 2026-10-04T15:32:00Z files: the approvals page that renders the nine plan-card sections from the API payload. Do not generate that text in the client. Do not edit agent_runtime. Do not enable L4. Do not commit. Do not revert the T6-04 fingerprint checks.

## 2026-10-04 — T6-05
Track: T6 T6-05.
Intent: The approvals page shows the nine plan-card sections the API sends. A changed assumption voids the old card.
Model / band: cursor-grok-4.6-high-fast. Pressure 10. Worker [Render the nine plan-card sections from the API](bc01c9da-3070-46e5-98ff-607d92a084d1). Tester [Re-run the nine-section plan-card checks](27d393ce-676e-48dd-a417-6ac4d3093358). Repair [Send the nine plan-card sections on the inbox list](3b7866d7-9664-48b8-8e04-4e18aeb792de). Tester [Re-check that listed cards include nine sections](f5a1bf17-e2f9-4545-9efe-db24d2d0c7d0). No reviewer. Pressure is 10.
Files: `apps/api/app/changeset/plan_card.py`, `apps/api/app/changeset/store.py`, `apps/api/app/changeset/inbox.py`, `apps/web/src/app/approvals/page.tsx`, `apps/api/tests/test_t6_05_plan_card_sections.py`.
Commands and results: VERIFIED. pytest the inbox, section, fingerprint, and golden tests — 28 passed. vitest `src/app/approvals/page.test.tsx` — 1 passed. Browser: Show plans on connection `d41fa8a5-bcc5-4f30-a46e-0a618fef9894` lists “Add a note” with the nine section headings.
Gates passed: T6-05, GATE-P3-10 for the section snapshot.
Negative tests: changing an assumption produces a new hash and voids the old card. A fingerprint mismatch still returns 409.
Not done: no commit. L4 stays off.
Risks introduced: listing a card rebuilds the nine section strings from the stored fields.

CLAIM T6-06 2026-10-04T15:50:00Z files: the R3 approval check. Two approvers must be distinct people. A protected target also needs the domain owner, a passed simulation, a backup, and an allowed window. Do not edit agent_runtime. Do not enable L4. Do not commit. Do not revert the T6-04 fingerprint checks.

RETARGET T6-06 2026-10-04T16:10:00Z. Tope: production R3 is one approval and the approver may be the requester. The two-person gate, domain owner, simulation, backup, and window move to heavy R4. Hard stop stays on raw SQL, rpc.write, payment secrets, posted entries, lock dates, and a group-less access rule. L4 still never applies R3 or R4.

## 2026-10-04 — T6-06
Track: T6 T6-06.
Intent: Everyday R3 is one approval, and the requester may be that approver. Heavy R4 on production needs two real users. Hard-stop R4 stays denied.
Model / band: grok-4.7-high. Pressure 14. Worker [Apply the one-approval R3 rule](7eec9226-e587-491b-b92c-f5bbc0dd4bda). Tester [Re-check the one-approval R3 rule](57f25e90-954e-47ca-8a46-703b5e8b4db0). Reviewer [What could be wrong with the new approval gates](7b16f01c-7ce7-4c55-991e-5288c31f68eb) blocked a missing user id. Repair [Bind a heavy approval to the real user](e211dbf4-020d-481c-9f07-8504c8a141f7). Tester [Re-check that a heavy approval needs two real users](d94e5e83-f3ce-4843-a812-888b7fc5447c). Reviewer [What could be wrong with binding a heavy approval to a user](698ebf83-7f30-418a-9cfd-ee17bfe2e7a1): no blocking finding.
Files: `apps/api/app/changeset/policy.py`, `apps/api/app/changeset/inbox.py`, `apps/api/app/changeset/store.py`, `apps/api/app/routers/inbox.py`, and the policy and inbox tests.
Commands and results: VERIFIED. pytest the engine, inbox, rollback, T6-04 binding, policy matrix, and RT-18 — 74 passed.
Gates passed: T6-06. L4 still cannot apply R3 or R4.
Negative tests: two decide calls with different approver ids and no user id leave heavy R4 pending. Two identities count once. A fingerprint mismatch returns 409. Hard-stop R4 stays denied.
Not done: no commit. L4 stays off.
Risks introduced: the requester can approve their own everyday R3 card.

CLAIM T6-07 2026-10-04T17:06:00Z files: the inbox list and decide path for a Client Approver. Another connection's plan returns 404. Do not edit agent_runtime. Do not enable L4. Do not commit. Do not revert the T6-06 approval rule.

## 2026-10-04 — T6-07
Track: T6 T6-07.
Intent: A Client Approver sees only their connection’s plans. Another client’s plan is 404 and the body says it was not found.
Model / band: composer-2.5-fast. Pressure 8. Worker [Hide other clients' plans from a Client Approver](996f7517-eaa7-4c09-bc58-382188557ac0). Tester [Re-run the client inbox scope checks](322c453b-830b-4317-b78e-74875c4e7a5d). Reviewer [What could be wrong with hiding other clients' plans](b78a6b13-b7e3-4eac-aac3-2f1f63d29c9b): no blocking finding. Reviewed because the card is access control.
Files: `apps/api/tests/test_t6_07_client_inbox_scope.py`, `apps/api/tests/test_client_approver_isolation.py`. The inbox routes already enforced the scope.
Commands and results: VERIFIED. pytest the four named tests — 4 passed.
Gates passed: T6-07, gate 6-2 on inbox list, submit, and decide.
Negative tests: a Client Viewer decide is 403. A Client Approver cannot submit. A cross-connection decide is 404, not 403.
Not done: no commit. L4 stays off.
Risks introduced: none beyond the tests locking the existing 404 behavior.

CLAIM T6-10 2026-10-04T17:13:00Z files: a grant and revoke screen on the existing access surface, calling POST and DELETE /api/accounts/connection-grants. Do not add a second grant API. Do not edit agent_runtime. Do not enable L4. Do not commit. Meet the UI bar in AGENTS.md.

## 2026-10-04 — T6-10
Track: T6 T6-10.
Intent: An admin grants and revokes client access on the Access page. The list stays inside that connection.
Model / band: composer-2.5-fast. Pressure 7. Worker [Add grant and revoke on the access screen](e7dd27c1-3118-45e6-80f0-50ef8042a48d). Tester fail [Re-run the grant and revoke checks](d4f698ce-eb9d-4eb7-87d7-66dc016c7f20). Repair [Cover a failed revoke and a private grant list](df79c3d0-e41c-4138-84c6-79f796b046e2). Tester [Re-check the failed revoke and the grant list](b702cfb8-27cd-4a1e-8676-3edb1ea8b4f3). Reviewer [What could be wrong with the grant screen](ab123f12-b57e-4e46-90f1-30c49cf0c7f5): no blocking finding. Reviewed because the card grants access.
Files: `apps/web/src/components/access/ConnectionTeamGrantsPanel.tsx`, `apps/web/src/app/connections/[id]/access/page.tsx`, `apps/api/app/routers/accounts.py` (read-only list), `apps/api/tests/test_connection_grants_list.py`.
Commands and results: VERIFIED. vitest the grants panel and nav — 11 passed. pytest the audit row and the grant list — 4 passed. Browser: Client access grants on the Granted client Access page shows email, Client approver or Client viewer, and Grant access disabled until an email is entered.
Gates passed: T6-10.
Negative tests: a failed revoke shows an error. A non-admin is refused. Another workspace’s connection is not found. A list for connection A does not include connection B’s grant. Revoke does not use window.confirm.
Not done: no commit. L4 stays off. A live grant against a real account was not submitted in the browser.
Risks introduced: workspace admins can list grants for a connection in their workspace.

CLAIM DEV-CS 2026-10-04T17:24:00Z files: Code Studio server-action bind and the Option A zip path, plus the Code Studio screen. Do not auto-promote. Do not edit agent_runtime. Do not enable L4. Do not commit. Meet the UI bar in AGENTS.md.

## 2026-10-04 — DEV-CS
Track: Developer modes DEV-CS.
Intent: A customer with the developer role can bind a live server action only after the probe, the confirm phrase, and a snapshot, or download an Option A zip that this screen does not install.
Model / band: grok-4.7-high. Pressure 15. Worker [Keep the Code Studio toast to one sentence](16b8e2e7-7971-4d38-9467-ee327d451a40). Testers [Re-check the Code Studio toast sentence](0140a4a0-5306-42ef-9ddf-c58e254ea8b2) and [Re-check Code Studio toast test](78e2d3bf-ac58-4201-ae5f-6f3322357b18). Reviewers [What could be wrong with the Code Studio gates](2a1f3f5a-fd34-4b2f-852c-5bae89c9da0b) and [Review Code Studio toast slice](f4970aea-2e20-4187-ab01-24e43a45cefa): no blocking finding.
Files: `apps/api/app/code_studio_service.py`, `apps/api/app/routers/code_studio.py`, `apps/web/src/app/connections/[id]/code-studio/page.tsx`, `apps/web/src/app/connections/[id]/code-studio/page.test.tsx`, `apps/web/src/app/connections/[id]/code-studio/present-error.ts`, `apps/web/src/components/code-studio/PythonLineEditor.tsx`.
Commands and results: VERIFIED. pytest `tests/test_code_studio_gating.py`, `tests/test_code_studio_live.py`, `tests/test_code_studio_probe.py` — 25 passed. vitest `src/app/connections/[id]/code-studio/page.test.tsx` — 5 passed, twice. Browser on connection `d41fa8a5-bcc5-4f30-a46e-0a618fef9894`: both limit cards are on the page; the notice and the toast say “The connection database is not reachable.”; Show details is closed until opened.
Gates passed: DEV-CS.
Negative tests: an import, sudo, unlink, a missing confirm phrase, an observer connection, a failed probe, and a failed test each refuse the bind. Option A returns a zip and does not install it. The toast does not contain the traceback.
Not done: no commit. L4 stays off. Promote stays a person. The Granted client database does not exist, so a live bind was not executed in the browser.
Risks introduced: after the probe, the confirm phrase, and a snapshot, a developer can write a live `state=code` server action.

CLAIM DEV-SR 2026-10-04T18:05:00Z files: `apps/api/app/script_runner/`, `apps/api/app/routers/script_runner.py`, and `apps/web/src/app/connections/[id]/script-runner/`. Do not edit Code Studio, `agent_runtime`, or `changeset`. Do not auto-promote. Do not enable L4. Do not commit. Meet the UI bar in AGENTS.md.

STOP DEV-SR 2026-10-04T19:10:00Z. Two repairs used. Do not start a third. [Review the globals escape repair](b076ebf2-6828-4a4a-b1c6-0738d37f1b32) blocked: `_guarded_import` and `_blocked_open` still point at `child_main`, so a script can walk `execute_kw.__func__.__globals__["__builtins__"]["__import__"].__globals__["os"]`. Pytest 15 passed does not cover that walk. Logged in `ERRORS.md`. DEV-PO stays unstarted.

CLAIM T4-SKT 2026-10-04T19:40:00Z files: a trigger runner outside `apps/api/app/changeset` and `agent_runtime`. Each firing creates a new plan card through existing functions. Do not edit those two trees. Do not enable L4. Do not commit. Do not treat an existing trigger as approval.

## 2026-10-04 — T4-SKT
Track: T4 T4-SKT.
Intent: A Community trigger firing opens its own plan card. The trigger existing is not approval.
Model / band: grok-4.7-high. Pressure 16. Worker [Gate every trigger firing](bffe7b03-ac9b-488a-b4ff-6d2d5e53c0dd). Tester [Re-run the trigger gate checks](fefc5223-7ae7-4fea-b855-8fd6b25b54b3). Reviewer [Review the trigger approval gate](d8cd53d0-ceaa-4477-830c-bbad58d59073): no blocking finding.
Files: `apps/api/app/triggers/__init__.py`, `apps/api/app/triggers/runner.py`, `apps/api/tests/test_t4_skt_triggers.py`.
Commands and results: VERIFIED. pytest `tests/test_mcp_guard.py` and `tests/test_t4_skt_triggers.py` — 11 passed in 28.36s.
Gates passed: T4-SKT, compiler DoD 15–18.
Negative tests: two firings create two plan cards and need two approvals. The runner does not call `executor.apply` without that firing’s approval id. Protected models raise before a card exists.
Not done: no commit. L4 stays off. `apps/api/app/changeset` was not edited.
Risks introduced: a firing now writes a pending plan card and a `note` audit row.

CLAIM T4-GROUND 2026-10-04T20:06:00Z files: dynamic tool targets through the existing schema client, the existing RAG index, and generated views that keep a named Odoo widget. Do not add a second corpus. Do not edit changeset or agent_runtime. Do not enable L4. Do not commit. No live LLM in a test.

## 2026-10-04 — T4-GROUND
Track: T4 T4-GROUND.
Intent: Tool targets go through the existing schema client, retrieval uses the existing RAG index, and a named Odoo widget stays on the generated view.
Model / band: cursor-grok-4.6-high-fast. Pressure 8. Worker [Ground tools, RAG, and widgets](b7ba2380-3289-4bfb-8b9e-3088d2a5001e). Tester [Re-run the grounding checks](98b9d9fb-128b-445d-8563-a655d1323392). No reviewer. Pressure is 8.
Files: `apps/api/app/ai_schema_client.py`, `apps/api/app/grounding/__init__.py`, `apps/api/app/grounding/tools.py`, `apps/api/app/grounding/rag.py`, `apps/api/tests/test_t4_ground.py`, `packages/module-generator/src/module_generator/__init__.py`, `packages/module-generator/tests/test_named_odoo_widget.py`.
Commands and results: VERIFIED. pytest `tests/test_t4_ground.py` and `tests/test_ai_schema_client.py` — 18 passed. pytest `packages/module-generator/tests/test_named_odoo_widget.py` — 3 passed.
Gates passed: T4-GROUND, compiler DoD 11, 13, 14.
Negative tests: an unknown model never becomes a tool. No second RAG root. A generic stand-in does not replace a named widget.
Not done: no commit. L4 stays off. No live LLM.
Risks introduced: tool offers now depend on the schema client admitting the target.

## 2026-10-05 — 5A-06
Track: T5A 5A-06.
Intent: A production destructive or billable apply needs a snapshot taken immediately before, on this connection.
Model / band: no model. The tests were already in the tree. Orchestrator re-ran them.
Files: `apps/api/app/snapshot_gate.py`, `apps/api/tests/test_snapshot_gate.py`. No new edit.
Commands and results: VERIFIED. pytest `tests/test_snapshot_gate.py` — 28 passed.
Gates passed: 5A-06, DoD 28.
Negative tests: a 2-hour-old snapshot is refused. A snapshot from another connection is refused. BILLABLE without a snapshot is refused.
Not done: no commit. L4 stays off.
Risks introduced: none. The gate was already in the tree.

CLAIM 5A-11 2026-10-05T06:36:00Z files: a compensating-plan builder that calls the existing change-set pipeline. Do not edit `apps/api/app/changeset/rollback.py` (it is already dirty). Do not edit `agent_runtime`. Do not enable L4. Do not commit. Do not undo a module install or a posted entry by this tier.

## 2026-10-05 — 5A-11
Track: T5A 5A-11.
Intent: A compensating plan comes from audit change rows and waits for the existing approval pipeline. A module install and a posted entry are not undone.
Model / band: cursor-grok-4.6-high-fast. Pressure 13. Worker [Build compensating rollback plans](5be7f4ea-76eb-4352-8fd7-edc1153518da). Tester [Re-run compensating rollback checks](86a55da4-c12a-455f-b682-ab3d6fd1e610). Reviewer [Review compensating rollback plans](0ffc0be8-32ef-4837-8ab0-0fa4de477caa): no blocking finding. Reviewed because the plan can unlink records.
Files: `apps/api/app/rollback_tiers.py`, `apps/api/tests/test_rollback_tiers.py`.
Commands and results: VERIFIED. pytest `tests/test_rollback_tiers.py` — 6 passed.
Gates passed: 5A-11.
Negative tests: a created `res.users` row is refused before any unlink is added. A posted `account.move` and a module install are listed as not reversible by this tier. `applied` stays false.
Not done: no commit. L4 stays off. No live database restore.
Risks introduced: an approved compensating plan can later unlink ordinary records. It does not apply itself.

CLAIM 5A-12 2026-10-05T06:50:00Z files: `apps/api/tests/test_production_budgets.py` only. The pointer test looks for phrases the T6-06 retarget no longer uses. Point it at the current card text. Do not change budget numbers. Do not reintroduce two-person R3. Do not edit agent_runtime or changeset. Do not enable L4. Do not commit.

## 2026-10-05 — 5A-12
Track: T5A 5A-12.
Intent: Production budgets stay at 40 steps, 120 tool calls, and 200 records. Everyday R3 stays one approval.
Model / band: composer-2.5-fast. Pressure 7. Worker [Point budgets at the current window](3a3680e5-a679-405d-80d1-ea7f2d4a6555). Tester [Re-run the production budget tests](c58bf300-0572-4522-bf9f-0bd0da8e54cd). No reviewer. Pressure is 7.
Files: `apps/api/tests/test_production_budgets.py`.
Commands and results: VERIFIED. pytest `tests/test_production_budgets.py` — 6 passed.
Gates passed: 5A-12.
Negative tests: the 41st step and the 121st tool call raise BudgetExceeded. 201 records on production raise BlastRadiusExceeded. L4 still cannot be constructed. R4 self-approval stays false.
Not done: no commit. L4 stays off. Change windows and the kill switch are pointers to T6-04, T6-06, and the existing bridge tests.
Risks introduced: none. The test now matches the current window wording.

CLAIM 5C-02 2026-10-05T06:52:00Z files: the L2 pause path and a property test over every catalog op. Do not enable L4. Do not edit agent_runtime unless the pause lives there. Do not start 5C-01. Do not commit.

## 2026-10-05 — 5C-02
Track: T5C 5C-02.
Intent: At L2, every catalog write pauses and none of them apply.
Model / band: composer-2.5-fast. Pressure 6. Worker [Pause every L2 write](0694a82f-2cdf-406a-ae39-0cadfba1691f). Tester [Re-run the L2 pause catalog](61d4b8e3-273c-4bbc-adb8-20d099feee70). No reviewer. Pressure is 6.
Files: `apps/api/tests/test_worker_bot_l2_catalog.py`.
Commands and results: VERIFIED. pytest `tests/test_worker_bot.py` and `tests/test_worker_bot_l2_catalog.py` — 72 passed. Catalog coverage 63 of 63.
Gates passed: 5C-02.
Negative tests: `module.uninstall` and `data.delete` are denied and still do not apply. The executor journal stays empty.
Not done: no commit. L4 stays off. 5C-01 stays unstarted because it depends on T8-EXEC.
Risks introduced: none. The test locks the pause that was already in the runtime.

CLAIM 5C-03 2026-10-05T06:56:00Z files: the L3 staging path and a property test over the catalog. Do not enable L4. Do not start 5C-01. Do not edit agent_runtime unless the pause lives there. Do not commit.

## 2026-10-05 — 5C-03
Track: T5C 5C-03.
Intent: L3 may apply a reversible change on staging only. Destructive and billable work still pauses. Production does not apply.
Model / band: composer-2.5-fast. Pressure 8. Worker [Prove L3 staging pauses](a229dfbe-96f0-4270-88d9-2c6c398cd346). Tester [Re-run the L3 staging catalog](e75c585c-97ca-49a0-8813-bb24f0b6332e). Reviewer [Review the L3 staging apply rule](8e2b1f67-aad3-4c36-9571-32e6ff04afa0): no blocking finding. Reviewed because staging can apply without a person.
Files: `apps/api/app/worker_bot/l3_policy.py`, `apps/api/app/worker_bot/runtime.py`, `apps/api/tests/test_worker_bot_l3_catalog.py`.
Commands and results: VERIFIED. pytest `tests/test_worker_bot.py`, `tests/test_worker_bot_l2_catalog.py`, and `tests/test_worker_bot_l3_catalog.py` — 201 passed.
Gates passed: 5C-03.
Negative tests: production L3 never calls apply. Destructive and billable catalog ops do not auto-apply on staging. L4 is not a valid level.
Not done: no commit. L4 stays off. 5C-01 and 5C-04 stay blocked on T8-EXEC.
Risks introduced: 22 reversible ops can apply on staging at L3 without a separate approval.

CLAIM 5C-05 2026-10-05T07:06:00Z files: the bot apply path when the fingerprint changed between plan and apply. Do not enable L4. Do not start 5C-01. Do not edit agent_runtime. Do not commit.

## 2026-10-05 — 5C-05
Track: T5C 5C-05.
Intent: A schema change between plan and apply aborts the bot. The apply does not run.
Model / band: composer-2.5-fast. Pressure 9. Worker [Abort the bot when the plan is stale](7d3aa920-a93b-4ce8-b7e1-5f670f921594). Tester [Re-run the stale-plan abort](61ab249d-39ae-429d-b2dd-e2366285bafb). No reviewer. Pressure is 9.
Files: `apps/api/app/worker_bot/runtime.py`, `apps/api/tests/test_worker_bot_drift.py`.
Commands and results: VERIFIED. pytest `tests/test_worker_bot.py`, `tests/test_worker_bot_l2_catalog.py`, `tests/test_worker_bot_l3_catalog.py`, and `tests/test_worker_bot_drift.py` — 202 passed.
Gates passed: 5C-05.
Negative tests: the drifted schema returns STALE, applied is false, and the journal stays empty. L2 still pauses all 63 ops. Production L3 still never applies.
Not done: no commit. L4 stays off.
Risks introduced: a matching fingerprint still proceeds to the existing apply path.

CLAIM 5C-06 2026-10-05T07:14:00Z files: a test that an instruction buried in a product description causes no destructive action at L2 and at L3. Do not enable L4. Do not edit agent_runtime. Do not commit.

## 2026-10-05 — 5C-06
Track: T5C 5C-06.
Intent: A product note that tells the bot to unlink records or grant admin does not cause that action at L2 or L3.
Model / band: composer-2.5-fast. Pressure 8. Worker [Block injected instructions at L3](c0070888-45c8-447b-87a3-4114cbc71070). Tester [Re-run the injection tests](57dfee49-6b63-47ec-ad7f-65346e6fa54f). Reviewer [Review the buried-instruction tests](49ba6a75-0e9d-4200-9329-1107b21ee273): no blocking finding. Reviewed because the note tries to cause a destructive action.
Files: `apps/api/tests/test_worker_bot_adversarial_embedded_5c06.py`.
Commands and results: VERIFIED. pytest the new file, the L2 record-text test, the RT-01 admin test, and the injected-instruction test — 5 passed.
Gates passed: 5C-06.
Negative tests: L2 journal is empty. L3 journal is only `mail_template.create`. A changeset that already includes `data.unlink` stays paused.
Not done: no commit. L4 stays off.
Risks introduced: none. The tests lock the existing refusal.

## 2026-10-05 — R3 self-approval test
Track: T6-06 follow-up. Not a new card.
Intent: The agent-runtime test matches the current rule. The same person may approve an everyday R3 plan. Heavy R4 stays refused.
Model / band: composer-2.5-fast. Worker [Align the R3 self-approval test](1052aab9-cbd6-424a-9c00-63828e576269). Tester [Re-check everyday R3 self-approval](31e59f11-b5cb-43b0-a529-4d3f0b261790).
Files: `apps/api/tests/test_agent_runtime.py`. The test is now `test_r3_self_approval_is_allowed`.
Commands and results: VERIFIED. pytest that test — 1 passed. `test_r4_is_refused_even_with_a_matching_hash` was not changed.
Not done: no commit. L4 stays off.
Risks introduced: none. The assertion now matches the policy that was already in force.

CLAIM 5C-07 2026-10-05T07:26:00Z files: a test that an L4 allow-list of every op still cannot unlink res.users, touch res.users.apikeys, or write a protected parameter. Do not enable L4 in any default. Do not edit agent_runtime. Do not commit.

## 2026-10-05 — 5C-07 and L4-11
Track: T5C 5C-07. Same tests close GATE-L4-11.
Intent: Even a full allow-list cannot unlink a user, touch API keys, or write a protected parameter. L4 stays off as a runtime level.
Model / band: cursor-grok-4.6-high-fast. Pressure 12. Worker [Keep never-allowed closed at L4](fcbd251a-67c6-427b-8252-40df317193e3). Tester [Re-run the L4 never-allowed checks](eddba123-b6da-4730-8aa8-cfaf7e748434). Reviewer [Review the L4 never-allowed gate](4518169f-bf53-4b70-8929-bf71b04ca2e7): no blocking finding. Reviewed because never-allowed is in the frontier family.
Files: `apps/api/app/worker_bot/l4_policy.py`, `apps/api/tests/test_l4_never_allowed.py`.
Commands and results: VERIFIED. pytest `tests/test_l4_policy.py`, `tests/test_l4_never_allowed.py`, and `test_invalid_level_l4_raises` — 9 passed.
Gates passed: 5C-07, GATE-L4-11.
Negative tests: unlink `res.users`, any method on `res.users.apikeys`, and `database.secret` are refused before the allow-list can return true. `WorkerBot("L4")` still raises.
Not done: no commit. L4 stays off. GATE-L4-08 evidence does not exist.
Risks introduced: none. The check runs before the only allow return.

CLAIM 5C-09 2026-10-05T07:34:00Z files: a repeat test that 50 billable or destructive requests at L3 all pause. Do not enable L4. Do not edit agent_runtime. Do not commit.

## 2026-10-05 — 5C-09
Track: T5C 5C-09.
Intent: Fifty billable or destructive requests at L3 all pause. None apply.
Model / band: cursor-grok-4.6-high-fast. Pressure 10. Worker [Pause fifty risky L3 repeats](5e9e13b4-40bb-4e9e-b760-0550265c1b78). Tester [Re-run the fifty L3 pauses](373320df-3718-4b66-9ca3-9246f43c16d5). No reviewer. Pressure is 10.
Files: `apps/api/tests/test_worker_bot_l3_repeat_pause_5c09.py`.
Commands and results: VERIFIED. pytest that file and the existing destructive/billable L3 catalog test — 2 passed.
Gates passed: 5C-09.
Negative tests: the loop is 50. Each response is paused and not applied. R4 denials are excluded from the count.
Not done: no commit. L4 stays off.
Risks introduced: none. The test locks the existing pause.

CLAIM L4-12 2026-10-05T07:39:00Z files: a check that a bot cannot widen its own allow-list. Do not enable L4 in any default. Do not edit agent_runtime. Do not stub GATE-L4-08. Do not commit.

## 2026-10-05 — L4-12
Track: T5C L4-12. GATE-L4-12.
Intent: Only a human admin can change the allow-list. A bot call is refused and audited. Secrets and long opaque tokens are not written into that note. L4 stays off.
Model / band: grok-4.7-high. Pressure 16. Worker [Stop a bot editing its allow-list](d6c37ee0-a357-473e-b277-fe29853e9120). Repairs [Keep secrets out of the allow-list note](67c7f9a9-0270-418d-af11-f8fe0196d6d8) and [Stop opaque tokens in the audit note](bd80c23e-51b6-4518-863f-9b20a95c308b). Testers [Re-run the allow-list grant checks](31528f9b-785f-4342-820e-81e5f7be4156), [Re-check the allow-list secret note](7d6f6fbe-23be-413d-bee4-6c5a38c2474e), and [Re-check the opaque tenant note](09e4f946-87ac-4f57-a2e6-f4642a996b23). Reviewers [Review the allow-list grant check](b7c6ee91-e8df-499a-88ff-d43dbde1e989) and [Review the secret-shaped tenant note](b805feec-5fef-4647-8abf-19ceb9adea94) blocked secret values in the note. Final reviewer [Review the opaque tenant note](7d978438-05e9-465a-939d-a176f7f6b513): no blocking finding.
Files: `apps/api/app/worker_bot/l4_policy.py`, `apps/api/tests/test_l4_allow_list_grant.py`.
Commands and results: VERIFIED. pytest `tests/test_l4_allow_list_grant.py`, `tests/test_l4_never_allowed.py`, and `test_invalid_level_l4_raises` — 23 passed.
Gates passed: L4-12, GATE-L4-12.
Negative tests: a bot tool call is refused. A template is not auto-applied. `sk-test-l412-do-not-log` and `0123456789abcdef0123456789abcdef` are absent from the note. A short slug is still stored. `WorkerBot("L4")` still raises.
Not done: no commit. L4 stays off. The check is not called from the runtime, because L4 is not a level yet. GATE-L4-08 evidence does not exist.
Risks introduced: a human admin can record an allow-list op in this policy object. Nothing applies it.

CLAIM L4-01 2026-10-05T08:26:00Z files: the allow-list content check. An op outside the list is refused. An R2 DDL op is refused. An outbound email action is refused. Do not enable L4. Do not edit agent_runtime. Do not stub GATE-L4-08. Do not commit.

## 2026-10-05 — L4-01
Track: T5C L4-01. GATE-L4-01.
Intent: An op is refused when it is off the allow-list, when it is an R2 schema change, or when it sends email. L4 stays off.
Model / band: grok-4.7-high. Pressure 16. Worker [Refuse ops outside the allow-list](9709879d-e882-41ab-8afb-ce5e8ef9fbcc). Repair [Refuse the real email action shape](d1734666-4a98-4402-869c-40fa52540d94). Testers [Re-run the allow-list content checks](98cada07-d220-429a-99ab-8c778a921f05) and [Re-check the real email refusals](9421a8cb-8e97-4b5f-8ca4-975f83ec3405). Reviewer [Review the allow-list content gate](fa874941-6cdb-4d15-979a-7f351b7d185f) blocked the first email walk. Final reviewer [Review the real email refusals](b7c79dc7-e3c4-44d2-924a-c88e1bd8a011): no blocking finding.
Files: `apps/api/app/worker_bot/l4_policy.py`, `apps/api/tests/test_l4_gates.py`.
Commands and results: VERIFIED. pytest the L4 policy, never-allowed, grant, gates, and invalid-level tests — 40 passed.
Gates passed: L4-01, GATE-L4-01.
Negative tests: an off-list op is refused. An R2 DDL op is refused. `safe_actions` `mail_post` and `action_server_ids` `mail_post` are refused. A non-email field write under `safe_actions` is not treated as outbound. `WorkerBot("L4")` still raises.
Not done: no commit. L4 stays off. GATE-L4-08 evidence does not exist.
Risks introduced: none. The check still does not run inside `WorkerBot`, because L4 is not a level.

CLAIM L4-02 2026-10-05T08:54:00Z files: one refusal test each for R3, R4, protected elevate, module install or upgrade, and promote. Do not enable L4. Do not edit agent_runtime. Do not stub GATE-L4-08. Do not commit.

## 2026-10-05 — L4-02
Track: T5C L4-02. GATE-L4-02.
Intent: An allow-list cannot unlock everyday approvals, heavy work, protected elevation, module changes, or promote. L4 stays off.
Model / band: grok-4.7-high. Pressure 16. Worker [Refuse R3 R4 modules and promote](d3412ef5-07d7-4985-a02a-b83ce0fd061e). Tester [Re-run the five L4 refusals](43b78648-58f3-4bed-bd53-d6b3fd0474e7). Reviewer [Review the five L4 refusals](a2edb55e-34f2-44df-abd1-124a63b21c6c): no blocking finding.
Files: `apps/api/app/worker_bot/l4_policy.py`, `apps/api/tests/test_l4_gate_02.py`.
Commands and results: VERIFIED. pytest the L4 gate, policy, gates, never-allowed, grant, and invalid-level tests — 45 passed.
Gates passed: L4-02, GATE-L4-02.
Negative tests: R3, R4, protected elevate, module install/upgrade/uninstall, and promote are each refused while allow-listed. An R1 field update on an elevate model is refused before the allow return. `WorkerBot("L4")` still raises.
Not done: no commit. L4 stays off. GATE-L4-08 evidence does not exist.
Risks introduced: none. The check still does not run inside `WorkerBot`.

CLAIM L4-03 2026-10-05T09:12:00Z files: the Mode T and verified-staging check on the L4 decision. Do not enable L4. Do not edit agent_runtime. Do not edit changeset/executor.py unless the flags cannot be seen from l4_policy. Do not stub GATE-L4-08. Do not commit.

## 2026-10-05 — L4-03
Track: T5C L4-03. GATE-L4-03.
Intent: A production decision is allowed only with Mode T and a verified staging apply of the same plan hash. Caller-supplied flags are not that record.
Model / band: grok-4.7-high. Pressure 16. Worker [Require a verified staging apply](ea713e8a-62ef-421d-9dd8-9ae9f88dacdb). Repair [Require a real verified staging record](622d88dd-68c4-486b-93d4-d3c9b100b29f). Testers [Re-run the verified staging check](d1d20602-8ae9-4673-9bb5-20948fcfb02f) and [Re-check the staging record requirement](61636839-bb5c-4162-a5d9-16e6341ace3f). Reviewer [Review the verified staging gate](18466dc8-0c5b-48f4-ac2b-8dcaf1e7eeb5) blocked the flags-only path. Final reviewer [Review the real staging record](93f1c245-9d70-422c-bd22-8ca5aa56f80c): no blocking finding.
Files: `apps/api/app/worker_bot/l4_policy.py`, `apps/api/tests/test_l4_gate_03.py`, and the L4 tests that now supply a real verified record on allow paths.
Commands and results: VERIFIED. pytest the L4 gate, policy, never-allowed, grant, and invalid-level tests — 53 passed.
Gates passed: L4-03, GATE-L4-03.
Negative tests: Mode C is refused. A failed verification is refused. A different hash is refused. Flags alone return false. `res.users` unlink stays refused with a verified record present. `WorkerBot("L4")` still raises.
Not done: no commit. L4 stays off. The executor was not edited. GATE-L4-08 evidence does not exist.
Risks introduced: none. The allow path now requires a real staging record.

CLAIM L4-04 2026-10-05T09:43:00Z files: a standing rule that becomes active only after two distinct admins, one of them the owner. Do not enable L4. Do not edit agent_runtime. Do not stub GATE-L4-08. Do not commit.

## 2026-10-05 — L4-04
Track: T5C L4-04. GATE-L4-04.
Intent: A standing rule is active only after two different admin user ids, and one of them is the owner. An active rule does not turn L4 on.
Model / band: grok-4.7-high. Pressure 16. Worker [Require two admins for a standing rule](321730b0-8d06-4a78-8b68-1af610b34428). Tester [Re-run the standing-rule checks](c7e65277-05ee-4f7b-adf4-0310c8942bda). Reviewer [Review the two-admin standing rule](920ab4c9-6b9c-4511-bb0b-fe7b005e42d2): no blocking finding.
Files: `apps/api/app/worker_bot/standing_rule.py`, `apps/api/tests/test_l4_gate_04.py`.
Commands and results: VERIFIED. pytest `tests/test_l4_gate_04.py`, `test_invalid_level_l4_raises`, `tests/test_l4_gate_03.py`, and `tests/test_l4_gate_02.py` — 27 passed.
Gates passed: L4-04, GATE-L4-04.
Negative tests: the same user id twice counts once. A missing user id does not count. Two admins who are not the owner do not activate the rule. `WorkerBot("L4")` still raises.
Not done: no commit. L4 stays off. No migration was applied. GATE-L4-08 evidence does not exist.
Risks introduced: none. The book is in memory.

CLAIM L4-05 2026-10-05T09:56:00Z files: standing-rule expiry, at most 30 days, checked at create and at apply. Do not enable L4. Do not edit agent_runtime. Do not stub GATE-L4-08. Do not commit.

PAUSE L4 sequence 2026-10-05T10:00:00Z. Tope: build missing or partial features before more audit and security cards. L4-05 was stopped before any edit. L4-06 through L4-10 stay open. L4 stays off. Do not resume this sequence until the feature cards ahead of it are built.

CLAIM T6-08 2026-10-05T10:01:00Z files: the command center at apps/web/src/app/command. Live counts for clients, pending approvals, failed jobs, and drift. Each tile has its own skeleton. A Client Approver is sent to their inbox. Do not enable L4. Do not edit agent_runtime or changeset. Do not commit.

## 2026-10-05 — T6-08
Track: T6 T6-08.
Intent: The command center shows live counts. A slow tile does not blank the page. A client approver is sent to their inbox.
Model / band: composer-2.5-fast. Pressure 8. Worker [Build the command center counts](f6dbae00-d050-4c25-acc0-894ace20854f). Tester [Re-run the command center tests](f28ce35e-d129-4e74-946f-aacd0adb8b99). No reviewer.
Files: `apps/api/app/routers/command_center.py`, `apps/api/app/main.py`, `apps/api/tests/test_command_center_tiles.py`, `apps/web/src/components/command/CommandCenterTile.tsx`, `apps/web/src/app/command/page.tsx`, `apps/web/src/app/command/page.test.tsx`, `apps/web/src/app/approvals/page.tsx`, `apps/web/src/app/approvals/page.test.tsx`.
Commands and results: VERIFIED. vitest the command page and the approvals page — 4 passed. pytest `tests/test_command_center_tiles.py` — 2 passed.
Gates passed: T6-08.
Negative tests: a client approver is redirected to `/approvals`. A client grant reading the clients tile gets 403.
Not done: no commit. L4 stays off. The API on :8001 does not reload, so the live page will not show the new counts until that process is restarted.
Risks introduced: consultants can read four fleet counts. Clients cannot.

CLAIM T6-09 2026-10-05T10:10:00Z files: one page for a single connection showing the connection, open change-sets, and the last snapshot. If there is no bot roster yet, say so. Do not invent bots. Do not enable L4. Do not edit agent_runtime or changeset. Do not commit.

## 2026-10-05 — T6-09
Track: T6 T6-09.
Intent: One page shows a connection, its open change-sets, and the last snapshot. The bot roster is not invented.
Model / band: composer-2.5-fast. Pressure 7. Worker [Build the per-client page](1231c317-7dbb-4452-ad37-ed0b5fdbfe8c). Tester [Re-run the per-client page test](45154080-a5ca-49ab-8731-60ceae888c1d). No reviewer.
Files: `apps/web/src/app/connections/[id]/client/page.tsx`, `apps/web/src/app/connections/[id]/client/page.test.tsx`, `apps/web/src/components/connection-client/ConnectionClientPanel.tsx`, `apps/web/src/components/connection-client/ClientSectionCard.tsx`, `apps/web/src/components/connection-client/useConnectionClientSections.ts`, `apps/web/src/lib/api/inbox.ts`, `apps/web/src/lib/api.ts`, `apps/web/src/lib/nav.ts`, `apps/web/src/components/overview/OverviewHomeChrome.tsx`.
Commands and results: VERIFIED. vitest `src/app/connections/[id]/client/page.test.tsx` — 2 passed.
Gates passed: T6-09.
Negative tests: a failed connection section does not hide the change-set and snapshot sections. The bot roster says it is not available yet.
Not done: no commit. L4 stays off. No live browser pass on this page.
Risks introduced: none. The page reads existing connection, inbox, and snapshot APIs.

CLAIM GND-PKT 2026-10-05T10:15:00Z files: apps/api/app/live_schema_context.py and a fixture test. Packet for sale.order lists partner_id and form siblings in arch order. A missing field or method is absent. A stale catalog yields an empty packet. No connection does not guess. Do not edit agent_runtime or changeset. Do not call a live model. Do not commit.

## 2026-10-05 — GND-PKT
Track: T1 GND-PKT.
Intent: Generation can read a packet of the connected schema. A missing field, a missing method, and a stale catalog do not become a yes.
Model / band: cursor-grok-4.6-high-fast. Pressure 10. Worker [Build the live schema packet](2def2823-a8da-4253-b58d-ff9257e6f42f). Tester [Re-run the schema packet tests](49d789cd-57f4-4661-9012-9d7ce0fb1dfa). No reviewer.
Files: `apps/api/app/live_schema_context.py`, `apps/api/tests/test_live_schema_context.py`.
Commands and results: VERIFIED. pytest `tests/test_live_schema_context.py` — 5 passed.
Gates passed: GND-PKT.
Negative tests: no connection raises. The packet does not guess Community defaults. `formatted_read_group` is absent on major 17.
Not done: no commit. Later cards still have to consume the packet. No live model call.
Risks introduced: none. The packet is built from the existing schema client.

CLAIM GND-GEN 2026-10-05T10:23:00Z files: Draft Studio generation reads the schema packet before the model reply is admitted. A field the packet does not contain is discarded. Do not call a live model. Do not edit agent_runtime or changeset. Do not commit.

## 2026-10-05 — GND-GEN
Track: T1 GND-GEN.
Intent: Draft Studio sees the connected schema packet. A field or app the packet does not contain is dropped.
Model / band: cursor-grok-4.6-high-fast. Pressure 12. Worker [Feed the schema packet into Draft Studio](44d41baa-6065-4fb3-bbb3-2754a39d06ef). Tester [Re-run the Draft Studio packet tests](c65026ee-ceae-46a5-8cc9-255251a1fe95). No reviewer.
Files: `apps/api/app/live_schema_context.py`, `apps/api/app/ai_conversation/intent_llm.py`, `apps/api/app/ai_conversation/understand.py`, `apps/api/app/ai_conversation/refine.py`, `apps/api/app/routers/ai_studio.py`, `apps/api/tests/test_gnd_gen_live_schema.py`.
Commands and results: VERIFIED. pytest `tests/test_gnd_gen_live_schema.py` and `tests/test_live_schema_context.py` — 9 passed.
Gates passed: GND-GEN.
Negative tests: `x_po_ref` is absent from the result. An intent host `project.task` outside the packet is discarded and is not a new app.
Not done: no commit. No live model. Expert, demo, and autopilot do not consume the packet yet.
Risks introduced: generation prompts now include the schema slice for that connection.

CLAIM GND-EXPERT 2026-10-05T10:45:00Z files: expert/ask.py cites the schema packet when a connection exists. A second read happens only when the first slice lacks the field. Do not call a live model. Do not edit agent_runtime or changeset. Do not commit.

## 2026-10-05 — GND-EXPERT
Track: T1 GND-EXPERT.
Intent: When a connection exists, Expert cites the schema packet. A second read happens before it says a field is missing.
Model / band: composer-2.5-fast. Pressure 9. Worker [Make Expert cite the schema packet](9b1319c3-b9c4-4ddc-b9b1-e8ed1732ac9d). Tester [Re-run the Expert packet tests](a70eeebb-ff3e-4f1d-a726-568bcc841282). No reviewer.
Files: `apps/api/app/expert/live_schema_ask.py`, `apps/api/app/expert/ask.py`, `apps/api/tests/test_gnd_expert_live_schema.py`.
Commands and results: VERIFIED. pytest `tests/test_gnd_expert_live_schema.py` and `tests/test_expert_ask.py` — 25 passed.
Gates passed: GND-EXPERT.
Negative tests: retrieval notes cannot introduce a field the packet does not contain. Decline happens only after the second read shows no field and no host to add one on.
Not done: no commit. No live model. Demo and autopilot do not consume the packet yet.
Risks introduced: Expert field answers for a connected database now come from the packet before the model reply.

CLAIM GND-AUTO 2026-10-05T10:52:00Z files: job autopilot planner, ingest classify, and workflow drop a model or method the schema packet does not contain, before sandbox apply. Do not call a live model. Do not edit agent_runtime or changeset. Do not commit.

## 2026-10-05 — GND-AUTO
Track: T1 GND-AUTO.
Intent: Job Autopilot, ingest, and workflow drop a model or method the connected schema does not contain, before apply.
Model / band: cursor-grok-4.6-high-fast. Pressure 10. Worker [Drop unknown names before autopilot apply](89cfd8b5-6e45-48ce-9934-840135af0a1f). Repair [Bind the schema packet on autopilot](360af10c-b5f4-4d20-a7ec-c52950a7462a). Testers [Re-run the autopilot packet tests](1ec2db5a-022e-4185-9542-97f227ade538) and [Re-check autopilot builds the packet](5d158b07-e46c-4548-a335-60a34577c1cc). No reviewer.
Files: `apps/api/app/job_autopilot/planner.py`, `apps/api/app/job_autopilot/executor.py`, `apps/api/app/routers/job_autopilot.py`, `apps/api/app/ingest/classify.py`, `apps/api/app/ingest/pipeline.py`, `apps/api/app/ai_workflow.py`, `apps/api/app/live_schema_context.py`, `apps/api/app/routers/ai_studio.py`, `apps/api/tests/test_gnd_auto_live_schema.py`.
Commands and results: VERIFIED. pytest `tests/test_gnd_auto_live_schema.py` — 8 passed. `build_job_packet_for_connection` drops `project.task` without the test passing a packet in.
Gates passed: GND-AUTO.
Negative tests: `formatted_read_group` does not leave the planner on major 17. Ingest and workflow drop models outside the packet.
Not done: no commit. No live model.
Risks introduced: an autopilot run with a connection now builds a schema packet before it plans.

CLAIM GND-DEMO 2026-10-05T11:15:00Z files: live demo answers for "Can Odoo do this?" with no client database. Do not call a live model. Do not ask the user to connect a database. Do not edit agent_runtime or changeset. Do not commit.

## 2026-10-05 — GND-DEMO
Track: T1 GND-DEMO.
Intent: An open demo question gets one model verdict. The version and edition table checks it. A failed check becomes not sure. Bullets are cut from that verdict.
Model / band: cursor-grok-4.6-high-fast. Pressure 10. Worker [Answer Can Odoo do this](5a0650c1-a8fb-4d9c-ae6a-bd9b46fe4b05) first shipped a table-only answer and removed the model. Repair [Restore one model call on the demo answer](8e1cd714-5b04-4f33-9dbd-2f1f58511737). Tester [Confirm the demo uses one model call](6693f631-a512-4f4e-8ec9-812f4ec7d189) read the code, not only the count.
Files: `apps/api/app/live_demo_copilot/stage2_answer.py`, `apps/api/tests/test_gnd_demo.py`.
Commands and results: VERIFIED. pytest `tests/test_gnd_demo.py` — 14 passed. The tester confirmed one `generate_json`, a failed check becomes not sure, and bullets are not rewritten by a second call.
Gates passed: GND-DEMO.
Negative tests: Helpdesk claimed as Community stock becomes not sure. A bank API claimed as stock becomes not sure. A not-sure model answer on quotations is not upgraded to Sales stock. Major 16 is not a demo target.
Not done: no commit. No live model. The pipeline still defaults the picker to major 20 and Community when the caller does not pass a target.
Risks introduced: a demo answer now depends on one scripted or live model call, then the table.

CLAIM T8-OP-SCHEMA 2026-10-05T11:43:00Z files: the schema operations model.create, model.scaffold, field.create, field.update, field.deprecate, field.delete, selection.update, and constraint.sql, using the existing executor. Do not enable L4. Do not edit agent_runtime. Do not commit.

## 2026-10-05 — T8-OP-SCHEMA
Track: T8 T8-OP-SCHEMA.
Intent: Creating and changing models and fields goes through the existing executor. Cascade stays off. A compute is R3. A type change is refused. Deleting a non-empty financial, HR, or stock field is R4.
Model / band: cursor-grok-4.6-high-fast. Pressure 12. Worker [Build the schema change operations](b97b941a-be4d-4261-b1fd-1d6f15daee01). Tester [Re-run the schema operation tests](93530952-85dc-48a1-b283-96a63c2c7ef9). No reviewer.
Files: `apps/api/app/changeset/schema_ops.py`, `apps/api/app/changeset/handlers.py`, `apps/api/app/changeset/dispatch.py`, `apps/api/app/changeset/meta_snapshot.py`, `apps/api/tests/test_schema_ops.py`, `apps/api/tests/engine/test_suite_01_op_conformance.py`.
Commands and results: VERIFIED. pytest `tests/test_schema_ops.py` and `tests/engine/test_suite_01_op_conformance.py` — 21 passed.
Gates passed: T8-OP-SCHEMA.
Negative tests: cascade is forbidden. A type change is unsupported. `constraint.sql` is refused off `x_` models. Scaffolding into a protected model is refused.
Not done: no commit. No live Odoo. L4 stays off.
Risks introduced: seven schema ops now apply through the executor, not only `field.create`.

CLAIM T8-OP-UI 2026-10-05T12:00:00Z files: view, action, menu, filter, and report operations on the existing executor. One anchor per inherit. Replacing the root or a large subtree is refused. Reports are R2. Do not enable L4. Do not edit agent_runtime. Do not commit.

CLAIM T8-OP-LOGIC 2026-10-05T12:15:00Z files: server action, automation, cron, sequence, mail template, activity type, stage, and config record ops on the existing executor. Code/email/SMS/webhook, outbound or mass automation, and cron are R3. Accounting/journal/legal sequences are R4. safe_eval AST rejects RT-25. Do not enable L4. Do not edit agent_runtime. Do not commit.

CLAIM T8-OP-SET 2026-10-05T12:20:00Z files: setting, config param, company, and module install/upgrade/uninstall ops on the existing executor. module_* is R3 and may be BILLABLE; protected keys forbidden; lock dates, fiscal year, currency, and chart are R4; uninstall is R4 and prohibited in v1. Do not enable L4. Do not edit agent_runtime. Do not commit.

CLAIM T6-11 2026-10-05T12:25:00Z owner: Grok bot (external). files: a new read-only five-track dashboard API router plus its include in main.py, and a new web route with its test. Not changeset/, agent_runtime/, worker_bot/, or l4_policy. Do not commit.

CLAIM T8-CLI 2026-10-05T12:50:00Z files: `changeset/cli.py`, `tests/test_changeset_cli.py`. plan|validate|simulate|apply|rollback on a two-op change-set against a fake port, no LLM import. Do not commit.

## 2026-10-05 — Heavy R4 gap: T8-OP-LOGIC and T8-OP-SET back to SEEDED, T8-OP-DATA held OPEN
`02_APPROVAL_FLOW.md` line 47–50: R4 heavy (data delete, accounting/legal sequences, fiscal year, currency, chart of accounts, admin grants, module uninstall) applies with 2 distinct people + domain owner when elevated + simulation + backup + allowed window. R4 hard stop (raw SQL, rpc.write, payment secrets, posted entries, lock dates, group-less ACL) is denied. `policy.py` already classifies both. The op families refuse every heavy op outright after the gate passes, which is narrower than the cards. Correction: the T8-OP-LOGIC entry's note "refused outright ... matches R4, which is denied everywhere" is wrong. Exception kept: `module.uninstall` stays prohibited (T8-OP-SET card says "prohibited in v1").
T8-OP-DATA (Grok bot, 2026-10-05T12:58Z): all other boxes pass; re-run `pytest tests/test_data_ops.py ... tests/test_red_team_engine.py` → 435 passed, 1 skipped, 32 errors (all Postgres 5433 down in conftest). Open: `data.delete` never applies.
Fix card T8-HEAVY-R4 (Grok bot): heavy ops apply only when the heavy gate passed; hard stops stay denied; without the gate they stay refused.

CLAIM T8-HEAVY-R4 2026-10-05T13:05:00Z owner: Grok bot (external). files: heavy-R4 branches in `changeset/logic_ops.py`, `setting_ops.py`, `data_ops.py`, `handlers.py`, `dispatch.py`, and their tests. Not `module.install`, not `cli.py`, not `meta_snapshot.py`. Do not commit.

## 2026-10-05 — 5C-04 returned to Grok bot (not DONE)
Grok changed `recovery.py` and `executor.py` (queue/wait lock, 5 s heartbeat, `reclaim_stale`, release in `finally`), added `test_multi_client_lock.py`, and rewrote `database_busy` assertions in `test_suite_13_lock.py` and `test_executor_wal.py`. The card requires a second apply to queue, so those rewrites are required, and the new ones are stronger (no interleave). `odoo_addons/` untouched.
Orchestrator re-run: 180 passed, 1 skipped, **1 failed**: `test_executor_wal.py::test_one_apply_per_odoo_database` fails 3/3. `timed_out["status"]` is VERIFIED, not NEEDS_HUMAN. Likely cause: run-1 is acquired at the fixed `_NOW` (2026-10-03) with `stale_after=30s`, so the waiting acquire reclaims it as stale and the apply proceeds.
Open notes for DONE:
- `recover_stale_applying` (which calls `reclaim_stale`) has no scheduler or caller. Stale locks are reclaimed only when another apply waits on them.
- The lock is in-process only. Separate API processes are not covered until the `apply_database_lock` table (alembic `s9t0u1v2w3x4`, not applied) is used.
- `depends_on` T8-EXEC is still OPEN.

## 2026-10-05 — GND-G-MAP and GND-G-TEXT DONE
`live_schema_context.py` gains `technical_names` and `unknown_technical_names` (same regex as `drop_unknown_technical_names`; no second cache).
- `ingest/map_columns._llm_map_columns`: the caller's `schema_packet` (or one built via `LiveSchemaClient`, fields only) goes in the prompt, and only fields on the packet model are kept. A dropped column stays unmapped with the warning "LLM proposed 'y', which is not a field on M". With no packet or no fields, the LLM is never called.
- `expert/narrative.generate_finding_narratives`: the packet (argument, or the bound packet) goes in the prompt. A paragraph naming something outside the packet and outside its own finding text falls back to `_fallback_paragraph`.
- `routers/ai_studio.refine_session_route` via `_grounded_refine_reply`: the packet goes in the prompt. A reply naming something outside the packet, the changed fields, or `patch_summary` is replaced by `patch_summary`.
The gate test moves the 3 entries to `live_packet`. New tests: `test_gnd_g_map_live_schema.py` (6), `test_gnd_g_text_live_schema.py` (6).
Commands, re-run by orchestrator: gate + new + `test_expert_upgrade` + `test_live_schema_context` + GND-GEN/AUTO/EXPERT tests → 51 passed in 4 of 5 runs. One run had 1 failure that didn't recur, probably shared DB state while the Grok bot was running tests.
Three wider failures are outside the files this pass changed:
- `test_build_draft_job_kwargs_includes_run_body_fields`: `build_draft_job_kwargs` lacks `ai_session_id`, from committed `ai_draft_jobs.py` (`807a62e`).
- `test_sync_job_loads_background_job_into_review`: a leftover `job-sync-test-1` row in the app DB.
- `test_expert_repairs_live_apply_activity_mixin`: the `apply_fixes` branch has no narratives.
Decisions accepted:
- A narrative may repeat names from its own finding text, so it can explain the bad name the finding is about.
- A refine reply may use only the packet, the changed fields, and `patch_summary`.
Follow-up: `review_draft` doesn't pass the connection packet into narratives yet.

## 2026-10-06 — GND-G-PIPE DONE
The worker hit the monthly usage limit before it reported. The orchestrator verified what it left on disk.
- `live_schema_context.py` gains the shared helpers `stock_field_allowed`, `_drop_unknown_stock_field_refs`, `_ground_value`, and `draft_grounding`.
- The 8 sites put `schema_packet` in the prompt and filter the output: `ai_pipeline._llm_json`, `ai_depth.llm_expand_depth`, `ai_critique.llm_critique`, `ai_model_quality.llm_deepen_model_fields` / `llm_emit_missing_scaffold_models`, `ai_domain_briefing._enrich_briefing_with_llm`, `ai_ollama.draft_module_from_prompt` / `call_ollama_generate`. `call_ollama_generate` is grounded, not deleted.
- The gate test lists all 8 as `live_packet`. New `test_gnd_g_pipe_live_schema.py` has 9 tests: one per site plus a no-connection prompt rule, with 13 assertions that an invented stock field is dropped and an `x_*` field is kept.
Commands, orchestrator:
- gate + `test_gnd_g_pipe_live_schema` + `test_gnd_gen_live_schema` → 27 passed.
- Known-failing suites (`test_ai_stock_first`, `test_ai_honesty_ir_independent`, `test_ai_conversation_integrations`): 10 failed / 51 passed, the same set before and after (baseline `/tmp/gnd_pipe_before_known.txt`).
- Touched-module suites (44 files, `/tmp/gnd_pipe_suites.txt`): 55 failed / 753 passed / 1 skipped, the same 55 ids before and after (`diff` empty).
GND-GATE now waits only on GND-G-OPTA (Grok bot; `ai_option_a_packet_ground.py` and the gate entries are already on disk, unverified) and GND-AGENT. files: the 8 pipeline sites, one shared helper, tests/test_gnd_gate_llm_call_sites.py (pipeline entries only), new tests. Not changeset/, agent_runtime/, ai_option_a_*, web. Do not commit. files: ingest/map_columns.py, expert/narrative.py, routers/ai_studio.py (refine reply only), tests/test_gnd_gate_llm_call_sites.py, new tests. Not changeset/, agent_runtime/, web. Do not commit.
CLAIM GND-G-OPTA 2026-10-05T14:40:00Z owner: Grok bot (external), after 5C-04. Files: ai_option_a_author.py, ai_option_a_feedback.py, a new static reference checker, tests/test_gnd_gate_llm_call_sites.py (Option A entries only).

## 2026-10-05 — UI-F11 DONE
Already in `49bcefb`: react-virtuoso above 50 rows (`DEFAULT_VIRTUALIZE_THRESHOLD`), a plain table at 50 or fewer, a sticky header, ArrowUp/Down with scroll-into-view, `BulkResultTable` via DataTable, and the 5,000-row sort/filter timing test (0.2–1.5 ms against 100 ms).
This pass, in `DataTable.tsx`:
- `aria-rowcount` counts the header row and is left off while loading or empty.
- Every row has an `aria-rowindex`, and sortable headers have `aria-sort`.
- The scroll frame shows a `ring-accent` focus ring.
- The active row gets an accent tint and bar while the table has focus.
- `fixedItemHeight` is removed so virtuoso measures wrapped rows.
Files: `DataTable.tsx`, `DataTable.test.tsx` (+6, existing unchanged), `app/e2e/data-table/page.tsx` (new harness), `e2e/a11y-ui-f11.spec.ts` (new), `docs/vision-verify/UI-F11/` (AUDIT.md, axe-results.jsonl, 4 shots).
Commands, re-run by orchestrator: vitest `src/components/ui` → 85 passed; `a11y-ui-f11.spec.ts` → 4 passed (axe 0 on the tables and the whole page, desktop and 390). Worker: tsc 18 → 18; `a11y-primary` + `a11y-ui-f05` 44/44; 40 ArrowDowns reach row 41 of 5,000.
Follow-ups that predate this card:
- eslint `react/display-name` on `TableHead`/`TableBody` (from `49bcefb`).
- Hand-built unbounded tables outside the card's Change list: housekeeping, `CronJobsList`, `BulkResultsSection`.
- The active row uses `aria-selected`, which overlaps checkbox selection in selectable tables.

UX audit (notes in `docs/vision-verify/UI-F11/AUDIT.md`):

| Area | Result |
|---|---|
| Hierarchy, Interaction, Feedback, Accessibility, Cognitive load, Trust, Performance, Business goal | Pass |
| IA, Errors, Copy, Forms | Not observable (nothing changed) | files: components/ui/DataTable.tsx and table callers as the card names. Not API. Do not commit.

## 2026-10-05 — GND-GATE SEEDED (gate built; not DONE)
`apps/api/tests/test_gnd_gate_llm_call_sites.py` (new, 11 tests) reads every `generate_json` / `generate_text` call site under `apps/api/app` without importing it, plus the callers of the two wrappers (`generate_json_with_timeout_retry`, `llm_json_with_budget`). Sites are keyed by file, function, and call count. It fails on any site not on the allowlist and on stale entries. A `live_packet` claim must reference `schema_packet` in its own function. `version_table` and `refuses_invent` claims need a marker in their module, and every grounded entry must point at an existing test. Mutant tests cover a new method call, a new bare call, a new wrapper caller, an extra call in a listed function, a stale entry, and a false `live_packet` claim. CI already runs the full api pytest (`ci.yml:61`), so no hook was needed.
Command, re-run by orchestrator: `pytest tests/test_gnd_gate_llm_call_sites.py tests/test_live_schema_context.py` → 16 passed.
Why not DONE: the card is "No ungrounded LLM surface left" and depends on GND-AGENT (OPEN). 30 sites total:
- 9 grounded: GND-GEN `intent_llm`/`understand`/`refine`, GND-EXPERT `ask_expert`, GND-AUTO `planner`/`classify`/`ai_workflow`, GND-DEMO `stage2_answer`, and `wireframe_live`, which refuses to invent.
- 5 can't name Odoo structure.
- 3 are provider plumbing.
- **13 ungrounded**, each listed as `ungrounded` in the test, not as grounded:
  - `ai_pipeline._llm_json`, `ai_depth.llm_expand_depth`, `ai_critique.llm_critique`
  - `ai_model_quality.llm_deepen_model_fields` / `llm_emit_missing_scaffold_models`
  - `ai_domain_briefing._enrich_briefing_with_llm`
  - `ai_ollama.draft_module_from_prompt` / `call_ollama_generate` (the latter has no callers)
  - `ai_option_a_author._default_generate_blocks`, `ai_option_a_feedback._default_repair_blocks`
  - `ingest/map_columns._llm_map_columns` (field list in the prompt, output not filtered)
  - `expert/narrative.generate_finding_narratives`
  - `routers/ai_studio.refine_session_route` (display-only paraphrase)

Each needs grounding, or a recorded out-of-scope decision, before DONE. When GND-AGENT lands, extend the scanned names to cover the gateway `complete()`. files as the card names (allowlist plus its test/CI hook). Not changeset/, agent_runtime/, web. Do not commit.

## 2026-10-05 — UI-F05 DONE
The Base UI swap, Radix removal, and `Tabs.test.tsx` were already in `65fbcbd`. Base UI already provides the roles, `aria-selected`, roving tabindex, `aria-controls`/`aria-labelledby`, arrow keys, and Home/End. This pass adds to `components/ui/Tabs.tsx`: a `ring-accent` focus-visible ring on tabs and panel; a Base UI `Tabs.Indicator` 2 px accent underline that moves only by `translate` plus `scaleX` (UI-F09 constants, 200 ms; opacity only under reduced motion); and an exported `tabsIndicatorMotionStyle`. Public API unchanged, 5 callers untouched.
Files: `Tabs.tsx`, `Tabs.a11y.test.tsx` (new, 11), `e2e/a11y-ui-f05.spec.ts` (new, 5), `docs/vision-verify/UI-F05/` (AUDIT.md, axe-results.jsonl, 4 shots).
Commands, re-run by orchestrator: vitest `src/components/ui` → 78 passed; `a11y-ui-f05.spec.ts` → 5 passed. Worker: tsc 18, none new. axe: the tabs subtree on `/e2e/kit` is 0 at desktop and 390. The whole page has 5 serious color-contrast failures outside the component this card touched: 4 `CodeBlock` syntax tokens and 1 `.text-success` in the bulk table. Those belong to UI-F12, which requires axe on every route.
Follow-ups that predate this card:
- Kit page contrast failures listed above.
- `/e2e/kit` scrolls sideways at 390 px (CodeBlock, DataTable, button row).
- `ProjectDiffPanel.test.tsx` "elevates a trustworthy change review…" expects "Promote stays human"; the committed copy says "Apply/Promote stay human". Not touched.
- The T7 card header says the typecheck baseline is 13; the measured baseline is 18.

UX audit (notes in `docs/vision-verify/UI-F05/AUDIT.md`):

| Area | Result |
|---|---|
| Hierarchy, Interaction, Feedback, Accessibility, Cognitive load, Trust, Performance, Business goal | Pass |
| IA, Errors, Copy, Forms | Not observable (nothing changed) | files: Tabs primitive to Base UI and its callers as the card names. Not API, Button, Tooltip. Do not commit.

## 2026-10-05 — UI-F06 DONE
The Base UI swap and Radix removal were already in `ba38ac9`. This pass adds to `components/ui/Tooltip.tsx`: the trigger points at the open popup with `aria-describedby` (Base UI 1.8.0 doesn't set it; a describedby the child already had is kept), and `tooltipMotionStyle` animates transform/opacity with the UI-F09 constants (200 ms enter, 150 ms exit; opacity only under reduced motion). Public API unchanged, 9 callers untouched.
Files: `Tooltip.tsx`, `Tooltip.a11y.test.tsx` (new, 7), `e2e/a11y-ui-f06.spec.ts` (new, 5), `docs/vision-verify/UI-F06/` (AUDIT.md, axe-results.jsonl, 4 shots).
Commands, re-run by orchestrator: vitest `src/components/ui` → 67 passed; `a11y-ui-f06.spec.ts` → 5 passed (axe 0 violations while open, desktop and 390). Worker: tsc 18, none new. Close delay is 0 ms; the card names no close timing.
Follow-ups that predate this card:
- `shell-expert.spec.ts` "expert panel opens from harness" fails because the `FirstWriteInterstitial` modal (last changed `bbc7111`) covers Ask Expert.
- Hydration id mismatch on `/e2e/expert`, above Tooltip.
- `Sidebar.tsx` (sr-only span) and `ExpertSources.tsx` (`<sup>`) tooltip triggers can't take focus, so keyboard users never see them.

UX audit (notes in `docs/vision-verify/UI-F06/AUDIT.md`):

| Area | Result |
|---|---|
| Hierarchy, Interaction, Feedback, Accessibility, Cognitive load, Trust, Performance, Business goal | Pass |
| IA, Errors, Copy, Forms | Not observable (nothing changed) |

## 2026-10-05 — UI-F07 DONE files: Tooltip primitive to Base UI and its callers as the card names. Not app/command, not API. Do not commit.

## 2026-10-05 — UI-F07 DONE
`components/ui/Button.tsx` `asChild` now uses Base UI `useRender` (`@base-ui/react` 1.8.0, nothing installed): merged className, chained onClick, forwarded + child refs kept; disabled/loading + asChild → `aria-disabled`, `tabIndex=-1`, navigation cancelled. Not the `@base-ui/react/button` primitive (adds `role="button"` to anchors and defaults `type="button"`, which would stop untyped form submits); the card allows `render`. Radix already gone (`rg -l "@radix-ui" src` → 0). Visible change: `ModuleSpecApplyBar` asChild span now dims while working.
Files: `Button.tsx`, `Button.asChild.test.tsx` (+6; existing 4 unchanged).
Commands: vitest `src/components/ui` → 60 passed (re-run by orchestrator); tsc 18 (baseline 19, none new); web restarted with `NEXT_PUBLIC_E2E=1`, `e2e/a11y-primary.spec.ts` → 38 passed, 1 failed; shots `docs/vision-verify/UI-F07/kit-desktop.png`, `kit-390.png`. No copy change.
The one failure is Automations `color-contrast`: `text-ui-meta text-muted` (`--muted` → `--n8`, #838388 on #fff = 3.77:1 at 11 px) on a `<p>` and `<span>`, not Button; styles unchanged in the working tree, so it predates this card. Follow-up for the token/colour work: `--n8` at 11 px fails AA wherever `text-ui-meta text-muted` sits on white.
Note: the web server on :3002 now runs with `NEXT_PUBLIC_E2E=1`.

CLAIM UI-F07 2026-10-05T14:10:00Z files: `components/ui/Button.tsx` asChild / Slot and its callers as the card names. Not app/command, not API. Do not commit.

## 2026-10-05 — UI-F10 DONE
One shared `components/auth/TotpCodeInput.tsx` (input-otp, already installed): 6 digit-only slots, numeric inputmode, `autocomplete="one-time-code"`, paste fills all (spaces/dashes stripped), linked label/description/error, `aria-busy` while verifying, opacity-only caret off under reduced motion. Logic in `lib/auth/totp.ts`. Login is the only code entry (no enrol page yet). Login screen brought to the UI bar on review: padded card, full-width primary Sign in / Complete sign-in, footer split into "New here? Create an account" and "Forgot your password?", hidden during the OAuth 2FA step.
Files: `lib/auth/totp.ts`, `components/auth/TotpCodeInput.tsx` + test (9), `app/login/page.tsx` + test (6), `e2e/ui-f10-totp.spec.ts`, `docs/vision-verify/UI-F10/` (4 shots + AUDIT.md).
Commands: vitest → 15 passed; Playwright with axe (WCAG 2.2 AA, no rules disabled) → 4 passed; tsc 19 (unchanged).
Acceptance: paste a 6-digit code, password-manager fill, WCAG 3.3.8 — met. Not auto-submit (card does not ask). Follow-up card candidate: recovery-code entry (API accepts `recovery_code`, web has no field).

CLAIM UI-F10 2026-10-05T14:00:00Z files: TOTP code entry on the web (input-otp), its test. Not API files, not app/command. Do not commit.

## 2026-10-05 — UI-F03 DONE
Evidence: `e2e/a11y-ui-f03.spec.ts` (axe, same rule set as `a11y-primary`, mocked API for loading/empty/populated states, desktop and 390 px) → 26 passed after the fix below; shots and `axe-results.jsonl` in `docs/vision-verify/UI-F03/`; 12-row UX audit and copy critique in `docs/vision-verify/UI-F03/AUDIT.md` (its one Issue row, the table grid, is now fixed).
Also fixed: the real connection loading screen (`components/shell/AppShell.tsx`, bare "Loading connection…") is now a shaped skeleton (`AppShell.test.tsx`); billing empty copy no longer says "seats". Orchestrator fix: `components/ui/DataTable.tsx` moved `role="grid"`, `aria-rowcount`, `aria-activedescendant`, focus, and arrow-key handling from the scroll wrapper onto the `<table>` in both the plain and virtualized branches (axe critical: a grid wrapping a native table).
Commands: vitest `DataTable.test.tsx kit.test.tsx settings/page.test.tsx` → 26 passed; UI-F03 vitest set 17 passed; tsc 19 (unchanged); Playwright needs `PLAYWRIGHT_BROWSERS_PATH=$HOME/Library/Caches/ms-playwright` when run from the agent shell.
Follow-ups closed the same day: (1) billing now shows "We couldn't load your plan." plus Try again on a failed request, and the sign-in empty state only for 401/403 or 400 "Workspace context required" (`lib/api/client.ts` attaches `status` to thrown errors; `useEntitlements` returns `signedOut`; 2 new tests). (2) Telemetry: `ga_evidence_summary` returns one row per workspace with zeros, so empty means no workspaces. Copy is now "No workspaces to report on" / "Each workspace appears here with its bulk runs, refusals, aborts, and restores, starting at zero." (AUDIT.md row updated). Vitest admin + billing 7 passed; axe spec 26 passed. The `layout.tsx` fallback is a safety net only reachable in tests; the real loading screen is `AppShell.tsx`.

## 2026-10-05 — T8-SIM DONE (Grok bot)
`changeset/simulate.py`: `plan_hash()` on reports; a recorded success is bound to that plan hash; optional fake `staging_port`; a failed simulation returns the phase to `PLAN` and clears the record. Modes: static always, Bridge in-place dry-run for non-DDL, staging for DDL and R≥3, synthetic. The executor already calls `guard_production_apply` before apply (`executor.py:277`), so production apply without a matching recorded simulation is refused (R1 direct only where policy allows). No existing assertion touched.
Files: `changeset/simulate.py`, `tests/test_simulation_modes.py` (8).
Command (re-run by the orchestrator with the database up): `pytest tests/test_simulation_modes.py tests/engine tests/test_changeset_cli.py tests/test_data_ops.py tests/test_setting_ops.py tests/test_logic_ops.py tests/test_bridge_protocol.py tests/test_executor_bridge.py` → 362 passed, 1 skipped, 1 xfailed.

CLAIM 5C-04 2026-10-05T13:45:00Z owner: Grok bot (external). files: a per-database apply lock with heartbeat and recovery, its use in `changeset/executor.py`, `tests/test_multi_client_lock.py`. Not `odoo_addons/`. Do not commit.

## 2026-10-05 — GND-MOD DONE
Docker Desktop restarted (stale backend force-stopped); app Postgres :5433 and Odoo 19 :8069 up.
Real e2e `/tmp/gnd_mod_e2e.py` on a fresh base-only sandbox database `gndmod_e2e_1791207113`: proposal "Your request edits quotations, which come from the Sales app. Install Sales to continue?" with reason; `module.install` → `sale` installed in 9.2 s; facts after `model_present=True, module_state='installed'`; re-read packet contains `sale.order`. Output ended `E2E OK`.
`pytest tests/test_gnd_mod_stock_app.py tests/test_gnd_mod_autopilot_map.py` with the database up → 40 passed (includes the strict continuation test: same session resumes to the locked diagnosis with host `sale.order`).
All four boxes met. Autopilot: plan approval is the confirm (founder decision). Left: Autopilot bootstrap installs outside the `module.install` op.

CLAIM T8-SIM 2026-10-05T13:20:00Z owner: Grok bot (external). files: `changeset/simulate.py`, the simulation check in the executor/policy path, `tests/test_simulation_modes.py`. Not `odoo_addons/`, not existing bridge assertions. Do not commit.

## 2026-10-05 — T8-HEAVY-R4 (Grok bot): LOGIC and SET back to DONE, DATA stays SEEDED
Heavy ops now apply only with the full heavy gate (`policy.heavy_gate_refusal` reusing `policy_decision(..., heavy=True)`): journal/kind/purpose sequences, company fiscal year/currency/chart. Hard stops stay denied with the full gate: lock dates, posted entries, and accounting/legal sequences on protected accounting targets (protected registry `deny` wins over heavy, per `r4_gate`). `module.uninstall` unchanged (prohibited). Admin grants are T8-OP-SEC.
Orchestrator corrections: the bot removed `data.delete` from `odoo_addons/ingenium_bridge/protocol.py` PROHIBITED_OPS and changed two existing assertions (`test_bridge_protocol.py`, `test_executor_bridge.py`) from `prohibited_op` to `max_risk`. Reverted all three: the addon only compares caller-supplied `risk` to caller-supplied `max_risk` and cannot verify the two-person approval, so it keeps refusing deletes. The bot's new `test_heavy_data_delete_applies_with_full_heavy_gate` is now `xfail(strict=True)` with that reason.
Command: the change-set + bridge pytest set → 478 passed, 1 skipped, 1 xfailed, 53 errors (Postgres :5433 down).
Open for T8-OP-DATA: `data.delete` needs the addon (BR-14 / T8-OD-BRIDGE) to verify a heavy-gate approval it can trust, such as a server-signed approval token. Unverified live: sequence create fields, company fiscal/currency/chart writes, unlink on allow-listed models 17–20; `data.merge` is `res.partner` wizard only.

## 2026-10-05 — GND-MOD: Autopilot uses the shared stock-app map
Founder decision: approving the Autopilot plan counts as the GND-MOD confirm. Planner vocabulary now names models and resolves modules through `stock_app_for_model`; each planned stock-app install adds the shared "why" line to `decision_record`; Enterprise-only apps (Helpdesk, Planning, Field Service) are never planned and get the shared explanation. The worker's extra pass that added every shared-map match on the inferred path was removed by the orchestrator (generic words like "transfer" would add apps); regression test `test_generic_shared_map_words_do_not_widen_inferred_apps`. "pipeline" → CRM predates today (present at HEAD).
Files: `stock_app_install.py` (`match_stock_apps`, `is_community`), `job_autopilot/planner.py`, `tests/test_gnd_mod_autopilot_map.py` (6).
Tests: `pytest tests/test_gnd_mod_autopilot_map.py tests/test_gnd_auto_live_schema.py -m 'not app_db'` → 14 passed. Autopilot suites with `--noconftest` → 80 passed, 1 skipped, 5 failed (router tests needing Postgres). The 10 failures in `test_ai_stock_first` / `test_ai_honesty_ir_independent` / `test_ai_conversation_integrations` are identical at HEAD (checked via `git archive HEAD`), so they predate this work.
Left: `job_autopilot/bootstrap.py` installs via `install_module_by_name`, not the `module.install` op (not small: busy-retry, module-list refresh, l10n).

## 2026-10-05 — UI-F03 batch H (card stays OPEN)
Kit Skeleton and EmptyState now on the remaining operate routes: `connections/[id]/layout.tsx` (shell fallback), `settings/page.tsx` (API status, keys, audit log), `settings/billing/page.tsx`, `settings/trust-safety/page.tsx` (also no longer stuck on loading after an error), `admin/page.tsx` (users, workspaces, telemetry no longer say "No … loaded" while fetching), `pipelines/page.tsx`. Loading blocks are status regions with screen-reader text; reduced motion via the `base.css` rule.
Tests: 7 vitest files → 16 passed (re-run by the orchestrator); `kit.test.tsx` 16 passed; tsc 19 errors before and after, identical list (baseline is now 19, not 13); eslint 0.
Met: kit on every operate route that can be empty; no `Loading...` in `src/app`; skeletons with no spinner flash; one sentence plus one action. Not met: axe on touched routes, desktop + 390 px shots in `docs/vision-verify/UI-F03/`, the 12-row UX audit and copy critique. All three need web :3002 and API :8001, which needs app Postgres :5433 (Docker unhealthy). Skipped as not operate pages: `reset-password`, `verify`.

## 2026-10-05 — GND-MOD SEEDED (built; two boxes open)
Built: `app/stock_app_install.py` (stock-app map for 10 Community apps; Enterprise-only apps explained, never offered; one confirm step; install only via the `module.install` change-set op), App Studio gate on session create and generate, `POST /ai/sessions/{id}/stock-app` (install → model check → schema packet re-read → intent + diagnosis re-run on the same session; decline → `stopped` with one line), Expert reuses the same map and wording, web `StockAppInstallCard` plus `resolveStockApp`.
Files: `stock_app_install.py`, `routers/ai_studio.py`, `expert/live_schema_ask.py`, `tests/test_gnd_mod_stock_app.py` (34), web `StockAppInstallCard.tsx` and test (5), `use-studio-brief.ts`, `StudioPageView.tsx`, `lib/api/studio-draft.ts`, `lib/studio-session.ts`.
Tests: `pytest tests/test_gnd_mod_stock_app.py` → 28 passed, 6 errors (app Postgres :5433 down); 34 passed earlier on a looser continuation assertion. Vitest 10 passed.
Open: (1) box 2 (Sales installed for real, schema re-read, request continues) only proven on a fake port. `/tmp/gnd_mod_e2e.py` (import fixed to `odoo_client.models`) got a connection reset from :8069 on `create_database`; Docker Desktop is unhealthy. Re-run the script and the 6 database tests after a Docker restart. (2) "one confirm step used by every GND consumer": Job Autopilot still installs stock apps its own way. (3) :8001 not restarted, so no browser check yet.

CLAIM UI-F03 2026-10-05T13:10:00Z files: operate pages adopting EmptyState and Skeleton. Not App Studio / Draft Studio pages (GND-MOD), not app/command or components/command (T6-11). Do not commit.

## 2026-10-05 — T8-META DONE
Order-independent equality (`snapshots_match`) and all 15 export categories already existed. Added `capture(port, config_allowlist=...)` (read-only `fields_get` + `search_read`; config params queried only by allowlisted key, so secrets are never read; xmlids only for `ingenium`; models missing from `ir.model` skipped), `MetaSnapshot.diff`, and a suite 2 port round trip (apply via executor → inverse → snapshot equality → engine undo check).
Files: `changeset/meta_snapshot.py`, `tests/test_meta_snapshot.py` (7 new), `tests/engine/test_suite_02_round_trip.py` (6 new).
Command: `pytest tests/test_meta_snapshot.py tests/engine tests/test_schema_ops.py tests/test_changeset_cli.py` → 212 passed, 1 skipped (re-run by the orchestrator).
Round trip restores `menu.create`, `view.create_base`, `automation.create`, `cron.create`. Gaps recorded by tests, for T8-ROLLBACK / T8-S02: `field.create` inverse only relabels, `config_param.set` has no inverse, and engine undo still applies inverses to its in-memory store, not the port. Capture uses default `active_test`, so archived rows are excluded; this matches soft inverses (archive) counting as restored. Unverified: field names on 16–20, and the cost of reading all of `ir.model.fields` / `ir.ui.view`.

CLAIM T8-META 2026-10-05T13:00:00Z files: `changeset/meta_snapshot.py`, suite 2 round-trip test, `tests/test_meta_snapshot.py`. Do not commit.

## 2026-10-05 — T8-CLI DONE (GATE-P3-09)
`python -m app.changeset.cli plan|validate|simulate|apply|rollback <file.json>` runs the two-op fixture `tests/fixtures/changeset_cli_two_ops.json` (`field.create` + `view.inherit.create`) against `FakePort`, exit 0, and a subprocess check shows no `app.llm_gateway`/google/anthropic/openai/litellm module loaded. CLI and the five subcommands already existed; added the fixture, a one-line `error:` on stderr for rejected files, and 11 tests.
Files: `changeset/cli.py`, `tests/fixtures/changeset_cli_two_ops.json`, `tests/test_changeset_cli.py`.
Command: `pytest tests/test_changeset_cli.py tests/engine` → 172 passed, 1 skipped (re-run by the orchestrator). `tests/test_changeset_engine.py` needs the app Postgres on 5433 (Docker) and was not run.
Notes: CLI rollback runs the existing `undo()` on an in-memory store and then clears the fake port, so it does not send inverse calls through the port. `plan` (and sometimes `simulate`) exits 0 on invalid ops while validate/apply/rollback exit 1; existing engine behaviour, left alone.

CLAIM T8-OP-DATA 2026-10-05T12:35:00Z owner: Grok bot (external), starts after T6-11. files: data ops on the existing change-set executor (`changeset/data_ops.py` or the existing data module, the data branch in `dispatch.py`, `tests/test_data_ops.py`). Do not enable L4. Do not commit.

CLAIM GND-MOD 2026-10-05T12:30:00Z files: stock-app map, one install-confirm step shared by GND consumers (Draft Studio/App Studio first), module.install through the executor, then schema re-read and continue. Not main.py, not app/command, not five-track files (T6-11 is the Grok bot's). Do not enable L4. Do not commit.

## 2026-10-05 — T8-OP-SET DONE
Settings and module ops apply through the existing executor with public model methods: `setting.set` = `res.config.settings` create + `execute`; `config_param.set` = `set_param` (None/False refused because they delete); `company.update` = `res.company` write; `module.install` / `module.upgrade` = `search_read` by name + `button_immediate_install` / `button_immediate_upgrade`. Method calls go through an optional port `execute_kw`; a port without it refuses before any write. `module.uninstall` never applies (`prohibited_op`). Already existed and kept: `module_*` R3, protected keys refused, lock dates/fiscal year/currency/chart R4 and refused, install warning. Added: the billable flag and warning on the plan card.
Files: `changeset/setting_ops.py`, `changeset/dispatch.py`, `changeset/plan_card.py`, `tests/test_setting_ops.py` (8 → 35 tests; one install assertion made stricter).
Command: the 17-file change-set pytest set in the worker report → 647 passed, 1 skipped (re-run by the orchestrator).
Follow-ups: the plan-card golden uses `setting.set` with dotted key `x_delivery.default_note`, which still renders but would now be refused at dispatch (belongs under `config_param.set`). `button_immediate_upgrade` over RPC on 17–20 and every method on Odoo 20 are unverified. No live port exists yet; it must provide `execute_kw`.

## 2026-10-05 — T8-OP-LOGIC DONE
All 18 logic ops apply through the existing executor (`apply` → `dispatch_op`); before this only `mail_template.create` and `config_record.upsert` dispatched. Risk raises (`logic_base_raise`) and the RT-25 safe_eval AST check already existed and were kept. Payloads copy an allowlist of public fields; stage ops accept only stage models; creates without a model and updates without an id are refused. Code-carrying ops stay behind the R3 gate (Option A unchanged).
Files: `changeset/logic_ops.py`, `changeset/dispatch.py`, `tests/test_logic_ops.py`, `tests/engine/test_suite_03_idempotency.py` (not-applied example is now `data.create_batch`; still a real dispatch failure).
Command: `pytest tests/test_logic_ops.py tests/test_ui_ops.py tests/test_schema_ops.py tests/engine tests/test_handlers_grants_skills.py` → 380 passed, 1 skipped (re-run by the orchestrator).
Notes: accounting/journal/legal sequences are refused outright. That matches R4, which is denied everywhere. Through the executor, RT-25 code is refused by the protected registry before dispatch; a direct dispatch test checks the named RT-25 reason. Payloads send the model name in `model_id`, the same convention as `ir.model.access`; the live `OdooPort` (not built yet) must resolve it to an `ir.model` id. Unverified on an instance: `action_server_ids` is 17+ only, and some stage models may have no `active` field.

## 2026-10-05 — T8-OP-UI DONE
All 14 view/action/menu/filter/report ops apply through the existing change-set executor (`apply` → `dispatch_op`); no second apply path. Files: `changeset/ui_ops.py`, `changeset/dispatch.py`, `tests/test_ui_ops.py`, `tests/engine/test_suite_03_idempotency.py` (not-applied example is now `server_action.create`).
Acceptance: R1 except reports R2 (`test_ui_family_risk_is_r1_except_reports_r2`, `test_reports_are_r2_through_the_executor`); one anchor (`test_view_inherit_requires_exactly_one_anchor` in `test_handlers_grants_skills.py`, plus the executor variant); RT-22 (`test_xpath_that_replaces_root_or_large_subtree_is_refused` and the executor variant).
Commands: `pytest tests/test_ui_ops.py tests/engine/test_suite_03_idempotency.py tests/engine/test_suite_01_op_conformance.py tests/test_schema_ops.py` → 150 passed; `pytest tests/test_handlers_grants_skills.py` → 13 passed. Tests run by the orchestrator (the tester agent ran out of usage).
Follow-up: suite 01 still lists params_schema and some inverses as known gaps for this family. Those belong to T8-S01, not this card.

## 2026-10-04 — Developer modes queued
Cards DEV-CS, DEV-SR, DEV-PO in `docs/plans/next-phase/cards/DEV_MODES_PRODUCTION.md`. Code Studio, Script Runner, and Power Ops become safe for a customer to use without the founder. When they are built, the screens have to meet the UI bar in `AGENTS.md`: taste, motion, copy, accessibility, empty/loading/error/success, and a real code surface in Code Studio. They start after T6-06. No product code in this entry.

## 2026-10-03 — PDF Studio queued
Cards PDF-01–06 in docs/plans/next-phase/cards/T7_PDF_STUDIO.md. Extends ReportDesigner. No product code.

## 2026-10-03 — Harness queued
Cards H1–H8 in docs/plans/next-phase/cards/HARNESS.md. PR eval stays cassette/property. No product code.

## 2026-10-04 — Live schema context queued
GND-PKT through GND-GATE. GenerateIR already rejects uncued invent. Other LLM surfaces do not yet see the live view order.

CLAIM T8-OP-LOGIC 2026-10-05T12:13:31Z files: apps/api/app/changeset/logic_ops.py, apps/api/app/changeset/dispatch.py, apps/api/tests/test_logic_ops.py

## 2026-10-05 — PDF-05 Unsafe template gate (built; card stays OPEN)

Track: T7 PDF Studio
Intent: Centralize a QWeb unsafe-arch gate so pasted/compiled report templates containing `t-raw`, `<script`, XXE (DOCTYPE/ENTITY), or `t-call` outside the stock-layout allowlist are refused **before** save/preview persist. Block text that looks like QWeb is refused with a clear human error. RT-22 root-replace refusal (PDF-03) stays intact.
Model / band: Grok high (executor). Card status left OPEN (do not mark DONE).
Files:
- `apps/api/app/qweb_unsafe_gate.py` (new) — allowlist + refuse_unsafe_qweb_arch / refuse_unsafe_block_text
- `apps/api/app/report_design.py` — compile gates block text then resulting arch
- `apps/api/app/routers/reports.py` — create/update/preview gate before ir.ui.view write
- `apps/api/app/live_schema_context.py` — XXE parse skip uses shared `arch_has_xxe`
- `apps/api/tests/test_pdf05_unsafe_template_gate.py` (new)
- `apps/web/src/components/reports/reportUnsafeGate.ts` + `.test.ts`
- `apps/web/src/components/reports/ReportDesigner.tsx` — client refuse on save/preview
- `apps/web/src/app/connections/[id]/reports/page.tsx` — Code-tab / emit-save refuse
Allowlist (t-call): `web.external_layout`, `web.html_container`, `web.basic_layout`, `web.minimal_layout`, `web.internal_layout`
Commands and results: VERIFIED
- `pnpm --filter @odoo-custom/web test -- src/components/reports` → 5 files, **51 passed**
- `cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_pdf05_unsafe_template_gate.py tests/test_cmp4_report_design.py tests/test_pdf04_report_grounding.py` → **35 passed**
Gates / tests named:
- `test_pdf05_refuses_t_raw_before_save`
- `test_pdf05_refuses_t_out`
- `test_pdf05_refuses_script_any_case`
- `test_pdf05_refuses_doctype_and_entity_xxe`
- `test_pdf05_refuses_non_allowlisted_t_call`
- `test_pdf05_rt22_root_replace_still_refused`
- `test_pdf05_block_text_qweb_injection_refused`
- `test_pdf05_compile_gates_block_text_and_emits_safe_arch`
- `test_pdf05_update_route_refuses_pasted_unsafe_arch`
- `test_pdf05_update_route_refuses_bad_t_call`
- `test_pdf05_create_route_gates_pasted_arch`
- vitest `reportUnsafeGate.test.ts` (7)
Negative: RT-22 root replace; XXE; block text interpreted as QWeb — covered above.
Not done / gaps: card acceptance checkboxes and Status remain OPEN (orchestrator/reviewer). No live Odoo paste e2e. `t-out` refused wholesale (designer never emits it). No second editor; agent_runtime / odoo_addons / L4 untouched.
Risks introduced: allowlist is explicit — a legitimate stock `t-call` outside the five keys needs an allowlist addition. Benign block text containing substrings like `t-if` is refused by design (prefer refuse).

## 2026-10-05 — UI-S-30 Bulk Suite elite UI pass (not DONE)
Track: T7 UI-S-30. Worker elite UI/UX on `/connections/[id]/bulk-suite`. No push. No DONE. L4 stays off.
Intent: Elevate Bulk Suite to Studio-cluster craft (playbook + ingenium-v2 Basalt/teal). Primary **Run bulk action**. Blast radius before write. What/why/next empty and error. Honesty for batch writes. Harness + vision under `docs/vision-verify/UI-S-30/`.
Files: `apps/web/src/lib/bulkSuiteScreen.ts` (+test), `apps/web/src/components/bulk/bulk-operate.css`, `BulkStateGuide`, `BulkOpRail`, `BulkBlastRadius`, `BulkErrorNotice`, `BulkResultCounts` (+tests), chrome/transition/edit/access/results/recipe rewires, `apps/web/src/app/connections/[id]/bulk-suite/page.tsx`, `apps/web/src/app/e2e/bulk-suite/page.tsx`, `docs/vision-verify/UI-S-30/*`.
Tests: `pnpm exec vitest run src/lib/bulkSuiteScreen.test.ts src/components/bulk src/lib/uif-regression.test.ts` → 15 passed. tsc: no new errors in bulk files (repo still has 19 pre-existing elsewhere).
Vision: 12 after shots (empty/select/dry-run/partial/progress/error × desktop/narrow), all overflowX=0. Canonical desktop=empty, narrow=dry-run.
Not done: mark UI-S-30 DONE; real-route axe re-sweep; mirror craft onto other ops screens.
