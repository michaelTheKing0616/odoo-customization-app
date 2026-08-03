# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- Commit (pending): **UIX-4b** — projects (`ProjectDiffPanel` + kit), access (matrix-first tabs + kit forms), automations (trigger→condition→action chain + ConfirmDialogV2), designer (PageHeader/Callout/toolbar card + keyboard reorder in `FormCanvas`).
- Gates: `pnpm test` 78 passed; `pnpm build` ok. E2e not re-run (Playwright browsers missing in sandbox).

## Next (prescribed wave order)
- **UIX-4c** — power-ops/bulk, journal, import, reports, menus, config, reminders, modulespec, settings, pipelines + legacy-style grep purge.
- **UIX-5** — copy guide pass + iconography audit.

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell provides nav chrome — connection pages keep content only.
- Diagnose errors: `ErrorNotice` + `reportApiError(..., { toast: true })` on mutations.
