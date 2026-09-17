# Odoo hosting + version kingship

How Ingenium stays ahead of Online / SaaS, Community, Enterprise, Odoo.sh, and on-prem as majors ship.

## Version string parsing

Online reports channel-prefixed versions such as `saas~19.4+e`. `parse_major` strips a leading `saas~` / `saas-` tag and takes the first integer major so connect treats these as supported 19.x (not an unsupported string).

## Hosting types (what operators mean)

| Label people say | What it is | URL shape | Notes |
|------------------|------------|-----------|--------|
| **Online / SaaS** | Odoo Online (`*.odoo.com`) | `https://<db>.odoo.com` | No custom Python modules. Prefer **API keys**. DB name ≈ subdomain. |
| **Odoo.sh** | PaaS git hosting | `https://<project>.odoo.sh` (or custom domain) | Full modules via git; still public RPC. |
| **Enterprise** | Paid edition (any host) | same as host | Public ORM only — never Studio internals. |
| **Community** | Open-source edition | same as host | Full safe subset we target. |
| **On-premise / VPS** | Self-hosted | `https://odoo.company.com` or `http://host:8069` | Full control; sandbox → promote. |

Edition (Community vs Enterprise) is **orthogonal** to hosting (Online vs odoo.sh vs on-prem).

## Why SaaS 19.4 often failed to connect

Typical failure modes we now harden against:

1. **Browser URL paste** — `https://db.odoo.com/odoo/...` → RPC must hit the **root**. `normalize_odoo_base_url` strips `/odoo`, `/web`, deep links, query, fragment.
2. **Wrong database** — Online DB is usually the subdomain (`acme` for `acme.odoo.com`). Connect UX auto-suggests it.
3. **Password vs API key** — Online often rejects login passwords for RPC; use **Settings → Users → API Keys**.
4. **XML-RPC blocked** — some Online / WAF paths block `/xmlrpc/2/*`. Client now **falls back to `/jsonrpc`**.
5. **Version string** — `19.4`, `19.4+e` parse as major **19** (already supported GA).

## Forward-compat strategy (stay king)

1. **Probe-first, never ceiling-hardcode** — `version()` → `parse_major` → capability matrix. Unknown majors fail closed with a clear message + path to add a registry row.
2. **Capability flags per major** — `packages/odoo-client/compat/` adapters (views, automation). New major = copy nearest adapter + smoke, then GA.
3. **Transport resilience** — XML-RPC primary, JSON-RPC fallback; hosting-aware error copy.
4. **Hosting honesty** — Online cannot install custom Python; UI/docs say so (`hosting.py` / connect tip).
5. **CI matrix** — unit tests for URL/hosting/version parse; live smoke against Docker 16–19 when available.
6. **When Odoo 20 ships** — add `ODOO_20_CAPABILITIES`, `for_major(20)`, adapter module, Docker smoke, promote to GA after parity checklist. No app rewrite.

## Operator checklist (Online 19.x)

1. URL = `https://YOURDB.odoo.com` (no `/odoo`).
2. Database = `YOURDB`.
3. Username = login email.
4. Password field = **API key**.
5. Save → capability probe should show major 19 + hosting Online.

## API key creation UX

Ingenium **never mints** Odoo API keys. Creation always happens in Odoo (Preferences → Account Security → New API Key).

Connect shows an **API key guide** panel with numbered steps and an **Open Odoo to create key** button that opens the instance web client (`/odoo` on Online, `/web` elsewhere). The user copies the one-time key and pastes it into Ingenium.

