# 01 TOKEN ECONOMY CHARTER

**Tope has a limited weekly token allocation shared across several projects. Waste is a defect.**

**Principle: deep reasoning internally; minimal sufficient output externally.** Efficiency never means shallow thinking or skipped verification. It means no padding, no repetition, no unnecessary work.

## ALWAYS
- Do only what the card requires. Nothing adjacent, nothing "while I'm here."
- Read only the files in the card's **context pack**. Any extra read needs a one-line logged reason; max 2 extra reads per card.
- Use targeted search (exact symbol, narrow path). No broad exploration, no re-reading what is already established.
- Reference handover sections by ID (e.g. "§4 P0-3 AC2"). Do not restate or re-quote them.
- Output **diffs, not files**. Do not regenerate unchanged code.
- Keep status messages ≤ 5 lines; handoff packets ≤ 15 lines.
- Do not narrate reasoning. No "thinking out loud." No explanations of obvious things.
- No alternative implementations unless there is a genuine architectural choice (then max 2 options, one recommended).
- Run the **narrowest test that proves the AC** (one file/one test). Full suites run only at phase exit or when the card says so.
- Test/log output is **summarised by script before any model reads it**: counts, failing test names, one-line cause. Never paste raw logs into context.
- Established facts live in `docs/build-plan/FACTS.md` (short, append-only, dated). Read it instead of re-deriving.
- Ask Tope only **blocking** questions, **batched into one message**, each with a recommended default. If it can be determined from files or the handover, determine it.
- Stop and report at **80% of a card's token budget** (do not silently overrun).
- If a task is finished, say so in one line and stop.

## NEVER
- Take screenshots, except at the UI checkpoints in `07_UI_EXCELLENCE_PROTOCOL.md` (baseline, after, final; one contact sheet per screen).
- Inspect unrelated files, repeat the problem statement, or add unrequested features, docs, or refactors.
- Spend tokens proving something one command can prove.
- Use a higher-tier model than the card's routing assigns. Escalate only on logged failure evidence (`05_MODEL_ROUTING.md`).

## Role economy
- **Elite planner (E1/E2):** think deeply once and write **dense, complete** artifacts (schemas, tables, pseudo-code, examples). Never pad. Complete does not mean long. The App Studio Pack budget is approved at G1.
- **Grok implementers (L1-L3):** read only the card and its context pack. Do not explore.

## Numbers live in `budget.json` (single source; edit one value to rescale)
- **Weekly allocation:** 40M cost-weighted tokens for this project (DEC-001, chosen 21 Oct `[Inferred]`). Unit = uncached input + output + 0.1 × cache-read input, summed from the Cursor usage view per role session. Agent sessions re-send their context on every tool call, so raw token counts are 5-10× this unit, and most of the extra is cheap cache reads.
- **Why 40M:** Phase 3 (30%) needs about 25 cards a week at a mostly-S/M mix: (worker 250k + tester 100k + reviewer 75k) × 25 ≈ 10.6M, which is about 27% of 40M. Every other phase fits inside its share at the same rates.
- **Class caps** (XS/S/M/L/XL × worker/tester/reviewer) and **phase weights** (`phase_weights`: weekly allocation minus reserve, split between at most two active phases in proportion to their weights; Stage 2 fix) are in `budget.json`. Reserve 15% every week. Never plan past 85%.
- **Typical card per class:** XS = rename, redirect, nav entry, copy swap. S = one component or function plus its test. M = a feature slice across 3-5 files. L = a pipeline stage or a gated write path. XL = elite design cards only; split anything else.
- **Recalibration:** the 3-card pilot logs real spend per role. `FACTS.md` records p50/p90 per class, and the caps in `budget.json` become p90 × 1.2. No card text changes, because cards name a class, not a number.

## Enforcement
- `.cursor/rules/00-token-economy.mdc` (alwaysApply, ≤ 40 lines). The draft is in `drafts/00-token-economy.mdc`. It is created after G0.
- Every card header: `TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: <class> (caps in budget.json). Stop at 80%.` `plan_lint` fails an unknown class.
- The token ledger in `STATE.md` records budget against spend per card, per role, and per phase. The Orchestrator updates it after every role.
- `plan_lint` fails a card that has no budget line.
