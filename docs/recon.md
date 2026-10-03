# Repository recon (one page)

Tags: **`[verified]`** = checked against this repo or cited project docs; **`[unverified]`** = open decision, external environment, or not re-validated here. No secrets. No claim that any customer production Odoo database was inspected.

---

## What this is

- **`[verified]`** Monorepo for a **no-code Odoo Community customization platform** (Studio-like UX via public ORM/RPC, not Enterprise Studio)—see root `README.md` and `AGENTS.md`.
- **`[verified]`** **`apps/api`**: FastAPI backend (connections, customization, jobs, audit middleware, AI/draft paths, auth).
- **`[verified]`** **`apps/web`**: Next.js frontend (`pnpm` workspace; dev entry documented in `README.md`).
- **`[verified]`** **`packages/odoo-client`**: Shared Python Odoo client (XML-RPC and JSON-2 transport code under `packages/odoo-client/src/odoo_client/`).
- **`[verified]`** Additional packages exist (e.g. module generator) per repo layout in `AGENTS.md` / `README.md`.

## Auth and API surface

- **`[verified]`** App API auth modes include **`AUTH_MODE=off`** for local gates and API-key mode documented in `AGENTS.md` (`Authorization: Bearer …` / `X-API-Key`).
- **`[verified]`** Self-hosted identity uses **Authlib** for OAuth (Google, Microsoft Entra, GitHub) in `apps/api/app/oauth_service.py` (`authlib` dependency in `apps/api/pyproject.toml`).
- **`[verified]`** **TOTP** second step is implemented (`totp_enabled`, `pyotp`, pending token flow in `oauth_service.py` / accounts router)—not a third-party IdP SaaS requirement for core login.
- **`[unverified]`** Hardened production auth configuration (rotated keys, `AUTH_MODE=api_key` on shared hosts) depends on operator env—not audited in this note.

## Sandbox and Odoo targets

- **`[verified]`** Local **Docker Compose** stacks live under `docker/` (primary gate + `docker-compose.sandbox.yml`; odoo 16–18 compose files present).
- **`[verified]`** README quick start: compose up, init DB, pytest unit vs optional `-m integration` against local Odoo 19.
- **`[unverified]`** Odoo **20** compose stack and adapter parity (D11)—specified as GA in `MEMORY.md`, not present as `docker-compose.odoo20.yml` in repo.

## Transport notes (JSON-2)

- **`[verified]`** JSON-2 client code exists (`packages/odoo-client/src/odoo_client/transport/json2.py`).
- **`[verified]`** `STATE.md` (2026-10-02): local tip **`/doc` → 404**; XML-RPC password login ok; Bearer without API key → 401.
- **`[unverified]`** Live Online `/doc` + API-key JSON-2 smoke still operator-owned per `STATE.md`.

## Planning / open tails (from STATE & next-phase pack)

- **`[verified]`** **D8 (AI gateway)**: thin in-house vs LiteLLM—**open**; ADR-02; work cards stop at documentation until accepted (`docs/plans/next-phase/01_LOCKS_DECISIONS_CONFLICTS.md`, `18_OPEN_QUESTIONS.md`).
- **`[verified]`** **L4 autonomy**: D10 decided in phase pack; **numeric thresholds** (e.g. 200 L3 applies, 60 days, rollback rate) written in locks doc but **`[unverified]`** as “confirmed before L4 turn-on” per `MEMORY.md` / `STATE.md` (“GATE-L4 numeric confirm” still open).
- **`[verified]`** **Mac §9**: agent sandbox/offline evidence exists; **UI paste of Studio Generate scorecards into DOCKET remains operator**—`STATE.md` explicitly says agent cannot claim §9 done.
- **`[verified]`** **Audit hash chain**: specified in `docs/plans/next-phase/11_LOGGING_AUDIT_OBSERVABILITY.md`; current `audit_logs` is HTTP mutating-request log without hash chain (**implementation `[unverified]`** relative to that spec).
- **`[unverified]`** Pen-test and full next-phase build cards (BL-01 onward in `14_WORK_CARDS.md`) completion state beyond what `STATE.md` lists as closed (D1–D7, D9–D12).

## Operator constraints echoed here

- **`[verified]`** Local API on **`:8001`** is often run **without `--reload`** per `AGENTS.md` / `STATE.md`—code changes need process restart to pick up routing fixes.
- **`[verified]`** Customization path stays **public ORM/RPC**; Enterprise Studio source is out of scope per `AGENTS.md`.

---

*Generated for internal recon; refresh tags after code or STATE changes.*
