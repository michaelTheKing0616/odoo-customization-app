# Wave 8 — PROD: production hardening (Document 1 remainders)

---

## PROD-1 — API Dockerfile + deploy profile

TASK: Containerize the API and provide a full-stack deploy compose profile.

INPUT: `apps/api/pyproject.toml`, uv workspace root, `docker/` stacks, `DEPLOY.md`,
`.env.example`.

CHECKLIST:
- [x] `apps/api/Dockerfile`: multi-stage (uv sync → slim runtime, non-root user, healthcheck
      hitting `/health`), workspace packages (odoo-client, module-generator) installed from
      the monorepo build context.
- [x] `apps/web/Dockerfile`: Next standalone build, non-root.
- [x] `docker/docker-compose.deploy.yml`: api + web + app-db (+ optional ollama service
      commented with hardware note); env-driven config; volumes for db; NOT touching the
      dev odoo stacks.
- [x] Sandbox-in-container note resolved: API in a container must still drive docker sandbox
      runs — document the docker-socket mount requirement + security note, gated by
      `SANDBOX_DOCKER_SOCKET` env (off default in deploy profile with honest limitation
      note).
- [x] `DEPLOY.md` updated: local prod-profile bring-up, Fly.io/Railway notes (per stack
      lock), secret handling (Fernet key, APP_API_KEY, admin bootstrap), backup note for
      app-db.
- [x] Gate: `docker compose -f docker/docker-compose.deploy.yml up` locally → health checks
      green, web talks to api, connect flow works against docker Odoo 19.

DONE MEANS: full stack boots from images locally; documented; dev stacks untouched.

DO NOT: modify dev compose files; bake secrets into images; add paid services.

GATE: compose boot test + smoke flow + `uv run pytest -q -m "not integration"` inside the
api image.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## PROD-2 — DB migration strategy + export README audit

TASK: Decide and implement schema-migration policy for the app DB; verify generated-module
README quality (Doc 1 Phase 8).

INPUT: `db.py` (init_db/create-all), `db_models.py`, Alembic docs, module-generator README
template.

CHECKLIST:
- [x] Decision implemented: adopt Alembic
- [x] CI-able check: drift test in pytest
- [x] Generated-module README audit + golden test
- [x] MEMORY.md entry: migration policy decision.

DONE MEANS: fresh DB + upgraded existing DB both reach head cleanly (tested); drift test
green; README golden test green.

DO NOT: rewrite existing table definitions; break test fixtures relying on create-all.

GATE: pytest incl. new drift test + alembic upgrade run on a copy DB.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## PROD-3 — Queue decision + job hardening

TASK: Decide arq vs in-process for background jobs; harden whichever is chosen.

INPUT: `jobs.py`, sandbox/export/health-check job usage, AGENTS.md stack lock (prefer lighter
solo stack), settings.

CHECKLIST:
- [x] Decision with rationale recorded in MEMORY.md (in-process v1 + JobRunner seam).
- [x] Hardening: interrupted on boot, timeouts, sandbox cancel hook, concurrent cap, logs.
- [x] Health-check job on same runner (ingest uses sync path; runner ready).
- [x] Tests: interrupted-job detection, cancel sandbox signal, concurrent cap.

DONE MEANS: restart mid-job yields visible interrupted status (not phantom running); cap +
timeout tests green; seam documented.

DO NOT: add Redis/arq unless the user overrides the recommendation (ask if in doubt —
that's a spend/infra decision).

GATE: pytest job suite + manual restart test recorded.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.
