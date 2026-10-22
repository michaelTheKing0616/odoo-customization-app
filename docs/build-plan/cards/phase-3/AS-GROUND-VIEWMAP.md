# AS-GROUND-VIEWMAP: View map: the real structure of each host view, per major

ID: AS-GROUND-VIEWMAP
Title: View map: the real structure of each host view, per major
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: AS-GROUND
Depends on: AS-GROUND-WIRE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U2 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.7 item 2
- apps/api/app/live_schema_context.py L437-555 (`_view_field_order`, `_packet_model`)
- packages/odoo-client/src/odoo_client/schema_graph.py L103 (`combined_arch` = `get_view`)
File allow-list:
- apps/api/app/view_map.py (new)
- apps/api/app/live_schema_context.py (add `view_maps` to PacketModel; render cap)
- packages/odoo-client/src/odoo_client/schema_graph.py (add read-only `view_inherit_chain`)
- apps/api/tests/test_view_map.py (new)
- apps/api/tests/fixtures/view_map/ (new; recorded arches per major)
Goal: Per host model and view type: anchor tree (header, button_box + its smart buttons, named groups, pages, chatter), each field's container path, label, widget, invisible/readonly, selection values, and owning module + view xml-id.
Steps:
1. Parse the combined arch with the existing XXE refusal (`arch_has_xxe`); build `ViewMap{anchors, fields, smart_buttons}`
2. Ownership: `ir.ui.view` search_read on model + type (inherit_id, mode, priority) joined to `ir.model.data` for xml-ids [Inferred API, verify on each major]
3. Labels and help from the database are untrusted: run `classify_injection`; render only inside the fence
4. Render under a named constant cap per model (`VIEW_MAP_RENDER_CHAR_CAP`), truncating deterministically with an "n more omitted" line
5. Record fixtures for `sale.order`, `res.partner`, `crm.lead`, `account.move` forms on disposable 17/18/19 sandboxes; 20 when its stack exists. Live checks run only on disposable `ingenium_*` sandboxes for 17, 18, 19 (and 20 once its stack exists); drop what you create (INV-03).
Acceptance criteria:
- AC1: ORACLES G-04 and G-05 pass unmodified
- AC2: Existing packet tests stay green (field order unchanged)
- AC3: Render stays under the cap on every fixture
Test plan:
- `cd apps/api && uv run pytest -q tests/test_view_map.py`
Elite design notes: Version facts (17 `<tree>`, 18+ `<list>`, chatter markup per major) come from the recorded fixtures, never from memory; any fact not seen in a fixture is [Inferred] and skipped.
Oracle tests: docs/build-plan/app-studio/ORACLES.md: app-studio/ORACLES.md G-04, G-05
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
