# Odoo Expert Bridge

Deep-link from Odoo Community to the No-Code Customization app Expert panel.

## Sandbox install (Docker)

1. **Module on disk** — already copied to `docker/sandbox-addons/odoo_expert_bridge` (or copy from `packages/odoo-expert-bridge`):

   ```bash
   cp -R packages/odoo-expert-bridge docker/sandbox-addons/odoo_expert_bridge
   ```

2. **Start sandbox** (port **18069**):

   ```bash
   docker compose -p odoo-sandbox -f docker/docker-compose.sandbox.yml up -d
   ```

3. **Install the module** in Odoo:
   - Open http://127.0.0.1:18069
   - Log in (default admin — set on first run)
   - **Apps** → update apps list → search **Odoo Expert Bridge** → Install  
   - Or: **Settings → Technical → Apps** → install `odoo_expert_bridge`

4. **Set the app URL** (System Parameter):
   - **Settings → Technical → System Parameters**
   - Create / edit:
     - **Key:** `expert_bridge.base_url`
     - **Value:** `http://localhost:3000` (your Next.js web app URL; no trailing slash)

5. **Use it:**
   - **Settings → Expert (Customization App)** opens the app with `?expert=1`
   - Optional record context: `/odoo-expert-bridge/open?model=x_branch&res_id=1`

## Production / remote Odoo

Copy `odoo_expert_bridge` into the instance's addons path, restart Odoo, install the module, set `expert_bridge.base_url` to your deployed web app URL (HTTPS).

## Chatter export (from the web app)

Expert answers can be logged as **internal notes** via **Log as Odoo note** when the shell has `model` + `res_id` context (e.g. deep-link with `res_id`).
