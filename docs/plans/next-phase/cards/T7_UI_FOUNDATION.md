# Cards — T7 UI foundation and page splits (D12)

Self-contained. Rules: `../T7_UI_MOTION_COPY.md`. Route blocks: `../13_UI_SCREEN_SPECS.md`. D12: Base UI primitives, Sonner toasts, `motion/react` as the only animation library, `input-otp` for TOTP, `react-virtuoso` for tables over 50 rows, `recharts` only for Dashboard Studio, `cmdk` stays.

**Skills to load before any card here** (Prime skills under `~/.cursor/skills/prime/`): `migrate-radix-to-base` (UI-F04–F07), `ask-sonner` (UI-F08), `motion`, `design-motion-principles`, `fixing-motion-performance` (UI-F09), `ui-craft-dense-dashboard`, `accessibility`, `frontend-a11y`, `feedback-patterns`, `error-handling-ux`, `no-ai-slop`. Read each skill's `SKILL.md` first; do not just name it.

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs; `:8001` does not reload; never loosen, delete, or snapshot-update a test to go green; stay inside "Change". **UI-specific:** one component family per card; `/e2e/kit` and `/e2e/tokens` stay green after each family; do not delete an `/e2e/*` harness to make a visual test pass; motion on `transform` and `opacity` only, never `transition: all`, never animate `backdrop-filter`; command palette open is instant; no scroll-reveal in tables; reduced motion becomes opacity only at ≤ 0.2 s; no new purple, no pie charts, no cards nested more than two deep; no business logic in components (it stays in `src/lib/`); no new i18n library (OQ-LANG); `pnpm --filter @odoo-custom/web typecheck` has 13 pre-existing errors: your card must not add one (record the count before and after).

**Current state (2026-10-02):** `package.json` has `@radix-ui/react-dialog`, `react-slot`, `react-tabs`, `react-tooltip`, `cmdk`, `motion@^14`, `sonner@^2`. Radix is imported by `src/components/ui/Button.tsx` (Slot), `Tabs.tsx`, `Sheet.tsx` (Dialog), `Dialog.tsx`, `Tooltip.tsx`. `AppToaster.tsx` (Sonner) is mounted in `src/app/layout.tsx`; the old `components/ui/Toast.tsx` is still used by 3 files. `MotionProvider.tsx` imports `motion/react`. Root `src/app/loading.tsx`, `error.tsx`, `not-found.tsx` and the same three under `connections/[id]/` exist. `.odoo-form-alert--*` already reads `--warning-*` tokens (lines 1328–1340 of `globals.css`). EmptyState or Skeleton appears on 5 of 70 pages. `e2e/a11y-primary.spec.ts` loops over a short path list.

**Shared commands:**

```bash
pnpm --filter @odoo-custom/web typecheck 2>&1 | rg -c "error TS"   # before and after; must not increase
pnpm --filter @odoo-custom/web test -- src/components/ui/kit.test.tsx
pnpm --filter @odoo-custom/web test:e2e e2e/a11y-primary.spec.ts
pnpm --filter @odoo-custom/web test:e2e e2e/vision-verify-sweep.spec.ts   # writes docs/vision-verify/
```

**Audit events:** none (UI). Build log entry includes the UX audit table and the copy critique for any card that changes visible text.

**Every UI card's evidence:** typecheck error count unchanged or lower; kit tests green; axe green for the routes touched; one desktop and one 390 px screenshot under `docs/vision-verify/<card-id>/`; the 12-row UX audit table in the progress log (Pass / Issue / Not observable); for copy changes, the 9-dimension critique with no 1 on Accuracy or Ethics.

---

### UI-F00 — Clear the 13 pre-existing type errors, then add typecheck to CI
- **Status:** OPEN
- **Pressure:** C2 U1 F1 K1 V0 I0 +0 = 5 → cheap
- **Change:** the files the errors point at; `.github/workflows/ci.yml` web job.
- **Acceptance:** [ ] `typecheck` exits 0; [ ] CI runs it.
- **Do not:** add `// @ts-ignore` or `any` to silence an error; fix the type.

### UI-F01 — Dark-mode alert tokens
- **Status:** DONE (verify): `.odoo-form-alert--info|warning|danger` use `--*-1/2/5` tokens.
- **Pressure:** 2 → cheap
- **Acceptance:** [ ] screenshot of each alert in light and dark under `/e2e/tokens`; contrast ≥ 4.5:1 in both.

### UI-F02 — loading, error, not-found
- **Status:** DONE (files exist at root and under `connections/[id]/`). Verify each uses the kit Skeleton and gives what / why / next step.
- **Pressure:** 3 → cheap
- **Acceptance:** [ ] `src/app/states.test.tsx` covers all six files.

### UI-F03 — EmptyState and Skeleton adopted on operate pages
- **Status:** OPEN (5 of 70 pages).
- **depends_on:** UI-F02
- **Pressure:** C2 U0 F1 K1 V1 I0 +0 = 5 → cheap; one sub-card per 5 pages is fine
- **Steps:** for each operate page in `../13` that can be empty or loading: (1) replace ad-hoc "Loading…" text or spinners with a Skeleton that matches the layout; (2) add an EmptyState with one sentence and one action, using the empty-state copy from the route block; (3) no spinner flash under 400 ms.
- **Acceptance:** [ ] every operate route in `../13` marked "can be empty" uses the kit; [ ] `rg -n "Loading\.\.\."` on those pages returns nothing.

### UI-F04 — Dialog family to Base UI
- **Status:** OPEN
- **Pressure:** C2 U2 F2 K2 V1 I1 +0 = 10 → Grok high effort (first family sets the pattern)
- **Read first:** skill `migrate-radix-to-base`; `src/components/ui/Dialog.tsx`, `Sheet.tsx`, `ConfirmDialogV2.tsx`, `src/components/ConfirmDialog.tsx`; `e2e/confirm-dialog.spec.ts`.
- **Change:** add `@base-ui-components/react` (check the current package name on npm before installing; record it); rewrite `Dialog.tsx` and `Sheet.tsx` internals; keep their exported props unchanged.
- **Steps:** (1) write a characterization test of the current Dialog (open, Escape closes, focus trap, focus returns, aria-labelledby); (2) swap internals; (3) run the characterization test unchanged; (4) remove `@radix-ui/react-dialog` from `package.json` only when no import remains.
- **Acceptance:** [ ] Dialog and Sheet on Base UI; [ ] characterization test unchanged and green; [ ] `e2e/confirm-dialog.spec.ts` green; [ ] Radix dialog import gone.
- **Negative:** Tab cannot leave an open dialog; Escape returns focus to the trigger.
- **Rollback:** revert the two files and `package.json`.

### UI-F05 — Tabs to Base UI
- **Status:** OPEN
- **depends_on:** UI-F04 (pattern)
- **Pressure:** 6 → Grok standard (mechanical after F04; cheap model acceptable)
- **Change:** `src/components/ui/Tabs.tsx`.
- **Acceptance:** [ ] arrow-key navigation, `aria-selected`, roving tabindex preserved; [ ] Radix tabs import gone.

### UI-F06 — Tooltip to Base UI
- **Status:** OPEN
- **Pressure:** 5 → cheap
- **Change:** `src/components/ui/Tooltip.tsx`.
- **Acceptance:** [ ] 125–200 ms; keyboard focus shows the tooltip; Escape hides it; [ ] Radix tooltip import gone.

### UI-F07 — Slot (Button asChild)
- **Status:** OPEN
- **Pressure:** 5 → cheap
- **Change:** `src/components/ui/Button.tsx`.
- **Acceptance:** [ ] `asChild` behavior preserved (Base UI `render` prop or a local Slot); `Button.test.ts` green; [ ] `@radix-ui/react-slot` removed; [ ] `rg -l "@radix-ui" src` returns nothing after F04–F07.

### UI-F08 — Sonner everywhere
- **Status:** PARTIAL (`AppToaster` mounted; `Toast.tsx` still used by 3 files).
- **Pressure:** 5 → cheap
- **Read first:** skill `ask-sonner`; `src/components/ui/AppToaster.tsx`, `Toast.tsx`; `rg -l "components/ui/Toast|useToast" src`.
- **Acceptance:** [ ] the 3 callers use Sonner; [ ] durations 3–5 s; errors persist until dismissed; `aria-live=polite`; [ ] `Toast.tsx` deleted only when unused.
- **Negative:** an error toast is still visible after 10 s.

### UI-F09 — Motion primitives
- **Status:** SEEDED (`MotionProvider.tsx`).
- **Pressure:** C2 U1 F1 K2 V2 I0 +0 = 8 → Grok standard
- **Change:** `src/components/ui/motion/` with `Drawer`, `SheetMotion`, `ListLayout` (approval list and diff panes).
- **Values (copied):** enter/exit `cubic-bezier(0.23, 1, 0.32, 1)`; drawers `cubic-bezier(0.32, 0.72, 0, 1)`; press 100–160 ms `scale(0.97)`; dropdown 150–250 ms; modal 200–300 ms; exit ≈ 75% of enter; stagger 30–80 ms, never in tables; interruptible; reduced motion opacity only ≤ 0.2 s.
- **Acceptance:** [ ] a Vitest asserts durations from one constants file; [ ] a reduced-motion test (`matchMedia` mock) asserts opacity-only; [ ] closing a drawer mid-open reverses from the current position.

### UI-F10 — input-otp for TOTP
- **Status:** OPEN
- **Pressure:** 5 → cheap
- **Change:** the TOTP step in `src/app/login/page.tsx` (plus enrol, if a page exists by then; `rg -ln -i "totp" apps/web/src`).
- **Acceptance:** [ ] paste of a 6-digit code works; password managers can fill it (`autocomplete="one-time-code"`); WCAG 3.3.8.

### UI-F11 — react-virtuoso for tables over 50 rows
- **Status:** OPEN
- **Pressure:** 6 → Grok standard
- **Change:** `src/components/ui/DataTable.tsx`, `BulkResultTable.tsx`.
- **Acceptance:** [ ] virtualized when rows > 50; keyboard row navigation preserved; sort and filter < 100 ms on 5,000 rows (measured in a test).

### UI-F12 — axe on every operate route
- **Status:** OPEN (short list today).
- **Pressure:** 5 → cheap
- **Change:** `e2e/a11y-primary.spec.ts` path list (use the `/e2e/*` harness pages when a route needs a live connection).
- **Acceptance:** [ ] every route in `../13` (or its harness twin) runs axe with zero serious or critical violations.

### UI-F13 — One canvas reorder primitive
- **Status:** OPEN
- **Pressure:** C2 U1 F2 K2 V2 I0 +0 = 9 → Grok standard
- **Owns the pattern.** Form, kanban, and printouts all reorder blocks with up/down buttons today. This card builds the one interaction. Screen cards consume it. They do not each invent a drag layer.
- **Change:** `src/components/ui/canvas/ReorderableBlocks.tsx` (pointer drag, keyboard arrows, drop rejected outside the canvas). Then switch these callers only: `components/reports/ReportCanvas.tsx`, `components/designer/FormCanvas.tsx`, `components/designer/KanbanCardPreview.tsx`, `components/designer/DesignerStructuralCanvas.tsx`, `components/designer/DesignerAdvancedStructureCanvas.tsx`.
- **Acceptance:** [ ] one component, five callers; [ ] keyboard path still passes `e2e/designer-keyboard.spec.ts` and `FormCanvas.test.tsx`; [ ] a drop outside the canvas inserts nothing.
- **Do not:** restyle the designer page here (that is UI-S-12, after UI-SP-DESIGNER). Do not change the saved XML or QWeb.

## Page splits (no behavior change; characterization tests first)

Template for every UI-SP card: **Pressure** C2 U1 F2 K1 V1 I0 = 7 → Grok standard. **Steps:** (1) write or confirm characterization tests (Vitest render + one Playwright happy path) before editing; (2) move sections into `components/<area>/` files under 400 lines each; (3) page file under 300 lines; (4) no prop, route, copy, or API change; (5) tests unchanged and green. **Do not:** restyle in the same card (R-09: one writer per file). **Acceptance:** [ ] line counts met; [ ] tests unchanged and green; [ ] typecheck count unchanged. **Rollback:** revert the card's commit.

| Card | File (lines today) | Existing tests to keep green |
|---|---|---|
| UI-SP-API | `apps/web/src/lib/api.ts` (6130) → `src/lib/api/<domain>.ts` with `api.ts` re-exporting | all Vitest |
| UI-SP-WIZARD | `connections/[id]/wizard/page.tsx` (1892) | `e2e/wizard-*.spec.ts` |
| UI-SP-STUDIO | `connections/[id]/studio/page.tsx` (1548) | `e2e/studio-preview.spec.ts` |
| UI-SP-DESIGNER | `connections/[id]/designer/page.tsx` (1429) | `e2e/designer-*.spec.ts` |
| UI-SP-BULK | `connections/[id]/bulk-suite/page.tsx` (1312) | Vitest for bulk components |
| UI-SP-OVERVIEW | `connections/[id]/page.tsx` (1225) | overview tests |
| UI-SP-CONFIG | `connections/[id]/config/page.tsx` (946) | config tests |
| UI-SP-CSS | `src/styles/studio-refinement.css` (1721), `src/app/globals.css` (1366): split by area, no rule change | `/e2e/tokens` screenshot diff |
