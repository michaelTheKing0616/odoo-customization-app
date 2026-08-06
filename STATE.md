# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-06
- **GEN2-8 complete:** root payload leak validator; statusbar_visible; _llm_status finalize; form semantic grouping (>10 fields); drop redundant x_*_name; global prompt → x_country_id on branch; slug stop-words; comprehensive workflow automation floor.
- Gates: `test_wave16_gen2.py` 31 passed; full `-m "not integration"` 1008 passed / 1 alembic suite-order flake (passes in isolation); live gate pass → `gen2_run_2026-08-06.json`.
- **Alembic flake fixed:** revision imports need `migration_helpers` on sys.path — `alembic.ini` prepend + absolute config in tests; removed module-level `DB_MIGRATIONS=auto` pollution.
- Committed GEN2-8 (user approved).

## Next
- Wave 16 close-out / next wave card selection.
- Re-run full `-m "not integration"` gate if needed before deploy.

## Rule
- Code Studio = probe per connection, never hosting-tier assumption.
- Bulk execute paths require dry-run receipt when `dry_run_first` is set in safety registry.
- TRUST-7 integration: `TEST_APP_DB_RESTORE=1 RESTORE_TEST_DATABASE_URL=postgresql://…/odoo_custom_restore_drill`.
