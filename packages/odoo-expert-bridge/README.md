# Odoo Expert Bridge

Deep-link from Odoo Community to the No-Code Customization app Expert panel.

## Root cause if the module never appeared

**Invalid `__manifest__.py`.** Odoo requires a **Python** dict (`True` / `False`). JSON literals (`true` / `false`) make Odoo **silently skip** the module — no error in Apps, nothing under Technical.

Generated modules from this platform use correct Python manifests. Only this bridge module had the JSON mistake (now fixed).

## One-command install (recommended)

```bash
./docker/install-expert-bridge.sh
```

Uses database **`odoo_dev`** (same as `docker/init-db.sh`), installs via CLI — **no Apps UI hunt required**.

Environment overrides: `ODOO_DB`, `ODOO_USER`, `ODOO_ADMIN_PASSWORD`, `INSTALL=0` (copy only).

## Does the docker-compose fix help other custom apps?

| Path | How modules land | Discoverable? |
|------|------------------|---------------|
| **Export → Promote** (local `:8069`) | `docker cp` → `/mnt/extra-addons/{module}` + `install_module_by_name` | Yes — API runs `update_list` + install |
| **Sandbox gate** (`:18069`) | Zip extracted to `sandbox-addons` or extra-addons | Yes — RPC install in gate scripts |
| **Repo modules** in `docker/sandbox-addons/` | Bind mount (after `compose up --force-recreate odoo`) | Yes — after `update_list` or `-i module` |

**Before the compose change:** main `:8069` used an empty Docker **volume**, so only modules copied via `docker cp` (promote) appeared — not files sitting only in the git repo.

**Custom apps you build** already get valid manifests from `module-generator`; they were **not** affected by the JSON bug.

## Odoo 19 — where is the module list?

There is **no** `Settings → Technical → Modules → Modules` in Odoo 19 Community.

Use one of:

1. **This install script** (easiest)
2. **Apps** app (top menu) → **Update Apps List** → search **`Odoo Expert Bridge`**
3. Remove the **Apps** filter chip if search is empty (shows non-app modules too)

Direct URL (developer mode): open Apps, enable debug, Update Apps List.

## After install

1. **Settings → Technical → System Parameters**
   - Key: `expert_bridge.base_url`
   - Value: `http://localhost:3000`
2. **Settings → Expert (Customization App)** — opens your web app with Expert panel

Record deep-link: `/odoo-expert-bridge/open?model=x_branch&res_id=1`

## Verify

```bash
docker exec odoo-custom-odoo cat /mnt/extra-addons/odoo_expert_bridge/__manifest__.py | head -5
# Must show: installable: True  (capital T)

docker exec odoo-custom-odoo odoo db -r odoo -w odoo -d odoo_dev shell -c "
print(env['ir.module.module'].search_read([('name','=','odoo_expert_bridge')], ['state']))
" 2>/dev/null || true
```
