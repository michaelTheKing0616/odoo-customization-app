# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-07
- **Apply-readiness v3 + follow-up (uncommitted):** billing demotion, Monetary header computes, depth/x_task restore, reuse link_only, scorecard gate; **sync `/enrich-draft`** now shares `finalize_enriched_draft` with async jobs; wizard shows score after reuse/enrich; sandbox smoke test added (skips without Docker). Tests: **67 passed**, 1 skipped (fixture5 sandbox).
- Prior: GEN2/EXP2 (`d38e90a`).

## Next
- User approval → commit apply-readiness v1–v3 + follow-up batch
- Re-save live supermarket draft (reuse toggle or Retry enrichment) to pick up all passes
- Run `pytest tests/test_apply_readiness.py::test_fixture5_sandbox_install_smoke` with Docker for full ERP gate
- EU Tongyi agreement still human/legal only

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
- No commit until user approves this wave
