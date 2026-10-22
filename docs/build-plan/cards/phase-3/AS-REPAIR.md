# AS-REPAIR: Polish step that cannot change structure

ID: AS-REPAIR
Title: Polish step that cannot change structure
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P1-2; AS-8.5-CRITIQUE
Depends on: AS-COMPILE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.3 (structure hash), §3 P
- handover L923
- docs/build-plan/app-studio/ORACLES.md C-11
File allow-list:
- apps/api/app/ai_conversation/ledger_polish.py (new)
- apps/api/tests/test_ledger_polish.py (new)
Goal: One optional LLM call (never a loop) improves labels, help text and view grouping; any structural change is discarded; skipped when the soft deadline has passed.
Steps:
1. Input = compiled design JSON + owner words; output schema = labels/help/groups only
2. Apply → recompute `structure_hash`; differs → discard + log `polish_structure_change`
3. Skip when the soft deadline is reached or profile.polish is False
Acceptance criteria:
- AC1: C-11 passes
- AC2: Polish off → identical design; polish on with fake output → only label/help fields differ
Test plan:
- `cd apps/api && uv run pytest -q tests/test_ledger_polish.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
