# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of this session.

## Last run
- Date: 2026-09-14
- **Shipped:** Expert no longer treats `xmlrpc.py` as a missing model. Sandbox ParseError `//field[@name='amount_tax']` is xpath-miss on `sale.order`; zip rewrite → `tax_totals`. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
- **Proof:** `test_sandbox_amount_tax_xpath_not_xmlrpc_model`, `test_extract_skips_xmlrpc_py_traceback`, `test_rewrite_sale_order_amount_tax_xpath`

## Next (operator)
1. Kill/restart `:8001` without `--reload`. Hard-refresh App Studio.
2. Retry **Sandbox Install and smoke** (zip rewrite, no re-author required). Do **not** Install this app.
3. Gate pass → human Promote.

## Docket (later — do not start)
- **PROD-FAULT-LOG:** Production log of **in-app** faults with a founder dashboard/export. **Blocked on** honest diagnosis. See `docs/PRODUCTION-PLAN.md` § Docket.
