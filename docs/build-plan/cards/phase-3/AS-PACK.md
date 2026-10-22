# AS-PACK: App Studio Design Pack (Stage 2B)

ID: AS-PACK
Title: App Studio Design Pack (Stage 2B)
Status: done
Phase: 3
Priority: P1
Type: docs
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: XL (caps in budget.json). Stop at 80%.
Ledger IDs: P1-2; AS-FAIL-A; AS-FAIL-B; AS-FAIL-D; AS-FAIL-C; AS-FIX-3; AS-FIX-CONSERVE; AS-FIX-EVAL; AS-ANYBRIEF; AS-FIXPLAN-SUPERSEDE
Depends on: DEC-002
Routing: Worker: E1 (planner, XL elite design card) · Reviewer: E2 Fable independent review (01_REVIEW.md) · Score: 17 (C3 U3 F3 K3 V3 I2)
Context pack:
- docs/specs/APP_STUDIO_HANDOFF.md, APP_STUDIO_FIX_PLAN.md, GAP_AUDIT.md §5; handover L863-951
- docs/build-plan/CODE_MAP.md
File allow-list:
- docs/build-plan/app-studio/**
- docs/build-plan/CODE_MAP.md
- docs/build-plan/cards/phase-3/AS-*.md
Goal: Root causes with evidence, the never-errors guarantee, the v3 design, oracles and buildable cards.
Steps:
1. Read sources and code paths
2. Write the Pack, oracles, CODE_MAP and cards
3. Independent Fable review; fold the findings in
Acceptance criteria:
- AC1: Pack §2 names each root cause with a code or log citation
- AC2: Every AS ledger row maps to a card file that lints clean
- AC3: Independent review recorded in 01_REVIEW.md with dispositions
Test plan:
- `python3 scripts/plan_lint.py cards --phase 3 --prefix AS-`
Elite design notes: docs/build-plan/app-studio/00_PACK.md is the elite design. Main risks and dispositions are in 01_REVIEW.md.
Oracle tests: docs/build-plan/app-studio/ORACLES.md (all sections).
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: docs/build-plan/app-studio/*, CODE_MAP.md, cards/phase-3/AS-*.md (21 Oct). Lint output in coverage/.
Rollback: Docs only: revert the files.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
