# Track 9 — Odoo 20 GA

D11: Community 20 is GA beside 17, 18, and 19. 16 stays experimental. ≤15 stays refused. Odoo 20.0 image pin starts at `odoo:20` and is recorded in the progress log when the gate runs. Blueprint live notes used `20.0-20260926`; re-verify, do not freeze a stale digest.

Community 20 has no `ai*` modules. Do not claim MCP, Studio, Helpdesk, Payroll, or Quality on the Community image.

## Gates O20-01–O20-16

| ID | Done when |
|---|---|
| O20-01 | `docker/docker-compose.odoo20.yml` serves Community 20 on host port 8073 with a matching Postgres and init script |
| O20-02 | `compat/registry.py` lists 20 as GA. `parse_major` accepts `20.0` and `20.0+e` |
| O20-03 | Adapters `views_v20`, `automation_v20`, and `security_v20` exist. 16–19 adapters unchanged |
| O20-04 | `ir.access` compiler: an ACL plus a domain becomes `ir.access` rows. Group `ir.rule` on 20 is refused with a warning, not silently dropped |
| O20-05 | Access screen (`/connections/[id]/access`) reads and writes `ir.access` on 20 and the old models on ≤19 |
| O20-06 | Every version-table row below has a fake-client test and a live test against the 20 stack |
| O20-07 | JSON-2 is the default protocol on 20. Password login explains why it cannot use JSON-2 |
| O20-08 | Snapshot strategy does not call the removed `db` service. Backup uses the documented 20 path or asks the human on Online |
| O20-09 | Native MCP detection returns absent on Community 20 |
| O20-10 | `docker/run-sandbox-major-gate.sh` includes 20 |
| O20-11 | Quote-to-cash (7 checks), procure-to-pay (6), and manufacture (2) pass on 20 |
| O20-12 | Designer opens a form view on 20 (list tag, not tree) |
| O20-13 | Production checklist below is a documented operator card, and the automated parts are tested |
| O20-14 | `name_search` uses `domain`, not `args` |
| O20-15 | `formatted_read_group` is used for aggregates. Legacy `read_group` shape is not sent |
| O20-16 | A 19 database's spec plan, replayed on 20, either applies through the translators or fails with a named migration note. It does not half-apply |

## Version differences (each row is a test)

| Area | ≤15 (refused) | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|
| Routes | `stock.location.route` | `stock.route` | same | same | same | `stock.route` |
| Account type | `user_type_id` | `account_type` | same | same | same | `account_type` |
| Account company | `company_id` | same | same | `company_ids` | same | `company_ids` |
| Analytic | tags | plans + `analytic_distribution` | same | same | same | same |
| Tax repartition | invoice/refund fields | same | `repartition_line_ids` + `document_type` | same | same | same |
| Tax included | `price_include` | same | same | verify override | verify | override + document-level switch |
| Payment term lines | `days` / `option` | verify | `nb_days` | same | same | `nb_days` |
| Product type | `detailed_type` | same | same | `type` + `is_storable` | same | same |
| Purchase UoM | `uom_po_id` | same | same | same | removed | removed |
| Stock done qty | `quantity_done` | same | `quantity` + `picked` | same | same | same |
| Automation | inherits server action | same | separate `ir.actions.server` | same | same | same |
| Cron `numbercall` | present | present | present | removed | removed | removed |
| User groups | `groups_id` | same | same | same | `group_ids` | `group_ids` |
| `name_search` | `args` | same | same | verify | `domain` | `domain` |
| Web URLs | `/web#` | same | `/web#action=` | `/odoo/...` | same | `/odoo/...` |
| API | XML/JSON-RPC | same | same | same | JSON-2 added | JSON-2 preferred; `db` removed |
| Fiscal position tax map | separate model | same | same | same | on the tax | on the tax |
| Access | `ir.model.access` + `ir.rule` | same | same | same | same | `ir.access` |
| Account groups | `account.group` | same | same | same | same | `parent_id`; group model gone |
| Root product category | `product.product_category_all` | same | same | same | Goods/Services/Expenses | same |
| UoM categories / packaging | present | same | same | same | removed | removed |
| Pricelist types | fixed/percentage/formula | same | same | same | same | fixed/discount/markup |
| Report layouts | standard/boxed/bold/striped | same | same | same | + bubble/wave/folder | standard, bubble, center, compact, dual, folder, lines, wave + `report_tables_id` |
| `account.payment.state` | — | — | verify | draft/in_process/paid | verify | draft/paid/reconciled |
| Partner `company_type` | present | same | same | same | same | removed |
| Partner `mobile` / `title` | present | same | same | same | verify | absent from base |
| Company registry | `company_registry` | same | same | same | same | `additional_identifiers` JSON |
| BOM consumption | present | same | same | same | verify | removed |
| Return wizard | `stock.return.picking` | same | same | same | verify | removed |
| Tracking values model | `mail.tracking.value` | same | same | same | verify | removed |
| `read_group` | legacy | same | same | same | formatted added | aggregates and tuples |
| User `role` | — | — | — | — | group_user / system | light / regular / system |

On ≤19, `demo=false` in the database create form still loads demo data because of a truthy-string bug. On 20 the flag parses. Tests must not assume `demo=false` works on 17–19.

`action_apply_inventory` returns None. XML-RPC must tolerate that. Playwright `networkidle` never settles on 20; wait for RPC idle (`quiet_ms` 400, timeout 20s).

## `ir.access` compiler rules

- `access_rights` on 20 compile to `ir.access` (`operation`, optional `domain`).
- `record_rules` that name a group on 20 fail the plan with a migration message: rewrite as `access_rights` with a domain.
- Do not write the computed `kind` field.
- On ≤19, domain-bearing rights still compile to an access row plus an `ir.rule`.
- Security models `ir.access`, `ir.model.access`, `ir.rule`, `res.groups` stay DESTRUCTIVE.

## Production checklist (operator plus automated)

- Bot user plus an `rpc`-scope API key with an expiry. `ODOO_PROTOCOL=auto`.
- `profile` output: every `(verify)` note is read.
- Replace `company_type`, `company_registry`, percentage pricelist rules, account groups, and legacy layouts via the translators.
- Rewrite group record rules as access rights with a domain. A security owner reviews.
- Re-run flow tests on a duplicate. Check a printed invoice layout.
- AI and MCP: agree key ownership before any Enterprise database is connected. Community skips this step.

## Definition of done additions

See `15_DOD_AND_E2E.md` items 33–36.

## Do not

- Do not vendor `odoo-config-agent`. Port the profile tests.
- Do not point the 20 stack at a customer database.
- Do not keep sending `ir.rule` creates on 20 because 19 tests passed.
