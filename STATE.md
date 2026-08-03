# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-08-03
- **UIX-1:** Design tokens (`globals.css`), Inter + JetBrains Mono, dark mode (`ThemeProvider`), `/e2e/tokens`.
- **UIX-2 (core):** `components/ui/*` kit subset (Button, Sheet, Callout, Badge, Toast, CommandPalette, icons, layout primitives); `/e2e/kit`.
- **UIX-3:** `connections/[id]/layout.tsx` app shell — sidebar (`nav.ts`), top bar, Cmd+K palette, React Query, Expert mount slot.
- **EXP-5:** `ExpertPanel` (chat, citations, error paste, sessionStorage thread), `ExplainThisButton` + `AskWhyButton`, wired on builder/designer/automations/wizard; `api.expertAsk`.
- Recovery cleanup: deduped replay corruption in 10+ web pages + `api.ts` so `pnpm build` passes.
- Gates: `pnpm test` 74 passed; `pnpm build` ok; Playwright `shell-expert` 2/3 (expert open selector fix pending re-run).

## Next
- **UIX-2 remainder** — full 20-component kit + per-component Vitest (DataTable, DiffView, ConfirmDialog v2, etc.).
- **UIX-4a** — page migrations (landing, connect, overview, Draft Studio).

## Rules
- Expert thread: `sessionStorage` key `expert-thread-{connectionId}`.
- Shell context: `useSyncShellContext` on builder/designer/automations/wizard.
- Diagnose errors: `diagnoseWithExpert(text)` from toast handlers.
