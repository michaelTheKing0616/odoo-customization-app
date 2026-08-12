# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-12
- **Shipped:** Web UI + Expert + Docker for Wave 18 ELITE:
  - Wizard: ELITE workflow (lint, validate, download zip, promote, Ask Expert), route context sync
  - Next proxy: 660s for elite-autopilot, export-sandbox, validate-live, ai/draft*
  - Docker: deploy expert-cache volume + ELITE/Expert env; init-db `INSTALL_EXPERT_BRIDGE=1`; sync script
  - Playwright: elite validate/promote workflow test
- **Prior:** Staged `_llm_status` parity; library natural score 10.0; live gate script

## Next
- Production migration: see `docs/PRODUCTION-PLAN.md`
- Operator: `uv run python scripts/run_elite_live_gate.py` with Ollama up (optional sandbox)
- Cloud generation trial: Grok or other openai-compatible endpoint vs local qwen3 latency/SLO

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
