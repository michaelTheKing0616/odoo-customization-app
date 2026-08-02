# Module interoperability

How this app works with **existing Odoo modules** and **other custom modules**.

## Two modes

| Mode | What it does | Portable? |
|------|----------------|-----------|
| **Live metadata** | RPC creates `x_*` fields, inherit views, automations, ACL on any model (`res.partner`, `sale.order`, peer `x_*` models) | Bound to that database until you export |
| **Export / promote** | Builds an installable addon zip that other databases can install | Yes — uses Odoo `depends` + `_inherit` |

Composition with other modules is always via normal Odoo mechanisms: **`depends` in `__manifest__.py`**, **`_inherit`**, **view `inherit_id` + xpath**, and **relational fields**.

## Live customization of existing modules

Already supported:

1. **Add `x_*` fields** to any model (e.g. `res.partner`) — Builder model field is free text.
2. **Relations** — Many2one / one2many / many2many to `sale.order`, another custom `x_ticket`, etc.
3. **Related fields** — pick a **concrete type** (char, many2one, …) + optional related path (`partner_id.country_id`).
4. **Automations / ACL** — any model.
5. **Field inject** — default strategy is **inherit** (creates a child `ir.ui.view` with xpath). Mutating the parent arch requires advanced confirm (`I understand the risks`) so upgrades of `sale`/`contacts` are safer.

## Export that extends stock / peer modules

`POST .../export-module`:

```json
{
  "technical_name": "partner_loyalty_ext",
  "display_name": "Partner Loyalty Ext",
  "include_custom_models": true,
  "include_extensions": true,
  "extend_models": ["res.partner"],
  "depends": ["contacts"],
  "install_mode": "python"
}
```

- **`include_extensions`** (default true): package `x_*` fields on non-`x_*` models as `_inherit` extensions.
- **`extend_models`**: force-include those models; if omitted, auto-detect models that already have manual `x_*` fields.
- **`depends`**: merged with **inferred** depends (e.g. M2O → `sale.order` adds `sale`; inherit `crm.lead` adds `crm`).

Generated Python for an extension looks like:

```python
class ResPartner(models.Model):
    _inherit = "res.partner"
    x_loyalty_tier = fields.Char(string="Loyalty tier")
```

Views use `inherit_id` + xpath when the primary view’s XML id can be resolved.

## Working with *other* custom modules

1. Ensure the peer module is **installed** on the connection (Apps).
2. Point relations / inherit / automations at its models (`x_other.thing` or whatever technical name it uses).
3. On export, pick peer modules from the **installed-module depends picker** (or free-form extra depends) if inference does not know them (only common stock modules are in the built-in map). API: `GET .../modules/installed?q=` or `GET .../modules?installed_only=true&applications_only=false`.
4. Sandbox/promote: the sandbox image is a clean Odoo 19 — **stock depends** that are not in the base image must be preloaded via `SANDBOX_EXTRA_MODULES` / `SandboxRunBody.extra_modules` (e.g. `sale,account`), or validate on a target that already has those modules. Use `docker/run-sandbox-extension-gate.sh` for sale/account (slower than smoke). Peer custom modules must be present on the promote target before install.

## What not to do

- Do not overwrite primary views of `sale`/`account` without confirm — use inherit inject.
- Do not expect `base_import_module` (data mode) to load Python `_inherit` with compute methods — use filesystem/python promote for real extensions.
- Do not share one API key across tenants — keys see all connections.

## Related code

- Generator: `ModelSpec.mode` / `inherit`, `infer_and_merge_depends`, xpath views
- Client: `inject_field_into_views(strategy="inherit")`, `create_inherit_view`
- Export: `apps/api/app/export_service.py`
