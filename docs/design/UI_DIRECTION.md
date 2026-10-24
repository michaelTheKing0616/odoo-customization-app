# Ingenium UI direction (NF stream)

Purpose: the patterns behind the winning X-ray screen (DEC-075). Every NF screen meets this floor and goes through the full trial process.
Tokens only: cite CSS variables from `apps/web/src/styles/globals/tokens.css` and `density.css`, or the Tailwind classes built on them. No raw hex.
Reference: `docs/design/bar/xray-floor.png`; code in `apps/web/src/app/e2e/trial-xray-grok/` (nf worktree).

## Compose from these shared components
- `Card`, `EmptyState`, `Skeleton`, `Kbd` (`@/components/ui/layout-primitives`) — panels, empty states, loading shapes, key hints.
- `Callout` (variant `warning`) — "you lack access" and "kept last data" notices.
- `ErrorNotice` — real failures only.
- `DataTable` (`density="compact"`) — every list of records.
- `Tabs`, `Select`, `Badge`, `Button`, `TechName` — sections, the 390 px "Show" switch, Example badge, actions, copyable Odoo names.
- `CommandPalette` + `useCommand` — screen actions also reachable from the keyboard.
- `DURATION`, `EASE_ENTER_EXIT` (`@/components/ui/motion/constants`), `usePrefersReducedMotion` — all motion.
- `toast` (sonner) — confirmations; in Example mode it says nothing was sent to Odoo.

## State design
Every screen draws six states: ready, loading, empty, partial, error, denied.
- Show per-area loading progress ("Reading 3 of 7 areas · about 2 min left") in a `Card`, with `Skeleton`s shaped like the final layout — applies to scans, reads, any job over 1 s.
- Partial results say how many areas were read and which was skipped and why; unknown is never shown as zero — applies to scans, fit-gap, migration reports.
- Errors keep the last good data on screen, stamped with its time in WAT ("From 22 Oct, 10:41 WAT. Odoo is not answering now.") — applies to every report that has a previous run.
- "You lack access" is amber: `Callout variant="warning"` using `--warning-subtle` / `--warning-strong`, naming the missing Odoo group via `TechName` and one fix — applies to denied reads and missing rights.
- Red (`--danger`, `--danger-subtle`, `--danger-strong`, `ErrorNotice`) is only for failures; never for access, warnings or risk counts — applies everywhere.
- Empty states use `EmptyState` with one clear primary action and one plain sentence — applies to first runs and filtered-to-nothing lists.
- Success ticks use `--success-strong`, small and quiet — applies to completed areas and checks.

## Density and type scale
- Use the density scale only: `text-ui-display` (page title), `text-ui-title` (section), `text-ui-body` (rows, copy), `text-ui-label` (meta, headers) — applies to all NF screens.
- Big numbers are `text-2xl font-semibold` with `--tracking-title`; nothing larger in an app screen — applies to summary grids.
- All numbers, times, dates and counts use the `.tabular` class (tabular-nums) — applies to tables, grids, meta lines, legends.
- Text colours: `text-ink` (primary), `text-muted` (secondary), `text-subtle` (hints only) — applies everywhere.
- Surfaces: `--background`, `--surface`, `--surface-raised`, `--surface-muted`; borders `--border-subtle`, `--border-strong` — applies to panels and tables.
- Radius `--r-sm` / `--r-md`; shadow at most `--shadow-subtle` on flat panels — applies to cards and chips.

## Summary number grid (adopted from the Cursor entry)
- Key figures sit in a 2x2 grid at 390 px and 4 across from `sm` up, joined by 1 px `--border-subtle` gaps — applies to every report summary.
- Each cell: label in `text-ui-label text-muted`, value tabular, one short caption ("From the areas read" when partial) — applies to summary cells.
- A cell that opens detail is a button with `bg-surface-muted` hover and `--focus-ring` / `ring-accent` focus — applies to clickable cells.

## Breadcrumbs
- Every NF page starts with an `ol` breadcrumb: Connections › connection name › section, `text-ui-label text-muted`, current item `text-ink` — applies to all connection-scoped pages.
- Example data shows a `Badge` reading "Example" next to the title — applies to fixtures, demos, unverified values.
- The meta line under the title holds Odoo version, run time and duration, all tabular — applies to report pages.

## Composition bars
- Stock parts use neutral ink shades (`bg-ink/80`, `/55`, `/35`, `/20`) — applies to model, module and size breakdowns.
- Accent (`--accent`, `bg-accent`, `bg-accent/45`) only marks the highlighted category, e.g. custom — applies to every bar.
- Hovering or focusing a segment or its legend row dims the others to 30% opacity, both ways — applies to bar plus legend pairs.
- Legend rows show name, tabular count and tabular percent, right-aligned — applies to legends.

## Dark tables
- Use `DataTable` with hairline rows (`divide-border-subtle`), no zebra stripes — applies to all record lists, light and dark.
- Row hover tint is instant (`bg-surface-muted`, 100 ms at most) — applies to rows and risk lists.
- j / k move through rows like the arrow keys, ignored while typing in inputs; show the hint with `Kbd` — applies to every table and list.
- Odoo technical names go through `TechName` so they can be copied — applies to model, field, group and module names.
- Less important columns hide at small widths (`hidden sm:table-cell`, `lg:table-cell`) — applies to dates and secondary counts.
- In dark mode the same tokens apply; check contrast, never swap in custom colours — applies everywhere.

## 390 px behaviour
- Layout stacks to one column; headers wrap with `flex-wrap`; no horizontal page scroll — applies to every screen.
- Tabs become a `Select` labelled "Show" (adopted from the Cursor entry) — applies to any screen with more than 3 tabs.
- Summary grid goes 2x2; actions move below the title — applies to report headers.
- Tap targets at least 44 px tall; chips at least 28 px with padding — applies to buttons, chips, rows.

## Motion
- Animate transform and opacity only; never layout, width or colour sweeps — applies to all motion.
- Durations 150–250 ms: `DURATION.dropdownMs` for enter, `DURATION.modalMs` for bars and panels, `DURATION.staggerMs` between cells — applies everywhere.
- Ease is `EASE_ENTER_EXIT.bezier` (or `--ease-out-strong` in CSS); enter is a 4 px rise plus fade — applies to panels and cells.
- Under reduced motion every transition lands instantly (`duration: 0`, `motion-reduce:transition-none`) — applies to all motion, checked in each trial round.

## Copy
- Plain words a business owner understands; Odoo names appear only inside `TechName` — applies to titles, notices, buttons.
- Say what happened, why, and the one next step — applies to errors, denied and empty states.
- Anything not real is labelled "Example", and actions in Example mode say nothing was sent to Odoo — applies to fixtures and drafts awaiting adviser sign-off.
- Times are shown in WAT with the label — applies to stamps and meta lines.
- No jargon list words (payload, endpoint, ORM, null); the jargon check must pass — applies to all copy.

## Contrast
- A light background always gets dark text (`text-ink` or the matching `--on-*` token) — applies everywhere, no exceptions.
- Coloured fills pair with their `--on-*` token (`--on-accent`, `--on-warning-subtle`, `--on-danger-subtle`) — applies to badges, buttons, callouts.
- A disabled primary button becomes `variant="secondary"` with a reason, not a faded primary — applies to all primary actions.
- Focus is always visible via `--focus-ring` — applies to every interactive element.
- Body text meets WCAG AA in both themes; axe finds 0 issues per state, theme and size — applies to every trial round.

## Above the floor
The X-ray trial is the minimum. Every NF screen beats it on these rules too.
- Response budget: under 100 ms feels instant, so give feedback in that time; past 1 s show progress; past 10 s show progress plus time left and a way to leave — applies to every action and job [ux-copy-kb F-035].
- Optimistic update for reversible writes to Ingenium's own data; on failure roll back visibly with an `ErrorNotice` and Retry — applies to toggles, renames, overrides [playbook §dembrandt].
- Skeletons wait 300 ms before showing, then stay at least 500 ms so they never flash — applies to all loading [emil].
- No layout shift: skeletons and reserved boxes match final sizes, numbers are `.tabular`; CLS under 0.1, INP under 200 ms — applies to every route [taste §6.D].
- Submit stays enabled until the request starts, then shows a spinner beside the original label, with width kept — applies to every primary action [jk-accessibility].
- Focus: style `:focus-visible` only, a 2 px solid `--focus-ring` with offset, checked against every surface it crosses and in forced-colours mode — applies everywhere [jk-accessibility].
- Keyboard map: j/k for rows, Enter to open, Esc to close, / for search, ⌘K for `CommandPalette`, ? for a key list in a `Sheet` using `Kbd`; Tab only between widgets, using roving tabindex — applies to every NF screen [jk-accessibility].
- Overlays move focus in on open, mark the background `inert`, and return focus to the trigger on close — applies to `Dialog`, `Sheet`, `CommandPalette` [jk-accessibility].
- Keyboard-started actions and anything used 100 or more times a day get no animation: j/k, tab switches, opening the palette — applies to tables and the palette [emil].
- Reversible actions get an undo toast (`toast` via `AppToaster`, role `status`, polite) that stays until it's dismissed or replaced and pauses while the tab is hidden — applies to dismiss, archive, override, hide [jk-accessibility] [emil].
- `ConfirmDialogV2` only for actions that can't be undone; the button repeats the consequence ("Delete 3 drafts"), never a bare "Yes" — applies to destructive actions [ux-copy-kb F-044] [jk-writing].
- Numbers use `Intl.NumberFormat("en-NG")`; money is ₦ with two decimals; dates read "22 Oct 2026, 10:41 WAT" in `Africa/Lagos`; relative times carry the absolute time in a `Tooltip` — applies to all numbers, money and stamps [jk-typography].
- Truncate with ellipsis (`min-w-0` on the flex child) and keep the full value reachable in a `Tooltip` or expanded view; long Odoo names use `TechName`, and `overflow-wrap: break-word` stops IDs escaping their box — applies to tables, chips, breadcrumbs [jk-typography].
- Errors give what happened, why, and what to do, beside where it broke; no "please", "sorry", "oops", "invalid" or blame, and no exclamation marks — applies to every `ErrorNotice`, `Callout` and field error [ux-copy-kb F-081] [jk-writing].
- Buttons start with a verb, are 3 words or fewer and fit on one line, with one label per intent across the screen — applies to all actions [ux-copy-kb F-083] [taste §4.5].
- Progressive disclosure: answer first, then details in a `Disclosure` with a visible cue; at most one hidden level — applies to evidence, technical detail, advanced options [jk-layout].
- Spacing uses a 4 px rhythm; the gap between groups is at least twice the gap within one (8 then 16 px); space groups before drawing lines — applies to all layouts [jk-layout].
- Optical alignment: icon-side padding about 2 px tighter; icon stroke 1.5 px beside regular text and 2 px beside semibold; nested radius equals inner radius plus padding — applies to buttons, badges, cards [jk-ui].
- Type: weight 400 or more below 18 px; line height at least 1.4 on text that wraps to 3 lines or more; `text-wrap: balance` on headings and `pretty` on descriptions — applies to all text [jk-typography].
- States matrix for every control: hover only under `(hover: hover) and (pointer: fine)`; press `scale(0.96)`; focus-visible; disabled with the reason as text beside it, not in a tooltip; loading; selected with `--accent-subtle` and `--on-accent-subtle` — applies to buttons, rows, chips, tabs [jk-ui] [jk-accessibility].
- Status never relies on colour alone; each state change also leaves an icon or label — applies to badges, `StatusPill`, bars [jk-accessibility].
- At 390 px touch targets are 44 px or more with 12 px between bordered controls (pseudo-element hit areas never overlap); inputs use 16 px text; layout reflows at 320 px and 200% zoom — applies to mobile [apple-design-hig] [jk-accessibility].
- Print: `@media print` hides chrome, actions and toasts, expands every `Disclosure`, prints `--ink` on white, and stamps the connection, WAT run time and "Example" where it applies; CSV and PDF exports use the same labels and formats — applies to reports, fit-gap, scans [impeccable harden].
- Motion order: frame, then title and meta, then summary cells (stagger `DURATION.staggerMs`, 30–80 ms), then bars, then tables; stagger never blocks input — applies to first paint [emil] [web-motion-design].
- Timings: press 100–160 ms, tooltip 125–200 ms (no delay after the first one opens), dropdown 150–250 ms, panel 200–300 ms; hover and colour 150 ms or less; exits faster than entries — applies to all motion [emil].
- Easing: ease-out for enter and exit (`EASE_ENTER_EXIT`, `--ease-out-strong`), ease-in-out only for on-screen moves, popovers scale from their trigger and modals stay centred — applies to overlays and panels [emil].
- Use transitions, not keyframes, for anything triggered often so it can be interrupted; name the exact properties — applies to interactive states [jk-ui].
- Switching theme turns all transitions off for one frame so the page snaps — applies to the theme toggle [jk-ui].
- First value: an empty screen offers one primary action, shows progress after the click, and reaches the first useful number in 3 clicks or fewer; Example data only with its label — applies to each NF feature's first run [impeccable onboard].
- Success is quiet: a `StatusPill` or a toast, never a modal — applies to completed jobs [apple-design-hig].

## Evidence viewer (BV-UI)
- Answer one question first: "Did this change work?" with a status chip (icon plus words, never colour alone), then a 2x2 / 4-across number grid, then "What was checked" (one row per part), checks by change, and the screenshot timeline — applies to verify runs in Bots.
- A platform notice (saved fine, Odoo shows non-admins an Access Error) is an amber "Needs a person to look" `Callout`, never red and never framed as a rollback — applies to every NEEDS_HUMAN reason.
- Skipped parts always say why ("Why skipped: ..."); a step with no screenshot says so in the preview box instead of leaving a gap — applies to layers and steps.
- Screenshot timeline is a listbox with roving tabindex: arrows, j/k, Home/End; the preview rises 4 px and fades in 200 ms and lands instantly under reduced motion; the j/k hint hides below `sm` — applies to any step timeline.
- Evidence values whose key looks secret or personal (key, token, password, email, phone, login...) render as "hidden"; Odoo names render via `TechName` — applies to check evidence.

## Anti-patterns (banned)
- `transition: all`, ease-in on UI, entering from `scale(0)`, animating width, height or margin [emil].
- Animation on keyboard-started or high-frequency actions; hover effects without the fine-pointer media query [emil].
- A confirm dialog for a reversible action; a disabled submit before the request starts [ux-copy-kb F-044] [jk-accessibility].
- Placeholder used as a label; `div` with onClick; `outline: none` with no replacement; positive tabindex [jk-accessibility].
- Em or en dashes, "please", "sorry", "oops", "invalid", "Click here" or a bare "Learn more" in UI copy [taste §9.G] [ux-copy-kb F-081].
- Status shown by colour alone; red for missing access; accent on static text [jk-colors].
- Decorative status dots, score bars on filled tracks, and hairlines under every row of short lists [taste §9.F].
- Fake-precise numbers without an "Example" label; generic names like "John Doe" or "Acme" in fixtures [taste §9.D].
- Truncated text with no way to read the full value; content hidden with no visible cue [jk-interface].
- Raw hex or primitive ramps (`--n1`…, `--accent1`…) used directly in components; use the role tokens [jk-colors].

## Beat-the-floor checklist (every UI Worker packet answers each item with evidence)
1. Six states × light/dark × 390/1280 contact sheet attached, with its path.
2. Loading: the 300 ms delay and 500 ms minimum in code (line); CLS measured under 0.1; INP under 200 ms.
3. Keyboard-only walk done: map listed, ? help opens, focus ring screenshots on light and dark, focus returns after each overlay.
4. States matrix filled for every control (table); hover gated (grep).
5. Undo toasts used for reversible actions; each `ConfirmDialogV2` justified in one line.
6. en-NG number, ₦ and WAT date samples pasted from the running screen.
7. Longest real Odoo model and field name rendered; truncation plus `Tooltip` screenshot.
8. Every error string quoted and checked against the what, why and what-to-do formula and the banned words.
9. 390 px targets measured at 44 px or more; no horizontal scroll at 320 px or 200% zoom.
10. Motion: order and timings listed; grep shows no `transition: all` or ease-in; reduced-motion recording.
11. Print preview PDF attached for report screens; export sample attached.
12. Spacing and optical alignment shown with an overlay or zoomed crop.
13. First value: click count stated; Example labels visible.
14. Anti-pattern grep clean (dashes, banned words, raw hex, primitive tokens).
15. Two concrete ways this screen beats `docs/design/bar/xray-floor.png`.

## Changes
- 2026-10-22 — Initial version, from DEC-075 (Grok X-ray trial entry won). Adopted the Cursor entry's 2x2 number grid and "Show" select at 390 px.
- 2026-10-22 — Above-the-floor rules added: perceived performance, keyboard map, undo, en-NG/WAT formats, truncation, error formula, disclosure, spacing, states matrix, touch, print/export, choreography, first value; Beat-the-floor checklist for UI Worker packets.
- 2026-10-22 — Sharpened from the full skills: exact timings, response budget, focus and overlay rules, persistent undo toasts, banned words; added Anti-patterns (banned).
- 2026-10-24 — BV-UI evidence viewer entry: verify-run answer-first layout, amber platform notices, timeline keyboard map, evidence masking.
