# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-06
- **Wave 17 deferred items shipped** (except qwen3-vl install): ING-3 LLM column map, ING-4 PDF text + vision gate + layout cache (`e1f2a3b4c5d6`), ING-5 dedupe, ING-7 Playwright e2e, ING-8 mail_notrack + live smoke, ING-9 Expert interview path.
- Gates: `test_ingest_*.py` **30 passed**; alembic drift green; Slice A live smoke green on docker-19 when reachable.
- **Final ING-4 step for operator:** `ollama pull qwen3-vl:8b` then `INGEST_VISION=ollama` in `.env`.

## Next
- Operator: pull qwen3-vl when license cleared; scan PDF smoke.
- Slice B/C: full pricelist.item multi-tier CSV fixtures; fuzzy dedupe merge UX.

## Rule
- Code Studio = probe per connection, never hosting-tier assumption.
- Bulk execute paths require dry-run receipt when `dry_run_first` is set in safety registry.
