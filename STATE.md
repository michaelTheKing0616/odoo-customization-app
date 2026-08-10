# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-10
- **Shipped:** Semantic apply-readiness (Top 3 + related); retail_supermarket pack source hygiene; regression fixture `draft_supermarket_semantic_corrupted_2026-08-10.json`; wizard scorecard shows dimension breakdown + finding labels; `.env.example` / `settings.py` docs; transition sync skips terminal outgoing edges.
- **Gate:** apply_readiness **52 passed**; wave15 pack + wave16 green.

## Prior (2026-08-08)
- GEN2-13 + follow-up — live apply prep, reuse wiring, promo compute, wizard reuse UI.
- Gate artifact `docs/research/gen2_13_run_2026-08-08.json` — **9.82/10**.

## Next
- Re-enrich saved supermarket draft (or restart API) so new passes run on live JSON.
- Optional: live LLM supermarket regen (Ollama) for gate artifact refresh.

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
