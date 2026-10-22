# UI-S-19 · Access (Studio-bar visual leap)

Status: Studio-bar visual leap on page + harness. **Not marked DONE.**

AccessVersionStrip stays in paper; gate honesty folded into bar. AccessSessionBar (composer) unchanged.

Gaps: unsaved matrix badge not yet driven into session badge.


---

## Prior elevate notes (archive)

# UI-S-19 · Access (Studio-bar visual leap)

Status: Studio-bar visual leap on page + harness. **Not marked DONE.**

Gate honesty in bar; AccessVersionStrip stays in paper. AccessSessionBar unchanged.

Gaps: unsaved matrix not driven into session badge.


---

## Prior elevate notes (archive)

# UI-S-19 Access: vision notes

Pressure 10. Route `/connections/[id]/access`, harness `/e2e/access?state=…`.
Primary CTA: **Save right** / **Save N rights** (teal, sticky save bar). In production (R3) the primary becomes an **Open plan card** link to `/approvals?connection_id=…`, with no inline apply.

## Design read
This is an operate-mode matrix: rows are groups, column groups are models, and each model has R/W/C/D sub-columns. Chrome is Basalt with one teal accent, used for granted, selected and primary. Amber means staged (not saved yet). Cinnabar never appears in UI. The screen stays honest about versions:
- Odoo 17–19: version strip `ir.model.access + ir.rule`, tabs Matrix / Access lines / Record rules.
- Odoo 20: version strip `ir.access` plus a note that rights and row filters share one model. Tabs are Matrix / Access lines only. No record rules tab, and `listRecordRules` is never called.
- Unknown version: no model claims and no rules tab, with a gate guide asking you to re-probe.

## Playbook rules applied
- One filled primary per view. Load, Discard and Create are secondary or ghost.
- No eyebrow kickers and no em dashes in UI copy.
- Inset hairline lists for access lines and rules instead of boxed cards.
- Real `<table>` with a caption, model `colgroup` headers, `scope=col` R/W/C/D headers and `scope=row` group headers. Sticky header row and sticky first column.
- Roving tabindex over cells (arrows, Home/End). Cells are toggle buttons with `aria-pressed` and a full label.
- The global row is read-only and carries a lock reason. Cells are editable only in inline write mode.
- Empty and error states use a what/why/next guide (`AccessStateGuide`). Errors use `role=alert` and a Retry button.
- Dark mode via tokens.

## States captured (`after-*`)
| State | What to verify |
|-------|----------------|
| harness legacy | 17–19 strip, Matrix default, "No changes staged", Save disabled |
| harness staged | amber halos, "3 changes staged" plain-word summary, teal Save 3 rights, Discard |
| harness odoo20 | ir.access strip and note, two tabs, "ir.access matrix" title |
| harness plan | production gate guide, Open plan card link as primary, cells locked |
| harness empty | what/why/next empty guide, no orphan save bar |
| harness error | alert guide with what/why/next and Retry |
| harness lines | inset access lines with CRUD letters and Global tag |
| harness unknown | capabilities-unknown gate guide, no rules tab |
| harness staged/plan dark | dark tokens, contrast |
| real 19 / 20 / production | the real page in AppShell, using Playwright route mocks |

Desktop is 1024 wide and mobile is 390. Every harness shot has overflowX=0. The real-page mobile shots show overflowX=99, which comes from the AppShell expert aside. It predates this work and also shows on `/job` and `/menus`.

## Capture and axe
```bash
cd apps/web
PLAYWRIGHT_E2E_BUILD=1 NEXT_PUBLIC_E2E=1 npx next dev --turbopack -H 127.0.0.1 -p 3019
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-19/capture.cjs \
  http://127.0.0.1:3019 ../../docs/vision-verify/UI-S-19 after
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-19/axe.cjs http://127.0.0.1:3019
```
axe result: 0 serious or critical violations across 8 harness states, each in light and dark.

## Tests
```bash
cd apps/web
npx vitest run src/components/access src/lib/accessScreen.test.ts src/lib/accessForm.test.ts "src/app/connections/[id]/access"
```

## Gaps
- Production edits only link to the `/approvals` inbox. No backend plan card is created from a staged access edit.
- It is not verified that the backend `list_access_rights` and `access/matrix` read `ir.access` on Odoo 20 (O20-07).
- No ir.access domain editing from matrix cells on Odoo 20.
- There is only one before shot, `before-harness-legacy-desktop.png`.

## Must not
- Em dashes or kickers in UI copy
- Orange or cinnabar CTAs, or Odoo purple
- A record rules tab or `ir.rule` claims on Odoo 20
- Inline apply on production (R3)
- More than one filled primary
