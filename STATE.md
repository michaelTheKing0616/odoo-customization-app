# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- Commit (pending): **UIX-4c complete** — menus, id-generator, reports, config, modulespec, builder, approvals, cron-manager, housekeeping onto kit; legacy hex/`odoo-shell`/`radial-gradient` purge on UIX-4c pages; ConfirmDialogV2 throughout.
- Prior: `d710521` UIX-4c partial (power-ops, journal, bulk-suite, import, settings, pipelines, reminders).
- Gates: `pnpm test` 78 passed; `pnpm build` ok. E2e smoke not re-run this session (Playwright install locally if needed).

## Next (prescribed wave order)
- **UIX-5** — copy guide pass + iconography audit.

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell provides nav chrome — connection pages keep content only.
- Diagnose errors: `ErrorNotice` + `reportApiError(..., { toast: true })` on mutations.
