# UI-S-34 · Reminders (Studio-bar visual leap)

Card: UI-S-34 `…/reminders`. Pressure 4 → cheap. Primary: **Create the reminder** (teal).
Status: Studio-bar visual leap implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before the leap:
- `/home/box/design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `/home/box/design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md` + tokens
- Premium eyes: UI-S-12 Designer chrome + UI-S-20-premier App Studio density
- Prior elevate (basic operate pass) preserved as `before-*`

## Design Read

Operate-mode reminder wizard with Designer-class basalt studio chrome. Session honesty lives in the studio bar (schedule on vs template-only). Empty what/why/next is a compact paper brief, not a second stacked banner. Paper desk + cream sheet for compose. One teal primary. No twin-banner formula. Claude/Stitch density.

## Before → after craft

| Before (elevate) | After (Studio-bar leap) |
|---|---|
| Plain title + pill step chips | Basalt `rm-studio` chrome with titlebar |
| Twin banners: honesty Callout + empty guide stacked | Honesty folded into `ReminderStudioBar`; empty as `density="brief"` |
| Flat white panel on gray page | Dot-grid desk + cream paper lift |
| Pill rail on light surface | Connected Studio nodes on basalt |
| Basic 42rem form card | 52rem shell, denser type (−0.02em), 8px field radius |

## What the leap delivers

| Thesis item | Where |
|---|---|
| Studio bar | `ReminderStudioBar` + `reminders-studio-chrome` |
| No twin-banner | Honesty only in bar; empty is brief inside paper |
| Create the reminder sole teal primary | `reminders-create-btn` unchanged |
| Schedule honesty | Bar title flips Schedule enabled vs Template only; schedule chip kept |
| Paper desk | `.rm-desk` / `.rm-paper` |
| Step rail | Connected nodes on chrome |

## States captured (`after-*`; prior elevate copied to `before-*`)

empty, schedule, template-only, confirm, created, created-template, error × desktop + narrow.
All measured `overflowX=0` (desktop confirmed; narrow re-captured with leap).

Regenerate:

```
cd apps/web
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-34/capture.cjs \
  http://127.0.0.1:3002 ../../docs/vision-verify/UI-S-34 after
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/remindersScreen.test.ts src/components/reminders` → **3 files, 13 passed**
- Playwright on shared `:3002` (no isolated mirror): `e2e/reminders.spec.ts` → **5 passed** (studio bar honesty + empty brief; template-only; created; created-template; error)

## Known gaps

- Live page still loads connection over the network; harness does not mock VersionAwarenessBanner.
- Confirm dialog itself is not screenshot-open in harness (confirm state uses a hint guide).
- Shared `:3002` reused; no agent mirror left running for this card.

## Files touched

- `apps/web/src/components/reminders/ReminderStudioBar.tsx` (+ test)
- `apps/web/src/components/reminders/ReminderStateGuide.tsx` (brief density)
- `apps/web/src/components/reminders/reminders-operate.css`
- `apps/web/src/app/e2e/reminders/page.tsx`
- `apps/web/src/app/connections/[id]/reminders/page.tsx`
- `apps/web/e2e/reminders.spec.ts`
- `docs/vision-verify/UI-S-34/{before,after}-*.png`, `NOTES.md`

## Not touched

`odoo_addons/`, git state (no commit/stash/checkout/push/clean), DONE markers, operations/fleet/bulk/power-ops/cron/housekeeping/plan-inbox/bots/billing/connect.
