# Expert eval baseline — 2026-08-03

Deterministic CI harness run (`tests/test_expert_eval.py`) against fake provider mocks.
Re-run on any change to chunking, retrieval, prompts, or model routing.

## Summary

| Metric | Score |
|--------|-------|
| Items | 41 |
| Pass rate | **100%** (41/41) |
| Grounding rate | 82.9% |
| Citation presence | 73.2% |
| Decline correctness | 100% (5/5 decline items) |

## Category pass rates

| Category | Pass rate | Count |
|----------|-----------|-------|
| doc_grounded | 1.000 | 16 |
| instance_grounded | 1.000 | 5 |
| protected_caution | 1.000 | 5 |
| should_decline | 1.000 | 5 |
| version_diff | 1.000 | 5 |
| bulk_routing | 1.000 | 5 |

## Gate command

```bash
cd apps/api && uv run pytest tests/test_expert_eval.py -q
```

## Live eval (optional)

```bash
EXPERT_EVAL_LIVE=1 AI_ASSIST=ollama uv run pytest tests/test_expert_eval.py::test_expert_eval_live_report -s
```

Live mode scores a stratified sample against the real model; not hard-fail in CI.

## Notes

- Eval set: `apps/api/tests/expert_eval/eval_set.jsonl`
- MASTER reference bundle not yet ingested — doc-grounded items use fixture chunks in CI
- Tier-1 detection uses full dotted model tokens (`sign.request`, `sale.subscription`, etc.)
