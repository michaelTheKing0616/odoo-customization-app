# UI-S-12 · Visual Designer look-and-feel (vision notes)

Card: UI-S-12 `…/designer` (split first of UI-SP-DESIGNER, depends on UI-F13).
Status: look-and-feel pass is implemented and verified locally. **Not marked DONE.** Nothing is committed.

Sources loaded before the UI edits:
- `design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md`
- `design-research/ingenium-canvas-2026-10-05/DESIGN_THESIS.md` (with the `11-odoo-studio.png` baseline)

## What the pass delivers (thesis → implementation)

| Thesis item | Where |
|---|---|
| Paper as object on a quiet pasteboard | `.designer-desk` dot grid plus `.designer-paper` card in `designer.css`. The form, kanban, list and all four structure canvases sit on the same desk, in the same family as the Reports (PDF-06) paper canvas. |
| Three-pane basalt chrome, one teal accent | Basalt session bar, tools rail and inspector. Teal is used only for primary actions, selection and focus. The `.designer-chrome` status overrides make Unpublished / ORM-required **amber**, not rust or cinnabar. |
| Cinnabar keystone only | No cinnabar in the designer chrome. Danger uses `--dz-danger` (a red token), which is never the brand cinnabar. |
| Typed palette and search kept | Fields rail is grouped by type (Text / Numbers / Choice / Relations / Odoo widgets), with counts and the "Filter by name or type" search. Tabs stay on one line (nowrap plus scroll, 12px). |
| UI-F13 primary reorder | The canvas uses `ReorderableBlocks` (UI-F13) unchanged. The pointer ghost is transform-only (`DesignerPointerGhost`). Up/down chevrons stay as the secondary, keyboard-friendly path. |
| Smoother than Studio | No per-keystroke layout animation. Only the inspector drawer animates. Structure-row "Remove" buttons are hidden until hover, focus or selection, and always visible on touch (`hover:none`). |

## Playbook rules applied

- **§0 law 3 (one accent):** teal is the only chromatic accent. The loud royal-blue notice Callout was retoned to a quiet info subtle inside `.designer-chrome`.
- **§0 law 6 (no boxes inside boxes):** the list canvas legend became chips, the table is quiet, and the structure sections are single cards with inset rows instead of nested borders.
- **§0 law 8 (copy is UI):** buttons are verb-first ("Add group", "Add page", "Remove notebook"). Headings name the thing ("List layout", "Kanban layout", "Search layout"). "Btn ·" became a `Button` kind chip.
- **§5 status palette, one meaning per colour:** amber = unsaved or warning, red = invalid or destructive, teal = primary or selected. Added the tokens `--dz-warn` and `--dz-danger` (light and dark).
- **§6 motion:** only the inspector drawer animates. The drag ghost uses `transform`. There is no layout animation on the canvas, and `prefers-reduced-motion` is honoured.
- **§9 no slop:** removed em dashes and glyph arrows (↑ ↓ × ↗) from designer and preview copy, using Lucide `ChevronUp/Down`, `X` and `ExternalLink` instead. Preview copy is plain: "Structural preview. Open in Odoo for the authoritative layout."
- **§15.1 lock tokens:** hard-coded ghost hexes now use `--dz-ghost-dot` and `--dz-ghost-meta`. The dark-mode Confirm text colour is computed from `--odoo-primary` lightness (relative OKLCH with a fallback), so a light teal primary gets dark text.
- **§15.4 error anatomy (what happened → why → what to do):** see the states below.

## Canvas states (human copy)

| State | Harness | Copy |
|---|---|---|
| View XML invalid | `/e2e/designer?state=xml-invalid` | Title: "The view XML has an error on line N". Plain-language gloss from `explainXmlReason()`, e.g. "The `<group>` opened on line 9 is still open when `</form>` closes. Close the `<group>` first." Then "Fix it in Advanced, then save again." The raw lxml text is kept under the label "Odoo's message". Action: **Open Advanced**. |
| Inherit conflict | `?state=inherit-conflict` | Title: "Odoo can't find where to attach this change". Body: "The parent view has no match for this locator. Another module may have moved or renamed it. Pick a named locator in Advanced, then save again." The XPath appears under "Locator" (`data-testid="designer-canvas-state-locator"`). Amber warning tone, `role="alert"`. |
| Preview stale | `?state=preview-stale` | Amber strip. Title: "Live Odoo shows the last saved view". Body: "Your canvas edits are not in it yet. Save to Odoo to publish them, or switch to the layout canvas to see them now." In live mode the iframe also carries a "Last saved version" tag (`designer-live-stale-tag`). |

## Shots (`after-*` produced by `capture.cjs`; `before-*` captured before the pass)

- `after-form-desktop`, `after-form-narrow`, `after-form-dark-desktop` (Confirm contrast fixed)
- `after-kanban-desktop`, `after-kanban-narrow`, `after-list-desktop`
- `after-state-xml-invalid-desktop`, `after-state-inherit-conflict-desktop`, `after-state-preview-stale-desktop`
- `after-form-drag-desktop` (transform ghost mid-drag), `after-form-keyboard-desktop` (keyboard move)
- `after-form-inspector-desktop` (Properties summary with a `Kbd` ↑ ↓ hint)
- `after-premium-desktop`
- `after-structure-form|list|kanban|search-desktop` (new harness `/e2e/designer-structure?view=…`)

Every shot measured `overflowX=0`.

Regenerate:

```
cd apps/web
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-12/capture.cjs http://127.0.0.1:3002 ../../docs/vision-verify/UI-S-12 after
```

## Tests

- Vitest: `npx vitest run src/components/designer src/components/ui/canvas src/components/odoo-preview`: **34 files, 108 passed** (the baseline was 105). New tests cover `explainXmlReason`, the glossed XML copy and the stale tag.
- Playwright against the dev server (`PLAYWRIGHT_BASE_URL=http://127.0.0.1:3002`) on designer-cmp3, designer-ee-panels, designer-premium, designer-vision and designer-keyboard: **13 passed, 2 failed**.
  - The 2 failures are both in `designer-cmp3`. They expect `--odoo-primary: #714B67` (Odoo purple) on `preview-theme-scope`, but the committed harness at HEAD already passes `var(--accent8)`, which is teal #115e59.
  - This is pre-existing spec drift and was not caused by this pass. Making it green means either editing the spec (forbidden by the card) or putting purple back into the harness (forbidden by the brand). It needs an owner decision.

## Known gaps (follow-ups)

- The real `DesignerFieldInspector` has no keyboard-move hint yet. Only the harness Properties panel shows ↑ ↓.
- The premium inspector accordions still read slightly boxed.
- The narrow session bar wraps onto two lines (no overflow, but crowded).
- Both kanban lanes show the same selected card. This is intentional, because it is a template preview.
- Pre-existing lint and type debt that was left alone: an `any` at `useDesignerCanvasMutations.ts:84`, an unused `PreviewThemeScope` import in `DesignerAdvancedStructureCanvas.tsx`, and TS7006 in `ReorderableBlocks.tsx` (UI-F13).

## Not touched

`odoo_addons/`, `ReorderableBlocks.tsx` (UI-F13), `ReportDesigner.tsx`, the internals of the real `DesignerFieldInspector`, all e2e spec files, and git state (no commit, stash or checkout).
