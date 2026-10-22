# UI-S-38 · Journal (Studio-bar visual leap)

Card: UI-S-38. Primary: **Roll back** (teal).
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

# UI-S-38 · Change Journal look-and-feel (vision notes)

Card: UI-S-38 `…/journal` (~356). Pressure 8. Primary: **Roll back** (teal).
Status: elite UI pass implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before the UI edits:
- `/home/box/design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `/home/box/design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md`
- Global rules + UI-S-38 block in `docs/plans/next-phase/13_UI_SCREEN_SPECS.md`
- Studio-cluster peers (read only): UI-S-31 power-ops, UI-S-35 script-runner
- Playbook §0 laws 3–9; ingenium-v2 Basalt / limestone / cinnabar-keystone-only

## Design Read

Operate-mode change journal and accounting batch desk. Basalt chrome, one teal **Roll back** primary on reversible snapshots. Honesty that restores can be partial (dropped columns stay), audit rows are replay not undo, and chain verify is planned with T5A-03 (not claimed live). What/why/next on empty, idle, partial, irreversible, audit, health, restored, and error. No purple, no orange primary CTAs, no em dashes, cinnabar never on buttons.

## What the pass delivers

| Thesis item | Where |
|---|---|
| Roll back is the sole teal primary on timeline | `journal-rollback-*` / harness `journal-rollback-btn` use `variant="primary"`; Intake on batch is secondary; Apply drafts stays primary only inside batch tab |
| Partial / irreversible honesty | `partialRollbackGuide`, `irreversibleGuide`, `reversibilityCopy`; badges Fully / Partially / Not reversible |
| Audit is replay | `auditReplayGuide` + honesty banner |
| Chain verify not claimed | `journal-chain-note` cites T5A-03 |
| Stage rail | `JournalStageRail` Timeline → Inspect → Roll back |
| What/why/next | Empty, idle, partial, irreversible, audit, health, restored, error via guides + `JournalErrorNotice` |
| Basalt / teal chrome | `.journal-operate` scoped CSS (4pt rhythm, reduced-motion) |

## States captured (`after-*` via `capture.cjs`)

| State | Harness | Verify |
|---|---|---|
| empty | `?state=empty` | Empty what/why/next; Refresh timeline; Timeline step current |
| idle | `?state=idle` | Honesty + idle guide; teal Roll back enabled; chain note |
| partial | `?state=partial` | Partial guide; Inspect step; dropped-columns honesty |
| irreversible | `?state=irreversible` | Irreversible guide; Roll back disabled |
| audit | `?state=audit` | Audit replay honesty |
| health | `?state=health` | Broken sweep guide |
| restored | `?state=restored` | Success guide; Roll back step current |
| error | `?state=error` | Error notice what/why/next + Diagnose with Expert |

Canonical: `desktop.png` = after-idle-desktop, `narrow.png` = after-partial-narrow.
Every after shot measured `overflowX=0` at 1440×900 and 390×844 (reduced motion).

Regenerate:

```bash
cd apps/web
INGENIUM_DIST_DIR=.next-uis38 NEXT_PUBLIC_E2E=1 pnpm exec next dev -H 127.0.0.1 -p 3068
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-38/capture.cjs \
  http://127.0.0.1:3068 ../../docs/vision-verify/UI-S-38 after
# then stop the :3068 mirror only
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/journalScreen.test.ts src/components/journal src/components/batch-os/JournalBatchPanel.test.tsx` → **5 files, 9 passed**
- Playwright (against isolated `:3068`): `e2e/journal.spec.ts` → **9 passed**
- Vision: 16 after shots + desktop/narrow aliases; all overflowX=0

## UX audit (12 rows)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | One teal primary (Roll back) on timeline; honesty above rail |
| IA | Pass | Stage rail mirrors Timeline → Inspect → Roll back |
| Interaction | Pass | Roll back disabled when not reversible; entry cards keyboard selectable |
| Feedback | Pass | Busy strip on restore; success guide after rollback |
| Errors | Pass | what/why/next on load/refresh/rollback; Diagnose with Expert |
| Accessibility | Pass | Stage rail aria-current; tablist on surfaces; focus rings on broken links |
| Cognitive load | Pass | Idle guide only when nothing selected; selection shows one contextual guide |
| Trust | Pass | Partial restore + audit replay + T5A-03 chain note; never claims auto-undo |
| Motion | Pass | Color/border transitions only; capture used reduced motion |
| Copy | Pass | Sentence case; verb buttons; no em dashes / Oops / AI magic |
| Density | Pass | 4/8 spacing; mono meta; tabular timestamps |
| Responsive | Pass | Narrow shots overflowX=0; card heads wrap |

## Vision verify notes (eyes on shots)

- Idle desktop: Basalt chrome feel via quiet surfaces; teal Roll back; amber honesty; disabled Roll back on irreversible card; audit/health rows read-only.
- Partial narrow: Inspect step current; partial guide with dropped-columns honesty; no horizontal overflow.
- Empty: teal-accent empty guide + Refresh timeline secondary.
- Error: danger notice with classified timeout why + Diagnose with Expert.

## Known gaps (follow-ups)

- Chain verify UI (T5A-03) is honesty-only; no verify action yet.
- Batch / invoices / orders / master tabs keep existing panels; only JournalBatchPanel honesty + Intake secondary polished; Document/Order/Master panels not restyled.
- Live route still loads snapshots/audits/health over the network; harness is API-free.
- Confirm dialog not used for Roll back today (existing API contract); phrase confirm remains on batch Apply post (L2).
- App shell / Next.js dev indicator may appear in harness shots; page body overflowX=0.
- Shared `EMPTY_STATES.journal` / `REVERSIBILITY` in copy-guide still contain em dashes; screen uses local `journalScreen` copy instead.

## Not touched

`odoo_addons/`, id-generator, operations, config, script-runner, cron-manager, reminders, expert, bulk-suite, power-ops, housekeeping, and other screens other agents own. Git state untouched (no commit / stash / checkout / push / clean). **Not marked DONE.** Isolated Next on `:3068` with `.next-uis38` started for capture/tests and stopped after. Ports `:3002` / other agents left alone.
