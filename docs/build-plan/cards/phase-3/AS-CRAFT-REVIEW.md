# AS-CRAFT-REVIEW: Senior Odoo reviewer: one bounded LLM pass that may only propose catalog rows (Q2, experiment X7)

ID: AS-CRAFT-REVIEW
Title: Senior Odoo reviewer: one bounded LLM pass that may only propose catalog rows (Q2, experiment X7)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT-QUALITY
Depends on: AS-CRAFT-APPLY, AS-UPGRADES, AS-CRAFT-SCORE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U2 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md Q2
- docs/build-plan/app-studio/00_PACK.md §3 (call count), §7 (deadlines)
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/review.py (new)
- apps/api/tests/test_odoo_craft_review.py (new)
- apps/api/evals/v2/experiments/x7_craft_review.md (new; results only)
Goal: An optional call reads the built design (no owner free text beyond the fenced brief) and returns `[{row_id, target, reason}]`; code applies only K rows whose trigger holds and turns U ids into chips; everything else is dropped and logged.
Steps:
1. Schema-constrained output (AS-DECODE); row ids must exist in the catalog
2. Runs only when time remains before the soft deadline; counts toward Pack §3's call budget
3. X7: paired run with and without the reviewer on dev + dev2; keep it only if Tope's rating rises with craft score and invention unchanged
Acceptance criteria:
- AC1: A reviewer output naming a new model or an unknown row is fully dropped (unit test)
- AC2: X7 result written with paired CIs; profile default stays off until X7 passes
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft_review.py`
Elite design notes: AI proposes, code authorises (INV-13): the reviewer can never add structure, only point at catalog rows.
Oracle tests: docs/build-plan/app-studio/ORACLES.md §K rows named in the ACs.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
