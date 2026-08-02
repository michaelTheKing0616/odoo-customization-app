# Vision-verify — Designer screenshots

Date: **2026-07-28**

Captured via Playwright e2e harness (`NEXT_PUBLIC_E2E=1`) at `/e2e/designer?mode=…`,
using real Designer chrome components (`FormCanvas`, `KanbanCardPreview`, `FieldPalette`,
`PropsInspector`) with mock Odoo 19 connection + sample `x_ticket` fields.

| Path | Mode | What it shows |
|------|------|----------------|
| `docs/vision-verify/designer-form.png` | form | View designer shell; field palette; Odoo-style form canvas (statusbar, header/smart buttons, groups with reorder ↑↓, chatter); field props inspector |
| `docs/vision-verify/designer-list.png` | list | View designer shell; field palette; list columns canvas (decoration-danger/info/muted, table preview, reorderable column list); column props inspector |
| `docs/vision-verify/designer-kanban.png` | kanban | View designer shell; group-by `x_stage`; kanban card preview with multi-column group-by chrome, card field reorder ↑↓ + remove, props Move up/down |

## How to re-capture

```bash
cd apps/web
pnpm exec playwright install chromium   # once
pnpm exec playwright test e2e/designer-vision.spec.ts
```

Screenshots write to this directory (`designer-*.png`).
