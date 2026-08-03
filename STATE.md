# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **EXP-3 shipped** (`b1e876a`): `POST /api/expert/ask` — ground-or-decline, citations, tier-1 refusal.
- **EXP-4 shipped:** `eval_set.jsonl` (41 items) + `test_expert_eval.py` harness; baseline
  `docs/research/expert_eval_baseline_2026-08-03.md` (CI 41/41 pass).
- Tier-1 fix: dotted model token detection (`sign.request`, `sale.subscription`).
- Gate: `test_expert_eval` 2 passed (+1 live skip); expert suite 40 passed total.

## Next
- **EXP-5** — Expert UX surfaces (requires UIX-3 shell) (`plans/PROGRESS.md`).

## Rules
- Expert eval gate: `uv run pytest tests/test_expert_eval.py -q`
- Re-run baseline on chunking/retrieval/model changes.
- Expert ask: `POST /api/expert/ask` requires `AI_ASSIST`.
