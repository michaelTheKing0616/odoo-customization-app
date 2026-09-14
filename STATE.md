# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** Premium Projects UX (surface 7) — PR off `cursor/premium-modulespec-ux-e324`
  - Four-stage shell: browse → inspect → review → apply (`apps/web/src/components/projects/*`)
  - Release board, elevated Review vs live diff, snapshot history + rollback CTAs
  - Glossary: Draft / Apply / Promote / Snapshot / Rollback / Sandbox; Completeness ≠ Cert ≠ Autopilot
  - Tests: `pnpm test src/lib/projects-journey.test.ts src/components/projects` (22 passing)
- **Failed:** Live `/connections/{id}/projects` needs API + Odoo; verified harness `/e2e/projects` instead. Next overlay “1 Issue” is `/api/billing/entitlements` 502 in this VM, not Projects chrome.
- **Rule:** Projects Apply creates models/fields only. Do not claim full rollback of created columns; snapshot restore is views/automations when Odoo allows.

## Next
- Operator: open `/connections/{id}/projects`, pick a draft, Review vs live, then Apply on a sandbox
- Remaining premium sweep: Odoo Expert (not this run)

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
