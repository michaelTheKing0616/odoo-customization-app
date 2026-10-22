# AS-DRAFTFOLD: Fold Draft Studio under App Studio

ID: AS-DRAFTFOLD
Title: Fold Draft Studio under App Studio
Status: todo
Phase: 3
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: S (caps in budget.json). Stop at 80%.
Ledger IDs: AS-DRAFTFOLD
Depends on: none
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 3 (C1 U0 F1 K1 V0 I0)
Context pack:
- handover §3.3 L247; FEATURE_AUDIT 14
- DEC-024
- docs/build-plan/UI_REFERENCE_MAP.md area 07
File allow-list:
- apps/web/src/app/connections/[id]/studio/**
- apps/web/src/app/connections/[id]/projects/**
- apps/web/src/components/studio/**
- apps/web/src/lib/nav.ts
Goal: (Not on the v3 critical path; schedule with the UI build pack, any time.) Saved drafts and the app plan live inside App Studio (Saved drafts; Advanced: app plan); old routes redirect; every feature preserved (INV-05).
Steps:
1. List what Draft Studio and Projects do today (INV-05 table in the PR text)
2. Move entry points; add redirects
3. Jargon guard + states (empty/loading/error) per the UI protocol
Acceptance criteria:
- AC1: Every listed feature reachable from App Studio
- AC2: Old routes redirect (Playwright)
- AC3: UI protocol checklist passes (side-by-side vs the area 07 references)
Test plan:
- `cd apps/web && pnpm vitest run src/components/studio`
- Playwright redirect spec
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Profile `legacy_v1` stays the default until AS-AUTHZ-DEFAULT, so production behaviour does not change.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
