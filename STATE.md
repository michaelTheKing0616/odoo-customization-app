# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- Commit (pending): **UIX-5 complete** — COPY_GUIDE copy fixes, `copy-guide.ts` empty/honesty strings, EmptyStates (automations/journal/bulk-suite/projects), GatingCallout + HealthCheckBanner + VersionAwarenessBanner on kit, Badge contrast tokens, `@axe-core/playwright` + 8-page axe e2e, audit in `plans/UIX-5-AUDIT.md`.
- Prior: `75cb19d` UIX-4c complete.
- Gates: `pnpm test` 78 passed; `pnpm build` ok; e2e `a11y-primary` + `automation-gating` 9 passed.

## Next (prescribed wave order)
- **Wave 7 CMP** — already marked complete in PROGRESS; next unstarted work is post-UIX backlog or new cards.

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell provides nav chrome — connection pages keep content only.
- Diagnose errors: `ErrorNotice` + `reportApiError(..., { toast: true })` on mutations.
