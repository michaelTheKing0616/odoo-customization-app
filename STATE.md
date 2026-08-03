# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **Wave 9 MON-2 shipped** — `entitlements.py` + seeded plan features, workspace subscriptions, Stripe/Paystack webhooks (fake mode), project lifecycle active|archived + slot gates, router feature deps, `useEntitlements()` hook.
- Gates: API pytest **659 passed**; entitlement suite 6 passed.
- Deferred: live Stripe checkout smoke (needs test keys), upgrade sheet UI, project-pass expiry job, Stripe bootstrap script.

## Next (prescribed wave order)
- **Wave 9 MON-3** — admin console + env bootstrap superadmin

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell provides nav chrome — connection pages keep content only.
- Diagnose errors: `ErrorNotice` + `reportApiError(..., { toast: true })` on mutations.
- Dev compose: always `-p odoo-custom-dev`; deploy: `-p odoo-custom-deploy`.
- Accounts auth: set `AUTH_MODE=accounts`; sessions via `oc_session` cookie (`credentials: include` on web fetch).
- Entitlements: bypass when `AUTH_MODE=off` or internal plan; `BILLING_MODE=fake` for webhook tests.
