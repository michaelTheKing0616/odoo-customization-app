# UI-S-28 · Universal Ingest (Studio-bar visual leap)

Card: UI-S-28 `…/ingest`. Primary: **Commit** (teal).
Status: Studio-bar visual leap implemented locally. **Not marked DONE.** Nothing committed.

## Design Read
Always-on dry-run Callout collapsed into OperateStudioBar. Basalt chrome + paper desk. Step rail uses data-state for connected nodes on basalt.

## What changed
- Removed twin `ingest-honesty` Callout stack; honesty in bar (`ingest-honesty` test id preserved on bar).
- OperateStudioChrome wraps page + harness.
- IngestStepRail emits data-state for studio chrome styling.
- Helpers in `lib/ingestScreen.ts`.

## Gaps
- Override reason still UI-gated only (API freeze).
- Vision OCR / prefs banners remain situational inside paper.

## Not touched
odoo_addons/, git, DONE. Stay out of operations/fleet/bulk/power-ops/cron/reminders peers.


---

## Prior elevate notes (archive)

# UI-S-28 · Universal Ingest (Studio-bar visual leap)

Status: Studio-bar visual leap implemented locally. **Not marked DONE.**

Always-on dry-run Callout collapsed into OperateStudioBar. Basalt chrome + paper desk. IngestStepRail uses data-state. Helpers in lib/ingestScreen.ts. Harness + page wrapped.

Gaps: override reason UI-gated only; vision OCR banners remain situational.

Not touched: odoo_addons/, git, DONE.


---

## Prior elevate notes (archive)

# UI-S-28 · Universal Ingest look-and-feel (vision notes)

Card: UI-S-28 `…/ingest` (504). Pressure 7. Primary: **Commit** (teal).
Status: elite UI pass implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before the UI edits:
- `design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md`
- Global rules + UI-S-28 block in `docs/plans/next-phase/13_UI_SCREEN_SPECS.md`
- Prime: `ui-craft-dense-dashboard`, `no-ai-slop`, `ux-copy`, `error-handling-ux`, `feedback-patterns`

## Design Read

Operate-mode master-data pipeline. Basalt chrome, one teal accent on Commit and the active step, honesty for dry-run vs commit, what/why/next on empty, gaps, and override. No purple, no orange primary, no em dashes, no Jane Doe placeholders.

## What the pass delivers

| Thesis item | Where |
|---|---|
| Commit is the sole teal primary | `ingest-commit-btn` uses `variant="primary"`; Dry-run / Analyze / Interview stay secondary |
| Dry-run vs commit honesty | Always-on Callout `ingest-honesty`; log labels "Dry-run result (no writes)" vs "Commit result (writes applied)" |
| Override needs a reason | Reason field (≥3 chars) gates `ingest-apply-overrides`; session notice echoes the reason (API contract unchanged) |
| Step rail | `IngestStepRail` + `resolveIngestStep` (upload → classify → plan → dry-run → commit) |
| Labeled fields, no fake people | Interview uses `Input`/`Textarea` labels; empty defaults (no Jane Doe / Widget) |
| Gaps what/why/next | Warning Callout `ingest-gaps` + red `ingest-gap-block` |

## States captured (`after-*` via `capture.cjs`; `before-planned-*` pre-pass)

| State | Harness | Verify |
|---|---|---|
| empty | `?state=empty` | Upload step active; empty what/why/next; Analyze disabled |
| planned | default / `?state=planned` | Gaps Callout; Commit disabled + gap-block; Plan step active |
| override | `?state=override` | Confirm type; reason gates Apply |
| dry-run | `?state=dry-run` | Log says no writes; Commit enabled; Dry-run step active |
| committed | `?state=committed` | Log says writes applied; Commit step active |

Every after shot measured `overflowX=0` at 1440×900 and 390×844 (reduced motion).

Regenerate:

```
cd apps/web
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-28/capture.cjs \
  http://127.0.0.1:3002 ../../docs/vision-verify/UI-S-28 after
```

## Tests

- Vitest: `pnpm exec vitest run src/components/ingest` → **1 file, 5 passed**
- Playwright (against existing `:3002`, no isolated mirror): `e2e/ingest.spec.ts` → **4 passed** (gaps block commit; override reason; dry-run honesty; empty what/why/next)
- Typecheck: no new ingest page/component TS errors (pre-existing repo debt elsewhere unchanged)

## UX audit (12 rows)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | One teal primary (Commit); honesty banner above the step rail |
| IA | Pass | Step rail mirrors the real pipeline; classification → order → prefs → actions |
| Interaction | Pass | Targets ≥24px; Commit disabled while gaps exist; override Apply gated on reason |
| Feedback | Pass | Dry-run/commit logs are labeled; busy skeleton on first analyze |
| Errors | Pass | what/why/next on select/analyze/override/interview failures; gaps Callout |
| Accessibility | Pass | Step rail `aria-current`; labeled inputs; radio fieldset; focus rings on dropzone |
| Cognitive load | Pass | Removed Jane Doe defaults; human doc-type labels; no nested cards beyond one level |
| Trust | Pass | Honesty banner; dry-run never claims writes; financial confirm phrase kept |
| Motion | Pass | Color transitions 80ms only; capture used reduced motion |
| Copy | Pass | Sentence case; verb buttons; no em dashes / Oops / AI magic |
| Density | Pass | 4/8 spacing; mono filenames; tabular confidence % |
| Responsive | Pass | Narrow shots overflowX=0; file row stacks on small widths |

## Known gaps (follow-ups)

- Override reason is UI-gated and echoed in the notice only; API `force_doc_types` body has no reason field (contract freeze).
- Harness empty state is thinner than the live page (no interview card) by design for vision focus.
- Live page still loads vision OCR + prefs over the network; harness does not mock those banners.
- Pre-existing `lib/api/ingest.ts` `formatDetailMessage` TS error left untouched.

## Not touched

`odoo_addons/`, code-studio, expert, import, menus, approvals, wizard, access, automations, job, designer, website, mail, qweb, studio, git state (no commit / stash / checkout). No isolated next/dev mirror started.
