# BV-STORE: Verify-run store: verify_runs / verify_artifacts tables behind BV-01's engine

ID: BV-STORE
Title: Verify-run store: verify_runs / verify_artifacts tables behind BV-01's engine
Status: todo
Phase: 5
Priority: P1
Type: build
Owner: backend-safe
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BV;NF-BV-STORE
Depends on: BV-03
Routing: Worker: L2 · Tester: T0 + L2 separate session · Reviewer: L2 separate session
Context pack:
- docs/build-plan/new-features/BOT_VERIFY.md §BV (sections 1–7)
- docs/build-plan/new-features/00_BASELINE.md (B1–B5)
- docs/build-plan/FACTS.md
- apps/api/app/bot_verify/contract.py (BV-01 injected engine)
- apps/api/app/routers/bot_verify.py
- apps/api/alembic/versions/ (latest head)
- apps/api/app/security/idor_registry.py
File allow-list:
- apps/api/app/bot_verify/store.py (new)
- apps/api/alembic/versions/<rev>_nf_verify_runs.py (new)
- apps/api/tests/test_nf_bot_verify_store.py (new)
Goal: Persist verify runs and artifacts so the BV-01 routes survive restarts, with every id scoped to its connection.
Steps:
1. Read BOT_VERIFY.md §6 and 00_BASELINE.md B5. Build only what this card's ACs name.
2. Write the tests first; they must fail before the code and pass after.
3. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts the epic doc; a check would need a non-`ingenium_` DB, a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434), a git write, an outbound call to a third party, or a new dependency; an Odoo claim proves false on any of 17–20.
Acceptance criteria:
- AC1: Alembic migration creates verify_runs (run_id, connection_id FK, workspace_id, changeset_id, status, layers JSON, started_at, finished_at) and verify_artifacts (artifact_id, run_id FK, connection_id, blob_path, content_type, created_at); upgrade then downgrade then upgrade is clean on an ingenium_* test DB; single alembic head.
- AC2: store.py implements BV-01's engine interface; the router uses it via the existing injection point only (no router change beyond the provider, else STOP-AND-ASK).
- AC3: Every lookup filters by connection_id (and workspace); a run_id or artifact_id belonging to another connection/workspace returns a 404 byte-identical (status, headers, body) to a random id.
- AC4: Artifact bytes live under the workspace data dir, never in the DB; blob_path is relative, and path traversal (../, absolute) is refused.
- AC5: No secrets or PII in stored rows (evidence values already masked by BV-02; test asserts a seeded secret/PII string never lands in a row).
Test plan:
- pytest -q tests/test_nf_bot_verify_store.py tests/test_nf_bot_verify_contract.py → pass
Focused set: own test + tests/test_nf_bot_verify_contract.py, tests/test_safety_route_registry.py, tests/test_protected_registry.py, tests/test_trust7_idor.py, tests/test_trust7_credentials.py, tests/test_trust7_app_db_restore.py.
Combined set (both orders): own test + tests/test_sec_gate_scope.py + tests/test_reg_np_dev.py + earlier NF contract tests (test_nf_*_contract.py). Random-order AC deferred until the main stream installs pytest-randomly.
Gate: none. Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label. Tester packet and Reviewer verdict in `docs/build-plan/STATE_NF.md`.
Rollback: Alembic downgrade of this revision, then revert this card's diff (allow-list files only).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Status set to done.
