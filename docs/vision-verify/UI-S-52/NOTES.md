# UI-S-52 Bots / Bridge pass: Contract Studio (vision notes)

Status: elite UI pass done and checked locally, after the bar raise. **Not marked DONE.** Nothing committed.

## Why this surface (scope decision)

UI-S-52 is `/bots` (roster). That route does not exist, and the API card it needs (T8-BOT-ROSTER) is still OPEN. T7 says Bot and Bridge screens wait until their API cards are DONE, so building a roster with nothing behind it would have meant faking the data.
The only real bots/bridge surface in `apps/web` is `/bridge/contracts/new` (Contract Studio, seeded as UI-S-56, backed by `POST /api/bridge/contracts/validate`). This pass raises that screen to Studio-cluster craft. `/bots`, `/bots/rooms/[id]`, `/bots/[id]` and `/bridge/connections` were not built.

## Design Read

Operate-mode integration desk for a Bridge contract. It matches the View designer: basalt top bar, a dotted canvas holding the contract as a paper sheet, and an inspector on the right with Contract / Request tabs. **Validate tier I** is the single teal primary, in the bar. The honesty line sits in the bar as one quiet sentence ("Read-only check. Nothing connects, sends, or syncs."). There are no always-on banners. Amber appears only when Remote wins can overwrite Odoo. Success and danger are used only for Tier I outcomes. No purple, no orange CTAs, no em dashes, no cinnabar.

## Before / after

- `before-desktop.png`, `before-narrow.png`: a 123-line form with a centred stack of native inputs, a full-width teal bar, and a one-line result. There was no flow model, no request visibility, and no explanation of connect or send.
- `after-*`: a studio layout with the contract shown as an object. The full table is below.

| Thesis item | Where |
|---|---|
| Paper-as-object | `.br-sheet` on a dotted `.br-canvas`. Shows the title, the n/m checks tally, a flow diagram (Odoo node, direction wire, third-party node), label/value terms rows, the Tier I checks ledger, and a verdict footer |
| Real artifact, not a claim | The ledger rows match the backend's Tier I order: local rows (distinct ids, conflict rule, money policy, signature, no secrets) update as you type. Server rows (Odoo verified, third-party verified) show "Checked on validate" until Tier I answers, then pass, fail ("Not found" / "Unverified"), or "Not reached" when an earlier check stopped Tier I |
| One teal primary | `bridge-validate-btn` in the basalt bar, with a `⌘↵` hint (hidden on touch). Retry, Copy and Clear form are secondary or ghost. The active tab uses ink plus the indicator, not a fill |
| Honesty for connect / send | Bar sentence. The pass verdict says "Nothing has synced... this screen does not save or start a sync". The status chip shows Draft, Checking, Tier I passed, Refused, Edited since check, or Unreachable |
| Amber only for real risk | `bridge-risk` appears only when Remote wins is set on money or on two-way conflicts ("can overwrite Odoo order totals...") |
| Richer states | idle / ready, invalid (per-field instructions, first error focused, inline re-validate), validating (pulse dot, "Checking…", server rows "Checking…"), passed, refused (side-specific), error (HTTP status, entries kept, Try again), stale (edited after a check, timestamp shown), risk, request tab |
| Micro-interactions | Clicking a canvas node focuses and flashes its inspector field. Segmented controls. A switch for money. Glyph scale-in on pass/fail (`@starting-style`). Press scale 0.97. Copy changes to Copied. Cmd/Ctrl+Enter validates from anywhere. All motion is under 300ms, uses transform/opacity/colour only, and turns off under reduced motion |
| Responsive | At 390px the inspector comes first, the flow goes vertical with rotated chevrons, ledger details wrap under labels, and inputs are 16px |
| Dark | `after-refused-dark.png`: basalt bar, stepped paper `#1a1c21`, well `#0c0d10`, bright teal link `#5eead4` |

## States captured (`capture.cjs`, harness `/e2e/bridge-contract?state=`)

empty, two-way, invalid, validating, passed, refused, error, risk, request at 1440x900 and 390x844 (reduced motion), plus refused-dark. Every shot measured overflowX=0.
Canonical: `desktop.png` = after-refused-desktop, `narrow.png` = after-invalid-narrow.

Regenerate:
```
cd apps/web
INGENIUM_DIST_DIR=.next-uis52 NEXT_PUBLIC_E2E=1 pnpm exec next dev --turbopack -H 127.0.0.1 -p 3052
# repo root
NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-52/capture.cjs http://127.0.0.1:3052 docs/vision-verify/UI-S-52 after
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/bridgeContractScreen.test.ts src/components/bridge` gives **2 files, 25 passed**. Covers copy (no dashes or hype), honesty, per-field validation, the exact contract body, ledger rules, chip and risk logic, refusal mapping, canvas-to-inspector focus, Cmd+Enter, retry, stale, and reset.
- Playwright on isolated `:3052`: `e2e/bridge-contract.spec.ts` (9) plus the `a11y-primary` "Bridge contract" row gives **10 passed**, with axe clean (no serious or critical issues) on empty, invalid, passed, refused, risk, and request.
- eslint is clean on the touched files. `tsc` reports no errors in bridge files (19 errors exist elsewhere in the repo).

## UX audit

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | Sheet title, then tally, flow, terms, ledger, and verdict. One teal primary |
| IA | Pass | Canvas shows the contract. Inspector edits it. Request tab shows the exact body |
| Feedback | Pass | Ledger updates live. Chip, verdict, and timestamp. aria-live on the result |
| Errors | Pass | Per-field instructions. Server refusals are mapped back to their fields. Network errors keep entries |
| Trust | Pass | Says plainly that nothing connects, sends, or syncs. Server rows never pass without Tier I |
| Accessibility | Pass | Labelled radiogroups, role=switch, focus rings everywhere, sr-only status words in the ledger, axe clean |
| Motion | Pass | Purposeful, under 300ms, reduced-motion safe. The keyboard shortcut does not animate |
| Copy | Pass | Sentence case, verb-first buttons, no em dashes, no slop words |
| Density | Pass | 4pt rhythm. Inspector at 12 to 13px. Mono for ids and the request body. Tabular numbers on the tally |
| Responsive | Pass | Narrow reflows to a single column with overflowX=0 |

## Known gaps

- `/bots` roster (UI-S-52 proper) waits for T8-BOT-ROSTER. Rooms and workbench (UI-S-53/54) and `/bridge/connections` (UI-S-57, Verify) are not built, so "Run Verify" has no in-app link yet.
- There is no save or persist endpoint for contracts. The screen says so instead of offering a fake Save.
- Connection ids are free text. There is no bridge connection list API to drive a picker.
- The entity is fixed to `orders`, matching the seeded backend payload. Multi-entity contracts need an API and spec decision.
- The `⌘↵` hint shows ⌘ on non-Mac pointers too, though Ctrl+Enter works there.
- The Next dev indicator ("N" badge) shows in dev captures only.
- `stepStates` / `STEPS` stay in the lib (tested) but the redesigned screen no longer renders a rail.
- Running `next dev` with `INGENIUM_DIST_DIR` adds a `.next-uisNN/types` include to `apps/web/tsconfig.json`. Peers' entries (uis35 to uis50) are already there. I removed my `.next-uis52` line after stopping the server.

## Not touched

`odoo_addons/`, live-demo-copilot, plan inbox, fleet, journal, config, cron, other operate screens, shared `components/ui/*` (only consumed Button, Tabs, icons), `e2e/a11y-primary.spec.ts`, API code, and git state (no commit, stash, checkout, push, or clean). No DONE. The isolated Next on `:3052` was stopped after tests and capture.
