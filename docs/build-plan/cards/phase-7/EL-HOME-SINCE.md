# EL-HOME-SINCE: Since you were last here

ID: EL-HOME-SINCE
Title: Since you were last here
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-HOME
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- handover §3.1
- apps/api/app/routers/command_center.py
- apps/api/app/schema_freshness.py
File allow-list:
- apps/api/app/since_last_visit.py (new)
- apps/api/app/routers/command_center.py
- apps/api/tests/test_since_last_visit.py (new)
- apps/web/src/components/overview/SinceLastVisit.tsx (new)
Goal: Per database, what changed since this person's last visit: apps added/removed, failed scheduled jobs, drift, Bridge dead letters, expiring keys; each row has one action.
Steps:
1. Diff stored snapshots by code; no LLM numbers (INV-15)
2. Empty → 'Nothing changed since <time>' state
3. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: every row links to the tool that resolves it
- AC2: counts match the App DB in a fixture test
Test plan:
- `cd apps/api && uv run pytest -q tests/test_since_last_visit.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
