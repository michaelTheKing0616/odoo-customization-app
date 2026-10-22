# AS-GROUND-DATA: Data shape facts that change what gets built

ID: AS-GROUND-DATA
Title: Data shape facts that change what gets built
Status: todo
Phase: 3
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-GROUND
Depends on: AS-GROUND-WIRE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.7 item 5
- apps/api/app/routers/builder.py (existing fill-rate endpoint `/models/{m}/fill`)
File allow-list:
- apps/api/app/ai_conversation/ground_data.py (new)
- apps/api/tests/test_ground_data.py (new)
Goal: Read-only facts for D and C: multi-company on/off, active currencies, installed languages, host stages/sequences present, fill rates of candidate anchors.
Steps:
1. Counts and flags only; never record contents (INV-17)
2. Feed K12 (company/currency) and translation rows only when the fact says so
Acceptance criteria:
- AC1: Facts object has only booleans, counts and technical names (property)
- AC2: Multi-company off → no company field emitted by craft
Test plan:
- `cd apps/api && uv run pytest -q tests/test_ground_data.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
