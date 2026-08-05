# Web e2e

Harness pages (gated by `NEXT_PUBLIC_E2E=1`):

- `/e2e/confirm` — ConfirmDialog phrase gating
- `/e2e/automation-caps` — mock Odoo 16 greys out update_path action kinds
- `/e2e/designer?mode=form|list|kanban` — Designer chrome + sample fields (vision-verify)

```bash
pnpm --filter @odoo-custom/web exec playwright install chromium
pnpm --filter @odoo-custom/web test:e2e
```

Uses `PLAYWRIGHT_E2E_BUILD=1 next build && next start` on **port 3010** (not `next dev`) to avoid
file-watcher EMFILE issues and clashes with Docker/dev on 3000/3002. Override with `PLAYWRIGHT_BASE_URL`.

E2E builds omit `output: standalone` and write to `.next-e2e/` so they do not clobber the dev
`.next/` cache. Production/Docker builds keep standalone in `.next/`.

If the webServer times out, ensure nothing else owns the port (`lsof -i :3010`) or set `CI=1` to force a
fresh build instead of reusing an existing server.
