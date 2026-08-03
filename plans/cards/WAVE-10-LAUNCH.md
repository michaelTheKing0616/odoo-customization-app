# Wave 10 — LAUNCH: deploy verification and operator readiness

Post-monetization launch gate. Wave 9 MON must be complete.

---

## LAUNCH-1 — Deploy smoke + operator checklist

TASK: Verify deploy profile and document operator smoke path.

INPUT: `DEPLOY.md`, `docker/docker-compose.deploy.yml`, `scripts/launch_smoke.sh`.

CHECKLIST:
- [x] `scripts/launch_smoke.sh` — curls API health, public billing plans, web `/pricing` + landing (no auth).
- [x] `DEPLOY.md` — LAUNCH-1 section: run smoke after deploy, env checklist (AUTH_MODE, DB_MIGRATIONS, billing keys optional).
- [x] CI-friendly: script exits non-zero on failure.

DONE MEANS: operator can run one script after deploy to confirm API + web surfaces respond.

GATE: `bash scripts/launch_smoke.sh` (with stack up) or documented skip when stack down.

---

## LAUNCH-2 — Operator runbook (deferred)

TASK: Single-page runbook: bootstrap admin, grant internal plan, rotate keys.

INPUT: MON-3 bootstrap, admin console.

CHECKLIST:
- [x] `docs/OPERATOR.md` — bootstrap, superadmin, grant-plan for testers, never commit secrets.

DONE MEANS: new operator can onboard without reading entire MASTER_PLAN.

GATE: doc review only.
