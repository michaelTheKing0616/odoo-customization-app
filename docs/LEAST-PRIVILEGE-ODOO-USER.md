# Least-privilege Odoo user for Odoo Custom

Use a **dedicated Odoo user** (not your day-to-day admin) when connecting instances to Odoo Custom.

## Why

- Odoo Custom acts through **public ORM/RPC only** — it can never exceed what that user can do in Odoo.
- A scoped user limits blast radius if credentials leak or an operator runs a risky bulk action.
- New connections default to **Observer** mode (read-only) until a workspace admin unlocks write mode.

## Recommended setup (Community 17–19)

1. In Odoo: **Settings → Users & Companies → Users → New**.
2. Create a user such as `customization_bot@yourcompany.com`.
3. Assign only the **application groups** needed for the models you will customize (e.g. Sales / Inventory), not **Settings / Administration** unless you truly need it.
4. Prefer an **API key** (Odoo 14+) over the main admin password:
   - Log in as that user → **Preferences → Account Security → New API Key**.
   - Paste the key into Odoo Custom Connect (stored encrypted at rest).
5. Connect in Odoo Custom — the connection starts in **Observer** mode.
6. Browse models, run Expert, and review capabilities. When ready, a workspace **admin** unlocks **Standard** write mode from the connection overview.

## Production write mode

**Production** mode is gated behind the **production readiness checklist** (Wave 12 TRUST-8). Until it passes, use **Standard** for sandbox/staging instances.

## Version notes

| Major | API keys | Notes |
|-------|----------|--------|
| 19 | Yes | Preferred |
| 18 | Yes | Preferred |
| 17 | Yes | Preferred |
| 16 | Password only | Experimental support — use a dedicated user with minimal groups |

## What Observer allows

Read-only RPC: `search_read`, `read`, `fields_get`, introspection, Expert grounding, health checks. Mutations (`create`, `write`, `unlink`, server actions) are blocked at the RPC client layer.
