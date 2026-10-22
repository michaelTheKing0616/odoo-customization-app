# AS-STOCKCARD: 'Use stock app X' as a first-class recommendation

ID: AS-STOCKCARD
Title: 'Use stock app X' as a first-class recommendation
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-STOCKCARD
Depends on: AS-RETRIEVE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- handover §3.3 L244, §3.17 L412
- docs/build-plan/CODE_MAP.md row: stock routing
File allow-list:
- apps/api/app/ai_conversation/ledger_compile.py (stock_suggestions only)
- apps/api/tests/test_stockcard.py (new)
Goal: When retrieval finds an installable stock app that covers most records (restaurant → POS, project_tracker → Project, retail → Sales/Inventory), the outcome carries a recommendation card first.
Steps:
1. Coverage = share of record entities whose top candidate belongs to one stock app
2. ≥ 0.6 → recommendation with plain reasons; owner can still choose custom
Acceptance criteria:
- AC1: 3 fixture briefs produce the expected stock app recommendation
- AC2: Recommendation never blocks the custom path
Test plan:
- `cd apps/api && uv run pytest -q tests/test_stockcard.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
