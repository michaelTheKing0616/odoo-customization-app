# UI-F05 — Tabs on Base UI evidence (2026-10-05)

Scope: `apps/web/src/components/ui/Tabs.tsx`. That is the only file the card allows. Its public API (`Tabs({ items, defaultValue, value, onValueChange, className })` and `TabItem`) is unchanged, so none of the five callers changed.

- The Base UI swap (`@base-ui/react` 1.8.0) and the Radix removal were already done in `65fbcbd`. `rg -l "@radix-ui" apps/web/src` returns nothing, and `package.json` has no `@radix-ui/react-tabs`. That commit also added `Tabs.test.tsx` (aria-selected, roving tabindex, ArrowRight).
- Base UI already provides `role="tablist"`, `role="tab"`, and `role="tabpanel"`. It also sets `aria-selected`, roving `tabindex`, `aria-controls` on the selected tab, and `aria-labelledby` on its panel. Inactive panels are unmounted, so `aria-controls` never points at a missing id.
- This pass adds three things:
  - A focus-visible ring on tabs and on the panel (`ring-2 ring-accent ring-offset-2`), the same studio token ring that `Input`, `Select`, and `Textarea` use. The panel needs it because Base UI makes the panel focusable (`tabindex="0"`).
  - A Base UI `Tabs.Indicator`: a 2 px `bg-accent` bar under the selected tab. It is 1 px wide and reaches the tab only through `translate(...) scaleX(width)`, so moving between tabs of different widths animates `transform` and never `width` or `left`. Motion uses the UI-F09 constants: 200 ms (dropdown range) with `EASE_ENTER_EXIT`. It stays at opacity 0 until Base UI has measured the tab.
  - With reduced motion, the indicator transition is opacity only at 200 ms, so the bar jumps to the new tab instead of sliding.

Evidence comes from `apps/web/e2e/a11y-ui-f05.spec.ts`. It ran against `pnpm dev` on `:3002` (`NEXT_PUBLIC_E2E=1`) on the `/e2e/kit` harness, which renders the kit `Tabs`. Desktop is 1440×900 and narrow is 390×844. Screenshots are viewport only, with the tabs scrolled into view.

## axe (wcag2a/aa, 21a/aa; same rule set as `a11y-primary.spec.ts`)

Raw results: `axe-results.jsonl`. Each state is scanned twice: the whole page (recorded) and the `[data-testid="tabs"]` subtree (gated).

| Route / state | Tabs subtree, desktop | Tabs subtree, 390 | Whole page, desktop | Whole page, 390 |
|---|---|---|---|---|
| `/e2e/kit`, Tab B selected by keyboard, focus ring showing | 0 | 0 | 5 (outside tabs) | 5 (outside tabs) |
| `/e2e/kit`, Tab B selected by click, reduced motion | 0 | 0 | 5 (outside tabs) | 5 (outside tabs) |

The five page-level hits are all `color-contrast` (serious), and none are inside the tabs: four `CodeBlock` syntax tokens (`.attr-name.token`, `.attr-value.token`) and one `.text-success` node in the bulk result table. See "Pre-existing" below.

The same spec also asserts the following:

- Tab focus lands on the selected tab (`tabindex="0"`; the other tab is `-1`). Its `aria-controls` equals the panel `id`.
- ArrowRight moves focus and selection to Tab B. The panel text changes, `aria-labelledby` follows, and the focused tab has a non-`none` `box-shadow` (the ring). The indicator's x position settles on Tab B.
- Home selects the first tab, and End selects the last tab.
- With reduced motion, the computed indicator `transition-property` is `opacity` at 200 ms or less.
- With full motion, it is `transform, opacity`. Every duration is under 300 ms, and the computed `width` does not change when selection moves.

## Screenshots

- `kit-tabs-keyboard-{desktop,390}.png`: Tab B selected with ArrowRight. The focus ring and the accent indicator show under Tab B.
- `kit-tabs-reduced-{desktop,390}.png`: Tab B selected by click with reduced motion emulated.

## UX audit (12 rows, `T7_UI_MOTION_COPY.md`)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | The selected tab has the `accent-subtle` fill and a 2 px accent underline. Inactive tabs stay `text-muted`. The panel follows. |
| IA | Not observable | No tab labels or order changed. |
| Interaction | Pass | Arrow keys, Home, and End move focus and selection (activate on focus). Click still selects. Only the selected tab is in the Tab order. |
| Feedback | Pass | The underline slides to the new tab in 200 ms. CSS transitions reverse mid-flight, so fast arrowing is interruptible. |
| Errors | Not observable | Tabs have no error states. |
| Accessibility | Pass | Roles, `aria-selected`, `aria-controls`, and `aria-labelledby` come from Base UI. The indicator is `role="presentation"`. Focus-visible rings on tabs and panel. axe on the tabs subtree is 0 at both widths. |
| Cognitive load | Pass | One added element: a thin underline. No new controls. |
| Trust | Pass | The labels and content come from the callers unchanged. |
| Copy | Not observable | No visible strings changed in this card. |
| Forms | Not observable | No form fields were changed. |
| Performance | Pass | Only `transform` and `opacity` animate, never `all`, `width`, or `left`. Reduced motion is opacity only at 200 ms or less. |
| Business goal | Pass | Keyboard users get a visible focus ring and a clear selected state on every tabbed screen. |

Not observable from screenshots: screen-reader announcement wording, latency.

## Pre-existing, not counted against this card

- On `/e2e/kit`, the `CodeBlock` syntax colors (`.attr-name.token`, `.attr-value.token`) and a `.text-success` label in the bulk result table fail `color-contrast` (serious). Those components are outside this card's "Change".
- At 390 px the `/e2e/kit` page overflows horizontally (CodeBlock, DataTable, and button row). The tabs themselves fit.
- `src/components/projects/ProjectDiffPanel.test.tsx` › "elevates a trustworthy change review with sentence-case filters" fails. The test expects "Promote stays human", but the committed copy in `ProjectDiffPanel.tsx` says "Apply/Promote stay human." Neither file is modified in the working tree. It is unrelated to Tabs.
