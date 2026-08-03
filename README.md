# Odoo Customization App

External no-code customization platform for **Odoo Community 19** (Studio-class UX via public ORM/RPC — not Enterprise Studio).

Phases 0–7 are implemented: connections, models/fields, view designer, automations, module export, sandbox→promote, access rights, API auth/rate-limit/audit.

## Quick start

```bash
# 1. Local Odoo gate target + app metadata Postgres
docker compose -f docker/docker-compose.yml up -d
./docker/wait-for-odoo.sh
./docker/init-db.sh   # creates odoo_dev / admin:admin

# 2. Python workspace
uv sync
cp .env.example .env   # adjust FERNET_KEY / AUTH_MODE for non-local

# 3. Tests (unit — no live Odoo)
uv run --directory packages/odoo-client pytest -q tests/test_models.py tests/test_view_arch.py tests/test_automation_models.py
uv run --directory packages/module-generator pytest -q
uv run --directory apps/api pytest -q

# Optional integration against local Odoo 19
ODOO_URL=http://127.0.0.1:8069 ODOO_DB=odoo_dev ODOO_USER=admin ODOO_PASSWORD=admin \
  uv run --directory packages/odoo-client pytest -q -m integration
uv run --directory apps/api pytest -q -m integration

# 4. API (port 8000)
uv run --directory apps/api uvicorn app.main:app --reload --port 8000

# 5. Web (port 3000)
pnpm install
pnpm --filter @odoo-custom/web dev
# open http://localhost:3000/connect
```

Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` if needed.

**End-user guide (every screen & flow, non-developer):** [docs/USER-GUIDE.md](docs/USER-GUIDE.md).

**Full local UAT checklist** (wizard → Designer → sandbox → promote): [docs/LOCAL-UAT.md](docs/LOCAL-UAT.md).

### Expert RAG ingest (EXP-1 setup)

After Postgres is up, populate the version-tagged knowledge store (git sparse-checkout of
`odoo/documentation`; cache under `.cache/expert/`, gitignored):

```bash
uv run --directory apps/api python -m app.expert.ingest --version 19.0
uv run --directory apps/api python -m app.expert.ingest --version 18.0 --offline  # after first fetch
```

Optional: `EXPERT_COMMUNITY_SOURCE=dir` + `EXPERT_COMMUNITY_DIR=/path/to/qa` for curated Q&A markdown.
Place `docs/reference/MASTER_REFERENCE.md` when the 8-document master reference is available.

## Layout

- `apps/web` — Next.js UI
- `apps/api` — FastAPI
- `packages/odoo-client` — typed XML-RPC client (Odoo 19)
- `packages/module-generator` — Jinja2 → installable addon zip
- `docker/` — `odoo:19` + Postgres + sandbox compose
- `DEPLOY.md` — production checklist (`AUTH_MODE=api_key`, proxy, secrets)
- `docs/USER-GUIDE.md` — complete product guide for operators
- `docs/LOCAL-UAT.md` — step-by-step local test / UAT checklist
- `skills/studio-parity.md` — clean-room Studio capability targets
- `skills/module-interop.md` — extending stock/peer modules via depends + inherit
- `skills/library-app.md` — Library reference vertical operator guide

Engineering system: `AGENTS.md`, `RULES.md`, `PIPELINE.md`, `MEMORY.md`, `STATE.md`.

## Confirm phrase

Destructive / advanced actions require typed confirmation:

`I understand the risks`
