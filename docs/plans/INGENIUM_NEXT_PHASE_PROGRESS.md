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
- T2-J1 `/doc` text match is not verified. Do not say JSON-2 is complete. Sandbox default stays XML-RPC. Promote stays human.
- L4 stays off until GATE-L4-08 evidence exists. Thresholds are confirmed.
- Production R3 stays blocked until an operator-owned neutralized clone exists for that tenant. Above R1 stays review-only.
- GATE-P6-04 has not been run. The tool shape is family lists.
- BL-08 commit plan is not written yet. A second yes is required before those commits.
- `safety_gate.preflight` does not pass `odoo_major`. `snapshot_gate.py` uses `== 20`. `database_backup.py` uses `>= 20`. Snapshot freshness (`created_at`, last write, BILLABLE) is not wired on that caller.
- An unset module major still emits `security/record_rules.xml` as `ir.rule` (`packages/module-generator`).
- Live Odoo 20 version-table probes stay skipped until `ODOO20_URL` is set.
- UI-F03 was not re-checked against every route in screen spec 13 marked "can be empty".
- `ConfirmDialogV2` is still its own overlay, not `DialogPanel`.
- `cmdk` still depends on `@radix-ui/react-dialog`. No source file imports it.
- The expert panel and billing still use `Sheet`, not the motion sheet.
- Axe was not run for `/bots`, `/bots/rooms/[id]`, `/bots/[id]`, `/studio/dashboards`, `/bridge/connections`, or `/onboarding`. `/connections` only redirects.
- Durable WAL is still T8-EXEC. The journal is in-process.
- T8-MEM is still open. ADR-09 records the four memory classes. The code does not exist yet. `memory_propose` is not implemented.
- The skill router is not built. ADR-10 records the package rules. No skill card has shipped the router.
- Audit retention is not wired. ADR-11 locks the chain shape. Append and verify already exist. 24 months, 7 years for accounting kinds, and 7 days for raw LLM payloads are still open.
- The KMS vendor is unchosen. ADR-12 keeps secrets on the existing `fernet_key`. No cloud KMS client.
- The eval harness is not built. ADR-13 records the A/B/C bars. GATE-P4-04 and GATE-P6 are still open.
- GATE-P0-03 is still open. The eight seed names exist only as catalog definitions in `apps/api/app/changeset/fixture_catalog.py`. Live fixtures on Odoo 17, 18, 19, and 20 were not brought up. The stand-in reset is not a live database reset.
- GATE-P0-05 stays open. `apps/api/tests/test_import_boundary.py` locks 22 Odoo-version branches outside `compat/` in `apps/api/app`. A new hit fails the test. Those branches were not moved.
- Missing call ids are still `call_{index:04d}`. The `call_<ulid>` form is not implemented. No ulid package was added.
- `parse_tool_args` rejects payloads over 256 KB. That reject has no dedicated test.
- GATE-P1-02 is not fully passed. Replay fixtures under `apps/api/tests/fixtures/llm_gateway/` are synthetic. Still needs an operator recording: C07, C08, C10, C11, C13, C14, C16, C17, C18, C19, and OpenAI C20.
- The model registry stores no product model ids yet. The outside-file scan passes because that list is empty. An unknown id stays untiered with read-only caps.
- GATE-P1-04 and GATE-P1-06 are proven with 200 scripted calls, not a live cassette. A recorded live 200-call cassette is still open.
- The transport contract in `packages/odoo-client/src/odoo_client/transport/contract.py` is proven on a fake send function. It is not wrapped around the XML-RPC or JSON-2 adapters. Local HTTP sandboxes are unchanged.
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
