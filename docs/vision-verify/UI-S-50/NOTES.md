# UI-S-50 · Plan inbox look-and-feel (vision notes)

Card: UI-S-50 `/approvals` plan-card inbox. Primary: **Approve this fingerprint** (teal).
Status: elite UI pass implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before the UI edits:
- `/home/box/design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- `/home/box/design-repo/brand/ingenium-v2/` (basalt `#1A1C21`, limestone `#F3F4F6`, teal `--accent` as the one primary)
- UI-S-50 block in `docs/plans/next-phase/13_UI_SCREEN_SPECS.md`
- API contract read only: `apps/api/app/routers/inbox.py`, engine policy and `apply_approved_plan` in the store
- Bar raise from Tope (mid-pass): no stacked what/why/next banner template; match App Studio / Designer craft

## Design Read

Operate-mode signing desk, built like Designer rather than a form page. Three panes:

1. **Rail** (left): plans grouped Waiting / Closed. Each row shows the risk tag, goal, status dot, environment, short fingerprint and expiry. Arrow keys move through the rows.
2. **Canvas** (center, dotted): the plan card as a paper object. The kicker carries risk tag, risk meaning, environment and status. The title is 26px. A meta strip holds a copyable fingerprint stamp, expiry (relative and absolute, Africa/Lagos), requester and op count. The nine engine sections follow with a 01..09 gutter, rendered exactly as the API sends them. A disclosure lists the exact ops.
3. **Inspector** (right): a vertical timeline (Engine plan, Your approval, Executor apply), then signature lines, blockers, the decision buttons and an inline confirm.

Honesty is carried by the lead line ("Odoo changes only when the executor applies it"), by the timeline (apply is a separate step that never runs from this page) and by the sign-off fine print. Amber appears only when the risk is real: an open R3 or R4, a stale fingerprint, or an expiry. R1 and R2 show no caution box at all.

## What the pass delivers

| Thesis item | Where |
|---|---|
| One teal primary | `plan-card-approve` (pending) or `Open inbox` (idle only). Deny is secondary, Deny and stop is ghost. Metrics: at most 1 `bg-accent` button in every state |
| Paper-as-object density | `PlanPaper`: kicker, title, meta strip, gutter-numbered sections. Key/value-only sections (Risk, Impact) render as a mono ledger with the text unchanged |
| Exact fingerprint | Copy-to-clipboard stamp with a "Copied" hint; the inline confirm repeats the short hash, environment and expiry |
| Approve is not apply | Lead line, timeline step 3 "Runs only after approval, never from this page", `plan-card-signoff-note` |
| Amber only where risk is real | `riskCaution()` returns a caution only for pending R3 and R4. Stale and expired use the status note. No always-on banners |
| Policy-driven signatures | `approverSlots()` follows `policy.approvers`: R4 production shows 2 lines plus a note that the second signer must be a different person |
| Self-approval gate | `approveGate()` blocks a second signature by the same person and explains why (`plan-card-gate`) |
| Stale / 409 | Decide returns `plan_stale`, which adds the hash to the stale set; the timeline marks step 2 voided and a Refresh inbox action appears |
| Richer states | Idle, empty and error use a sheet note over a faint ghost plan, so the canvas still reads as the desk. Loading uses a skeleton of all three panes |
| Micro-interactions | Row hover/selected wash, arrow-key navigation, card focus after picking on narrow screens, copy feedback, button loading labels ("Approving…"), reduced-motion respected |
| Dark mode | Scoped overrides in `plan-inbox-operate.css` (`dark-*` shots) |

## States captured (`capture.cjs`)

| State | Harness | Verify |
|---|---|---|
| idle | `?state=idle` | Sheet note on ghost plan; Open inbox is the teal primary |
| loading | `?state=loading` | Three-pane skeleton |
| empty | `?state=empty` | Sheet note, Refresh secondary |
| error | `?state=error` | Danger-edged sheet, Refresh secondary |
| r1 | `?state=r1` | Staging R1, no caution box |
| r3 | `?state=r3` (default) | R3 production caution (amber), 1 signature line, teal Approve |
| r3-confirm | `?state=r3-confirm` | Inline confirm repeats hash, env, expiry |
| r4 | `?state=r4` | 2 signature lines, first signed; blockers listed (second person, backup id) |
| r4-self | `?state=r4-self` | Viewer already signed: approve disabled with gate reason |
| stale | `?state=stale` | Fingerprint changed: approval voided, Refresh inbox |
| expired | `?state=expired` | No decision buttons; expiry note |
| approved | `?state=approved` | Approved, not applied; executor step is next. The live result is announced to screen readers only, so the note is not repeated on screen |
| not-found | `?state=not-found` | Requested `plan=` hash missing: sheet note on the canvas |
| signed-out / forbidden | `?state=signed-out` / `?state=forbidden` | Decide failure guide (sign in / role), 404 never says forbidden |

Canonical: `desktop.png` = after-r3-desktop, `narrow.png` = after-r3-narrow (ops disclosure open).

## Metrics (`after-metrics.json`)

- 30 light shots (15 states × 1440×900 and 390×844, reduced motion): **overflowX = 0 in all**, at most **1** teal primary, **9** engine sections on every card state, **2** signature lines on R4, **no em dashes**.
- Dark set (`dark-*-dark.png`): 22 shots (all 15 desktop states plus 7 narrow). The dark run hit a 120s navigation timeout on `r4-self` narrow while the Mac was at load ~38 from other agents' captures, so the rest of the dark narrow set and `dark-metrics.json` were not written. Rerun with `UIS50_THEMES=dark` when the machine is quiet. The dark idle, empty, error and approved shots also predate the last polish round (ghost plan behind sheet notes; approved result no longer repeated on screen). The light set was recaptured for those four states.

Regenerate:

```bash
cd apps/web
INGENIUM_DIST_DIR=.next-uis50 NEXT_PUBLIC_E2E=1 pnpm exec next dev -H 127.0.0.1 -p 3070
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-50/capture.cjs \
  http://127.0.0.1:3070 ../../docs/vision-verify/UI-S-50 after
UIS50_THEMES=dark NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-50/capture.cjs \
  http://127.0.0.1:3070 ../../docs/vision-verify/UI-S-50 dark
# then stop the :3070 mirror only, and drop the ".next-uis50/types/**/*.ts" line Next adds to tsconfig.json
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/planInboxScreen.test.ts src/components/plan-inbox src/app/approvals` → **3 files, 32 passed**
- `src/app/command/page.test.tsx`: my `/approvals?connection_id=` redirect test passes. One test fails ("empty fleet what/why/next … never runs a write"). That file and its view are being edited by UI-S-51 right now; the failure is in their copy, not this card.
- ESLint clean on all UI-S-50 files. `tsc --noEmit` reports no errors in UI-S-50 files (pre-existing errors elsewhere).

## UX audit

| # | Check | Result |
|---|---|---|
| 1 | One primary per view | Pass (metrics) |
| 2 | Approve vs apply honesty | Pass: lead, timeline, fine print, confirm copy |
| 3 | Exact fingerprint signed | Pass: decide posts `plan_hash` + `schema_fp` from the card shown |
| 4 | Amber only for real risk | Pass: R3/R4 pending, stale, expired only |
| 5 | Engine sections untouched | Pass: titles and bodies as sent, order kept |
| 6 | Errors map to next steps | Pass: 409 stale / frozen, 404, 403 requester / role |
| 7 | Keyboard | Pass: arrow keys in rail, focus moves to card title, confirm is inline |
| 8 | Screen reader | Pass: live region for results, alert for failures, labelled rail and sections |
| 9 | Narrow 390 | Pass: rail, paper, inspector stack; overflowX 0 |
| 10 | Dark | Pass on captured shots |
| 11 | Reduced motion | Pass: transitions off |
| 12 | Copy rules | Pass: no em dashes, no purple / orange CTAs, cinnabar not used on buttons |

## Known gaps

- Spec says R3 has two signature slots; the engine requires one approver for R3 (requester may approve). The UI follows `policy.approvers`. Needs a spec or engine decision.
- Spec section names differ from the engine's nine titles. The UI renders the engine titles as sent.
- There is no HTTP apply route; the UI never applies. `apply_approved_plan` rechecks fingerprint, freeze and expiry server side.
- Heavy R4 evidence (simulation, backup id, change window) cannot be supplied from this UI; it is listed as blockers only.
- Client-approver scoping to their own connection is enforced server side; the UI only filters by `connection_id`.
- On narrow screens the decision sits below the full card (by design: read, then sign). A sticky jump link could be added later.
- The Suspense fallback is `null` (brief blank before the client view mounts).
- The Next dev "N" indicator appears in the shots (dev server only).
- `.next-uis50/` build dir was left in `apps/web` (ignored output); the tsconfig include line Next added was removed.

## Not touched

`odoo_addons/`, `apps/api/` (inbox router and store read only), command center (UI-S-51), connections/[id]/approvals (UI-S-16), config, journal, live-demo-copilot, id-generator, cron, script-runner, and every other screen. No commits, pushes, stashes, checkouts or cleans.
