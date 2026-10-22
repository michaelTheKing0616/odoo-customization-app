# AS-CONTRACT-QUOTES: Contract quotes come only from the owner's words

ID: AS-CONTRACT-QUOTES
Title: Contract quotes come only from the owner's words
Status: todo
Phase: 3
Priority: P1
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: XS (caps in budget.json). Stop at 80%.
Ledger IDs: P1-1-AC1
Depends on: none
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: L1 separate session · Reviewer: L2 separate session · Score: 2 (C0 U1 F1 K0 V0 I0)
Context pack:
- handover L516 (P1-1 AC1)
- docs/build-plan/CODE_MAP.md rows: owner words, contract call
File allow-list:
- apps/api/tests/test_contract_quotes.py (new)
Goal: Prove AC1 with a unit test (the handover says the behaviour is already in code).
Steps:
1. Fake provider returns a contract whose one row quotes 'Create a Widget model'
2. Owner words do not contain it; the expansion does
3. Call `_call_intent_contract` with `set_original(owner)`; assert the row is dropped or re-quoted from the owner's words
Acceptance criteria:
- AC1: P1-1 AC1 verbatim: "contract quotes come only from the owner's original words; AI expansion is context only and never quotable"
- AC2: If the test fails, the card stops and reports; the fix belongs to AS-SRC-BRIEF
Test plan:
- `cd apps/api && uv run pytest -q tests/test_contract_quotes.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
