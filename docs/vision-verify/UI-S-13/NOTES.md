# UI-S-13 · Menus (Studio-bar visual leap)

Status: Studio-bar visual leap on page + harness. **Not marked DONE.**

Basalt OperateStudioChrome; honesty "Tree edits stay local until Save the menu." ComposerSessionBar (MenuSessionBar) unchanged for composer submit/discard.

Gaps: unsaved badge not yet wired to staged move state (tree chip still shows Unsaved move).


---

## Prior elevate notes (archive)

# UI-S-13 · Menus (Studio-bar visual leap)

Status: Studio-bar visual leap on page + harness. **Not marked DONE.**

Basalt OperateStudioChrome; honesty folded into bar. MenuSessionBar (composer) unchanged.

Gaps: session badge not yet wired to staged-move state.


---

## Prior elevate notes (archive)

# UI-S-13 Menus: vision verify

Route `/connections/[id]/menus` · harness `/e2e/menus` · pressure 6 · primary action **Save the menu**.
Status: elite UI/UX pass delivered for review. **Not marked DONE.** Nothing committed.

## Design read
Menus is a Studio-cluster operate screen: a structural tree on the left, one calm editing panel on the right.
The tree is the work, so it gets the APG tree pattern, guide lines that show depth, and drag re-parenting
that refuses illegal drops *before* anything reaches Odoo. Brand ingenium-v2: basalt chrome, teal for
selection / valid drop / primary, amber only for "unsaved", danger red only for refused drops and delete.
Cinnabar never appears (logo keystone only). Craft reference: UI-S-19 Access (`access-operate.css`).

## Playbook rules applied
- One filled primary per view: **Save the menu** (detail) or **Create menu** (composer). The rest are secondary or ghost.
- Hierarchy through type weight and spacing, not boxes: one panel with hairline sections, legends floated.
- Selection uses a 3px teal inset bar on the row. Callouts use a 1px border, a light tint and an icon (no thick coloured left borders).
- Motion values mirror `components/ui/motion/constants.ts` (row hover 80ms, save confirm 150ms, press 130ms, EASE_ENTER_EXIT). Reduced-motion and reduced-transparency fallbacks are in place.
- Copy is plain: no em dashes, refusals say what / why / next ("Odoo refuses recursive menus").
- Tokens only: every colour resolves to an existing theme variable or a `color-mix` of one. Dark mode uses `--mn-accent-text` so teal text clears 4.5:1 on basalt.
- 390px reflow: the grid collapses to one column, the sticky save bar becomes static below 1024px, and the keyboard legend hides on coarse pointers.

## States
| State | Where | What the user sees |
|---|---|---|
| Loading | `?state=loading` | Skeleton rows at three indent levels inside the tree box (`role=status`, `aria-busy`). Count and key legend are hidden. |
| Empty | `?state=empty` | "No menus yet", one sentence, one action (**Create menu**, secondary). |
| No filter match | type in filter | "No matching menus" plus **Clear filter**. |
| Error (load) | `?state=error` | Guide: "Menus didn't load" / why (Odoo message) / next ("Check the connection on Overview, then try again"), **Try again** reloads. The tree says it will appear once Odoo answers; it does not claim there are no menus. |
| Error (save/create/delete/restore/bind) | real page | Same guide with action-specific copy and **Dismiss**. |
| Default | `?state=default` | Tree with Visitors selected, detail panel, "No changes" save bar. |
| New | `?state=new` | Composer with a segmented choice between an existing action and a new one. |
| Staged move | `?state=staged` | Row shows the amber "Unsaved move" chip; detail says "Moving from Configuration to Visitors. Not saved yet."; save bar reads "1 change: parent". |
| Refused drop | `?state=refused` | Refusal guide under the tree: "Can't move “Front desk” under “Badge types”" / "Odoo refuses recursive menus..." / next, with Dismiss. Announced through a polite live region. |
| Drag blocked | `?state=blocked` | Rows lose the grip; "Dragging is off: ..." explains why (e.g. a save is running). |

## Keyboard walk (recorded by `e2e/menus-tree.spec.ts` and `MenusTree.test.tsx`)
1. Tab into the tree: focus lands on the selected row (roving tabindex, one tab stop).
2. ↑ / ↓ move between visible rows. Home / End jump to first / last.
3. → opens a closed branch, then moves to the first child. ← closes an open branch, then moves to the parent.
4. Enter or Space selects the focused row and loads it in the detail panel. Selection does not follow focus.
5. Typing letters jumps to the next row whose label starts with them (type-ahead).
6. The chevron toggles a branch without selecting it. `aria-expanded` is set only on parents.
7. Keyboard re-parenting goes through the **Parent** select in the detail panel; the same refusal rules apply.

## 12-point UX audit
| # | Check | Result |
|---|---|---|
| 1 | One clear primary per view | Pass. "Save the menu" is the only filled button in the detail view. |
| 2 | Tree semantics (APG) | Pass. `tree` / `treeitem`, level, setsize, posinset, expanded, selected; unit and e2e tested. |
| 3 | Invalid drag refused with a reason | Pass. Self, descendant, same-parent and missing-parent each have title / why / next; drop cursor shows "none". |
| 4 | Drag never writes by itself | Pass. A drop stages the parent; only Save the menu writes. Discard reverts. |
| 5 | Change summary before save | Pass. "1 change: parent" and the move strip; top-level moves add the default app icon so Odoo accepts them. |
| 6 | Loading / empty / error states | Pass. Skeleton; one sentence plus one action; what / why / next with a real next step. |
| 7 | Destructive action isolated | Pass. Delete lives in its own danger row with the existing typed-phrase confirm. |
| 8 | Focus visible everywhere | Pass. Inset teal ring on rows, accent ring on inputs and links. |
| 9 | Contrast light and dark | Pass. axe 0 serious / critical across 8 states x 2 themes. |
| 10 | 390px reflow | Pass on the harness (overflowX 0). Real page mobile shows 99px from the AppShell expert aside, same as the before shots. |
| 11 | Copy and brand | Pass. No em dashes in menus files, no purple, no orange primary, cinnabar absent. |
| 12 | Motion restraint | Pass. Values from motion constants; reduced motion removes transitions. |

## Shots (`after-*` = this pass, `before-*` = pre-change)
Harness (desktop 1440 and mobile 390 each): `after-harness-{default,new,staged,refused,empty,loading,error,blocked}`,
`after-harness-default-dark`, `after-harness-refused-dark`.
Real page with mocked API: `after-real-19`, `after-real-19-dark`.
Flows on the real page: `after-flow-drag-refused`, `after-flow-drag-staged`, `after-flow-keyboard`.
Before: `before-harness-default`, `before-real-19`, `before-real-empty`, `before-real-error`.

## Commands
Run from `apps/web` against a dev server started with `NEXT_PUBLIC_E2E=1`:
```
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-13/capture.cjs http://127.0.0.1:3913 ../../docs/vision-verify/UI-S-13 after
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-13/axe.cjs http://127.0.0.1:3913
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3913 npx playwright test e2e/menus-tree.spec.ts --project=chromium
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3913 npx playwright test e2e/a11y-primary.spec.ts -g Menus --project=chromium
npx vitest run src/components/menus src/lib/menuTree.test.ts src/lib/menuForm.test.ts
```

## Results (2026-10-05)
- Vitest: 5 files, 48 passed (menuTree 20, MenusTree 13, MenuDetail 6, menuForm 7, MenuSessionBar 2).
- Playwright `e2e/menus-tree.spec.ts`: 11 passed (keyboard walk, drag refused, drag then Save the menu, axe on 8 states).
- Playwright `e2e/a11y-primary.spec.ts -g Menus`: 1 passed.
- `axe.cjs`: 0 serious / critical on 16 runs (8 states x light and dark).
- eslint on menus files: clean.
- tsc: 19 errors repo-wide, none in menus files (all in other agents' in-flight work).

## Gaps
- Unsaved detail edits are dropped when another menu is selected or dragged (no "leave with changes" guard yet).
- No keyboard drag; keyboard re-parenting uses the Parent select.
- HTML5 drag on touch depends on the browser; the Parent select is the reliable mobile path.
- On a load error the composer still shows on the right; a create may also fail until the connection is fixed.
- GroupPicker's blue badge comes from a shared component outside this card.
- The floating Expert button overlaps the bottom right of the sticky save bar on the real page (AppShell).
- Real-page mobile overflowX 99 comes from the AppShell expert aside (pre-existing, also in before shots).
- `useReportsPage.ts` still carries the old caveat string with an em dash (not a menus file).
