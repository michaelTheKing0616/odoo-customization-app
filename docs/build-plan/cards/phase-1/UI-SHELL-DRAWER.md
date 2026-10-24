# UI-SHELL-DRAWER: below sm the app sidebar is an off-canvas drawer and the page does not scroll sideways
ID: UI-SHELL-DRAWER
Title: below sm the app sidebar is an off-canvas drawer and the page does not scroll sideways
Status: done
Phase: 1
Priority: P0
Type: build
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: L (caps in budget.json). Stop at 80%.
Ledger IDs: SHELL-DRAWER
Depends on: none (phase order applies)
Routing: Worker: L3 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L3 separate session · Score: 6 (C1 U1 F2 K1 V1 I0)
Context pack:
- apps/web/src/components/shell/Sidebar.tsx
- apps/web/src/components/shell/AppShell.tsx
- apps/web/src/components/shell/TopBar.tsx
- apps/web/src/components/ui/motion/Drawer.tsx (read only)
- docs/build-plan/FACTS.md
File allow-list:
- apps/web/src/components/shell/Sidebar.tsx
- apps/web/src/components/shell/AppShell.tsx
- apps/web/src/components/shell/TopBar.tsx
- apps/web/src/components/shell/AppShell.test.tsx
- apps/web/src/app/e2e/shell-drawer/page.tsx (new)
- apps/web/e2e/shell_drawer.spec.ts (new)
- apps/web/playwright.shell-drawer.config.ts (new)
Goal: Make every AC below true for `UI-SHELL-DRAWER` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. Load the Prime skills for taste, motion, copy, and accessibility before editing the shell.
2. Below the `sm` breakpoint (640px), `app-sidebar` is closed and off-canvas. From `sm` up it stays the docked column it is today, including collapse.
3. Reuse `Drawer` from `@/components/ui/motion` (`side="left"`). Do not edit that file. The open control sits in the top bar and is labelled "Open sidebar". Escape, the drawer close control, and the scrim close it. Motion stays the drawer's transform and opacity, under 300ms, and reduced-motion safe.
4. Run the Test plan. The harness is Example data and does not call port 8001.
5. STOP-AND-ASK: a needed file is outside the allow-list; `Drawer` cannot hold the existing nav; an AC is ambiguous; a live check would need a non-`ingenium_` DB, a forbidden port, a git write, or a new dependency.
Acceptance criteria:
- AC1: Below `sm`, the app shell sidebar is an off-canvas drawer, closed when the page loads, and not in the document flow. From `sm` up, the docked sidebar is unchanged. (source: NF report 24 Oct; Tope asked for this card)
- AC2: At 390×844, in light and in dark, the shell harness has no horizontal scroll (`documentElement.scrollWidth` is at most `clientWidth`, and the same is true for `[data-testid="app-shell"]`). Axe on `[data-testid="app-shell"]` reports 0 serious or critical violations in both themes, with the drawer closed and again with it open.
- AC3: The loading skeleton uses the same `sm` cutoff as the loaded sidebar.
Test plan:
- `cd apps/web && pnpm playwright test e2e/shell_drawer.spec.ts --config=playwright.shell-drawer.config.ts` → pass
- That config serves `next dev` on `127.0.0.1:3114` with `INGENIUM_DIST_DIR=.next-shell-drawer`. It does not run `next build`, does not write `.next` or `.next-e2e`, and does not reuse a server it did not start. Delete `.next-shell-drawer` when the run finishes.
- The spec sets the viewport to 390×844, runs light and dark, checks the scroll widths, and runs `@axe-core/playwright` on `[data-testid="app-shell"]`. It also checks the docked sidebar at 1440×900.
Common mistakes: raw hex instead of tokens; a bare `next build` (overwrites dev `.next`); editing `Drawer.tsx`, `Tooltip.tsx`, `globals.css`, `nav.ts`, `playwright.config.ts`, or `apps/web/src/app/connections/`; restarting `:8001`; a new dependency; hiding the docked sidebar at desktop widths. The existing `Tooltip.tsx` type error is out of scope.
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
Oracle tests: Oracle-first: a separate L3 Oracle session writes the red Playwright spec in `apps/web/e2e/shell_drawer.spec.ts` (one positive scroll and axe check, one negative that the docked sidebar is still present from `sm` up) before the Worker starts; locked (Worker may not edit); E1 reviews them when score ≥ 10 (DEC-046).

2026-10-24 closed. Playwright 2 passed in 8.8s. Tester 2 passed in 8.9s. SHELL-DRAWER is [Done, code]. Reviewer APPROVE.
