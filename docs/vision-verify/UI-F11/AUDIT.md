# UI-F11 — react-virtuoso for tables over 50 rows, evidence (2026-10-05)

Scope: `apps/web/src/components/ui/DataTable.tsx` and `BulkResultTable.tsx`. `BulkResultTable` renders through `DataTable`, so it needed no change. The public `DataTable` props are unchanged, so no caller changed.

- These parts were already done in `49bcefb` before this pass:
  - `react-virtuoso` is installed.
  - `DataTable` switches to `TableVirtuoso` when there are more than `DEFAULT_VIRTUALIZE_THRESHOLD = 50` rows (`shouldVirtualizeRows`). Callers can override this with `virtualizeThreshold`.
  - Tables with 50 rows or fewer render as a plain `<table>`.
  - The header is pinned with `fixedHeaderContent` plus `sticky top-0`.
  - ArrowUp and ArrowDown move the active row. In the virtual path, `scrollIntoView` brings it into view.
  - `DataTable.test.tsx` has the threshold, keyboard, and BulkResultTable tests, plus the 5,000-row sort and filter timing (0.2 to 1.5 ms per run, limit 100 ms).
  - Earlier today, `role="grid"`, `aria-rowcount`, `aria-activedescendant`, and `onKeyDown` were moved onto `<table>`. They stay there.
- This pass adds the following:
  - `aria-rowcount` now counts the header row (data rows + 1). The header row has `aria-rowindex="1"`, and each data row has `aria-rowindex = sorted index + 2`. That holds in both paths, so a screen reader still gets the true position while only around 10 of 5,000 rows are in the DOM. `aria-rowcount` is left off while loading or empty, so it never counts skeleton or empty-state rows wrong.
  - `aria-sort` (`none`, `ascending`, or `descending`) on sortable column headers.
  - Visible keyboard state:
    - The scroll frame shows the shared `--focus-ring` when the grid has `:focus-visible`. The global `:focus-visible { outline: none; box-shadow }` rule would otherwise be clipped by the scroll frame.
    - While focus is inside the table, the active row gets an `accent-subtle` tint and a 2 px inset accent bar on its first cell.
  - Removed `fixedItemHeight`. Virtuoso now measures each row, starting from `defaultItemHeight`. At 390 px, wrapped "Detail" text makes some bulk rows taller than 40 px, and a fixed height would put the scroll range out of step with the real rows.
- No motion was added. Rows do not animate (`getAnimations()` is 0), and nothing reveals on scroll.

Evidence comes from `apps/web/e2e/a11y-ui-f11.spec.ts`. It ran against `pnpm dev` on `:3002` (`NEXT_PUBLIC_E2E=1`) on the new harness `/e2e/data-table`, which has three tables: a 5,000-row `DataTable`, a 120-record `BulkResultTable`, and a 12-row `DataTable`. Desktop is 1440×900 and narrow is 390×844.

## axe (wcag2a/aa, 21a/aa; same rule set as `a11y-primary.spec.ts`)

Raw results: `axe-results.jsonl`. Each state is scanned twice: the whole page (recorded) and the three table cards (gated).

| Route / state | Tables, desktop | Tables, 390 | Whole page, desktop | Whole page, 390 |
|---|---|---|---|---|
| `/e2e/data-table`, row 41 of 5,000 active by keyboard, focus ring showing | 0 | 0 | 0 | 0 |
| `/e2e/data-table`, bulk filtered to Failed (virtual to plain), reduced motion | 0 | 0 | 0 | 0 |

The same spec also asserts the following:

- 5,000 rows: the scroll frame is present, fewer than 100 `<tr>` are in the DOM, `aria-rowcount="5001"`, and the header row has `aria-rowindex="1"`.
- Tab reaches the grid, and the frame's `box-shadow` is not `none`.
- Forty ArrowDown presses move `aria-activedescendant` to `data-table-row-f-40`. That row is rendered with `aria-rowindex="42"` and a non-transparent background. It sits below the pinned header and inside the frame, and `scrollTop` is greater than 0. The `thead` stays at the top of the frame.
- Clicking "Size" sets `aria-sort="ascending"`. `aria-rowcount` stays 5001.
- Bulk, 120 records: virtualized with `aria-rowcount="121"`. Scrolling to the bottom shows "Partner 120" at `aria-rowindex="121"` (390 px included, where rows wrap). "Failed" leaves 12 rows: the plain table with `aria-rowcount="13"`.
- The 12-row table is a plain table: 12 `<tr>` and `aria-rowcount="13"`.

Unit tests added in `DataTable.test.tsx`:
- The threshold switches 50 → 51 → 50, and the plain path stays keyboard-operable.
- `aria-rowcount` and `aria-rowindex` match the sorted data index on 5,000 virtualized rows, and on the plain path.
- `aria-rowcount` is left off while loading or empty.
- `aria-sort` follows sorting, and `aria-rowindex` follows the sort order.
- Keyboard navigation renders and activates row 31 of 500 under `VirtuosoMockContext`, with a jsdom scroll stub. That row was outside the virtual window at first.

## Screenshots

- `data-table-keyboard-{desktop,390}.png`: the 5,000-row table after 40 ArrowDown presses. The frame focus ring, the tinted active row with its accent bar, and the pinned header all show.
- `data-table-bulk-filtered-{desktop,390}.png`: the bulk table filtered to Failed (plain path), with reduced motion emulated.

## UX audit (12 rows, `T7_UI_MOTION_COPY.md`)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | The header stays pinned while rows scroll. The active row is the only accent-tinted row, and only while the table has focus, so idle tables stay calm. |
| IA | Not observable | No column, label, or order changed for any caller. |
| Interaction | Pass | ArrowUp and ArrowDown move the active row in both paths. Virtuoso scrolls the row into view only when it is outside the frame. Clicking a row sets it active. Sort buttons are unchanged. |
| Feedback | Pass | The focus ring is on the frame, and the active row has a tint plus a 2 px bar. Sorting is instant (5,000 rows sort and filter in under 2 ms). |
| Errors | Not observable | The table has no error states. The loading skeleton and empty state are unchanged. |
| Accessibility | Pass | `role="grid"`, `aria-rowcount` (header included), `aria-rowindex` on every rendered row, `aria-activedescendant`, and `aria-sort`. axe on the tables is 0 at both widths. |
| Cognitive load | Pass | No new controls. Long tables keep a fixed 360 px frame instead of pushing the page 200,000 px tall. |
| Trust | Pass | Screen readers announce the true row position ("row 42 of 5001") even though only the visible rows exist in the DOM. |
| Copy | Not observable | No visible strings changed in the shared components. Harness-only headings were added under `/e2e/data-table`. |
| Forms | Not observable | Row checkboxes and select-all are unchanged. |
| Performance | Pass | About 10 to 20 rows are in the DOM for 5,000 rows. Sort and filter of 5,000 rows is measured under 100 ms in a unit test. Nothing animates, and there are no scroll reveals in tables. |
| Business goal | Pass | Bulk results, audit logs, and model lists stay fast and keyboard-navigable at thousands of rows. |

Not observable from screenshots: screen-reader announcement wording, scroll smoothness on low-end hardware.

## Pre-existing, not counted against this card

- `eslint` reports `react/display-name` on the `TableHead` and `TableBody` `forwardRef` components in `DataTable.tsx`. They came from `49bcefb`, and this pass did not touch those lines.
- Hand-rolled `<table>` markup with unbounded rows sits outside this card's "Change", so it is not virtualized:
  - `connections/[id]/housekeeping/page.tsx` (orphan rows)
  - `components/cron/CronJobsList.tsx`
  - `components/bulk/BulkResultsSection.tsx` (preview and relinks)

  These are already bounded: `AccessMatrixPanel` (40 groups), the import preview (5 rows), and the `OdooListView` sample rows.
- "Active row" is announced through `aria-selected`, which overlaps with checkbox selection in `selectable` tables. This behavior is unchanged.
- Re-running `a11y-ui-f05.spec.ts` as a regression check rewrote the four untracked UI-F05 screenshots with the same states. Its `axe-results.jsonl` was restored afterwards.
