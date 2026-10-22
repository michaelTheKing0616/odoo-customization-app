# UI-S-41 · Settings (Studio-bar visual leap)

Card: UI-S-41. Primary: **Create API key** (teal).
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

# UI-S-41 · API settings look-and-feel (vision notes)

Card: UI-S-41 `/settings` (347). Pressure 7. Primary: **Create API key** (teal); bootstrap uses **Generate first API key** when that path is open.
Status: elite UI pass implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before the UI edits:
- `/home/box/design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `/home/box/design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md` + `tokens.css`
- Global rules + UI-S-41 block in `docs/plans/next-phase/13_UI_SCREEN_SPECS.md`
- Studio-cluster peers (read only): UI-S-36 config, UI-S-35 script-runner, UI-S-38 journal
- Playbook §0 laws 3–9; ingenium-v2 Basalt / limestone / cinnabar-keystone-only

## Design Read

Operate-mode API settings desk. Basalt chrome, one teal primary (**Create API key**, or **Generate first API key** while bootstrap is open), honesty that browser save is localStorage-only, new keys are shown once, and revoke is permanent with phrase confirm. What/why/next on empty, idle, bootstrap, revealed, saved, and error. No purple, no orange primary CTAs, no em dashes, cinnabar never on buttons.

## What the pass delivers

| Thesis item | Where |
|---|---|
| Create API key is the sole teal primary (or bootstrap) | `settings-create-key-btn` / `settings-bootstrap-btn` use `variant="primary"`; Save in browser stays secondary |
| Honesty: browser save + one-time reveal | Always-on `settings-honesty`; revealed panel + guide; save guide after Save in browser |
| Revoke confirmation | `ConfirmDialogV2` danger + phrase `revoke this key` |
| What/why/next | Empty, idle, bootstrap, revealed, saved guides; `SettingsErrorNotice` for load/bootstrap/create/revoke/save/unlink |
| Stage rail | `SettingsStageRail` Status → Keys → Audit |
| Basalt / teal chrome | `.settings-operate` scoped CSS (4pt rhythm, reduced-motion) |

## States captured (`after-*` via `capture.cjs`)

| State | Harness | Verify |
|---|---|---|
| empty | `?state=empty` | Empty what/why/next; Create API key teal; Keys empty |
| idle | `?state=idle` | Honesty + idle guide; teal Create API key; Save secondary |
| bootstrap | `?state=bootstrap` | Bootstrap guide; teal Generate first API key; no Create |
| revealed | `?state=revealed` | Copy-once guide + reveal panel; Keys step current |
| saved | `?state=saved` | Browser-save honesty guide |
| error | `?state=error` | Error notice what/why/next + Diagnose with Expert |

Canonical: `desktop.png` = after-idle-desktop, `narrow.png` = after-revealed-narrow.
Every after shot measured `overflowX=0` at 1440×900 and 390×844 (reduced motion).

Regenerate:

```bash
cd apps/web
INGENIUM_DIST_DIR=.next-uis41 NEXT_PUBLIC_E2E=1 pnpm exec next dev -H 127.0.0.1 -p 3071
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-41/capture.cjs \
  http://127.0.0.1:3071 ../../docs/vision-verify/UI-S-41 after
# then stop the :3071 mirror only
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/settingsScreen.test.ts src/components/settings src/app/settings/page.test.tsx` → **5 files, 13 passed**
- Playwright (against isolated `:3071`): `e2e/settings.spec.ts` → **7 passed**
- Vision: 12 after shots + desktop/narrow aliases; all overflowX=0

## UX audit (12 rows)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | One teal primary (Create or Generate first); Save secondary; Revoke ghost/danger |
| IA | Pass | Stage rail mirrors Status → Keys → Audit |
| Interaction | Pass | Revoke needs phrase confirm; Copy on one-time reveal |
| Feedback | Pass | Busy strip; saved / revealed guides; Copied label |
| Errors | Pass | what/why/next on load/bootstrap/create/revoke/save/unlink; Diagnose with Expert |
| Accessibility | Pass | Stage rail aria-current; labeled key fields; focus rings on links |
| Cognitive load | Pass | Honesty separate from contextual guide; panels one deep |
| Trust | Pass | localStorage honesty; shown-once; revoke permanent; never claims server sync |
| Motion | Pass | Color/border transitions only; capture used reduced motion |
| Copy | Pass | Sentence case; verb buttons; no em dashes / Oops / AI magic |
| Density | Pass | 4/8 spacing; mono prefixes; tabular nums |
| Responsive | Pass | Narrow shots overflowX=0; cards stack |

## Vision verify notes (eyes on shots)

- Idle desktop: Basalt quiet surfaces; amber honesty; teal idle guide; teal Create API key; secondary Save in browser; Keys list with revoke.
- Revealed desktop: Keys step current; copy-once guide + reveal panel; Copy key secondary.
- Bootstrap narrow: teal Generate first API key; no Create; empty audit.
- Error desktop: danger notice with Diagnose with Expert; Save stays secondary.

## Siblings for follow-up (not elevated this pass)

- UI-S-42 `/settings/billing`
- UI-S-43 `/settings/trust-safety`
- UI-S-44 `/admin`
- UI-S-45 `/pipelines`

## Not touched

plan-inbox, fleet/command, bots/bridge, live-demo-copilot, journal, connection `…/config`, `odoo_addons/`, DONE markers, git commit/push/stash.
