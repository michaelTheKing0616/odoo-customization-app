# BOT-PROCESS-DESIGN — Odoo-native design of a multi-step business process

Status: built (uncommitted, awaiting review/merge)

## Scope
Any client process in any Odoo area. Input: business description (structured steps) plus the
optional BOT-FITGAP result. Output: a design spec for BOT-CONFIG-VERIFY
(`items`: kind, model, key, expected, relations, verdict, reason, risk, ref) and a plan whose
every step routes through the Bots write spine (`requires_approval: true`). Never writes to Odoo.

- Manufacturing-type steps (inputs/outputs/work center/checks): `mrp` module, work centers
  (shared utilities summed into `costs_hour`), BoMs, BoM lines (shared inputs, multi-level),
  operations, by-products and co-products (`cost_share`), recirculation (by-product consumed
  upstream), quality points (pass/fail, measure with tolerances).
- Other areas: data-driven `templates.json` keyed by BOT-FITGAP concept id (stages, pipelines,
  approvals, journals, taxes, price lists, groups, routes, picking types...), plus per-step
  `approval` (approval.category) and `automation` (base.automation).
- Grounding: `read_inventory` (installed modules + `fields_get`, read-only). Verdict per item:
  `stock` | `stock-install` | `needs-custom` (exact missing fields) | `needs review`.
- Risk: existing `risk.classifier.task_floor` per item (`m:<model>:create`, `mod:`, `s:`).
- Fail closed: unknown model/field, unmapped step, bad numbers, main-product BoM cycle -> review
  list / blocked plan step; no steps -> `not enough input`; no inventory -> all `needs review`.

## Files
- apps/api/app/bots/process_design/{__init__.py,design.py,templates.json}
- apps/api/tests/test_nf_bot_process_design.py
- apps/api/tests/fixtures/process_design/generic_pack.json (fit-gap mapping + test pack)
- apps/api/tests/fixtures/process_design/industry_optional.json (optional industry data only)

## Review follow-ups
- R1 (BLOCK) fixed: step-coverage invariant; shared-ref conflicts -> review; quality points keyed title+product; all numbers validated (finite/range); iterative cycle check; Enterprise-only reasons; journal short codes, putaway link as relation, `needs` lists for thin templates; fit-gap concept status respected; unclassified risk blocks plan.
- Low: false conflict when two operations of the same BoM both use a shared component. Safe (goes to review), but Odoo allows separate lines.
- Low: trim bad values in review text (`repr()[:40]`).
- No live check yet: the inventory reader is tested with a fake only.
- Locations and operation types come only from fit-gap concepts.
