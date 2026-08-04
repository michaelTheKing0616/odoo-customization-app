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
- Rotate `FERNET_KEY` with `scripts/rotate_fernet_key.sh` (see procedure in script header).

## App database backup & restore

The app Postgres holds metadata snapshots, audit rows, and encrypted Odoo credentials — treat it as production-critical.

**Backup (daily recommended):**

```bash
export DATABASE_URL='postgresql+psycopg://user:pass@host:5432/odoo_custom'
PG_URL="${DATABASE_URL/postgresql+psycopg/postgresql}"
pg_dump -Fc --no-owner --no-acl -f "odoo_custom_$(date +%Y%m%d).dump" "$PG_URL"
```

Store dumps off-host (object storage or encrypted volume). Retain ≥30 days for snapshot rollback support.

**Restore (maintenance window — destructive to target DB):**

```bash
export DATABASE_URL='postgresql+psycopg://user:pass@host:5432/odoo_custom'
./scripts/restore_app_db.sh /path/to/odoo_custom_YYYYMMDD.dump
```

Verify on a **copy** first. After restore: restart API, `GET /health`, spot-check one connection probe.

**Fernet rotation:** snapshot DB → `OLD_FERNET_KEY` + `NEW_FERNET_KEY` → `scripts/rotate_fernet_key.sh --dry-run` → apply → deploy new key.

## Beta / GA (TRUST-9)

```bash
export BETA_PRODUCTION_GATING_ENABLED=1
export PRODUCTION_WRITE_MODE_GA_UNLOCKED=0   # flip at GA launch
export BETA_GA_MIN_WORKSPACES=8
export BETA_GA_MIN_WEEKS=4
```

Partner runbook: `docs/BETA_PROTOCOL.md`. Mark workspaces via admin console or
`PATCH /api/admin/workspaces/{id}/beta-partner`.

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
| `security-supply-chain` | Every PR — pip-audit, pnpm audit (high+), secrets scan |

## Post-deploy smoke

1. `GET /api/auth/status` (or health) with API key.
2. Create connection → probe → confirm hosting badge + capabilities.
3. Online connection: Python promote must fail with Online-specific message.
4. Self-host: sandbox → data or filesystem promote as appropriate.

## Rollback honesty

Snapshots cover views, automations, ACL, menus, reports. Dropped columns / data loss are only partially recoverable — UI must keep warning.
