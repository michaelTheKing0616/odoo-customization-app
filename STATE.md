# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** Premium Job Autopilot UX (surface 5) on `cursor/premium-job-autopilot-fc2c` off Draft Studio:
  - Stage rail: brief → run → scorecard → promote
  - Extracted chrome in `apps/web/src/components/job-autopilot/` + `job-autopilot-journey.ts`
  - Production refuse is header + danger gate + disabled Run; sandbox-only honesty kept
  - PR: https://github.com/michaelTheKing0616/odoo-customization-app/pull/9
- **Tests:** 23 vitest (journey + shell/rail/banners/scorecard/brief/handoff) green
- **Failed:** none. Video OCR hallucinated typos that are not in source.

## Next
- Continue premium sweep only if asked (do not start ModuleSpec / Projects / Expert here)
- Live Autopilot run still needs a real sandbox + API, not the mock used for chrome verify

## Rule
- Job Autopilot premium is a four-stage operator shell. Never fuse Completeness / Cert / Autopilot, and never auto-promote.
