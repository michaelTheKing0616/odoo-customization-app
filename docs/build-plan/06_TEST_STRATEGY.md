# 06 Test strategy

Cards name only the layers that apply, with exact commands. Execution is always T0 (scripts); models author or interpret.

## Commands (repo-verified paths; never use ports 3002, 8001, 8002, 8012, 5433, 5436, 8069-8073, 11434)

| Layer | Command |
|---|---|
| API unit/contract | `cd apps/api && uv run pytest -q <file>` |
| API random order | `cd apps/api && uv run pytest -q -p randomly <file>` (needs `pytest-randomly`, MIT; not installed on 21 Oct, added as a dev dependency by B0-GREEN after Tope's yes at Phase 0 G2, DEC-047) |
| Web unit | `cd apps/web && pnpm vitest run <file>` |
| Types / lint | `cd apps/web && pnpm typecheck && pnpm lint` |
| E2E | `cd apps/web && pnpm playwright test <spec>` against an isolated build: own `distDir`, port 3100 (never a bare `next build`) |
| Live 17–20 | the L2-HARNESS runner (created by card L2-HARNESS) on disposable `ingenium_*` DBs; Odoo 20 once O20-01 exists |
| Plan | `python3 scripts/plan_lint.py all` |

## Layers and when they run

| Layer | Scope | Runs |
|---|---|---|
| Unit | validators, compilers, guards, pure functions | every card, narrow |
| Contract | API schemas/OpenAPI, module-export structure | card touches an API or exporter |
| Property/fuzz | AI-output validators, compilers, parsers: malformed model output never reaches compile (Hypothesis, MPL-2.0; not installed on 21 Oct: the first card needing it adds it as a dev dependency, DEC-047) | card touches a parser/validator |
| Idempotency | every plan type run twice on a disposable DB; the second run writes 0 records | every write card |
| Undo round-trip | change → undo → DB equals snapshot | every write card on an A5-gated page |
| E2E | key flows in a real browser | UI cards; phase exit |
| Live 17–20 | one harness; version matrix table in PROGRESS | gates and nightly; prove-live cards |
| Security | tenancy sweep over all routers, red-team pack, SSRF, headers, rate limits, secrets-in-cache grep, licence/SBOM, audit-chain tamper | CI/PR and each GATE-E |
| A11y/contrast | axe + Tope's rule (light-ish background → dark ink), light and dark | UI cards; phase exit (all routes) |
| Perf | INP < 200 ms at 4× CPU, long tasks < 50 ms, LCP < 2 s, CLS < 0.05, JS/route budget, virtualisation | UI cards (affected routes); phase exit (all) |
| Hydration | console crawl of every route | UI cards (affected routes); phase exit |
| Visual regression | Playwright snapshots per route/state, light/dark, 390 and 1440 | UI cards |
| AI eval | App Studio fresh sessions, hierarchical bootstrap CIs, `--fresh` honoured, no cache hits | AI changes; weekly |
| Oracle | locked input → expected cases (`app-studio/ORACLES.md`, `elevate/ORACLES.md`, card Oracle tests) | every card that has them; Worker may not edit |
| Metamorphic | paraphrase, filler, typos, reorder, language swap do not change App Studio IR beyond tolerance | AI changes; weekly |
| Regression | one test per "fixed but worth regression tests" item and per built touch | permanent (REG-* cards) |

## Rules (the Reviewer rejects a card that breaks one)

1. A test must be able to fail: the Reviewer asks "would this pass if the feature were broken?" A test that would is rejected.
2. No test reads `~/.ingenium`, hits the dev App DB, calls real Vertex/LLMs (unless marked `live_ai`, skipped by default), or touches a non-`ingenium_` DB or a non-loopback host.
3. No order dependence: random or reverse order must pass. GATE-E runs the full suites twice in random order.
4. Flaky = defect: quarantine with a new card, never ignore or retry-until-green.
5. Every "[Done, code]" handover item has a prove-live card, so "unproven" never silently becomes "done".
6. `evals/v2/holdout_fresh/` is sealed: no test or tuning reads its gold (INV-16).
7. Economy: narrow tests per card; full suites at phase exit; live harness at gates/nightly. T0 writes a summary (counts, failing names, one-line cause); models read the summary, not raw logs.
8. Live runs create only `ingenium_*` DBs and drop them; `assert_isolated()` and the docker guard are never weakened (INV-03).

## Phase-exit suite (GATE-E, T0)

```
cd apps/api && uv run pytest -q -p randomly                           # twice, different seeds
cd apps/web && pnpm vitest run && pnpm typecheck && pnpm lint          # twice (vitest --sequence.shuffle)
cd apps/web && pnpm playwright test                                    # isolated build
python3 scripts/plan_lint.py all                                       # 0 errors, 0 uncovered for the phase
<L2 harness> --matrix 17,18,19,20                                      # from Phase 2 on
```
