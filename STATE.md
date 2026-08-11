# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-11
- **Shipped:** 10/10 apply-readiness passes — statusbar transition chains (`approved→closed`), adjustment header dedupe, `REASON/` sequence prefix + help sync, branch form notebook + Operations menu, manager-only branch record rules, go-live review notes; scorecard allows statusbar terminal chains; stock.picking integrity fix.
- **Gate:** apply_readiness **55 passed**; wave16 green.

## Prior (2026-08-08)
- GEN2-13 + follow-up — live apply prep, reuse wiring, promo compute, wizard reuse UI.
- Gate artifact `docs/research/gen2_13_run_2026-08-08.json` — **9.82/10**.

## Next
- Re-enrich saved supermarket draft (or restart API) so new passes run on live JSON.
- Optional: live LLM supermarket regen (Ollama) for gate artifact refresh.

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
