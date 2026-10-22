# AS-CRAFT-COMMS: Work around the record: activities, overdue, email, print (K36-K39)

ID: AS-CRAFT-COMMS
Title: Work around the record: activities, overdue, email, print (K36-K39)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT-PLUS
Depends on: AS-CRAFT-APPLY
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md rows K36-K39
- docs/build-plan/app-studio/ORACLES.md K-14
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/comms.py (new)
- apps/api/tests/test_odoo_craft_comms.py (new)
Goal: Activity types from the owner's reminder rules, overdue filters and decorations, and email/print only when the owner asked.
Steps:
1. K36/K37 rows from rules and date + lifecycle facts
2. K38 only when a cited owner quote says send/email/share; K39 extends K16
3. No outbound email is ever sent by App Studio itself (INV-18): templates and buttons only
Acceptance criteria:
- AC1: ORACLES K-14 passes unmodified
- AC2: No K38 element without a cited owner quote (property)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft_comms.py`
Elite design notes: Rows register in the AS-CRAFT-APPLY `ROWS` registry; syntax only from the verified per-version catalog; every edit carries `craft:Kxx`; never a business record or field (ORACLES K-05).
Oracle tests: docs/build-plan/app-studio/ORACLES.md §K rows named in the ACs.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
