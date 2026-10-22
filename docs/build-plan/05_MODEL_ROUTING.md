# 05 Model routing

## Step 0: roster (21 Oct 2026)

Source: the model list Cursor exposes to this agent (`FACTS.md` L10). Cursor's picker, relative prices and context sizes were **not** observable from here, so the ranking is `[Inferred]` until the pilot measures it (DEC-030).

| Tier | Model | Role | Evidence |
|---|---|---|---|
| T0 | none (scripts) | run tests, `tsc`, lint, guards, `plan_lint`, contrast math, pixel diff, screenshots, counts, summaries, `STATE.md` updates | — |
| L1 | `grok-4.7-xhigh` (collapsed tier) | mechanical edits, docs, fixtures, redirects, copy swaps, mechanical spot review | DEC-030; `cursor-grok-4.6-high-fast` replaces it for **XS chores only** if the pilot shows an equal first-pass rate |
| L2 | `grok-4.7-xhigh` | pattern-following features, UI against a finished spec, test authoring from oracles, clear-repro bugs, Tester interpretation, most review | DEC-030 |
| L3 | `grok-4.7-xhigh` | write gate, money guard, auth/tenancy, `ir.access` shim, Alembic, canvas engine, App Studio stages, security review; always with Elite notes + locked oracles | DEC-030 |
| E1 | Opus 5.5 | escalation only: diagnose a card that failed at L3 and write a **fix note** (not code); E1 sample review at phase exit for score ≥ 10 cards; oracle review for score ≥ 10 cards | master §5 |
| E2 | Fable 5.x | plan authoring, Pack, zero-loss audit at each GATE-E, deadlock arbitration. Never a Worker | master §5 |

With one Grok model, L1/L2/L3 differ by **what the session is given**, not by model: L3 sessions get Elite design notes, locked oracles, a separate L3 Reviewer, and the guarded-path checklist. Reasoning effort is the model's own (`xhigh`); do not pick a cheaper model to save tokens on L3 work.

## Difficulty score (recorded on every card's Routing line)

Score 0–2 on each: **C** risk class (money, security, access, data loss, write gate) · **U** ambiguity · **F** breadth (files/modules) · **K** novelty/design · **V** version-matrix/live dependency · **I** irreversibility. Example: `Score: 6 (C2 U1 F1 K1 V1 I0)`.

| Score | Tier | Must carry |
|---|---|---|
| 0–2 | L1 | T0 checks; L1 spot review |
| 3–5 | L2 | Reviewer L2 (or L1 for mechanical) |
| 6–9 | L3 | Elite design notes; locked oracle tests; Reviewer L3 separate session |
| 10–12 | L3 | as 6–9, plus E1 oracle review before the Worker starts and an E1 sample review at phase exit |

**Guarded paths** (`plan_lint` `RISK_PATHS`: `write_gate`, `dry_run_middleware`, `dry_run_ledger`, `protected_`, `money`, `auth`, `tenan`, `ir_access_shim`, `alembic`): Worker L3 and Reviewer L3 whatever the score; E1 samples at phase exit.

## Card class → tier (default until the pilot replaces it)

| Card type | Worker | Tester | Reviewer |
|---|---|---|---|
| docs, decision | L1 | T0 | L1 spot |
| regression (test for fixed behaviour) | L2 | T0 | L2 |
| verify (measurement, no product change) | L2 | T0 | L2 |
| test (new suite or harness) | L2; L3 if guarded | T0 + L2 | same as Worker |
| build / rebuild | by score | T0 + L2 | by score |
| prove-live | L2; L3 if it writes through a guarded path | T0 (live harness) | L2/L3 |
| ui-spec | by score (usually L2) | T0 (plan_lint) | L3 for P1-10 flagship screens, else L2 |
| ui-build | L2; L3 for canvas/editor engines | T0 UI checks + L2 | L2 + GATE-B |
| oracle authoring (Oracle session) | L3, separate from Worker | T0 (tests are red) | E1 for score ≥ 10 |

## Oracle authoring (who writes the locked red tests)

- App Studio (`AS-*`) and Elevate (`EL-*`): from the elite-authored `ORACLES.md` files; the Oracle session transcribes them into test files.
- Every other card with score ≥ 6: a **separate L3 Oracle session** writes red tests from the card's verbatim ACs before the Worker starts; for score ≥ 10 an E1 session reviews them (DEC-046, default yes). The Worker may not edit them; a Worker who believes an oracle is wrong sends ESCALATE.

## Escalation ladder (never loop silently)

loop 1 fails → loop 2 with the Reviewer's CHANGES list → same card one tier up (L2→L3, or L3 + E1 fix note if already L3) → E1 fix note implemented by L3 → still failing → **stop and report to Tope**. De-escalate the next card of the same class as soon as one proves mechanical.

Escalation log (append to `STATE.md` § Escalations):

```
| date | card | from→to | trigger (loop n, failing AC) | E1 fix note path | tokens spent | outcome |
```

## Projected token share by tier (cost-weighted, `budget.json` units)

| Tier | Share | Why |
|---|---|---|
| T0 | ~0 | scripts |
| L1 | 10% | docs, chores, mechanical review |
| L2 | 45% | most Workers, Testers, Reviewers |
| L3 | 35% | guarded paths, App Studio, canvas engines, Oracle sessions |
| E1 | 7% | fix notes, oracle review ≥ 10, phase-exit samples |
| E2 | 3% | GATE-E zero-loss audits |

The Orchestrator reports actual share per tier at each GATE-E; if E1+E2 exceed 12%, the next phase's routing is reviewed with Tope.

## Grok fitness pilot (before Phase 1 G2)

Three low-risk cards with no live writes, each run three times (L1-style, L2-style, L3-style briefing; same model) in fresh sessions:

| Pilot | Card | Class |
|---|---|---|
| P-1 mechanical | `DOC-HANDOVER-ERRATA` | docs |
| P-2 UI component | `F1-CONTRAST-TOKENS` | build (UI) |
| P-3 test authoring for existing guard behaviour | `REG-HOSTGUARD` | regression |

Measure first-pass AC success, fix loops, tokens (Cursor usage view per session) and Reviewer verdict. Rule: use the lightest briefing that passes first time on 2 of 3 runs; record the result here and in `FACTS.md`. Also run P-1 once on `cursor-grok-4.6-high-fast`; if it passes with ≤ the same loops, that model takes XS chores. Re-run the pilot if the roster changes. Budget caps then become measured p90 × 1.2 per class (`budget.json` `_doc`).

Pilot results (21 Oct, one pass each, not the 3×3 matrix):

| Card | Pass | Loops | Reviewer | Label | Tokens |
|---|---|---|---|---|---|
| DOC-HANDOVER-ERRATA | first pass | 0 | APPROVE | [Done, code] | n/a |
| F1-CONTRAST-TOKENS | first pass after the allow-list gained `tokens.css` and `theme.css` | 0 | APPROVE | [Done, code] | n/a |
| REG-HOSTGUARD | first pass | 0 | APPROVE | [Done, code] | n/a |

L2-style and L3-style reruns were not run: the first pass already edited the files, and git is read-only, so a second session cannot rewrite the same card independently. P-1 on `cursor-grok-4.6-high-fast` was not run. No briefing comparison is claimed. The lightest-briefing rule stays unmeasured.
