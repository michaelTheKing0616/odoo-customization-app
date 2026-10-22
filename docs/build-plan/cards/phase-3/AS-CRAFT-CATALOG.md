# AS-CRAFT-CATALOG: Verify the Odoo craft catalog on 17, 18, 19 and 20

ID: AS-CRAFT-CATALOG
Title: Verify the Odoo craft catalog on 17, 18, 19 and 20
Status: todo
Phase: 3
Priority: P1
Type: verify
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT
Depends on: none
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U2 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md (the 19 rows)
- skills/odoo-rpc-gate.md
- apps/api/app/ai_design_compile.py L95-150 (existing view idioms, read only)
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/__init__.py (new)
- apps/api/app/ai_conversation/odoo_craft/catalog_v17.py, catalog_v18.py, catalog_v19.py, catalog_v20.py (new; data only)
- apps/api/tests/test_odoo_craft_catalog.py (new)
- apps/api/evals/v2/craft_probe.py (new; the RPC probe script)
- docs/build-plan/app-studio/ODOO_CRAFT.md (Verified/Rejected column only)
Goal: Every catalog row has exact per-version syntax read from real stock Odoo, not from memory.
Steps:
1. For each major, create a disposable `ingenium_craft_<ver>` database on the existing local stack (never a new port; drop it after), install `sale`, `crm`, `project`, `calendar`
2. `craft_probe.py`: `get_views` on `sale.order`, `crm.lead`, `project.task`, `res.partner` (form, list/tree, kanban, search, calendar, pivot, graph, activity); extract chatter syntax, button box, statusbar, smart button, list sum/optional/decoration, kanban template name, search filter/group-by shapes; read `ir.sequence`, `base.automation` trigger fields, and `ir.model.access`/`ir.rule` vs `ir.access` field lists
3. Write the findings as data into `catalog_v{ver}.py`; mark each ODOO_CRAFT row Verified (with the stock view it was read from) or Rejected (with why)
4. Answer the L! questions with evidence: can a live custom field carry a count/total compute on each major, and what does it require
Acceptance criteria:
- AC1: Every ODOO_CRAFT row is Verified or Rejected on all four majors, each citing a stock view or model read on that major
- AC2: The probe is re-runnable and writes the same catalog files (golden diff)
- AC3: All four `ingenium_craft_*` databases are dropped at the end (Tester lists DBs)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft_catalog.py` (schema of the catalog data; offline)
- `cd apps/api && uv run python evals/v2/craft_probe.py --majors 17,18,19,20` (live, sandbox only)
Elite design notes: This is the "perfect understanding of how Odoo works under the hood" requirement turned into evidence. Read stock views; never copy Enterprise or Studio code (INV-12). Odoo 20's stack is specified but not built (AGENTS.md): if no v20 stack runs, mark v20 rows Pending and raise it in the Tester packet instead of guessing.
Oracle tests: Catalog schema test; the probe's golden output.
Gate: GATE-A (live sandbox RPC). Then Tester PASS → Reviewer PASS (separate sessions).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
