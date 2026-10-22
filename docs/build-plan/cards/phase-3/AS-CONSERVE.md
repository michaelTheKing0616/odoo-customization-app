# AS-CONSERVE: Conservation audit and orphan repair

ID: AS-CONSERVE
Title: Conservation audit and orphan repair
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-FIX-CONSERVE
Depends on: AS-COMPILE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F2 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.4 step 1
- docs/build-plan/app-studio/ORACLES.md C-12
- docs/build-plan/CODE_MAP.md row: orphan repair
File allow-list:
- apps/api/app/ai_conversation/conservation.py (new)
- apps/api/app/ai_conversation/orphan_repair.py (accept ledger orphans as input)
- apps/api/tests/test_conservation.py (new)
Goal: Precision (every element has lineage) and recall (every in-scope ledger item is realized) are checked; a miss gets one repair call, then an honest left_out.
Steps:
1. `audit(design, voted, brief) -> {unlicensed:[…], unrealized:[…]}`
2. Unlicensed elements are removed + logged (never shown as 'built')
3. Unrealized items and L5 orphan clauses → `orphan_repair.repair_step` with only those clauses, owner words only (1 call max, `timeout_s` from the caller) → re-compile those items → still missing → left_out `not_built_yet` with quote
4. `audit(..., allow_repair=False)` under `owner_override` re-runs (AS-PROMOTE)
Acceptance criteria:
- AC1: C-12 passes
- AC2: Property: after audit, unlicensed = [] and every unrealized item is in left_out
Test plan:
- `cd apps/api && uv run pytest -q tests/test_conservation.py`
Elite design notes: docs/build-plan/app-studio/00_PACK.md §6.4. This is the coverage-by-construction mechanism for failure C; it must run after compile and before polish.
Oracle tests: docs/build-plan/app-studio/ORACLES.md C-12 plus the two properties in the ACs.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
