# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-05
- **Wave 14 UIF shipped (UIF-1 → UIF-4):**
  - `InstanceIdentity` once in top bar; CapabilityProbePanel quiet row only; Overview identity chips removed.
  - Bulk Suite duplicate six-section block + Housekeeping duplicate recompute removed.
  - Sidebar exact Overview active match; collapsible nav + localStorage; unique icons; Operations hub `/operations`.
  - Overview tabs (Overview / Models / Develop), primary actions, first-run card, playbook accordions.
  - Playbook panels → ErrorNotice + Retry; journal HealthCheckBanner removed (health filter tab).
  - Gates: `pnpm lint` 0 errors · `pnpm test` 101 passed · `pnpm build` OK.
  - Playwright vision-verify sweep: spec updated (+ operations-hub); run locally (webServer timeout in agent env).

## Next
- Run `pnpm exec playwright test e2e/vision-verify-sweep.spec.ts` locally to refresh `docs/vision-verify/` screenshots.
- Commit Wave 14 when user approves.

## Rule
- Code Studio = probe per connection, never hosting-tier assumption.
- Bulk execute paths require dry-run receipt when `dry_run_first` is set in safety registry.
- TRUST-7 integration: `TEST_APP_DB_RESTORE=1 RESTORE_TEST_DATABASE_URL=postgresql://…/odoo_custom_restore_drill`.
