# AS-CRAFT-SMART: Smart buttons both ways, including on stock records

ID: AS-CRAFT-SMART
Title: Smart buttons both ways, including on stock records
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT
Depends on: AS-CRAFT-APPLY
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md rows K09, K18
- docs/build-plan/app-studio/ORACLES.md K-03
- apps/api/app/ai_craft_smart_buttons.py, apps/api/app/ai_stock_host_smart_buttons.py (existing; read, then reuse)
- apps/api/app/view_engine.py module docstring (xpath by name, never positional, never `replace`)
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/smart_buttons.py (new)
- apps/api/tests/test_odoo_craft_smart.py (new)
Goal: Every one2many / reverse many2one, including links from stock hosts (res.partner, product, employee), gets a smart button; it is applied automatically under v3 instead of as an opt-in chip.
Steps:
1. Enumerate relations from the compiled design + snapshot; one button per (source record, related records)
2. Custom → custom: button in the parent's button box; stock → custom: inherited view of the stock form anchored by `//div[@name='button_box']` via `view_engine`
3. Live lane: window action with the filtered domain and the default link in context (no count); module lane: count field from the fixed compute template (AS-CRAFT-MODULE)
4. Reuse the existing modules' relation-detection logic by import; do not change their legacy behaviour
Acceptance criteria:
- AC1: ORACLES K-03 passes unmodified
- AC2: bakery_ng design → buttons Order → Lines and Contact → Orders; salon_voice → Contact → Appointments
- AC3: No positional xpath and no `replace` in any emitted view (grep test)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft_smart.py`
Elite design notes: Smart buttons on stock records are the clearest sign of senior Odoo work; they must never break the stock form. Anchor only on named nodes that AS-CRAFT-CATALOG verified per major.
Oracle tests: docs/build-plan/app-studio/ORACLES.md K-03.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
