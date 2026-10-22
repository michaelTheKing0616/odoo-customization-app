# AS-CRAFT-FIELDS: Fields that behave like a senior developer set them up (K20-K27)

ID: AS-CRAFT-FIELDS
Title: Fields that behave like a senior developer set them up (K20-K27)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT-PLUS
Depends on: AS-CRAFT-APPLY
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md rows K20-K27
- docs/build-plan/app-studio/ORACLES.md K-10, K-11
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/fields.py (new)
- apps/api/tests/test_odoo_craft_fields.py (new)
Goal: Defaults, delete policy, copy flags, indexes, link domains, widgets, owner-worded help and reference search on every owner field.
Steps:
1. One row function per K20-K27, registered in `ROWS`
2. Help text = the shortest owner quote that created the field (Redactor-restored, escaped)
3. Live lane: dynamic defaults (today, current user) go to `craft_deferred` and are built only in the module lane (DEC-042 resolved: module route)
Acceptance criteria:
- AC1: ORACLES K-10 and K-11 pass unmodified
- AC2: No help text contains words outside the cited owner quote (property)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft_fields.py`
Elite design notes: Rows register in the AS-CRAFT-APPLY `ROWS` registry; syntax only from the verified per-version catalog; every edit carries `craft:Kxx`; never a business record or field (ORACLES K-05).
Oracle tests: docs/build-plan/app-studio/ORACLES.md §K rows named in the ACs.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
