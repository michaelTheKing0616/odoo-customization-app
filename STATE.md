# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-16
- **Shipped:** Option A acceptance smoke + self-heal
  (`ai_option_a_acceptance.py`): contracts stamped at author;
  labels / tax_totals placement / price_effect checked in sandbox RPC;
  smoke fail → Failure IR → one auto-repair → re-install.
  Free harden: `string=` on x_*, note→tax_totals xpath.

## Next (operator)
1. Restart `:8001` without `--reload`.
2. New Sales markup app → Sandbox install & smoke must pass acceptance
   (labels + price change) before Promote unlocks.
3. Uninstall any prior broken markup module on `odoo_ngn` first.
4. Promote stays human.

## Docket
- Designer extract; live-demo branch merge hygiene
