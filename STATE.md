# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-16
- **Shipped:** OWL guard — view↔Python field consistency
  (`ai_option_a_view_fields.py`): authoring + structural zip fail on
  undefined/non-`x_*` arch fields; free align; sandbox `fields_get` smoke.
- **Root cause of Quotation crash:** installed arch refs `markup_percentage`
  etc. while registry has no markup fields (`fields_get` empty).

## Next (operator)
1. Restart `:8001` without `--reload` so gates load.
2. On `odoo_ngn`: **uninstall** the broken markup module (Apps → uninstall),
   then App Studio → Repair / re-author → Sandbox smoke → **Promote** again.
3. Open Quotation via `/odoo/action-…` — form must load without OwlError.
4. Promote stays human.

## Docket
- Designer extract; live-demo branch merge hygiene
