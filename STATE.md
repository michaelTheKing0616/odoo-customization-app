# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- Commit `754d1ac`: UIX-2 full kit, Expert error diagnosis, landing/connect migration, e2e fixes.
- **UIX-4a (complete):** Overview (`connections/[id]/page.tsx`) — removed legacy nav, PageHeader, stat cards, DataTable tabs, kit export panel. Draft Studio (`wizard/`) — pipeline rail, Card composer, kit controls, template cards.
- Gates: `pnpm test` 78 passed; `pnpm build` ok; `shell-expert` e2e 3/3.

## Next (prescribed wave order)
- **UIX-4b** — designer, projects, automations, access page migrations onto kit.
- **UIX-4c** — remaining pages + per-page nav strip removal.
- **UIX-5** — copy guide pass + iconography audit.

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell provides nav chrome — connection pages keep content only.
- Diagnose errors: `ErrorNotice` + `reportApiError(..., { toast: true })` on mutations.
