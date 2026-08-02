# Handover — unfinished work (multi-version + follow-ups)

> **Audience:** a fresh agent continuing this repo.  
> **Author session end:** 2026-07-27 / handoff 2026-07-28 / **implementable close 2026-07-28** / **upgrade-map Phases 0–D closed 2026-07-28**.  
> Multi-version scaffolding, HANDOVER implementable items, **and upgrade-map Phases 0–D are closed on disk** unless a regression is found. **§7 stays out of scope.** Honest remainders: §1.7 hygiene and Studio-parity limits in §2.11 / §9 (not silent TODO debt).

Read first (in order): `AGENTS.md` → `MEMORY.md` → `ERRORS.md` → `STATE.md` → this file → `docs/MULTI_VERSION_ODOO_PLAN.md` → `docs/STUDIO_PARITY_BY_MAJOR.md` → `skills/odoo-rpc-gate.md` → `skills/studio-parity.md`.

Confirm phrase for advanced/destructive API: `I understand the risks`.

---

## 0. What *was* shipped (so you don’t redo it)

Treat these as **done unless you find regressions**:

| Area | Status |
|------|--------|
| Compat registry 16–19; GA = 17+18+19; experimental = 16 | Done (17 promoted 2026-07-28; **do not GA 16**) |
| Cap matrix API + `CapabilityProbePanel` on Connect/Browse/Designer/Builder/Automations/Power Ops | Done |
| Automations grey-out (object_write / related_write / object_create) | Done |
| Designer grey-out (inject/mutate, header object_write, smart buttons, bind modes) + banners | Done |
| Builder grey-out (inject, monetary/currency_field) + banners | Done |
| `VersionAwarenessBanner` on connection-scoped surfaces (wizard, menus, reports, access, …) | Done |
| Enterprise warn-only (probe message + banners; same caps as Community for major) | Done |
| Odoo 18 Docker `:8070`, live integration + Power Ops after `account` | Done (when stacks up) |
| Odoo 17/16 Docker `:8071`/`:8072`, hardened init, **deepened** live smokes (menus/reports/17 related_write) | Done |
| One zip per connection major (`manifest_version_for_major`) + `list_view_for_major` in export/sandbox gate | Done |
| Matching-major ephemeral sandbox `:18069` + **CI `major-matrix`** (manual dispatch; local proof 16–18) | Done |
| Power Ops recipe `tags` / `min_major` wired in UI | Done |
| Docs: STUDIO_PARITY (menus/reports ✅), FULL-SCALE 19-primary, USER-Guide Online/Enterprise, LOCAL-UAT live commands | Done |

Permanent stacks (do not collide ports):

| Major | Compose | Port | Init |
|-------|---------|------|------|
| 19 | `docker/docker-compose.yml` | 8069 | `init-db.sh` |
| 18 | `-p odoo18` + `docker-compose.odoo18.yml` | **8070** | `init-db-18.sh` (hardened) + optional `ensure-account-18.sh` |
| 17 | `-p odoo17` … | 8071 | `init-db-17.sh` (stop → drop → `run -i base,web`) |
| 16 | `-p odoo16` … | 8072 | `init-db-16.sh` (same pattern) |
| Ephemeral sandbox | `-p odoo-sandbox` + `docker-compose.sandbox.yml` | **18069** | via `app/sandbox.py` + `docker/run-sandbox-major-gate.sh` |

---

## 1. Explicit “not touched / follow-up” from the last arcs

### 1.1 CI matrix for matching-major sandbox (16–18) — **DONE**

- **Evidence:** `.github/workflows/odoo-sandbox.yml` gate `major-matrix`; `docs/LOCAL-UAT.md` §CI; MEMORY decision (manual dispatch, not default cron).

### 1.2 Live smoke depth on 16 / 17 — **DONE (deepened; not exhaustive)**

- **Evidence:** `test_integration_odoo17.py` — related_write/object_write, menu `view_mode` tree, QWeb report create; `test_integration_odoo16.py` — refuse related_write, menus/reports path aligned with 17+; STUDIO_PARITY row ✅ 16–19.
- **Still thin / optional (not blockers):** module zip install smoke on permanent 16/17 stacks (sandbox gate covers zip install); pipelines sandbox hop for major ≠ 19. **A2 / C3 closed:** access/mail/inject on `:8072` + Power Ops dry-runs in `test_power_ops_odoo16.py` / `test_power_ops_odoo17.py` (accounting skips until `ensure-account-16.sh` / `ensure-account-17.sh`).

### 1.3 Promote 17 (or 16) to GA — **17 DONE; 16 NOT**

- **Evidence:** `ga_majors()` includes 17; 16 remains experimental (no `update_path`); MEMORY + 12/12 live smokes for 17 arc.
- **Do not** promote 16 without adapter + evidence + MEMORY unlock.

### 1.4 Capability grey-out / banners — **DONE (implementable sweep)**

- **Evidence:** `VersionAwarenessBanner` on wizard/reminders/menus/reports/config/access/import/modulespec/projects/journal/pipelines; Power Ops `belowMinMajor`; Designer/Builder/Automations/Power Ops + `CapabilityProbePanel`.
- **A1 (upgrade-map):** Menus/Reports/Access/Projects RPC mutations grey-out via `mutationAllowed` / `canAdvanced` + disabled controls — **DONE** (`menus/page.tsx`, `reports/page.tsx`, `access/page.tsx`, `projects/page.tsx`).

### 1.5 Designer / Builder — capability wiring — **DONE**

- **Evidence:** Designer `inject_strategy` inherit/mutate + `view_inject_mutate` grey-out; bind modes via `bindModeSupported`; Builder `currencyFieldSupported` warning; list/tree via adapters + `list_view_for_major` on export/sandbox paths.

### 1.6 Online SaaS product copy / packaging — **DONE (USER-GUIDE)**

- **Evidence:** `docs/USER-GUIDE.md` § “Odoo Online / Enterprise (connections)” — warn-only, public ORM only, no Studio.
- Marketing “follow-host” wording in STUDIO_PARITY remains **packaging-only** (not a separate tier).

### 1.7 Permanent “keep smokes green” hygiene — **ONGOING**

- Odoo 19 related_write live smoke; Odoo 18 Power Ops after `./docker/ensure-account-18.sh`; re-run after compat/adapter changes.
- Not fully automated beyond optional/manual workflows and live skips when Docker is down.

---

## 2. Silently incomplete / inconsistent items (easy to miss)

### 2.1 Docs drift — **DONE**

- **Evidence:** FULL-SCALE §1.3 multi-version + 19-primary Library; MULTI_VERSION header → this file; pytest `integration` mark in `apps/api/pytest.ini` + `packages/odoo-client/pyproject.toml`; LOCAL-UAT §F2 live commands.
- **Historical only:** early MEMORY M2 “18 experimental; refuse ≤17” — superseded; don’t follow.

### 2.2 Sandbox code vs proof — **DONE (local gate)**

- **Evidence:** `docker/run-sandbox-major-gate.sh` builds zip via `list_view_for_major` + `run_sandbox_install` per major; CI `major-matrix`; manual local proof 16–18 documented in STATE/MEMORY arc.

### 2.3 Odoo 16 automation adapter honesty — **DONE (hard-fail)**

- **Evidence:** `automation_v16.py` raises on `encode_related_write_server_vals` / `encode_update_field_server_vals` / `related_write_update_path`.

### 2.4 Init / module install gaps — **DONE (18 aligned)**

- **Evidence:** `init-db-18.sh` stop → drop → `compose run -i base,web` (same class as 16/17).
- **Note:** `account` still not auto on 18 init — use `ensure-account-18.sh` for Power Ops.

### 2.5 Export / generator remaining risk — **DONE (core path); optional audit**

- **Evidence:** `list_view_for_major` + adapter normalization in `module_generator`; sandbox major gate + export inherit path use it.
- **Optional:** Library `app_templates.py` hard-codes `<list>` (acceptable — Library vertical **19-primary**).

### 2.6 `connectionSupports` fail-open — **DONE (fail-closed)**

- **Evidence:** `apps/web/src/lib/capabilities.ts` — `if (!caps) return false`; `belowMinMajor` / `currencyFieldSupported` fail-closed when major unknown.

### 2.7 Capability probe UI coverage — **DONE**

- **Evidence:** `CapabilityProbePanel` on Connect, Browse, Designer, Builder, Automations, Power Ops.

### 2.8 Persist vs derive capabilities — **DONE (re-probe)**

- **Evidence:** Connect `reprobe()` → `api.probeConnection`; `connections.py` `probe_connection` refreshes `server_version` + derived capabilities.

### 2.9 Menus / reports on 16–17 — **DONE**

- **Evidence:** `docs/STUDIO_PARITY_BY_MAJOR.md` ✅ 16–19; integration tests in `test_integration_odoo16.py` / `test_integration_odoo17.py`.

### 2.10 Power Ops `min_major` unused — **DONE**

- **Evidence:** `power-ops/page.tsx` filters/blocks recipes via `belowMinMajor`.

### 2.11 Studio-parity product gaps (all majors — not multi-version specific) — **MOSTLY DONE**

- Property fields — out of scope v1 (intentional; §7)
- Kanban card designer — **DONE (C1)** — `KanbanCardPreview` + reorder + live `:8069` round-trip; `nolabel` still unsupported in arch helpers
- In-Odoo OWL feel — external app + Open-in-Odoo only
- Vision-verify Designer — **DONE (C2)** — PNGs in `docs/vision-verify/`; Vision Checker **PASS** 2026-07-28
- Full ACL matrix / multi-company rule builder — previously rejected (MEMORY)

### 2.12 Library / full-scale plan contradiction — **DONE (19-primary explicit)**

- **Evidence:** FULL-SCALE §1.3 — platform multi-version live; Library smoke/UAT/CI **19-centric** by design.

### 2.13 Future majors / floor — **INFORMATIONAL**

- Majors ≤15 refused; Odoo 20+ not registered; Enterprise beyond `+e` heuristic — unchanged until MEMORY unlock.

### 2.14 Tests not run / skipped class — **DONE (documented)**

- **Evidence:** LOCAL-UAT §F2 + §matching-major sandbox; `integration` mark registered.
- **Hygiene:** live tests skip when instance down — don’t confuse unit-only green with live green (see §1.7).

### 2.15 Web e2e — **DONE (automation caps)**

- **Evidence:** `apps/web/e2e/automation-caps.spec.ts` + `/e2e/automation-caps` harness (mock Odoo 16 greys out update_field / related_write); LOCAL-UAT pointer.

---

## 3. Known hazards (from ERRORS.md / session) — don’t relearn the hard way

1. **Never** `docker compose down -v` on sandbox/version files without distinct `-p` project names.
2. **Never** `-i base` while a long-running Odoo worker has the DB open → `KeyError: ir.http` (use stop → drop → `compose run --rm` → start).
3. Sandbox host port is **18069**; permanent Odoo 18 is **8070** — do not reunify.
4. `create_model` default list view: use adapter `list_type_fallbacks("list")[0]` (`tree` on ≤17).
5. `ir.model.fields` optional columns (`currency_field`, etc.): filter via `fields_get` (`_ir_model_fields_columns`).
6. No Studio / Enterprise source; public ORM/RPC only.
7. No router `if major == N` for encode logic — **compat adapters + registry only**.
8. Confirm phrase + API flags for advanced/destructive actions.
9. Sandbox before promote; Python = Option A (module → sandbox → promote).

---

## 4. Recommended implementation order for the next agent

**Multi-version + upgrade-map remainders are closed.** Prefer hygiene unless the user opens new scope:

1. **Keep smokes green** (§1.7) after compat changes — permanent stacks + optional `major-matrix`.
2. **Do not** GA 16, unlock 20+/≤15, or touch Studio (§7).
3. Optional later: kanban `nolabel` arch support; Odoo 20 registry after MEMORY unlock.

---

## 5. File map for unfinished work

| Concern | Primary files |
|---------|----------------|
| Caps / GA | `packages/odoo-client/src/odoo_client/compat/{capabilities,registry}.py` |
| Adapters | `…/compat/adapters/automation_v{16,17,18,19}.py`, `views_v{16,17,18,19}.py` |
| Client list/fields | `packages/odoo-client/src/odoo_client/client.py` |
| API matrix | `apps/api/app/capabilities.py` |
| Sandbox | `apps/api/app/sandbox.py`, `docker/run-sandbox-major-gate.sh`, `docker/docker-compose.sandbox.yml` |
| Export version | `apps/api/app/export_service.py`, `packages/module-generator/.../manifest_version_for_major`, `list_view_for_major` |
| Power Ops tags | `apps/api/app/power_ops_recipes.py`, `apps/web/.../power-ops/page.tsx` |
| UI helpers | `apps/web/src/lib/capabilities.ts`, `VersionAwarenessBanner.tsx`, `CapabilityProbePanel.tsx` |
| Live smokes | `packages/odoo-client/tests/test_integration_odoo{16,17,18,19}.py` |
| CI | `.github/workflows/odoo-sandbox.yml`, `docker/run-sandbox-*.sh` |
| Vision-verify (C2) | `docs/vision-verify/`, `apps/web/e2e/designer-vision.spec.ts`, `skills/vision-verify-ui.md` |
| Decisions | `MEMORY.md`, this file |

---

## 6. Acceptance criteria checklist (copy into STATE when working)

Use as a definition of “multi-version follow-through complete”:

- [x] Docs no longer claim “Community 19 only” where multi-version is live — FULL-SCALE §1.3, USER-GUIDE, STUDIO_PARITY
- [x] Live sandbox install succeeds for majors **18, 17, 16** (minimal zip each) on `:18069` — `run-sandbox-major-gate.sh` + local/CI major-matrix
- [x] Gate scripts / CI use `:18069` and optional major matrix (manual dispatch documented)
- [x] Integration mark registered; documented live pytest commands — `pytest.ini`, `pyproject.toml`, LOCAL-UAT §F2
- [x] 16/17 menus+reports smoke-proven; matrix ✅ in STUDIO_PARITY
- [x] Power Ops UI respects `min_major` + connection major — `belowMinMajor` in Power Ops page
- [x] Remaining builder surfaces have experimental/Enterprise banners — `VersionAwarenessBanner` sweep
- [x] v16 related/update_path cannot be invoked via encoder without capability (hard fail) — `automation_v16.py`
- [x] `init-db-18` hardened — stop/drop/`compose run` like 16/17
- [x] MEMORY updated for GA 17; STATE retro for HANDOVER close
- [ ] **Ongoing:** keep permanent-stack live smokes green after changes (§1.7)
- [x] **C3:** Power Ops 16/17 live dry-run tests + `docker/ensure-account-16.sh` / `ensure-account-17.sh` (accounting skips when `account` absent)
- [x] **C1:** Kanban designer polish — `KanbanCardPreview` + Designer kanban mode
- [x] **C2:** Vision-verify screenshots in `docs/vision-verify/` — Vision Checker **PASS** 2026-07-28 (form/list/kanban)

---

## 7. Out of scope (intentional — do not “finish” unless user asks)

- Odoo Enterprise Studio / `web_studio` source
- Property fields
- Celery as default queue
- Paid cloud LLM required for core
- Multi-manifest module zips
- Majors ≤15 or 20+ without MEMORY unlock
- Pretending field drops / uninstall are fully reversible
- Live `state=code` as default no-code path (Option A only)

---

## 8. Session protocol reminder for the new agent

After meaningful work:

1. Update `STATE.md` retro (≤15 lines).
2. Log decisions → `MEMORY.md`.
3. Failures (>2 attempts) → `ERRORS.md`.
4. End coding replies with: files changed / not touched / follow-up.
5. Odoo API claims → verify on instance (`skills/odoo-rpc-gate.md`).

---

## 9. Upgrade-map Phases A–C (2026-07-28) — **CLOSED**

Card execution after Phase 0 re-verify. **Do not edit** `.cursor/plans/` plan files — track status here only.

| Card | Scope | Status | One-line evidence |
|------|--------|--------|-------------------|
| **A1** | Grey-out depth (Menus/Reports/Access/Projects RPC) | **DONE** | `mutationAllowed` / `canAdvanced` disables create/bind/delete on `menus`, `reports`, `access`, `projects` pages |
| **A2** | Deepen Odoo 16 live smokes (still experimental) | **DONE** | `test_integration_odoo16.py` — access, mail_post/next_activity, field inject inherit; **10 passed** on `:8072`; `ga` stays false |
| **A3** | `list_view_for_major` / export path honesty | **DONE** | `module_generator.list_view_for_major` + unit tests; export/sandbox/ai_enrich use adapter list/tree |
| **A4** | Sandbox operator docs / cadence | **DONE** | `docs/LOCAL-UAT.md` §operator cadence + `run-sandbox-major-gate.sh` 16–19; HANDOVER §2.2 |
| **B1** | Online / Enterprise product copy | **DONE** | `docs/USER-GUIDE.md` § “Odoo Online / Enterprise (connections)” — warn-only, follows host major, no Studio |
| **C1** | Kanban designer polish | **DONE** | `KanbanCardPreview.tsx` + Designer kanban layout; Playwright `e2e/designer-vision.spec.ts` kanban capture |
| **C2** | Vision-verify Designer milestones | **DONE** | PNGs `docs/vision-verify/designer-{form,list,kanban}.png` — Vision Checker **PASS** 2026-07-28 |
| **C3** | Power Ops live probe 16/17 | **DONE** | `apps/api/tests/test_power_ops_odoo16.py`, `test_power_ops_odoo17.py`; `docker/ensure-account-16.sh`, `ensure-account-17.sh` |

**Still refused (plan §5 / HANDOVER §7):** Property fields, Studio source, ≤15 / 20+ without MEMORY, live default `state=code`, pretending full field-drop rollback, **GA for 16**.

---

*Updated 2026-07-28 — HANDOVER + upgrade-map Phases 0–D closed on disk (vision Checker PASS). Prefer editing this file when new scope opens rather than STATUS bit-rot.*
