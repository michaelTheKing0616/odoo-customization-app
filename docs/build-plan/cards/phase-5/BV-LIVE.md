# BV-LIVE: Live read-back proof on Odoo 17–20

ID: BV-LIVE
Title: Live read-back proof on Odoo 17–20
Status: todo
Phase: 5
Priority: P1
Type: build
Owner: backend-safe
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BV;NF-BV-LIVE
Depends on: BV-STORE
Routing: Worker: L3 · Tester: T0 + L2 separate session · Reviewer: L2 separate session
Context pack:
- docs/build-plan/new-features/BOT_VERIFY.md §BV (sections 1–7)
- docs/build-plan/new-features/00_BASELINE.md (B1–B5)
- docs/build-plan/FACTS.md
- apps/api/app/bot_verify/collector.py, readback.py (BV-02)
- apps/api/app/changeset/verify.py, ops.py (OP_CATALOG), executor.py
File allow-list:
- apps/api/app/bot_verify/collector.py
- apps/api/app/bot_verify/readback.py
- apps/api/tests/test_nf_bot_verify_live.py (new; live-marked, skipped without the live env)
- apps/api/tests/live/nf_bv_seed.py (new; disposable DB create/seed/drop helper)
Goal: Prove BV-02's read-back against real Odoo 17, 18, 19 and 20 and close the gaps fakes cannot show.
Steps:
1. Read BOT_VERIFY.md §6 and 00_BASELINE.md B5. Build only what this card's ACs name.
2. Write the tests first; they must fail before the code and pass after.
3. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts the epic doc; a check would need a non-`ingenium_` DB, a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434), a git write, an outbound call to a third party, or a new dependency; an Odoo claim proves false on any of 17–20.
Targets: only DBs named ingenium_nf_bv_{17,18,19,20}, created for the run and dropped afterwards (drop asserted in teardown, also on failure). Never aonb or client DBs; never a reserved port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434).
Acceptance criteria:
- AC1: Persona check proven with per-user logins (as_uid): requester, low-privilege internal and portal users each get their own session; view-render and access checks run under that uid; portal users get AccessError where expected and that counts as the expected result, not a pass by default. No persona login = skipped with reason.
- AC2: Before-snapshot is captured server-side by the collector before apply (not handed in by the caller); a seeded mismatch against it fails the check on every version.
- AC3: An Odoo 429/503 during read-back yields skipped with reason "retryable"; the caller retries and never rolls back on that result (test proves no rollback call).
- AC4: setting.set read-back reads company fields (res.company) and group-backed settings (res.groups membership / implied groups), not only ir.config_parameter, on 17–20.
- AC5: Free-text fields (function, comment, description and other Text/Html fields) are masked in samples and evidence; grep over the evidence bundle finds no seeded PII string.
- AC6: One change-set per op family applied and read back on each of 17–20: pass on the good set, fail on its seeded-defect twin ([Done, live]).
Test plan:
- pytest -q -m live tests/test_nf_bot_verify_live.py → pass on 17–20 (live env); offline run → all skipped with reason
Focused set: own test + tests/test_nf_bot_verify_collector.py, tests/test_verify.py, tests/test_safety_route_registry.py, tests/test_protected_registry.py, tests/test_trust7_idor.py, tests/test_trust7_credentials.py, tests/test_trust7_app_db_restore.py.
Combined set (both orders): own test + tests/test_sec_gate_scope.py + tests/test_reg_np_dev.py + earlier NF contract tests (test_nf_*_contract.py). Random-order AC deferred until the main stream installs pytest-randomly.
Gate: none. Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label. Tester packet and Reviewer verdict in `docs/build-plan/STATE_NF.md`.
Rollback: Drop ingenium_nf_bv_* DBs; revert this card's diff (allow-list files only). No Odoo writes outside dropped ingenium_* DBs.
Definition of Done: Every AC has evidence on all of 17–20; DBs dropped; oracle tests unmodified and green; no file outside the allow-list changed; Status set to done.
