# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-14
- **Shipped:** World-class UAT report on tip `cursor/premium-odoo-expert-ux-77b3` @ `efda9a9`
  - `docs/UAT-PREMIUM-WORLD-CLASS.md` — chain average **3.3/5**, Expert ~4.1, Designer ~2.4
  - Chrome harnesses: `/e2e/designer-premium`, automations, builder, menus, access, studio, draft-studio, job
  - P0 polish: Designer inject/checkpoint contrast; gate ModuleSpec/Projects e2e
- **Failed:** No live Odoo/API — chrome UAT only, not RPC UAT. Screenshots from `/e2e/*`.
- **Rule:** `/e2e/*` must gate `NEXT_PUBLIC_E2E=1`. Designer production dump ≠ extracted A–D widgets. Access live pack is unconfirmed.

## Next
- Founder live UAT on `:8069` (skip Access “Apply live pack”). Confirm-gate Access. Extract Designer page. Pick one AI studio CTA.

## Rule
- Opening balances never auto-post; inventory via dedicated stock.quant path only
- Vision default-off in `.env.example`; local unlock ≠ EU commercial clearance
