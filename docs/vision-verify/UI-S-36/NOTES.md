# UI-S-36 · Config / Instance Config (Studio-bar visual leap)

Card: UI-S-36. Primary: **Save the setting** (teal).
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

# UI-S-36 · Instance Config look-and-feel (vision notes)

Card: UI-S-36 `…/config` (946→split UI-SP-CONFIG). Pressure 7. Primary: **Save the setting** (teal).
Status: elite UI pass implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before the UI edits:
- `/home/box/design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `/home/box/design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md`
- Global rules + UI-S-36 block in `docs/plans/next-phase/13_UI_SCREEN_SPECS.md`
- Studio-cluster peers (read only): UI-S-31 power-ops, UI-S-35 script-runner
- Prime: `ui-craft-dense-dashboard`, `no-ai-slop`, `ux-copy`, `error-handling-ux`, `feedback-patterns`

## Design Read

Operate-mode recipe Command Center for Day-1, numbering, apps, allowlisted settings, and master packs. Basalt chrome, one teal primary per panel (**Save the setting** on settings board; **Apply** / **Apply pack** / **Install pack** / **Create company** on other panels), honesty that dry-run never writes and Save/Apply are live with the risk phrase. What/why/next on empty, idle, error, and applied. Open links stay secondary. No purple, no orange primary CTAs, no em dashes, cinnabar never in UI (danger tokens stay on ConfirmDialogV2 only).

## What the pass delivers

| Thesis item | Where |
|---|---|
| Save the setting is the settings primary | `config-save-setting-btn` uses `variant="primary"`; Dry-run stays secondary |
| Apply locked until dry-run | `dryRunKey === applyKey` + unlock reason copy |
| Honesty: dry-run never writes | Always-on `config-honesty`; confirm warning repeats it |
| What/why/next | Empty, idle, applied guides; `ConfigErrorNotice` for load/dry-run/apply/settings/atlas/panel |
| Stage rail | `ConfigStageRail` Recipes → Configure → Dry-run → Save |
| Result honesty | `config-result-label` "Dry-run plan (no writes)" / "Applied plan (writes applied)" |
| Basalt / teal chrome | `.config-operate` scoped CSS (4pt rhythm, reduced-motion) |

## States captured (`after-*` via `capture.cjs`)

| State | Harness | Verify |
|---|---|---|
| empty | `?state=empty` | Empty what/why/next; Recipes current |
| idle | `?state=idle` | Honesty + idle guide; recipe cards; Open secondary |
| configure | `?state=configure` | Apply locked; unlock reason; Configure current |
| dry-run | `?state=dry-run` | No-writes label; Apply unlocked teal; Dry-run current |
| settings | `?state=settings` | Teal **Save the setting**; dry-run plan label |
| applied | `?state=applied` | Writes-applied label; applied guide; Save current |
| error | `?state=error` | Error notice what/why/next + Diagnose with Expert |

Canonical: `desktop.png` = after-idle-desktop, `narrow.png` = after-settings-narrow.
Every after shot measured `overflowX=0` at 1440×900 and 390×844 (reduced motion).

Regenerate:

```bash
cd apps/web
INGENIUM_DIST_DIR=.next-uis36 NEXT_PUBLIC_E2E=1 pnpm exec next dev -H 127.0.0.1 -p 3066
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-36/capture.cjs \
  http://127.0.0.1:3066 ../../docs/vision-verify/UI-S-36 after
# then stop the :3066 mirror only
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/configScreen.test.ts src/components/config` → **6 files, 12 passed**
- Playwright (against isolated `:3066`): `e2e/config.spec.ts` → **8 passed**
- Vision: 14 after shots + desktop/narrow aliases; all overflowX=0

## UX audit (12 rows)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | One teal primary per panel (Save the setting / Apply*); Open secondary |
| IA | Pass | Stage rail mirrors Recipes → Configure → Dry-run → Save |
| Interaction | Pass | Apply/Save disabled until dry-run key matches; phrase confirm kept |
| Feedback | Pass | Plan honesty labels; busy progress strip; unlock reason |
| Errors | Pass | what/why/next on load/dry-run/apply/settings/atlas/panel |
| Accessibility | Pass | Stage rail `aria-current`; labeled settings filter; focus rings on packs |
| Cognitive load | Pass | Cards one deep; honesty separate from recipe grid |
| Trust | Pass | Honesty banner; dry-run never claims writes; risks listed before confirm |
| Motion | Pass | Color transitions only; capture used reduced motion; prefers-reduced-motion |
| Copy | Pass | Sentence case; verb buttons; no em dashes / Oops / AI magic on chrome |
| Density | Pass | 4/8 spacing; mono keys/ops; tabular nums |
| Responsive | Pass | Narrow shots overflowX=0; grid stacks |

## Vision verify notes (eyes on shots)

- Idle: Basalt chrome, teal Recipes step, amber honesty band, teal idle guide, secondary Open on recipe cards.
- Configure: Apply teal but disabled; unlock reason visible; Configure current.
- Dry-run narrow: "Dry-run plan (no writes)" + unlocked teal Apply; no horizontal overflow.
- Settings: teal **Save the setting**; dry-run plan label.

## Known gaps (follow-ups)

- Live route still loads recipes/atlas over the network; harness does not mock VersionAwareness / fingerprint / expert disclosure chrome.
- Expert controls (sequences, mail/paper, scheduled i18n) keep prior forms inside Disclosure; not given their own stage rail.
- Offline-queued state for settings writes is not built.
- App shell may stay open at 390px on the live route; harness shots are shell-light via `/e2e/config`.
- Confirm dialog overlay not captured as its own vision state (existing ConfirmDialogV2; phrase contract unchanged).
- T5B import/export controls remain depends_on for deeper settings export (card note); UI dry-run gate shipped without waiting on T5B.

## Not touched

`odoo_addons/`, script-runner, id-generator, operations, cron-manager, reminders, expert screen, bulk-suite, power-ops, housekeeping, import, code-studio, git state (no commit / stash / checkout / push / clean). Isolated Next on `:3066` with `.next-uis36` was started and stopped after capture. Ports `:3002` / other agents left alone. **Not marked DONE.**
