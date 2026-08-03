# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- Commit (pending): **UIX-4c partial** — power-ops (recipe cards, dry-run-first, BulkResultTable), journal (merged timeline + filter chips + rollback badges), bulk-suite (section Cards + BulkResultTable), import (stepper + seed cards), settings, pipelines (stage-flow cards), reminders.
- Prior: `44cb7b3` UIX-4b complete.
- Gates: `pnpm test` 78 passed; `pnpm build` ok.

## Next (prescribed wave order)
- **UIX-4c finish** — menus, config, reports, modulespec, id-generator, builder shell; legacy-style grep purge; e2e smoke.
- **UIX-5** — copy guide pass + iconography audit.

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell provides nav chrome — connection pages keep content only.
- Diagnose errors: `ErrorNotice` + `reportApiError(..., { toast: true })` on mutations.
