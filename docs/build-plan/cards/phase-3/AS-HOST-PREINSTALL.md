# AS-HOST-PREINSTALL: Stock host fit before install (wrong host fix)

ID: AS-HOST-PREINSTALL
Title: Stock host fit before install (wrong host fix)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-WRONGHOST
Depends on: AS-RETRIEVE, AS-COMPILE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F2 K1 V0 I0)
Context pack:
- handover §3.3 L242
- docs/specs/APP_STUDIO_FIX_PLAN.md 'Host-fit check'
- docs/build-plan/CODE_MAP.md rows: stock routing, install
File allow-list:
- apps/api/app/ai_conversation/host_fit.py (new)
- apps/api/app/ai_conversation/ledger_compile.py (call site only)
- apps/api/tests/test_host_fit.py (new)
Goal: A stock host is used only when its app is installed (or installable via the install step) and its required fields can be filled from the brief; otherwise the next candidate or a new model. Delivered as `host_fit(model, facts, snapshot) -> Fit`, passed into `ledger_compile.compile` in place of the default `installed_in_snapshot` (ORACLES C-16).
Steps:
1. Required fields from the snapshot; satisfiable if a ledger fact or a default covers each
2. Not installed but installable → install step (GND-MOD flow, one confirmation)
3. Neither → next candidate; none → new record model with a note
Acceptance criteria:
- AC1: generator_lure: fleet.vehicle.log.fuel rejected (needs vehicle) → Fuel Purchase model
- AC2: CRM brief before CRM install → install step, not res.partner
Test plan:
- `cd apps/api && uv run pytest -q tests/test_host_fit.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
