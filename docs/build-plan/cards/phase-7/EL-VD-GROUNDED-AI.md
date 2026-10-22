# EL-VD-GROUNDED-AI: Edit with AI places by labels and verifies

ID: EL-VD-GROUNDED-AI
Title: Edit with AI places by labels and verifies
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-VD, AS-GROUND-PLACE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- apps/api/app/view_engine_ai.py
- apps/api/app/ai_conversation/ground_place.py (AS-GROUND-PLACE)
File allow-list:
- apps/api/app/view_engine_ai.py
- apps/api/tests/test_view_engine_ai_grounded.py (new)
Goal: View Designer AI edits resolve placement through ground_place and are re-read after publish, same as App Studio.
Steps:
1. AI proposes typed ops with the owner phrase; code places them
2. Post-publish fidelity check (EL-X-FIDELITY)
Acceptance criteria:
- AC1: 'put X after Payment Terms' → xpath on `payment_term_id`
- AC2: misplaced node rolled back with a plain reason
Test plan:
- `cd apps/api && uv run pytest -q tests/test_view_engine_ai_grounded.py`
Elite design notes: Shares AS-GROUND-PLACE; no second placement engine.
Oracle tests: docs/build-plan/elevate/ORACLES.md: app-studio/ORACLES.md G-06, G-11 run against view_engine_ai
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
