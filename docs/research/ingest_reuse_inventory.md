# Ingest reuse inventory (ING-0)

**Date:** 2026-08-06 · **Vision decision:** `deferred` (qwen3-vl not installed; Tongyi license review before ship)

## Ollama runtime

| Model | Status |
|-------|--------|
| qwen3:8b | installed |
| qwen3:14b | installed |
| qwen3-vl:* | **not installed** — ING-4 text-PDF only until license cleared |

## Existing import entrypoints (reuse, do not rebuild)

| Path | Capability |
|------|------------|
| `apps/api/app/data_import.py` | CSV/XLSX parse, mapping, dry-run/commit batch create/upsert |
| `apps/api/app/routers/data_import.py` | REST preview/parse/commit + confirm phrase |
| `apps/web/src/app/connections/[id]/import/page.tsx` | Upload → Map → Validate → Commit wizard |
| `apps/api/app/bulk_suite/dedupe.py` | Exact/fuzzy duplicate scan + merge |
| `apps/api/app/invoicing_l10n.py` | l10n package detection — CoA guardrail |
| `apps/api/app/industry_seeds.py` | Seed CSV packs (partner/product exemplars) |
| `apps/api/app/image_import.py` | ZIP image bulk attach (out of universal ingest v1) |

## Wave 17 new surface

| Path | Role |
|------|------|
| `apps/api/app/ingest/extract_pdf.py` | Text PDF → LLM/deterministic structured extract |
| `apps/api/app/ingest/extract_vision.py` | Vision OCR gate — enable after `ollama pull qwen3-vl:8b` |
| `apps/api/app/ingest/layout_cache.py` | Repeat supplier fingerprint cache |
| `apps/api/app/ingest/interview.py` | Expert interview → IngestBatch |
| `apps/api/app/routers/ingest.py` | Multi-file job API |
| `apps/web/src/app/connections/[id]/ingest/page.tsx` | Review plan + dry-run UI |
