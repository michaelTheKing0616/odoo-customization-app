# EL-SET-SIGNIN: Single sign-on and your sessions list

ID: EL-SET-SIGNIN
Title: Single sign-on and your sessions list
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-SET, SEC-AUTH-SESSION
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 8 (C2 U1 F2 K1 V1 I1)
Context pack:
- handover §2.8, §3.14 (named approvers need sign-in)
- apps/api/app/auth.py
- apps/api/app/oauth_service.py
File allow-list:
- apps/api/app/auth_oidc.py (new)
- apps/api/app/auth.py
- apps/api/tests/test_auth_oidc.py (new)
- apps/web/src/app/settings/security/ (new)
Goal: Optional OIDC single sign-on (Authlib, BSD) and a screen to list and revoke your sessions. Password hashing, session cookies and TOTP MFA are SEC-AUTH-SESSION (handover §6.1 AC2); this card builds on them.
Steps:
1. OIDC client secret encrypted at rest with the existing key; issuer + client id in settings, never in code
2. Sessions list shows device, place (coarse) and last seen; Revoke ends the session server-side
3. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: OIDC login with a mismatched state or nonce is refused
- AC2: revoked session can't call the API
- AC3: no secret in logs (scrub test)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_auth_oidc.py`
Elite design notes: Guarded path (auth): L3 Worker and a separate L3 Reviewer (INV-14). Never roll custom crypto.
Oracle tests: docs/build-plan/elevate/ORACLES.md: EL-SET-SIGNIN-1 OIDC callback with wrong state refused; EL-SET-SIGNIN-2 revoked session → 401
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
