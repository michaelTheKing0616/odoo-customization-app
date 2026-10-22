# AS-UPGRADES: Suggested upgrades a senior developer would offer (U01-U12), opt-in only

ID: AS-UPGRADES
Title: Suggested upgrades a senior developer would offer (U01-U12), opt-in only
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-CRAFT-UPGRADES, AS-UPGRADE-ALL
Depends on: AS-CRAFT-APPLY, AS-PROMOTE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/ODOO_CRAFT.md 'Suggested upgrades'
- docs/build-plan/app-studio/00_PACK.md §6.5
- docs/build-plan/app-studio/ORACLES.md K-16
File allow-list:
- apps/api/app/ai_conversation/odoo_craft/upgrades.py (new)
- apps/api/tests/test_odoo_craft_upgrades.py (new)
Goal: Every matching upgrade is offered (DEC-044): ranked by fit, top 3 inline, the rest under "More suggestions (n)" with per-item add and "Add all"; each has one plain sentence; nothing is built until the owner clicks, then Promote applies it with no LLM call.
Steps:
1. Offer rules exactly as the U table, from ledger shape + snapshot (installed / installable apps)
2. Never offer an upgrade the owner excluded (left_out not_wanted) or a module the hosting lane cannot install
3. Click → `owner_override` → re-run C, D, A (same path as Promote)
4. The owner-facing screen for this card is built in UI-APPSTUDIO-BUILD to the 07_UI_EXCELLENCE_PROTOCOL bar (Tope: the absolute best design on every screen); this card ships the API contract and plain copy only.
Acceptance criteria:
- AC1: ORACLES K-16 passes unmodified
- AC2: An offered upgrade adds 0 elements until clicked (property)
- AC3: Every upgrade whose trigger matches appears in `suggestions` (inline ∪ more = all matches; none dropped by count), ranking is deterministic, and no suggestion touches an excluded or future topic (property)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_odoo_craft_upgrades.py`
Elite design notes: Upgrades are suggestions, not craft: they never count as invented because nothing exists until the owner asks.
Oracle tests: docs/build-plan/app-studio/ORACLES.md §K rows named in the ACs.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
