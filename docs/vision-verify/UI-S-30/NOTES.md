# UI-S-30 Bulk Suite (`…/bulk-suite`) — vision notes

Pressure 9. Route `/connections/[id]/bulk-suite`, harness `/e2e/bulk-suite?state=…`.
Primary CTA: **Run bulk action** (teal). Dry-run secondary. Phrase confirm stays on write.
Status: **paper-desk visual leap** (Ops/Fleet craft) implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources: DESIGN_SYSTEM_PLAYBOOK, ingenium-v2, Ops/Fleet leap (UI-S-29/51), Contract Studio UI-S-52 (raised-bar peer).

## Design Read

Operate-mode bulk ops desk. Limestone pasteboard + paper sheet. Basalt title. One compact OperateStudioBar for write honesty (not twin Callouts). Work panels sit on a dotted desk inside the sheet. Cross-links to Journal are quiet chips, not info Callouts. No purple, no orange CTAs, no em dashes, no eyebrows, cinnabar never on buttons.

## Before → after craft leaps

| Before | After |
|---|---|
| PageHeader + twin journal Callouts + always-on honesty Callout + separate work desk | One `bu-sheet` on pasteboard; masthead type; compact studio bar; quiet cross-links; dotted `bu-work` for panels |
| Two nested desks (chrome desk + work desk) | Single sheet wrapping chrome + children work |
| Template stack | Paper-as-object matching Ops/Fleet / Contract Studio bar |

## States captured

| State | Verify |
|---|---|
| empty | Masthead; stage rail Model; empty guide; honesty bar; Run disabled |
| select | Ids selection; blast radius known; Dry-run + Run |
| dry-run | Blast 412 on 1 model; count tiles; results table |
| partial | Partial guide; Failed count; Failed row |
| progress | Busy strip; buttons disabled |
| error | Error notice what/why/next |

Canonical: `desktop.png` = after-empty-desktop; `narrow.png` = after-dry-run-narrow. All overflowX=0.

```bash
cd apps/web
INGENIUM_DIST_DIR=.next-uis30b NEXT_PUBLIC_E2E=1 pnpm exec next dev -H 127.0.0.1 -p 3076
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-30/capture.cjs \
  http://127.0.0.1:3076 ../../docs/vision-verify/UI-S-30 after
# stop YOUR :3076 only
```

## Tests

- Vitest: `bulkSuiteScreen`, `BulkStateGuide`, `OperateStudioBar` → passed
- Vision: 12 after shots + aliases; overflowX=0
- First capture on `:3002` was polluted by a peer Turbopack overlay (`e2e/config` mid-write); recaptured clean on isolated `:3076`

## Skipped this wave

Power Ops / Housekeeping / Cron: wave-2 peer actively refreshing vision (UI-S-31/32/33 after shots at 21:43–21:53). Left alone.

## Gaps

- Honesty still a compact studio bar (write risk is imminent here); not a one-line Contract Studio sentence yet
- Real route still has many op panels; density inside panels not fully Designer-grade
- Dark pasteboard not vision-captured

## Not touched

`odoo_addons/`, plan-inbox, billing, auth, bridge. No DONE. No commit.
