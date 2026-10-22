# UI-S-22 Job Autopilot — vision notes

Pressure 9. Primary CTA: **Run Autopilot** (teal) on brief; demoted to secondary when promote-ready so **Promote/Handoff** is the sole teal primary.

## Design Read
Operate-mode sandbox job runner. Basalt chrome, one teal accent, Completeness ≠ Cert ≠ Autopilot honesty, no live Python install on Odoo Online.

## States captured
| State | What to verify |
|-------|----------------|
| brief / empty | One teal Run Autopilot; Plan secondary; what/why/next empty guide |
| scorecard | Recipe rail order; score meters; smoke strip; promote primary |
| progress | Honesty line; run ledger; no Completeness conflation |
| production | Refuse gate; error what/why/next; Run disabled |
| online | Online honesty banner; no live Python install claim |

## Capture
```bash
cd apps/web
# with NEXT_PUBLIC_E2E=1 webServer (playwright.config) or:
NEXT_PUBLIC_E2E=1 pnpm exec next start -p 3002
NODE_PATH=apps/web/node_modules node docs/vision-verify/UI-S-22/capture.cjs \
  http://127.0.0.1:3002 docs/vision-verify/UI-S-22 after
```

## Must not
- Em dashes in UI copy
- Orange primary CTAs / Odoo purple
- Imply Completeness 10.0 = go-live or Autopilot
- Imply live Python install on Odoo Online
- Promote without confirm dialog
