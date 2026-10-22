# AS-NO-PACKS: No vertical packs on the v3 path

ID: AS-NO-PACKS
Title: No vertical packs on the v3 path
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-NOPACK
Depends on: AS-PROFILE
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 4 (C1 U1 F1 K1 V0 I0)
Context pack:
- docs/build-plan/app-studio/00_PACK.md §0a, §11
- docs/build-plan/app-studio/ORACLES.md K-09
- apps/api/app/ai_conversation/intent_gate.py L75-150 (pack ranking; read)
File allow-list:
- apps/api/app/ai_conversation/studio_profile.py (`packs: bool`, False in v3, True in legacy_v1)
- apps/api/app/ai_conversation/intent_gate.py (skip pack ranking when `profile.packs` is False)
- apps/api/tests/test_no_packs_v3.py (new)
Goal: Under v3, vertical domain packs never add structure, never fill a degraded outline and never steer classification; legacy is unchanged.
Steps:
1. Add the profile field; gate the `rank_domain_packs` / `retrieve_domain_pack_lexical` / `load_domain_pack` calls in `intent_gate`
2. Grep every other App Studio entry point that imports `ai_domain_packs` or an `ai_domain_pack_*` module and list them in the Tester packet with how v3 avoids each
3. Spy test: a v3 run on 5 dev briefs never calls any pack function and no lineage has a pack id
Acceptance criteria:
- AC1: ORACLES K-09 passes unmodified
- AC2: legacy_v1 intent_gate output unchanged (golden on 3 briefs)
Test plan:
- `cd apps/api && uv run pytest -q tests/test_no_packs_v3.py`
Elite design notes: INV-05 applies: packs are not deleted. Draft Studio keeps them until Tope decides; only the v3 App Studio path stops using them. Stock-first app reuse is not a pack and stays (retrieval + host_fit).
Oracle tests: docs/build-plan/app-studio/ORACLES.md K-09.
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
