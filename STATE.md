# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-06
- **Operator/external finish (then commit+push):**
  - Alembic head `f2a3b4c5d6e7` (ingest_prefs_json) applied
  - docker-19: installed `l10n_us`, `mrp`, `hr`
  - Slice B/C/D live: `test_ingest_slice_b_live.py` + `test_ingest_slice_c_live.py` green
  - `ollama pull qwen3-vl:8b` done; `INGEST_VISION=ollama` in local `.env`
  - Vision smoke: `check_vision_model` ready + `extract_image_with_vision` OK
  - Odoo 19 UoM: map uses `relative_uom_id` (no `category_id`); BoM CSV → nested tables + defaults
- Gates: `pytest -k ingest` **57+** passed; Slice B/C integration 3 passed
- **Cannot complete:** Tongyi Qianwen EU commercial agreement (human/legal only)

## Next
- Owner: file Tongyi agreement before marketing vision OCR in EU
- Optional: live vision OCR on a real invoice scan (smoke used blank PNG)

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
