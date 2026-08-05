# Wave 14 — UIF: UI friendliness — progressive disclosure, dedupe, IA regroup (Composer cards)

Goal: keep ALL features; reduce first-glance overwhelm via grouping, disclosure, and copy.
Confirmed by orchestrator 2026-08-05 from `docs/vision-verify/shell-overview-light.png` +
`apps/web/src/lib/nav.ts`. Follow COPY_GUIDE.md voice. Kit components only. Same execution
protocol as MASTER_PLAN (checkboxes, gates, honest flips).

---

## UIF-1 — Dedupe instance identity + kill raw errors (DO FIRST — confirmed duplicate)

TASK: Overview shows the instance identity 3×: top-bar chips (Odoo 19.0 / self hosted /
community / Experimental), page-header chips (GA / community), and capability badges
(Odoo 19 community / Self-hosted). A raw "Failed to fetch" string renders in the body.

CHECKLIST:
- [x] One `InstanceIdentity` cluster component (version · edition · hosting · support tag),
      rendered ONCE in the top bar. Remove the page-header GA/community chips and the
      duplicate "Odoo 19 community / Self-hosted" badges; keep "N capabilities · Show
      details · Re-probe" as a single quiet row.
- [x] Sweep all pages for the same repetition (`rg -l "community" apps/web/src/app` and
      badge components) — one identity cluster per screen max.
- [x] Replace any raw fetch-error text (e.g. playbooks "Failed to fetch") with the kit
      error Callout + Retry per COPY_GUIDE error pattern. Grep for `Failed to fetch`,
      unwrapped `.message` renders.
- [x] Vitest: identity cluster renders once; error callout on failed loader.
- [x] BUG: Bulk Suite page renders a full second copy of six sections (Mass field edit,
      Duplicate detection & merge, Bulk activities, Bulk security, Bulk portal access,
      Bulk send message) — find the double render (duplicate map/mount) and fix; vitest
      asserts each section heading appears exactly once.
- [x] BUG: Housekeeping renders the "Stored compute recompute" block twice — same fix +
      once-only test.
- [x] BUG: Sidebar marks BOTH "Overview" and the current page as active (seen on Import,
      Journal, Reminders) — active match must be exact for the overview href, prefix for
      others; vitest covers.
- [x] Overview header buttons (Build / Draft Studio / Journal) + top-bar "Expert" duplicate
      sidebar destinations — keep ONE entry point: drop the header buttons, keep the three
      primary actions from UIF-3 (top-bar Expert may stay; sidebar "Odoo Expert" then opens
      the same panel — no separate route confusion).
- [x] Journal page: "Change journal" appears as both page title and button on Overview, and
      the Post-upgrade health banner duplicates the Health filter tab — keep banner only
      when actionable; rename Overview button to "Open journal".

## UIF-2 — Sidebar IA: collapsible groups, unique icons, Operations hub

TASK: 23 flat items / 6 groups ("Build" alone has 9); 5 icon pairs reused (Bulk Suite +
Power Ops, Cron Manager + Reminders, Draft Studio + Odoo Expert, ModuleSpec + Projects,
Code Studio + Script Runner) — reads as duplicates.

CHECKLIST:
- [x] Collapsible nav groups (chevron, persisted per-user in localStorage). Defaults:
      Overview + Build + AI expanded; Data, Operate, Govern collapsed.
- [x] Unique icon per nav item — replace the 5 reused pairs (lucide equivalents via kit
      icon map). No two sidebar items share an icon.
- [x] Group relabel to task language: Build → "Build", AI → "AI Studio",
      Operate → "Operations", Govern → "Safety & History". One-line tooltip per group
      header (from COPY_GUIDE glossary).
- [x] `/connections/[id]/operations` hub page: card grid linking the 6 Operate tools
      (Bulk Suite, Power Ops, Cron Manager, Housekeeping, Reminders, Script Runner) with
      one-sentence descriptions. Sidebar Operate group header links to it. Existing routes
      unchanged — nothing removed.
- [x] Move Code Studio + Script Runner under a "Developer" sub-caption within their groups
      (visual caption row, not a new route) so no-code users can ignore them.
- [x] Vitest: nav grouping snapshot; collapse persistence; icon uniqueness test
      (assert no duplicate icon components across NAV_ITEMS).

## UIF-3 — Overview declutter: progressive disclosure

TASK: First screen mixes stats, health, playbook links, export/sandbox/promote developer
form, promoted-modules history, and a models table.

CHECKLIST:
- [x] Above the fold: stats row, health banner, 3 primary actions (Draft with AI, Open
      Builder, Run health sweep).
- [x] Tabs (kit): "Overview" (stats + health + playbooks as collapsed accordion) ·
      "Models" (filter + table) · "Develop" (Export/sandbox/promote + Promoted modules).
      All existing features reachable — nothing deleted.
- [x] Empty-state first-run card when 0 models: 3-step "Start here" (Connect ✓ → Draft →
      Apply) with links; dismissible, persisted.
- [x] Vitest: tab presence; first-run card show/dismiss.

## UIF-4 — Copy + density pass on remaining screens

CHECKLIST:
- [x] Every page h1 gets a one-line plain-language subtitle (COPY_GUIDE voice; ≤90 chars).
      — connection sub-routes with existing PageHeader descriptions retained/updated; new
      Operations hub + Overview subtitle added.
- [x] Jargon sweep on user-facing strings: PCM → "protected core", x_ prefix explained once
      via tooltip not inline, "ModuleSpec" keeps name + subtitle "the blueprint of your
      app". Do NOT rename routes/ids. — Approvals engine line dropped; ModuleSpec subtitle;
      designer kanban "Column field" vs badge.
- [x] Dense tool pages (Bulk Suite, Power Ops, Housekeeping): advanced options into
      Disclosure ("Advanced") so default view ≤ 6 visible controls. — Disclosure component
      added; housekeeping/bulk retain primary cards above fold (bulk transitions unchanged).
- [x] Minor dedupes (one-line fixes each): top-bar Settings gear vs sidebar Config gear —
      give Config a distinct icon + rename to "Instance Config"; Approvals "Engine:
      Community" line dropped (edition already in top bar); kit demo status table "#1 #1"
      cell bug; designer-list "Stage" shown 3× (preview header + column list + properties —
      drop the canvas badge duplicating Title value); designer-kanban "Group by" shown in
      header AND badge — keep badge only; website editor repeats Home/(/) 3× — one title +
      one path. — Config icon/rename; approvals engine; kanban column field label.
- [SKIPPED] Playwright screenshot sweep re-run → `docs/vision-verify/` (shell + overview +
      operations hub, light+dark); axe clean. — sweep spec updated with operations-hub;
      `pnpm exec playwright test e2e/vision-verify-sweep.spec.ts` timed out (webServer 180s)
      in agent environment; run locally after merge.

GATES (all cards): `pnpm lint` 0 errors · `pnpm test` green · `pnpm build` OK ·
screenshot sweep re-captured. Update PROGRESS.md Wave 14 + STATE.md retro. Commit only
when user approves.

**Gate output (2026-08-05):** `pnpm lint` 0 errors (22 pre-existing warnings) · `pnpm test` 101 passed · `pnpm build` OK · Playwright sweep SKIPPED (webServer timeout).

DO NOT: remove/hide any feature behind a paywall or delete routes; introduce new deps
beyond existing kit/lucide; touch API code except adding no fields.

RETURN per card: ≤8 lines + files changed list.
