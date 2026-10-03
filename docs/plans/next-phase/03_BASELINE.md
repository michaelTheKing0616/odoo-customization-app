# Baseline measured 2026-10-02

**Read §B first.** §A (the tables below §B) was written earlier the same day, before a concurrent build agent landed a large uncommitted slice. Where §A and §B disagree, §B wins. Re-verify with card BL-01 before writing feature code.

## §B — Re-measure (2026-10-02, later the same day)

**The working tree is mostly uncommitted.** `git status` shows 81 modified tracked files, plus untracked modules, migrations, and tests. That includes code §A lists as "exists" (`ai_generate_ir*.py`, `ai_schema_client.py`, `client_access.py`). Nothing below is safe until card BL-08 (commit hygiene, Tope's explicit yes) lands. A builder must not `git clean`, `git checkout .`, or `git stash` this tree.

| Area | Measured | Command |
|---|---|---|
| Routers | 51 files in `apps/api/app/routers/` (new: `bridge.py`, `inbox.py`) | `ls apps/api/app/routers/*.py \| rg -v __init__ \| wc -l` |
| Migrations | 25 files. Head is `r8s9t0u1v2w3` (idempotency_keys), which revises `q7r8s9t0u1v2` (plan_cards). Untracked migrations: `m3n4…` connection_access_grants, `n4o5…` audit_chain, `o5p6…` audit_chain canonical ts, `p6q7…` bridge connections queue, `q7r8…` plan_cards, `r8s9…` idempotency_keys | `rg -l "down_revision.*<rev>"` |
| API tests | 350 `test_*.py`; 48 untracked. The untracked set passed 256 and failed 1 (`test_no_mcp_write.py` scans `.pytest_cache`, card BL-07) | API pytest |
| New API modules (untracked) | `changeset/`, `llm_gateway/`, `agent_runtime/`, `bots/`, `worker_bot/`, `bridge/`, `config_as_code/`, `odoo20/`, `offline/`, `skills/`, `progress/`, `audit_chain.py`, `rpc_classify.py`, `rpc_guard.py`, `mcp_guard.py`, `dry_run_ledger.py`, `dry_run_middleware.py`, `plan_fingerprint.py`, `snapshot_gate.py`, `request_id.py`, `logging_config.py` | `git status --short apps` |
| Still missing | `apps/api/app/evals/` (eval harness), automation/security v20 adapters, verify endpoint or CLI for the audit chain, bot roster/rooms/routines, Dashboard Studio | `ls` |
| odoo-client (untracked) | `env_profile.py`, `schema_graph.py`, `schema_fingerprint.py`, `read_plane.py`, `rpc_policy.py`, `transport/`, `compat/version_table.py` (19 of the 32 rows in `cards/T9_ODOO20.md`), `compat/adapters/views_v20.py`; tests `test_json2_transport`, `test_odoo20_version_table`, `test_read_plane`, `test_registry_odoo20`, `test_rpc_policy`, `test_schema_graph` | `git status --short packages` |
| Docker | `docker/docker-compose.odoo20.yml` (port 8073) and `docker/run-odoo20-smoke.sh` exist, untracked. The major gate script still rejects 20 | `ls docker` |
| Op catalog | `OP_CATALOG` has 62 ops and matches the six family tables in `cards/T8_ENGINE_CORE.md` exactly. `user.unlink` is never-allowed and is not in either. An earlier same-day count of 63 included an `rpc.write` entry that has since been removed. The brief's "about 55" is superseded by the counted 62 | `python -c "from app.changeset.ops import OP_CATALOG; print(len(OP_CATALOG))"` (from `apps/api`) |
| Skills | 188 skill stubs exist | `ls apps/api/app/skills` |
| Web | 70 `page.tsx`. Root and `connections/[id]/` `loading`, `error`, `not-found` exist (untracked) plus `states.test.tsx`. `AppToaster.tsx` (Sonner) is mounted in `layout.tsx`; the old `Toast.tsx` is still used by 3 files. `MotionProvider.tsx` uses `motion/react`. Radix is still imported by 5 files: `Button` (Slot), `Tabs`, `Sheet`, `Dialog`, `Tooltip`. New pages: `/approvals` (98 lines), `/command` (34), `/bridge/contracts/new` (123). EmptyState or Skeleton is used on 5 of 70 pages. `typecheck` reports 13 pre-existing errors | `rg -l "@radix-ui" apps/web/src` |
| Lint slot | `BL04_LINT_SLOT.md`, `apps/api/scripts/lint_new_modules.sh`: BL-04 is in progress by another builder | — |

Rows in §A's "Missing" list that are now at least seeded: `classify_rpc`, the never-allowed list, request ids, JSON logs, the `tsc` script, the Odoo 20 compose file, `motion/react`, Sonner, and the shared loading/error/not-found files. The card statuses in `14` reflect §B.

## §A — First measure (earlier 2026-10-02) Paths are relative to the repo root. Status is exists / partial / missing against this pack, not against a wish list.

## What exists

| Area | Evidence |
|---|---|
| API surface | 49 routers under `apps/api/app/routers/`, about 468 unique method+path pairs, prefix `/api`. `GET /health` in `apps/api/app/main.py` |
| Tables | 49 SQLAlchemy tables: 30 in `db_models.py`, 12 in `account_models.py`, 7 in `billing_models.py` |
| Migrations | 20 Alembic files. Head `m3n4o5p6q7r8` (`connection_access_grants`, revises `l2m3n4o5p6q7`) |
| Odoo client | `packages/odoo-client`: XML-RPC primary, legacy JSON-RPC fallback, JSON-2 in `transport/json2.py`. Registry majors 16–19. ≤15 raises `UnsupportedOdooMajorError`. Sandbox forces XML-RPC |
| Schema client | `apps/api/app/ai_schema_client.py`: `LiveSchemaClient._fg_cache`, `SCHEMA_CATALOG_TTL_S = 15*60`, deny-on-stale. Not a package-level TTL service |
| GenerateIR | `ai_generate_ir.py` (`GenerateIR`, `admit_and_apply`), enforce + lint modules, tests `test_generate_ir_*` |
| Job Autopilot | `app/job_autopilot/*`, router, web `/connections/[id]/job` |
| Snapshots | `metadata_snapshots`, `routers/snapshots.py`: list, rollback, artifact download |
| Accounts | Signup, sessions, OAuth Google/GitHub/Microsoft, TOTP (`pyotp`), recovery codes |
| Client Approver | `connection_access_grants`, `client_access.py`, `POST /api/accounts/connection-grants`, `tests/test_client_approver_isolation.py` |
| Prove | `ai_option_a_quality.py`, sandbox `run_tests`, module spec prove defaults `run_tests=True` (D2) |
| Docker | `docker-compose.yml` Odoo 19 :8069; 18 :8070; 17 :8071; 16 :8072; sandbox :18069; deploy API :8000 web :3000. No Odoo 20 file yet |
| Tests | 314 `apps/api/tests/test_*.py`; 37 package tests (28 odoo-client, 9 module-generator); ~156 Vitest; 24 Playwright specs. CI: `.github/workflows/ci.yml`, `odoo-sandbox.yml` |
| Web | Next.js 15.5 App Router, React 19, Tailwind v4 tokens in `apps/web/src/app/globals.css` (no `tailwind.config`). Radix dialog/tabs/tooltip, cmdk, lucide. No framer-motion. No product i18n. Dark mode via `html.dark` |
| Approvals today | Connection-scoped rules and entries in `routers/approvals.py` and `/connections/[id]/approvals`. These are Odoo approval processes, not the hash-bound plan card |

## Partial

| Concept | What exists | What is missing |
|---|---|---|
| Dry-run hash | `dry_run_receipts.params_hash` for trust bulk; Job Autopilot instance fingerprint | Track 5 plan hash bound to approvals, 16 hex chars, `res_id` excluded, re-plan on apply |
| Approval inbox | Per-connection approval UI | Top-level inbox, plan card sections 1–9, R3 two-person rule |
| Bridge | Product name locked. Autopilot connectors under `job_autopilot/connectors/` | Contract schema, Connections subsystem, Shopify, tiers 3a/3b/3c, Contract Studio |
| Compiler | ModuleSpec + `ai_document_compiler.py` + `ai_studio_contract.py` | ISPEC round-trip, Recompile, Sync, drift detector that blocks |
| l10n | `invoicing_l10n.py`, Autopilot country→`l10n_*` | YAML adopt-by-xmlid engine |
| JSON-2 | Transport code and unit tests | Live Online `/doc` smoke (operator). Local tip `/doc` returned 404 on 2026-10-02 |
| Audit | `audit_logs` via `AuditLogMiddleware` on mutating HTTP calls | Hash chain (`prev`, `hash`), redaction, verify endpoint, auth events in the same chain |

## Missing

`classify_rpc`, never-allowed list in code, request IDs, structlog/JSON logs, ruff, mypy, pyright, a `tsc` script, MCP product package, IndexedDB offline queue, Dashboard Studio, Worker Bots, ISPEC drift detector, Shopify connector, Odoo 20 compose file and `ir.access` adapter, `motion/react`, Base UI, Sonner, shared `loading.tsx` / `error.tsx` / `not-found.tsx`.

EmptyState and Skeleton appear on 3 of 67 pages. ErrorNotice appears on 35 of 67. Axe covers 8 pages (`e2e/a11y-primary.spec.ts`).

## Logging today

stdlib `logging` only. No correlation ID. Opt-in dumps: `.cache/ai_ir_trace/` (`AI_IR_TRACE`), `.cache/ai_llm_prompts/` (`AI_LOG_LLM_PROMPTS`). Do not treat those as the product audit chain.

## Oversized frontend files (split before restyle)

| Lines | File |
|------:|------|
| 6130 | `apps/web/src/lib/api.ts` |
| 1892 | `apps/web/src/app/connections/[id]/wizard/page.tsx` |
| 1721 | `apps/web/src/styles/studio-refinement.css` |
| 1548 | `apps/web/src/app/connections/[id]/studio/page.tsx` |
| 1429 | `apps/web/src/app/connections/[id]/designer/page.tsx` |
| 1366 | `apps/web/src/app/globals.css` |
| 1312 | `apps/web/src/app/connections/[id]/bulk-suite/page.tsx` |
| 1225 | `apps/web/src/app/connections/[id]/page.tsx` |
| 946 | `apps/web/src/app/connections/[id]/config/page.tsx` |

## Settings flags a card may touch

Auth: `auth_mode`, `app_api_key`, OAuth client ids, SMTP, `app_admin_*`. LLM: `ai_assist`, provider keys, `ai_pipeline_mode`, `ai_ir_trace`. Sandbox: `sandbox_docker_socket`, `sandbox_docker_enabled`. Never print these values into the progress log.

## Explicitly not built (do not describe as done)

Hash-bound plan card, two-person R3, WAL journal, executor Mode T/C, hash-chained audit, approval inbox, L3/L4 autonomy, Bot roster, Contract Studio, Dashboard Studio, offline queue, Odoo 20.
