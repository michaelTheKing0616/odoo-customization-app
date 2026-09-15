# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-15
- **Shipped:** Studio-like View Designer (`cursor/studio-view-designer-3f46` off `premium-local-tip`)
  - Shell: session bar + compact toolbar, live iframe / Odoo-widget canvas, right tools rail
  - HTML5 DnD (`lib/designer-dnd.ts`) + `DragAutoScroll`; inherit save / confirms / snapshots stay
  - Overlay in rail; xpath in Advanced tab; field-inject dump behind extras disclosure
  - Harness `/e2e/designer` + `/e2e/designer-premium`; spec `e2e/designer-premium.spec.ts`
- **Tests:** Vitest designer/odoo-preview/dnd 40 passed; `check-legacy-colors` passed
- **Failed:** Playwright not yet run (needs `NEXT_PUBLIC_E2E=1` next build)

## Next
- Playwright: `designer-premium` / keyboard / studio-preview / cmp3 / designer-vision
- Live: `http://127.0.0.1:3002/connections/{id}/designer` — drag field, edit props, save inherit

## Rule
- Designer hero canvas is live Odoo or `odoo-preview` widgets — never dashed wireframe boxes
