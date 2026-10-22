# AS-GROUND-EXISTS: Know what already exists before adding anything

ID: AS-GROUND-EXISTS
Title: Know what already exists before adding anything
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-GROUND
Depends on: AS-GROUND-VIEWMAP, AS-COMPILE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C2 U1 F1 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.7 item 4, §6.3 (host_fit)
- docs/build-plan/cards/phase-3/AS-COMPILE.md
File allow-list:
- apps/api/app/ai_conversation/ground_exists.py (new)
- apps/api/app/ai_conversation/ledger_compile.py (one call site)
- apps/api/tests/test_ground_exists.py (new)
Goal: Reuse stock fields matched by label+type(+selection), earlier Ingenium `x_` fields and existing smart buttons; name the installed app that already does the ask; each reuse is an undoable assumption.
Steps:
1. Match on normalised label + type (+ selection values); ties go to the stock field
2. Earlier Ingenium fields: `x_` fields whose lineage marker is ours
3. Smart buttons: same target relation already in `button_box` → no new button
4. Write each reuse as an assumption with the owner's quote and an Undo
Acceptance criteria:
- AC1: ORACLES G-08, G-09 and G-10 pass unmodified
- AC2: Zero duplicate fields or smart buttons across the extension eval set
Test plan:
- `cd apps/api && uv run pytest -q tests/test_ground_exists.py`
Elite design notes: A wrong reuse is worse than a duplicate: below the match threshold, ask (Q stage) rather than reuse silently.
Oracle tests: docs/build-plan/app-studio/ORACLES.md: app-studio/ORACLES.md G-08, G-09, G-10
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
