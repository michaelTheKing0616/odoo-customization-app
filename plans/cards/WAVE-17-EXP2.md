# Wave 17 — EXP2: Odoo Expert to 10/10 (benchmark rigor + draft-review companion)

Goal: same rigor for the Expert as GEN2-12 gives generation. Current state: EXP-1..5 +
REM-9 shipped (RAG, live grounding, ground-or-decline, 5-scenario live eval). 5 scenarios
is not a benchmark, and the Expert doesn't yet review drafts.

## EXP2-1 — Real benchmark: 40+ scenarios, decline adversarials, version pinning

- [x] Expand the eval set to ≥40 scored scenarios across: view arch how-tos, ORM/RPC
      usage, automations/server actions, access/record rules, troubleshooting (error-mode
      inputs), multi-version differences (17 vs 18 vs 19 API changes — answers must be
      version-pinned to the connection's major), and Odoo Online tier limitations.
- [x] Decline adversarials (≥8): questions whose answers are NOT in the corpus (invented
      modules, Enterprise-source internals, future versions) — Expert MUST decline with
      the honesty template, never fabricate. Scored as pass/fail.
- [x] Citation quality scoring: every factual answer cites ≥1 corpus chunk; cited chunk
      must actually contain the claim (string-overlap heuristic). Score in the harness.
- [x] Version-pinning tests: same question against a 17-connection and a 19-connection
      yields version-appropriate answers (e.g. attrs→invisible expression syntax change).
- [x] Live baseline recorded to `docs/research/expert_bench_<date>.json`: overall pass
      rate ≥85%, decline adversarials 100%, citation validity ≥90%. CI keeps the mocked
      fast subset; live run is the wave gate.

## EXP2-2 — Draft-review companion: the Expert runs the scorecard

The in-product version of the orchestrator's grading loop (GEN2-12 rubric).

- [x] "Expert review" action on any draft/project: runs `draft_scorecard` (GEN2-12),
      then the Expert generates a prioritized, cited review — top findings explained in
      plain language, each with a one-click "Apply fix" when the repair is deterministic
      (reuses critique repair machinery) or a suggestion card when not.
- [x] Domain-fit commentary grounded in the connection: Expert cross-references the
      draft's reuse plan against installed modules ("You built x_expense but hr_expense
      is installed — consider linking instead") using the AI-9 overlap sources.
- [x] Review verdict follows COPY_GUIDE honesty labels; never claims a fix it didn't
      apply (repairs vs suggestions split, same contract as the critique block).
- [x] Wizard integration: after a draft scores <9, banner offers "Ask the Expert to
      review and fix" → runs review → applies accepted deterministic fixes → rescores;
      show before/after score.
- [x] Tests: mocked review flow (score → findings → apply → rescore improves)
- [x] Playwright e2e for the wizard scorecard banner path (`e2e/wizard-scorecard.spec.ts` — chip via Callout `testId`, expert review before/after score)

GATES: API suite 0 failed; live bench artifact + live review artifact under
`docs/research/`; PROGRESS.md Wave 17 + STATE.md updated. No commit until user approves.

DO NOT: hosted LLMs (still deferred); fabricate bench results (fixture-labeled only for
the CI subset); Enterprise source in the corpus.
