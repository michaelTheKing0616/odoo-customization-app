# Skill: Odoo 19 RPC Gate

## When to use
Any task that creates or changes Odoo RPC helpers, metadata writes (`ir.model`,
`ir.model.fields`, `ir.ui.view`, `base.automation`, access rules), or generated modules.

## Why
Models confidently invent Odoo API shapes. A unit mock green ≠ works on Community 19.
This gate is the mechanical fail (RULES.md Rule 4) for Odoo-facing work.

## Done means (all required)
1. Local Docker stack is up: `odoo:19` + Postgres, reachable on the expected port.
2. Scripted proof ran against that instance (not mocked): connect → authenticate → exercise
   the new/changed call → assert response shape.
3. Output captured (exit code 0 + short log path or inline result) for the judge/checker.
4. For destructive ops: snapshot/backup step ran first, or the call was limited to a
   throwaway DB named for testing.

## Card fragment (paste into worker cards)
```
DONE MEANS: pytest/script against local odoo:19 returns exit 0 for the new RPC path;
  paste the command and last 20 lines of output in RETURN.
DO NOT: mark done based on mocks alone; do not write to any non-sandbox Odoo URL.
```

## Checker notes
- Cheap tier can grade "did the smoke script exit 0?"
- High tier checker for: security of generated automations, correctness of view XML vs
  golden examples, whether a field delete is safely gated.

## ModuleSpec first-try apply
A finished draft must satisfy `ai_live_apply_contract` (`_live_apply.ready`). When live
UI apply skips or Faults a row, add the **stamp and the scorecard finding together** —
do not patch apply only. Python/tests/i18n stay Option A (module → sandbox → promote).
Known live Faults to stamp: monetary `currency_field` before the currency M2O exists;
O2M before its inverse M2O; O2M onto stock (`hr.employee`) which cannot grow `x_*`
inverses; related fields (including related `x_currency_id`) before their hop M2O;
`mail_post` / Python-shaped `object_write` (not live metadata); search `group_by`
or filter `domain` on a missing field (including leftover `x_status` after a
register demote). Apply may also rank/skip those rows, but generation must not ship them.
Live Generate UI must apply `spec.menus` (grouped Operations / Inventory / People)
and hide `*_line` menus — flattening every `x_*` model as a root child is not a
domain flow. Return `root_menu_id` so the operator can Open app in Odoo.
Walkthrough seed writes data rows — confirm phrase required; unit-test with a
fake client (do not mark done on mocks of the RPC shape alone if the create
vals omit required FKs).

## Job Autopilot
Sandbox Autopilot is done when **RPC process smoke** passes: partner → product →
quotation **with a line** → `sale.order.action_confirm` → public
`sale.advance.payment.inv.create_invoices` (never private `_create_invoices` over RPC)
(and custom residual: header + line + **Confirm `ir.actions.server.run`**, not an
`x_status` write). The implementation-job scorecard (stack / coverage / data /
smoke) is separate from ModuleSpec 10.0 — overall is the min, and a smoke fail
is never go-live. Refuse `write_mode=production`. Promote to another connection
stays human. Stock install/config is `ensure_module_installed` + versioned
recipes (l10n/CoA/journals/locations/UoM/pricelist/users) — do not LLM-generate
`ir.config_parameter`. Connector recipes (payments → inbound → messaging →
hardware → statutory compute-only) are domain-agnostic: land on stock
`payment.provider` / `sale.order` / Community POS-IoT; never generate
`payment.transaction` or `hr.payslip`; never write partner secrets. Do not seed
walkthrough demo data when client files exist. Do not clone a customer
production database. Autopilot `GET /jobs` ECONNRESET means uvicorn died
(reload/OOM/double Run) — poll retries, one job per connection, zip off the
poll payload; do not `--reload` while a job is running. Smoke retries must
not re-run Expert-fix. Autopilot custom residual is pack/skeleton + closer,
never `draft_module_from_prompt`. Residual clip keeps packet model + `_line` +
`_party` (not a parallel `x_bill`). Open smoke invoice must deep-link the
`account.move` id with the customer-invoice window action — not Accounting home.
Reuse of a dirty sandbox is warned, not wiped. Brief sample partners/products
may seed when no client files exist (not walkthrough when files exist). Poll until the backend is terminal — a
quiet `step_label` is not a failed job.

## Known failure modes
- Using Odoo 17/18 docs mental model on 19 without checking changelog differences.
- Treating `base.automation` Community availability as identical action types across versions.
- Installing a generated module on the shared dev DB without the ephemeral sandbox path.
