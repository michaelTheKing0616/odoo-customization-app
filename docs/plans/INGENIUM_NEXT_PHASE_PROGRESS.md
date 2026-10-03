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
