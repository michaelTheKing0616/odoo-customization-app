# UI-S-31 · Power Ops look-and-feel (vision notes)

Card: UI-S-31 `…/power-ops` (~409). Pressure 8. Primary: **Run recipe** (teal).
Status: elite UI pass implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded before the UI edits:
- `~/Desktop/prime-skills-pack/docs/DESIGN_SYSTEM_PLAYBOOK.md`
- `~/Desktop/ingenium-v2/final/BRAND_GUIDE.md`
- Global rules + UI-S-31 block in `docs/plans/next-phase/13_UI_SCREEN_SPECS.md`
- Studio-cluster peers: UI-S-26 import, UI-S-28 ingest, UI-S-30 bulk-suite craft (read only; those trees not edited)

## Design Read

Operate-mode multi-step bulk RPC recipes. Basalt chrome, one teal **Run recipe** primary (unlocked after dry-run), amber only for honesty / dry-run caution, danger reserved for danger-zone recipes and the phrase confirm. What/why/next on empty, idle, blocked, partial, and error. Honesty for destructive ops: dry-run never writes; successful steps are not auto-undone; risk phrase stays. No purple, no orange primary CTAs, no em dashes, cinnabar never in UI.

## What the pass delivers

| Thesis item | Where |
|---|---|
| Run recipe is the sole teal primary | `power-ops-run-btn` uses `variant="primary"`; Dry-run stays secondary |
| Dry-run gate before live run | Execute unlocks only when `dryRunKey === runKey`; unlock reason copy visible |
| Destructive honesty | Always-on `power-ops-honesty`; danger-zone band; ConfirmDialogV2 phrase + blast radius |
| Result honesty | Labels "Dry-run result (no writes)" vs "Run result (writes applied)"; count tiles |
| Stage rail | `PowerOpsStageRail` Recipe → Configure → Dry-run → Run |
| What/why/next | Empty, idle, blocked, partial, error via `PowerOpsStateGuide` / `PowerOpsErrorNotice` |
| Basalt / teal chrome | `.power-ops-operate` scoped CSS (4pt rhythm, reduced-motion) |

## States captured (`after-*` via `capture.cjs`)

| State | Harness | Verify |
|---|---|---|
| empty | `?state=empty` | Empty what/why/next; Re-probe; Recipe step current |
| idle | `?state=idle` | Honesty + idle guides; Run locked; Configure step |
| blocked | `?state=blocked` | Blocked what/why/next; major gate copy |
| dry-run | `?state=dry-run` | Counts dry-run; no-writes label; Run unlocked; Dry-run step |
| danger | `?state=danger` | Danger zone selected; Run still locked until dry-run |
| executed | `?state=executed` | Writes-applied label; partial guide; Run step |
| error | `?state=error` | Error notice what/why/next |

Every after shot measured `overflowX=0` at 1440×900 and 390×844 (reduced motion).
Canonical: `desktop.png` = after-idle-desktop; `narrow.png` = after-dry-run-narrow.

Regenerate:

```
cd apps/web
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-31/capture.cjs \
  http://127.0.0.1:3002 ../../docs/vision-verify/UI-S-31 after
```

## Tests

- Vitest: `pnpm exec vitest run src/lib/powerOpsScreen.test.ts src/components/power-ops` → **5 files, 10 passed**
- Playwright (against existing `:3002`, no isolated mirror): `e2e/power-ops.spec.ts` → **7 passed** (honesty; empty; dry-run unlock; executed writes label; blocked; error; no em dashes)
- Typecheck: no new power-ops page/component TS errors introduced in this pass

## UX audit (12 rows)

| Area | Result | Note |
|---|---|---|
| Hierarchy | Pass | One teal primary (Run recipe); Dry-run secondary; honesty above recipes |
| IA | Pass | Stage rail mirrors Recipe → Configure → Dry-run → Run |
| Interaction | Pass | Run disabled until dry-run key matches; danger keeps phrase confirm |
| Feedback | Pass | Count tiles + dry-run / writes-applied labels; busy progress strip |
| Errors | Pass | what/why/next on load/probe/dry-run/run/domain/blocked |
| Accessibility | Pass | Stage rail states; labeled Model/Domain; focus rings on recipe cards |
| Cognitive load | Pass | Safe recipes first; danger band separated; no nested card soup |
| Trust | Pass | Honesty banner; dry-run never claims writes; risks listed before confirm |
| Motion | Pass | Color transitions only; capture used reduced motion |
| Copy | Pass | Sentence case; verb buttons; no em dashes / Oops / AI magic |
| Density | Pass | 4/8 spacing; mono model/domain; tabular counts |
| Responsive | Pass | Narrow shots overflowX=0; recipe grid stacks |

## Vision verify notes (eyes on shots)

- Idle/danger: Basalt chrome, teal Run recipe (disabled until dry-run), amber honesty band (caution role, not a primary CTA), red danger band for destructive recipes only.
- Dry-run: "Dry-run result (no writes)" + Would process/succeed/fail tiles; Run recipe enabled teal.
- Empty: what/why/next + Re-probe.
- Executed narrow: writes-applied label + partial failure guide; no horizontal overflow.

## Known gaps (follow-ups)

- Live route still loads recipes over the network; harness does not mock VersionAwareness / capability probe / FirstWrite interstitial chrome.
- Philosophy Callout still surfaces API `caps.philosophy` when present (sanitized); not re-authored.
- `≥` glyph remains on Odoo major badges (not an em dash); ASCII `>=` used inside blocked why copy.
- Confirm dialog overlay not captured as its own vision state (existing ConfirmDialogV2; phrase contract unchanged).
- AppShell sidebar still open at 390px on the live shell (global); harness captures page body with overflowX=0.

## Not touched

`odoo_addons/`, code-studio, expert, bulk-suite, ingest, import, menus, approvals, wizard, access, automations, job, designer, website, mail, qweb, studio, git state (no commit / stash / checkout / push / clean). No DONE. No isolated next/dev mirror left running for this card (tests/capture used existing `:3002`).
