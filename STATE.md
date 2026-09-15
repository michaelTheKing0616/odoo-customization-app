# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-15
- **Shipped:** Studio-like View Designer — PR #15 (`cursor/studio-view-designer-3f46` → `premium-local-tip`)
  - Center live iframe / Odoo-widget FormCanvas; right Fields/Properties/Structure/Overlay/Advanced rail
  - HTML5 DnD (`lib/designer-dnd.ts`); inherit save / confirms / snapshots / human Promote unchanged
  - Proof: `docs/vision-verify/designer-studio-shell.png`, `designer-premium-studio.png`
- **Tests:** Vitest designer 40 passed; Playwright designer-premium/keyboard/studio-preview/cmp3/vision 12 passed
- **Failed:** none this pass (Playwright needed `playwright install chromium` once)

## Next
- Live UAT: `http://127.0.0.1:3002/connections/{id}/designer` — load model, drag field, edit props, save inherit
- Optional: extract remaining save/state hook out of the ~5.9k Designer page

## Rule
- Designer hero canvas is live Odoo or `odoo-preview` widgets — never dashed wireframe boxes
