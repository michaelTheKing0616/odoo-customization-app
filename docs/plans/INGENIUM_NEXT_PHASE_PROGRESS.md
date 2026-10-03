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

