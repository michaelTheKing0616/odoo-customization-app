# EL-SUITE-BASELINE: Approved configuration baseline and drift

ID: EL-SUITE-BASELINE
Title: Approved configuration baseline and drift
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-SUITE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- handover §3.7 (ideas 25, 39)
- apps/api/app/suite_insights.py
- apps/api/app/suite_change.py
File allow-list:
- apps/api/app/suite_baseline.py (new)
- apps/api/tests/test_suite_baseline.py (new)
- apps/web/src/components/suite/BaselinePanel.tsx (new)
Goal: Save 'how this database should be set up' (settings, taxes, journals, sequences, access); show changes made directly in Odoo since; restore any of them through a Change batch with Check and Undo.
Steps:
1. Snapshot via existing config_as_code readers
2. Restore = a Change batch through the write gate; money items under the money guard
3. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: a settings change made in Odoo appears as drift
- AC2: restore runs Check first and records Undo
- AC3: money items require the money guard
Test plan:
- `cd apps/api && uv run pytest -q tests/test_suite_baseline.py`
Elite design notes: Extends suite idea 25 and Home drift; restore never bypasses Check/Run/Review.
Oracle tests: docs/build-plan/elevate/ORACLES.md: EL-SUITE-BASELINE-1 drift detected after direct change; EL-SUITE-BASELINE-2 restore of a tax item without money guard → refused
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
