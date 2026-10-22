# UI-S-32 · Cron Manager look-and-feel (vision notes)

Card: UI-S-32 `…/cron-manager` (~523). Pressure 5. Primary: **Save the cron** (teal).
Status: elite UI pass implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before / during the UI edits:
- `/home/box/design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `/home/box/design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md` + `tokens.css`
- Global rules + UI-S-32 block in `docs/plans/next-phase/13_UI_SCREEN_SPECS.md`
- Studio-cluster peers: UI-S-30 bulk-suite, UI-S-31 power-ops (read only; those trees not edited)

## Design Read

Operate-mode scheduled-actions desk. Basalt chrome, one teal **Save the cron** primary, amber only for honesty / dry-run caution, danger reserved for load/error guides and phrase confirm. What/why/next on empty and error. Honesty for enable / disable / trigger: Dry-run never writes; Enable resumes nextcall; Disable and Run now need the risk phrase. Next-run preview in the connection timezone (UTC honesty when tz not reported). No purple, no orange primary CTAs, no em dashes, cinnabar never in UI.

## What the pass delivers

| Thesis item | Where |
|---|---|
| Save the cron is the sole teal primary | `cron-save-btn` uses `variant="primary"`; Dry-run / Run now stay secondary |
| Enable / Disable honesty | Row pills: active → Disable; inactive → Enable; Disable opens ConfirmDialogV2 |
| Dry-run vs live trigger | Result label "Dry-run result (no writes)" vs "Run now result (live trigger)"; amber dry-run band |
| Stage rail | `CronStepRail` List → Select → Trigger → Save |
| What/why/next | Empty, honesty, notice, error via `CronStateGuide` + `cronManagerScreen` guides |
| Next-run preview | `CronNextRunPreview` + `formatPreviewNextRun` / `resolveCronTimeZone` |
| Basalt / teal chrome | `.cron-operate` scoped CSS (4pt rhythm, reduced-motion, cr-control fields) |

## States captured (`after-*` via `capture.cjs`)

| State | Harness | Verify |
|---|---|---|
| empty | `?state=empty` | Empty what/why/next; honesty; List step current; Save teal; Dry-run/Run now disabled |
| list | `?state=list` | Two sample rows; Enable/Disable pills; next-run + Africa/Lagos zone |
| select | `?state=select` | 1 selected; Select step; Dry-run/Run now enabled secondary |
| dry-run | `?state=dry-run` | Trigger step; "Dry-run result (no writes)" amber band |
| error | `?state=error` | Danger what/why/next (timeout classified) |
| compose | `?state=compose` | Save step; next-run preview zone Africa/Lagos; Save teal |

Every after shot measured `overflowX=0` at 1440×900 and 390×844 (reduced motion).
Canonical: `desktop.png` = after-list-desktop; `narrow.png` = after-dry-run-narrow.

Regenerate:

```
cd apps/web
PLAYWRIGHT_E2E_BUILD=1 NEXT_PUBLIC_E2E=1 pnpm exec next dev -H 127.0.0.1 -p 3032
# from repo root:
NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-32/capture.cjs \
  http://127.0.0.1:3032 docs/vision-verify/UI-S-32 after
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/cronManagerScreen.test.ts src/components/cron` → **3 files, 13 passed**
- Playwright (isolated `:3032`): `e2e/cron-manager.spec.ts` → **5 passed** (honesty+empty; select enables secondary; dry-run no-writes label; compose timezone; error what/why/next)
- Shared `:3002` was 500 during this pass; not reused. Isolated mirror stopped after capture.

## UX audit (12 rows)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | One teal primary (Save the cron); Dry-run / Run now secondary; honesty above list |
| IA | Pass | Stage rail mirrors List → Select → Trigger → Save |
| Interaction | Pass | Disable / Run now / create keep phrase confirm; Enable is direct |
| Feedback | Pass | Busy strip; notice guide; dry-run vs live result labels |
| Errors | Pass | what/why/next on load/refresh/discover/dry-run/run/create/enable/disable |
| Accessibility | Pass | Stage rail aria-current; labeled fields; focus rings on status pills and controls |
| Cognitive load | Pass | Honesty once; table then compose; no nested card soup |
| Trust | Pass | Dry-run never claims writes; risk phrase on live trigger / disable / save |
| Motion | Pass | Color transitions only; capture used reduced motion |
| Copy | Pass | Sentence case; verb buttons; no em dashes / Oops / AI magic |
| Density | Pass | 4/8 spacing; mono model/method; tabular next-run |
| Responsive | Pass | Narrow shots overflowX=0; table scrolls inside wrap |

## Vision verify notes (eyes on shots)

- Empty: Basalt chrome, teal List step + Save the cron, amber honesty band (caution role, not a CTA), teal empty guide.
- Select / list: Enable/Disable honesty pills; next-run stamped with Africa/Lagos; Dry-run and Run now secondary.
- Dry-run: "Dry-run result (no writes)" amber result; Trigger step current.
- Error narrow: red danger guide with classified timeout why + next; Save still teal primary.
- Compose narrow: next-run preview + Africa/Lagos; Save step; no horizontal page overflow.
- Done vs current rail chips both sit in the green/teal family (`--success` #059669 vs `--accent` #0f766e); readable via weight + fill, not a second hue.

## Known gaps (follow-ups)

- Live route still loads crons / models / probe over the network; harness does not mock VersionAwareness / FirstWrite interstitial chrome.
- Narrow table keeps horizontal scroll inside `.cr-table-wrap` for Next run / Active columns (page overflowX=0).
- Confirm dialog overlay not captured as its own vision state (existing ConfirmDialogV2; phrase contract unchanged).
- AppShell sidebar still open at 390px on the live shell (global); harness captures page body with overflowX=0.
- Success and accent are adjacent teals; done-step chips can read "teal" on quick glance.

## Not touched

`odoo_addons/`, code-studio, expert, bulk-suite, power-ops, housekeeping, reminders, script-runner, id-generator, ingest, import, menus, approvals, wizard, access, automations, job, designer, website, mail, qweb, studio, git state (no commit / stash / checkout / push / clean). No DONE. Isolated next fav on `:3032` stopped after tests/capture.
