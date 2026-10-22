# AS-AUTHZ-DEFAULT: Turn profile v3 on by default

ID: AS-AUTHZ-DEFAULT
Title: Turn profile v3 on by default
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: XS (caps in budget.json). Stop at 80%.
Ledger IDs: P1-1-AC6
Depends on: AS-RELEASE-BARS
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 3 (C0 U1 F2 K0 V0 I0)
Context pack:
- handover L521 (P1-1 AC6)
- experiments/release_bars.md
File allow-list:
- apps/api/app/ai_conversation/studio_profile.py (default name only)
Goal: Default `INGENIUM_STUDIO_PROFILE` becomes v3 after the bars pass (or written exceptions) and Tope agrees.
Steps:
1. One-line default change
2. Restart is Tope's (`:8001` runs without --reload)
Acceptance criteria:
- AC1: P1-1 AC6 (adapted to v3; the legacy authorizer is superseded): "authorizer turned on by default only after AC4 passes and Tope agrees"
- AC2: Rollback = set the env var to legacy_v1 (documented in the PR text)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_studio_profile.py`
Gate: GATE-R input: Tope's written yes in the current message (INV-18).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
