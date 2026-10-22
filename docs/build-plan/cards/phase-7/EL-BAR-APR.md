# EL-BAR-APR: Approvals: pass the Feature Excellence Bar

ID: EL-BAR-APR
Title: Approvals: pass the Feature Excellence Bar
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-BAR
Depends on: EL-X-BAR, EL-X-AUTHZ, REL-STATIC-WRITE, EL-X-ERRORS
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- handover §3.14 (this feature)
- docs/build-plan/elevate/00_ELEVATE.md §1
- `python3 scripts/excellence_scorecard.py --feature apr` output
File allow-list:
- apps/web/src/components/approvals/ (and co-located tests)
- apps/web/src/app/approvals/ (and co-located tests)
- apps/api/app/routers/approvals.py (and co-located tests)
- apps/api/app/routers/inbox.py (and co-located tests)
- the EL-X baseline files (remove this feature's entries only)
Goal: Every §1 check is green for Approvals on every route and endpoint it owns.
Steps:
1. Run the scorecard; paste the red rows into the Worker packet
2. Fix one red row at a time inside the allow-list; re-run the scorecard after each
3. A fix that needs a guarded path (INV-14) or another feature's files stops and becomes a new card
4. UI checkpoints: baseline, after, final
5. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: scorecard for `apr` exits 0
- AC2: this feature's entries are gone from every EL-X baseline file
- AC3: keyboard-only walkthrough of the main task passes (Playwright)
- AC4: Tope rates each screen ≥ 8 at the final checkpoint
Test plan:
- `python3 scripts/excellence_scorecard.py --feature apr`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
