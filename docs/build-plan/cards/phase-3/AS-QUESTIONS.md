# AS-QUESTIONS: At most three questions, each with a default

ID: AS-QUESTIONS
Title: At most three questions, each with a default
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-QUESTIONS-ROW; AS-8.7-AC7
Depends on: AS-STABILITY
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F2 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.2, §8 items 2-3
- handover §8.7 AC7 (L948)
File allow-list:
- apps/api/app/ai_conversation/ledger_questions.py (new)
- apps/api/app/routers/ai_studio.py (clarify route: v3 branch only)
- apps/api/tests/test_ledger_questions.py (new)
Goal: Questions come only from voted doubts that change structure, ranked by impact, max 3, with owner-plain copy and a default; 'Use my defaults' resolves all.
Steps:
1. Rank as Pack §6.2
2. Copy templates per role pair (record vs fact, record vs line, future vs record) in plain words; no technical names (jargon guard)
3. Answers become `owner_override` and re-run V→C→A with no LLM call
4. Overflow (candidates beyond the top 3) take their default and become suggestion chips with a stored proposal; count `overflow_unsure` in `llm_outcome` (Pack §6.2)
5. `thin` records (L2) enter the pool at the lowest rank with "What do you note about each ___?"
Acceptance criteria:
- AC1: Never more than 3 questions (property)
- AC2: Every question has a default and 'Use my defaults' produces a proposal
- AC3: §8.7 AC7 verbatim: "owner UI: questions at most 3, each with a default; the assumption ledger is editable; every proposed item shows the owner's quote it came from; plain words only" (API half; UI half is UI-APPSTUDIO-BUILD)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_ledger_questions.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
