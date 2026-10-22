# AS-CRAFT-PARITY: Stock-parity score: does it sit next to stock Odoo apps without looking amateur? (Q1)

ID: AS-CRAFT-PARITY
Title: Stock-parity score: does it sit next to stock Odoo apps without looking amateur? (Q1)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT-QUALITY
Depends on: AS-CRAFT-CATALOG, AS-CRAFT-SCORE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md 'Quality systems' Q1
- AS-CRAFT-CATALOG probe output (stock exemplar views per major)
File allow-list:
- apps/api/evals/v2/craft_parity.py (new)
- apps/api/evals/v2/tests/test_craft_parity.py (new)
Goal: For each generated view, list the features its stock exemplar of the same shape has (header, button box, chatter, filters, group-bys, sums, kanban card parts) and report every gap.
Steps:
1. Exemplar per shape: document with lines → sale.order; pipeline → crm.lead; task-like → project.task; contact-like → res.partner
2. Feature extraction is the same parser for both sides
3. Report gaps per brief, per major
Acceptance criteria:
- AC1: Synthetic pair (exemplar vs a view missing chatter and filters) reports exactly those 2 gaps
- AC2: Release bar in AS-RELEASE-BARS: 0 gaps that the exemplar of the same shape has, on the module lane
Test plan:
- `cd apps/api && uv run pytest -q evals/v2/tests/test_craft_parity.py`
Elite design notes: Stock views are the reference for 'world-class'. Read them over RPC; never copy Enterprise or Studio code (INV-12).
Oracle tests: docs/build-plan/app-studio/ORACLES.md §K rows named in the ACs.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
