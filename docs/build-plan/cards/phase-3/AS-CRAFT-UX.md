# AS-CRAFT-UX: Forms, lists and kanban that guide the user (K28-K35)

ID: AS-CRAFT-UX
Title: Forms, lists and kanban that guide the user (K28-K35)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT-PLUS
Depends on: AS-CRAFT-APPLY, AS-CRAFT-SMART
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md rows K28-K35
- docs/build-plan/app-studio/ORACLES.md K-12, K-13
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/ux.py (new)
- apps/api/tests/test_odoo_craft_ux.py (new)
Goal: State-aware forms, ribbons, confirm text, rich kanban cards, empty-state help, default filters, context defaults and inline lines.
Steps:
1. One row function per K28-K35, registered in `ROWS`
2. State expressions use the 17+ `invisible=`/`readonly=` syntax only; never `attrs`
3. Empty-state help and confirm text are plain owner language and pass the jargon guard
Acceptance criteria:
- AC1: ORACLES K-12 and K-13 pass unmodified
- AC2: Every emitted view passes the existing per-major view validators
- AC3: Jargon guard passes on every help and confirm string
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft_ux.py`
Elite design notes: Rows register in the AS-CRAFT-APPLY `ROWS` registry; syntax only from the verified per-version catalog; every edit carries `craft:Kxx`; never a business record or field (ORACLES K-05).
Oracle tests: docs/build-plan/app-studio/ORACLES.md §K rows named in the ACs.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
