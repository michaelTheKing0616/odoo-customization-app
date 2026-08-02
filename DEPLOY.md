# Deploy checklist

Production / shared-host setup for the Odoo Customization API + web UI.

## Required before exposing the API

1. Set a real Fernet key (never `dev-only-*` outside local):
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
2. Set `AUTH_MODE=api_key` and either `APP_API_KEY=…` or bootstrap via `/api/auth/bootstrap`.
3. Point `DATABASE_URL` at the app metadata Postgres (not the Odoo DB).
4. Restrict `CORS_ORIGINS` to your web origin(s).
5. Put the API behind a reverse proxy (Caddy/nginx) with TLS.
6. If the proxy sets `X-Forwarded-For`, set `TRUSTED_PROXY=true` so rate limit + audit use the real client IP. Leave `false` when the API is reachable directly (prevents spoofing).

## Recommended env

See root `.env.example`. Highlights:

| Var | Prod value |
|-----|------------|
| `AUTH_MODE` | `api_key` |
| `FERNET_KEY` | real Fernet key |
| `TRUSTED_PROXY` | `true` behind proxy |
| `RATE_LIMIT_PER_MINUTE` | `60`–`120` |
| `AUDIT_LOG_ENABLED` | `true` |
| `AUDIT_RETENTION_DAYS` | `90` (purge via `POST /api/audit/purge`) |

## Operator model

v1 is single-operator: **every valid API key can see every connection**. Do not share keys across tenants. Store browser keys carefully (`localStorage` is XSS-sensitive — prefer a hardened host and short-lived keys).

## Sandbox / promote

- Sandbox uses Docker compose project `odoo-sandbox` on host port **18069** (image `odoo:{16|17|18|19}` from connection major). Never `down -v` without `-p odoo-sandbox`. Port **8070** is reserved for the permanent Odoo 18 stack.
- Long runs: `POST .../sandbox/run` with `"async_job": true`, then poll `GET /api/jobs/{id}`.
- Promote still requires sandbox validation (or `run_sandbox=true`) + confirm phrase `I understand the risks`.

## Health

`GET /health` reports `database_ok` and warns when `AUTH_MODE` is off.
