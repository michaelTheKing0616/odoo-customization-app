# AS-CRAFT-SCORE: Measure craft live: every applicable idiom works on the sandbox

ID: AS-CRAFT-SCORE
Title: Measure craft live: every applicable idiom works on the sandbox
Status: todo
Phase: 3
Priority: P1
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT-EVAL
Depends on: AS-CRAFT-MODULE, AS-HARNESS
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.6 (last bullet), §9 craft score
- docs/build-plan/app-studio/ODOO_CRAFT.md
File allow-list:
- apps/api/evals/v2/craft_score.py (new)
- apps/api/evals/v2/tests/test_craft_score.py (new)
Goal: For each eval design, install it on disposable sandboxes and check every applicable K row by RPC; report a craft score per brief and per major next to the structure metrics.
Steps:
1. Applicable rows = the triggers in ODOO_CRAFT for that design
2. RPC checks: create a record (reference assigned), move its state, open a smart button action and count rows, post a chatter message, run each search filter, read pivot/graph/calendar views
3. Live lane and module lane scored separately; `craft_deferred` rows count as not applicable on the live lane and are listed
4. Results join the harness row (profile, fingerprint, major)
Acceptance criteria:
- AC1: Score = passing applicable rows / applicable rows, per brief and per major (unit test on a synthetic RPC transcript)
- AC2: The report lists every failing row with the RPC error in plain words
- AC3: Bar for release (AS-RELEASE-BARS): ≥ 95% per brief on the module lane, on 17-20
Test plan:
- `cd apps/api && uv run pytest -q evals/v2/tests/test_craft_score.py`
Gate: GATE-A (sandbox RPC). Then Tester PASS → Reviewer PASS (separate sessions).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
