# UI-S-26 · Bulk data import (Studio-bar visual leap)

Card: UI-S-26 `…/import`. Pressure 8. Primary: **Commit** (teal).
Status: Studio-bar visual leap implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources: DESIGN_SYSTEM_PLAYBOOK.md, ingenium-v2, eyes on UI-S-12 / UI-S-20 / UI-S-52 Contract Studio.

## Design Read
Operate-mode CSV/XLSX import desk with Designer-class basalt studio chrome. Dry-run honesty lives in the studio bar (not twin banners). Empty what/why/next is a compact paper brief. Paper desk for upload/map. One teal Commit primary.

## Before → after craft
| Before (elevate) | After (Studio-bar leap) |
|---|---|
| PageHeader + pill stage chips | Basalt `op-studio` chrome with titlebar |
| Empty guide as full card under rail | Honesty in `OperateStudioBar`; empty as `density="brief"` |
| Flat panels on gray page | Dot-grid desk + cream paper lift |
| Pill rail on light surface | Connected Studio nodes on basalt |

## States captured
empty, map, dry-run, partial, progress, error × desktop + narrow. overflowX=0 targeted.

## Tests
Vitest: importScreen (+ honesty/badge), ImportStateGuide (brief density), OperateStudioBar.
Harness: `/e2e/import?state=…` wrapped in OperateStudioChrome.

## Gaps
- Seed pack gallery still live-API on real route.
- Commit available before dry-run (API contract); copy + bar honesty nudge dry-run first.
- Image import remains folded secondary.

## Not touched
odoo_addons/, git (no commit/stash/checkout), DONE, peers outside this leap list. Stopped this agent's :3260 mirror after capture.


---

## Prior elevate notes (archive)

# UI-S-26 · Bulk data import (Studio-bar visual leap)

Card: UI-S-26 `…/import`. Pressure 8. Primary: **Commit** (teal).
Status: Studio-bar visual leap implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources: DESIGN_SYSTEM_PLAYBOOK.md, ingenium-v2, eyes on UI-S-12 / UI-S-20 / UI-S-52.

## Design Read
Operate-mode CSV/XLSX import desk with Designer-class basalt studio chrome. Dry-run honesty lives in the studio bar (not twin banners). Empty what/why/next is a compact paper brief. Paper desk for upload/map. One teal Commit primary.

## Before → after
| Before (elevate) | After (Studio-bar leap) |
|---|---|
| PageHeader + pill stage chips | Basalt `op-studio` chrome via OperateStudioChrome |
| Empty guide as full card under rail | Honesty in OperateStudioBar; empty as density=brief |
| Flat panels on gray page | Dot-grid desk + cream paper lift |

## States
empty, map, dry-run, partial, progress, error × desktop + narrow. Canonical desktop=empty.

## Tests
Vitest: importScreen honesty/badge, ImportStateGuide brief, OperateStudioBar.

## Gaps
- Seed packs still live-API on real route.
- Commit available before dry-run (API contract); bar honesty nudges dry-run first.
- Image import remains folded secondary.

## Not touched
odoo_addons/, git, DONE. Stopped this agent's mirror after capture.


---

## Prior elevate notes (archive)

# UI-S-26 Bulk data import (`…/import`) — vision notes

Pressure 8. Route `/connections/[id]/import`, harness `/e2e/import?state=…`.
Primary CTA: **Commit** (teal). Dry-run is secondary. Phrase confirm stays on write.

## Design Read
Operate-mode bulk CSV/XLSX import desk. Basalt chrome, one teal Commit primary, dry-run count strip before write, what/why/next empty and error, Studio-cluster craft. No purple, no orange CTAs, no em dashes, cinnabar never in UI.

## States captured
| State | What to verify |
|-------|----------------|
| empty | Stage rail on Upload; what/why/next empty guide; Parse disabled without a file |
| map | Mapping table with Unmapped chip; teal Commit primary; Dry-run secondary |
| dry-run | Validate stage; create/update/skip/error count strip |
| partial | Commit counts with failed > 0; partial what/why/next; Download error CSV |
| progress | Committing rows… busy strip; Commit disabled |
| error | Could not parse the file; classified why; next step; Diagnose with Expert |

Canonical: `desktop.png` = after-empty-desktop, `narrow.png` = after-map-narrow. All after shots: overflowX = 0.

## Capture
```bash
cd apps/web
# with NEXT_PUBLIC_E2E=1 webServer, or a running next on :3002
NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-26/capture.cjs \
  http://127.0.0.1:3002 docs/vision-verify/UI-S-26 after
```

## UX audit (12 rows)

| # | Area | Before | After |
|---|------|--------|-------|
| 1 | Primary CTA | "Commit writes" was solid danger/red beside Dry-run. | One filled teal **Commit**. Dry-run is secondary. Confirm dialog keeps danger risk. |
| 2 | Hierarchy | Raw inputs, JSON sample dump, duplicate error/notice lines. | PageHeader, stage rail, seed panel, upload/map panel, folded image import. |
| 3 | Empty | No teach-line; empty was just an idle form. | `ImportStateGuide` what/why/next: parse a file, then dry-run counts. |
| 4 | Error | Bare `ErrorNotice` / duplicated red text. | `ImportErrorNotice`: title, detail, classified why, next, Diagnose with Expert. |
| 5 | Dry-run counts | `created=… updated=…` prose. | Four count tiles (Create / Update / Skip / Error) with tone. |
| 6 | Partial failure | Error CSV link only. | Warning guide + Download error CSV; row results table. |
| 7 | Mapping | Plain inputs, no gap signal. | Unmapped chip + row tint; commit/dry-run blocked reason in visible text. |
| 8 | Progress | Busy disabled buttons only. | `import-progress` live region with stage label. |
| 9 | Copy | Em dash in seed notice; arrow soup in description. | Sanitized copy; verb-first Parse / Dry-run / Commit; no em dashes. |
| 10 | Chrome | Kit dump on max-w-5xl. | `.import-operate` Basalt / limestone, teal accent, 4pt rhythm, reduced-motion. |
| 11 | Image import | Always-open second danger CTA panel. | Folded `<details>`; Commit images teal when preview ready. |
| 12 | Phone | Untested. | Narrow 390 captures overflowX=0; tables scroll inside their wrap. |

## Gaps (not fixed here)
- AppShell sidebar stays open at 390px (global shell). Harness collapses it when the toggle exists.
- Real-route Playwright axe sweep not re-run in this pass (harness + unit tests green). Existing `a11y-primary` and `vision-verify-sweep` still target `import-page`.
- Seed pack cards still load live API on the real route; harness empty state skips the seed panel.
- Image import remains secondary; no separate vision states for image-only flow.
- Commit is available before dry-run (same as prior API contract). Copy nudges dry-run first; hard-gating would change behavior.

## Must not
- Em dashes in UI copy
- Orange / Odoo purple primary CTAs
- Danger-colored Commit button (confirm dialog only)
- Remove phrase confirmation on write
- Touch menus / code-studio / expert / approvals / wizard / access / automations / job / designer / website / mail / qweb / studio
- Commit, push, stash, checkout, git clean, DONE, or `odoo_addons/`
