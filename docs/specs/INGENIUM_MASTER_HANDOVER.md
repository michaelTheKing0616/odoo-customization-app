# Ingenium master handover

**For:** the next AI coding model taking over Ingenium end to end.
**From:** Grok Bot, on behalf of Fabian Umole, for the owner Tope (Temitope Olaitan Michael).
**Snapshot taken:** Wednesday 21 October 2026, about 08:00 WAT (Africa/Lagos, UTC+1).
**Repo:** `/Users/temitopeolaitanmichael/Odoo_Customization_App` on Tope's Mac, branch `premium-local-tip`, HEAD `e094e79` ("test: check the Odoo 20 version table against the live tip").

Your job has two halves. Redo, to a world-class standard, what was built poorly. Build everything that is not built yet. Tope is unhappy with the UI quality so far. Treat every screen as unfinished until it passes the UI standard in section 5 and the visual QA process in section 5.14.

---

## 0. How to read this document

### 0.1 Evidence labels
Every status claim carries one of these labels. Never upgrade a label without new evidence.

| Label | Meaning |
|---|---|
| **[Done, live]** | Code exists and a live run on disposable Odoo 17, 18, 19 and 20 databases is logged as passing in `apps/api/evals/v2/PROGRESS.md` (Mac) or `/workspace/ingenium_builders/PROGRESS.md` (box). |
| **[Done, code]** | Code and unit tests exist. No live 17 to 20 pass is logged. Treat as unproven. |
| **[Partial]** | Some of the spec is built. The gap is named. |
| **[Missing]** | No symbol, route or screen was found by grep (GAP_AUDIT method) and no log entry says it was built. |
| **[Inferred]** | My reading of the evidence, not a logged fact. Verify before relying on it. |
| **[Reported by Tope]** | Stated in the commissioning brief for this document, not found in any log or file. Confirm with Tope or measure it yourself. |
| **[Verified 21 Oct]** | I measured it myself, read-only, while writing this document. |

### 0.2 Sources read for this document
On the box (`/workspace/ingenium_builders/`):
- `IDEA.md` (builders goal), `SPEC.md` (View Designer, reports, App Studio adoption, bots), `CONFIG_SUITE_SPEC.md` (Configuration Suite and Bulk Setup), `BRIDGE_RUNNER_SPEC.md` (code runner, Bridge, LLM caching, AI guards), `FEATURE_AUDIT.md` (app-wide audit, approved "all"), `DESIGN_TOUCHES.md` (162 design touches, all approved), `APP_STUDIO_HANDOFF.md`, `APP_STUDIO_FIX_PLAN.md`, `GAP_AUDIT.md` (latest status, 20 Oct), `PROGRESS.md` (the builders build log, to 19 Oct 17:40), `ODOO_CONFIG_CATALOG.md` (headings only), `stage3/contrast.md`, `stitch_config_suite.md` (not read in full; Stitch screens were evidence only).
- Design pack at `/home/box/design-repo`: `skills/DESIGN_SYSTEM_PLAYBOOK.md` (laws and QA checklist), `skills/CATALOG.md` (index only), `brand/ingenium-v2/final/BRAND_GUIDE.md` and `tokens.css`.

On Tope's Mac (read only; nothing changed):
- `apps/api/evals/v2/PROGRESS.md` (the full App Studio and Build 5 log, including the QUEUE CHECKLIST Q1 to Q8 and the GAP_AUDIT queue G1 to G9). Copied to the box at `/workspace/ingenium_src/PROGRESS_mac.md`.
- `README.md`, `AGENTS.md`, `RULES.md`, `docs/SAFETY.md`, `docs/ODOO_HOSTING_AND_VERSION_KINGSHIP.md`, `docs/DEPLOY.md` (sections), `docs/HANDOVER_UNFINISHED_WORK.md` (headings, dated 11 Aug, mostly superseded).
- Structure of `apps/web/src` and `apps/api/app`, `apps/api/app/settings.py`, `apps/web/package.json`, `apps/web/next.config.ts`, `apps/web/src/styles/globals/tokens.css`, `apps/web/src/lib/nav.ts`, `git status`, listening ports, and one read-only `GET /api/connections` count.

### 0.3 Name the parts the same way every time
- **App DB:** Ingenium's own Postgres (connections, plans, History, audit). Never a client's Odoo database.
- **Client DB:** any Odoo database a user connects. Production client DBs are never touched by tests.
- **Disposable DB:** a throwaway Odoo database named `ingenium_*` on a local Odoo 17, 18, 19 or 20 container, dropped after each run.
- **Write gate:** the shared server-side check every write passes (test-run receipt, money guard, approval rule, undo point). Code lives in `app/write_gate.py`, `app/dry_run_middleware.py`, `app/dry_run_ledger.py`.
- **Test run:** what the UI used to call "dry run". The UI word is now "Test run" (Oct 20 b). Code identifiers still say `dry_run`.
- **History:** the single timeline of every change, with undo (FEATURE_AUDIT A4).

---

## 1. Product vision, users, positioning, tiers, hosting and versions

### 1.1 What Ingenium is
Ingenium is a no-code customization SaaS for Odoo. It connects to an existing Odoo database over Odoo's public API and lets a person:
- design apps from a plain-language brief (App Studio),
- edit screens, lists, kanban boards, printed reports and emails visually (View Designer and Report Designer),
- set up a whole database in one checked plan (Configuration Suite, Bulk Setup),
- connect Odoo to other systems (Bridge),
- run safe scripts (Code Runner),
- answer client questions live in a sales demo (Live Demo Co-Pilot),
- and undo any of it from one History.

The brand idea (BRAND_GUIDE): "An arch is a pile of parts that stands only once the keystone drops in. Odoo is the arch; the module you build and test in Ingenium is the keystone that locks it. *Ingenium* is the Latin root of *engineer*."

The repo README still describes the older positioning: "External no-code customization platform for Odoo Community 19 (Studio-class UX via public ORM/RPC, not Enterprise Studio)." The current product supports Community and Enterprise on 17 to 20 (AGENTS.md: "Community 20 + 19 + 18 + 17 = GA; 16 = experimental"). Update the README as part of docs work (section 9.5).

### 1.2 Users
1. **Odoo consultants and agencies (primary).** They run many client databases, need speed, safety and proof. FEATURE_AUDIT designs for them: agency groups on Connect, a fleet Command center, client portal, white-label, re-billing reports.
2. **In-house Odoo admins.** One or two databases, moderate technical skill.
3. **Non-technical clients and business owners.** They type briefs in plain, messy, code-switched language (Pidgin, Yoruba, Hausa appear in the eval briefs), approve plans in Client mode, and must never see technical terms by default.
4. **Developers (secondary).** They want "Show code", the term card with technical names, generated modules that read like craft, and the "Show the request" developer switch (touch 158).

FEATURE_AUDIT A8 approves adaptive onboarding that asks "Agency, in-house admin or developer?" and shapes the menu and Home around the answer. [Missing]

### 1.3 Positioning
- **Beyond Odoo Studio** in fidelity, safety and craft (IDEA.md). Studio is Enterprise-only and writes directly. Ingenium works on Community and Enterprise, previews first, checks everything with code, and keeps undo.
- **Beyond Odoo 20's own AI agent.** CONFIG_SUITE_SPEC 20.2 records that Odoo 20's agent tools "run without further checks", have no dependency ordering and no documented undo. Ingenium adds a typed plan, dependency order, version-aware mechanisms, a live check with a receipt, reversibility shown up front, an undo plan, the money guard, approvals and one run at a time per database.
- **Clean-room.** Public ORM and RPC only. Never read, copy or reverse-engineer Enterprise Studio source (AGENTS.md).
- **Honest.** Never invent data. Every number on screen comes from the connected database or is labelled "Example" (CONFIG_SUITE_SPEC 7.5).

### 1.4 Tiers and billing (as built)
- `app/billing_models.py` holds `BillingPlan` ("Seeded plan catalog: prices live in processor dashboards, refs stored here") with `stripe_price_id` and `paystack_plan_code`, plus `PlanFeature` entitlements. The default plan id is `free_solo`. No other seeded plan id was found by grep. [Verified 21 Oct]
- Home shows plan chips from the billing catalog; hard-coded prices were removed (Build 5 S5, "UI-S-42 real prices only met").
- `app/entitlements.py`, `tier_gating.py`, `tier_matrix.py` gate features by hosting, edition and modules.
- The full pricing and billing target is in section 9.2.

### 1.5 Hosting types (what each one allows)
Hosting is orthogonal to edition (Community or Enterprise). Source: `docs/ODOO_HOSTING_AND_VERSION_KINGSHIP.md`, PROGRESS Q3.

| Hosting | How Ingenium detects it | What Ingenium may do | Install path |
|---|---|---|---|
| **Odoo Online (SaaS)** | URL `*.odoo.com`, or server version starting `saas~` | No custom Python modules. No-code metadata changes and approved stock apps only. Prefer Odoo API keys; Online often rejects passwords for RPC. | No module install. Metadata via RPC. |
| **Odoo.sh** | URL `*.odoo.sh` or `*.dev.odoo.com` | Full modules through git. Still public RPC for live changes. | Export a module zip with `DEPLOY_ODOO_SH.md`; the panel says "Deploy via Odoo.sh Git push". [Done, live on 20 only] |
| **Self-hosted** | Anything else | Full control. Sandbox test, then promote. | Direct install of the generated module after a sandbox gate. |

Detection order (`app/hosting.py`, `hosting_hint_from_url`): saved choice, then `saas~` version, then URL. The Connect form prefills the picker with "Looks like X. Change it if that's wrong." The choice is saved on the connection (`odoo_connections.hosting`, alembic `w3x4y5z6a7b8`) and read by tier context, capabilities, suite, views, App Studio, module spec, bulk suite and grounding. [Done, code; Odoo.sh path live on 20]

### 1.6 Odoo versions 17 to 20
- **Supported:** 17, 18, 19 and 20 are GA. 16 is experimental and gets a notice plus a read-only Inspector. 15 and older are refused.
- **Version facts live in one place:** `apps/api/app/compat/odoo_versions.py`. Known facts:
  - list root `<tree>` on 17, `<list>` from 18;
  - kanban card `kanban-box` on 17, `card` from 18;
  - access: `ir.model.access` plus `ir.rule` on 17 to 19, `ir.access` on 20 (fields `model_id` and `group_id` on the 20 nightly `20.0-20260926`; `ir.rule` is gone);
  - units: categories on 17 and 18, reference unit and factor (`relative_uom_id`) on 19 and 20;
  - contracts: `hr.contract` on 17 and 18, `hr.version` on 19 and 20;
  - Odoo 20 has no XML-RPC `db` service; `ir.attachment` has no `datas` (only `raw`); `res.users` uses `group_ids`;
  - `base_import` on 17 to 19 takes raw text, on 20 wants base64;
  - Odoo 17 `safe_eval` needed a `LIST_TO_TUPLE` shim; Odoo 20 sandbox needs `--http-interface=0.0.0.0` and Postgres 16.
- **Version is read, never chosen.** The UI shows the version the connected database reports. There is no version switcher (CONFIG_SUITE_SPEC 8). Comparisons with other versions use a stock catalogue captured from disposable databases and are labelled "Stock Odoo {v}".

---

## 2. Architecture as built

### 2.1 The stack
| Layer | What is there | Evidence |
|---|---|---|
| Web | Next.js 15.5.24 (App Router, Turbopack), React 19.1.0, TypeScript 5, Tailwind CSS 4, Base UI 1.8.0, `motion` 14, `cmdk`, `sonner` 2, `react-virtuoso` 4, `lucide-react`, Geist, Geist Mono and Libre Franklin via `@fontsource-variable` (self-hosted). Tests: Vitest 3, Playwright 1.62. | `apps/web/package.json` [Verified 21 Oct] |
| Web size | 126 `page.tsx` routes, 702 component `.tsx` files under `components/`. | [Verified 21 Oct] |
| API | FastAPI, Python 3.12+, Pydantic 2, SQLAlchemy 2, psycopg 3, Alembic, httpx, openpyxl, pypdf, pypdfium2, Pillow, segno, argon2, pyotp, authlib. uv workspace with `packages/odoo-client` (typed RPC client) and `packages/module-generator` (Jinja2 to installable addon zip). | `apps/api/pyproject.toml` |
| API size | 658 Python files in `apps/api/app`, 75 router files, 541 entries in `apps/api/tests`, 35 Alembic version files. | [Verified 21 Oct] |
| App DB | Postgres. Main app DB on `:5433`; an Odoo 20 stack app DB on `:5436`. Raw-SQL tables since 3 Oct (`journal_entry`, `before_image`, `apply_database_lock`, `plan_cards`) are now mapped in `db_models` (Oct 20 h). | PROGRESS |
| Migrations | Alembic. Startup also runs `init_db` ALTERs, which caused drift (section 4, P0-2). | PROGRESS Oct 20 h, G5 fix |
| AI | Shared client `app/ai_client/` (`shared_client.py`, `ai_cache.py`, `ai_scope.py`, `context_cache.py`, `guards.py`) above `app/llm_gateway/` and `app/llm_provider.py`. Gemini on Vertex. Pipeline model `gemini-3.8-flash`; fallback `gemini-2.5-flash` on timeout or 5xx; agent mode `gemini-3.1-pro-preview` with fallback to 3.8-flash. `settings.py` default is `gemini_model = "gemini-3.6-flash"` and `gemini_backend = "studio"`; the running environment overrides them (the `.env` was not read). Local Ollama on `:11434` for local-AI paths. | SPEC 3.1, HANDOFF, PROGRESS Oct 19, settings.py |
| Odoo stacks (local) | Docker: Odoo 19 `:8069`, 18 `:8070`, 17 `:8071`, 20 `:8073`. Isolated sandbox stacks `ingenium_sandbox_v<N>` on `127.0.0.1:18100+N`. | PROGRESS S12, R2 |
| Processes | `ingenium.api` (launchd) on `127.0.0.1:8001`, started **without `--reload`** (a code change is not live until the process restarts). Eval API `:8002`, agent arm `:8012`, web dev `:3002`. | AGENTS.md, PROGRESS |

### 2.2 Clean-room: public ORM and RPC only
- Every Odoo read and write goes through `packages/odoo-client` using XML-RPC, JSON-RPC or JSON-2. XML-RPC is primary with a JSON-RPC fallback (some Online paths block `/xmlrpc/2/*`). JSON-2 create sends `vals_list` (`transport/execute_kw_map._create_body`).
- Customization uses only `ir.model`, `ir.model.fields`, `ir.ui.view`, `ir.ui.menu`, `ir.actions.*`, `base.automation`, access records and Odoo's own wizards (`base_import`, `portal.wizard`, `base.document.layout`, chart `try_loading`).
- No direct SQL on any client DB. No server-side Ingenium module is required for live changes. Generated modules are the escape hatch for hosting that allows them.
- Odoo 20 compatibility shims (section 2.9) hook once in `OdooClient.execute_kw`.

### 2.3 The write gate (every write passes it)
The contract, from CONFIG_SUITE_SPEC 7.2 and PROGRESS:
1. **Check first.** The tool calls its test-run route. Code validates every model, field, value, button and permission against the live database (schema read with TTL 0 on apply, `schema_freshness.py`, one TTL of 300 s shared by `odoo_snapshot` and `ai_schema_client`).
2. **Receipt.** The server issues a receipt for that exact plan in `dry_run_ledger` (1 hour). Any change to the plan clears it in the UI and on the server.
3. **No receipt, no write.** `dry_run_middleware` refuses gated writes without a matching receipt (HTTP 428 in the suite, 403 elsewhere). Non-JSON bodies are covered too (fixed 19 Oct; content-type check made case-insensitive 20 Oct; `tests/test_dry_run_non_json.py`).
4. **One run per database** (`mutation_lock`, 409 `mutation_in_progress`), an hourly budget (`anomaly_guard`, 500 mutations per connection per hour), caps and pacing (`blast_radius`: sample first at 50, reversible cap 1,000, destructive cap 200, batch 25, sleep 200 ms).
5. **Shared guards for any page** (`app/write_gate.py`, `guard_one`): money guard refusal, approval rule (suite threshold, same approvals list, action `shared_write`, "Large record change"), and an undo point (History snapshot `record_values` with before-values).
6. **Audit.** Every run writes a hash-chained audit row (`audit_chain.py`) and a run record.

Where the shared guards are wired (A5) [Done, code]: Bulk Suite mass edit, ID generator live apply, Power Ops real runs, Import commit (money guard, approval, undo for created rows and, since Oct 20 z, updated rows), dedupe merge, recompute, portal access, company settings, email-template settings, activity types, Day-1 setup, multi-company, document branding. The record editor is gated through setup plans. Email body saves keep their own put-back.

### 2.4 The money guard
- **Never written in bulk or directly:** accounting entries' financial fields, taxes, fiscal positions, journals, payment logic, stock valuation, POS payments (tier 1 in `protected_modules.py`, `protected_enforcement.py`, `changeset/protected_core.yaml`).
- **Chart of accounts and taxes come only from Odoo's country package** via `try_loading`. A plan never contains invented accounts, tax rates or fiscal positions. A brief asking for a "VAT 7.5% custom tax" yields a route, not a tax. [Done, live 17 to 20 in G4]
- **Currency, costing method and valuation** settings are allowed only while the company has no accounting entries and no stock moves.
- **Opening balances and initial stock** always run last, always need approval, and become a draft entry on the Opening journal only.
- **Odoo's own invoice buttons** (post, reset to draft, cancel) are allowed in "Move records forward" under the money guard with manager approval (decision D2).
- **Power Ops** accounting and delete recipes are locked (`LOCKED_RECIPES`: `purge_journal_entries`, `mass_unlink`, `cancel_account_moves`, `reset_and_cancel_moves`, `post_account_moves`, `unreconcile_and_draft`; any write, unlink or method on `account.*` refused with 403 `money_guard`). The UI shows them in a "Switched off to keep your books safe" band. [Done, code]
- **Accounting-import rule (Tope, Oct 20 z and ab):** imports of accounting setup (accounts, taxes, journals, fiscal positions, tax groups) go through approval every time, and the consultant who asks may approve their own request; History records a `self_approval` entry with who and when. Other large changes keep "someone else approves". Posted entries, journal items, payments and invoices are always refused.

### 2.5 Undo and History
- `snapshots.py`, `rollback_tiers.py` (compensating plans), `changeset/rollback.py`, `changeset/recovery.py`.
- Bulk Setup builds an **Undo plan** after every run: Revert steps restore old values, Remove steps archive or delete created records, one-way steps are listed with the manual route (CONFIG_SUITE_SPEC 20.8). [Done, live 17 to 20]
- Imports use Ingenium external ids `__ingenium_import__.{job}_{table}_{row}` so re-uploads update and Undo finds exactly what was created.
- Code Runner undo is a code-generated reverse script (newest first; deletes and actions are listed, not undone; no second undo).
- **History (A4):** `routers/history.py` plus `HistoryTimeline` exist (Oct 20 e). Cmd-K opens History on a change via `?change=`. Per-page snapshot panels on Access, Automations, Menus, Builder and Projects were meant to go; GAP_AUDIT marks their removal "not confirmed". [Partial]
- Reversibility levels shown on every Run sheet: Look only, Undo available, Hard to undo, Never here (CONFIG_SUITE_SPEC 7.1).

### 2.6 The test-copy flag
- `is_test_copy` column on connections (alembic `y5z6a7b8c9d0` plus an `init_db` ALTER). "Connect a test copy" prefills the form (name "(test copy)", database `_test`, same URL, user, group and hosting; password blank) and sets the flag. The Connect list has a checkbox to edit it (PATCH, rollback on error). Unset rows show "(guessed)" from a name guess with `certain: false`. [Done, code]
- Every `ConfirmDialogV2` (38 screens) names its target: "On <connection> [Live | Test copy]"; unset rows say "Probably …" (touch 92).
- Touch 28 (hazard band on test copies) and 29 (a colour per database) are logged as already built (Q2 batch 4).

### 2.7 AI_ASSIST off
- `settings.ai_assist` defaults to `"off"`. Until 20 Oct, "off" did not switch AI off: tier routing (`ai_llm_tier_fast` default `"gemini"`) built a Vertex provider anyway, so "offline" tests called Vertex live and read the `~/.ingenium` cache. Fixed in `llm_provider._raw_provider_for_tier` (off returns None; the test "mock" tier is still allowed). [Done, code]
- Consequence: some tests had passed only because they silently called Vertex. They now fail honestly or were rewritten (car-rental pack tests, Oct 20 h and i).

### 2.8 Auth modes
From `apps/api/app/settings.py` and AGENTS.md:
- `AUTH_MODE=off` (default; local gates only; `/health` warns).
- `AUTH_MODE=api_key` (also `on`, `true`, `1`): `APP_API_KEY` or hashed keys in `app_api_keys`; send `Authorization: Bearer …` or `X-API-Key`.
- `AUTH_MODE=accounts`: user accounts (MON-1), sign-up, login, verify, reset, TOTP (`pyotp`), OAuth (`authlib`), `password_breach.py`.
- Known gap: with auth off, the second-approver rule cannot tell people apart. Bridge money flows now require two different typed names when sign-in is off and mark the approval `verified: false` (G5a). That is a stopgap, not security (section 6).

### 2.9 Odoo 20 compatibility shims
- `packages/odoo-client/.../compat/ir_access_shim.py`, hooked once in `OdooClient.execute_kw`: maps `ir.access` domains, fields, values and results between `model` and `model_id`, and `group` and `group_id`, when the build renamed them. `ir.rule` missing on 20 reads as empty and writes are refused plainly. Earlier ad-hoc patches were removed. [Done, live 17 to 20 for model, access create, list, update, rules list and create, export]
- About 43 other `ir.access` call sites (writes, sibling ids, `view_engine_logic`, suite) were flagged OPEN before the shim landed. The shim should cover them because it sits in `execute_kw`. [Inferred] Prove it with a live 20 pass over each of those paths.
- Install allow-list: the Community allow-list was hard-coded "19.0"; it is now version-aware, and for majors without a list it uses the live module's LGPL licence. OEEL modules are always refused. `dry_run` on install was ignored (a "preview" really installed); it now reads only. [Done, live on 20 only; 17 to 19 stacks were down]
- `build_module_zip` kept a "19.0" manifest for major 20 (module uninstallable). Fixed (R3).
- Host guard in tests: `packages/odoo-client/tests/conftest.py` and `apps/api/tests/conftest.py` refuse `aonb*`, `*.odoo.com`, `*.odoo.sh` and `INGENIUM_BLOCKED_HOSTS` at socket level. The two `.env.json2` readers are skipped unless `INGENIUM_LIVE_CLIENT_TESTS=1`.

### 2.10 Other foundations worth knowing
- **Write mode:** Observer (default for new connections; blocks all mutating RPC), Standard, Production (needs the production readiness checklist and, pre-GA, a beta partner workspace unless `PRODUCTION_WRITE_MODE_GA_UNLOCKED=1`). (`write_mode_service.py`, SAFETY.md.)
- **Changesets:** `app/changeset/` validates in 9 stages, simulates, applies a policy risk ladder, runs approvals, executes and rolls back. Setup plans and change batches persist in `plan_cards` via `changeset/store.py` (`suite_store`). The executor, inbox and policy integration for suite runs is NOT done (Oct 19 item 4).
- **Bots and autonomy:** `app/bots/grant.py` ("Prose does not grant permission. Effective rights are an intersection"; risk R0 to R4, autonomy cap L2 by default), `app/worker_bot/` (L3 and L4 policies, standing rules), `app/skills/` (at most three skills per call, never widen a grant, commit `a510de4`). D10 in AGENTS.md: L4 production autonomy stays off until GATE-L4-08 evidence exists.
- **Caching:** exact cache keyed on model, provider, system prompt, prompt, options, database, Odoo version and snapshot hash; sliding 7-day TTL; per-model dependency stamps; Vertex cached contents for system prompts of 16k characters or more; `X-Ingenium-Fresh` bypass; daily cleanup. Settings page shows `AiSavingsCard`. Semantic cache is [Missing]; batching is [Partial].

### 2.11 Known architecture problems to fix
1. **Test fixtures leak into the dev App DB.** `GET /api/connections` on the dev API returned **16,014 rows (10.5 MB, unpaginated)** [Verified 21 Oct]. Top names: "Matrix conn" 1,862, "Other client" 1,127, "Granted client" 1,127, "code-studio" 772, "fake-m3" 564, "Alice victim conn" 423, "fake-ops" 393, "role-matrix" 345. Tope's brief says 16,013; the count has grown by one. See P0-3.
2. **Production test builds overwrite the dev server's `.next`.** `next.config.ts` uses `distDir` only when `INGENIUM_DIST_DIR` or `PLAYWRIGHT_E2E_BUILD=1` is set. Otherwise `next build` writes `output: "standalone"` into the default `.next`, the same folder `next dev` on `:3002` uses. G9 used an isolated build (`INGENIUM_DIST_DIR`, port 3017), but nothing enforces it. See P0-4.
3. **The connections list is unpaginated.** The Connect page loads every row. That is a likely cause of the frozen Connect page Tope reported. [Inferred] See P0-5.
4. **Mixed startup schema changes and Alembic.** `init_db` ALTERs plus Alembic migrations make "already exists" errors and drift. See P0-2.
5. **Dangerous sandbox defaults existed.** On 19 Oct a test called `run_sandbox_install` against the shared Odoo 20 dev stack and ran `docker compose down -v`, wiping all Odoo 20 databases and the `:5436` app DB. Fixed with isolated `ingenium_sandbox_v<N>` stacks, `assert_isolated()` and a test fixture that blocks real `docker` unless `INGENIUM_LIVE_INFRA=1`. Keep those guards; never weaken them.

---

## 3. Every module and feature

Each module below has five parts: **Intended premium spec**, **Built**, **Real status**, **Known bugs**, **What's left**. "What's left" items are repeated with acceptance criteria in section 4. Routes are under `apps/web/src/app/` and API modules under `apps/api/app/` unless stated.

### 3.1 Overview (Home) and the agency Command center
**Intended premium spec.** A logged-in Home that answers "Is my Odoo healthy, and what needs me?": databases with health, drift and pending items; a "Needs you" list across databases (approvals, failures, expiring tokens); "Continue where you left off"; a greeting with substance ("Good morning, Tope. 2 approvals and 1 failed sync since yesterday."); an "All clear" screen when nothing needs attention; for agencies, a sortable portfolio of every client database (FEATURE_AUDIT 21, A12, A25, A27; touches 72, 93).

**Built.** `connections/[id]` overview (`components/overview/*`), `/command` fleet tiles (`routers/command_center.py`), greeting from `GET /accounts/whoami` and real tile counts (touch 93), `FirstRunCard` checklist that strikes through and folds into a "Setup complete" stone (touch 129), health score with dot numerals once (touch 64), plan chips from billing on the marketing Home.

**Real status.** [Partial]. Home is not yet the real agency dashboard. The Command center still shows counts; clicking a tile does not open a filtered list (FEATURE_AUDIT 21.2). No "Needs you across all databases".

**Known bugs.** None logged specifically. The Connect page freezing affects the path into Home (see 3.2).

**What's left.** Agency Home (portfolio table, health, drift, pending, sortable, virtualised); "Needs you" list; "Continue where you left off"; tile drill-down; activity feed per database; health score on every database card (A27).

### 3.2 Connect (with hosting auto-detect)
**Intended premium spec.** Tope's add 3: "a clean, modern, uncluttered redesign to the highest bar: one clear primary action, guided by hosting type, saved connections as tidy cards with health, progressive disclosure for advanced fields, plain errors with fixes". Plus FEATURE_AUDIT Connect ideas 1 to 7: guided connect by hosting with a live checklist (version, rights, apps, mail), health chips, agency groups and search, "Connect a test copy", failure guides (wrong URL, two-factor on, API key missing, IP blocked), credential rotation and expiry warnings, CSV import of many connections.

**Built.** Hosting picker (Odoo Online, Odoo.sh, My own server) with URL and version auto-detect and a saved choice; failure guides `two_factor`, `ip_blocked`, `db_missing` (`lib/connectScreen.ts`); saved-list search (more than 3 rows); a health chip per row; "Run checks" per saved connection (`GET /live-check`: version, rights, apps, mail); "Group (optional)" saved as `group_label` with grouped, sorted lists; "Connect a test copy"; test-copy checkbox; `SlowHint` on loading (touch 66); arch on the empty state; API key guide that opens Odoo to create a key (Ingenium never mints Odoo keys).

**Real status.** [Done, code] for the features. [Not acceptable] for quality: Tope reports the Connect page freezes [Reported by Tope]. The list endpoint returns 16,014 rows in one 10.5 MB response [Verified 21 Oct], which a page rendering every row as a card cannot handle. [Inferred cause]

**Known bugs.** Frozen page; unpaginated list; junk test connections fill the list (P0-3); no virtualisation; credential rotation, expiry warnings and CSV import not built.

**What's left.** Paginate and virtualise; clean junk rows; rebuild the page to the section 5 standard (single primary action, hosting-first wizard, cards with health); rotation and expiry warnings; CSV import for agencies; a "sample database to explore" option (FEATURE_AUDIT Login 3).

### 3.3 App Studio (and Draft Studio)
**Intended premium spec.** A non-technical owner types or dictates a brief, in any style, and gets a correct Odoo app design: stock Odoo first, custom models only for things the owner keeps rows of, fields, views, menus, security, standard automations, a preview that looks like Odoo, an install on the live database with a test-run receipt, a money guard and approval, and a full revert. At most three questions, each with a recommended default; everything else becomes a visible, editable assumption; "maybe later" items are listed as left out, not built. Section 8 covers the reliability problem in depth.

**Built (pipeline, `app/ai_conversation/`).** Brief kept verbatim (`brief_checklist.set_original`, `source_brief()`); optional AI expansion held separately (`brief_expand.py`); understanding and intent contract (`understand.py`, `intent_contract.py`, `intent_llm.py`, `clause_grounding.py`, `conflict_look.py`); question gate and assumptions (`intent_gate.py`, `clarify.py`); diagnosis (`diagnosis_decision.py`, `capability.py`, `stock_routing.py`); one design LLM call (`app_design.py`); repair and validation (`validate_and_repair`, `design_quality.strengthen_design`, `dedupe_fields`, `ensure_jobs`, `complete_from_brief`, `scope_and_limits`, `_merge_outline`, `_cover_sections`, `design_scope.py`, `design_refresh.py`); model authorizer (`model_authorizer.py`, shadow only); orphan repair (`orphan_repair.py`, off or shadow); install step (`install_step.py`, `POST /{id}/install-apps`); apply and revert with dry-run receipt (`spec_apply_ui.py`, install journal); refine (`refine.py`). Agent mode (`studio_agent.py`, flag `INGENIUM_STUDIO_MODE=agent|pipeline`, default pipeline). UI: `components/studio/*` including `AppDesignPanel`, `AgentPlayback`, `InstallStepCard`, `StudioApplyBar`, `DesignPreview` (via `lib/design-preview.ts`), "Open in View Designer" hand-off (`?draft=key`, `DesignerDraftHandoff`).

**Real status.**
- End-to-end install path: [Done, live 17 to 20] for "add to an existing app" briefs (CRM extend, Maintenance on 20) in S12 and S12b, including the install-app step, the gate, design refresh after install, reminder offsets (−7 on 17 and 18, 7 plus "before" on 19 and 20) and a real activity created by the automation.
- Design quality on fresh briefs: [Not good enough]. Latest comparable numbers (20 Oct head-to-head, dev plus dev2, 28 briefs, k=3, fresh): pipeline coverage 0.484, invented models per run 0.417, entity recall 0.527, stability 0.534, mean latency 88 s. Handoff numbers on the sealed holdout after the h-fix: coverage 0.528, unauthorized invention 0.433, invented severity 1.88.
- Model authorizer: [Done, code; OFF]. Offline replay cut invention (0.739 to 0.162 per run) but failed the false-fold gate (0.234, limit 0.10) and dropped coverage on 6 briefs.
- Brief-contract fix: [Partial, paused at a clean point 19 Oct 15:30]. Contract quotes now resolve against the owner's original words; role repair exists. Offline check, subset k=5 re-record and gates not run.
- Shadow mode on real sessions for a week: [Missing] (waits on Tope).
- Fresh holdout (`evals/v2/holdout_fresh/`, 13 briefs, MANIFEST hash `bf494739…3b2399`, gold DRAFT): exists, sealed, never run.
- Agent mode: [Done, code; lost the head-to-head]. Deferred re-run (section 4, P2-3).

**Known bugs (open).**
- A detail mentioned once becomes its own model with invented fields (salon "Salon Service" and "Stylist Schedule", NGO "Food Pack Type", generator "Generator Log" and "Resident Share"). This is failure A in section 8.
- Run-to-run variance (failure B).
- Computed counts drift into `python_needed` (failure D).
- Answer cache hit despite `--fresh` (pipeline extend_sales reps at 0.5 s with 1 LLM call): the fresh header does not bypass that cache. [Open]
- "Skip view <model>.form.extension: refusing to rewrite stock model" warning still shows although fields land via the inject (S12b note; a 19 Oct fix says the warning no longer fires for extension views; re-verify).
- Pre-install design can pick the wrong host (res.partner before CRM); harmless because the gate blocks and refresh fixes it, but confusing.
- `studio-draft.ts` was reformatted by a non-repo Prettier on 19 Oct and two methods (`decideStudioStockApp`, `startOptionABatch`) were recovered from a webpack cache. Tope should eyeball this file's diff. `startOptionABatch`'s return type is reconstructed.
- Restaurant, project_tracker and retail_supermarket packs are rejected (stock apps cover them) and only recommend "Use stock app X".
- Fixed but worth regression tests: reminder offset lost, junk fields from non-field phrases (`x_to_each_opportunity_a_field_for_source`, `x_remind_the_salesperson_a_week_before_t`, both from sentence-length labels), JSON-2 `vals_list` 422 (was a deliberate empty probe), one TTL.

**What's left.** Section 8 target architecture; finish and gate the contract fix; shadow week; fresh holdout run; the "App Studio contract fix" item in section 4 (P1-1); answer-cache fresh bypass; agent-mode re-run after the cache leak is fixed and an eval DB API key exists; Draft Studio folded under App Studio ("Saved drafts", "Advanced: app plan", FEATURE_AUDIT 14).

### 3.4 View Designer (form, list, kanban, search, dashboards)
**Intended premium spec.** SPEC.md sections 2 to 20. A Figma-led editor on a shared view engine that renders real Odoo arch faithfully for 17 to 20 with live records, turns every edit into the smallest safe inherited view (name-based anchors, never `replace` on stock, inline conditions, never `attrs`), validates, publishes as an inactive preview, checks fidelity by re-reading Odoo's combined arch, then promotes. Layers, Fields and Add panels; a canvas at 50 to 200 percent; Properties, Show and hide, Who can see, Checks; role preview; 17 to 20 version view; desktop, tablet and phone frames; usage suggestions from `read_group` counts; layout checks; undo and redo, named versions, compare, revert; pinned comments; Cmd-K with plain-English edits (AI proposes typed ops, code validates). Premium additions (section 16): widget picker with live preview, inline field create, related fields by drag, smart buttons and status bar editing, Tidy up, screen health score, list designer, kanban card designer, search designer, translations side by side, history scrubber, upgrade guard, reusable sections, move a layout between databases, presence, heavy-field performance hint. Section 17: a full component library at least equal to Odoo Studio's set and "new screen from blank". Section 18 and 19: 19 plus 20 approved ideas.

**Built.** Engine (`view_engine.py`, `view_engine_2c.py`, `view_engine_2d.py`, `view_engine_logic.py`, `view_engine_access.py`, `view_engine_ai.py`, `view_engine_library.py`, `view_engine_portable.py`, `view_engine_store.py`; routers `view_engine*.py`, `views.py`, `preview_proxy.py`). UI: `components/view-designer/*`, `components/designer/*`, `components/odoo-preview/*`, `ViewDesignerShell`, `EngineCanvas` (cursors), `WhoCanSeePanel`, `HistoryPanel` (scrubber), `AIEditBox`, `SaveAsComponentButton`, Builder2c sheets (pivot), heatmap overlay, Tidy up, health score, `HealthArch` on Checks, fill-rate bars on "Fields not on screen" (`GET /connections/{id}/models/{m}/fill`), multi-select count pill, keystone moment on first publish, publish toast "You can also undo this later in History".

**Real status (GAP_AUDIT section 1, D 17, P 11, M 6, plus G9).**
- [Done, live] Stage 1 structure, Stage 2 logic (conditions, role preview, history, comments, command bar, proof loop), 2b, 2c, 2d ideas, Edit with AI for views, reports and emails.
- [Done, live] Stage 3 to 4 live checks (G9): axe contrast light and dark on form, list and kanban; keyboard-only walkthrough with visible focus; INP under 200 ms (`e2e/designer-stage34.spec.ts`, 9 of 9 pass on an isolated build). Dark theme failed first (1.1:1 and 2.25:1 on the white Odoo sheet) and was fixed by pinning paper ink to Odoo's ink inside `.ofp-sheet`.
- [Missing] widget picker with live preview; list designer (widths, optional columns, totals, row colours, inline edit, default grouping); search designer; number tiles (19.6); hide never-filled fields (19.7); stage checklist (19.8); report from a photo or PDF (19.14).
- [Partial] inline field create and related-by-drag (not confirmed); kanban card designer (engine supports kanban, no designer UI); translations side by side (only `ConfigScheduledI18n`); upgrade guard (version_watch exists, no re-check-and-fix flow in the designer); heavy-field performance hint; full Studio-parity component library and new screen from blank; scheduled publish, A/B layout test and digest (one weak hit each); three named approvers (needs sign-in).
- [Open decisions, SPEC 14] reading up to 80 live records in the browser; one live reference page for DESIGN.md (Figma's editor); app orange `--brand #f97316` next to cinnabar.

**Known bugs.** Dark-mode paper contrast (fixed G9; keep the test). Margins overlay for the PDF proof deferred because the PDF viewer's page offset is unknown (touch 131). `/designer/classic` now redirects to `/designer` (backup at `/tmp/designer_classic.bak` on the Mac; that file may not survive a reboot).

**What's left.** All [Missing] and [Partial] items above, built to the SPEC wording, live on 17 to 20; Studio-parity library; blueprint mode and canvas cursors are built, keep them.

### 3.5 Report Designer, QWeb print layouts and the email designer
**Intended premium spec.** SPEC 5 and 16: a paper canvas at true page size, blocks anywhere in the body, line tables with chosen columns and totals, conditional blocks, QR code, barcode, signature, page numbers, watermark (Draft, Paid); a Proof pane showing the real PDF from Odoo for a chosen record, debounced 1.2 s, with page checks (rows split across pages, content in header or footer zones, page count change, images over 2 MB); language, currency and company previews; brand once through Odoo's own `base.document.layout`; before and after compare (poppler raster, side by side or slider); starter gallery (invoice, quotation, delivery slip). Emails share the same blocks and brand with desktop and phone previews, real-client frames (Gmail, Outlook, iPhone Mail, dark mode) and "Send me a test" (touch 132). QWeb raw page templates become an "Advanced: page templates" tab inside Report Designer using the code runner's editor (FEATURE_AUDIT 6.2).

**Built.** `report_design.py` (block spec to QWeb, `INHERIT_SLOT_MAP`, grounding, unsafe gate), `view_engine_report.py`, `view_engine_report_blocks.py`, `view_engine_pdf.py`, `routers/view_engine_reports2.py`, `odoo_client.report_render.render_report_pdf`, `ReportDesignerShell` (page breaks), `BlockEditor`, `EmailDesigner`, `QwebPaperPreview`, `ReportCanvas`, `AIEditBox` for reports and emails (`ai_edit_blocks.py`), proof on a desk at A4 proportion with a paper shadow, explain sheet as a PDF (`view_engine_2d`), test email to one typed address, Slack or Teams digest webhook, offline banner with Retry. Report table inspector has `ScrubNumber` on column width.

**Real status.** [Done, live] for blocks anywhere, conditional blocks, QR and barcode, watermark, email previews (GAP_AUDIT section 1 row "reports"). [Partial] for real-client email frames (touch 132 not logged done), print-grade typography (touch 130 not logged), QWeb views folded into Report Designer (old `/reports`, `/mail-templates`, `/qweb-views` pages still exist and are in the menu, `nav.ts`). [Missing] report from a photo.

**Known bugs.** `report-designer/EmailDesigner.tsx:226` (`emailSendMeTest`) had two `tsc` errors from another worker's in-progress edit on 20 Oct 15:59 (G6 note). Verify `tsc` is clean before anything else.

**What's left.** Retire the three old pages (redirect, remove from menu); QWeb advanced tab; real-client email frames; print-grade proofs (hyphenation, hanging punctuation, decimal-aligned money, no widows); margins overlay once the PDF page geometry is known; report from a photo through the wireframe reader.

### 3.6 Website builder
**Intended premium spec.** FEATURE_AUDIT 7: create pages from templates with View Designer-style blocks, phone, tablet and desktop preview, publish through approval and scheduled publish, SEO and speed check, website menu editor, AI page from a brief, forms builder that creates Odoo records, translations side by side, version history and undo, accessibility check, redirect manager. Note: SPEC 12 put a website or page builder out of scope for builders v1; FEATURE_AUDIT (approved "all", 17 Oct) adds the upgrades. Treat FEATURE_AUDIT as the newer decision but confirm scope with Tope before a big build. [Inferred]

**Built.** `connections/[id]/website` (81-line page at audit time), `routers/website.py`, `website_blocks.py`: list pages, edit blocks, upload images, publish.

**Real status.** [Partial, thin]. Publish is direct. No create page, preview, SEO or menu editor.

**What's left.** Everything in FEATURE_AUDIT 7 and 7+, with publish through the write gate.

### 3.7 Configuration Suite (all stages and ideas)
**Intended premium spec.** CONFIG_SUITE_SPEC: an "operate-mode control room" with a suite home plus workspaces: **Set up** (Bulk Setup engine), **Ask** (Copilot, Search, Help me decide), **Explore** (Inspector, What this database can do, Look closer), **Change records** (Move records forward, Edit a field on many records, Merge duplicates, Schedule activities, Give portal access, Record editor, plus security, message and recompute tools), **Upkeep** (Scheduled actions, Files and storage), **Safety** (Check a change, After an upgrade, Before you upgrade, Money guard, approvals). One flow everywhere: Pick, Choose, Check, Run, Review. Four safety levels. Runs tray. Passport chip with the exact version string. Writes On or Off. Copilot side panel with screen context.

**Built.** API: `routers/suite.py`, `suite_change.py`, `suite_upkeep.py`, `suite_insights.py`, `suite_records.py`; modules `suite_catalog.py` (254 tasks parsed from the catalog, dependency ranks, version mechanisms), `suite_setup.py`, `suite_workbook.py`, `suite_import.py`, `suite_change.py`, `suite_upkeep.py`, `suite_ask.py`, `suite_insights.py`, `suite_store.py`, `suite_playbooks.py`. Web: `components/suite/*`, routes under `connections/[id]/suite/` (home, ask, setup, explore, explore/capabilities, explore/insights, explore/models/[model], change/[tool], upkeep/[area], safety/check, upgrade, money, approvals, states).

**Real status by stage.**
| Stage | Status | Evidence |
|---|---|---|
| Stage 1 structure (shell, routes, redirects, passport, catalog, plans, workbook) | [Done, live] 44 of 44 checks on 17 to 20 | builders PROGRESS Config Suite stage 1 chunk 3 |
| Stage 2 logic (Check, Run, Review for all Change tools, undo, duplicates, activities, portal, schedules, files, money guard, AI 9.1 to 9.4, decision guide, approvals) | [Done, live] 18 of 18 on every version | PROGRESS G4 |
| Stage 2B Bulk Setup (waves, check by mechanism, apply board, undo plan, money guard, import documents, workbook) | [Done, live] for the 20.12 list: NG package with zero invented taxes, bad-row workbook, units per version, access roles (including `ir.access` on 20), order, forced mid-run failure, undo, money guard, no receipt no write, mixed `.docx` import | PROGRESS G4, G8 |
| Stage 3 styling (tokens, type, states, copy, icons, zero-jargon scan) | [Partial]. Suite module CSS, states preview, copy scan test exist. `impeccable detect` and measured contrast runs are not logged for the suite. | builders PROGRESS suite stage 3 chunk 2 |
| Stage 4 polish (motion, a11y, Cmd-K batch plans, Check on every version, Before you upgrade) | [Done, code] G9: `EveryVersion.tsx`, Cmd-K "Batch plans", live regions, 160 ms fades, reduced motion. Keyboard-only walkthrough of a full Change run and INP on a 5,000-row virtualised table are not logged. | PROGRESS G7, G9 |

**Ideas 1 to 34 (section 16), status.**
- Built (look only, "Look closer" page, live 15 of 15 routes on 17 to 20, G9): 5 data quality board, 8 archive dependency check, 10 two-database compare, 12 role x-ray, 13 access hygiene, 15 numbering check, 17 translation coverage, 18 automation catalogue, 19 unused apps, 20 custom field clean-up, 21 storage forecast, 22 import aftercare, 24 record time-travel, 29 Day-1 review, 33 hot-spot heatmap.
- Built earlier: 2 scheduled batch runs (Send later, repeat, reschedule), 3 team recipes, 26 run time estimate, 14 mail health (partial), 23 "why is this record stuck" (Co-Pilot only).
- [Missing]: 1 rehearsal replay, 4 filters from words with a live count, 6 leaver playbook, 7 bulk reassign owner, 9 tag manager, 11 handover pack, 16 multi-company consistency, 25 watch this, 27 shareable check result, 28 client mode for the suite, 30 Copilot memory per database, 31 approval in chat (Slack, Teams), 32 undo all of today, 34 explain this setting. (27 to 34 were "not grepped individually" by GAP_AUDIT; treat as missing until proven.)

**Ideas 35 to 48 (section 20.14, all approved), status.**
- Present: 39 plan from an existing database (`config_as_code` importers), 40 client sign-off (PlanLedger), 41 offer our Check to Odoo 20 agents (partial MCP check), 47 source-linked records (provenance chip).
- [Missing]: 35 re-run means only what's different (unverified), 36 setup rehearsal on a throwaway copy, 37 one plan many companies, 38 setup progress score, 42 out-of-hours setup window, 43 industry starter plans (unverified), 44 setup handover chapter, 45 email-in import address, 46 spot-the-difference on re-upload, 48 import health after go-live.

**Known bugs.** Fixed live and worth regression tests: suite store re-kinded rows into a 16-character column (every suite call 500'd on Postgres), steps needing a model installed in an earlier wave were Blocked, workbook duplicate rows, update-after-create, prefixed import headers, access op policy key. Open: suite runs still use the suite runner and the builders' approvals list, not the changeset executor, inbox and policy (Oct 19 item 4).

**What's left.** All missing ideas, writes through Change batches and the write gate; suite Stage 3 measured contrast and `impeccable`; Stage 4 keyboard walkthrough and 5,000-row INP; executor and inbox integration.

### 3.8 Imports: "Bring data in" and the accounting-import rules
**Intended premium spec.** One "Bring data in" flow (FEATURE_AUDIT top-5 #4): drop any files or forward an email, Ingenium sorts them, maps, checks with Odoo's own test import, runs and undoes. Any document for any database (CONFIG_SUITE_SPEC 20.13): candidates from the catalog and live DB (no closed list, no Contacts fallback), questions never guesses, answers remembered per layout, Ingenium external ids, undo by external id, source-linked records. Extras: cleaning step, match against existing records with a review queue, opening balances wizard (only through Odoo's import, under the money guard), email-in importer, Google Sheets and OneDrive live source, OCR from photos, big-file mode, template downloads, import report PDF.

**Built.** `suite_import.py` and the setup `import` step (paste, CSV, XLSX, DOCX, PDF text; questions for unknown columns; Check = Odoo `base_import` dry run; Apply with `__ingenium_import__` ids; Undo by those ids). Older `ingest/` pipeline (classify, extract, map, order, dry-run, commit; local vision OCR off by default; layout memory; chart-of-accounts alignment; opening balance as draft on the Opening journal; stock counts via `action_apply_inventory`) and `data_import.py`, `image_import.py`. Import commit runs the shared write gate. Accounting-import rules as in section 2.4.

**Real status.** [Done, live] for the suite import path (mixed `.docx`, bad rows). [Partial] for the merge: the nav label says "Bring data in", but Import (`/import`), Ingest (`/ingest`) and the suite import are still three flows (GAP_AUDIT section 4). The CONFIG_SUITE_SPEC says `/ingest` should redirect to Set up.

**Known bugs.** Ingest still has the closed list of 11 document types and the Contacts fallback unless the redirect is done [Inferred from spec limits list; verify]. Updated import rows were not undoable until Oct 20 z.

**What's left.** One flow; redirects; email-in address (idea 45); spot-the-difference (46); import health (48); cleaning step; match and review queue; big-file mode; opening balances wizard; import report PDF.

### 3.9 Bridge (integrations, flows, delivery queue, approvals, handbooks)
**Intended premium spec.** BRIDGE_RUNNER_SPEC 32 items: connector gallery (Shopify, WooCommerce, Stripe, Paystack, Flutterwave, QuickBooks, Xero, HubSpot, Salesforce, Slack, Teams, WhatsApp, Google Sheets, banks, shipping, payroll); any app from API docs, OpenAPI, Postman or a sample payload (AI reads, code builds and checks); guided auth, vault, token refresh; health check on connect; a **Figma-quality visual flow canvas with live data**; plain-words flow drafting; field-mapping studio; matching rules and review queue; direction and conflict rules; triggers (webhook, schedule, Odoo change, manual); delivery engine (retries, backoff, durable queue, idempotency keys, ordering, pacing); dead-letter inbox with fix and replay; contract tests; schema drift alerts; sandbox run; versioned flows with review, approvals, gradual rollout and rollback; safe backfill; money guard plus reconciliation; live monitor; end-to-end record trace (touch 58 transit map); alerts; daily reconciliation; uptime and SLA; owned middleware service generator (Docker, deploy, logs, health); generated Odoo module; documented code export plus handbook PDF; recipes; integration score; Odoo 20 agent calls; quota and cost watch; data residency and PII masking; client mode.

**Built.** `app/bridge/`: `gallery.py` (16 connectors), `live_probe.py`, `spec_import.py` (OpenAPI 3, Swagger 2, Postman 2.1, sample payload; refuses http, private hosts, over 5 MB), `mapping.py`, `sync_rules.py`, `reliability.py` (dead letters, replay, contract tests, drift, sandbox run), `flows.py` (versions, propose, approve, rollout 0, 5, 25, 50, 100 percent, rollback, backfill plan, reconcile, trace, monitor), `ops.py` (alerts, digest, Slack and Teams payloads composed not sent, reconciliation report, SLA, quota watch, PII masking, client-mode guard), `drafting.py` (AI draft checked by code, 11 recipes, integration score), `export.py` (FastAPI service with Dockerfile, Odoo module LGPL-3, handbook markdown), `canvas.py`, `delivery.py` (durable engine on `integration_events`: idempotent submit, one at a time per record oldest first, backoff 2 s to 15 min with jitter, dead after 6 tries, pacing), `tokens.py` (6 OAuth providers, reuse until 2 minutes left, "Sign in again" on 400 or 401). Web: `/bridge/gallery`, `/bridge/mapping` (`MappingStudio`), `/bridge/flows` (`FlowsBoard` with a simple SVG canvas, monitor, versions, Approve as second person, Hold to roll back, record trace, "Last hour" sparkline with a table switch), `/bridge/contracts/new`.

**Real status.** [Done, live on 17 to 20] for health probe, mapping, matching, sandbox, reconcile, generated module install. [Done, code] for the delivery engine and token refresh (G5). [Partial]: the **canvas is a simple SVG, not Figma-grade** (no flow-canvas library); drift alerts generic; live monitor and SLA thin; OAuth refresh only in `tokens.py` (not proven against real providers); middleware generator produces a Dockerfile per the 19 Oct log but GAP_AUDIT found "no Dockerfile output" by grep (verify); PII masking in logs via `scrub.py`. [Missing] **AI on spec import** (the importer is deterministic only). Second approver when sign-in is off is a typed-name stopgap. Bridge is not in `nav.ts` (top-level `/bridge/*` pages only). [Verified 21 Oct]

**Known bugs.** Second-approver rule cannot identify people without sign-in. Payloads for Slack and Teams are composed but not sent (by design until approved). Paystack has no stock Odoo payment module on any version (S4.1 probe), so Paystack flows must go through Bridge.

**What's left.** Figma-grade canvas; AI spec import; real OAuth round-trips; handbook PDF (sealed, touch 134); nav entry; live monitor and SLA screens; drift alerts with proposed fixes; gradual rollout UI polish; WhatsApp and Google Sheets connectors proven live.

### 3.10 Code Runner
**Intended premium spec.** BRIDGE_RUNNER_SPEC 29 items: Monaco with Keystone theme, tabs, minimap, split, palette, multi-cursor, Vim and Emacs keys; Odoo-aware autocomplete from the live DB; live lint; version view; inline AI as accepted diffs; snippets; command bar; test run by default; safety meter and money guard; real runs through approval, receipt and undo; batches with progress, pause, resume, stop; resume failed runs; estimates; results table; before and after diff; rich console; record links; performance profile; script library with versions; promote to scheduled job, server action or button; parameter forms; share across connections; gallery; live co-editing and line comments; audit trail; notebook mode; script tests on a disposable copy; secrets vault; local AI default, cloud with consent.

**Built.** `app/code_runner/` (`schema`, `lint`, `versions`, `snippets`, `ai`, `child` (own process, import allowlist, forbidden-RPC policy), `runs`, `store`, `vault`, `library`, `promote`, `testing`), `routers/code_runner.py`, `components/code-runner/*` including `CodeRunnerEditor` and `R3Panels.tsx`. Monaco 0.52.2 pinned (0.57 breaks `monaco-vim`), loaded locally.

**Real status.** [Done, live 17 to 20] for items 1 to 18 and the R3 backend (GAP_AUDIT: D 25, P 4). [Partial]: 24 live co-editing (comments plus a 4-second poll with conflict bar, not real-time), 18 per-line profile exists but GAP_AUDIT found no symbol (verify), 1 split and minimap unverified. R3 screens built but **never clicked through in a browser** ("token rule: no screenshots").

**Known bugs.** "Dry run" stands in for a rolled-back transaction because Odoo's API cannot roll back: writes are intercepted on an observer connection. Make sure the UI says so honestly. Query counts are not available over Odoo's API (call counts shown instead).

**What's left.** Browser click-through of every panel with screenshots; real-time co-editing; profile verification; the old `script-runner` and `code-studio` pages folded or redirected.

### 3.11 Ingenium Bots, Expert mode and avatars
**Intended premium spec.** SPEC 20.2 and touches 7, 104, 105, 107, 109, 110, 112, 113: a distinctive avatar set in the Keystone family for Ingenium Expert and each bot (expert, ask, builder, inspector, runner, guard), arch-masked (humans in circles), live state machine (idle, thinking, working, done, needs you) as one Rive file; visible steps instead of a spinner; honest three-bar confidence; provenance chips "Drafted by Expert, checked by code"; presence without nagging; steer while it works; one calm voice. Backend: bots act only within an intersected grant (risk ceiling, ops allowed, apps allowed, autonomy cap).

**Built.** `components/suite/BotAvatar.tsx` (arch tile per touch 7, per-bot sign glyphs, states, sizes 16 to 48, light and dark), `BOT_SPECIALTY` lines, `ConfidenceMark`, `ProvenanceChip`, pencil-hatch for AI drafts, Ask live steps from real events (`POST /suite/ask/stream` NDJSON; "Change course" while running; Esc stops), "Instant, 0.04 s, free" tag on real cache hits. Backend `app/bots/grant.py`, `app/worker_bot/`, `app/skills/`.

**Real status.** [Done, code] for the avatar component and grant model. [Missing] the Rive state-machine file (touch 104 is a BIG item; current avatars are CSS states). [Partial] step streaming exists only for Ask; other bots have no step events (touch 105 logged "needs API step events" before G9; Ask now done).

**What's left.** Rive avatar file with the five states; step events for builder, runner, setup and Co-Pilot; bot cursors in shared editing (touch 77); a bots catalogue page that explains what each bot may do (its grant) in plain words.

### 3.12 Live Demo Co-Pilot (Vexa self-hosted; whisper panel by default)
**Intended premium spec (Q7 scope change, Tope, 20 Oct).** A self-hosted open-source bot joins Zoom, Teams or Meet from an invite link as a visible named participant with a listening notice; live transcript with speaker tracking; detects Odoo questions from client-side speakers only; answers from the existing engine (stock catalogue plus the live demo DB snapshot) with four labels ("In your demo", "Standard Odoo, not set up yet", "Possible with customisation", "Not available") and the AI guards (topic guard, injection classifier, PII redaction); a **private whisper panel to the presenter by default**; meeting chat and speak-aloud opt-in per meeting; after-meeting summary, Q&A, a draft follow-up email (never auto-sent) and a starter plan. Kept from Tope's add 2: a **demo builder** that reads a BRD or SOW (any format) plus a target Odoo DB (often free Odoo Online), makes a demo plan (apps, Bulk Setup config, App Studio and View Designer tweaks within hosting limits, labelled demo data, a demo script mapped to the BRD), shows it for approval, builds it with check and undo, ticks requirements off a coverage view as they are shown, and removes all demo data in one click after the call. Plus calm presenter mode, demo scripts per industry, objection library, CRM link, practice mode, language support (FEATURE_AUDIT 16 and 16+).

**Built.** `app/live_demo_copilot/` (`vexa_client.py` (Vexa, Apache-2.0), `attendee_client.py`, `bot_backend.py`, `bot_status.py`, `db_grounding.py` (installed modules, four labels set by code), `stage1_filter.py`, `stage2_answer.py`, `after_meeting.py`, `leave_purge.py`, `webhook_crypto.py`, `pipeline.py`, `service.py`, `store.py`, `events.py`), `routers/live_demo_copilot.py`, `components/live-demo-copilot/*`, `/live-demo-copilot/overlay` (PresenterOverlay sets `html[data-presenting]`, which mutes sounds). Disclosure lists where answers go: private panel on; meeting chat and speak-aloud shown honestly as not available with the current bot.

**Real status.** [Partial]. Routes exist and tests are mocked. **Never joined a real meeting** (no Vexa or Attendee server deployed). Vexa 0.12 docs checked: chat write and speak return 404 (chat read only), so both stay "not available". Licences checked from LICENSE files: Vexa Apache-2.0 (allowed), Attendee Elastic License 2.0 (avoid per licence policy), MeetingBaaS meeting-bot-as-a-service has no licence (avoid). [Missing] demo builder, requirement-coverage view, one-click demo-data undo (GAP_AUDIT section 4). The numbered "test bench" panels FEATURE_AUDIT criticised: P1 calm presenter mode planned, logged progress unclear [Inferred: verify on screen].

**Known bugs.** `attendee_client.py` exists although Attendee is ELv2; keep it unused or remove it after Tope agrees (section 6.12).

**What's left.** Deploy Vexa self-hosted on the Mac (needs Tope's go) and run one real meeting test on each of Zoom, Teams and Meet; demo builder; coverage view; one-click demo undo; after-call pack wired to `DraftExternalMessage`-style drafting (never auto-send); calm presenter mode; practice mode.

### 3.13 Wireframe to build (premium)
**Intended premium spec (Q6 spec).** On App Studio "Start from a sketch": an image (png, jpg, webp, heic) or PDF (up to 10 pages, 10 MB). (1) Shared AI client vision call returns strict JSON `{screens:[{title, kind: form|list|kanban|dashboard, regions:[{label, widget, field_guess, required?}]}], notes, unreadable[]}`. (2) Map each label to stock fields via the stock-first catalogue and live `fields_get`: reuse, extend a stock model, or a new `x_` field with plain names. (3) Emit the existing AppDesign (stock extension or custom module per hosting) through every App Studio gate, then an Odoo-style preview with the sketch side by side and each mapped region highlighted. Unmapped regions become at most 3 questions. Guards: PII redaction on OCR text, injection classifier on extracted text, size cap, no storage beyond the session unless saved. Also: hand off to View Designer as a draft screen; merge with "report from a photo" into one "From a picture" entry; multi-page and handwritten forms; whiteboard photo to App Studio brief.

**Built.** `app/wireframe/` (`reader.py`, `stock_map.py`, `compile.py`, `review.py`), `wireframe_live.py`, `routers/wireframe.py` (status, read, clarify, map), `components/wireframe/*` including `StockMapPanel` (outlines valid `[x,y,w,h]` boxes, never guessed; hover strengthens the row), `connections/[id]/wireframe`. Vision accepts Vertex as well as a Studio key, always through the shared client; Anthropic only if `ai_vision_provider` opts in.

**Real status.** [Done, code] "all Q6 spec items present" (Oct 20 p). No live end-to-end run on 17 to 20 is logged. Wireframe is still not in `nav.ts` [Verified 21 Oct], so users cannot find it.

**Known bugs.** One `StockMapPanel` vitest error noted during G9 "from another worker". Verify.

**What's left.** Live 17 to 20 proof (sketch to installed app); nav entry inside App Studio; hand-off to View Designer; "From a picture" merge with report from photo; fixture sketches (hand-drawn and Figma export) with golden JSON as the spec requires.

### 3.14 Approvals
**Intended premium spec.** One Approvals inbox with two tabs, "Approvals inside Odoo" (Odoo's own approval rules) and "Approvals for Ingenium changes" (designers, suite, Bridge, imports), each with before and after; approve from email, Slack or Teams; snooze; named approvers per record type (needs sign-in); second approver rule; self-approval only for accounting setup imports (section 2.4).

**Built.** `/approvals` (hash-bound plan approvals), `connections/[id]/approvals` (Odoo approval rules), `connections/[id]/suite/safety/approvals`, builders approvals (`view_engine_2c` `APPROVAL_ACTIONS`), `routers/approvals.py`, `routers/inbox.py`, `approval_service.py`, `ai_approval_flow.py`. Snooze on Approvals (device-only view setting, tomorrow 8:00 WAT or 2 hours; says the approval still waits). Favicon approvals badge.

**Real status.** [Partial]. Three approval places still exist (FEATURE_AUDIT 5 and 21). The rename and merge are not logged as done. Approve from chat is [Missing] (suite idea 31).

**What's left.** One inbox; rename the Odoo rules page "Approvals inside Odoo"; before and after on every item; chat approvals with signed links; delegation and escalation (FEATURE_AUDIT 5+).

### 3.15 History
**Intended premium spec.** One timeline for every write from every page (receipt, diff, undo), filters by person, page and record type, readable diffs, "Undo this" and "Undo from here", undo all of today, tamper-proof export for auditors, time-travel view, plain-language search ("who changed tax settings last month?"), retention settings (FEATURE_AUDIT 10, A4).

**Built.** `routers/history.py`, `HistoryTimeline`, `routers/snapshots.py`, `journal` page (to be renamed History), `audit_chain.py` (hash-chained; side copies expire without rewriting the chain, commit `e28c9bd`), record time-travel (idea 24, look only).

**Real status.** [Partial]. Per-page snapshot panels removal not confirmed; "Undo from here" and "Undo all of today" [Missing]; auditor export [Missing].

**What's left.** Remove per-page panels and point them at History; undo from here; undo all of today; signed export; plain-language search through Ask.

### 3.16 Cmd-K ("Find anything")
**Intended premium spec.** A13 and touch 85: Cmd-K searches pages, models, records, menus, automations, settings, docs and past runs, and also acts ("archive inactive contacts" opens a checked plan); nested pages, recent items, a live preview pane, per-item actions; keycaps by platform; go-to pairs.

**Built.** `CommandPalette` in `AppShell` (cmdk): pages, records (contacts, products, orders, invoices, leads, projects, employees; read-only name search, opens in Odoo), History changes, Batch plans (Setup plans and Change batches). G-then-key go-to pairs (G H, G A, G B, G S, G C), hold-for-hints, shortcut sheet on "?", keycaps.

**Real status.** [Done, code] for search depth (A6). [Partial] for the Raycast-grade behaviour: no live preview pane or per-item actions are logged; the database switcher is not discoverable (Tope reports an undiscoverable switcher) [Reported by Tope].

**What's left.** Preview pane; per-item actions; "acts" for plain-language commands through the write gate; settings and docs search; a visible database switcher in the sidebar and in Cmd-K (section 5.4).

### 3.17 Domain packs and the trusted (curated) list
**Intended premium spec.** Stock-first starter packs per industry that App Studio and Draft Studio can use without inventing models that duplicate stock Odoo. Only packs on a trusted list may add satellite models.

**Built.** `ai_domain_packs.py` and per-domain packs (`ai_domain_pack_hospital.py`, `_hotel`, `_law_firm`, `_library`, `_oil_gas`, `_project_tracker`, `_purchase_request`, `_real_estate`, `_restaurant`, `_retail_supermarket`, `_subscription`, `_helpdesk`), `ai_pack_stock_first.stock_first_rework` (drop a duplicate model, repoint links to stock, move inverse fields, drop automations owned by the dropped model, add stock depends, carry unique fields as `x_` onto the stock model). `CURATED_PACKS` (11): library_management, car_rental (extends `fleet.vehicle`), law_firm, purchase_request, hospital, real_estate, hotel, subscription, helpdesk_tickets, clinic, field_service, oil_gas_operations. (The log says "All 8 admitted … 11 curated total" after naming 12; treat the code as the source of truth.) `admit_pack_models` stamps `pack_provenance`; `curated_pack_has()` re-reads the registered pack body so a payload cannot forge provenance (`tests/test_curated_pack_provenance.py`). Rejected: restaurant (stock POS Restaurant), project_tracker (stock Project and Timesheets), retail_supermarket (stock Inventory, POS, Purchase); they now recommend the stock app.

**Real status.** [Done, code]. Pack/AI suites 568 pass at Oct 20 i. Not run live on 17 to 20 as installs.

**Known bugs.** `industry_seeds` car_rental CSV was stale (fixed to `fleet.vehicle` with "Brand Model"; import creates missing fleet brand and model on commit only). `model_id/name` import needs the Fleet model in the DB.

**What's left.** Live install of each curated pack on 17 to 20; a reviewed industry starter plan per pack (idea 43); show "Use stock app X" as a first-class recommendation card in App Studio, not only Draft Studio.

### 3.18 Other Build, Data and Run pages
| Page (route) | Intended (FEATURE_AUDIT) | Built and status |
|---|---|---|
| Models and fields (`builder`) | Relationship map, field table with fill rate and "used by", plain type picker with live sample, safe rename and type change through Check and Undo, computed fields in plain words, merge with App Studio extend, model health. | List, add and edit models and fields, invoicing link panel, `<Term>` on ModelDetail. [Partial]; direct writes behind a first-write warning per audit; whether they now pass the write gate is not logged. |
| Menus | Drag tree with live app-bar preview, "see it as" role, hide unused, menu plus screen in one step, broken-link finder, Edit with AI. | Tree, create, edit, delete, `EditInPlace` title. [Partial]. |
| Access | Rules in plain words, "test as user" on a real record, visual matrix with diff, role templates, risk flags, Role x-ray and Access hygiene as tabs. | Rights, rules, groups, matrix, `ir.access` shim. [Partial]; FEATURE_AUDIT #5 "test as user" [Missing]. |
| Automations | Plain-sentence builder (Reminders folded in), test on a real record, run history, loop detector, templates, visual flow sharing Bridge's canvas. | Form composer, gate checks, migration assist, `<Term>` on AutomationDetail, plain wording "Python changes need a person to approve them". [Partial]; plain-sentence builder [Missing]. |
| Odoo approval rules (`approvals`) | Rename, plain-sentence rules, flow preview, bottleneck report. | Existing page. [Partial]. |
| Numbering (`id-generator`) | Rename to Numbering, merge with sequences and numbering check, live pattern preview, backfill under the money guard. | Live apply through the write gate; plain wording. [Partial]; rename and merge not logged. |
| Reminders | Fold into Automations as templates. | Create-only wizard. [Missing] merge. |
| Instance Config (`config`) | Becomes the Settings view of Explore. | Big backend (35 endpoints), small page. [Partial]. |
| Job Autopilot (`job`) | Client project autopilot: one brief to a plan across App Studio, Bulk Setup and Bridge. | Existing; VoussoirProgress rail; Expert-fix score dumbbell. [Partial]. |
| Projects and App plan (`projects`, `modulespec`) | Move under App Studio. | Existing pages. [Missing] move. |
| Pipelines | Plain wording, visual lanes, promote screens, plans and flows too. | Existing page; jargon fixed. [Partial]. |
| Client (`client`) | Client portal home (suite idea 28), brandable. | Thin panel. [Missing] portal. |
| Settings, Billing, Trust and safety, Admin | Tabs (Profile, Team, Keys, AI and privacy, Notifications, Danger zone), team invites, usage meter, proration preview, Paystack and Flutterwave, public safety page, real ops view. | Settings with Sound and reading, AI savings, theme picker incl. Lagos sunset; Billing API-backed. [Partial]. |
| Dashboard Studio (`/studio/dashboards`) | Hide until the dashboard designer ships. | Backend is a stub. Hide it. |
| Power Ops | Rebuild remaining recipes as Change records actions. | Locked recipes done. [Partial]. |
| Cron Manager, Housekeeping, Bulk Suite, Odoo Expert | Fold into the suite (D1). | Redirects done (Oct 19 Task 2 D). [Done, code]. |

### 3.19 LLM caching and AI guards (app-wide)
**Intended.** BRIDGE_RUNNER_SPEC caching (a to h) and guards (1 to 5).
**Status.** Caching: a shared client, b exact cache, c provider context cache, e sub-results, g savings card, h fresh answer [Done, code; live 17 to 20 for cache hits]; d semantic cache [Missing]; f batching [Partial]. Guards: 1 injection classifier [Done, core]: meaning-level families, small-model grey zone, fencing, per-paragraph withholding, `sweep_unfenced` on internal prompts (G2); 2 PII and secret redaction before cloud calls with exact restore [Done, code; live]; 3 output checker [Done]; 4 topic guard [Done]; 5 red-team pack `tests/redteam_pack.json` in the default pytest run and a CI step "AI red-team pack + guards (release gate)" in `.github/workflows/ci.yml` [Done, code]. Fence hooks exist for BRD uploads, Bridge payloads and website content but those call sites did not exist on 19 Oct; check each new AI call site uses `fence_fields(source=...)`.

### 3.20 Design touches (162 approved) status
From PROGRESS Q1, Q2 batches 1 to 27 and GAP_AUDIT section 6.
- **Built (non-exhaustive):** 1 keystone loader, 2 keystone settle on Bridge 100 percent rollout, 3 cinnabar audit, 4 15-degree cut on selected-card marker (tab indicator skipped), 5 voussoir progress, 6 HealthArch, 7 arch bot tiles, 8 grain, 11 favicon badge and dimming, 12 fonts, 13 TechName chips, 14 slashed zero, 15 Money, 16 RollingNumber, 17 and 18 tracking and wrapping, 19 Keycap, 21 RelativeTime, 23 three-layer shadows, 24 machined edge, 27 dim and desaturate backdrops, 28 and 29 hazard band and database colour, 31 image outline, 34 HoldButton, 39 flick to dismiss, 40 blur bridge, 41 Sonner, 42 snap nudge, 43 drag weight, 44 ScrubNumber, 45 check draw, 46 copied glow, 47 EditInPlace, 48 edge fade, 50 sounds (5 CC0 files from Kenney, off by default), 55 sparkline, 56 fill bars, 57 dumbbell, 59 heartbeat line, 62 ghost chart, 63 table switch, 64 dot numerals, 65 15-degree shimmer, 66 SlowHint, 68 ErrorNotice with fix and trace id, 69 offline band, 70 success sized to stakes, 72 and 73 AllClear, 75 arch 404, 76 selection and caret, 78 canvas cursors, 79 selection count (no marquee exists), 82 hold for hints, 83 shortcut coaching, 84 go-to pairs, 88, 89 shortcut sheet, 91 numbers on buttons, 92 confirmations name the target, 93 greeting, 94 undo lines, 95 specific loading verbs, 105 and 112 on Ask, 108 pencil hatch, 109 provenance, 111 instant tag, 113 bot specialty, 115 dark text weight, 117 Odoo canvas bezel and dim, 118 theme reveal, 119 Lagos sunset, 121 and 122 density (lists only), 123 focus mode, 129 satisfying checklist, 131 proof on desk (margins overlay deferred), 135 focus ring, 137 gentler reduced motion, 138 reading comfort, 139 hit areas, 141 prefetch on intent, 144 zero layout shift test (CLS under 0.05 on connect, menus, settings, approvals), 146 background work pill, 147 blueprint mode, 150 seasonal AllClear, 152 colophon, 159 snooze.
- **Open and named in your brief:** 151 year in review, 153 premium icons for generated modules, 155 Odoo screens stay Odoo (plain help and placeholders on custom fields), 157 split view, 158 "Show the request" developer switch, 161 wallet-style database switcher, 131 margins overlay (untested), 60 and 61 synchronised crosshair and history markers (blocked: need multi-chart screens), 127 welcome letter (needs Tope's own words).
- **Other open touches** (from the Q2 remaining list, after subtracting later batches; verify each on screen): 9 logo from construction lines, 10 empty-state arch everywhere, 20 typographic care, 22 brand-tinted greys, 25 glass only where layers are real, 26 lamp-lit desk, 30 wide-gamut teal, 32 cursor light on marketing cards, 33 tooltip warm-up, 35 shared-element morphs, 36 tab colour under the pill, 37 leave faster than arrive, 38 capped stagger, 49 honest page moves (needs a router hook), 51 sound logo, 52 and 53 sound rules, 54 phone haptics, 58 record journey transit map (data exists, view not built), 67 empty states with real starters, 71 stone dust, 74 partial success plainly, 77 bot cursors, 80 selection that survives, 81 ghost-cursor tours, 85 and 86 Cmd-K depth and list navigation, 87 Esc ladder, 90 named voice guide, 96 placeholders from real data, 97 tone by stakes, 98 to 102 icon layer and line drawings, 104 Rive avatar, 106 phrase streaming, 107 honest confidence everywhere, 110 presence dot, 114 basalt dark mode, 116 higher means lighter, 120 charts tuned for dark, 124 presenter density, 125 onboarding builds the arch, 126 Lagos sample company, 128 power features when ready, 130 print-grade proofs, 132 real-client email previews, 133 receipt-quality Ingenium emails, 134 sealed handover PDFs, 136 screen-reader copy review, 140 optimistic safe actions, 142 instant shell, 143 local-first search, 145 smoothness test, 148 loose keystone, 149 "ingenium" in Cmd-K, 154 generated code craft, 156 "Prepared with Ingenium" footer, 160 publishes as deployments, 162 live preview before saving everywhere.
- **Blocked by spec text:** the Oct 20 d log says "the numbered S4 touch list (1 to 162) and A2, A4, A5, A6 specs are not on disk (only their numbers here)". They are on the box in `DESIGN_TOUCHES.md` and `FEATURE_AUDIT.md`. Copy both into the repo's `docs/` (already present: `docs/DESIGN_TOUCHES.md`, `docs/FEATURE_AUDIT.md` exist on the Mac; confirm they match the box copies).

---

## 4. Remaining work, prioritised, with acceptance criteria

Rules for this list:
- **P0** blocks trust or daily work. Do these first, in order.
- **P1** is the core premium product. **P2** completes approved scope. **P3** is polish and bold bets.
- Every item ends with acceptance criteria (AC). An item is done only when every AC passes and the evidence is logged in `apps/api/evals/v2/PROGRESS.md` with the date, the command or script, and the result.
- "Live 17 to 20" always means disposable `ingenium_*` databases on the local Odoo 17, 18, 19 and 20 containers, dropped afterwards, containers returned to the state you found them in.
- Ask Tope before starting any item marked **(needs Tope)**.

### P0: trust, hygiene and performance blockers

**P0-1. Prove the repo is green before you change anything.**
Run `tsc`, the full web Vitest suite, the API pytest suite (not integration) and the CI red-team step. Record counts.
- AC1: `pnpm --filter @odoo-custom/web exec tsc --noEmit` exits 0 (the 20 Oct `EmailDesigner.tsx:226` errors are gone).
- AC2: web Vitest passes in full (last logged: 1,571 pass with 1 unrelated `StockMapPanel` error).
- AC3: API pytest failure count is written down with each failing test's file and a one-line cause. Last logged: 82 failed, 4,898 passed (Oct 20 y).

**P0-2. Fix the stale and failing tests (about 82 to 83 API failures) and the Alembic drift history.**
Known clusters (PROGRESS): direct XML-RPC in `code_runner/testing.py`, `bridge/export.py`, `routers/view_engine.py` that bypass the transport contract; version-branch baseline 37 vs 22 (`import_boundary`); pack and Expert copy tests that expect old jargon; the mastery battery; order-dependent tests (`t6_04`, `t6_07`, `test_create_session_blocks_low_ir`, `test_diagnosis_name_strips_management_fluff`); `test_ai_ollama` and `test_ai_module_generation` cases that passed only through live Vertex before AI_ASSIST off worked; 5 `understand` tests; `test_llm_provider::test_ollama_routes_bulk_vs_reasoning_and_strips_cot`.
- AC1: API pytest has 0 failures, or each remaining failure is marked `xfail` with a reason and a linked P-item, and Tope has agreed to each `xfail`.
- AC2: the suite passes twice in a row with `pytest -p randomly` (or the repo's own random-order option), proving no order dependence. If no random-order plugin is installed, run the suite in reverse file order once.
- AC3: `test_alembic_drift` passes on a fresh database created only by `alembic upgrade head`, with `init_db` ALTERs disabled. Startup schema ALTERs are removed or made no-ops once a migration covers them; the migration chain from base to head has one head (`alembic heads` prints one line).
- AC4: no test reads `~/.ingenium` (AI cache path set per test) and no test reaches Vertex unless it is marked `live_ai` and skipped by default.

**P0-3. Isolate tests from the dev App DB and clean up the 16,014 junk connections.**
Evidence: `GET /api/connections` on `:8001` returned 16,014 rows (10.5 MB) on 21 Oct, named after test fixtures ("Matrix conn", "Other client", "Granted client", "code-studio", "fake-m3", "Alice victim conn", "fake-ops", "role-matrix"). [Verified 21 Oct]
- AC1: every API test uses its own throwaway database (a per-session Postgres database or schema, or SQLite only where the code is DB-agnostic), set by `apps/api/tests/conftest.py` before the app imports settings. A test that tries to open the dev `DATABASE_URL` fails loudly (same pattern as the host guard).
- AC2: running the full suite leaves the dev App DB row counts for `odoo_connections`, `plan_cards`, audit and History tables unchanged (a test asserts before and after counts against a snapshot taken by a wrapper script).
- AC3: a cleanup script (`scripts/cleanup_test_connections.py`, dry run by default) lists rows that match test-fixture patterns and have never been used by a real session, prints counts, and deletes only with `--apply` after Tope's yes. Back up the App DB with `pg_dump -Fc` first. (needs Tope)
- AC4: after cleanup, `GET /api/connections` returns only real connections, and the count is reported to Tope.

**P0-4. Stop production test builds overwriting the dev server's `.next` folder.**
- AC1: `next.config.ts` never builds into `.next` while `next dev` runs: any `next build` started by a script, test or agent uses a separate `distDir` (for example `.next-build` or `.next-e2e-<port>`), set by the script itself, not by remembering an env var.
- AC2: Playwright's web server config and every repo script that runs `next build` set the distDir explicitly.
- AC3: test: start `next dev` on `:3002`, run the production e2e build, then load three routes on `:3002`. All return 200 with no "missing chunk" or manifest errors.
- AC4: `.gitignore` covers every new distDir.

**P0-5. Make the Connect page fast and stop it freezing.**
- AC1: `GET /api/connections` is paginated (cursor or limit and offset, default 50, max 200) and supports search and group filters server-side.
- AC2: the saved-connections list is virtualised (`react-virtuoso` is already a dependency) and renders at most what fits plus overscan.
- AC3: with 20,000 seeded connections in a test DB, the page's first useful paint is under 1 s on a mid-range laptop profile, no long task over 50 ms after load, INP under 200 ms when typing in search (Playwright plus `PerformanceObserver`).
- AC4: no hydration warnings in the console on load (section 5.12).

**P0-6. Fix the known contrast failures (Tope's rule: light-ish backgrounds always get dark text).**
Measured from `tokens.css` on 21 Oct: white on `--brand #f97316` is 2.80:1 (fails 4.5:1 for text); white on dark-mode `--brand #fb923c` 2.26:1; white on teal `#14b8a6` 2.49:1; white on `#2dd4bf` 1.86:1; white on `#0d9488` 3.74:1 (fails for normal text); teal text `#14b8a6` on `--accent-subtle #ccfbf1` 2.21:1; `#0d9488` on `#ccfbf1` 3.32:1. Passing pairs: white on `#0f766e` 5.47:1, basalt `#1a1c21` on `#2dd4bf` 9.16:1, basalt on `#f97316` 6.08:1. [Verified 21 Oct by calculation]
- AC1: a token-level rule: every surface token carries a paired `on-*` text token, and any background with relative luminance above 0.18 (roughly, anything lighter than mid-grey) pairs only with dark ink. Implemented as data, not by eye.
- AC2: an automated test (`contrast.test.ts` plus a Playwright axe run) fails the build when any rendered text has a contrast below 4.5:1 (3:1 for 24 px and up or 18.66 px bold) or any light-ish background has light text. It runs on every route in light and dark.
- AC3: the teal chip and every white-on-orange element pass AC2. Orange is never a text-on background for white text. Decide `--brand` with Tope (SPEC open decision 3); my recommendation is section 5.2.
- AC4: the known border fix (border-strong n6) stays: light 4.83 on n1, dark 4.12 on n1.

**P0-7. Fix the hydration error.** [Reported by Tope; not in logs]
- AC1: no React hydration warning or error on any route in `next dev` and `next start` (Playwright collects console messages on a crawl of all 126 routes with a seeded connection and fails on "Hydration", "did not match" or "Text content does not match").
- AC2: anything that depends on time, locale, theme, random ids or `window` renders only on the client (or uses `useId`, a fixed server value and a client effect). The Lagos-sunset theme uses the existing no-flash script and never renders a different tree on the server.

**P0-8. Stop rendering 16,000 rows anywhere.** [Reported by Tope: "rendering 16k rows"]
- AC1: every list or table that can exceed 200 rows is virtualised or paginated (audit every `map(` over API arrays in `components/`).
- AC2: a lint or test fails when a known-large endpoint result is rendered without virtualisation.
- AC3: the 5,000-row records table INP under 200 ms (CONFIG_SUITE_SPEC Stage 4 AC) passes.

**P0-9. Mac hygiene (read section 10 rules first).**
State on 21 Oct: 848 modified files, 804 untracked, 1 deleted, 1 stash, one worktree; 13 `.patch` files and 9 `APPLY_*.sh` scripts at the repo root; listeners on 3002 (web dev), 8001 (API), 5432, 5433, 5436, 8069, 8070, 8071, 8073, 11434 (Ollama). [Verified 21 Oct]
- AC1: a written inventory (`docs/handoff/WORKTREE_STATE.md`) groups the uncommitted changes by feature with a proposed commit plan. You commit nothing without Tope's yes.
- AC2: leftover dev servers and stray processes are listed with their purpose; you stop only ones you started.
- AC3: `/tmp` backups referenced by PROGRESS (`/tmp/designer_classic.bak`, `/tmp/fp_*.bak`, `/tmp/no_school_casual.gold.bak`, eval outputs) are listed; anything worth keeping is proposed for a durable location under `docs/` or `apps/api/evals/v2/` (needs Tope).
- AC4: root-level patch and APPLY scripts are listed with whether their content is already in the tree.

### P1: the core premium product

**P1-1. App Studio: the contract fix and the open bugs.**
- AC1: contract quotes come only from the owner's original words; AI expansion is context only and never quotable (already in code; prove with a unit test that feeds an expansion containing "Create a X model" and asserts no requirement quotes it).
- AC2: every model row in the contract has a role from `{record, attribute, dimension, context, future, rule, access}`; a missing role is repaired deterministically.
- AC3: the offline check and a subset k=5 re-record on dev plus dev2 run on a disposable v20 DB with the same seeds for both arms. Report with hierarchical bootstrap 95 percent CIs.
- AC4: gates (from APP_STUDIO_FIX_PLAN): invented models per run down with CI upper bound below the baseline; false_fold_rate at most 0.10 (point and CI upper); ITT coverage drop above 0.05 on at most one brief; exclusion recall stays 1.0.
- AC5: the answer cache honours `x-ingenium-fresh` (rerun extend_sales k=3 with `--fresh`; every rep makes its own LLM calls and latency is not 0.5 s).
- AC6: authorizer turned on by default only after AC4 passes and Tope agrees.

**P1-2. App Studio: section 8 target architecture, phase 1** (intermediate representation, schema retrieval, constrained decoding, deterministic authorizer, repair loop, eval harness). ACs are in section 8.7.

**P1-3. Live 17 to 20 proof for everything marked "Done, code".**
Build one harness (`apps/api/evals/live/run_all.py` or extend `/tmp/gap/suite_live.py` and `setup_live.py` into the repo) that creates `ingenium_live_v{17..20}`, runs each feature's acceptance list, writes a JSON report and drops the DBs.
- AC1: the harness covers at least: wireframe sketch to installed app; curated packs install; Bridge delivery engine end to end (submit, retry, dead letter, replay) and token refresh against a mock OAuth server; History undo from every A5-gated page; Cmd-K record search; test-copy flag; suite ideas built "look only"; Odoo.sh export on 17 to 19 (only 20 was proven); install allow-list on 17 to 19 (stacks were down); `ir.access` shim over every call site that touches access.
- AC2: every row in section 3 that says [Done, code] either moves to [Done, live] with the report path, or gets a P-item for the failure.
- AC3: the harness runs in under 60 minutes and leaves no `ingenium_live_*` DB behind (asserted at the end).

**P1-4. Bridge: Figma-grade flow canvas.**
- AC1: canvas built on a maintained MIT or Apache-2.0 flow library (React Flow `@xyflow/react` is MIT [Inferred: confirm the licence file]) or equivalent; pan, zoom 25 to 400 percent, snap, minimap, keyboard navigation (Tab through nodes, arrows to move, Enter to open), multi-select, undo and redo.
- AC2: nodes show live data: last event time, throughput sparkline, error count, and a "money" badge on accounting steps; idle flows lie flat (touch 59).
- AC3: the record journey transit map (touch 58) renders a real trace with stations "outside", "Ingenium", "Odoo" and per-step milliseconds from `bridge/delivery.py`.
- AC4: 200 nodes pan at 60 fps on a mid-range laptop (no long task over 50 ms while panning).
- AC5: every edit is a proposal on a new flow version; approval, rollout and rollback reuse `flows.py`.

**P1-5. Bridge: AI spec import.**
- AC1: given API docs as HTML or PDF text (not only OpenAPI, Postman or samples), the shared AI client proposes a connector descriptor; the text is fenced as untrusted and PII-redacted.
- AC2: code validates every endpoint, method, auth kind and field against the document (each with a source quote) and refuses http, private hosts and anything not quoted.
- AC3: on 5 public API docs (for example Paystack, Flutterwave, Shopify, HubSpot, a bank API sandbox) the descriptor passes contract tests against recorded sample payloads; injected instructions in the docs change nothing.

**P1-6. View Designer premium items.**
Widget picker with live preview; list designer; kanban card designer UI; search designer; translations side by side; number tiles; hide never-filled fields; stage checklist; inline field create and related-by-drag; upgrade guard flow; heavy-field hint; full Studio-parity component library and new screen from blank; report from a photo.
- AC (each): the SPEC wording is met; edits compile to the minimal inherited view (no positional anchors, no `replace` on stock, inline conditions); publish passes the fidelity check; revert restores Odoo's combined arch byte-equal; live 17 to 20; keyboard-equivalent for every drag; INP under 200 ms on a 60-field form.
- Specific ACs: widget picker filters by field type and version and shows only widgets present on the connected version; list designer writes `optional="show|hide"`, `sum`, `decoration-*` and `editable` correctly per version (`<tree>` on 17); "hide never-filled fields" proposes only fields empty on all of at least 20 records, not required, not conditional, not read by rules.

**P1-7. Live Demo Co-Pilot: demo builder and a live Vexa test.** (needs Tope for the Vexa deployment)
- AC1: a BRD or SOW (DOCX, PDF, text) becomes a demo plan: apps, Bulk Setup steps, App Studio and View Designer changes within hosting limits, labelled demo data, and a demo script with each step mapped to a BRD requirement id.
- AC2: the plan goes through the normal Check, approval and Run; every created record carries an Ingenium external id; "Remove demo data" removes all of it in one action (hold to confirm), verified by counts before and after on 17 to 20.
- AC3: a requirement-coverage view ticks a requirement when its demo step is shown or answered, and exports a coverage summary.
- AC4: Vexa self-hosted runs on the Mac (Apache-2.0); the bot joins one real Zoom, one Teams and one Meet call as a visible named participant with a listening notice; transcript has speaker labels; client-side questions produce whisper-panel answers with the four labels; no answer claims something exists in the DB that does not (claim verifier); after the call a summary, Q&A list and draft follow-up email appear, nothing is sent.
- AC5: meeting chat and speak-aloud stay "not available" until the bot supports them; the disclosure says so.

**P1-8. Wireframe to build, finished.**
- AC1: fixtures: at least 6 sketches (3 hand-drawn photos, 2 Figma exports, 1 multi-page PDF) with golden JSON; reader output matches golden on labels and kinds at 90 percent or better; boxes only when valid.
- AC2: live 17 to 20: sketch to design to install, with the sketch side by side and regions highlighted; at most 3 questions; PII redaction and injection classifier proven by a fixture containing a phone number and an injected instruction.
- AC3: entry point "Start from a sketch" inside App Studio; a "From a picture" entry also opens report-from-photo.

**P1-9. Design touches still open that Tope named.**
- 151 year in review: AC: real numbers only from History and audit (checks run, undos), shareable as an image; no fake numbers; hidden when data is under 30 days.
- 153 premium icons for generated modules: AC: each generated module gets an icon in Odoo's style (colour tile plus glyph), a description and a readme; verified by installing on 17 to 20 and viewing the Apps screen.
- 155 Odoo screens stay Odoo: AC: no Ingenium chrome inside client Odoo; every generated custom field ships with plain help text and a placeholder where the widget supports it; a test asserts `help` is non-empty for generated fields.
- 157 split view: AC: two databases or two versions of a screen side by side with a draggable divider, keyboard-resizable, state in the URL.
- 158 "Show the request": AC: a Developer switch shows the exact Odoo calls Ingenium made for the current screen (model, method, args with secrets masked), copyable; off by default; never shows credentials.
- 161 wallet-style database switcher: AC: databases as a stack of cards in their own colours; flick or arrow through; Enter picks; reachable from the sidebar header and Cmd-K; works with 500 databases (virtualised, searchable); reduced motion uses a plain list.
- 131 margins overlay: AC: a margins toggle on the proof that matches the paper format margins within 1 mm when measured on a rendered PDF on 17 to 20; if the PDF viewer's offset cannot be read, render the overlay on Ingenium's own rasterised page instead.
- 60 and 61: AC: once at least one screen has two or more time charts (Bridge monitor, Upkeep, Home), hovering one shows the same moment on all with exact values, and publishes, imports and plan runs appear as keystone markers from History.
- 127 welcome letter: AC: shown once per person, typeset, signed; text supplied by Tope verbatim (needs Tope). Do not write the letter yourself.

**P1-10. UI rebuild to the section 5 standard, screen by screen.**
Start with the screens people see first: Connect, Overview, App Studio, View Designer, Configuration Suite home, Approvals, History, Settings.
- AC (per screen): passes the visual QA process (section 5.14) against at least two named references; passes contrast, keyboard, reduced motion, hydration, INP and CLS tests; one primary action; every state built; no jargon (jargon guard and term guard pass); before and after screenshots at 1440 by 900 and 390 by 844 in light and dark logged in `docs/vision-verify/<screen>/`.

### P2: complete approved scope

**P2-1. Configuration Suite ideas still missing.** 1 rehearsal replay, 4 filters from words with live count, 6 leaver playbook, 7 bulk reassign, 9 tag manager, 11 handover pack, 16 multi-company consistency, 25 watch this, 27 shareable check result, 28 client mode, 30 Copilot memory, 31 approval in chat, 32 undo all of today, 34 explain this setting, 35 diff-only rerun, 36 rehearsal on a throwaway copy, 37 one plan many companies, 38 setup score, 42 out-of-hours window, 43 industry starter plans, 44 setup handover, 45 email-in import address, 46 spot-the-difference, 48 import health.
- AC (each): the one-line spec in CONFIG_SUITE_SPEC 16 or 20.14 is met; anything that writes goes through Change batches and the write gate (receipt, money guard, approval, undo); live 17 to 20; plain copy; states preview page.
- Specific: 35 AC: applying a plan twice changes nothing the second time (write count 0 on the second run). 36 AC: refused on Odoo Online with a plain reason. 45 AC: forwarded documents arrive as a draft import plan, never written until checked; sender allow-list per database. 32 AC: reverses every reversible run from a chosen day in reverse order and lists one-way runs.

**P2-2. Feature audit items.** A2 page frame (state guide, error, empty state on every page), A4 remove per-page snapshot panels, A7 Edit with AI for Access, Automations, Menus and Models, #4 one "Bring data in", #5 plain-sentence Automations with Reminders folded in and Access "test as user" on a real record, Approvals merge, Numbering rename and merge, Projects and App plan moved under App Studio, old Reports, Mail templates and QWeb pages retired, Website upgrades, Client portal, Settings tabs, Billing upgrades, onboarding (A8, A9), notification centre (A10), daily brief (A11), recent and pinned (A12), database switcher (A15), version chips (A16), workspace roles (A24), templates library (A28), offline-safe drafts (A29).
- AC (each): FEATURE_AUDIT wording met; every write through the write gate; plain copy; live 17 to 20 where Odoo is involved.
- Specific: #5 AC: "When an invoice is overdue 7 days, email the customer and assign a task to the account owner" compiles to a stock `base.automation` with the correct offset per version and is tested on a real record with a test run before turning on. "Test as user" AC: pick a user and a record; the result says allowed or blocked and names the rule, matching what Odoo does for that user (verified by logging in as a test user on a disposable DB).

**P2-3. Deferred agent-mode re-run.** (needs Tope: "when I tell you")
Preconditions: an eval DB API key for the sandbox connection (the 20 Oct run logged "JSON-2 401 Invalid apikey at :8073" on the agent arm) and the answer-cache fresh leak fixed (P1-1 AC5).
- AC1: dev plus dev2, 28 briefs, k=3, fresh, same disposable v20 DB for both arms, common random numbers.
- AC2: report paired deltas with 95 percent CIs for coverage, invented per run, entity recall, stability, false folds, latency, LLM calls and cost per run.
- AC3: no row hits a cached answer (LLM calls per row at least 1 for every AI route).

**P2-4. Code Runner browser click-through and real-time co-editing.**
- AC: every R3 panel clicked through in Playwright with screenshots; co-editing with two browser contexts shows live cursors and no lost edits under 200 ms latency injection.

**P2-5. LLM semantic cache and call batching.**
- AC: semantic hits only above a confidence floor and only for read-only answers; never for anything containing PII or secrets; hit rate and money saved shown on the savings card; a red-team test shows no cross-database leakage.

**P2-6. Security items in section 6** not already covered (rate limits per route, ASVS L2 gaps, SBOM and licence scan in CI, secrets out of local caches).

### P3: polish and bold bets
- Remaining design touches in section 3.20 "other open touches", each with its own AC from DESIGN_TOUCHES.
- Bold capabilities B1 to B8 (upgrade co-pilot, process mining, database doctor, knowledge capture, benchmarking, training mode, compliance packs). New ideas beyond the approved lists need Tope's approval (section 10).
- Mobile companion (A20): approvals, alerts, run status and Ask on the phone; no editing.

---

## 5. UI and UX standard

Tope is unhappy with the UI quality. This section is the bar. If a screen does not meet it, it is not done, even if it works.

### 5.1 The reference class
Ingenium should feel like it belongs next to Linear, Stripe Dashboard, Vercel, Raycast, Arc, Things and Claude. What these share, stated so you can test it:
- **One clear job per screen.** One primary action, visually obvious. Secondary actions are quieter. Destructive actions are separated and confirmed.
- **Calm by default.** Neutral surfaces, colour used only for meaning (state, brand, focus). No decorative gradients, glows, glass, or emoji in chrome.
- **Fast and certain.** Every click answers in under 100 ms (optimistic state or a skeleton in the final layout). No spinners on pages, no layout jump when data arrives.
- **Keyboard first.** Every action reachable by keyboard, with a visible focus ring. Cmd-K reaches every page and action. Shortcuts shown in menus and tooltips.
- **Typographic hierarchy, not boxes.** Hierarchy from size, weight and space. Borders and cards only where they group something.
- **Considered motion.** Short, physical, purposeful. Never blocks input.
- **Words that a business owner understands.** No internal terms.

How to use the references: for each screen you rebuild, pick two references for the same kind of screen (for example Linear issue list and Stripe payments list for a records table), take screenshots at the same size, and compare spacing, type scale, density, empty and loading states side by side. Log the comparison (5.14).

### 5.2 Brand and tokens (single source)
Source of truth: `/home/box/design-repo/brand/ingenium-v2/final/BRAND_GUIDE.md` and `tokens.css` (on the box), mirrored into `apps/web/src/app/globals.css`. Do not invent tokens. Do not hard-code hex values in components.
- **Brand mark:** ingenium-v2 "keystone and arch". The keystone is also the motif for markers (History events on charts), the loader, and the empty-state art. Use the supplied SVGs only.
- **Typefaces:** Geist for UI, Geist Mono for code, ids and numbers in tables (tabular figures), Libre Franklin for display and marketing headings only. Loaded through `@fontsource` (already installed), self-hosted, `font-display: swap`, subset to used weights.
- **Colour roles:** `--brand` orange (`#f97316` light, `#fb923c` dark) is the brand mark and highlights, not a text background for white text. `--accent` teal (`#0f766e` light, `#2dd4bf` dark) is the interactive colour (links, focus, selected, primary buttons). `--brand-cinnabar #cf4527` is for the danger and money-guard family only (white on cinnabar 4.63:1 passes).
- **Pairing rule (Tope's rule):** a light-ish background (luminance above about 0.18, which includes every orange, teal 300 to 500, yellow, light chips, `--accent-subtle`) always gets dark ink (basalt `#1a1c21` or the token's `on-*`). White text only on dark backgrounds that pass 4.5:1 (for example teal `#0f766e` 5.47:1, cinnabar 4.63:1).
- **Recommendation for open decision 3 (needs Tope):** keep orange as the brand mark and data highlight; primary buttons use teal `#0f766e` with white text in light mode and teal `#2dd4bf` with basalt text in dark mode (9.16:1). Where an orange button is wanted (marketing), use basalt text on orange (6.08:1).
- **Radii:** `--r-sm 6`, `--r-md 10`, `--r-lg 16`. Controls `sm`, cards and popovers `md`, sheets and dialogs `lg`.
- **Spacing:** 4 px base scale (4, 8, 12, 16, 24, 32, 48, 64). No arbitrary values in Tailwind classes except via tokens.
- **Elevation:** at most three levels (flat, raised for popovers and menus, overlay for dialogs). Shadows from tokens.
- AC: a lint (Stylelint or an ESLint rule) fails on raw hex, raw `rgb(`, or Tailwind arbitrary colour values in `apps/web/src/components/**`. Exceptions only in the tokens file.

### 5.3 Information architecture
- Top-level groups in the sidebar, in this order: **Home**, **Build** (App Studio, View Designer, Reports and emails, Website, Wireframe), **Set up** (Configuration Suite, Imports), **Connect systems** (Bridge, Code Runner, Bots), **Meetings** (Co-Pilot), **Review** (Approvals, History), **Settings**. [Inferred: proposed grouping from SPEC and FEATURE_AUDIT; confirm with Tope.]
- `nav.ts` today lacks Bridge and Wireframe entries [Verified 21 Oct]. Every shipped feature must be reachable from the sidebar and Cmd-K.
- Retired pages (FEATURE_AUDIT) redirect to their new homes with a one-time toast saying where it moved.
- Breadcrumb: database, then area, then item. Page title equals the sidebar label.
- AC: a test walks `nav.ts` and asserts every `page.tsx` route is either in nav, reachable from a parent page, or listed as internal; no duplicate labels.

### 5.4 Sidebar and database switcher
Tope's complaint: the switcher is undiscoverable.
- The current database sits at the top of the sidebar as a large, labelled control: database name, version chip (17, 18, 19, 20), hosting chip (Online, Odoo.sh, Self-hosted), "test copy" badge if `is_test_copy`, and a chevron. It looks clickable.
- Click or `Cmd/Ctrl+O` opens the switcher: search, recent, pinned, grouped by client; virtualised; shows health dot and last used.
- Switching shows the new database colour band for 1 s so the change is felt. Never switch silently.
- The sidebar collapses to icons (`Cmd/Ctrl+\`), remembers state, tooltips with labels and shortcuts.
- AC: in a usability check with 3 people who have not seen the app, all 3 find and use the switcher within 10 s without help (record the sessions or notes). Keyboard-only switch works. 500 databases stay smooth.

### 5.5 Command palette (Cmd-K)
- Opens in under 50 ms, from anywhere, including inside dialogs (closes them first).
- Sections: Go to, Actions, Records (live search in the current database), Recent, Help. Each row shows its shortcut and where it goes.
- Plain-sentence actions ("add a field to Contacts") route to the right tool with the text prefilled.
- AC: every nav item and every primary action on every page has a Cmd-K entry (test compares registry to nav and page action lists); result list virtualised; typing latency under 16 ms per keystroke for 10,000 indexed items.

### 5.6 Density
- Two densities: Comfortable (default) and Compact (for lists, tables, logs). Row height 40 and 32 px. Saved per person.
- Tables: sticky header, column resize, column chooser, keyboard row navigation, numbers right-aligned in Geist Mono tabular figures.
- AC: both densities pass contrast and touch-target rules (24 by 24 CSS px minimum, WCAG 2.2 target size).

### 5.7 Motion
- Durations: 120 ms for small (hover, press), 180 to 240 ms for panels and dialogs, never over 320 ms. Easing: standard out for entering, in for leaving; springs only for drag and direct manipulation (`motion` library).
- Motion never blocks input and never delays content that is ready.
- `prefers-reduced-motion: reduce` replaces movement with opacity or nothing; parallax, autoplay and looping animation are off.
- AC: a test with reduced motion emulated asserts no transform animations run (check computed `animation-name`/`transition-property` on key components); no animation runs on page load after 1 s.

### 5.8 States: every component, every page
Each data view has: loading (skeleton in final layout, no spinner after 300 ms without a message), empty (plain sentence, one action, keystone art), partial, error (what happened, what to do, retry, copy details), offline, no permission, too much data (paginate or virtualise, never freeze), read-only (Odoo Online limits explained), and success.
- AC: each page has a `?state=` preview in the states guide page; a Playwright crawl screenshots every state in light and dark.

### 5.9 Microcopy
- Speak like a calm, expert colleague. Short sentences. Verb-first buttons ("Add field", "Run check", "Undo").
- Banned in UI (enforced by the existing jargon guard and term guard, extend the list): IR, intermediate representation, lanes, residual, payload, endpoint (say "address"), schema (say "structure"), XML-RPC, JSON-2, xpath, arch, ORM, inherit, idempotent, recipe id, receipt token, dry run (say "Check"), blast radius, tier-1, ACL (say "access rule"), domain (say "filter"), model (say "record type" in owner-facing copy; "model" is fine in Developer views).
- Odoo's own words for Odoo things (Invoice, Contact, Sales Order) so people recognise them.
- Numbers with units and real dates ("3 fields changed, 21 Oct, 14:05 WAT").
- Errors never blame the user and never show stack traces outside Developer views.
- AC: jargon guard runs over all strings in `components/` and API error messages, and fails CI on any banned term outside Developer-only components.

### 5.10 Accessibility: WCAG 2.2 AA, plus Tope's rule
- Contrast 4.5:1 text, 3:1 large text and UI components and focus indicators (P0-6).
- Light-ish backgrounds always dark text, enforced by test (P0-6 AC2).
- Full keyboard use, visible focus (2 px teal ring with offset, 3:1 against adjacent colours), no keyboard traps, logical order, skip link.
- Focus not obscured (2.4.11), dragging has a non-drag alternative (2.5.7), target size 24 px (2.5.8), consistent help (3.2.6), redundant entry avoided (3.3.7), accessible authentication without puzzles (3.3.8).
- Semantic HTML first; Base UI primitives for dialogs, menus, popovers (they handle focus and ARIA); live regions for toasts and run progress.
- AC: axe-core via Playwright reports 0 serious or critical issues on all routes, light and dark; a manual screen-reader pass (VoiceOver on Mac) on Connect, App Studio, View Designer and Approvals is logged.

### 5.11 Dark mode
- Full parity, not inverted. Uses the dark token set (`--accent #2dd4bf`, `--brand #fb923c`). Light-ish accents in dark mode still get dark ink.
- Theme: light, dark, system, and the existing Lagos-sunset auto. No flash on load (inline script sets the class before paint).
- AC: every route screenshot in dark mode passes contrast and visual review; switching theme causes no layout shift.

### 5.12 Performance budgets
- **INP under 200 ms** at p75 on every interaction (lab measurement with a 4x CPU slowdown).
- **No long tasks** over 50 ms after the first render on key flows (typing, opening panels, switching tabs).
- **Shell paint under 100 ms** after navigation within the app (sidebar and header never re-render on route change; route content streams in).
- LCP under 2.0 s on first load locally, CLS under 0.05.
- **No hydration mismatches** (P0-7).
- **Virtualised lists** for anything over 200 rows (P0-8).
- JS per route under 200 KB gzip for first load (excluding Monaco and the canvas, which load on demand).
- API: list endpoints paginated; p95 under 300 ms for reads against local Odoo.
- AC: a Playwright perf suite measures these on 10 key routes and fails CI on regression over 10 percent; bundle analyzer report committed per release.

### 5.13 Responsive
- Breakpoints: 390 (phone), 768 (tablet), 1024, 1440, 1920. Desktop is the main target; phone must work for Approvals, History, Home and Co-Pilot whisper panel.
- AC: no horizontal scroll at 390 px except inside tables and the canvas; every route screenshotted at 390 and 1440.

### 5.14 Visual QA process
1. Before changing a screen, take baseline screenshots (light, dark, 1440 and 390, every state).
2. Pick two references (5.1) and note three things each does better.
3. Build. Then screenshot again and put before, after and references side by side in `docs/vision-verify/<screen>/`.
4. Run the automated checks: contrast and Tope's rule, axe, hydration crawl, perf suite, jargon guard, reduced motion.
5. Self-review against the DESIGN_SYSTEM_PLAYBOOK QA checklist (§11): alignment to the 4 px grid, one primary action, consistent radii, no orphan colours, real copy (no lorem), states present.
6. Ask Tope to review screenshots for every screen in P1-10 before calling it done.
- AC: Playwright visual regression snapshots exist for every route and state; any pixel diff over threshold needs an approved update.

### 5.15 Known failures to fix (named)
| Failure | Evidence | Fix | Item |
|---|---|---|---|
| Teal chip text unreadable | `#14b8a6` on `#ccfbf1` 2.21:1; `#0d9488` on `#ccfbf1` 3.32:1 [Verified 21 Oct] | chip text uses teal 800 or basalt on `--accent-subtle` | P0-6 |
| White text on orange | 2.80:1 light, 2.26:1 dark [Verified 21 Oct] | basalt on orange, or teal primary | P0-6 |
| Hydration error | [Reported by Tope] | client-only for time, theme, random | P0-7 |
| Rendering 16k rows | 16,014 connections returned unpaginated [Verified 21 Oct] | paginate and virtualise | P0-5, P0-8 |
| Frozen Connect page | follows from the above [Inferred] | same | P0-5 |
| Undiscoverable switcher | [Reported by Tope] | 5.4 | P1-10 |
| Missing nav entries | Bridge and Wireframe absent from `nav.ts` [Verified 21 Oct] | 5.3 | P1-10 |

---

## 6. Security standard

Target: OWASP ASVS 4.0.3 Level 2 for the web app and API, plus the Odoo-specific rules below. Ingenium holds keys to clients' business databases. Treat every failure here as P0.

### 6.1 Authentication
- Modes today: `auth_mode` `off` (default in `settings.py`), `api_key`, `accounts` [Verified 21 Oct]. `off` is for local development only.
- AC1: production refuses to start with `auth_mode=off` unless `ENV=development` and the bind address is loopback (startup check plus test).
- AC2: `accounts` mode: passwords hashed with Argon2id (or bcrypt cost 12 or more), session cookies `HttpOnly`, `Secure`, `SameSite=Lax`, rotation on login, idle timeout 12 h, absolute 7 days; MFA (TOTP, and passkeys when ready) available, required for owners and approvers.
- AC3: login, reset and MFA endpoints rate-limited (6.10) and give the same response for unknown and known emails.
- AC4: CSRF protection on every state-changing cookie-authenticated request.

### 6.2 Tenancy and authorisation
- Every row in the App DB that belongs to a workspace carries the workspace id; every query filters by it in one shared dependency, never by hand in a router.
- Roles: owner, admin, builder, approver, viewer (A24). Server checks role on every route; the UI hiding a button is not a check.
- AC1: an automated tenancy test logs in as workspace A and calls every API route (from the OpenAPI list) with workspace B's ids; every call returns 404 or 403. Runs in CI. (Existing role-matrix and "Alice victim" tests are a start; make them cover all 75 routers.)
- AC2: object-level checks for connections, plans, approvals, History entries, bots, flows and files.

### 6.3 Credentials and secrets
- Odoo credentials are API keys, not passwords, wherever the version supports it (all of 17 to 20). The Connect flow explains how to make a dedicated integration user with least privilege and an API key.
- Secrets at rest encrypted with a key from the environment or a KMS (Fernet or AES-GCM), never in plaintext columns, never in logs, never in the browser beyond the moment of entry.
- **No credentials in local caches.** The AI cache under `~/.ingenium`, the answer cache, Next.js caches, `localStorage`, `sessionStorage` and IndexedDB must never contain an API key, password, token or session id.
- AC1: a test greps every cache directory and the browser storage (Playwright `storageState`) after a full run for patterns of the test credentials; zero matches.
- AC2: log redaction filter masks `password`, `api_key`, `token`, `secret`, `authorization` keys and bearer strings; test asserts.
- AC3: rotating a connection's key takes effect on the next call without restart.

### 6.4 Least privilege toward Odoo
- Ingenium asks only for the access a task needs. The read-only health and look-only modes use a read-only key where possible.
- Developer-only features (Code Runner, module install) are off for viewers and builders by default.
- Install allow-list (only modules Ingenium generated or Tope approved) enforced server-side.

### 6.5 Write gate and approvals
All writes to Odoo pass through the write gate. Keep every layer that exists [Done, code]: dry-run receipt (1 h, bound to the exact plan hash), `dry_run_middleware` (428 without receipt, 403 when invalid), `mutation_lock`, `anomaly_guard` (500 writes per hour), `blast_radius` caps (50 / 1,000 / 200), batches of 25 with 200 ms spacing, `write_gate.guard_one`.
- **Second approver:** any plan that touches money, access, deletes or over 50 records needs a second person to approve. The author cannot approve their own plan, except the self-approval in the next bullet (section 2.4 wins).
- **Self-approval:** any requester may self-approve their own accounting-setup import (audited; section 2.4 wins). The old limit (one member, and draft entries only) is withdrawn. History records a `self_approval` entry with who and when. Posted entries, journal items, payments and invoices stay refused. The money guard and the dry-run receipt still apply. Label it clearly in the UI.
- **Refused outright:** writes to posted journal entries, posted invoices and bills, reconciled or posted payments, locked periods, and anything in `LOCKED_RECIPES`. Tier-1 protected models are try-loading only (validate, never commit).
- **Audit log:** every check, approval, write and undo recorded in History with who, when, what, before and after values and the plan hash; hash-chained (`audit_chain`) so tampering is detectable.
- AC1: tests try each refused case on 17 to 20 disposable DBs and assert refusal with a plain reason and no DB change.
- AC2: a test shows any requester may self-approve their own accounting-setup import, including in a two-person workspace, and History records a `self_approval` entry with who and when. The money guard and the dry-run receipt still apply. Self-approval of other large changes is refused.
- AC3: tamper test: altering one History row breaks chain verification and the UI shows the warning.

### 6.6 AI safety: prompt injection and PII
- All content from Odoo records, uploads, websites, emails, meeting transcripts and API docs is untrusted. It is fenced in prompts and never treated as instructions.
- PII redaction (emails, phones, IBAN and account numbers, national ids, addresses where detectable) before any cloud AI call; local Ollama may see unredacted data only if the person allows it.
- AI proposes; code authorises (section 7.2). AI output never directly calls a write.
- AC1: the red-team pack (existing, extend it) covers: instructions inside record names, notes, file names, PDF text, image text, transcript lines, API docs; data exfiltration attempts ("send the API key to..."); tool-escalation attempts. Runs in CI on every PR; zero passes allowed.
- AC2: a redaction test sends seeded PII through each AI route and asserts the outbound request (captured by a mock) contains none of it.

### 6.7 Test isolation: never touch client or production databases
- Tests use only disposable `ingenium_*` Odoo databases on local containers and a throwaway App DB (P0-3).
- The existing host guard refuses non-loopback Odoo hosts in tests; keep it and extend it to refuse any database name not starting with `ingenium_` during tests.
- Sandbox stacks bind to `127.0.0.1:18100+N` only.
- AC: a test that points at a non-`ingenium_` database or a non-loopback host fails before any network call.

### 6.8 Transport and web hardening
- HTTPS only in production, HSTS, secure headers (CSP with nonces, `frame-ancestors 'none'` except where embedding is a feature, `Referrer-Policy`, `Permissions-Policy`, `X-Content-Type-Options`).
- Outbound fetches (Bridge, website import, API doc import) refuse private, loopback and link-local addresses (SSRF guard) except configured local Odoo in development.
- Uploads: size limits, type sniffing, no execution, virus scan hook (ClamAV is GPL-2.0 as a separate process; allowed as a service).
- AC: an automated header check and an SSRF test suite (169.254.169.254, 127.0.0.1, `[::1]`, DNS rebinding) pass.

### 6.9 Code Runner and Bots sandboxing
- Code Runner executes only in the sandbox containers, no host mounts, no network except the target sandbox Odoo, CPU and memory limits, timeout.
- Bots act with a scoped key and their own rate limits; every bot action is in History.

### 6.10 Rate limiting and abuse
- Per IP and per account limits on auth routes; per workspace limits on AI routes (cost cap per day, shown in Settings); per connection write limits (existing anomaly guard).
- AC: load test shows 429 with `Retry-After` beyond limits and no impact on other workspaces.

### 6.11 Dependencies and licences
- Policy: free and open source only. Allowed: MIT, BSD, Apache-2.0, ISC, MPL-2.0, LGPL (dynamically linked), PostgreSQL licence. Odoo modules generated for clients are LGPL-3 to match Odoo Community.
- Avoid: Elastic License 2.0 (for example Attendee), SSPL, BSL, Commons Clause, and anything without a licence (for example MeetingBaaS repositories as reviewed). Do not use Elasticsearch or Elastic-licensed code.
- AC1: CI produces an SBOM (CycloneDX) for web and API and runs a licence check (`license-checker` or `pip-licenses`) that fails on a disallowed licence.
- AC2: `pnpm audit` and `pip-audit` run in CI; high and critical issues block merge unless an exception is recorded with a date.

### 6.12 ASVS L2 gap review
- AC: a checklist file `docs/security/ASVS_L2.md` lists each L2 requirement with status (met, not applicable, gap with P-item). Gaps feed P2-6.

---

## 7. Functionality and reliability standard

### 7.1 Stock first
Before creating anything custom, use what Odoo already has: a stock app, a stock field, a stock setting, a stock automation, a stock report. The domain packs (`CURATED_PACKS`) encode this.
- AC: for every App Studio brief in the eval set, any custom model that duplicates a stock model (for example a custom "Customer" when `res.partner` exists) counts as an invention and fails the brief.

### 7.2 AI proposes, code authorises
- AI may draft plans, fields, views, mappings and copy. Only deterministic code decides what is valid and what runs: schema validation against the live Odoo structure, version checks, the write gate, the money guard and approvals.
- AC: there is no code path where model output reaches `execute_kw`, a file write in an exported module, or an install without passing a validator. A static test checks that write functions are only called from the plan runner.

### 7.3 Idempotent operations
- Every plan step has an external id or natural key, so running it twice changes nothing the second time.
- Imports match on keys and update instead of duplicating.
- Retries (Bridge delivery, plan runs) are safe.
- AC: for each plan type, a test runs it twice on a disposable DB and asserts the second run writes zero records.

### 7.4 Undo everything
- Every write is recorded with before values and can be reversed from History, newest first; one-way operations (for example sending an email, posting is refused anyway) are labelled before running.
- AC: for each A5-gated page, a live test makes a change, undoes it, and asserts the DB matches the snapshot taken before.

### 7.5 Live proof on Odoo 17, 18, 19 and 20
- Unit tests with fakes are not proof. Each feature needs a live run on all four versions (P1-3).
- Odoo 20 shims (for example `ir_access_shim`, `<list>` vs `<tree>`, renamed fields) live in one version-adapter module, not scattered.
- AC: a version matrix table in PROGRESS shows pass or fail per feature per version, generated by the harness.

### 7.6 Test strategy
| Layer | What | Where | When |
|---|---|---|---|
| Unit | pure functions, validators, compilers, guards | `apps/api/tests`, Vitest | every commit |
| Contract | API schemas, module export structure | pytest + OpenAPI | every commit |
| E2E | key flows in a real browser against local API and disposable Odoo | Playwright, separate distDir | every PR |
| Live | full acceptance lists on 17 to 20 | live harness (P1-3) | nightly and before release |
| AI eval | App Studio briefs, fresh sessions | `apps/api/evals/v2` | on AI changes and weekly |
| Perf | INP, long tasks, shell paint, list sizes | Playwright perf suite | every PR |
| Accessibility and contrast | axe, Tope's rule, reduced motion | Playwright + `contrast.test.ts` | every PR |
| Security | tenancy, red-team, SSRF, headers, licences | CI | every PR |

Rules: tests never touch the dev App DB or any non-`ingenium_` Odoo DB (P0-3, 6.7); no test depends on order; no test calls a real cloud AI unless marked and skipped by default.

### 7.7 Observability
- Structured JSON logs with request id, workspace id, connection id (never secrets).
- OpenTelemetry traces across web, API and Odoo calls (OTel is Apache-2.0); metrics for write counts, guard refusals, AI calls, cost and latency.
- Health page for operators: Odoo reachability per connection, queue depth (Bridge), error rates.
- Error tracking self-hosted (GlitchTip is MIT [Inferred: confirm licence]) or OTel backend; never send PII.
- AC: one trace shows a plan run end to end from the button click to the Odoo call and back.

### 7.8 Reliability targets
- No data loss on API restart during a run (runs resume or stop safely with a clear state).
- Bridge delivery: at-least-once with idempotency keys, dead letter after 5 attempts, replay.
- Backups before risky runs on self-hosted connections when Odoo allows it (9.8).

---

## 8. The App Studio challenge, in depth

App Studio turns a business owner's description ("I run a borehole drilling company, I want to track jobs, rigs and payments") into a working Odoo app: models, fields, views, menus, access, built stock first. It is the hardest and most important feature. This section records what was tried, what the numbers say, why it is hard, and the architecture to build next.

### 8.1 The flow as built today [Done, code]
1. **Diagnosis.** The owner describes the business. Ingenium understands the brief (`understand` step), names it plainly (stripping filler such as "management"), and asks **at most 3 questions**, each with a **recommended default** so the owner can just accept.
2. **Assumption ledger.** Every guess Ingenium makes is listed in plain words ("I assumed one rig per job"), each changeable.
3. **Stock-first domain packs.** `CURATED_PACKS` map common businesses to stock apps and fields before anything custom.
4. **Contract.** A list of requirements quoted from the owner's own words, with roles (record, attribute, dimension, context, future, rule, access).
5. **Build plan.** Models, fields, views, menus, access, checked against the live Odoo structure and version.
6. **Install** through the write gate, Odoo Online limits respected (no custom Python on Online; Odoo.sh gets a git module export; self-hosted gets a direct install).

### 8.2 What was tried, and what happened
- **Clarify-online fix.** On Odoo Online, the questions now steer away from features needing custom Python. [Reported by Tope; not found in logs]
- **Guard vs new model for a passing mention.** A word mentioned in passing ("we sometimes rent tools") was becoming a whole new model. A guard now treats passing mentions as context or a field, not a model. The authorizer and false-fold metric measure this. [Done, code]
- **Field-name length.** Generated technical names exceeded Postgres and Odoo limits on long business words; names are now shortened deterministically with a collision check. [Reported by Tope; partial evidence in logs]
- **Outline fallback when AI fails.** If the AI step fails or times out, App Studio shows an outline built from the packs and the owner's words instead of an error. [Reported by Tope; not found in logs]
- **The Gemini model saga.** 3.8-flash timeouts "even on Say OK"; a 25 s primary-call cap bug caused 452 fallbacks to 2.5-flash; 429 quota errors on 3.1-pro; a DNS outage during session S8. It ended on Vertex `gemini-3.8-flash` [Reported by Tope]. Note: `settings.py` defaults still say `gemini_model "gemini-3.6-flash"` and `gemini_backend "studio"` [Verified 21 Oct], so the running config comes from the environment. Make the default match what is actually used, or document it.
- **Five briefs and holdout_fresh evals.** The five headline briefs [Reported by Tope]; `holdout_fresh` has 13 briefs: borehole, carwash, gym, hostel, photo_studio, poultry_pidgin, printshop, radio_ads, recycling_negation, solar, thrift_yoruba, tiles_extend, water_hausa [Verified 21 Oct]. These include Pidgin, Yoruba and Hausa phrasing and a negation case, which matter for Nigerian users.
- **Customer Health 5/10.** Tope rated the Customer Health result 5 out of 10. [Reported by Tope]
- **Holdout after the h-fix:** coverage 0.444 to 0.528, invention 0.333 to 0.433 (invention went up), severity 1.88. [From PROGRESS]
- **Authorizer replay:** invented models 0.739 to 0.162 (good), but false folds 0.234 against a 0.10 gate (fail), 6 briefs dropped coverage. The authorizer stays OFF. [From PROGRESS]
- **Pipeline vs agent head-to-head (20 Oct, 28 briefs, k=3):**

| Metric | Agent | Pipeline |
|---|---|---|
| Coverage | 0.369 | 0.484 |
| Invented models per run | 0.333 | 0.417 |
| Entity recall | 0.42 | 0.527 |
| Stability | 0.431 | 0.534 |
| False folds | 0.46 | n/a in log |
| Latency mean | 420 s (p50 280, p95 599) | 88 s |
| LLM calls per run | 3.7 | 2.8 |
| Cost per run | about $0.10 ($0.099) | not logged |

Caveat: the answer cache was hit despite `--fresh`, and the agent arm hit "JSON-2 401 Invalid apikey" at `:8073`, so the agent numbers are not clean (P2-3). The pipeline is better on coverage and speed; the agent invents slightly less.

### 8.3 Why this is hard
- **Briefs are messy.** Mixed languages, negation ("we don't do delivery"), passing mentions, extensions of existing apps ("tiles_extend"), vague nouns.
- **Two opposite errors.** Inventing models that are not needed vs folding real ones into fields (false folds). Fixing one tends to worsen the other, as the authorizer replay showed.
- **The target is a moving schema.** Odoo 17 to 20 differ in models, fields, view tags and access; the installed apps differ per database.
- **Free-form generation is unstable.** Same brief, different output (stability 0.43 to 0.53).
- **Evaluation leaks.** Caches and shared sessions make runs look better or worse than they are.
- **Latency and cost.** Owners will not wait 7 minutes; each extra LLM call costs money and fails sometimes.

### 8.4 Target architecture
```
Owner brief
  -> 1. Understand: language detection, normalise, extract candidate entities with quotes (LLM, constrained)
  -> 2. Retrieve: real Odoo structure for this database and version (models, fields, installed apps, packs)
  -> 3. Map: each candidate to stock model / stock field / new field / new model / out of scope (LLM, constrained, with retrieved options only)
  -> 4. Ask: at most 3 questions where the map is uncertain, each with a recommended default
  -> 5. Build IR: a typed app spec (JSON Schema) - the single source of truth
  -> 6. Authorise: deterministic validators and rules (no LLM)
  -> 7. Critique and repair: LLM reviews IR against the quotes; validators re-run; max 2 loops
  -> 8. Compile: IR -> Odoo module or RPC plan per version and hosting
  -> 9. Check, approve, install, undo (write gate)
```

### 8.5 The parts in detail
- **Structured intermediate representation (internal only; never say "IR" in the UI).** A versioned JSON Schema: `models[]` with `role`, `source_quotes[]`, `stock_ref?`, `fields[]` (type, required, selection values, relation, `source_quotes[]`), `views[]`, `menus[]`, `access[]`, `automations[]`, `assumptions[]`, `questions[]`, `out_of_scope[]`. Every element must cite at least one quote or an assumption id. Pydantic models generate the schema.
- **Retrieval over the real Odoo schema.** At connect time, index `ir.model`, `ir.model.fields`, installed modules, and pack descriptions for that database and version. At build time, retrieve the top candidates per entity (hybrid keyword plus embeddings; pgvector is PostgreSQL-licensed and fits the existing Postgres). The mapping step may only choose among retrieved options or "new".
- **Constrained decoding plus schema validation.** Use the provider's structured output (Vertex Gemini `response_schema`) or a grammar for local models (Ollama supports JSON schema format). Validate with Pydantic; on failure, one repair call with the validation errors; then fall back to the outline.
- **Deterministic authorising.** Code rules: no custom model when a stock model matches above a threshold; no model for a passing mention (mentioned once, no attributes, no actions); negation removes items; technical names generated and length-checked by code; version and hosting compatibility; relations must point to real or planned models; access generated from roles.
- **Self-critique and repair loops.** A second, cheaper call compares the IR with the quotes and lists unsupported or missing items; code decides what to change. At most 2 loops; latency budget enforced.
- **Eval harness with fresh-session isolation.** Each run uses a new session, a new disposable DB, no answer cache (honour `x-ingenium-fresh`), fixed seeds where supported, and records the prompt and model versions. Hierarchical bootstrap CIs across briefs and reps.
- **Regression suites of messy briefs.** Keep the 28-brief set and `holdout_fresh` (13), add at least 20 more: Pidgin, Yoruba, Hausa, Igbo mixes; voice-note style run-ons; negation; extension of existing apps; very short briefs; very long briefs; briefs with prices and money (to test the money guard); briefs with injected instructions. Golden expected outputs reviewed by a person (Tope or a functional consultant).

### 8.6 Measurable bars (proposed; confirm with Tope)
| Metric | Today (best) | Bar for release |
|---|---|---|
| Coverage (requirements met) | 0.528 holdout / 0.484 pipeline | at least 0.80 |
| Invented models per run | 0.162 (authorizer, off) to 0.433 | at most 0.10 |
| False folds | 0.234 (authorizer) | at most 0.10 |
| Entity recall | 0.527 | at least 0.85 |
| Stability (same brief, k=3) | 0.534 | at least 0.80 |
| Exclusion recall (negation) | 1.0 | 1.0 |
| Latency p95 to first proposal | 599 s agent / 88 s pipeline mean | under 45 s |
| Cost per brief | about $0.10 agent | under $0.05 |
| Owner rating (Tope's 1 to 10) | 5 (Customer Health) | at least 8 on all five headline briefs |
| Installs cleanly on 17 to 20 | partial | 100 percent of eval briefs |

### 8.7 Acceptance criteria for the new App Studio
- AC1: the IR schema exists, is versioned, and every compiled artefact is generated only from it.
- AC2: retrieval indexes are built per connection and refreshed on module install; the mapper cannot choose a model or field outside the retrieved set or "new".
- AC3: structured output plus validation; a fuzz test of malformed model output never reaches compile.
- AC4: authoriser rules each have unit tests with positive and negative cases from real briefs.
- AC5: the harness reports all 8.6 metrics with CIs on the full suite, fresh, on a disposable v20 DB, and the same on 17 to 19 for at least 10 briefs.
- AC6: release only when every 8.6 bar is met or Tope accepts an exception in writing.
- AC7: owner UI: questions at most 3, each with a default; the assumption ledger is editable; every proposed item shows the owner's quote it came from; plain words only.

---

## 9. Other premium aspects

### 9.1 Onboarding
- First run: connect a database (with a clear guide to making an API key and a least-privilege user), pick what you want to do (build an app, change a screen, set up, connect a system), see a first useful result in under 5 minutes.
- Sample database option: a disposable `ingenium_demo_*` DB on local Odoo for trying things safely (local and self-hosted only).
- Checklist on Home that disappears when done. Welcome letter (touch 127) once Tope supplies the text.
- AC: a new person with an Odoo URL and API key reaches a first successful Check in under 5 minutes in a timed test (3 people).

### 9.2 Pricing and billing tiers
- Today the billing code knows only one plan id, `free_solo` [Verified 21 Oct]. Tiers in section 1 are the intent; prices are not set. (needs Tope)
- Build: plans as data (limits on databases, members, AI credits, Bridge flows, Co-Pilot minutes), metering, usage shown in Settings, upgrade and downgrade, invoices.
- Payment provider: Paystack and Flutterwave for Nigeria and Africa, Stripe for elsewhere [Inferred: confirm with Tope]. Use their hosted checkout so card data never touches Ingenium.
- AC: limits enforced server-side; a plan change takes effect immediately; usage numbers match metering logs; tests cover over-limit behaviour with a plain message.

### 9.3 White-label (for partners)
- Partner logo, colours (validated against contrast rules so a partner cannot pick white-on-yellow), custom domain, email sender, and hiding the Ingenium name in client-facing views (client portal, reports, emails).
- AC: a partner theme that fails contrast is refused with a suggestion; client views show no Ingenium branding when white-label is on.

### 9.4 Internationalisation
- UI strings extracted (`next-intl` is MIT [Inferred: confirm]) with English first; French, Portuguese and Arabic (RTL) as candidates for Africa [Inferred]; Pidgin, Yoruba, Hausa input understood by App Studio already in evals.
- Dates, numbers and currency by locale; Naira formatting; time zone per person (Lagos default for Tope).
- AC: pseudo-localisation run shows no clipped or hard-coded strings; RTL layout passes visual QA.

### 9.5 Docs and help
- In-app help: every page has "What is this?" with a short plain explanation and a link to the docs page.
- Docs site (static, versioned) with guides per task, hosting limits, security overview, and a changelog.
- Update `README.md`, `AGENTS.md`, `RULES.md`, `ODOO_HOSTING.md`, `SAFETY.md` to match reality after each P-item (they are partly out of date; for example settings defaults vs the running Vertex model).
- AC: every page has a help entry; docs build in CI; no broken links.

### 9.6 Privacy-respecting telemetry
- Opt-in product analytics, self-hosted (PostHog is MIT for the core [Inferred: check the licence of the self-hosted edition] or Plausible AGPL as a separate service). No record contents, no PII, no Odoo data.
- AC: a test captures telemetry payloads and asserts no field values, names, emails or URLs with ids.

### 9.7 Deployment
- Containers for web and API; Postgres managed or self-hosted; migrations by Alembic only (P0-2); zero-downtime deploys; separate environments (dev, staging, prod) with separate databases and keys.
- Next.js standalone output in its own distDir (P0-4).
- AC: one command deploys staging from a clean checkout; health checks gate the switch; rollback in one command.

### 9.8 Backups and recovery
- App DB: daily encrypted backups, 30-day retention, monthly restore test.
- Client Odoo: Ingenium does not own client backups, but before risky runs on self-hosted connections it offers a database backup through Odoo's own manager when available, and always keeps its own before values for undo.
- AC: a restore drill brings staging back from backup with a measured recovery time (target under 1 hour) logged.

---

## 10. Working rules (read before touching anything)

1. **Git.** Do not run `git checkout`, `git reset`, `git stash`, `git commit`, `git rebase`, `git push` or any history-changing command without Tope's explicit say-so. The worktree has 848 modified and 804 untracked files of real work [Verified 21 Oct]; losing them is unrecoverable.
2. **Formatters.** Use only the repo's own formatters and linters (its Prettier, ESLint, Ruff configs). Do not reformat files you are not changing.
3. **Databases.** Use only disposable `ingenium_*` databases on the local Odoo containers. Never touch a client or production database. Drop what you create. Do not wipe sandbox stacks you did not create.
4. **Plain language.** Every word the owner sees is plain. No internal terms (5.9). Reports to Tope are plain too.
5. **Preserve every feature.** Rebuilding a screen must keep every capability it had. Before removing or merging anything, list what it did and where that now lives. Retirements follow FEATURE_AUDIT and need Tope's yes.
6. **New ideas need Tope's approval.** Anything not in SPEC, CONFIG_SUITE_SPEC, BRIDGE_RUNNER_SPEC, FEATURE_AUDIT or DESIGN_TOUCHES is a proposal. Write it down, do not build it.
7. **Evidence or it did not happen.** Log every finished item in `apps/api/evals/v2/PROGRESS.md` with date, command and result. Use the evidence labels from section 0.
8. **Never invent facts.** If you do not know, say so and label inferences.
9. **Free and open source only** (6.11). No Elastic-licensed or unlicensed code.
10. **One change at a time, verified.** Small steps, each tested (unit, then live), before the next.
11. **Leave the machine as you found it.** Stop servers you started; do not take over ports used by Tope's running services (3002, 8001, 8002, 8012, 5433, 5436, 8069 to 8073, 11434).

---

## Appendix A. Ports and processes (as of 21 Oct)
| Port | Service |
|---|---|
| 3002 | Next.js web dev server |
| 8001 | API (`ingenium.api`, launchd, no `--reload`) |
| 8002 | API for evals |
| 8012 | API for agent-mode evals |
| 5432 | Postgres (Odoo containers) [Inferred from listener] |
| 5433 | App DB Postgres |
| 5436 | App DB for the Odoo 20 stack |
| 8069 / 8070 / 8071 / 8073 | Odoo 19 / 18 / 17 / 20 |
| 18100+N | sandbox stacks `ingenium_sandbox_v<N>` (loopback) |
| 11434 | Ollama |

## Appendix B. Where things are (Mac repo)
- Web: `apps/web` (Next.js 15.5, React 19.1, Tailwind 4, Base UI). 126 `page.tsx`, 702 component `.tsx`. Navigation: `apps/web/src/lib/nav.ts` [Inferred path from earlier read; confirm]. Tokens: `apps/web/src/app/globals.css`.
- API: `apps/api` (FastAPI, Python 3.12). 658 `.py` files, 75 routers, 541 test entries. Settings: `settings.py`. Migrations: Alembic (35 versions).
- Packages: `packages/odoo-client` (clean-room ORM and RPC), `packages/module-generator`.
- Evals and log: `apps/api/evals/v2/` and its `PROGRESS.md`.
- Specs (box): `/workspace/ingenium_builders/` (IDEA, SPEC, CONFIG_SUITE_SPEC, BRIDGE_RUNNER_SPEC, FEATURE_AUDIT, DESIGN_TOUCHES, APP_STUDIO_HANDOFF, APP_STUDIO_FIX_PLAN, GAP_AUDIT, PROGRESS).
- Brand (box): `/home/box/design-repo/brand/ingenium-v2/final/`.

## Appendix C. Plain-word glossary (internal term, what to say)
| Internal | Say in the UI |
|---|---|
| dry run | Check |
| receipt | (do not show) |
| write gate | safety checks |
| blast radius | how many records this changes |
| money guard | money protection |
| IR | (do not show) |
| lanes | (do not show) |
| residual | what's left |
| model | record type (owner views) |
| field | field |
| view / arch | screen |
| domain | filter |
| ACL / ir.model.access | access rule |
| xpath / inherit | (do not show) |
| external id | (do not show) |
| test copy | test copy |

## Appendix D. Source index
Box: `IDEA.md`, `SPEC.md`, `CONFIG_SUITE_SPEC.md`, `BRIDGE_RUNNER_SPEC.md`, `FEATURE_AUDIT.md`, `DESIGN_TOUCHES.md`, `APP_STUDIO_HANDOFF.md`, `APP_STUDIO_FIX_PLAN.md`, `GAP_AUDIT.md`, `PROGRESS.md` (builders log), `stage3/contrast.md`, `BRAND_GUIDE.md`, `tokens.css`, `skills/DESIGN_SYSTEM_PLAYBOOK.md`.
Mac (read-only copies in `/workspace/ingenium_src/`): `apps/api/evals/v2/PROGRESS.md`, `README.md`, `AGENTS.md`, `RULES.md`, `ODOO_HOSTING.md`, `SAFETY.md`; plus targeted reads of `next.config.ts`, `settings.py`, `nav.ts`, `git status`, listeners, and one read-only `GET /api/connections` on 21 Oct.

*End of handover.*
