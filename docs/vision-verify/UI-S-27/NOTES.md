# UI-S-27 · ID Generator (Studio-bar visual leap)

Card: UI-S-27. Primary: **Download updated CSV** (teal).
Status: Studio-bar harness leap implemented locally (shared OperateStudio chrome). **Not marked DONE.** Nothing committed.

Sources: Playbook + ingenium-v2; eyes on UI-S-12 + UI-S-20-premier.

## Design Read

Operate surface with Designer-class basalt studio chrome. Honesty in `OperateStudioBar` (no twin-banner). Empty/idle guides use brief density on the paper desk.

## Before → after craft

| Before (elevate) | After (Studio-bar) |
|---|---|
| PageHeader + rail + honesty (+ empty) cards | Basalt studio header + session honesty bar + connected rail |
| Twin banners | Honesty in bar; empty/idle `density="brief"` |
| Flat panels | Shared desk + cream paper via operate-studio.css |

## Files

- Shared: `apps/web/src/components/operate-studio/*`
- Harness + StateGuide density + operate CSS import + session badge helper + e2e studio asserts
- `before-*` copied from prior elevate `after-*`

## Gaps

- Live route still uses prior PageHeader layout (CSS tokens available; JSX chrome wrap pending mirror of harness).
- Vision after re-capture should be run on shared `:3002`.
- No DONE / commit / agent mirrors.

---

## Prior elevate notes (kept)

# UI-S-27 ID Generator (`…/id-generator`) — vision notes

Pressure 4 (cheap). Route `/connections/[id]/id-generator`, harness `/e2e/id-generator?state=…`.
Primary CTA: **Download updated CSV** (teal). Live Apply is secondary behind dry-run + risk phrase.
Status: elite UI pass implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before the UI edits:
- `design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md`
- Global rules + UI-S-27 block in `docs/plans/next-phase/13_UI_SCREEN_SPECS.md`

## Design Read

Operate-mode reference-code desk. Basalt chrome, one teal Download primary, honesty for preview/CSV vs live Apply and optional ir.sequence, what/why/next on empty and error, Studio-cluster craft. No purple, no orange CTAs, no em dashes, cinnabar never in UI.

## What the pass delivers

| Thesis item | Where |
|---|---|
| Download is the sole teal primary | `id-generator-download` uses `variant="primary"`; Preview / Dry-run / Apply stay secondary |
| Preview vs Apply honesty | Always-on `id-generator-honesty`; preview panel labels "never write" / "no writes" / "writes applied" |
| Sequence honesty | `id-generator-sequence-guide` when Live; bridge is optional and after Apply only |
| Stage rail | Source → Rules → Preview → Deliver via `IdGeneratorStageRail` |
| what/why/next | Empty, error, counts, and sequence guides |
| No em dashes | `sanitizeIdGenCopy` / `emptyCellDisplay("none")`; unit-locked |

## States captured (`after-*` via `capture.cjs`)

| State | Harness | Verify |
|---|---|---|
| empty | `?state=empty` | Source step; honesty; empty what/why/next; Download disabled with reason |
| csv-preview | `?state=csv-preview` | Preview step; counts; teal Download enabled; "Nothing was written" |
| live-dry-run | `?state=live-dry-run` | Dry-run counts; preview says no writes |
| applied | `?state=applied` | Deliver step; succeeded counts; writes applied copy |
| sequence | `?state=sequence` | Sequence guide "after Apply" |
| error | `?state=error` | Danger what/why/next |

Canonical: `desktop.png` = after-empty-desktop, `narrow.png` = after-csv-preview-narrow.
Every after shot measured `overflowX=0` at 1440×900 and 390×844 (reduced motion).

Regenerate:

```
cd apps/web
# NEXT_PUBLIC_E2E=1 on an isolated port (this pass used :3027, INGENIUM_DIST_DIR=.next-s27)
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-27/capture.cjs \
  http://127.0.0.1:3027 ../../docs/vision-verify/UI-S-27 after
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/idGeneratorScreen.test.ts src/components/id-generator` → **4 files, 10 passed**
- Playwright (against `:3027`, no other ports killed): `e2e/id-generator.spec.ts` → **5 passed**
- Capture: 12 after shots, all overflowX=0

## UX audit (12 rows)

| # | Area | Before | After |
|---|------|--------|-------|
| 1 | Primary CTA | Download and Apply both `variant="primary"` (two teals). | Only **Download updated CSV** is teal. Apply is secondary + confirm. |
| 2 | Hierarchy | Flat tabs + cards, jargon description. | PageHeader, sample code, honesty, stage rail, source / rules / preview panels. |
| 3 | Empty | EmptyState only, thin teach-line. | what/why/next empty guide with Preview / Dry-run action. |
| 4 | Error | Bare `ErrorNotice` string. | Classified what/why/next by context (preview, download, dry-run, apply, sequence). |
| 5 | Honesty | No preview-vs-write contract. | Always-on honesty; panel subcopy; sequence guide separate from code writes. |
| 6 | Counts | Message prose only. | Total / Changed / Skipped (+ Succeeded / Failed on live). |
| 7 | Sequence | Checkbox with no explanation. | Toggle + warning/neutral guide: bridge after Apply, not part of CSV download. |
| 8 | Progress | Busy skeletons only. | `ig-progress` live region while working. |
| 9 | Copy | Em dash `—` in Old/New cells; slashy description. | `none` for empty cells; sanitized messages; verb CTAs. |
| 10 | Chrome | Default kit on max-w-5xl. | `.idgen-operate` Basalt / limestone, teal accent, 4pt rhythm, reduced-motion. |
| 11 | Apply safety | Apply always enabled. | Apply blocked until a live dry-run exists; phrase confirm unchanged. |
| 12 | Phone | Untested this route. | Narrow 390 captures overflowX=0; tables scroll inside wrap. |

## Gaps (not fixed here)

- AppShell sidebar may stay open at 390px (global shell). Capture collapses it when the toggle exists.
- Real-route Playwright axe sweep not re-run in this pass (harness + unit + id-generator e2e green). Existing `a11y-primary` / `vision-verify-sweep` still target `id-generator-page`.
- Live Apply gated on dry-run in UI; API still accepts apply without dry-run if called directly (contract freeze).
- Harness omits file picker chrome on empty (vision focus); live page keeps the file input.
- `next.config.ts` gained optional `INGENIUM_DIST_DIR` for isolated dist folders; default behavior unchanged.
- Next auto-added `.next-s27/types/**/*.ts` to `apps/web/tsconfig.json` include while the mirror ran.

## Must not / not touched

- Em dashes in UI copy; orange / Odoo purple primary CTAs; cinnabar on buttons
- Remove phrase confirmation on live Apply
- cron-manager / reminders / script-runner / expert / bulk-suite / power-ops / housekeeping / import / ingest pages
- Commit, push, stash, checkout, git clean, DONE, or `odoo_addons/`
- Did not kill other agents' ports; left `/private/tmp/s25web` alone (3025 was listening)
