# Odoo Expert — Build Plan Progress (gap audit vs. external brief)

> **2026-08-06:** Audited against the "Odoo's Native AI" build brief (Phases 0–8).
> **Do not rebuild** what Wave 5 EXP already shipped — see `plans/cards/WAVE-5-EXP.md`.

## Summary

| Phase | Status | Evidence |
|-------|--------|----------|
| 0 — Environment | **DONE** (pre-existing) | Ollama + qwen3; MiniLM via `ai_rag.py`; Postgres `expert_chunks` (JSON embeddings, not pgvector — see deviation) |
| 1 — Ingestion | **DONE** | `app/expert/ingest.py`, `fetcher.py`, `chunker.py`; `test_expert_ingest.py` |
| 2 — Live introspection | **DONE** | `app/expert/grounding.py`; `test_expert_grounding.py` |
| 3 — Retrieval & ranking | **DONE** (minor deviation) | `app/expert/retrieval.py` — vector + Jaccard fallback, version filter, source boost; no separate keyword-boost layer on embeddings |
| 4 — Generation | **DONE** | `app/expert/ask.py`; routing 8b/14b; ground-or-decline; `test_expert_ask.py` |
| 5 — Guardrails | **DONE** | PCM/protected modules in ask pipeline; adversarial tests in `test_expert_ask.py` |
| 6 — UX surfaces | **DONE** | `ExpertPanel`, `ExplainThisButton`, error mode — EXP-5; Playwright specs |
| 7 — Eval harness | **DONE** | 41-item `tests/expert_eval/eval_set.jsonl`; baseline `docs/research/expert_eval_baseline_2026-08-03.md`; 28 expert tests green |
| 8 — Competitive parity | **DONE** (this session) | `docs/research/expert_vs_odoo_native_ai_2026-08-06.md` |

## Deviations from external brief (documented, not bugs)

1. **pgvector:** Not used. Embeddings stored as JSON in `expert_chunks.embedding_json`; cosine in Python (`ai_rag.py`). Sufficient at current scale; pgvector is a future scale item only.
2. **Hybrid keyword boost:** Brief asks vector + exact-term boost; we use embedding OR Jaccard fallback (not additive hybrid). Acceptable — Jaccard handles identifier-heavy queries when embeddings off; optional enhancement deferred.
3. **Voice transcription:** Not built — accepted gap (text-only Qwen3 stack).
4. **Community Q&A scrape:** Ingestion path exists (`EXPERT_COMMUNITY_SOURCE=dir`) but scraper explicitly out of scope per WAVE-5.

## Gate commands (re-verify anytime)

```bash
cd apps/api && uv run pytest tests/test_expert_eval.py tests/test_expert_ask.py tests/test_expert_grounding.py tests/test_expert_ingest.py -q -m "not integration"
ollama list   # qwen3:8b + qwen3:14b expected locally
```

## Last verified

- **2026-08-06:** Expert test suite 28 passed (1 skipped live-only); eval set 41 lines; alembic + GEN2-8 on master.
