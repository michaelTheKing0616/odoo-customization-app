# STATE.md — Current Run / Loop State

> Read at the start of every session. Updated at the end of every session.

## Last run
- Date: 2026-09-15
- **Shipped:** Sales markup sandbox Fault root cause — authored `@depends(..., 'tax_id')` on `sale.order.line`.
  - Deterministic rewrite `tax_id` → `tax_ids` (strings + `.tax_id` attrs)
  - Failure IR parses Wrong @depends; author/repair prompts updated
- **Proof:** `test_rewrite_sale_order_line_tax_id_depends`, `test_wrong_depends_tax_id_failure_ir`

## Next (operator)
1. Kill/restart `:8001` without `--reload`. Hard-refresh App Studio.
2. **Repair with AI** (or Sandbox again) — free rewrite should fix tax_id before LLM budget.
3. Do **not** Install this app. Gate pass → human Promote.

## Docket
- Designer extract; live-demo branch merge hygiene
