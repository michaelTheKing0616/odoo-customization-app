# BOT-VARIANCE-CONTROL — actual vs expected for any process, policy-driven

Status: built (uncommitted, awaiting review/merge)

## Scope
Any process in any Odoo area. Read-only: compares ACTUAL (live `fields_get` + `search_read`)
with EXPECTED and flags deviations beyond tolerance. Follow-ups are plan steps only
(`needs_approval: true`, level L2/L3 from `risk.classifier.task_floor`, route
`bots-write-spine`, `writes: 0`). Never writes to Odoo.

- Metric catalogue `metrics.json` (data, not code): model, domain, actual field (sum/avg,
  date-diff `days_from`, `ratio_filter`), expected source (record field | caller standard |
  BOT-PROCESS-DESIGN spec item by kind/ref), unit/uom/currency fields, group_by, date_field,
  direction (both/over/under), default tolerance, follow-ups. Shipped: component consumption,
  production output, work-order duration, standard cost, purchase price,
  sale price, stock count, bill vs received qty, lead time.
- Tolerance: abs and/or pct, asymmetric `over`/`under`, `breach_factor` (default 2: within <= tol,
  warn <= 2x, breach beyond). Missing/invalid tolerance -> `warn` + `review_needed`.
- Statuses: within / warn / breach / cannot-measure / no-data.
- Aggregation: company always in group key; per record (`id`), product, work center, partner
  (caller override); period day/month/year with rolling window; recirculated record ids
  excluded and reported; by-product share; `split_shared` for shared-input allocation.
- Output: rows (expected, actual, delta, delta_pct, status, reason, evidence ids capped at 50 +
  count), summary counts, truncated metrics, `ok` only when every row is within and nothing
  truncated; stable ordering.

## Fail closed
Missing model/field -> cannot-measure; read error/odd result -> cannot-measure; no records ->
no-data; NaN/inf/huge/bool/string -> cannot-measure; zero expected -> pct undefined, abs only,
non-zero delta with pct-only tolerance -> breach; mixed or unknown units -> normalise via
`uom.uom` factor (same category) else "unit mismatch"; mixed currency or standard without
currency on monetary metrics -> "currency mismatch"; truncated read downgrades within -> warn;
ambiguous/unsupported design spec -> cannot-measure; unclassifiable follow-up -> L3.

## Review round 1 fixes
- UoM shape probed via `uom.uom` fields_get: 17/18 `category_id` (q/factor), 19+ `relative_uom_id`
  chain + absolute `factor` (root = chain top); unknown shape/cycle -> unit mismatch. Unit field
  resolved from candidates (`product_uom`/`product_uom_id`/`uom_id`); none -> cannot-measure.
- Prices (`uom_kind: per_unit`) normalised per root unit; mixed units need a standard unit.
- by_product_share dropped (qty share is not cost share); ratio + design sources stay generic.
- standard_cost read per company with company context; company currency must match standard.
- Favourable deviation: within only inside tolerance, else warn (never breach, never silent).
- Rolling status counts in summary/ok/plan; undated records -> cannot-measure row; split_shared
  rejects negative total and weights <= 0; caller domain fields checked against fields_get;
  limit (1..20000), period, rolling validated.
- Live read-only test (ODOO_LIVE=1, nf sandboxes 17/20): `test_nf_bot_variance_live.py`.

## Files
- apps/api/app/bots/variance/{__init__.py,variance.py,metrics.json}
- apps/api/tests/test_nf_bot_variance.py (fake Odoo, both UoM shapes, asserts no writes)
- apps/api/tests/test_nf_bot_variance_live.py (gated, read-only)

## Review follow-ups
- A caller standard without a unit is assumed to be in the single record unit; document this or require the unit.
- The price average is per line, not quantity-weighted.
- The force_company context is ignored on Odoo 17+.
- Odoo 18/19 not run live (the 19 UoM shape is assumed from 20).
- The live DBs had only stock, so the price, mrp and purchase metrics are tested with a fake only.
- The version-capability check (BOT-VERSION-CAPS) is to be wired in.
- by_product_share was removed pending a correct definition.
