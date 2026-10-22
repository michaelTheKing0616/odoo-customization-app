# AS-CRAFT-DATA: Ready on day one: ordered selections, lookup data, import templates, upgrade-safe data (K40-K44)

ID: AS-CRAFT-DATA
Title: Ready on day one: ordered selections, lookup data, import templates, upgrade-safe data (K40-K44)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT-PLUS
Depends on: AS-CRAFT-APPLY, AS-CRAFT-MODULE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md rows K40-K44
- docs/build-plan/app-studio/ORACLES.md K-15
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/data.py (new)
- apps/api/app/ai_conversation/odoo_craft/module_templates/ (data + import template files only)
- apps/api/tests/test_odoo_craft_data.py (new)
Goal: Owner-listed values and lookup records exist as data, each record has an import template, and module data survives upgrades.
Steps:
1. K40/K41 from verbatim listed values only
2. K42 import template columns in form order
3. K43/K44 checks run inside the existing structural zip gate
Acceptance criteria:
- AC1: ORACLES K-15 passes unmodified
- AC2: Reinstalling the module over owner-edited data keeps the edits (sandbox test, GATE-A)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft_data.py`
Elite design notes: Rows register in the AS-CRAFT-APPLY `ROWS` registry; syntax only from the verified per-version catalog; every edit carries `craft:Kxx`; never a business record or field (ORACLES K-05).
Oracle tests: docs/build-plan/app-studio/ORACLES.md §K rows named in the ACs.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
