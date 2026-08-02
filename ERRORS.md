# ERRORS.md — Failure Log

> Check this before suggesting an approach to a task similar to one that's failed before.
> Log any approach that took more than ~2 attempts to work.

## Format
```
### [Date] — [what was being attempted]
**Didn't work:** the approach that failed
**Worked instead:** what actually fixed it
**Note for next time:** one line, generalized if possible
```

### 2026-07-28 — ModuleSpec apply skipped draft smart buttons / automations
**Didn't work:** Strict `on_model`/`related_model` + exact `AutomationTrigger` enum; assumed `relation_field` already on target; no M2O create before O2M/bundle.
**Worked instead:** Normalize key/trigger aliases; `_ensure_m2o_on_target_for_smart_button` before bundle; apply `access_rules` when resolvable.
**Note for next time:** AI drafts use Studio-ish labels (`create`/`write`, `source_model`); apply must coerce — related-window M2O always on target.

### 2026-07-28 — ModuleSpec builder showed Models (0) after Open from Wizard
**Didn't work:** Persist-on-mount wrote default `{ models: [] }` into `sessionStorage` before the AI draft was read, wiping the Wizard handoff.
**Worked instead:** Gate session writes on `hydrated` after load completes.
**Note for next time:** Never mirror React state to sessionStorage until initial hydrate finishes.

### 2026-07-28 — Open in Odoo: Name 'active_id' is not defined
**Didn't work:** Designer picked first act_window matching view_mode by name order (e.g. "API Loans") — related smart-button actions whose context/domain reference `active_id`.
**Worked instead:** Prefer standalone actions (`standalone_only` + `pickStandaloneWindowAction`); never deep-link related windows without a parent record.
**Note for next time:** Related window actions are correct for smart buttons; Open-in-Odoo must exclude any domain/context containing `active_id`/`active_ids`.

### 2026-07-28 — Activity Open in Odoo: Missing template "undefined"
**Didn't work:** Designer emitted `<activity><field/>…</activity>` without `<templates><div t-name="activity-box">`.
**Worked instead:** Match stock mail activity arches — always emit `activity-box` OWL template; put display fields inside it.
**Note for next time:** Activity view type is template-driven (OWL); ORM arch validation ≠ web client requirements.

### 2026-07-28 — Activity Save to Odoo: root should be `<activity>`, not `<data>`
**Didn't work:** Inherit strategy second-save wrote `render_inherit_replace_arch` (`<data><xpath>…`) onto the designer *primary* view (same name `model.designer.activity` as the first create).
**Worked instead:** When the designer-named view *is* the primary, update full typed arch in place; only use `<data><xpath>` for true extension children.
**Note for next time:** Never write inherit wrappers onto a primary `ir.ui.view` — Odoo validates root tag by `type` (activity/form/…).

### 2026-07-27 — Generate UI broke Contacts (`phone` xpath)
**Didn't work:** `_inject_button_box` rewrote `res.partner` primary form via `render_form_arch` → stock inherits looking for `//field[@name='phone']` failed.
**Worked instead:** Always upsert `{model}.studio.smart_buttons` inherit into `button_box` (or create box before sheet children); refuse stock primary rewrites for explicit views / polish.
**Note for next time:** Never mutate stock module primary arches — inherit xpath only (same rule as field inject / header actions).

### Soft warning — Odoo RPC claims without instance proof
**Didn't work:** (anticipated) Shipping `ir.model` / view XML / `base.automation` calls from model memory alone.
**Worked instead:** Smoke-test every new RPC helper against local Docker Odoo 19 before the next card.
**Note for next time:** Odoo API "certainty" is a gate failure waiting to happen — verify on `odoo:19`.

### 2026-07-27 — next_activity default user_id on custom models
**Didn't work:** `activity_user_field_name=user_id` on `x_lib_book` (no such field) → KeyError on `ir.actions.server.run`.
**Worked instead:** Resolve assignee field to `user_id` → `create_uid` → `write_uid`; Designer/API omit hard-coded `user_id`.
**Note for next time:** Custom `x_` models rarely have `user_id`; never assume CRM-like fields for mail activities.

### 2026-07-27 — Library status is loaned not borrowed
**Didn't work:** UAT wrote `x_status='borrowed'` (invalid selection).
**Worked instead:** Use `available|loaned|lost`; Designer update-field picker reads real selection options.
**Note for next time:** Never hard-code selection literals — load from `ir.model.fields.selection`.

### 2026-07-27 — Duplicate Mark Available from stacked inherits
**Didn't work:** Smoke created `x_lib_book.uat.phase2.buttons` then `x_lib_book.uat2.phase2.buttons` — both inject `<header>` before sheet → two buttons + two statusbars.
**Worked instead:** Single upsert inherit `x_lib_book.studio.header_actions`; unlink stale `*.uat*` views; smoke asserts `Mark Available` count == 1.
**Note for next time:** Form button/header xpath inherits must use one stable name and overwrite, never a new name per run.

### 2026-07-27 — Odoo 19 DB init CLI changed
**Didn't work:** Legacy `odoo -d DB -i base --stop-after-init --admin-passwd=...` (`--admin-passwd` gone; CLI is subcommand-based). Also failed when connection flags were placed after `init`.
**Worked instead:** `odoo db --db_host=db -r odoo -w odoo init --username admin --password admin [--force] DBNAME`
**Note for next time:** On `odoo:19`, run `odoo db --help` / `odoo db init --help` before assuming pre-19 recipes.

### 2026-07-27 — Sandbox compose tore down primary Odoo
**Didn't work:** `docker compose -f docker/docker-compose.sandbox.yml down -v` without `-p` (project defaults to folder name `docker`, same as primary stack).
**Worked instead:** Always `docker compose -p odoo-sandbox -f docker/docker-compose.sandbox.yml …` (wired in `app/sandbox.py`). Host port is **18069** (not 8070 — that belongs to permanent Odoo 18).
**Note for next time:** Sibling compose files in the same directory need distinct `-p` project names **and** non-overlapping host ports.

### 2026-07-27 — base_import_module cannot load Python models
**Didn't work:** Promote Python addon zip via `base.import.module` / `import_module` (access CSV fails: `model_x_*` missing because Python never loads).
**Worked instead:** Filesystem install into `/mnt/extra-addons` (+ restart) for local Docker; `install_mode=data` (ir.model / ir.model.fields XML) for remote import.
**Note for next time:** Treat `base_import_module` as data-only; never assume it equals `button_immediate_install` of a Python addon.

### 2026-07-27 — Odoo 19 res.groups / ACL field shapes
**Didn't work:** Assuming `res.groups.category_id` still exists (KeyError on Odoo 19).
**Worked instead:** Read `full_name`, `name`, `share`. `ir.model.access` / `ir.rule` `perm_*` are booleans; `ir.rule.groups` is many2many.
**Note for next time:** Probe field lists via `fields_get` on Odoo 19 before hard-coding Enterprise-era assumptions.

### 2026-07-27 — Confirm gates after Odoo connect hid 403
**Didn't work:** Calling `_client()` / Odoo RPC before `require_advanced_confirmation` on delete routes — bad connection → 502 instead of confirmation 403.
**Worked instead:** Connection existence check → confirm phrase → then Odoo client / mutation.
**Note for next time:** Authz/confirm gates must run before any dependency that can 502.

### 2026-07-27 — Required many2one + on_delete set null (Odoo 19)
**Didn't work:** Creating required `many2one` via `ir.model.fields` without `on_delete` (defaults to set null).
**Worked instead:** Set `on_delete=restrict` (or cascade) when `required=True`.
**Note for next time:** Odoo 19 validates m2o ondelete against required; Studio-like builders must set it.
**Note for next time:** `fields_get` before coding ACL helpers — group UX changed in 19.

### 2026-07-27 — Odoo 16/17 init while worker running → KeyError ir.http
**Didn't work:** `docker exec … odoo -i base --stop-after-init` against a DB the long-running container was already serving (partial registry; XML-RPC 500).
**Worked instead:** Stop worker → DROP DATABASE → `compose run --rm --no-deps odooN -i base,web --stop-after-init` → start worker.
**Note for next time:** Never install modules into a DB that a live odoo worker already has open.

### 2026-07-27 — create_model type=list fails on Odoo ≤17
**Didn't work:** Hard-coded `ir.ui.view.type='list'` / `<list>` arch (ValueError wrong value).
**Worked instead:** `views_vN.list_type_fallbacks("list")[0]` for type + matching arch root (`tree` on 16/17).
**Note for next time:** Prefer adapter list-type order for creates, not only for find_view fallbacks.

### 2026-07-27 — ir.model.fields.currency_field missing on Odoo 16
**Didn't work:** Always `read`/`search_read` including `currency_field` (Invalid field on 16).
**Worked instead:** `_ir_model_fields_columns()` filters via `fields_get` once per client.
**Note for next time:** Optional columns on `ir.model.fields` must be version-probed, not assumed from 19.
