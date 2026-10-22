# UI-S-51 · Fleet command look-and-feel (vision notes)

Card: UI-S-51 `/command`. Pressure 8. Primary: **Open a client** (teal); empty uses **Connect Odoo**.
Status: **visual leap** (command-center paper desk) implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded:
- DESIGN_SYSTEM_PLAYBOOK + ingenium-v2 + Studio refs UI-S-20 / UI-S-12
- Design research thesis (paper-as-object / basalt + teal)
- Taste: impeccable / design-taste-frontend / no-ai-slop

## Design Read

Operate-mode fleet command center. Limestone pasteboard + paper sheet. Basalt type. One teal primary in the masthead. Stage rail is a quiet segmented track. Honesty is an uppercase caption (not amber Callout). Situational callouts only for empty / loading / partial / error. Tiles are a 2×2 command grid with large tabular counts, status chips, and accent spine when hot.

## Before → after craft leaps

| Before (banner-stack pass) | After (visual leap) |
|---|---|
| Amber honesty + teal idle Callouts stacked | Quiet caption + masthead orientation; no twin Callouts on idle |
| Four plain number cards under banners | 2×2 command tiles with chips (Connected / Waiting / Needs care / Clear), large counts, hot spine |
| CTA buried in teal Callout | Masthead **Open a client** / **Connect Odoo** |
| Sparse white settings page | Paper desk command center |

## States captured

| State | Harness | Verify |
|---|---|---|
| empty | Connect Odoo; empty callout; Fleet step |
| idle | Masthead CTA; caption honesty; 3/2/1/0 tiles; Inspect step |
| loading | Loading callout; skeletons |
| partial | Partial callout; Failed jobs error; siblings stay |
| error | Danger callout; tiles hidden; CTA escape |

Canonical: `desktop.png` = after-idle-desktop; `narrow.png` = after-partial-narrow. All overflowX=0.

## Tests

- Vitest: fleet lib + FleetStateGuide + FleetStageRail → passed
- Playwright against `:3002`: `e2e/command.spec.ts` → **4 passed**

## Known gaps

- Live `/command` still hits real tile APIs; harness freezes phases for vision.
- Failed-jobs / drift hrefs still land on `/connect` (seeded).
- Dark mode paper desk not vision-captured in this pass.

## Not touched

`odoo_addons/`, plan-inbox, bots, billing, auth, git. No DONE. Isolated `:3075` / `.next-uis2951` stopped after work.
