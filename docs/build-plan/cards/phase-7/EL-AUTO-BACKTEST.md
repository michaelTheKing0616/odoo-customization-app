# EL-AUTO-BACKTEST: Automation backtest before going live

ID: EL-AUTO-BACKTEST
Title: Automation backtest before going live
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-BUILD
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- handover §3.18 (Automations)
- apps/api/app/routers/automations.py
File allow-list:
- apps/api/app/automation_backtest.py (new)
- apps/api/tests/test_automation_backtest.py (new)
Goal: For a draft automation: 'would have fired n times in the last 30 days on these records', read-only, using the trigger domain and dates.
Steps:
1. Read-only search with the trigger domain; time triggers evaluated over the window
2. Python-backed triggers: say 'can't predict code' honestly
3. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: fixture with 3 matching records → 3
- AC2: zero writes on any path
Test plan:
- `cd apps/api && uv run pytest -q tests/test_automation_backtest.py`
Elite design notes: Domain evaluation goes through Odoo search, never a local re-implementation.
Oracle tests: docs/build-plan/elevate/ORACLES.md: EL-AUTO-BACKTEST-1 any path → zero writes
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
