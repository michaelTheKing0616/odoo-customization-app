# AS-BRIEFS-NEW: Twenty or more new messy briefs with gold

ID: AS-BRIEFS-NEW
Title: Twenty or more new messy briefs with gold
Status: todo
Phase: 3
Priority: P1
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-8.5-BRIEFS
Depends on: none
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 3 (C1 U1 F1 K0 V0 I0)
Context pack:
- handover L925
- docs/build-plan/app-studio/00_PACK.md §9 sets
File allow-list:
- apps/api/evals/v2/dev3/*.md
- apps/api/evals/v2/dev3/*.gold.yaml
- apps/api/evals/v2/dev3/README.md
Goal: ≥ 20 briefs: Pidgin, Yoruba, Hausa, Igbo mixes; voice-note run-ons; negation; extension of existing apps; very short; very long; money; injected instructions. Gold DRAFT with spans, for Tope's review (DEC-026).
Steps:
1. Write blind to failure cases (don't open holdout_fresh)
2. Each brief has gold with spans and a style tag
3. README lists the strata counts
Acceptance criteria:
- AC1: ≥ 20 briefs covering every stratum named in handover L925
- AC2: Every gold span verbatim (reuse test_gold_spans)
Test plan:
- `cd apps/api && uv run pytest -q evals/v2/tests/test_gold_spans.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
