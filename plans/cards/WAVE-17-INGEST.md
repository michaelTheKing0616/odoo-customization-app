# Wave 17 — INGEST: Universal document → Odoo data pipeline

Shared context: `plans/UNIVERSAL_INGESTION_PIPELINE.md`. Reuse `data_import.py`,
`bulk_suite/dedupe.py`, `invoicing_l10n.py`. Canonical schema: `IngestBatch`.
Order: ING-0 → ING-1 → (ING-2‖ING-3‖ING-4) → ING-5 → ING-6 → ING-7 → ING-8 → ING-9.

---

## ING-0 — License + runtime inventory (gate before vision)

TASK: Confirm local models and legal posture for OCR; document dimensions/paths.

CHECKLIST:
- [x] `ollama list` records qwen3:8b / qwen3:14b (already expected); note whether
      `qwen3-vl:*` is present — **do not pull large VL models until license note filed**.
- [x] Short note in `MEMORY.md` or this card: Tongyi Qianwen vs Apache 2.0 Qwen3 —
      EU deploy needs separate agreement; no competing multimodal training. Decision:
      `vision_tier: local_ok` (2026-08-06 product-owner unlock; EU commercial still gated).
- [x] Inventory existing import entrypoints (`data_import` routes, import UI) in 10 lines
      under `docs/research/ingest_reuse_inventory.md` (no code rewrite).

GATE: Decision recorded; inventory file exists; no VL dependency merged if
`eu_blocked` without product owner override.

DO NOT: Pull 30B VL; send sample customer docs to cloud OCR.

RETURN: ≤8 lines + decision.

---

## ING-1 — Canonical schema + job skeleton

TASK: Define `IngestBatch` types + persistence + orchestrator stub that runs empty stages.

INPUT: `data_import.py`, `db_models.py`, alembic pattern.

CHECKLIST:
- [x] Pydantic/dataclass models: `IngestJob`, `IngestFile`, `IngestTable`, `IngestRef`,
      `IngestPlan` in `apps/api/app/ingest/` (new package).
- [x] Table `ingest_jobs` (JSON payload + status) + Alembic revision `d0e1f2a3b4c5`.
- [x] `run_pipeline(job_id)` stub: stages 1–6 callable.
- [x] Unit tests: serialize/deserialize round-trip; unknown doc_type rejected by allowlist.

GATE: `uv run pytest tests/test_ingest_schema.py -q` green.

DO NOT: Implement PDF OCR or UI wizard yet.

RETURN: ≤8 lines + migration id.

---

## ING-2 — Classifier (closed vocabulary)

TASK: Stage 1 — classify upload → `doc_type` + confidence.

INPUT: ING-1 schema; `llm_provider.py`; Document 4 show-don’t-tell style.

CHECKLIST:
- [x] Closed vocab: `coa | bom | product_catalog | customer_list | vendor_list |
      price_list | employee_roster | opening_trial_balance | inventory_count | other`.
- [x] Structured path: header/column signals (no LLM if score ≥ threshold).
- [x] Ambiguous path: LLM JSON classify with 1–2 structural cues per type; temp ≤0.2.
- [x] Below threshold → `needs_user_confirm: true` (never silent guess).
- [x] Tests: fixture headers for partner/product/CoA-like → correct types; garbage → other.

GATE: `uv run pytest tests/test_ingest_classify.py -q` green.

DO NOT: Open-ended “what is this document?” without vocab.

RETURN: ≤8 lines.

---

## ING-3 — Extract CSV/XLSX → IngestTable (wire existing)

TASK: Stage 2 for structured files — wrap `data_import`, no new parser.

INPUT: `data_import.py`, ING-1, ING-2.

CHECKLIST:
- [x] `extract_tabular(file) -> IngestTable[]` using `parse_tabular` + header alias hints.
- [x] LLM column map **only** when headers miss aliases (reuse field meta).
- [x] Multi-file job: N CSVs → N tables on one `IngestJob`.
- [x] Tests: seed-pack CSV → `res.partner` / `product.template` tables with natural keys.

GATE: `uv run pytest tests/test_ingest_extract_tabular.py -q` + one real seed-pack file.

DO NOT: Reimplement CSV reader; touch PDF.

RETURN: ≤8 lines.

---

## ING-4 — Extract PDF / vision (Slice C enabler; after ING-0)

TASK: Stage 2 for PDF/scans — type-specific extractors emitting `IngestTable`.

INPUT: ING-0 decision; ING-1; optional `qwen3-vl` if allowed.

CHECKLIST:
- [x] Text PDF path (pypdf already in deps): extract text → LLM structured extract per
      `doc_type` schema (CoA / BoM nested / price list with qty breaks).
- [x] BoM: **two-pass** (parent + lines); nested sub-assemblies as child tables / refs —
      never silently flatten multi-level BoMs.
- [x] Price list: require qty-break + validity fields in schema (forbid single collapsed price).
- [x] Employee: org fields only; strip/refuse wage-like columns with warning.
- [x] Vision path behind `INGEST_VISION=off|ollama` (default off); **final step:** `ollama pull qwen3-vl:8b`.
- [x] Layout template cache table: `(source_fingerprint, doc_type) → exemplar mapping`
      for repeat suppliers (few-shot).
- [x] Tests: fixture PDF text (synthetic) for CoA + BoM nested; wage column stripped.

GATE: pytest fixtures green; vision off still passes CI.

DO NOT: Cloud OCR; invent fiscal accounts; write payroll fields.

RETURN: ≤8 lines + vision flag status.

---

## ING-5 — Map + cross-reference (live schema + dedupe)

TASK: Stage 3 — map rows to **this instance’s** fields; fuzzy match live + batch.

INPUT: `data_import._field_meta`, `bulk_suite/dedupe.py`, Expert grounding patterns.

CHECKLIST:
- [x] Per target model: load required/readonly/selection via existing field meta.
- [x] Resolve m2o / UoM against live `uom.uom` (fail soft with gap, don’t assume “kg”).
- [x] Call dedupe scan (exact + fuzzy) against live IDs **and** other tables in job.
- [x] Produce `IngestRef` unresolved list for missing products/partners/accounts.
- [x] Tests: fake client — required field missing; UoM missing; batch-internal product match.

GATE: `uv run pytest tests/test_ingest_map.py -q` green.

DO NOT: Static generic schema tables that ignore custom fields / l10n.

RETURN: ≤8 lines.

---

## ING-6 — Dependency graph + topo-sort

TASK: Stage 4 — whole-batch commit order (the novel piece).

INPUT: ING-1 tables + refs.

CHECKLIST:
- [x] Build digraph: edge A→B means “A must exist before B”.
- [x] Default edges from doc_type/model registry (contacts→invoices skipped until those
      models appear; products→bom lines; coa→opening TB; categories→products; products→pricelist).
- [x] Topo-sort; unrelated components → `parallel_ok: true`.
- [x] Missing deps → `plan.gaps[]` (no silent placeholders).
- [x] Tests: synthetic batch order; bom line ordering; gap surfacing via refs.

GATE: `uv run pytest tests/test_ingest_order.py -q` green.

DO NOT: Rely on upload order; auto-create bare stub products.

RETURN: ≤8 lines.

---

## ING-7 — Validate / dry-run / review UI

TASK: Stage 5 — human review surface + dry-run without writes.

INPUT: import page patterns; ING-5/6 plan; advanced confirm.

CHECKLIST:
- [x] API: `POST /connections/{id}/ingest/jobs/{id}/dry-run` → per-table preview counts.
- [x] UI: `/connections/[id]/ingest` — doc type+confidence, commit order, gaps, dry-run/commit.
- [x] Financial confirm: CoA / opening TB require typed phrase (reuse advanced-action pattern).
- [x] CoA: surface l10n alignment warnings via `invoicing_l10n` (country package present?).
- [x] Playwright or component test: order visible; gap blocks commit button.

GATE: API dry-run tests + UI smoke; no write without confirm.

DO NOT: Auto-post journals; skip review for “high confidence”.

RETURN: ≤8 lines.

---

## ING-8 — Commit + idempotent re-upload

TASK: Stage 6 — batched write in plan order; delta on re-upload.

INPUT: `data_import.dry_run_or_commit`, `bulk_suite` context flags, ING-6 plan.

CHECKLIST:
- [x] Commit follows `IngestPlan` order; parallel_ok groups may run concurrently (cap N=2).
- [x] Context: `tracking_disable` / `mail_notrack` where client supports.
- [x] Natural-key upsert default for re-upload (SKU, account code, email/VAT).
- [x] Job log: counts created/updated/failed on `IngestCommitLog`.
- [x] Live smoke (optional mark): docker-19 partners+products+pricelist 3-file job (`test_ingest_slice_a_live.py`).
- [x] Tests: fake client batch order assertions; second upload → updates not dupes.

GATE: `uv run pytest tests/test_ingest_commit.py -q` green; live smoke logged if run.

DO NOT: Per-row RPC loops; chatter flood; duplicate on re-upload.

RETURN: ≤8 lines + artifact path if live.

---

## ING-9 — Expert interview → same pipeline (optional)

TASK: No-document path — structured Q&A builds `IngestTable`s, then Stages 3–6.

INPUT: `expert/ask.py`, ING-1 schema.

CHECKLIST:
- [x] Interview mode endpoint: questions for expense categories / product vs service /
      starter contacts → emit `IngestBatch` with `source: interview`.
- [x] Hand off to existing map/order/dry-run/commit — **zero duplicate commit path**.
- [x] Test: fake answers → batch with ≥1 product table + ≥1 partner table.

GATE: pytest green; UI link “Build starter data with Expert” on ingest page.

DO NOT: Separate write path; invent CoA outside l10n guidance.

RETURN: ≤8 lines.

---

## Slice A acceptance (MVP ship)

After ING-8 (CSV-only path sufficient):

- [x] Upload 3 CSVs (customers, products, pricelist) unordered → plan shows products before
      pricelist items; dry-run then commit on docker-19 or fake-client CI.
- [x] Re-upload updated products → upsert by SKU, no duplicates.
- [x] PROGRESS.md Wave 17 Slice A marked done (live smoke green when Odoo 19 up).

## Production hardening (post ING-9 — 2026-08-06)

- [x] Opening TB: draft JE on Opening journal only — never auto-post / never raw move.line invent
- [x] CoA align vs live/l10n codes + `allow_coa_as_is` financial confirm
- [x] inventory_count commit blocked until dedicated stock path
- [x] notify_mode: `batch_summary` | `individual`
- [x] Live m2o resolve + fuzzy/exact dedupe; VAT/VIES via base_vat when installed
- [x] Image + scanned PDF vision path; review UI confidence/override/commit log
- [x] BoM product/UoM live ID resolve in map; employee org allowlist

## CONTINUE gap-close (2026-08-06)

- [x] True CoA remap: `suggest_coa_remaps` / `apply_coa_remap` + `POST .../coa-remap` + UI auto-align
- [x] inventory_count dedicated path: `stock.quant` `inventory_quantity` + `action_apply_inventory`
- [x] UoM resolve category-aware (`_resolve_uom` + product category hint; Odoo 19 `relative_uom_id`)
- [x] Persist prefs: `ingest_prefs_json` on connection + GET/PATCH `/ingest/prefs` + UI save default
- [x] Vision enable runbook: `docs/research/ingest_vision_enable.md`

## Operator / external finish (2026-08-06)

- [x] Alembic `f2a3b4c5d6e7` applied (ingest_prefs_json)
- [x] `l10n_us` + `mrp` + `hr` installed on docker-19
- [x] Slice B live: `tests/test_ingest_slice_b_live.py` (CoA align + opening TB dry path)
- [x] Slice C/D live: `tests/test_ingest_slice_c_live.py` (BoM parent dry-run + employee org-only)
- [x] Local `INGEST_VISION=ollama` + `qwen3-vl:8b` pull (see STATE for smoke result)
- [ ] **EU Tongyi Qianwen commercial agreement** — human/legal only; cannot be agent-completed

EU commercial vision marketing still needs Tongyi Qianwen agreement (owner/legal).
