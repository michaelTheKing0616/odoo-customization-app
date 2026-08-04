# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-04
- **Follow-ups shipped:**
  - `Card` forwards div props (`data-testid`) — pricing e2e uses `pricing-tier-*` + `project-pass` again.
  - `test_restore_drill_on_copy_database` — row-count drill (baseline restore → delete 1 `odoo_connections` row → `restore_app_db.sh` → count restored); **passed** on `odoo_custom_restore_drill`.
- **Prior operator evidence (still valid):** Playwright 7/7 live overlay + TRUST-7 manual drill; `docs/vision-verify/overlay-editor-live.png`.

## Next
- None blocking — optional backlog from prior waves only.

## Rule
- Code Studio = probe per connection, never hosting-tier assumption.
- Bulk execute paths require dry-run receipt when `dry_run_first` is set in safety registry.
- TRUST-7 integration: `TEST_APP_DB_RESTORE=1 RESTORE_TEST_DATABASE_URL=postgresql://…/odoo_custom_restore_drill`.
