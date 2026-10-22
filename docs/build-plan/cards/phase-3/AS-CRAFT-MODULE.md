# AS-CRAFT-MODULE: Module lane: a senior-grade installable module from the same design

ID: AS-CRAFT-MODULE
Title: Module lane: a senior-grade installable module from the same design
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT; AS-CRAFT-LANE
Depends on: AS-CRAFT-APPLY, AS-CRAFT-SMART
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 9 (C2 U1 F2 K2 V1 I1)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.6 (lanes)
- docs/build-plan/app-studio/ODOO_CRAFT.md rows K03, K11, K14, K15, K16, K19
- docs/build-plan/app-studio/ORACLES.md K-08
- apps/api/app/module_spec_codec.py `export_draft_module_zip` (L450) and apps/api/app/ai_structural_zip_gate.py (read, then extend)
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/module_templates/ (new: Jinja2 templates for sequence default, count compute, total compute, constraints, QWeb report, TransactionCase test)
- apps/api/app/module_spec_codec.py (render craft rows when present; drafts without them export byte-identically)
- apps/api/tests/test_odoo_craft_module.py (new)
Goal: The module lane renders every applicable K row, including the Python ones, from fixed reviewed templates; it passes the structural zip gate and installs on the sandbox.
Steps:
1. Templates per K03/K15/K14/K16/K19, each parameterised only by validated technical names (no free text into Python; names checked against `^[a-z_][a-z0-9_]*$`)
2. Security per major: CSV + record rules on 17-19, `ir.access` data on 20
3. Manifest: minimal `depends` from the design's hosts, LGPL-3, `application: True` for new apps
4. One TransactionCase test per module: install, create a record, check the reference, walk the states, check the smart button count
5. Sandbox install on 17-20 through the existing sandbox path (never prod; promote stays human)
Acceptance criteria:
- AC1: ORACLES K-08 passes unmodified
- AC2: bakery_ng and Customer Health modules install on disposable sandboxes 17, 18, 19 (and 20 when its stack exists) and their generated tests pass (`build_test_enable_argv`)
- AC3: Drafts without craft rows export byte-identically to today (golden zip listing)
- AC4: No template accepts an owner string inside Python code (static test over the templates)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft_module.py`
- Sandbox install per AC2 (GATE-A)
Elite design notes: This is generated Python, so it sits under Option A: sandbox before any install, promote is human, never prod. The Python is fixed templates reviewed once, never LLM-written, which is why it is allowed without the authoring gate; any template change needs an L3 Reviewer. Owner text reaches only XML strings (labels, help), escaped.
Oracle tests: docs/build-plan/app-studio/ORACLES.md K-08; static template-injection test.
Gate: GATE-A (sandbox installs). Then Tester PASS → Reviewer PASS (separate sessions).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
