# DOC-WEBSITE vision shots

Harness: `/e2e/website` with `NEXT_PUBLIC_E2E=1`.

Captured 2026-10-05 (Lagos):
- `desktop.png` — workbench page list + paper preview
- `empty.png` — empty pages list
- `locked.png` — paper-only locked snippet state
- `error.png` — what / why / next unsafe-gate refusal

```bash
cd apps/web
NEXT_PUBLIC_E2E=1 pnpm exec next dev -H 127.0.0.1 -p 3011
# other terminal:
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3011 pnpm exec playwright test e2e/doc-website-vision.spec.ts
```
