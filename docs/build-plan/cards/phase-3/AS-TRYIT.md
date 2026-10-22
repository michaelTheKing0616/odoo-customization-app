# AS-TRYIT: Try it with your data: sandbox walkthrough before install (Q3)

ID: AS-TRYIT
Title: Try it with your data: sandbox walkthrough before install (Q3)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT-QUALITY
Depends on: AS-CRAFT-MODULE, AS-CRAFT-DATA
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U1 F1 K1 V2 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md Q3
- INV-03 (disposable ingenium_* DBs), INV-15 (honest data)
File allow-list:
- apps/api/app/ai_conversation/try_it.py (new)
- apps/api/app/routers/ai_studio.py (new route `POST /{id}/try`)
- apps/api/tests/test_try_it.py (new)
Goal: After a sandbox install, load 5-20 rows from the owner's own spreadsheet (via the K42 import template and Universal Ingest) or clearly labelled Example rows, and run a scripted walkthrough: create, move state, open a smart button, print.
Steps:
1. Sandbox only: a disposable `ingenium_try_<session>` DB, dropped after 24 h or on install
2. Owner rows never leave the sandbox; Example rows are labelled 'Example' everywhere (INV-15)
3. Walkthrough steps and their results return as plain events
4. The owner-facing screen for this card is built in UI-APPSTUDIO-BUILD to the 07_UI_EXCELLENCE_PROTOCOL bar (Tope: the absolute best design on every screen); this card ships the API contract and plain copy only.
Acceptance criteria:
- AC1: Walkthrough on bakery_ng with Example rows passes every step on a disposable v19 sandbox (GATE-A)
- AC2: The DB is dropped by the cleanup job (test lists DBs before/after)
- AC3: No owner row appears in any log (scrub test, INV-17)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_try_it.py`
Elite design notes: This touches customer data in a sandbox: disposable DB only, never a client DB, never logged.
Oracle tests: docs/build-plan/app-studio/ORACLES.md §K rows named in the ACs.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
