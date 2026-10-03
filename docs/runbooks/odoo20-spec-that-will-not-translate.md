# Odoo 20 spec that will not translate

Use this runbook when a config spec authored for Odoo 19 is replayed as major 20 and the apply stops with a named migration note. Replay is fail-closed: the first refused op writes nothing. Do not enable L4. Do not call a live Odoo host from this path.

## How to detect

- Replay / apply raises `MigrationNote` (an `ApplyError`) before the fake or real port is called.
- `port.call_count` for that apply is `0`. Earlier settings, fields, or records are not left behind.
- The note name is one of the known refusals below, or `not_translated` for a version-table row that still says verify.

## Known refusals

These 19 constructs do **not** auto-translate. Rewrite the spec, then replay again.

| Note name | Operator message | What to do |
|---|---|---|
| `company_type_removed` | company_type removed | Drop `company_type`. Odoo 20 removed the field. Do not invent a replacement column. |
| `group_record_rule` | group record rules must become ir.access with a domain | Delete `record_rules` / `ir.rule`. Add an `access_rights` row with a domain. The existing access compiler emits `ir.access`. A security owner reviews the domain. |
| `percentage_pricelist_is_discount` | percentage pricelist is discount | Change pricelist `compute_price` / type from `percentage` to the 20 discount shape. The replay will not rewrite the value. |
| `company_registry_is_additional_identifiers` | company_registry is additional identifiers | Remove `company_registry`. On 20 the registry lives in additional identifiers. The replay will not guess a JSON key. |

Access rights that already carry a domain **do** apply through the existing `compile_access` translator (`ir.access` on 20). That is not a second compiler.

## Rows that still say verify — not translated

These version-table rows still say **verify** on 19. If the spec uses them, replay names the **area** as not translated. It does not guess a 20 field name.

| V-id | Area | Do not guess |
|---|---|---|
| V06 | tax_included | Not `override`, not a document-level switch name |
| V24 | account_payment_state | Not `reconciled` / a 20 state list |
| V26 | partner_mobile | Not a 20 partner field name |
| V28 | bom_consumption | Not a substitute BOM field |
| V29 | return_wizard | Not a replacement wizard model |
| V30 | tracking_values_model | Not a replacement tracking model |

If the table still says verify, treat the row as **not translated**, not as a field to invent.

## How to stop the bleed

1. Do not retry the same spec against a customer 20 database.
2. Read the `MigrationNote.name` and the operator message.
3. Confirm the fake port (or journal) has zero writes for that apply.
4. Leave L4 off. `write_mode=production` stays refused.

## How to recover

1. Edit the 19 spec: remove or rewrite the refused construct using the table above.
2. Replay on a fake port first (`replay_19_on_20`). Expect either `ir.access` writes or another named note.
3. Only after a clean fake replay, run the operator production checklist on a duplicate database — not on production.
4. Promote stays human.

## Audit kinds that prove recovery

- Config apply / change-set journal for the failed apply: no `RESULT` rows after a `MigrationNote`.
- The successful retry’s plan card (`plan_hash`, environment) and fake-port `ir.access` creates (no `ir.rule`).
- Hash-chained HTTP audit if the retry later goes through the API (`http_mutation`). A refused replay that never reached the port should not append a mutation row.

## Related

- Version table: `packages/odoo-client/src/odoo_client/compat/version_table.py`
- Access compiler: `apps/api/app/odoo20/access_compiler.py`
- Replay: `apps/api/app/odoo20/spec_replay.py`
- Production checklist: `docs/runbooks/odoo20-production-checklist.md`
