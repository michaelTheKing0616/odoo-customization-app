# Expert live run transcripts — 2026-08-03 (REM-9)

Structured captures from `/api/expert/ask` for regression and prompt tuning.
CI uses deterministic eval (`test_expert_eval.py`); these artifacts document live-shaped output.

## Runs

| File | Question | Notes |
|------|----------|-------|
| `run_01_xpath_inherit.json` | View inheritance xpath basics | doc_grounded |
| `run_02_access_error.json` | AccessError on res.partner write | instance + error paste |
| `run_03_protected_tiers.json` | What are the protected module tiers? | project / MASTER_REFERENCE |

## Re-record (live)

Requires docker Odoo 19 + Ollama (`AI_ASSIST=ollama`):

```bash
EXPERT_RUNS_LIVE=1 ./scripts/record_expert_runs.sh
```

Or pytest:

```bash
EXPERT_RUNS_LIVE=1 uv run pytest tests/test_expert_runs_live.py -s -m integration
```
