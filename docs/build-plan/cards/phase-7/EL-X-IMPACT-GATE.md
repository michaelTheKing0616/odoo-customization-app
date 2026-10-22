# EL-X-IMPACT-GATE: Show everything that breaks before a delete, rename or type change

ID: EL-X-IMPACT-GATE
Title: Show everything that breaks before a delete, rename or type change
Status: todo
Phase: 7
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-REL
Depends on: EL-X-BAR
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- packages/odoo-client/src/odoo_client/schema_graph.py L83 (`find_usages`)
- apps/api/app/routers/builder.py (field delete/rename)
- apps/web/src/components/ConfirmDialog.tsx
File allow-list:
- apps/api/app/impact_gate.py (new)
- apps/api/app/routers/builder.py (call the gate before destructive ops)
- apps/api/tests/test_impact_gate.py (new)
- apps/web/src/components/ConfirmDialog.tsx (impact list slot)
Goal: Before a destructive schema op, list views, automations, reports, server actions, Bridge mappings and saved scripts that use the field; block until the owner confirms with the list on screen.
Steps:
1. Odoo-side usages from `find_usages`; Ingenium-side usages from the App DB (mappings, scripts)
2. API requires the existing advanced confirmation flag plus the impact hash the owner saw
3. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: delete without the matching impact hash → refused
- AC2: list shows Odoo and Ingenium usages
- AC3: copy passes the jargon guard
Test plan:
- `cd apps/api && uv run pytest -q tests/test_impact_gate.py`
Elite design notes: Confirmation binds to the exact impact list (hash) so a stale screen cannot authorise a bigger change.
Oracle tests: docs/build-plan/elevate/ORACLES.md: EL-X-IMPACT-1 stale impact hash → refused; EL-X-IMPACT-2 field used by a Bridge mapping → listed
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
