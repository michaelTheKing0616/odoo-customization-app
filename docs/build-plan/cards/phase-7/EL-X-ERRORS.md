# EL-X-ERRORS: One error shape and plain error messages everywhere

ID: EL-X-ERRORS
Title: One error shape and plain error messages everywhere
Status: todo
Phase: 7
Priority: P1
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: ELR-REL
Depends on: EL-X-BAR
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: L2 separate session · Reviewer: L2 separate session · Score: 5 (C1 U1 F1 K1 V1 I0)
Context pack:
- apps/api/app/main.py (no exception handlers today [Verified 21 Oct])
- apps/web/src/lib/api-error.ts, format-fetch-error.ts
- apps/web/src/components/ui/ErrorNotice.tsx
File allow-list:
- apps/api/app/errors_catalog.py (new)
- apps/api/app/main.py (register handlers only)
- apps/api/tests/test_errors_catalog.py (new)
- apps/web/src/lib/api-error.ts
- apps/web/src/components/ui/ErrorNotice.tsx
- apps/web/src/lib/api-error.test.ts
Goal: Every API error returns `{code, message, fix, retryable, request_id}`; the web shows message + fix + Retry; no stack trace reaches a user.
Steps:
1. Catalog: code → owner sentence + fix, jargon-guarded
2. Handlers for HTTPException, validation errors and the unhandled case (logs request_id, never secrets)
3. Web maps codes to ErrorNotice; unknown codes get the generic catalog entry
4. UI: every screen this card touches meets handover §5 + `UI_REFERENCE_MAP.md` + `07_UI_EXCELLENCE_PROTOCOL.md` (Tope: the absolute best design on every screen): designed empty/loading/error/offline states, tokens only, Base UI + Sonner, motion < 300 ms transform/opacity with reduced-motion, plain copy that passes the jargon guard. UI checkpoints only: baseline, after, final (one contact sheet per screen).
Acceptance criteria:
- AC1: an unhandled exception returns the envelope with a request_id and no traceback
- AC2: every catalog message passes the jargon guard
- AC3: web test renders fix + Retry
Test plan:
- `cd apps/api && uv run pytest -q tests/test_errors_catalog.py ; cd apps/web && pnpm vitest run src/lib/api-error.test.ts`
Gate: Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). No existing behaviour is removed by this card; a ratchet baseline file, where present, keeps today's known gaps listed so the revert is clean.
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
