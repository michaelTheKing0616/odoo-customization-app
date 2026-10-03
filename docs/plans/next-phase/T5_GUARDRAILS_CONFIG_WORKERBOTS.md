# Track 5 — guardrails, config-as-code, worker bots

Sources: master §6A, blueprint §5–§8, `odoo-config-agent` as the D7 oracle. One implementation. T8 extends this core; it does not fork it.

Map `classify_rpc` onto existing Bucket A / B / C. Do not leave a parallel taxonomy (master DoD 21).

## Risk classes

| Class | Meaning |
|---|---|
| READ | No state change |
| REVERSIBLE | Undoable from the changelog or an inverse |
| DESTRUCTIVE | Irreversible, security-sensitive, or externally visible |
| BILLABLE | May change what the client pays |

R0–R4 in `02_APPROVAL_FLOW.md` are the approval scale. READ/REVERSIBLE/DESTRUCTIVE/BILLABLE are the RPC scale. The mapping card writes the table both ways and tests it.

## Verbatim lists (oracle: blueprint and `guardrails.py`; copy into Ingenium, do not import the package)

### READ_METHODS

```
search, search_read, read, search_count, fields_get, name_search,
default_get, read_group, formatted_read_group, context_get, exists, get_views
```

### SENSITIVE_MODELS

```
ir.model.access, ir.rule, ir.access, res.groups, res.groups.privilege, ir.config_parameter,
ir.mail_server, fetchmail.server, auth.oauth.provider, res.users.apikeys, ir.module.module,
account.move, account.payment, account.bank.statement, account.bank.statement.line,
hr.payslip, ir.cron, ir.actions.server, base.automation, ir.ui.view,
ir.model, ir.model.fields, payment.provider
```

### DESTRUCTIVE_METHODS

```
unlink, button_immediate_uninstall, button_uninstall, action_post, button_cancel,
action_cancel, action_reverse, button_draft, action_send_mail, message_post,
send_mail, action_invoice_sent, action_register_payment, action_create_payments,
action_validate, button_validate, button_mark_done, action_done, unlink_all,
toggle_active, action_archive, action_unarchive, reconcile, remove_move_reconcile
```

### BILLABLE_METHODS

```
button_immediate_install, button_install, button_upgrade,
button_immediate_upgrade, iap_*, *_iap_*, action_buy_*
```

### NEVER_ALLOWED

```
("res.users", "unlink")
("res.company", "unlink")
("ir.model.data", "unlink")
("ir.config_parameter", "unlink")
("res.users.apikeys", "*")
```

### PROTECTED_PARAMS

```
database.secret, database.uuid, database.create_date, web.base.url,
database.enterprise_code, database.expiration_date
```

Forbidden actions return a classification with `forbidden=True`. The gate denies them. Returning DESTRUCTIVE plus forbidden is acceptable if the gate cannot be skipped. Naming them "just destructive" is not.

## Extra classification rules

- A write touching more than 50 ids escalates to DESTRUCTIVE.
- Module install on Community is DESTRUCTIVE. On enterprise, online, or Odoo.sh it is BILLABLE.
- A new internal user (`share` falsy) on a paid edition is BILLABLE.
- `res.config.settings` with `module_*=True` follows the same edition rule.
- Protected parameter writes are forbidden even with approval.

## Phase 5A gates

| ID | Gate |
|---|---|
| 5A-1 | A sample of reads, creates, unlinks, security models, billable installs, and protected params classifies as the lists say |
| 5A-2 | Every write-capable tool in Tracks 1, 3, and 4 refuses a live write until a dry-run hash of `(tool, args minus dry_run)` has been seen |
| 5A-3 | Plan fingerprint is SHA-256 of the actionable changes JSON (`sort_keys`, `res_id` excluded), truncated to 16 hex chars. Apply re-plans. Mismatch aborts with plan drift. Test at least one operation per track |
| 5A-4 | Never-allowed has no override, including at L4 |
| 5A-5 | A tampered audit entry is detected by the verify command |
| 5A-6 | A DESTRUCTIVE or BILLABLE production apply refuses without a successful snapshot recorded immediately before |
| 5A-7 | Code inspection: zero write-effect calls through an MCP client |
| 5A-8 | Production apply of anything except READ and an allow-listed REVERSIBLE glob requires approval |
| 5A-9 | Staging auto-approves only READ and REVERSIBLE |
| 5A-10 | Oracle tests from `test_guardrails_audit.py` have Ingenium equivalents: `test_read_is_read`, `test_create_is_reversible`, `test_unlink_destructive_and_forbidden`, `test_security_models_destructive`, `test_billable_depends_on_edition`, `test_protected_params_forbidden`, `test_mass_write`, `test_policy_thresholds`, `test_audit_chain_and_tamper`, `test_redaction` |

### Audit entry

Fields: `ts`, `run`, `actor`, `kind`, payload, `prev` (SHA-256 of the previous entry, genesis = 64 zero hex chars), `hash` (SHA-256 of the entry without its own `hash`).

Kinds include `rpc_write`, `change`, `tool_call`, `approval`, `llm_turn`, `screenshot`, `error`, `module`, `settings`, `flow_test`, `note`, plus auth kinds from Track 6.

`change` payload: `model`, `action` (`created` or `updated`), `res_id`, `key`, `xmlid`, `changes: {field: {old, new}}`.

Redact keys matching `pass|password|secret|token|api[_-]?key|smtp_pass|authorization`.

Retention: at least 24 months. Accounting-related changes: 7 years. The audit write must not break the request path if the logger fails closed into a retry, but it must not drop the entry silently.

### Rollback tiers

1. Database snapshot restore, where `/web/database/*` exists (not Odoo Online, not Odoo.sh, and not relied on for Odoo 20's removed `db` service — see T9).
2. Compensating plan from the audit: created → unlink, updated → write old values. Module installs and posted entries are not undone this way.
3. Manual, with the changelog.

### Further production budgets (blueprint §5.6)

Max 40 LLM steps. Max 120 tool calls. Blast radius 200 records per apply unless a tighter card says otherwise (L4 is 50). Change windows. Two-person rule for R3. Kill switch.

## Phase 5B — declarative config

YAML top-level keys: `version`, `project`, `description`, `target`, plus these sections, applied in this order:

`modules`, `languages`, `currencies`, `companies`, `settings`, `users`, `sequences`, `mail_servers`, `tax_groups`, `accounts`, `taxes`, `journals`, `payment_terms`, `fiscal_positions`, `analytic_plans`, `analytic_accounts`, `product_categories`, `product_attributes`, `warehouses`, `locations`, `operation_types`, `routes`, `products`, `pricelists`, `reorder_rules`, `putaway_rules`, `crm_stages`, `sales_teams`, `sale_templates`, `workcenters`, `boms`, `departments`, `jobs`, `employees`, `leave_types`, `pos_payment_methods`, `pos_configs`, `projects`, `task_stages`, `custom_fields`, `views`, `server_actions`, `automations`, `crons`, `access_rights`, `record_rules`, `records`.

Common entry fields: `key`, `xmlid`, `match`, `company`, `values`, `create_only`, `note`.

Refs: `key:`, `ref:`, `find:`, `name:`, `secret:`, optional `?` prefix. `secret:` is a vault pointer, never a literal.

| Gate | Proof |
|---|---|
| Second apply is a no-op | Same spec, same database, zero writes |
| Fingerprint drift | Edit the database between plan and apply; apply aborts |
| Version briefing | Live-probed, not a static paragraph |
| l10n | Adopt `l10n_ng` taxes by xmlid `account.<company_id>_l10n_ng_*`. Do not duplicate the tax |
| Custom fields | `x_` prefix required. `x_studio_*` avoided |
| Blocked items | Skipped unless `--include-blocked` |
| Production | Requires an explicit production acknowledgement flag. `write_mode=production` on the connection remains refused by the repo lock; this flag is for the spec apply inside an allowed sandbox or a confirmed staging connection |

Import rules: CSV `id` column always. Prefer `field/id`. Order categories → products → partners → pricelists → opening stock → opening GL. Dates `YYYY-MM-DD`. Validate against `fields_get`. Prefer `load()`. Batch 500. Context `tracking_disable`, `mail_create_nolog`, `mail_notrack`. Phone normalized to `+234…`. Fuzzy name dedupe ≥ 0.92 with 3-character blocks. Blank cells are never a dedupe key. Partner merge is DESTRUCTIVE. Opening balances need approval. Posting is DESTRUCTIVE.

Oracle test names to reimplement: every function in `test_spec.py`, `test_importers.py`, and `test_versions_profiles.py` listed in `17_COVERAGE_MATRIX.md`.

Nigeria figures in the blueprint (VAT 7.5%, WHT 5% and 10%) are illustrative. The accountant decides. PAYE, PenCom, and NHF come from a specialist, not the model.

## Phase 5C — Worker Bots L0–L3

One chassis executes representative tasks from Tracks 1, 3, and 4 through one loop, one guardrail engine, and one audit log (master DoD 25).

| Level | Behavior |
|---|---|
| L0 | Assistant, no writes |
| L1 | Read-only tools |
| L2 | Every write pauses for approval. 100% of writes pause. This is the production default |
| L3 | REVERSIBLE unsupervised on staging. DESTRUCTIVE and BILLABLE pause |
| L4 | Separate cards. See GATE-L4. Not this phase's default |

| Gate | Proof |
|---|---|
| Multi-client lock | A second client queues; it does not interleave applies |
| Drift | An out-of-band change between plan and apply aborts |
| Adversarial | An instruction embedded in a product description causes no destructive action |
| Never-allowed at L4 | Direct test, not a review |
| Evals | Golden, adversarial, ambiguity, version drift, cost, and safety. Safety is 100% approval on billable and destructive repeats |

Flow checks when a flow runner exists: quote-to-cash 7 checks, procure-to-pay 6, manufacture 2. Never on production. Prefix test records so they are identifiable.

## Autonomy target from the blueprint

L3 on staging, L2 on production, until GATE-L4-08 evidence exists. Then L4 only inside the allow-list.
