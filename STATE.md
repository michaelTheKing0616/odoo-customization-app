# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **UIX-2 (full kit):** Input, Textarea, Select, Combobox, Dialog, Tabs, DataTable, CodeBlock, DiffView, BulkResultTable, ConfirmDialogV2, StatusPill, ErrorNotice, useCommand registry; `/e2e/kit` expanded; `kit.test.ts`.
- **EXP-5 follow-up:** `ErrorNotice` + `reportApiError` + toast listener wired on builder/automations/wizard/designer; mutation failures toast with Diagnose action.
- **UIX-4a (partial):** Landing + Connect restyled on tokens/kit (3-step connect flow, summary step).
- **E2E:** `shell-expert.spec.ts` 3/3 green (fixed API mocks for overview sub-routes).
- Gates: `pnpm test` 78 passed; `pnpm build` ok.

## Next
- **UIX-4a remainder** — Overview hub + Draft Studio wizard rebuild on kit.
- **UIX-4b/c** — designer, automations, remaining page migrations + per-page nav strip removal.
- Vision-verify screenshots (tokens/kit/shell light+dark).

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell context: `useSyncShellContext` on builder/designer/automations/wizard.
- Diagnose errors: `ErrorNotice` inline + `reportApiError(..., { toast: true })` for mutations.
