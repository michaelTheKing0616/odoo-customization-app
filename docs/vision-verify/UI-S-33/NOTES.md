# UI-S-33 · Attachment housekeeping (vision notes)

Card: UI-S-33 `…/housekeeping` (538→705). Pressure 7. Primary: **Clean** (teal).
Status: elite UI pass implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before the UI edits:
- `~/Desktop/prime-skills-pack/docs/DESIGN_SYSTEM_PLAYBOOK.md`
- `~/Desktop/ingenium-v2/final/BRAND_GUIDE.md`
- Global rules + UI-S-33 block in `docs/plans/next-phase/13_UI_SCREEN_SPECS.md`
- Peer craft: UI-S-28 ingest (step rail, honesty Callout, sole teal primary)

## Design Read

Operate-mode destructive attachment cleanup. Basalt chrome, one teal accent on Clean, honesty for dry-run vs permanent delete, snapshot id shown when present, what/why/next on empty and results. No purple, no orange primary CTA, no em dashes, no AI-slop.

## What the pass delivers

| Thesis item | Where |
|---|---|
| Clean is the sole teal primary | `housekeeping-clean-btn` uses `variant="primary"`; scans / dry-run / recompute stay secondary |
| Dry-run vs clean honesty | Always-on Callout `housekeeping-honesty`; result labels "Dry-run result (no writes)" vs "Clean result (files deleted)" |
| Snapshot id shown | `housekeeping-snapshot-id` on clean result when `result.snapshot_id` present; harness cleaned/confirm show `snap_hk_7f3a` |
| Step rail | `HousekeepingStepRail` + `resolveHousekeepingStep` (scan → review → dry-run → clean) |
| Empty what/why/next | `EmptyState` when no scan yet |
| Labeled fields | `Input` for min bytes, older days, recompute model/field/ids |
| Destructive confirm kept | `ConfirmDialogV2` phrase + danger risks unchanged in spirit |

## States captured (`after-*` via `capture.cjs`)

| State | Harness | Verify |
|---|---|---|
| empty | `?state=empty` | Scan step active; empty what/why/next; Clean disabled |
| scanned | default / `?state=scanned` | Review step; 2 selected; Clean enabled |
| dry-run | `?state=dry-run` | Log says no writes; Dry-run step active |
| cleaned | `?state=cleaned` | Log says files deleted; snapshot id; Clean step active |
| confirm | `?state=confirm` | Confirm-phrase hint Callout; snapshot id on result |

Every after shot measured `overflowX=0` at 1440×900 and 390×844 (reduced motion).

Regenerate:

```
cd apps/web
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-33/capture.cjs \
  http://127.0.0.1:3002 ../../docs/vision-verify/UI-S-33 after
```

## Tests

- Vitest: `pnpm exec vitest run src/components/housekeeping` → **1 file, 5 passed**
- Playwright (against existing `:3002`, no isolated mirror): `e2e/housekeeping.spec.ts` → **4 passed** (empty what/why/next; scanned enables Clean; dry-run honesty; cleaned snapshot id)
- Typecheck: housekeeping page/harness/components clean for this surface

## UX audit (12 rows)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | One teal primary (Clean); honesty banner above the step rail |
| IA | Pass | Step rail mirrors scan → review → dry-run → clean |
| Interaction | Pass | Targets ≥24px; Clean disabled with empty selection |
| Feedback | Pass | Dry-run/clean logs labeled; snapshot chip on clean |
| Errors | Pass | ErrorNotice + what/why/next empty; probe Callout on recompute |
| Accessibility | Pass | Step rail `aria-current`; labeled inputs; checkbox aria-labels |
| Cognitive load | Pass | Cards one level deep; recompute demoted from competing primary |
| Trust | Pass | Honesty banner; dry-run never claims writes; confirm phrase kept |
| Motion | Pass | Color transitions 80ms only; capture used reduced motion |
| Copy | Pass | Sentence case; verb buttons; no em dashes / Oops / AI magic |
| Density | Pass | 4/8 spacing; mono linked models; tabular sizes |
| Responsive | Pass | Narrow shots overflowX=0 |

## Known gaps (follow-ups)

- Live `POST …/attachments/clean` does **not** yet create a snapshot before delete (`AttachmentCleanResult` has no snapshot_id wiring). UI surfaces id when present and harness demonstrates the required state; backend snapshot-on-clean is a follow-up outside this UI pass (and outside forbidden `bulk-suite` surface edits for this card).
- Harness is thinner than the live page (no duplicate card / recompute) by design for vision focus.
- Warning Callout / cleanable Badge use semantic warning (amber) tokens — not brand orange CTA. Primary remains teal.
- Shared `:3002` was restarted in-repo during the pass after it had started returning 500 on all routes; not an isolated mirror.

## Not touched

`odoo_addons/`, code-studio, expert, bulk-suite, power-ops, ingest, import, menus, approvals, wizard, access, automations, job, designer, website, mail, qweb, studio, git state (no commit / stash / checkout / push / clean). No DONE. No isolated next/dev mirror left running for this card.
