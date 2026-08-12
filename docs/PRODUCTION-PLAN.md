# Production migration plan — Odoo Customization Platform

> **Goal:** Run the full product (web + API + app Postgres + Expert RAG + optional sandbox)
> on a public host — not tied to `localhost`, your laptop, or Docker Desktop quirks.
>
> **Constraints (from AGENTS.md / MEMORY.md):** Prefer Fly.io or Railway; no paid SaaS
> dependencies until paying users; Community Odoo 19/18/17 GA; sandbox before prod module
> install; TRUST-9 beta gating still applies until GA unlock.

---

## Recommended path (best cost / complexity balance)

**Single VPS + Docker Compose + Caddy TLS** for the first production host.

| Why | Detail |
|-----|--------|
| **Cost** | ~€6–12/mo (Hetzner CX22, DO Basic) vs $40–80/mo managed PaaS for same stack |
| **Already built** | `docker/docker-compose.deploy.yml` + Dockerfiles + Alembic `DB_MIGRATIONS=auto` |
| **Sandbox option** | Mount Docker socket on VPS only (you control the host; not multi-tenant SaaS) |
| **Expert / RAG** | Persistent volume for `.cache/expert` + one-time ingest job |
| **LLM** | Start with **Groq / OpenAI-compatible** (no GPU on small VPS); add Ollama sidecar later |

Move to **Fly.io / Railway** when you want zero server ops or a second region — same
images, different orchestration.

---

## Target architecture (production)

```
                    Internet
                       │
                       ▼
              ┌─────────────────┐
              │  Caddy / nginx  │  TLS (Let's Encrypt)
              │  app.example.com│
              └────────┬────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
  ┌─────────────┐            ┌─────────────┐
  │  web :3000  │  proxy     │  api :8000  │
  │  Next.js    │───────────▶│  FastAPI    │
  └─────────────┘  /api/*     └──────┬──────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
             ┌──────────┐    ┌────────────┐   ┌───────────────┐
             │ app-db   │    │ LLM API    │   │ Customer Odoo │
             │ Postgres │    │ (Groq/etc) │   │ (outbound RPC)│
             └──────────┘    └────────────┘   └───────────────┘

Optional (VPS with Docker socket):
  api ──▶ docker compose (odoo-sandbox) ──▶ ephemeral Odoo :18069

NOT on production app host:
  - Dev Odoo gate :8069 (keep on laptop or separate “dev” VPS)
  - Expert git caches can live on volume; re-fetch on upgrade
```

---

## Deployment options compared

| Option | Monthly cost (solo) | Ops effort | Sandbox promote | Best for |
|--------|---------------------|------------|-----------------|----------|
| **A. VPS + Compose** | $6–15 | Medium | Yes (socket mount) | **Recommended first prod** |
| **B. Railway** | $20–50 | Low | Hard (no DinD) | Fastest “it’s online” |
| **C. Fly.io** | $15–40 | Medium | Hard | Global edge, scale later |
| **D. Split: Vercel web + Fly API** | $20–35 | Medium | API on Fly only | If Next.js edge matters |

**Recommendation:** **Option A** until first paying customers; revisit **B/C** when ops time
exceeds ~2h/month.

---

## Phase 0 — Pre-flight (local, 1–2 hours)

Fix / verify before paying for a server.

### 0.1 Secrets

```bash
cd /path/to/Odoo_Customization_App
cp .env.example .env

# Fernet (encrypts Odoo connection passwords in app DB)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Strong API key (if AUTH_MODE=api_key)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set in `.env`:

```env
FERNET_KEY=<generated>
AUTH_MODE=api_key
APP_API_KEY=<generated>
APP_PUBLIC_URL=https://app.yourdomain.com
SESSION_COOKIE_SECURE=true
TRUSTED_PROXY=true
DB_MIGRATIONS=auto
CORS_ORIGINS=https://app.yourdomain.com
NEXT_PUBLIC_API_URL=https://app.yourdomain.com
API_PROXY_TARGET=http://api:8000
```

### 0.2 Validate deploy profile locally

```bash
docker compose -p odoo-custom-deploy -f docker/docker-compose.deploy.yml up --build -d

API_URL=http://127.0.0.1:8000 WEB_URL=http://127.0.0.1:3000 bash scripts/launch_smoke.sh
```

### 0.3 Expert RAG — image + ingest (required for Expert quality)

The API Dockerfile currently runs `uv sync` **without** `--extra ai-rag`. For production:

1. Rebuild API with ai-rag (see Phase 2 patch below).
2. Run ingest once against production `DATABASE_URL`.

```bash
cd apps/api
uv sync --extra ai-rag
export AI_RAG=on EXPERT_ODOO_SOURCE=on
for v in 16.0 17.0 18.0 19.0; do
  uv run python -m app.expert.ingest --version "$v" --offline
done
```

---

## Phase 1 — VPS provision (day 1)

### 1.1 Server spec (minimum)

| Resource | Minimum | Comfortable |
|----------|---------|-------------|
| RAM | 4 GB | 8 GB (Ollama sidecar) |
| CPU | 2 vCPU | 4 vCPU |
| Disk | 40 GB SSD | 80 GB (Expert caches + logs) |
| OS | Ubuntu 24.04 LTS | same |

Providers: Hetzner CX22, DigitalOcean Basic, Linode, Vultr.

### 1.2 Bootstrap server

```bash
# On the VPS (as root or sudo user)
apt update && apt upgrade -y
apt install -y git docker.io docker-compose-plugin curl

# Deploy user
adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy
su - deploy
```

### 1.3 DNS

| Record | Value |
|--------|-------|
| `A` `app.yourdomain.com` | VPS public IP |
| Optional `api.yourdomain.com` | same IP (or path-only routing via Caddy) |

---

## Phase 2 — Deploy stack on VPS (day 1–2)

### 2.1 Clone and configure

```bash
su - deploy
git clone https://github.com/YOUR_ORG/Odoo_Customization_App.git
cd Odoo_Customization_App
cp .env.example .env
# Edit .env with production values (Phase 0.1)
nano .env
```

### 2.2 Caddy (TLS reverse proxy)

Create `/home/deploy/Caddyfile`:

```caddy
app.yourdomain.com {
    reverse_proxy /api/* 127.0.0.1:8000
    reverse_proxy /*      127.0.0.1:3000
}
```

Run Caddy (Docker):

```bash
docker run -d --name caddy --restart unless-stopped \
  -p 80:80 -p 443:443 \
  -v $HOME/Caddyfile:/etc/caddy/Caddyfile \
  -v caddy_data:/data \
  caddy:2-alpine
```

Browser uses **same origin** (`https://app.yourdomain.com/api/...`) — set
`NEXT_PUBLIC_API_URL=https://app.yourdomain.com` and `CORS_ORIGINS` to match.

### 2.3 Start application stack

```bash
cd ~/Odoo_Customization_App
docker compose -p odoo-custom-deploy -f docker/docker-compose.deploy.yml up --build -d
docker compose -p odoo-custom-deploy -f docker/docker-compose.deploy.yml ps
curl -fsS http://127.0.0.1:8000/health | python3 -m json.tool
```

### 2.4 Expert RAG ingest on server

```bash
cd ~/Odoo_Customization_App/apps/api

# One-time: clone odoo docs + odoo source caches (online, ~10–20 min)
for v in 16.0 17.0 18.0 19.0; do
  docker compose -p odoo-custom-deploy -f ../../docker/docker-compose.deploy.yml \
    run --rm -e AI_RAG=on -e EXPERT_ODOO_SOURCE=on api \
    python -m app.expert.ingest --version "$v"
done
```

Persist `.cache/expert` on a volume (add to compose in a follow-up PR) so re-ingest
is incremental.

### 2.5 LLM for production (pick one)

**A. Groq / OpenAI-compatible (recommended on 4 GB VPS — no GPU):**

```env
AI_ASSIST=openai-compatible
OPENAI_COMPATIBLE_BASE_URL=https://api.groq.com/openai/v1
OPENAI_COMPATIBLE_API_KEY=gsk_...
OPENAI_COMPATIBLE_MODEL=llama-3.3-70b-versatile
```

**B. Ollama sidecar (8 GB+ RAM):** uncomment `ollama` in `docker-compose.deploy.yml`,
set `OLLAMA_BASE_URL=http://ollama:11434`, pull a small model.

---

## Phase 3 — Odoo Expert Bridge + connections (day 2)

Customer Odoo instances call **your** public URLs.

### 3.1 Install bridge on customer/sandbox Odoo

```bash
# From repo on server or laptop
./docker/install-expert-bridge.sh
# Or copy packages/odoo-expert-bridge to Odoo addons path
```

### 3.2 Odoo system parameters (per database)

| Parameter | Value |
|-----------|-------|
| `expert_bridge.base_url` | `https://app.yourdomain.com` |
| `expert_bridge.api_base_url` | `https://app.yourdomain.com` |
| `expert_bridge.connection_id` | UUID from Connect wizard |

Odoo server must reach `https://app.yourdomain.com/api/...` (outbound HTTPS).

### 3.3 Connect wizard

1. Open `https://app.yourdomain.com`
2. Add connection → Odoo URL (customer’s public Odoo or your dev `:8069` via tunnel)
3. Store API key / Odoo credentials (encrypted with `FERNET_KEY`)

---

## Phase 4 — Sandbox on production (optional, day 3)

**Default:** sandbox **disabled** in deploy profile (safe).

**Enable on trusted single-operator VPS:**

1. Uncomment Docker socket mount in `docker-compose.deploy.yml`.
2. Set `SANDBOX_DOCKER_SOCKET=/var/run/docker.sock`.
3. Ensure port **18069** is firewalled (localhost only — not public).

```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
# Do NOT expose 18069 publicly
```

**Alternative without socket:** run API **natively** on host with `docker` CLI; keep
web+db in compose — hybrid layout from DEPLOY.md.

---

## Phase 5 — Backups, monitoring, CI (week 1)

### 5.1 Postgres backup (daily)

```bash
# cron on VPS
0 3 * * * docker exec odoo-custom-deploy-app-db pg_dump -U odoo_custom odoo_custom | gzip > /backups/app-$(date +\%F).sql.gz
```

Back up: connections, Expert chunks, snapshots, audit — **not** customer Odoo DBs.

### 5.2 Health monitoring

```bash
# External uptime (UptimeRobot free) → GET https://app.yourdomain.com/api/health
# Alert if database_ok != true or status != ok
```

### 5.3 CI → deploy (later)

Add `.github/workflows/deploy.yml`:

1. Build + push images to GHCR on `main`.
2. SSH to VPS `docker compose pull && up -d` (or Watchtower).

Not required for first launch — manual deploy is fine.

---

## Known gaps to close in codebase (prioritized)

| # | Gap | Fix | Phase |
|---|-----|-----|-------|
| 1 | API image lacks `ai-rag` | `uv sync --extra ai-rag` in Dockerfile | 0 |
| 2 | `AUTH_MODE=off` default in compose | Default `api_key`; fail health if off in prod | 0 |
| 3 | Expert ingest not on startup | One-shot job + persistent `.cache/expert` volume | 2 |
| 4 | Sandbox hardcoded `127.0.0.1:18069` | Configurable `SANDBOX_BASE_URL` | 4 |
| 5 | Dev port 8001 vs prod 8000 | Document only; proxy uses `API_PROXY_TARGET` | 0 |
| 6 | In-process jobs (no Redis) | Accept single-instance until scale | 5+ |
| 7 | `/api/billing/plans` 404 on deploy image | Fix route registration (LAUNCH-1) | 0 |
| 8 | TRUST-9 beta gating | Set `PRODUCTION_WRITE_MODE_GA_UNLOCKED` when ready | launch |
| 9 | Multi-tenant isolation | Not v1 — single operator per deploy | — |

---

## Cost model (monthly, solo operator)

| Item | Low | Notes |
|------|-----|-------|
| VPS 4 GB | $6–12 | Hetzner / DO |
| Domain | ~$1 | amortized |
| Managed Postgres | $0 | use compose `app-db` on same VPS |
| LLM (Groq free/low) | $0–5 | pay per token at scale |
| TLS (Caddy) | $0 | Let's Encrypt |
| Backups (S3 optional) | $0–2 | B2 / R2 |
| **Total** | **~$8–20/mo** | before customer revenue |

Railway/Fly equivalent: **~$25–50/mo** for less ops.

---

## Migration checklist (copy-paste)

```bash
# === LOCAL VALIDATION ===
cd /path/to/Odoo_Customization_App
cp .env.example .env   # fill secrets
docker compose -p odoo-custom-deploy -f docker/docker-compose.deploy.yml up --build -d
API_URL=http://127.0.0.1:8000 WEB_URL=http://127.0.0.1:3000 bash scripts/launch_smoke.sh

# === VPS DEPLOY ===
ssh deploy@YOUR_VPS
git clone YOUR_REPO && cd Odoo_Customization_App
cp .env.example .env && nano .env
docker compose -p odoo-custom-deploy -f docker/docker-compose.deploy.yml up --build -d

# === POST-DEPLOY ===
curl -fsS https://app.yourdomain.com/api/health
# Expert ingest (once)
docker compose -p odoo-custom-deploy -f docker/docker-compose.deploy.yml run --rm api \
  python -m app.expert.ingest --version 19.0

# === SMOKE ===
API_URL=https://app.yourdomain.com WEB_URL=https://app.yourdomain.com bash scripts/launch_smoke.sh
```

---

## What works remotely without changes

- Outbound Odoo RPC to customer URLs (Online, Odoo.sh, self-hosted)
- Connection wizard, Designer, metadata writes (with auth + write mode)
- Expert ask (with LLM + ingested RAG chunks)
- Module export zip download
- Encrypted credentials at rest (`FERNET_KEY`)

## What needs explicit production config

- Public `APP_PUBLIC_URL` / Expert bridge params
- `AUTH_MODE` not `off`
- LLM provider reachable from API container
- Expert RAG ingested into app Postgres
- CORS / cookies / TLS aligned on one public origin

## What is intentionally limited in v1

- Single-operator API keys (all connections visible)
- Sandbox from container requires Docker socket (security tradeoff)
- No horizontal scale (in-process job queue)
- Beta production write gating until GA unlock

---

## Next implementation tasks (repo work)

1. **Dockerfile:** add `--extra ai-rag` to API build.
2. **Compose:** volume for `/workspace/.cache/expert`; optional ingest init container.
3. **Compose:** default `AUTH_MODE=api_key`; require `APP_API_KEY` not placeholder.
4. **Settings:** `SANDBOX_PUBLIC_URL` env for non-local sandbox links.
5. **CI:** optional `deploy.yml` + GHCR push.
6. **Fix:** billing plans route on deploy image.

Track progress in `STATE.md` after each phase ships.
