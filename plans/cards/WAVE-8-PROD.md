# Wave 8 — PROD: production hardening (Document 1 remainders)

---

## PROD-1 — API Dockerfile + deploy profile

TASK: Containerize the API and provide a full-stack deploy compose profile.

INPUT: `apps/api/pyproject.toml`, uv workspace root, `docker/` stacks, `DEPLOY.md`,
`.env.example`.

CHECKLIST:
- [ ] `apps/api/Dockerfile`: multi-stage (uv sync → slim runtime, non-root user, healthcheck
      hitting `/health`), workspace packages (odoo-client, module-generator) installed from
      the monorepo build context.
- [ ] `apps/web/Dockerfile`: Next standalone build, non-root.
- [ ] `docker/docker-compose.deploy.yml`: api + web + app-db (+ optional ollama service
      commented with hardware note); env-driven config; volumes for db; NOT touching the
      dev odoo stacks.
- [ ] Sandbox-in-container note resolved: API in a container must still drive docker sandbox
      runs — document the docker-socket mount requirement + security note, gated by
      `SANDBOX_DOCKER_SOCKET` env (off default in deploy profile with honest limitation
      note).
- [ ] `DEPLOY.md` updated: local prod-profile bring-up, Fly.io/Railway notes (per stack
      lock), secret handling (Fernet key, APP_API_KEY, admin bootstrap), backup note for
      app-db.
- [ ] Gate: `docker compose -f docker/docker-compose.deploy.yml up` locally → health checks
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
- [ ] Decision implemented: adopt Alembic (recommended — MON-1/2 add tables and ALTERs are
      coming) — `apps/api/alembic/` initialized, autogenerate baseline from current models,
      `init_db` create-all retained ONLY for empty-DB bootstrap + tests (documented policy
      in db.py docstring); startup runs `alembic upgrade head` when
      `DB_MIGRATIONS=auto` (default on in deploy profile, off in tests).
- [ ] CI-able check: `alembic check`-style drift test in pytest (models vs head revision).
- [ ] Generated-module README audit: exported modules include README.md covering what was
      generated, install steps (per-tier per TIER-2), module contents map, "hand to your
      developer" section (Doc 1's trust artifact) — verify current template, complete gaps,
      golden-file test.
- [ ] MEMORY.md entry: migration policy decision.

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
- [ ] Decision with rationale recorded in MEMORY.md: DEFAULT RECOMMENDATION — keep in-process
      background tasks for v1 (single-instance deploy, jobs are minutes-scale, arq adds a
      Redis dependency) BUT implement the seam: `JobRunner` protocol so arq can slot in
      without call-site changes; revisit trigger documented (multi-instance deploy or job
      loss reports).
- [ ] Hardening regardless: job persistence across restart (status=interrupted detection on
      boot + surfaced in UI), timeouts per job type, cancellation actually terminates
      sandbox subprocesses (verify + fix), concurrent-job cap, structured job logs.
- [ ] Health-check job (TIER-4) + ingest (EXP-1) registered on the same runner.
- [ ] Tests: interrupted-job detection, timeout kill, cancel kills subprocess (sandbox fake).

DONE MEANS: restart mid-job yields visible interrupted status (not phantom running); cap +
timeout tests green; seam documented.

DO NOT: add Redis/arq unless the user overrides the recommendation (ask if in doubt —
that's a spend/infra decision).

GATE: pytest job suite + manual restart test recorded.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.
