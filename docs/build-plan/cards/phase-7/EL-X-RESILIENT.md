# EL-X-RESILIENT: Nobody loses work: offline banner, retries, autosave

ID: EL-X-RESILIENT
Title: Nobody loses work: offline banner, retries, autosave
Status: todo
Phase: 7
Priority: P2
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-REL
Depends on: EL-X-ERRORS
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- apps/web/src/lib/api.ts
- apps/web/src/components/shell/AppShell.tsx (existing online/offline handling)
- apps/web/src/components/view-designer/useViewDesigner.ts, report-designer/useReportDesigner.ts (existing offline hooks)
File allow-list:
- apps/web/src/lib/autosave.ts (new)
- apps/web/src/lib/autosave.test.ts (new)
- apps/web/src/lib/api.ts (retry with backoff for idempotent calls)
- apps/web/src/components/shell/AppShell.tsx
Goal: Idempotent requests retry with backoff; a calm offline banner with Retry; brief, view, report, script and flow drafts autosave locally and offer restore.
Steps:
1. Retry only GET and calls carrying an idempotency key
2. Autosave keyed by connection + editor + record; cleared on successful save
3. Restore prompt names what and when
4. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: non-idempotent POST is never retried (test)
- AC2: autosave restores after reload (test)
- AC3: offline banner announced via live region
Test plan:
- `cd apps/web && pnpm vitest run src/lib/autosave.test.ts`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
