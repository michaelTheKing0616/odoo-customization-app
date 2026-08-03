# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **Wave 9 MON-1 shipped** — `AUTH_MODE=accounts`: users/workspaces/memberships/sessions, argon2id + TOTP, cookie sessions, workspace-scoped connections, login/signup/verify/reset web pages, Alembic `a1b2c3d4e5f6`.
- Gates: API pytest **653 passed**; MON auth suite 25 passed; web build ok.
- OAuth: **[SKIPPED]** per card — env stub `OAUTH_PROVIDERS` only.

## Next (prescribed wave order)
- **Wave 9 MON-2** — Stripe/Paystack billing, `entitlements.py`, feature gating, project slots

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell provides nav chrome — connection pages keep content only.
- Diagnose errors: `ErrorNotice` + `reportApiError(..., { toast: true })` on mutations.
- Dev compose: always `-p odoo-custom-dev`; deploy: `-p odoo-custom-deploy`.
- Accounts auth: set `AUTH_MODE=accounts`; sessions via `oc_session` cookie (`credentials: include` on web fetch).
