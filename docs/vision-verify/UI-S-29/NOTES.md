# UI-S-29 · Operations hub look-and-feel (vision notes)

Card: UI-S-29 `…/operations` (100). Pressure 3. Primary: **Open Bulk Suite** (teal) in the masthead.
Status: **visual leap** (paper-desk craft) implemented and verified locally. **Not marked DONE.** Nothing committed.

Sources loaded:
- `/home/box/design-repo/skills/DESIGN_SYSTEM_PLAYBOOK.md`
- Brand `/home/box/design-repo/brand/ingenium-v2/`
- Studio refs: `docs/vision-verify/UI-S-20/`, `UI-S-12/after-premium-desktop.png`
- Design research: `/workspace/design-research/ingenium-canvas-2026-10-05/`
- Taste: impeccable / design-taste-frontend / no-ai-slop

## Design Read

Operate-mode tool desk. Limestone pasteboard + paper sheet. Basalt type. One teal **Open Bulk Suite** in the masthead. Orientation is inline typography (not a twin Callout). Honesty is a quiet dashed caption beside write tools (risk imminent when choosing a write path), not an always-on amber banner. Featured Bulk Suite card spans the write row. No purple, no orange CTAs, no em dashes, no eyebrows, cinnabar never on buttons.

## Before → after craft leaps

| Before (banner-stack pass) | After (visual leap) |
|---|---|
| Amber honesty Callout + teal pick Callout stacked under header | No twin Callouts on idle. Pick copy is masthead lead. Honesty is a quiet caption under tools |
| One teal button trapped inside the teal Callout | Masthead primary CTA; tool cards stay quiet Open links |
| Sparse equal cards on flat white | Paper sheet on limestone pasteboard; denser group rhythm; featured Bulk Suite hairline + icon |
| Template SaaS settings feel | Desk / paper-as-object; section labels + blurbs as type, not banners |

## States captured

| State | Harness | Verify |
|---|---|---|
| idle | `?state=idle` | Masthead CTA; inline pick lead; caption honesty; featured Bulk Suite; overflowX=0 |

Canonical: `desktop.png` = after-idle-desktop; `narrow.png` = after-idle-narrow.

```bash
cd apps/web
NODE_PATH=$PWD/node_modules node ../../docs/vision-verify/UI-S-29/capture.cjs \
  http://127.0.0.1:3002 ../../docs/vision-verify/UI-S-29 after
```

## Tests

- Vitest: `operationsHubScreen` + `components/operations` → passed
- Playwright (`PLAYWRIGHT_BASE_URL=http://127.0.0.1:3002`): `e2e/operations.spec.ts` → **3 passed**

## Known gaps

- Hub still has a single harness state (`idle`).
- AppShell / floating chrome at 390px is global.
- Paper craft is light-mode strongest; dark pasteboard tokens exist but not vision-captured.
- Icon set still Lucide-era product icons (taste prefers Phosphor); left as-was to avoid a second icon migration in this pass.

## Not touched

`odoo_addons/`, plan-inbox, bots, billing, auth, git (no commit/stash/checkout/push/clean). No DONE.
