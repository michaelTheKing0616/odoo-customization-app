# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** Premium ModuleSpec UX (surface 6) on `cursor/premium-modulespec-ux-e324` off Job Autopilot:
  - Stage rail: load → edit → validate → apply
  - Extracted chrome in `apps/web/src/components/modulespec/` + `modulespec-journey.ts`
  - Structured models/views/menus/security; JSON is an escape hatch
  - Local + live readiness; Generate UI / zip kept; Completeness ≠ Cert ≠ Autopilot
- **Tests:** 20 vitest (journey + shell/rail/session/banners/readiness/handoff/editor) green
- **Failed:** none. Browser verified on `/e2e/modulespec`.

## Next
- Continue premium sweep only if asked (do not start Projects / Expert here)
- Live Generate UI / validate-live still need a real connection + API

## Rule
- ModuleSpec premium is a four-stage IR workbench. JSON stays secondary. Completeness is hygiene, not go-live. Promote stays human.
