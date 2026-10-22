# AS-HARNESS: Eval harness: isolation, seeds, versions, cost meter, ledger recording

ID: AS-HARNESS
Title: Eval harness: isolation, seeds, versions, cost meter, ledger recording
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P1-2; AS-8.5-HARNESS; REL-7.1
Depends on: AS-PROFILE, AS-FRESH-BYPASS
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C2 U1 F1 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §9
- docs/build-plan/CODE_MAP.md rows: eval harness
- handover §8.5 'Eval harness' bullet (L924)
File allow-list:
- apps/api/evals/v2/score.py
- apps/api/evals/v2/replay.py
- apps/api/evals/v2/metrics.py (cost fields only)
- apps/api/evals/v2/tests/test_harness.py (new)
Goal: Every run is fresh (new session, `--fresh`), on a named disposable DB, with `seed=hash(brief_id,repeat)` where honoured, and records profile + fingerprint, prompt version, model id, tokens and cost.
Steps:
1. `score.py --profile <name> --k N --split dev,dev2` sets `INGENIUM_STUDIO_PROFILE` for the API it starts (port 8102; never 3002, 8001, 8002, 8012 or any INV-11 port) and refuses `holdout_fresh` unless `EVAL_UNSEAL=yes`
2. Per run, write {brief_id, repeat, seed, profile, fingerprint, prompt_versions, model_ids, llm_calls, input/output tokens, usd (price table in one dict), latency, outcome kind}
3. `INGENIUM_RECORD_DIR` captures raw ledger samples (v3) and pre-authorizer designs (legacy) for replay
4. `replay.py --profile v3` replays V/C/A offline from recordings at 0 LLM calls
5. Re-derive the handover's authorizer replay numbers (invented 0.739 → 0.162, false folds 0.234) from the existing legacy recordings with `replay.py`, and log them in PROGRESS.md as the X2 baseline; if they differ, the re-derived numbers win (they are [From handover §8.2] until then)
Acceptance criteria:
- AC1: A run against `holdout_fresh` without `EVAL_UNSEAL=yes` exits non-zero before any request
- AC2: Two runs with the same profile and recordings replay to byte-identical scores
- AC3: Every result row has profile, fingerprint, tokens, usd and outcome kind (schema test)
Test plan:
- `cd apps/api && uv run pytest -q evals/v2/tests/test_harness.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
