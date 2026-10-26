# BOT-CONFIG-VERIFY: read-only check of a configured database against a design

Status: built, awaiting review. Code: `apps/api/app/bots/configverify.py`.

## What it does
`verify(spec, call, companies=...)` takes a BOT-PROCESS-DESIGN spec (`spec_version: 1`, `items[]`)
and reports, per item, one of: **matches / missing / differs / cannot-read / not designed**, with
expected vs found values, summary counts, groups, company shown, `truncated`, `company_view`.

## Rules (fail closed)
- Read-only: the caller is wrapped; only `fields_get, search_read, search_count, read,
  default_get` reach Odoo, anything else raises `ReadOnlyViolation`. No write method names in source.
- Access error, missing model/field, read limit, partial company view => `cannot-read`, never `matches`.
- Design verdict `needs-custom` / `needs review`, invalid items (types, NaN/inf, huge values),
  duplicate refs => `not designed`. Empty/invalid spec => `not enough input`. No crash on bad input.
- Field existence from live `fields_get`; many2one/x2many compared by resolved ids
  (display_name ilike + exact, leaf-name fallback for `a / b` hierarchical names), not text.
- Floats compared to the field's digits (half a unit), else 1e-6.
- Archived (`active=False`) or more than one record per key => `differs`.
- Links: `relations` values that are refs of other items (or lists of refs) are checked after
  all items; a match whose target is not a match, absent from the design, or not pointed to
  becomes `differs` with the link named. Repeated to a fixed point (cycle-safe).
- Multi-company: reads with `allowed_company_ids`; if the bot sees fewer companies than exist,
  company-scoped records are `cannot-read` (never matches or missing from a partial view).
- Limits: max 2000 items (rest `cannot-read`, `truncated: true`); name lookups >=200 hits => cannot-read.

## Tests
`tests/test_nf_bot_configverify.py` (fake Odoo, every fail-closed path), live
`tests/test_nf_bot_configverify_live.py` (ODOO_LIVE=1, Odoo 17 + 20).

## Known limits
- Names resolve to exactly one record (archived included) by display_name / name /
  default_code, or via the record's product (BoMs); more than one => `cannot-read`
  (ambiguous), archived target => `differs`. A name Odoo knows under none of those reads `missing`.
- `group` relations are not checked. Settings read via `default_get` (what the Settings page shows).
- Partial company view is detected by count only (bot's allowed list vs all companies).

## Review follow-ups
- R1 (BLOCK) fixed: ambiguous/archived name targets never match; settings on a partial company
  view => cannot-read; products/BoMs resolved by name/code/product; real process-design output
  test; tests pinning the 200-hit cap and the multi-pass link fixpoint (mutants killed);
  `missing` reason notes access rules may hide records.
- Checks only the live database today. The version-capability layer (BOT-VERSION-CAPS: "available in this version, needs install" for uninstalled modules) is queued and must be wired in.
- A key must match display_name, name or default_code exactly; a case or whitespace difference reports missing.
- Group relations are not checked.
- The live test covers contacts and tags only; manufacturing items are tested with a fake only.
