# BV-UI: Evidence viewer: screenshot timeline and check results in Bots

ID: BV-UI
Title: Evidence viewer: screenshot timeline and check results in Bots
Status: todo
Phase: 5
Priority: P1
Type: build
Owner: ui
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BV;NF-BV-UI
Depends on: BV-01 (contract); BV-04 for real data
Routing: Worker: L2 · full UI trial process (trial screen is the floor) · Tester + Reviewer separate sessions
Context pack:
- docs/build-plan/new-features/BOT_VERIFY.md §BV (sections 1–7)
- docs/build-plan/new-features/00_BASELINE.md (B1–B5)
- docs/build-plan/FACTS.md
- apps/api/app/changeset/verify.py
- apps/api/app/changeset/ops.py (OP_CATALOG)
- apps/api/app/changeset/executor.py
- apps/api/app/security/idor_registry.py
File allow-list:
- apps/web/src/components/bots/EvidenceViewer.tsx (new)
- apps/web/src/components/bots/EvidenceViewer.test.tsx (new)
- docs/design/UI_DIRECTION.md (BV-UI entry only)
Goal: Show a verify run: layer status, check results per op, screenshot timeline, flow outcome, rollback state, in the Bots area (area 12).
Steps:
1. Read BOT_VERIFY.md §6 and 00_BASELINE.md B5. Build only what this card's ACs name.
2. Write the tests first; they must fail before the code and pass after.
3. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts the epic doc; a check would need a non-`ingenium_` DB, a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434), a git write, an outbound call to a third party, or a new dependency; an Odoo claim proves false on any of 17–20.
Acceptance criteria:
- AC1: Renders every VerifyRun status and every LayerResult status, including skipped with reason.
- AC2: Screenshot timeline keyboard-navigable; axe clean; reduced-motion respected.
- AC3: Uses botVerify.ts types only; no new API.
- AC4: Full UI trial run; result beats the trial screen; UI_DIRECTION.md entry added.
- AC5: Plain-language copy; no secrets or raw PII shown (masked screenshots only).
Test plan:
- cd apps/web && pnpm vitest run src/components/bots/EvidenceViewer.test.tsx → pass
- pnpm typecheck → no new errors
Focused set: own test + tests/test_safety_route_registry.py, tests/test_protected_registry.py, tests/test_trust7_idor.py, tests/test_trust7_credentials.py, tests/test_trust7_app_db_restore.py, tests/test_verify.py.
Combined set (both orders): own test + tests/test_sec_gate_scope.py + tests/test_reg_np_dev.py + earlier NF contract tests (test_nf_*_contract.py). Random-order AC deferred until the main stream installs pytest-randomly.
Gate: none. Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label. Tester packet and Reviewer verdict in `docs/build-plan/STATE_NF.md`.
Rollback: Revert this card's diff (allow-list files only). No Odoo writes outside dropped `ingenium_*` DBs.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Status set to done.
