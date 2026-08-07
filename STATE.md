# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-07
- **GEN2-10/11/12 + EXP2-1/2 follow-ups complete (no commit — awaiting user approval):**
  - Playwright `wizard-scorecard.spec.ts` green (Callout `testId` fix on scorecard chip)
  - Live Ollama background job → `docs/research/gen2_run_2026-08-07.json` gate **pass** (`llm_partial`, score **9.88**, 962s)
  - Full API gate (final re-run): **1066 passed**, 2 skipped, 0 failed (~33 min)
  - Expert + GEN2 targeted: 47 passed; Playwright 1 passed
- Prior: post-critique, production shape, scorecard, expert bench/review artifacts

## Next
- User approval → commit GEN2/EXP2 batch
- EU Tongyi agreement still human/legal only

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
- No commit until user approves this wave
