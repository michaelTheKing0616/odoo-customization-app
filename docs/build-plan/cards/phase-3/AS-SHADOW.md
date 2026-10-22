# AS-SHADOW: Shadow week: v3 beside legacy on real sessions

ID: AS-SHADOW
Title: Shadow week: v3 beside legacy on real sessions
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-SHADOW; AS-FIX-5
Depends on: AS-CONTRACT-EVAL
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F2 K2 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §10 X5
- DEC-009
File allow-list:
- apps/api/app/ai_conversation/v3_shadow.py (new)
- apps/api/app/routers/ai_studio.py (call shadow after legacy returns; never awaits it)
- apps/api/tests/test_v3_shadow.py (new)
Goal: For real sessions, run v3 in a background thread after legacy answers; log verdict summaries only (no owner-visible change).
Steps:
1. Log: brief hash, counts (built/folded/suggested), structure hash, timings; never brief text or record values (INV-17)
2. Kill switch in the profile
3. X5 measure (Pack §10): when the owner installs the legacy design, log the installed model set's structure hash and names hashed, next to v3's built / folded / suggested sets for the same session; compute v3 misses (installed by the owner, folded or absent in v3) and v3 extras (built by v3, never installed) per session
Acceptance criteria:
- AC1: Owner response time unchanged (test: shadow raising or sleeping does not delay the route)
- AC2: No brief text in shadow logs (scrub test)
- AC3: The X5 rates are computable from the logs alone (fixture with 3 synthetic sessions → expected miss and extra rates)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_v3_shadow.py`
Elite design notes: Real-session data is customer data: log counts and hashes only. The shadow never writes to Odoo and never calls install paths.
Oracle tests: A shadow worker that raises and one that sleeps 60 s: the route returns in normal time both ways; the log contains no text from the fixture brief.
Gate: GATE-A: Tope's go to start the week (DEC-009). Then the normal card gate.
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
