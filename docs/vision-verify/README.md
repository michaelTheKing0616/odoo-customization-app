# Vision-verify screenshots

Date: **2026-08-03** (REM-12 sweep)

## Harness & shell

| File | Theme | Source |
|------|-------|--------|
| `tokens-light.png` / `tokens-dark.png` | light/dark | `/e2e/tokens` — neutrals, 5-step semantic ramps, typography |
| `kit-light.png` / `kit-dark.png` | light/dark | `/e2e/kit` — component kit showcase |
| `shell-overview-light.png` / `shell-overview-dark.png` | light/dark | `/connections/demo-conn` — AppShell + overview (mocked API) |

## Primary pages (UIX-4c operate/govern)

| File | Page |
|------|------|
| `journal-{light,dark}.png` | Snapshots & Journal |
| `bulk-suite-{light,dark}.png` | Bulk Suite |
| `reminders-{light,dark}.png` | Reminders |
| `id-generator-{light,dark}.png` | ID Generator |
| `reports-{light,dark}.png` | Reports |
| `housekeeping-{light,dark}.png` | Housekeeping |
| `approvals-{light,dark}.png` | Approvals |
| `import-{light,dark}.png` | Import |

## Designer & overlay (prior passes)

| File | Notes |
|------|-------|
| `designer-form.png` | View designer form mode |
| `designer-list.png` | List mode |
| `designer-kanban.png` | Kanban mode |
| `overlay-editor.png` | REM-6 overlay harness |

## Re-capture

```bash
cd apps/web
pnpm exec playwright install chromium   # once
pnpm exec playwright test e2e/vision-verify-sweep.spec.ts e2e/designer-vision.spec.ts e2e/overlay-editor.spec.ts
pnpm exec playwright test e2e/a11y-primary.spec.ts
```

Requires `NEXT_PUBLIC_E2E=1` (set in `playwright.config.ts` webServer env).

Audit tables: `docs/UIX_AUDIT.md`.
