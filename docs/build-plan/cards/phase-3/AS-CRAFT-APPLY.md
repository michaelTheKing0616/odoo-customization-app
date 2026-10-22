# AS-CRAFT-APPLY: Craft stage D: apply senior-developer idioms to every compiled design

ID: AS-CRAFT-APPLY
Title: Craft stage D: apply senior-developer idioms to every compiled design
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT
Depends on: AS-CRAFT-CATALOG, AS-COMPILE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 8 (C2 U1 F2 K2 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.6
- docs/build-plan/app-studio/ODOO_CRAFT.md
- docs/build-plan/app-studio/ORACLES.md §K (K-01, K-02, K-04..K-07)
- apps/api/app/ai_design_compile.py (statusbar L102, views L119-144, menus L311-347, mixins L406/L460; read, then reuse)
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/apply.py (new)
- apps/api/app/ai_design_compile.py (only to accept the craft fields AppDesign now carries: search filters, list sums/optional/decorations, button box, tracking; no behaviour change for designs without them)
- apps/api/tests/test_odoo_craft.py (new)
Goal: `apply(design, voted, snapshot, major, lane) -> AppDesign`: pure, applies K01-K14, K17 and the live half of K09 per ODOO_CRAFT triggers, with `craft:Kxx` lineage; lists M/L! rows in `craft_deferred` on the live lane.
Steps:
1. One function per K row, each `(design, voted, snapshot, catalog) -> list[CraftEdit]`, registered in a `ROWS` registry keyed by K id; triggers exactly as the ODOO_CRAFT table. Later craft cards (AS-CRAFT-FIELDS, -UX, -COMMS, -DATA) add rows in their own files and only register them
2. Syntax only from `catalog_v{major}`; a row not Verified is skipped + logged (K-06)
3. Merge edits deterministically (row order K01 → K19); never add a model or a business field (K-05 property)
4. Extend `ai_design_compile` to render the new view features per major; designs without craft fields render byte-identically to today
Acceptance criteria:
- AC1: ORACLES K-01, K-02, K-04, K-05, K-06, K-07 pass unmodified
- AC2: Golden: legacy drafts without craft fields compile byte-identically (3 recorded drafts)
- AC3: Every view D emits passes the existing view validators for its major (no `attrs`, `<tree>` on 17 / `<list>` on 18+, xpath by name)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft.py tests/test_ai_design_compile.py`
Elite design notes: docs/build-plan/app-studio/00_PACK.md §6.6. Craft is keyed on ledger shape (fact kinds, rules, links), never on industry words; a pack lookup here is a defect (K-09). If `tests/test_ai_design_compile.py` does not exist, use the narrowest existing test that imports `ai_design_compile` and name it in the Tester packet.
Oracle tests: docs/build-plan/app-studio/ORACLES.md §K.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
