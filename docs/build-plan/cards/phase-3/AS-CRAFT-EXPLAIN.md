# AS-CRAFT-EXPLAIN: Explain every idiom in one plain sentence, and let the owner switch it off (Q4)

ID: AS-CRAFT-EXPLAIN
Title: Explain every idiom in one plain sentence, and let the owner switch it off (Q4)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT-QUALITY
Depends on: AS-CRAFT-APPLY
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md Q4
- handover Appendix C (glossary)
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/explain.py (new)
- apps/api/tests/test_odoo_craft_explain.py (new)
Goal: Each K row has one owner sentence ('Added a reference number so you can find orders by number'); each craft edit can be switched off through `owner_override`.
Steps:
1. One sentence per K row, filled with the record's owner label
2. Switch-off re-runs D and A with that row excluded for that record
3. The owner-facing screen for this card is built in UI-APPSTUDIO-BUILD to the 07_UI_EXCELLENCE_PROTOCOL bar (Tope: the absolute best design on every screen); this card ships the API contract and plain copy only.
Acceptance criteria:
- AC1: Every registered K row has a sentence (test fails on a missing one)
- AC2: Jargon guard passes on all sentences
- AC3: Switch-off survives regenerate
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft_explain.py`
Elite design notes: Plain language is an invariant (INV-04): no 'mixin', 'compute', 'xpath' or 'IR' in owner copy.
Oracle tests: docs/build-plan/app-studio/ORACLES.md §K rows named in the ACs.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
