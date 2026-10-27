---
name: ingenium-ui-excellence
description: Use for every Ingenium UI build or change (any screen, component, state, copy or motion in apps/web), including ui-spec and ui-build cards, NF UI cards and UI reviews. The X-ray trial screen is the absolute floor; every screen must beat it. Self-contained: all craft rules are written out here.
---

# Ingenium UI excellence

Goal: the most beautiful, calm and easy-to-use product UI we can ship. The X-ray trial screen
(`docs/design/bar/xray-floor.png`) is the minimum. A screen that only matches it is not done.
Ingenium is an Operate product: people come to finish a task. Scanability, consistency and trust
beat expression. Brand lives in precise details, not decoration.

## 0. Mandatory reads (before touching code)

Read these in the main tree, in this order, every time:
1. `docs/design/UI_DIRECTION.md`: the X-ray patterns, Above-the-floor rules, anti-patterns and the Beat-the-floor checklist.
2. `docs/design/bar/xray-floor.png`: the floor. Look at it at full size.
3. `AGENTS.md` § UI bar: Operate screens are dense and calm, on studio tokens, Base UI and Sonner; no second visual language.
4. `docs/build-plan/07_UI_EXCELLENCE_PROTOCOL.md` §1 (principles), §3 (shared states), §4 (per-screen process), §5 (surpass bars), §6 (reviewer checklist).
5. `docs/build-plan/UI_REFERENCE_MAP.md`: your screen's area row and its two references.
6. `docs/design/references/ingenium-ui/<area>/`: the official captures, `REFERENCE_NOTES.md`, `MANIFEST.md`, `MOTION_NOTES.md`.
7. `docs/brand/README.md`: `BrandMark` follows the theme; never invert the mono mark.
If a file is missing, say so in the packet. Don't guess what it would say.

## 1. Process (follow every step, in order)

### Step 1: study, then write the design intent (5 lines)
- Open both references for the area. Write down 3–5 patterns to adopt (layout rhythm, density, type scale, hover/focus, transitions) and what is deliberately different. Never copy logos, colours, copy, pixel layouts or vendor assets.
- Write a 5-line design intent at the top of the spec (`docs/design/specs/<screen>.md`):
  1. Job: what the user finishes here, plus the one primary action.
  2. Hierarchy: the one hero element, the support elements, and what stays quiet.
  3. Density: Comfortable or Compact, with the row height and type sizes.
  4. Motion: what moves, and why (feedback, state change, or spatial continuity only).
  5. Beat the floor: two concrete ways this screen will be better than the X-ray floor.

### Step 2: design every state (B1)
Design and write real copy for every state before building. A missing state is a failed card.
- ready, loading (per-area progress), empty (first run), empty (filtered to nothing), partial, error (keeps the last data), offline, denied (no permission), too much data, read-only, success.
- Each state names its one action. Put each one in a states preview route so it can be screenshotted.
- Add the keyboard map, the a11y notes, the responsive plan (320/390/768/1024/1440/1920) and dark parity to the spec.

### Step 3: build in four stages (don't mix them)
1. Structure: semantic HTML landmarks, one `<h1>`, headings in order, DOM order equals reading order, real `<button>`/`<a>`, all states rendered from fixture data. No styling beyond layout.
2. Logic: data, loading and error paths, optimistic updates and rollback, keyboard handlers, focus management, URL holds view state (tab, filter, sort, selection).
3. Styling: tokens only, the density scale, spacing rhythm, both themes, 390 and 320 layouts.
4. Polish: motion, the interaction-state matrix, optical alignment, truncation and tooltips, copy pass, print styles.
Commit nothing between stages yourself; git belongs to Tope's process.

### Step 4: look, compare, fix (up to 6 rounds)
Each round:
1. Capture the matrix: 1440×900 and 390×844, light and dark, for every state (Playwright screenshots into a scratch folder outside the repo, deleted on close).
2. Put the captures beside the two references and `xray-floor.png`.
3. Compare in this order and write the gaps down as a numbered list:
   - Hierarchy: is the job obvious in 3 seconds, with one hero and one primary action?
   - Density and rhythm: 4 px grid, gap between groups at least 2× the gap within one, aligned edges.
   - Type: scale steps, weights, tabular numbers, wrapping, truncation.
   - Colour: one accent meaning, a light background always with dark text, status colours used only in their roles.
   - States: every state present, the error keeps data, denied is amber, empty has one action.
   - Dark mode: same hierarchy, no glare, borders visible.
   - 390: no horizontal scroll, 44 px targets, "Show" select in place of tabs.
   - Motion (live, at 10% speed in DevTools): order, timings, no layout animation, reduced motion.
   - Copy: plain words, verbs on buttons, no banned words.
4. Fix every gap in one batch, then re-capture.
Round 7 is not allowed: stop and report. The packet lists each round's gaps and fixes.

### Step 5: T0 gates (all must pass before any review)
- axe: 0 serious or critical issues for every state, theme and size (`@axe-core/playwright`; extend `apps/web/e2e/a11y-*.spec.ts`).
- Contrast: `src/lib/a11y/contrast.test.ts` and `src/lib/f1_contrast_tokens.test.ts` pass. Every text pair is AA (4.5:1 body, 3:1 for 18 px+ or 14 px bold, 3:1 for UI parts and focus rings). A light background always gets dark text.
- Jargon guard: `src/lib/jargon-guard.test.ts` passes; Odoo names appear only through `TechName` or `Term`.
- Reduced motion: emulate `prefers-reduced-motion: reduce`; everything lands instantly and nothing moves.
- Types: `pnpm --filter web typecheck` (`tsc --noEmit`) is clean in the files you touched.
- Also: `pnpm --filter web test` (vitest) passes for touched tests; `scripts/hex_lint_product.sh` and `test:legacy-colors` are clean; no hydration warnings; CLS < 0.05; INP < 200 ms at 4× CPU slowdown.

### Step 6: contact sheet
One sheet per screen in `docs/vision-verify/<screen>/sheet.png`: baseline, after and final; light and dark at 1440 and 390; every state labelled. The sheet also sits beside `xray-floor.png`. Rate states, density and hierarchy, dark mode, 390 and copy each as at, above or below the floor. Any "below" means CHANGES.

### Step 7: Worker packet (template, answer every line with evidence)
```
Card: <id>   Screen: <route>   Rounds used: n/6
Design intent: <5 lines>
References: <two areas/files>; adopted: <3–5 patterns>; different: <what and why>
Contact sheet: docs/vision-verify/<screen>/sheet.png
Floor rating: states <at/above>, density <>, dark <>, 390 <>, copy <>
Rounds: R1 gaps → fixes; R2 …
T0: axe 0 (<spec>), contrast (<test>), jargon (<test>), reduced motion (<how>), tsc clean, CLS <n>, INP <n>
Beat-the-floor checklist (UI_DIRECTION.md), one line of evidence each:
 1 sheet path · 2 skeleton 300/500 ms code line, CLS, INP · 3 keyboard walk, ? help, focus screenshots,
 focus return · 4 states matrix table, hover gated · 5 undo toasts, each ConfirmDialogV2 justified ·
 6 en-NG/₦/WAT samples · 7 longest Odoo name + Tooltip · 8 each error string vs formula ·
 9 44 px targets, 320 px and 200% zoom · 10 motion order/timings, grep no transition-all/ease-in,
 reduced-motion · 11 print PDF, export sample · 12 spacing/optical crop · 13 first-value click count ·
 14 anti-pattern grep clean · 15 two ways it beats the floor
Self-critique rubric: 7 scores (§3) with one sentence each
Files touched: <list>
```

## 2. Craft rules (all checkable)

### 2.1 Typography and type scale
- Use only the density scale: `text-ui-display` (20/28, page title), `text-ui-title` (16/24, section), `text-ui-body` (rows and copy), `text-ui-label` (12/16, meta and headers). Big summary numbers use `text-2xl font-semibold` with `--tracking-title`, and nothing bigger appears in app screens.
- Hierarchy comes from size and weight jumps of at least one step, not from boxes. A child heading never outweighs its parent.
- Weight 400 or more below 18 px. Weights under 300 only at 28 px+ (never in app UI).
- Line height: headings about 1.1–1.25; body 1.5–1.6; any text wrapping to 3+ lines at least 1.4, even in a dense row.
- Measure: long text capped at 60–75 characters (`max-w-[65ch]`).
- `.tabular` (tabular-nums) on every number, time, date, count, money and changing value.
- `text-wrap: balance` on headings, `text-wrap: pretty` on descriptions, `overflow-wrap: break-word` where IDs or URLs could escape, `whitespace-nowrap` on badges and short labels.
- Small uppercase labels get slight positive tracking (`--tracking-label`); use them for at most 1 label per 3 sections.
- Fonts are the repo's (`--font-sans`, `--font-mono`, `--font-display`); never add a font. Mono only for code and technical names.
- Text stored in natural case; casing done with CSS. Sentence case everywhere.
- Smart punctuation: curly quotes in prose, `…` (one character), `&nbsp;` between number and unit.
- Inputs use 16 px text on mobile so iOS doesn't zoom.

### 2.2 Spacing rhythm and layout
- A 4 px grid. Steps 4/8/12/16/20/24/32/48. No odd values.
- Group with space first, background second, lines last. The gap between groups is at least 2× the gap within one (8 then 16+).
- More space above a heading than below it.
- Pick alignment edges and keep them; every stray edge is a defect. Use logical properties (`ps-`, `pe-`, `ms-`, `me-`).
- Concentric radius: outer radius = inner radius + padding. One radius system: `--r-sm` for chips and inputs, `--r-md` for cards and panels, `--r-lg` for sheets and dialogs.
- Use a card only when elevation means hierarchy; otherwise `divide-y` or space. Shadow at most `--shadow-subtle` on panels, `--shadow-raised` on popovers, `--shadow-overlay` on dialogs.
- One job per screen, one filled primary action per view; peers are secondary or ghost.
- Order by importance: top and leading edge first. The primary action is never in a spot that scrolling or resizing can clip.
- Breakpoints come from the content: keep the wide layout while it fits, collapse late, and prefer container queries for components.
- No fixed width or height on text containers; let them wrap (translations grow).
- CSS grid, not flex percentage maths. `min-w-0` on flex children that truncate; `minmax(0,1fr)` tracks.
- Z-index only from the documented layers (sticky header, popover, dialog, toast).

### 2.3 Colour and contrast
- Tokens only. Surfaces: `--background`, `--surface`, `--surface-raised`, `--surface-overlay`, `--surface-muted`. Text: `--ink` (primary), `--muted` (secondary), `--subtle` (hints only). Borders: `--border-subtle`, `--border-strong`.
- A light background always gets dark text. Every fill pairs with its `--on-*` token: `--on-accent`, `--on-accent-subtle`, `--on-warning-subtle`, `--on-danger-subtle`, `--on-success-subtle`, `--on-info-subtle`, `--on-surface-muted`.
- One accent hue (`--accent`, `--accent-hover`, `--accent-subtle`), and it means "interactive or highlighted" everywhere. Never put accent on static text.
- Status roles only: `--success*` done; `--warning*` attention and "you lack access"; `--danger*` real failures and destructive actions only; `--info*` neutral notices. Within 15° of hue counts as the same colour, so status never collides with accent.
- Primitive ramps (`--n1`…`--n12`, `--accent1`…`--accent10`, `--danger-1`…) are never used in components; use role tokens.
- Colour is never the only carrier of meaning: add an icon, label or pattern.
- Contrast is measured on the background the text actually renders on, in both themes. A failing pair is reported and fixed by changing lightness, not hue.
- A disabled primary becomes `variant="secondary"` with the reason shown as text beside it.
- Focus ring uses `--focus-ring` and must reach 3:1 against every surface it crosses.

### 2.4 Density
- Operate screens are dense and calm: table rows 36–40 px Compact, 44–48 px Comfortable; panel padding 16–20 px; meta in `text-ui-label text-muted`.
- Dense means less chrome, not smaller targets: hit areas stay 24 px minimum on desktop (40 px preferred) and 44 px on touch, extended with a pseudo-element if needed.
- At most 4 key figures in a summary row; 2×2 at 390.
- No 20-row dumps in a summary: show the top 3–5 plus "View all" into the table view.

### 2.5 Interaction states (matrix, required for every control)
| State | Rule |
|---|---|
| Hover | Only under `@media (hover: hover) and (pointer: fine)`; tint to `bg-surface-muted` in ≤ 100 ms; no scale on hover in app UI |
| Active/press | `scale(0.96)` with a 100–160 ms ease-out transform; a `static` prop turns it off for rows |
| Focus-visible | 2 px solid `--focus-ring`, 2 px offset (inset inside tables); never `outline: none` without a replacement |
| Disabled | Native `disabled`, or `aria-disabled` when it must stay focusable; the reason is written beside it, never only in a tooltip |
| Loading | Spinner inside the control beside the original label; width kept; stays enabled until the request starts |
| Selected | `--accent-subtle` background with `--on-accent-subtle` text plus a check or bar, never colour alone |
| Error | `aria-invalid="true"`, `aria-describedby` to the inline message, focus moves to the first invalid field |
Icons use `currentColor`: outline by default, filled marks active. Stroke 1.5 px beside regular text and 2 px beside semibold; one icon set (`@/components/ui/icons`).

### 2.6 Keyboard and focus
- Every pointer action has a keyboard path. Tab moves between widgets; arrows move within composites using roving tabindex (`0` on the active item, `-1` on the rest); never a positive tabindex.
- The map, shown in a `?` help `Sheet` with `Kbd`: `j`/`k` rows, `Enter` open, `Esc` close, `/` search, `⌘K` `CommandPalette`, `?` help. Shortcuts are ignored while typing in an input.
- Every screen registers its actions with `useCommand` so ⌘K reaches them.
- Overlays (`Dialog`, `Sheet`, `ConfirmDialogV2`, `CommandPalette`) move focus in on open, set the background `inert`, use `overscroll-behavior: contain`, close on Esc and return focus to the trigger.
- A "Skip to content" link comes first when chrome precedes `<main>`. Anchored headings get `scroll-margin-top`.
- Live regions: `role="status"` (polite) for toasts and counts, rendered empty before text arrives; `role="alert"` only for urgent errors.
- Icon-only buttons have an `aria-label`; decorative icons get `aria-hidden`, never on focusable elements.

### 2.7 Motion
Personality: Corporate (calm and sharp). No overshoot or bounce on data or money.
| Use | Duration | Easing |
|---|---|---|
| Press feedback | 100–160 ms (`DURATION.pressMs` 130) | ease-out |
| Hover, colour | ≤ 150 ms, or instant | ease |
| Tooltip, small popover | 125–200 ms; instant after the first tooltip opens | ease-out |
| Dropdown, select, panel enter | 150–250 ms (`DURATION.dropdownMs` 200) | `EASE_ENTER_EXIT` / `--ease-out-strong` |
| Modal, sheet, bar grow | 200–300 ms (`DURATION.modalMs` 250, `drawerMs` 280) | ease-out (`EASE_ENTER_EXIT`) |
| Stagger between items | 30–80 ms (`DURATION.staggerMs`) | — |
| Exit | faster than enter (about 70%) | ease-out, small fixed `translateY`, never full height |
- Animate only `transform` and `opacity`. Never width, height, top, left, margin or padding. Never `transition: all`; name the properties.
- Never ease-in for UI. Ease-in-out only for an element moving on screen. Linear only for progress bars and spinners.
- Never enter from `scale(0)`: start at `scale(0.95)` with `opacity: 0`, and a 4–8 px rise. Popovers scale from their trigger (`transform-origin` at the trigger); modals stay centred.
- Frequency test: 100+ times a day (j/k, tab switch, palette open, row select) means no animation. Tens a day means ≤ 150 ms opacity or colour. Occasional (dialogs, toasts) gets standard motion. Rare (first run, success) can add one moment of delight.
- Keyboard-started actions never animate.
- Choreography on first paint: frame, then title and meta, then summary cells (staggered), then bars, then tables. One hero motion per screen. Stagger never blocks input. Under `AnimatePresence`, use `initial={false}` so in-page re-renders don't replay entrances.
- Transitions (interruptible) for interactive states; keyframes only for one-off staged sequences. Toasts enter and leave from the same edge.
- Every animated state change also leaves a static cue (colour, icon, label).
- Theme switch: turn transitions off for one frame so the page snaps, not smears.
- `will-change` only on transform or opacity, only when you see first-frame stutter.
- Reduced motion: read `usePrefersReducedMotion`; every transition takes `duration: 0` and every class gets `motion-reduce:transition-none`. Parallax, loops and autoplay are removed. Check it in every round.

### 2.8 Perceived performance (thresholds)
- Under 100 ms feels instant: every click gives visible feedback in that time (press state, optimistic change, or skeleton).
- 1 s keeps the flow of thought: past 1 s show progress. 10 s is the attention limit: past 10 s show progress, time left ("about 2 min left") and a way to leave or keep working.
- Skeletons wait 300 ms before appearing, then stay at least 500 ms so they never flash. They match the final layout exactly; no generic page spinner.
- Optimistic updates for reversible writes to Ingenium's own data; on failure, roll back visibly with an `ErrorNotice` and Retry. Never optimistic for writes to a client's Odoo.
- CLS < 0.05 (reserve sizes, tabular numbers, fixed skeleton heights). INP < 200 ms at 4× CPU slowdown. LCP < 2 s.
- Virtualise any list that can pass 200 rows; paginate server-side.
- A fast spinner feels faster than a slow one; spinners only inside buttons.

### 2.9 Forms
- Visible label above each input (`<label for>`), helper text below the label, error text below the input. A placeholder is an example (`name@example.com`), never the label.
- One column. Mark optional fields "(optional)"; never use asterisks alone.
- The right `type`, `inputmode` and `autocomplete`; never block paste.
- Validate on submit (and on blur after the first submit); keep values after an error; focus the first invalid field.
- Errors say how to fix, next to the field: "Use the Odoo database name, like acme-prod", not "Invalid database".
- Explain why we ask for sensitive data (API key, phone) in one helper line.
- Settings toggles describe the ON state ("Send weekly digest").

### 2.10 Tables (`DataTable`)
- Hairline rows (`divide-border-subtle`), no zebra stripes, no border above and below every row. Headers in `text-ui-label text-muted`.
- Numbers right-aligned and tabular; text left-aligned; one alignment per column.
- Instant row hover tint; j/k move the active row; Enter opens; the selected row keeps a visible marker.
- Sortable headers show their direction and announce it (`aria-sort`).
- Less important columns hide as the width shrinks (`hidden sm:table-cell`, `lg:table-cell`); the first column never hides. Tables may scroll sideways at 390; the page may not.
- Long Odoo names go through `TechName` (copyable, truncated with a `Tooltip`).
- The empty table says what's filtered and offers "Clear filters".

### 2.11 Empty, error, denied, partial
- Empty (first run): what this place is, how it fills, one primary action (`EmptyState`). No persistent information in an empty state. Example data only with an "Example" `Badge`.
- Empty (filtered): name the filter or query and offer "Clear filters".
- Error: keep the last good data on screen with a WAT time stamp ("From 22 Oct 2026, 10:41 WAT. Odoo is not answering now."), plus Retry. `ErrorNotice` only for real failures, in red roles.
- Denied: amber `Callout variant="warning"`, never red. Name the missing Odoo group with `TechName` and give one fix ("Ask your Odoo admin to add Settings access").
- Partial: say how many areas were read, which was skipped and why; unknown is never shown as zero.
- Offline: the banner stays until the connection returns; actions queue or disable with a reason.
- Success is quiet: a `StatusPill` or a toast, never a modal; sized to the stakes.

### 2.12 Copy
- Formula for errors: what happened, why, what to do, in one or two short sentences with one action. "Couldn't read Sales. Odoo timed out after 30 s. Retry, or read the other areas first."
- Formula for empty states: name, purpose, action. "No scans yet. A scan shows how your Odoo is set up. Run first scan."
- Buttons start with a verb, use 3 words or fewer, fit on one line, and use one label per intent across the app. A confirm button repeats the consequence ("Delete 3 drafts" / "Cancel").
- Address the reader as "you". In errors avoid "we". Name the actor; no actorless passive.
- Plain words a business owner understands; Odoo's own names for Odoo things (the glossary is law). Match the device: "select" when both touch and pointer apply.
- Never build sentences from fragments around a variable; use full templates with plural rules.
- Link text names its destination ("Read the API key guide"), never "Click here" or a bare "Learn more".
- Anything not real is labelled "Example"; Example-mode actions say nothing was sent to Odoo. No invented numbers.
- Tone: errors calm and plain; success and empty warm but brief; data loss and security serious and explicit.
- Banned words in UI copy: please, sorry, oops, invalid, forbidden, "you forgot", simply, just, seamless, effortless, unlock, elevate, empower, leverage, utilize, robust, cutting-edge, next-level, game-changer, delve, streamline, revolutionize, supercharge. Also banned: em dashes and en dashes as separators, exclamation marks in errors, all-caps sentences, emoji in chrome, "Let's…" openers, "Not just X, it's Y", forced groups of three, "I hope this helps".
- Times: absolute times in WAT with the label; relative times carry the absolute time in a `Tooltip`. Numbers in `en-NG` format; money as ₦ with two decimals.

### 2.13 Small screens and zoom (390, 320, 200%)
- 390: one column; header wraps; actions move under the title; summary grid 2×2; more than 3 tabs become a `Select` labelled "Show"; targets 44 px or more with 12 px between bordered controls; full-width buttons inset 16 px from the edges.
- 320: still no horizontal page scroll; nothing clipped or overlapping; long words wrap.
- 200% zoom on desktop: content reflows, no lost controls, `min-height` instead of a fixed height on text boxes.
- Safe areas: sticky bottom actions pad with `env(safe-area-inset-bottom)`.
- Tables may scroll inside their own box with a visible edge cue (the next column peeks 16–32 px).

### 2.14 Dark mode craft
- Designed alongside light from the first stage, never by inverting it. Same hierarchy: if the primary pops in light, it pops in dark.
- Depth comes from surface steps (`--background` → `--surface` → `--surface-raised` → `--surface-overlay`), not heavier shadows. Borders stay visible (`--border-subtle`).
- Reduce vividness of fills in dark; status fills use their `-subtle` tokens with `--on-*-subtle` text.
- No pure white body text and no pure black surfaces: use `--ink` and `--background` as defined.
- `BrandMark` follows the theme automatically; never `brightness-0 invert`.
- Every contrast pair re-measured in dark; screenshots in both themes for every state.
- One switching mechanism (the existing theme provider); no mixing `prefers-color-scheme` with a class.

### 2.15 Print and export
- `@media print`: hide nav, actions, toasts and tooltips; expand every `Disclosure`; `--ink` on white; no shadows; avoid breaking rows across pages; stamp the connection, the WAT run time and "Example" where it applies.
- CSV and PDF exports use the screen's labels, en-NG formats and WAT stamps.

### 2.16 Progressive disclosure and first value
- Answer first, details on request (`Disclosure`, `Sheet`); at most one hidden level, always with a visible cue.
- The path from empty to first value: one primary action → visible progress → the first useful number in 3 clicks or fewer, and the first successful check in under 5 minutes.

## 3. Self-critique rubric (score before the packet; minimums are binding)
Score 1–5 with one sentence of evidence each. Any score below its minimum means another round.
| Axis | 5 means | Minimum |
|---|---|---|
| Fidelity to references | Adopted patterns visibly present, the identity is Ingenium's | 4 |
| Hierarchy and density | Job obvious in 3 s, one hero, calm density, 4 px rhythm | 4 |
| States | All §2.11 states designed with real copy, the error keeps data | 5 |
| Dark mode | Equal quality to light, every pair passes | 4 |
| 390 px | Feels designed for a phone, not squeezed | 4 |
| Copy | Plain, verb-first, formula-true, zero banned words | 5 |
| Would I ship this | Beats the X-ray floor in at least two named ways | 4 |
Total must be 30 or more out of 35, and no axis may be "below floor" against `xray-floor.png`.

## 4. Anti-patterns (banned on sight)
- `transition: all`; ease-in; `scale(0)` entries; animating layout properties; bounce on data.
- Animation on keyboard-started or high-frequency actions; hover without the fine-pointer media query.
- Confirm dialogs for reversible actions; a disabled submit before the request starts.
- Placeholder as label; `div` with onClick; `outline: none` with no replacement; positive tabindex; `aria-hidden` on focusable elements.
- Status by colour alone; red for missing access; accent on static text; more than one filled primary per view.
- Generic page spinners; skeletons that don't match the layout; layout jumps on load.
- Truncation with no way to read the full value; content hidden with no cue.
- Decorative status dots, score bars on filled tracks, hairlines under every row of short lists, glow, glass or gradients in chrome, emoji in UI.
- Fake-precise or invented numbers without an "Example" label; "John Doe" or "Acme" in fixtures.
- Raw hex or rgb, primitive ramp tokens in components, a second visual language, new fonts.
- Banned copy from §2.12.
- Re-implementing a shared component that already exists (§5).

## 5. Repo rules
- Tokens only; no raw hex, rgb or hsl in components (`scripts/hex_lint_product.sh`, `test:legacy-colors`). Tokens live in `apps/web/src/styles/globals/tokens.css` and `density.css`; `.tabular` is in `base.css`.
- Verified token names: `--background --surface --surface-raised --surface-overlay --surface-muted --ink --muted --subtle --border-subtle --border-strong --accent --accent-hover --accent-subtle --on-accent --on-accent-subtle --brand --on-brand --success --success-subtle --success-strong --warning --warning-subtle --warning-strong --danger --danger-subtle --danger-strong --info --info-subtle --info-strong --on-warning-subtle --on-danger-subtle --on-success-subtle --on-info-subtle --on-surface-muted --focus-ring --r-sm --r-md --r-lg --shadow-subtle --shadow-raised --shadow-overlay --ease-out-strong --ease-in-out-strong --dur-fast --dur-base --dur-slow --tracking-title --tracking-label --font-sans --font-mono --font-display`, and the density sizes `--text-ui-display-size`, `--text-ui-title-size`, `--text-ui-label-size` (Tailwind `text-ui-*`).
- Compose these existing components (verified in `apps/web/src/components/ui/`); never rebuild them:
  - Layout and states: `Card`, `EmptyState`, `Skeleton`, `Kbd` (`layout-primitives`), `Callout`, `ErrorNotice`, `LoaderCallout`, `StatusPill`, `Badge`.
  - Controls: `Button`, `Select`, `Combobox`, `Input`, `Textarea`, `Tabs`, `Disclosure`, `Tooltip`.
  - Overlays: `Dialog`, `Sheet`, `ConfirmDialogV2` (with `useConfirmTarget`), `CommandPalette` + `useCommand`, `AppToaster` + `toast` (sonner).
  - Data: `DataTable`, `BulkResultTable`, `DiffView`, `CodeBlock`, `TechName`, `Term`.
  - Motion: `DURATION`, `EASE_ENTER_EXIT` (`motion/constants`), `usePrefersReducedMotion`, `Drawer`, `SheetMotion`; `motion/react` for animation.
  - Brand: `BrandMark` (`components/brand/BrandMark.tsx`).
  - Icons: `@/components/ui/icons` only.
- No new dependencies. The stack is already Base UI (`@base-ui/react`), `motion`, `sonner`, Tailwind and `@axe-core/playwright`.
- No Prettier. Use only the repo's own formatter and lint (`pnpm --filter web lint`).
- Don't run a plain `pnpm install`, and don't commit `pnpm-lock.yaml`.
- No secrets, `.env` files or client data in fixtures, screenshots or logs; fixtures are labelled Example.
- Ports and databases follow the build plan's reserved list; use disposable `ingenium_*` databases only.
- Git belongs to Tope: no commit, push, rebase, reset or stash from this skill.

## 6. Done means
All of these hold: every state designed; T0 green; the contact sheet saved and rated at or above the floor on every axis; rubric minimums met; the packet complete; nothing in §4 present.
