# UI-S-37 · Live Demo Co-Pilot (Studio-bar visual leap)

Card: UI-S-37. Primary: **Launch bot / Start the session** (teal).
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

# UI-S-37 · Live Demo Co-Pilot look-and-feel (vision notes)

Card: UI-S-37 `…/live-demo-copilot` (+ presenter overlay). Pressure ~7. Primary: **Launch bot** (teal).
Status: elite UI pass implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before the UI edits:
- `/home/box/design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `/home/box/design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md` + `tokens.css`
- Studio-cluster peers (read only): UI-S-35 Script Runner, UI-S-33 Housekeeping
- Product docs: `docs/live-demo-copilot/{README,PROGRESS,ATTENDEE,OPS,PILOT}.md`

## Design Read

Operate-mode consent-first meeting assist. Basalt chrome, one teal **Launch bot** primary, honesty for mock vs live Attendee capture, private presenter overlay never for screen share. What/why/next on empty, consent, ready, live, mock, declined, waiting-host, answers empty, transcript empty, and error. Stage rail Meeting → Consent → Launch → Live. No purple, no orange primary CTAs, no em dashes, cinnabar never in UI.

## What the pass delivers

| Thesis item | Where |
|---|---|
| Launch bot is the sole teal primary | `live-demo-launch-btn` uses `variant="primary"`; Create / Record consent / Open overlay stay secondary |
| Honesty: mock vs live | Always-on `live-demo-honesty`; mode badge Mock/Live; limits call out WhatsApp out of scope + private overlay |
| What/why/next | State guide + empty answers/transcript guides; `LiveDemoErrorNotice` for disclosure/create/consent/launch/leave/status/feed/overlay |
| Stage rail | `LiveDemoStageRail` + `liveDemoStepFromState` |
| Basalt / teal chrome | `.live-demo-operate` scoped CSS (4pt rhythm, reduced-motion) |
| Overlay honesty | Presenter empty Why/Next; sanitize copy; Not for screen share badge kept |

## States captured (`after-*` via `capture.cjs`)

| State | Harness | Verify |
|---|---|---|
| empty | `?state=empty` | Meeting current; honesty unset; Launch disabled |
| consent | `?state=consent` | Consent current; meeting created guide |
| ready | `?state=ready` | Launch current; teal Launch enabled; live honesty |
| mock | `?state=mock` | Mock honesty; Mock badge; Live current |
| live | `?state=live` | Live honesty; transcript sample |
| declined | `?state=declined` | Declined what/why/next |
| waiting | `?state=waiting` | Host action guide |
| answers | `?state=answers` | Answer card with bullets |
| error | `?state=error` | Error notice what/why/next + Diagnose with Expert |

Canonical: `desktop.png` = after-empty-desktop, `narrow.png` = after-ready-narrow.
Every after shot measured `overflowX=0` at 1440×900 and 390×844 (reduced motion).

Regenerate:

```bash
cd apps/web
INGENIUM_DIST_DIR=.next-uis37 NEXT_PUBLIC_E2E=1 pnpm exec next dev -H 127.0.0.1 -p 3067
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-37/capture.cjs \
  http://127.0.0.1:3067 ../../docs/vision-verify/UI-S-37 after
# then stop the :3067 mirror only
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/liveDemoCopilotScreen.test.ts src/components/live-demo-copilot "src/app/connections/[id]/live-demo-copilot/page.test.tsx"` → **6 files, 13 passed**
- Playwright (against isolated `:3067`): `e2e/live-demo-copilot.spec.ts` → **5 passed**
- Vision: 18 after shots + desktop/narrow aliases; all overflowX=0

## UX audit (12 rows)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | One teal primary (Launch bot); honesty banner above the stage content |
| IA | Pass | Meeting → Consent → Launch → Live mirrors the real path |
| Interaction | Pass | Targets ≥24px; Launch disabled until consent; overlay secondary |
| Feedback | Pass | Mode badge; bot status Callout; SSE status on overlay |
| Errors | Pass | what/why/next on disclosure/create/consent/launch/leave/status/feed/overlay; Diagnose with Expert |
| Accessibility | Pass | Stage rail `aria-current`; labeled fields; consent checkboxes |
| Cognitive load | Pass | Panels one deep; limits separate from honesty |
| Trust | Pass | Explicit mock vs live; private overlay guidance; retention default do not retain |
| Motion | Pass | Rail transitions ≤150ms; reduced-motion capture; scoped CSS respects prefers-reduced-motion |
| Copy | Pass | Sentence case; verb buttons; no em dashes / Oops / AI magic |
| Density | Pass | 4/8 spacing; mono bot ids; tabular stage indexes |
| Responsive | Pass | Narrow shots overflowX=0; panels stack |

## Known gaps (follow-ups)

- Live page still depends on API for disclosure; harness empty hides consent panel until a session-like state (live page shows disclosure as soon as the API returns).
- Presenter overlay pop-out is not separately vision-captured (session page + harness cover the operate thesis; overlay unit tests cover empty/answer/low-confidence).
- Real Attendee join and first pilot remain operator work (`docs/live-demo-copilot/PILOT.md`), outside this UI pass.
- Next auto-touched `apps/web/tsconfig.json` include for `.next-uis37/types` (same pattern as other agent dist dirs). Left dirty; not committed.

## Not touched

`odoo_addons/`, id-generator, config, journal, operations, script-runner, cron-manager, reminders, expert, bulk-suite, power-ops, ingest, import, menus, approvals, wizard, access, automations, job, designer, website, mail, qweb, studio, code-studio, housekeeping, and other agent-owned screens. No DONE. No commit / stash / checkout / push / clean. Isolated `:3067` mirror stopped after capture; `:3002` left alone.
