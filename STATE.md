# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **Wave 7b + Wave 8 PROD-2/3 shipped** — TIER-6 EE view attrs + golden tests; UIX-6 overlay + reality check; UIX-7 website blocks/API/page; Alembic baseline; JobRunner seam; README in zips; dev compose project names.
- Gates: API pytest **645 passed**; web build ok; odoo-client EE golden 6 passed; module-generator README 2 passed.

## Next (prescribed wave order)
- **Wave 9 MON** — auth accounts, billing, admin console, pricing UX

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell provides nav chrome — connection pages keep content only.
- Diagnose errors: `ErrorNotice` + `reportApiError(..., { toast: true })` on mutations.
- Dev compose: always `-p odoo-custom-dev`; deploy: `-p odoo-custom-deploy`.
