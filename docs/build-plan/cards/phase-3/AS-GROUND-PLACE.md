# AS-GROUND-PLACE: Place by meaning, verify by re-reading Odoo

ID: AS-GROUND-PLACE
Title: Place by meaning, verify by re-reading Odoo
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: AS-GROUND
Depends on: AS-GROUND-VIEWMAP, AS-CRAFT-APPLY
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U1 F2 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.7 item 3
- apps/api/app/live_schema_context.py L644-683 (`resolve_form_anchor`)
- apps/api/app/view_engine.py (existing name-based xpath builder; reuse, do not fork)
File allow-list:
- apps/api/app/ai_conversation/ground_place.py (new)
- apps/api/tests/test_ground_place.py (new)
Goal: Owner placement words resolve against labels and containers; output name-based xpath on the host's primary view; after apply, re-read and roll back any node that landed elsewhere.
Steps:
1. Resolve phrase → anchor by label, then technical name, then alias; containers by page/group label
2. Emit `//field[@name]`, `//page[@name]`, `//div[@name='button_box']`, `//header` only; unnamed anchor → nearest named ancestor (reason logged)
3. Never `replace` on stock; never positional; inherit the primary view of that type
4. Post-apply: `combined_arch` re-read; node not in the planned container → roll back that view, `left_out` with a plain reason
5. Live: 3 extension eval briefs on disposable 17-19 sandboxes (20 when built). Live checks run only on disposable `ingenium_*` sandboxes for 17, 18, 19 (and 20 once its stack exists); drop what you create (INV-03).
Acceptance criteria:
- AC1: ORACLES G-06, G-07 and G-11 pass unmodified
- AC2: Live: 100% of placed nodes in the planned container on every major run
- AC3: No positional xpath and no `replace` in any emitted view (property)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_ground_place.py`
Elite design notes: Pack §6.7. Placement is deterministic code over the view map; the LLM only supplies the owner's phrase, quoted.
Oracle tests: docs/build-plan/app-studio/ORACLES.md: app-studio/ORACLES.md G-06, G-07, G-11
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
