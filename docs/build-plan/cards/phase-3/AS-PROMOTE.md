# AS-PROMOTE: Promote and demote without an LLM call

ID: AS-PROMOTE
Title: Promote and demote without an LLM call
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-PROMOTE-ROW
Depends on: AS-COMPILE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.5
- docs/build-plan/app-studio/ORACLES.md C-13
File allow-list:
- apps/api/app/routers/ai_studio.py (new route `POST /{id}/override`)
- apps/api/app/ai_conversation/ledger_compile.py (apply overrides)
- apps/api/tests/test_promote.py (new)
Goal: `{item, action: promote|demote}` re-runs C and A only; the result is stable on re-run.
Steps:
1. Store overrides in session `resolved_answers['_owner_overrides']`
2. Promote restores `left_out[].proposal`; demote folds a model onto its host as selection/char
3. Return the new outcome in < 1 s (fake provider asserts 0 calls)
Acceptance criteria:
- AC1: C-13 passes
- AC2: 0 provider calls (assert); the conservation audit runs with repair skipped under `owner_override` (Pack §6.4 step 1)
- AC3: Override survives a regenerate
Test plan:
- `cd apps/api && uv run pytest -q tests/test_promote.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
