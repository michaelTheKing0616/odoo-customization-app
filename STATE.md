# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-08
- **Shipped:** GEN2-13 + follow-up — live apply prep (`prepare_spec_for_live_apply`, `record_rules` RPC), reuse wiring (`sale.order`/`account.move`), promo→line discount compute, wizard auto-wired reuse UI + JSON paste import, gate artifact refresh.
- **Gate:** `docs/research/gen2_13_run_2026-08-08.json` — **9.82/10**, validators green, `gate_pass: true`, features block confirms reuse/promo/live prep.

## Draft #6 verdict (post GEN2-13)
- Raw cached draft capped at **6.0** (validator failures) — no longer self-scores 10.
- After post-critique + production-shape: **9.82/10**, all validators green, depth ok.

## Next
- Optional: live LLM supermarket regen (Ollama) to replace fixture6 replay in gate artifact.
- EU Tongyi agreement still human/legal only

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
