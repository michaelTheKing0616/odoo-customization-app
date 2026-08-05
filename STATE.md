# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-05
- **Wave 15 GEN-1 → GEN-6 complete** + minor polish:
  - Reject inferred/installable reuse → auto-regen + `rejected_reuse_models` API.
  - Installable modules → structured `installable` decisions + wizard panel.
  - Pack `reuse_stock` processed before noun inference (pack metadata wins).
- Gate artifact: `docs/research/gen_fix_run_2026-08-05.json` (live Ollama).
- Tests: 35 passed (wave15 + reuse planner).

## Next
- None — committed and pushed on user request.

## Rule
- Code Studio = probe per connection, never hosting-tier assumption.
- Bulk execute paths require dry-run receipt when `dry_run_first` is set in safety registry.
- TRUST-7 integration: `TEST_APP_DB_RESTORE=1 RESTORE_TEST_DATABASE_URL=postgresql://…/odoo_custom_restore_drill`.
