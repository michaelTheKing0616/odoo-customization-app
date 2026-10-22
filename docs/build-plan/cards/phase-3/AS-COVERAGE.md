# AS-COVERAGE: Coverage miss audit (failure C)

ID: AS-COVERAGE
Title: Coverage miss audit (failure C)
Status: todo
Phase: 3
Priority: P1
Type: verify
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-FAIL-C
Depends on: AS-EVAL-FAIR, AS-CONSERVE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U2 F1 K0 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §2 RC8
- docs/specs/APP_STUDIO_FIX_PLAN.md 'Coverage'
File allow-list:
- apps/api/evals/v2/coverage_audit.py (new)
- apps/api/evals/v2/experiments/coverage.md (new; results)
Goal: Classify every missed need on legacy and v3 recordings as unreached / scorer-miss / true miss, so fixes target the real cause.
Steps:
1. Run on recordings only (0 LLM calls)
2. Scorer-miss = aligned by span but not by stems
3. Write counts per class and the 10 largest true misses with their quotes
Acceptance criteria:
- AC1: Report exists with the three counts for both profiles
- AC2: Each true miss names the missing element kind (model, field, automation, access)
Test plan:
- The Tester re-derives one count by hand from the raw JSON
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
