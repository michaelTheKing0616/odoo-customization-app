# EL-VD-EDGE: Preview the screen with edge-case records

ID: EL-VD-EDGE
Title: Preview the screen with edge-case records
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-VD, EL-X-EDGE-RECORDS
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- apps/web/src/components/odoo-preview/
File allow-list:
- apps/web/src/components/view-designer/EdgeRecordPicker.tsx (new)
- apps/web/src/components/view-designer/EdgeRecordPicker.test.tsx (new)
Goal: A picker to preview with the longest-name, emptiest, most-lines or archived record, with layout warnings.
Steps:
1. Uses EL-X-EDGE-RECORDS ids
2. 'None in this database' shown honestly
3. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: each case switches the preview record
- AC2: missing case shows the honest state
Test plan:
- `cd apps/web && pnpm vitest run src/components/view-designer/EdgeRecordPicker.test.tsx`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
