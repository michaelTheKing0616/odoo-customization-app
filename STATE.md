# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-05
- **Wave 16 GEN2 + draft cache complete** (uncommitted — awaiting user approval):
  - GEN2-1→7 + honest gaps (Alembic, enrich jobs, root menu groups, live gate script).
  - **Fix:** LLM timeout now falls back to domain pack (`pack_fallback`) instead of 502 crash.
- Gate artifact: `docs/research/gen2_run_2026-08-05.json` — **deviation** (live run 947s; Ollama timed out → `pack_fallback`, 10 models, no top-level `error`).
- Tests: 18 wave16 + 47 targeted; **full gate `-m "not integration"`: 987 passed** (32 min).
- Alembic: `c9d0e1f2a3b4_ai_draft_cache.py` added; local `upgrade head` blocked by pre-existing oauth migration duplicate column (stamp/fix separately).

## Next
- User approval → commit.
- Optional: `alembic stamp` / fix oauth migration drift; re-run gate when Ollama is warm for `llm_full`/`llm_partial`.

## Rule
- Code Studio = probe per connection, never hosting-tier assumption.
- Bulk execute paths require dry-run receipt when `dry_run_first` is set in safety registry.
- TRUST-7 integration: `TEST_APP_DB_RESTORE=1 RESTORE_TEST_DATABASE_URL=postgresql://…/odoo_custom_restore_drill`.
