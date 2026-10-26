# BL-07b: The MCP scan writes nothing on a second run

ID: BL-07b
Title: The MCP scan writes nothing on a second run
Status: done
Phase: 0
Priority: P2
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: NP-BL-07b
Depends on: BL-07
Routing: Worker: L1 (grok-4.7-xhigh) · Tester: T0 + L1 separate session · Reviewer: L1 separate session · Score: 2 (C0 U0 F0 K1 V0 I1)
Context pack:
- docs/build-plan/cards/phase-0/BL-07.md
- apps/api/tests/test_bl_07.py
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/test_bl_07.py
Goal: Close the idempotency sentence without an Odoo plan. The scan only reads files.
Steps:
1. Add one test: run the scan twice and assert the second run writes 0 records.
2. Do not connect to a database. Do not call Odoo.
3. STOP-AND-ASK: the proof would need a file outside this allow-list.
Acceptance criteria:
- AC1: A second scan run writes 0 records. The test does not open a database. (source: BL-07 AC4, held 2026-10-22)
Test plan:
- `cd apps/api && uv run pytest -q -p no:randomly tests/test_bl_07.py` → pass.
Gate: none. Narrowest named test green → Tester PASS → Reviewer PASS.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code]).
Rollback: Revert `apps/api/tests/test_bl_07.py` only.
Definition of Done: AC1 is green; no file outside the allow-list changed.
