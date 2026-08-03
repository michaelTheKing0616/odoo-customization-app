# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **Wave 9 MON-4 shipped** — registry-driven `/pricing`, upgrade sheet + `FeatureGatedError`, billing settings, project slot UX, terms/privacy stubs, landing tier strip.
- Gates: API pytest 661 passed (prior); web build ok; e2e `pricing.spec.ts` added.

## Next
- Wave 9 complete — polish deferred items (live Stripe smoke, internal StatusPill in shell, project-pass expiry job) or next wave per `plans/PROGRESS.md`.

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell provides nav chrome — connection pages keep content only.
- Diagnose errors: `ErrorNotice` + `reportApiError(..., { toast: true })` on mutations.
- Dev compose: always `-p odoo-custom-dev`; deploy: `-p odoo-custom-deploy`.
- Accounts auth: `AUTH_MODE=accounts`; sessions via `oc_session` cookie.
- Entitlements bypass: `AUTH_MODE=off` or internal plan; upgrade via `/pricing` or `UpgradeSheet`.
