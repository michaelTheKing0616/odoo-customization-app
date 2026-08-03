# Wave 6 — UIX: UI/UX revamp (premium identity, complete specification)

Shared context: target feel = calm precision (Anthropic warmth, Linear density, Stripe
clarity). Keep Odoo-familiar STRUCTURAL conventions (breadcrumbs, control panel, one primary
button) per compendium §20; identity is OURS — never Odoo's purple. Principles binding every
card: one primary action per screen; density with air (4px grid); honesty states are designed
first-class states; progressive disclosure (Advanced toggles); never block without why +
options. Copy: `plans/COPY_GUIDE.md` is law. New deps allowed (MIT): `radix-ui` primitives,
`lucide-react`, `cmdk`, `@tanstack/react-query`. Gates for every UIX card: `pnpm lint`,
`pnpm test`, `pnpm test:e2e` relevant specs, vision-verify screenshots
(`skills/vision-verify-ui.md`) attached to the return.

---

## UIX-1 — Design tokens, typography, dark mode foundation

TASK: Token system + fonts + dark mode plumbing, replacing ad-hoc styles at the root.

INPUT: `apps/web/src/app/globals.css`, `layout.tsx`, Tailwind v4 setup.

CHECKLIST:
- [ ] Neutral scale (warm gray, 12 steps) as CSS custom properties `--n1..--n12`
      (light: paper `#FAF9F7` → ink `#131211`; dark: charcoal inversion, NOT pure black);
      accent teal ramp `--accent1..--accent10` anchored ~`#0E7569` (hover/active/subtle
      surface steps); semantic ramps: success (green), warning (amber), danger (red), info
      (blue) — 5 steps each; ALL light/dark pairs meet WCAG AA for their intended text/bg
      role (document the contrast table in a comment).
- [ ] Tailwind v4 `@theme` bindings so utilities consume tokens (`bg-surface`, `text-ink`,
      `border-subtle`, `bg-accent`, etc. — naming table in file header).
- [ ] Typography: Inter via `next/font` (system-stack fallback) for UI; Fraunces retained for
      marketing display ONLY (landing); JetBrains Mono for code/XML/JSON/domain strings.
      Scale: 12/13/14(base)/16/18/22/28/36 with paired line-heights; tokens
      `--text-xs..--text-3xl`.
- [ ] Radius 6/10/16 (`--r-sm/md/lg`), shadows 3 elevations (subtle, raised, overlay),
      motion tokens 120/200/300ms ease-out + `prefers-reduced-motion` kill-switch,
      focus ring token (2px accent, offset 2).
- [ ] Dark mode: `class` strategy on <html>, system-preference default, persisted override
      (localStorage), no-flash inline script in layout.
- [ ] Purge legacy: old `--odoo-primary` purple-plum vars removed/aliased with a migration
      note; existing pages must still render (aliases keep them working until UIX-4*).
- [ ] Visual sanity page `/e2e/tokens` (E2E-gated like existing harnesses) rendering the full
      palette/type/spacing for vision-verify.

DONE MEANS: tokens page screenshots (light + dark) pass vision-verify; all existing pages
still render (Playwright smoke).

DO NOT: restyle feature pages here; introduce any purple-brand color; hardcode hexes outside
the token file.

GATE: pnpm lint/test/e2e smoke + screenshots.

RETURN: ≤10 lines + screenshot paths.

DEVIATIONS: conservative + log.

---

## UIX-2 — Component kit + icon system

TASK: Build `apps/web/src/components/ui/` — the 20-component kit with exact contracts, plus
the icon mapping.

INPUT: UIX-1 tokens; Radix/lucide/cmdk deps; existing components (ConfirmDialog,
DomainBuilder — to be wrapped/restyled, not discarded).

CHECKLIST (a component checks off only with its Vitest coverage):
- [ ] Button: variants primary/secondary/ghost/danger; sizes sm/md; loading (spinner +
      disabled); icon slot. ONE primary per screen rule documented in JSDoc.
- [ ] Input, Textarea, Select (Radix), Combobox (searchable, async options).
- [ ] Dialog (Radix, focus-trapped) + Sheet (side panel, right/left).
- [ ] Toast system (provider + useToast; success/error/info; action slot).
- [ ] Tabs (Radix).
- [ ] DataTable: sticky header, column sort, row selection with bulk-action bar slot,
      virtualization ≥200 rows (windowing — no new dep, simple slice-on-scroll or
      @tanstack/react-virtual if trivially available via query dep tree — decide + document),
      density toggle, loading skeleton rows, empty-state slot.
- [ ] Badge/StatusPill: semantic variants + specialized: GA / experimental / Tier 1 lock /
      Tier 2 shield / hosting (Online/sh/on-prem) / Internal (MON).
- [ ] Callout: info/warning/danger; title + body + optional actions — THE gating surface
      (three-options layout support).
- [ ] EmptyState: icon + teach-line + primary action (copy from COPY_GUIDE).
- [ ] Skeleton primitives; Tooltip (Radix); Kbd; Card; Breadcrumbs; PageHeader (title +
      actions right — the control-panel convention).
- [ ] CodeBlock: Shiki (or refractor) highlight for xml/json/python; copy button; line wrap
      toggle.
- [ ] DiffView: side-by-side + unified toggle, add/remove token colors (used by projects
      diff + snapshots).
- [ ] BulkResultTable: renders BulkRunResult (per-record ok/error, filters, retry-failed
      slot) — Doc 7 §10 contract.
- [ ] ConfirmDialog v2: wraps existing phrase-confirm logic; risk levels (danger = red
      header + consequences list + snapshot note); backward-compatible API so existing pages
      keep working before their migration.
- [ ] CommandPalette shell (cmdk): provider + registration API (`useCommand(group, items)`);
      wired fully in UIX-3.
- [ ] Icon module `src/components/ui/icons.ts`: lucide re-exports with the FIXED mapping —
      models=Database, fields=Columns3, views=LayoutPanelTop, menus=PanelsTopLeft,
      automations=Zap, approvals=CheckCheck, reports=FileText, access=Shield, import=Upload,
      bulk=Layers, snapshots=History, pipelines=GitBranch, expert=Sparkles, connection=Plug,
      sandbox=FlaskConical, config=Settings2, housekeeping=Brush, cron=Clock,
      dedupe=Combine, id-generator=Hash. No icon used outside this module.
- [ ] Storybook-less showcase page `/e2e/kit` for vision-verify (all components, both themes).

DONE MEANS: kit page screenshots pass vision-verify (light+dark); every component has Vitest;
zero existing-page breakage.

DO NOT: adopt shadcn wholesale (hand-rolled on Radix per above); use any icon outside the
mapping; break existing ConfirmDialog callers.

GATE: pnpm lint/test + e2e kit page + screenshots.

RETURN: ≤10 lines + screenshot paths.

DEVIATIONS: conservative + log.

---

## UIX-3 — App shell: sidebar, top bar, command palette, Expert mount

TASK: New persistent shell for all `/connections/[id]/*` routes + global navigation chrome.

INPUT: UIX-1/2; `apps/web/src/app/connections/[id]/` (add `layout.tsx`); `src/lib/api.ts`;
TIER-1 matrix endpoint; @tanstack/react-query.

CHECKLIST:
- [x] `connections/[id]/layout.tsx`: left sidebar with grouped nav — Overview · Build
      (Models & Fields, View Designer, Menus, Automations, Approvals, Reports, Access) ·
      AI (Draft Studio, ModuleSpec, Projects, Odoo Expert) · Data (Import, Seed Packs,
      ID Generator) · Operate (Bulk Suite, Power Ops, Cron Manager, Housekeeping, Reminders) ·
      Govern (Snapshots & Journal, Config, Pipelines). Collapsible (icon-only mode,
      persisted); active states; icons from the mapping.
- [x] Capability-aware nav: matrix-gated items render with a lock badge and open a Callout
      explaining why + options (never hidden). Items for not-yet-built pages (Approvals,
      Bulk Suite, etc.) appear only once their wave ships — nav config is data-driven
      (`src/lib/nav.ts`) so later cards add one entry.
- [x] Top bar: connection switcher (name, version pill, hosting badge, GA/experimental);
      Cmd+K button; Expert toggle; dark-mode toggle; settings avatar menu. Breadcrumbs row
      beneath (route-driven).
- [x] Command palette: navigation (all nav items), jump-to-model (introspection-fed, cached
      via react-query), actions registered by pages (Snapshot now, New field…); shortcuts:
      Cmd+K, g+letter group jumps, ? opens shortcut sheet.
- [x] Expert mount: right Sheet slot + `ShellContext` provider (route, connectionId,
      currentModel?, draftSummary?) that pages can populate — EXP-5 consumes; renders a
      placeholder "Expert arrives in Wave 5" state if EXP not yet shipped (honest, not
      broken).
- [x] React Query provider at shell level; connection meta + capability matrix fetched once,
      shared; error boundary + offline banner.
- [ ] Old per-page header/nav removed where the shell now provides it (pages keep content
      only — minimal edits here; full migrations are UIX-4*).
- [x] Playwright: nav all groups, palette navigation, keyboard shortcuts, gated-item callout,
      theme toggle; vision-verify light+dark.

DONE MEANS: every existing page reachable through the new shell with zero functional
regression (full e2e suite green).

DO NOT: rewrite page bodies here; hide gated features; hardcode nav (data-driven).

GATE: pnpm lint/test + FULL existing e2e suite + screenshots.

RETURN: ≤10 lines + screenshot paths.

DEVIATIONS: conservative + log.

---

## UIX-4a — Page migrations: landing, connect, overview, Draft Studio

TASK: Migrate the entry funnel + AI surface onto the kit with the specified layouts.

INPUT: UIX-1/2/3; pages `page.tsx` (landing), `connect/`, `connections/[id]/` (hub),
`connections/[id]/wizard/`; COPY_GUIDE.

CHECKLIST:
- [ ] Landing: restrained premium marketing — Fraunces display headline, one accent, real
      product screenshots (capture from the running app), feature triad (Build / Operate /
      Expert), honest tier-coverage strip (Online/sh/Community/Enterprise), single primary
      CTA ("Connect your Odoo"); footer with docs links. No gradient soup, no emoji.
- [ ] Connect: 3-step wizard — (1) credentials form with inline validation + help
      ("where do I find my API key" expander); (2) probe progress with live capability
      readout streaming in (version, hosting, edition, notable modules); (3) summary "what
      you can do here" tuned from the matrix + primary action → Overview. Edit/delete flows
      kept; errors get recovery copy.
- [ ] Overview (replaces hub top): health header (connection status, version + upgrade
      banner from TIER-4, hosting/edition badges), stat cards (models/views/automations/
      snapshots counts), recent journal strip, quick actions; metadata browser below as
      kit DataTables (modules/models/fields/views tabs) with search + tier badges (PCM-4);
      export/sandbox/promote panel restyled with per-tier deployment states (TIER-2).
- [ ] Draft Studio (wizard rebuild): prompt composer (textarea + ambition selector + reuse
      chips redesigned); staged progress rail — Entities → Fields → Relationships →
      Workflow → Automations → Views with live per-step status/timing (poll job or staged
      events; single-pipeline renders consolidated steps honestly); results: model cards
      grid, warnings as designed Callouts (generation-gap, pack-merge notes), refusal panel
      (PCM-3), draft actions (Review in ModuleSpec / Generate UI / Export) with ONE primary;
      template gallery (app_templates) as cards with preview counts.
- [ ] All four pages: empty/loading/error states per COPY_GUIDE; react-query for data;
      Playwright per page incl. draft flow with mocked API; vision-verify light+dark.

DONE MEANS: four pages fully on kit, zero legacy classes, e2e + screenshots pass.

DO NOT: change API contracts (UI-only unless a card said otherwise); regress any existing
flow covered by e2e.

GATE: pnpm lint/test/e2e + screenshots.

RETURN: ≤10 lines + screenshots.

DEVIATIONS: conservative + log.

---

## UIX-4b — Page migrations: designer, projects, automations, access

TASK: Migrate the four builder-heavy pages.

INPUT: UIX-1/2/3; `designer/`, `projects/`, `automations/`, `access/` pages + components.

CHECKLIST:
- [ ] Designer: full-bleed three-pane — left palette (curated widgets per field type,
      Advanced toggle per compendium §15; CMP-3 will extend items), center canvas (existing
      FormCanvas/Kanban restyled on tokens; keyboard reordering: arrow keys move selected
      node — a11y requirement), right inspector (props, conditional attrs hook for CMP-2);
      top toolbar: view-type switcher, undo/redo, preview, snapshot, Open in Odoo; unsaved-
      changes guard.
- [ ] Projects: DiffView side-by-side (spec vs live) replacing text lists — conflicts /
      creates / existing as filterable diff sections; apply flow with dry-run validator
      results (TIER-2) inline.
- [ ] Automations: visual chain layout trigger → condition (DomainBuilder restyled) →
      actions (ordered cards); capability-gated triggers show lock + Callout (matrix);
      Option A code path visually distinct ("exports as module — review required" banner);
      advanced-confirm dialogs on ConfirmDialog v2.
- [ ] Access: matrix-first (the access matrix as the landing tab, editable grid), groups
      tab with visual hierarchy tree (implied groups as indented tree, read-only v1), ACL +
      record-rule forms on kit; danger states for global rules (compendium §6 warning
      surfaced as a Callout when creating a no-group rule).
- [ ] States/copy/query migration + Playwright per page (designer keyboard test included) +
      vision-verify.

DONE MEANS: four pages migrated, designer keyboard-operable, e2e + screenshots pass.

DO NOT: alter arch-generation logic; drop any existing designer capability.

GATE: pnpm lint/test/e2e (incl. existing designer specs) + screenshots.

RETURN: ≤10 lines + screenshots.

DEVIATIONS: conservative + log.

---

## UIX-4c — Page migrations: operate + govern + remaining

TASK: Migrate power-ops, journal, import, reports, menus, config, reminders, modulespec,
settings, pipelines onto the kit; build the Bulk Suite page chrome.

INPUT: UIX-1/2/3; the listed pages; BLK backend endpoints (whatever has shipped — page
sections appear per shipped card, nav-driven).

CHECKLIST:
- [ ] Power Ops: recipe cards with risk badges (danger zone section), dry-run-first flow
      enforced in UI, BulkResultTable for outcomes, capability chips per recipe.
- [ ] Bulk Suite page: sectioned host for BLK-1/2/3/6/7 tools (each section = picker →
      dry-run → confirm → BulkResultTable pattern, shared subcomponents).
- [ ] Journal: timeline layout (snapshots + audit merged chronologically, filter chips),
      rollback with reversibility honesty labels (`yes`/`partial` badges + explanation).
- [ ] Import: stepper (upload → map → validate → commit) with per-row error table;
      seed packs as cards. ID Generator page (BLK-9) on the same patterns.
- [ ] Reports/menus/config/reminders/modulespec/settings/pipelines: restyle onto kit
      (PageHeader, DataTable, forms, Callouts) — no logic changes; pipelines gets a
      stage-flow visual (sandbox → staging → prod cards with hop history).
- [ ] States/copy/query migration + Playwright smoke per page + vision-verify on power-ops,
      journal, pipelines.
- [ ] Legacy purge: after this card, zero remaining pre-kit styling (grep for legacy class
      names documented in UIX-1's migration note — must return empty).

DONE MEANS: all pages on kit; legacy-style grep empty; full e2e green.

DO NOT: change any endpoint behavior; leave a page half-migrated.

GATE: pnpm lint/test + FULL e2e + screenshots.

RETURN: ≤10 lines + screenshots.

DEVIATIONS: conservative + log.

---

## UIX-5 — Copy application pass + iconography audit

TASK: Apply COPY_GUIDE across every surface and verify icon-mapping compliance.

INPUT: `plans/COPY_GUIDE.md`; all pages/components post-migration.

CHECKLIST:
- [ ] Sweep every user-facing string: sentence case; verb-first buttons; destructive scope
      stated ("Delete 214 records"); no "Submit/OK/Oops"; no exclamation marks; no emoji;
      glossary terms only (Draft/Apply/Promote/Snapshot/Rollback/Sandbox/Recipe).
- [ ] Every gating message uses the three-part template (what → why → options); enumerate
      all instances in the return (there must be one per matrix-gated feature).
- [ ] Every page has designed empty/loading/error states with COPY_GUIDE copy (audit table:
      page × state — no cell empty).
- [ ] Error toasts name recovery ("Retry", "Check connection", "Diagnose with Expert").
- [ ] Icon audit: grep for lucide imports outside `ui/icons.ts` → empty; every icon-only
      button has aria-label + Tooltip.
- [ ] a11y sweep: axe run (Playwright @axe-core) on the 8 primary pages — zero serious/
      critical violations.

DONE MEANS: audit tables complete (strings, states, gates); axe clean; grep checks empty.

DO NOT: reword technical terms away from the glossary; touch backend strings that appear in
API contracts/tests without updating both.

GATE: pnpm lint/test/e2e + axe report + audit tables in return.

RETURN: audit tables + ≤10 lines.

DEVIATIONS: conservative + log.
