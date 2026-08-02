# Deploy checklist (mastery M6)

Production wrap for the No-Code Odoo Customization Platform API + web.

## Auth (required on shared/deployed API)

```bash
export AUTH_MODE=api_key
export APP_API_KEY='generate-a-long-random-secret'
# optional: hashed keys in app_api_keys table via API bootstrap
```

Clients send `Authorization: Bearer <key>` or `X-API-Key: <key>`.

Local gates may keep `AUTH_MODE=off`. **Never** ship a public URL with auth off.

## Rate limit / audit

```bash
export RATE_LIMIT_PER_MINUTE=120   # 0 disables (dev only)
# Audit middleware is on by default — confirm logs do not store Odoo passwords
```

## Secrets

- `FERNET_KEY` — encrypts Odoo connection secrets at rest (required).
- `DATABASE_URL` — app Postgres (not customer Odoo DB).
- Prefer Odoo **API keys** over passwords in connection forms.

## Process

1. Migrate/init app DB (`init_db` on API startup or explicit Alembic if added).
2. Start API (`uvicorn app.main:app`) behind TLS.
3. Start web (`pnpm build && pnpm start`) with `NEXT_PUBLIC_API_URL` pointing at the API.
4. Optional: Docker sandbox host for Option A promote (Docker socket access for ephemeral `:18069`).

## Hosting targets

Fly.io or Railway — no paid SaaS dependency required for bootstrapping.

## CI policy

| Gate | When |
|------|------|
| Unit pytest / vitest | Every PR |
| Playwright caps harness | Every PR if browser installed |
| `major-matrix` sandbox | Manual workflow dispatch / weekly optional |
| Live Odoo 16–19 integration | Local or scheduled; skip when stacks down |

## Post-deploy smoke

1. `GET /api/auth/status` (or health) with API key.
2. Create connection → probe → confirm hosting badge + capabilities.
3. Online connection: Python promote must fail with Online-specific message.
4. Self-host: sandbox → data or filesystem promote as appropriate.

## Rollback honesty

Snapshots cover views, automations, ACL, menus, reports. Dropped columns / data loss are only partially recoverable — UI must keep warning.
