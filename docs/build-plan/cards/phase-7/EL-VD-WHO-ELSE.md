# EL-VD-WHO-ELSE: Who else touches this spot

ID: EL-VD-WHO-ELSE
Title: Who else touches this spot
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-NEXT
Depends on: EL-BAR-VD, AS-GROUND-VIEWMAP
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- handover §3.4
- apps/api/app/view_map.py (AS-GROUND-VIEWMAP)
File allow-list:
- apps/api/app/view_conflicts.py (new)
- apps/api/tests/test_view_conflicts.py (new)
- apps/web/src/components/view-designer/WhoElsePanel.tsx (new)
Goal: For a selected element: every module view that inherits at that anchor, with module and priority; warn before an edit that would collide.
Steps:
1. Ownership from the view map
2. Warning names the other module in plain words
3. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: fixture with two inheriting modules lists both
- AC2: colliding edit shows a warning before publish
Test plan:
- `cd apps/api && uv run pytest -q tests/test_view_conflicts.py`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
