# AS-DRAFT-ADOPT: Draft Studio runs the App Studio v3 pipeline; no domain packs

ID: AS-DRAFT-ADOPT
Title: Draft Studio runs the App Studio v3 pipeline; no domain packs
Status: todo
Phase: 3
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: AS-DRAFT-V3
Depends on: AS-RELEASE-BARS, AS-V3-WIRE
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L3 separate session · Score: 7 (C2 U1 F2 K1 V1 I0)
Context pack:
- docs/build-plan/09_DECISIONS_FOR_TOPE.md DEC-043
- apps/api/app/ai_pipeline.py L87-170 (`seed_unpacked_draft`, `seed_studio_draft`), L699 (`run_staged_pipeline`)
- handover §3.17 (what packs do today)
File allow-list:
- apps/api/app/ai_pipeline.py (route generation to `v3_pipeline` under profile v3)
- apps/api/tests/test_draft_studio_v3.py (new)
- docs/build-plan/app-studio/PACK_PRESERVATION.md (new)
Goal: Once v3 passes its release bars, Draft Studio's generate path calls `v3_pipeline`; no `ai_domain_pack*` module is reachable from it; everything packs did for users still exists.
Steps:
1. Write PACK_PRESERVATION.md first (INV-05): each pack behaviour → where it lives under v3 (stock_first_rework → host_fit + AS-GROUND-EXISTS; "Use stock app X" → stock_reuse card; industry seed CSVs → K42 import templates / AS-TRYIT; curated provenance → retired with the packs)
2. Route Draft Studio generate through `v3_pipeline` when the profile is v3; legacy profile unchanged
3. Import-graph test: from the Draft Studio v3 entry, no `ai_domain_pack` module is importable
4. On ship, the Orchestrator asks Tope to approve the AGENTS.md Draft Studio pack sentence edit (rules file)
Acceptance criteria:
- AC1: Draft Studio eval subset under v3 meets the AS-RELEASE-BARS numbers
- AC2: import-graph test passes
- AC3: every row of PACK_PRESERVATION.md names a live replacement or a Tope-approved retirement
- AC4: "Use stock app X" still shown for restaurant / project / retail briefs
Test plan:
- `cd apps/api && uv run pytest -q tests/test_draft_studio_v3.py`
Elite design notes: DEC-043: Tope approved dropping packs from Draft Studio once v3 works. File deletion is AS-PACK-RETIRE, not this card.
Oracle tests: docs/build-plan/app-studio/ORACLES.md: AC2 and AC4 are locked: Tester writes them from this card before the Worker starts
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
