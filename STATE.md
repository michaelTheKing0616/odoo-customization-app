# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **Wave 9 MON complete** — billing jobs, feature flags, admin deactivate/flags, plan-diff downgrade UX, internal plan badge, bootstrap_stripe, lifecycle tests.
- **Wave 10 LAUNCH-1/2** — `scripts/launch_smoke.sh`, DEPLOY.md LAUNCH section, `docs/OPERATOR.md`.
- Gates: API **667 passed** (`-m "not integration"`); web build ok.

## Next
- Run `launch_smoke.sh` against a live deploy stack; optional live Stripe test-mode checkout smoke (needs test keys).
- Post-revenue deferrals: metered AI tier (`DEFERRALS.md`).

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell provides nav chrome — connection pages keep content only.
- Diagnose errors: `ErrorNotice` + `reportApiError(..., { toast: true })` on mutations.
- Dev compose: always `-p odoo-custom-dev`; deploy: `-p odoo-custom-deploy`.
- Accounts auth: `AUTH_MODE=accounts`; sessions via `oc_session` cookie.
- Entitlements bypass: `AUTH_MODE=off` or internal plan; upgrade via `/pricing` or `UpgradeSheet`.
