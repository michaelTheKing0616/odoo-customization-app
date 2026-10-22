# EL-BR-REPLAY: Replay last week before rolling out a flow

ID: EL-BR-REPLAY
Title: Replay last week before rolling out a flow
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-BR
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U1 F2 K1 V1 I0)
Context pack:
- handover §3.9
- apps/api/app/bridge/flows.py
- apps/api/app/bridge/reliability.py (sandbox run)
- apps/api/app/bridge/delivery.py
File allow-list:
- apps/api/app/bridge/replay.py (new)
- apps/api/tests/test_bridge_replay.py (new)
- apps/web/src/components/bridge/ReplayDiff.tsx (new)
Goal: Run a proposed flow version against the last N recorded events in sandbox mode and show per-event differences against the current version before any rollout step.
Steps:
1. Events from `integration_events`, PII-masked (existing scrub)
2. Sandbox mode only; no outbound calls, no Odoo writes
3. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: identical versions → zero differences
- AC2: changed mapping → per-event field diff
- AC3: zero outbound HTTP on any path (test)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_bridge_replay.py`
Elite design notes: Replay is read-only by construction: the executor is the sandbox runner, never delivery.
Oracle tests: docs/build-plan/elevate/ORACLES.md: EL-BR-REPLAY-1 any path → no outbound HTTP
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
