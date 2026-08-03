# Deploy checklist

Production / shared-host setup for the Odoo Customization API + web UI.

## Quick start — local prod profile (Docker)

From the repository root:

```bash
cp .env.example .env
# Edit .env: set a real FERNET_KEY and APP_API_KEY before any shared host.

docker compose -p odoo-custom-deploy -f docker/docker-compose.deploy.yml up --build
```

| Service | URL |
|---------|-----|
| Web UI | http://localhost:3000 |
| API health | http://localhost:8000/health |

Smoke checks:

1. `curl -fsS http://localhost:8000/health` → `"status":"ok"`, `"database_ok":true`
2. Open the web UI → Connect page loads and can reach the API (browser uses `NEXT_PUBLIC_API_URL`, default `http://127.0.0.1:8000`)
3. Point Connect at a running Odoo instance (local `docker compose -f docker/docker-compose.yml up` Odoo on `:8069` is fine)

The deploy profile starts **api + web + app-db** only. It does **not** replace the dev Odoo stacks under `docker/docker-compose.yml` / `docker-compose.odoo*.yml`.

### Env highlights (deploy profile)

| Var | Default in compose | Notes |
|-----|-------------------|-------|
| `FERNET_KEY` | dev placeholder | **Must** be a real Fernet key before shared use |
| `AUTH_MODE` | `api_key` | Set `off` only for local experiments |
| `APP_API_KEY` | `change-me-before-deploy` | Bearer / `X-API-Key` for the web + API |
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Browser-visible API origin |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Must include your web origin |
| `SANDBOX_DOCKER_SOCKET` | *(empty)* | Ephemeral sandbox disabled by default |

Back up the `deploy-app-db-data` volume before upgrades (app metadata, connections, audit rows — not customer Odoo DBs).

## LAUNCH-1 — Post-deploy smoke

After `docker compose … up` (or any deploy), run from the repo root:

```bash
chmod +x scripts/launch_smoke.sh
API_URL=http://127.0.0.1:8000 WEB_URL=http://127.0.0.1:3000 bash scripts/launch_smoke.sh
```

The script checks:

1. `GET /health` — API + database connectivity
2. `GET /api/billing/plans` — public billing registry (no auth)
3. Web `/pricing` and `/` — HTTP 200

Exit code is non-zero on any failure (CI-friendly). When the stack is not running, skip or expect failure — do not treat as a code defect.

### Accounts + billing env (Wave 9)

| Var | Notes |
|-----|-------|
| `AUTH_MODE` | `accounts` for SaaS; `api_key` for programmatic-only deploys |
| `APP_ADMIN_EMAIL` / `APP_ADMIN_PASSWORD` | Bootstrap superadmin once (never commit) |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Optional until live checkout; test keys for checkout smoke |
| `PAYSTACK_SECRET_KEY` | Optional NGN path |
| `BUSINESS_TRIAL_ENABLED` | Default `true` — 14-day business trial on new workspaces |
| Alembic | Run migrations before first traffic: `uv run alembic upgrade head` in `apps/api` |

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

## Container images

| Image | Dockerfile | Notes |
|-------|------------|-------|
| API | `apps/api/Dockerfile` | uv workspace sync; non-root `appuser`; healthcheck on `/health` |
| Web | `apps/web/Dockerfile` | Next.js `standalone` output; non-root `webuser` |

Build context is always the **repository root** (monorepo packages `odoo-client`, `module-generator`).

## Sandbox from a containerized API

Ephemeral module validation uses `docker compose` against `docker/docker-compose.sandbox.yml` on the **host** (port **18069**).

**Default (deploy profile):** `SANDBOX_DOCKER_SOCKET` is unset → sandbox runs return an honest error. Promote flows that require sandbox validation must run the API on the host, or enable Docker socket access deliberately.

**To enable from the API container** (security tradeoff — API can control host Docker):

1. Uncomment the socket volume in `docker/docker-compose.deploy.yml`:
   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock
   ```
2. Set `SANDBOX_DOCKER_SOCKET=/var/run/docker.sock`.
3. Ensure the API image can reach the host Docker daemon (Linux: socket mount; macOS Docker Desktop: same mount path inside the VM).

Only enable on trusted single-operator hosts. Never expose the API with an open Docker socket to the public internet.

Host-native API (no container) continues to use the local `docker` CLI without `SANDBOX_DOCKER_SOCKET`.

## Optional Ollama (local LLM)

The deploy compose file includes a **commented** `ollama` service. Uncomment only when the host has enough RAM/GPU, then set:

```
AI_ASSIST=ollama
OLLAMA_BASE_URL=http://ollama:11434
```

Pull a model inside the container: `docker exec -it odoo-custom-deploy-ollama ollama pull qwen2.5:7b-instruct-q4_K_M`

## Fly.io / Railway (later)

Per stack lock — no paid SaaS until paying users. Suggested split:

| Component | Fly.io | Railway |
|-----------|--------|---------|
| API | `fly launch` from `apps/api/Dockerfile` context = repo root | Dockerfile service |
| Web | separate app; set `NEXT_PUBLIC_API_URL` to public API URL | same |
| app-db | Fly Postgres or attached volume | Railway Postgres plugin |

Secrets: `FERNET_KEY`, `APP_API_KEY`, `DATABASE_URL` via platform secret stores — never bake into images.

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

## Sandbox / promote (host API or enabled socket)

- Sandbox uses Docker compose project `odoo-sandbox` on host port **18069** (image `odoo:{16|17|18|19}` from connection major). Never `down -v` without `-p odoo-sandbox`. Port **8070** is reserved for the permanent Odoo 18 stack.
- Long runs: `POST .../sandbox/run` with `"async_job": true`, then poll `GET /api/jobs/{id}`.
- Promote still requires sandbox validation (or `run_sandbox=true`) + confirm phrase `I understand the risks`.

## Health

`GET /health` reports `database_ok` and warns when `AUTH_MODE` is off.

## In-container test gate

After building the API image:

```bash
docker compose -f docker/docker-compose.deploy.yml build api
docker compose -f docker/docker-compose.deploy.yml run --rm api \
  pytest -q -m "not integration"
```

(Requires the deploy stack's app-db or `DATABASE_URL` pointing at a reachable Postgres.)
