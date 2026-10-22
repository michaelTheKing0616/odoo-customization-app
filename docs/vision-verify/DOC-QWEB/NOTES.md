# DOC-QWEB · vision notes

Harness: `/e2e/qweb-views` with `NEXT_PUBLIC_E2E=1`.

Captured 2026-10-05 (Lagos):
- `desktop.png` — list + paper preview with grounded blocks
- `empty.png` — empty desk empty-state
- `source.png` — Source XML tab
- `error.png` — UI-S-14 what / why / next gate refusal

Teal-only accent; cream paper on gray pasteboard — same family as Reports / Mail / UI-S-12 Designer desk. Do not revert teal to purple.

```bash
cd apps/web
NEXT_PUBLIC_E2E=1 pnpm exec next dev --turbopack -H 127.0.0.1 -p 3012
# other terminal (temp config skips webServer / production build):
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3012 pnpm exec playwright test e2e/doc-qweb-vision.spec.ts --config=playwright.doc-qweb.config.ts
```
