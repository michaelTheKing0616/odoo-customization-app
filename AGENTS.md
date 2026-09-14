# AGENTS.md — Session Defaults (read automatically every session)

> Referenced from `.cursor/rules/` so every Cursor model reads this at the start of
> every session. Edit rarely after the stack and permanent facts are locked.

## Who's working on this
- Name / role: Temitope, Senior Software Developer (solo founder)
- Project: No-Code Odoo Customization Platform — Studio-like builder for Odoo Community
  via public ORM/RPC (metadata customization + module export)
- Strong in: software engineering, Cursor agentic workflows
- Still learning: Odoo internals at depth (treat Odoo API claims as verify-against-instance)
- Adjust depth accordingly — don't over-explain known engineering; always verify Odoo API usage

## Communication defaults
- No filler ("Great question!", "Certainly!"). Start with the answer.
- Match response length to task complexity. Don't pad or restate the question.
- Show 2–3 approaches before any significant task and wait for a choice, unless the task is
  small enough that picking the obvious approach and noting it is faster.
- If uncertain about a fact or Odoo API detail — say so explicitly; then verify against local
  Odoo 19 or docs before shipping.

## Behavior defaults
- Ask, don't assume. Unclear scope or intent → ask before writing a line.
- Simplest solution first. No unrequested abstraction or flexibility.
- Stay in scope. Don't touch, refactor, rename, or reformat anything outside the current
  task — note it at the end instead of acting on it.
- Confirm before anything destructive or external: deleting files, overwriting code, schema
  changes, pushing to any environment, running migrations, writing to a non-sandbox Odoo
  instance. An explicit yes in the current message is required.
- After any coding task, end with: files changed, one line per file on what changed, files
  intentionally not touched, follow-up needed.
- For architecture decisions, debugging, or non-trivial features: reason through the
  problem step by step, show the reasoning, flag uncertainty, then implement.

## Tech stack (lock this — flag if something seems like the wrong tool, but don't
## silently substitute)
- Language: TypeScript (frontend) + Python 3.12 (backend)
- Framework: Next.js (web) + FastAPI (api)
- Package manager: pnpm (web monorepo) + uv/pip (api)
- Database: Postgres (app metadata store; separate from customer Odoo DBs)
- Odoo target: **Community 19 + 18 + 17 = GA**; **16 = experimental** (Docker `odoo:19`/`18`/`17`/`16`)
- Odoo RPC: `odoorpc` or stdlib `xmlrpc.client` — prefer typed wrappers in `packages/odoo-client`
- Module templating: Jinja2
- Queue: RQ or arq (prefer lighter solo stack over Celery until scale demands it)
- Sandbox: Docker Compose ephemeral Odoo 19 + Postgres (primary); optional 18/17/16 stacks for gates
- Testing: pytest (api/odoo-client), Vitest/Playwright (web); RPC smoke tests against local Odoo
- Styling: Tailwind CSS
- Hosting (later): Fly.io or Railway — no paid SaaS until paying users

## Repo layout (target)
```
/apps/web              Next.js frontend
/apps/api              FastAPI backend
/packages/odoo-client  Shared typed Odoo RPC wrapper
/docker                Local Odoo 19 (+ optional 18/17/16) for gates
```

## Permanent facts / constraints
- **Odoo Community 19 + 18 + 17 = GA.** **16 = experimental** (16 omits dotted `update_path` /
  related_write). Majors ≤15 refused. No silent “best effort” outside the capability registry.
- Customize via **public ORM/RPC only** (`ir.model`, `ir.model.fields`, `ir.ui.view`,
  `ir.ui.menu`, `ir.actions.*`, `base.automation`, access rules). Legitimate; not Studio.
- **Never** read, copy, or reverse-engineer Odoo Enterprise Studio source.
- Two tiers: (1) live metadata customization, (2) installable module generation (escape hatch).
- **Python / dangerous actions (Option A):** default no-code path stays safe (no live
  `state=code`). Custom Python is authored → packaged as a module → sandbox-tested →
  explicitly promoted/installed to become live. Advanced admin actions (code, webhook,
  equation compute, destructive deletes) are allowed when the UI shows an Odoo-style
  warning and the API receives an explicit confirmation flag — assume the operator
  understands ERP risk.
- **Rollback:** snapshot metadata (and generated-module versions) before risky mutations;
  offer one-click restore where Odoo allows (views/automations/server actions yes;
  dropped columns/data loss only partially recoverable — warn honestly).
- Never install unvalidated modules into a customer prod instance — sandbox gate first
  (advanced confirm can still require sandbox for Python promote).
- **Job Autopilot** (sandbox only): stock-first install/config, custom `x_*` residual only,
  ingest dry-run then sandbox auto-commit, RPC process smoke as the done bar (quote→confirm→
  invoice wizard; custom Confirm server action). Domain-agnostic connector recipes run in
  fixed order (payments → inbound orders → messaging → hardware → statutory compute-only)
  on stock models; they do not invent a vertical `x_*` or write partner API keys.
  Implementation-job scorecard is separate from ModuleSpec 10.0. **Promote to another
  connection stays human.** Refuse `write_mode=production`. Do not clone a customer
  production database.
- **Generation Engine** (Draft Studio): classify before pack/LLM **and before component
  grain**. Residual → stock-first pack or unpacked seed. Explicit `stock_first` + residual
  none → `stock_reuse` (empty spec; Job Autopilot is the done-bar) **only when residual
  is explicitly none and the brief is not an inherit/extension ask**. Empty ModuleSpec is
  **not** Cert Gold — cap to ReviewRequired; Completeness 10.0 is hygiene, not a custom app.
  Named residual or
  “add X on invoices” still draft/apply custom x_* or field packs. Out of scope / “later
  Option A only if we ask” must not select gold POS or invoice Pay/QR. Option A gold
  (`pos_receipt_options` / `invoice_qweb` / `currency_rate_cbn`) is a shortcut when the
  prompt matches. Any other Python/QWeb/HTTP/OWL ask is LLM-authored (`option_a_authored`);
  zip and sandbox stay locked until the authoring gate passes. Missing inherit hosts
  (`sale.order` not on the connection) offer to install the stock CE app (Sales / `sale`);
  that is not Live Install of the zip — re-verify the gate, then zip → sandbox → Promote.
  App Studio skips pack/stock chips when classify is gold or authored; inherit seeds `sale.order` for sales markup/WHT
  (not a new home tile). Intent LLM may extract `host_model` / `needs_module`. App Studio
  shows a locked diagnosis card (host, inherit vs new app, Option A vs fields) and generate
  waits for confirm; the compiler fails the draft if it contradicts that lock. Never invent `x_receipt` /
  `x_fx` from the prompt. Community 19 has no ECB Service (upgrade tease); CBN gold
  inherits Settings and writes stock `res.currency.rate`.
  Explicit Apps Store clone/copy/reverse-engineer is refuse; a GM product-name paste is
  still the honest POS options template. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
  Surface/Install gates are invariants + mutants (`ai_surface_invariants.py`), not
  screenshot denylists — new Odoo failures add a property, never `if display_name == "…"`.
  Local uvicorn on `:8001` is started **without `--reload`** — routing fixes are not live
  until that process is killed and restarted.
- Credentials encrypted at rest; prefer Odoo API keys over passwords.
- **App API auth (Phase 7):** `AUTH_MODE=api_key` + `APP_API_KEY` or hashed keys in
  `app_api_keys`. Send `Authorization: Bearer …` or `X-API-Key`. Default `AUTH_MODE=off`
  for local gates; enable for any shared/deployed API.
- No paid subscription dependencies while bootstrapping.

## Session-end protocol
When the session is wrapping up, run:
```
Run a retro on this session. Write into STATE.md:
- what shipped, with links/paths
- what failed and why, one line each
- one rule to add to skills/ or this file so the failure can't repeat
Keep it under 15 lines.
```
And if a decision was made or an approach failed twice, log it in `MEMORY.md` or
`ERRORS.md` respectively before ending — see RULES.md Rule 9.

## Full ruleset
See `RULES.md` for the complete governing ruleset. This file is the always-loaded summary;
`RULES.md` is the canonical reference. Skills live in `skills/`.
