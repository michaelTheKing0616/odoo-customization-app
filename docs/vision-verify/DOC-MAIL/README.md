# DOC-MAIL vision shots

Harness: `/e2e/mail-templates` with `NEXT_PUBLIC_E2E=1`.

Captured 2026-10-05 (Lagos):
- `desktop.png` — workbench list + paper letter
- `empty.png` — empty templates list
- `preview.png` — paper-only preview shot

```bash
cd apps/web
NEXT_PUBLIC_E2E=1 pnpm exec next dev -H 127.0.0.1 -p 3010
# other terminal:
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3010 pnpm exec playwright test e2e/doc-mail-vision.spec.ts
```
