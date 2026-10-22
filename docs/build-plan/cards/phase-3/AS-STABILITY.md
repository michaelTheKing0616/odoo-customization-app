# AS-STABILITY: Cluster and vote samples (self-consistency)

ID: AS-STABILITY
Title: Cluster and vote samples (self-consistency)
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: AS-FAIL-B
Depends on: AS-LEDGER-SCHEMA, AS-ROBUST-FUZZ (adds the `hypothesis` dev dependency)
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U1 F2 K1 V1 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §6.1
- docs/build-plan/app-studio/ORACLES.md §V
File allow-list:
- apps/api/app/ai_conversation/ledger_vote.py (new)
- apps/api/tests/test_brief_ledger_vote.py (new)
Goal: `cluster(entities_by_sample) -> clusters` and `vote(samples) -> VotedLedger`, pure, order-free and canonical.
Steps:
1. Union-find over all entities of all samples; join nodes from different samples at mention-interval Jaccard ≥ 0.2; at most one node per sample per cluster (tie-break in Pack §6.1 step 1); canonical cluster order by first-mention offset, then label casefold
2. Presence rules for k = 3 / 2 / 1 exactly as Pack §6.1 step 2
3. Majority role; ties and splits → `unsure` with the conservative default order (Pack §6.1 step 3, includes `stock_host`)
4. Granularity merge (Pack §6.1 step 4)
5. Fact attachment by majority; confidence = votes/k; canonical sort by first-mention offset
Acceptance criteria:
- AC1: Oracles V-01..V-11 pass unmodified (hypothesis for V-01..V-04)
- AC2: No pairwise/assignment solver anywhere in `ledger_vote.py` (Reviewer reads; order-free by construction)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_brief_ledger_vote.py`
Elite design notes: docs/build-plan/app-studio/00_PACK.md §6.1. The conservative order and the "1 of 2 → unsure, never dropped" rule are the anti-invention and anti-silent-fold guarantees under disagreement; neither changes without an Elite note.
Oracle tests: docs/build-plan/app-studio/ORACLES.md §V.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
