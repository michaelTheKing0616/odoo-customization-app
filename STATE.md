# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** Premium Odoo Expert UX (surface 8) — PR off `cursor/premium-projects-ux-371f`
  - Copilot drawer: header, context bar, thread, sources, caution flags, composer (`apps/web/src/components/expert/*`)
  - `?expert=1` Overview destination card + inbound studio links
  - Honesty: Completeness ≠ Cert ≠ Autopilot; Expert never auto-promotes
  - Tests: vitest expert libs/components 28 passed; Playwright `expert-flows` + `shell-expert` 5 passed
- **Failed:** First Playwright run lacked Chromium; installed browsers. Visual review caught blank Error log on explain-this — fixed.
- **Rule:** `formatExpertDiagnosePrompt` is diagnose-only. Explain-this / Ask-why must not attach an empty Error log.

## Next
- Parent coordinates world-class UAT (not this run)
- Operator: `/connections/{id}?expert=1` and `/e2e/expert` (`NEXT_PUBLIC_E2E=1`)

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
