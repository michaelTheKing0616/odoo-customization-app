# Web e2e

Harness pages (gated by `NEXT_PUBLIC_E2E=1`):

- `/e2e/confirm` — ConfirmDialog phrase gating
- `/e2e/automation-caps` — mock Odoo 16 greys out update_path action kinds
- `/e2e/designer?mode=form|list|kanban` — Designer chrome + sample fields (vision-verify)

```bash
pnpm --filter @odoo-custom/web exec playwright install chromium
pnpm --filter @odoo-custom/web test:e2e
```

Uses `next build && next start` (not `next dev`) to avoid file-watcher EMFILE issues.
