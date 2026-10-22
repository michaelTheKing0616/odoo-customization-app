# AS-COMPUTE-MATRIX: Counts, sums and latest values without custom Python

ID: AS-COMPUTE-MATRIX
Title: Counts, sums and latest values without custom Python
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-FAIL-D
Depends on: AS-COMPILE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.3 (report row)
- docs/specs/APP_STUDIO_FIX_PLAN.md 'D/C shared cause'
File allow-list:
- apps/api/app/ai_conversation/ledger_compile.py (report rules only)
- apps/api/tests/test_compute_matrix.py (new)
Goal: A report rule becomes a pivot/graph measure, list sum, group-by or related field; `python_needed` stays empty unless the contract says option_a.
Steps:
1. Table: count→pivot count + graph; sum/total→list sum + pivot measure; average→pivot avg; latest→related field on the parent or a sorted o2m
2. Live count on the parent form → left_out 'not built: needs custom code' with quote (metadata-only lane)
Acceptance criteria:
- AC1: C-08 passes
- AC2: Across 10 hand-written ledgers covering every report wording in dev/dev2 golds (count, total, average, latest, per-period), `python_needed` count = 0 except rows whose contract decision is option_a. The 28-brief replay check moves to AS-CONTRACT-EVAL step 1, once v3 recordings exist
Test plan:
- `cd apps/api && uv run pytest -q tests/test_compute_matrix.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
