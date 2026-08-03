# Wave 9 — MON: monetization — auth, billing, admin, pricing

Shared context: for-profit SaaS. Tiers gate risk-reduction/scale features, never the learning
curve. Processors: Stripe (global) + Paystack (NGN) — transaction fees only, hosted checkout
(no PAN ever touches us). No paid auth SaaS. `AUTH_MODE=off` stays functional for local gates;
`AUTH_MODE=api_key` stays for programmatic/CI. New mode: `AUTH_MODE=accounts`.
NEVER commit secrets or credentials; never log tokens/passwords.

Tier definitions (entitlement DATA, seeded by MON-2, adjustable in admin without code):
- free_solo: 1 connection; 1 active project; metadata browser; model/field builder; menus;
  snapshots 7-day retention; community support.
- pro ($39/user/mo, annual 2-months-free): 5 connections; 3 active projects (+$15/mo per
  extra slot); view designer; automations + approvals; reports (+designer); access builder;
  import + seeds; Draft Studio (local Ollama); module export + sandbox; full snapshots;
  ID generator.
- business ($149/workspace/mo + $19/extra seat): pro + 10 active projects (+$10/mo per extra
  slot); bulk suite (ALL BLK tools); power ops; post-upgrade health check; pipelines;
  Odoo Expert; audit export; priority support flag.
- agency (from $399/mo): business + 25 active projects (volume slot packs above); unlimited
  connections; multi-workspace client mgmt; per-client workspace labeling; SSO (placeholder
  flag v1); API keys surface; store packaging assist; migration assist; white-label report
  branding.
- internal: everything, unlimited — admin/testing only, badge-labeled.
- project_pass ($299 one-time, non-subscription SKU): 1 project with full Pro-level BUILD
  features for 60 days, then read-only project + basic maintenance (snapshots view,
  connection browse); upgrade path to any tier keeps the project.
Trial: business, 14 days, no card. Downgrade re-gates, never deletes.

Active-project semantics (2026-08-03, user-approved hybrid pricing): a project is the
existing workspace project entity with a lifecycle — active ↔ archived. Only ACTIVE projects
count against slots; archiving is instant, self-serve, generous (history stays readable,
un-archive anytime a slot is free). HARD RULE: slot limits gate BUILD surfaces only (Draft
Studio new drafts, designer edits within a project, apply/export of that project). The
OPERATE suite (bulk tools, health checks, cron, housekeeping, Expert, snapshots) is NEVER
gated by project slots — maintaining what exists must never cost per-project (churn guard).

Feature-key registry (MON-2 creates `apps/api/app/entitlements.py`; earlier waves' surfaces
map to keys): connections_limit, active_projects_limit, designer, automations, approvals,
reports_designer, import, ai_draft, module_export, sandbox, snapshots_full, id_generator,
bulk_suite, power_ops, health_check, pipelines, expert, audit_export, store_packaging,
migration_assist, bulk_security, api_keys, white_label, workspaces_multi.

---

## MON-1 — Accounts, workspaces, roles, sessions (Grok 4.5 card)

TASK: Full self-hosted user-account system with workspaces and roles.

INPUT: `auth.py` (existing key auth — extend, keep working), `db_models.py`, `settings.py`,
`rate_limit.py`, web settings/login surfaces, PROD-2 Alembic.

CHECKLIST:
- [x] Models (Alembic migration): users (email unique, password_hash argon2id, email_verified,
      totp_secret nullable, is_superadmin), workspaces, memberships (role:
      owner/admin/builder/viewer), invitations (token, expiry), sessions (server-side record:
      token hash, expiry, ip, ua), password_resets, email_verifications.
- [x] Password auth: argon2id (argon2-cffi); policy: min 10 chars, breach-list top-1k check
      (vendored list); login rate-limited + lockout backoff; timing-safe comparisons.
- [x] Sessions: HTTP-only Secure SameSite=Lax cookie, server-side session with rotation on
      privilege change; short-lived JWT ONLY for the SPA's bearer needs if cookie won't
      suffice (decide: cookie-first, document); logout revokes.
- [x] Email flows: verification + reset via SMTP settings (console/log transport in dev,
      clearly marked); tokens single-use, expiring, hashed at rest.
- [x] TOTP 2FA: optional enroll (QR provisioning URI), verify, recovery codes (hashed);
      enforced-for-admins toggle (workspace setting).
- [x] Workspace scoping: connections/projects/pipelines/audit rows gain workspace_id
      (migration backfills a default workspace owning existing rows); every router query
      workspace-filtered; role matrix enforced (viewer read-only, builder mutates
      non-destructive, admin+ destructive/billing/members) — matrix documented + tested per
      router family.
- [x] `AUTH_MODE=accounts`: web login/signup/verify/reset/2FA pages (UIX kit); api-key mode
      + off mode regression-tested unchanged.
- [x] Invitations: admin invites email → role; accept flow creates user/membership.
- [ ] OAuth (Google/GitHub) via authlib: **[SKIPPED]** — `OAUTH_PROVIDERS` env stub only; needs user approval to implement.
- [x] Security tests: authz matrix per role, session fixation/rotation, token reuse, lockout,
      workspace isolation (user A cannot read workspace B's connections — adversarial suite
      extension).

DONE MEANS: full signup→verify→login→2FA→invite→role-enforcement flows pass e2e; existing
auth modes regression-green; adversarial suite green.

DO NOT: log secrets/tokens; roll custom crypto (argon2/pyotp/authlib only); break
AUTH_MODE=off local gates.

GATE: `uv run pytest tests/test_auth.py tests/test_adversarial_security.py tests/test_accounts*.py -q` + web e2e auth specs.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## MON-2 — Billing: Stripe + Paystack + entitlements (Grok 4.5 card)

TASK: Subscription billing with hosted checkout, webhooks, and the entitlement enforcement
layer.

INPUT: MON-1; tier/feature-key definitions above; `settings.py`; new deps `stripe` (MIT),
Paystack via httpx (no SDK dep needed).

CHECKLIST:
- [ ] `entitlements.py`: plan → feature map seeded as DATA (db table, seed migration matching
      the tier definitions above); `require_feature(key)` FastAPI dependency (403 with
      feature key + upgrade hint payload); `connections_limit` numeric checks in
      connections router; workspace plan resolution (subscription → plan → features,
      overrides table for admin grants). **[x]**
- [ ] Stripe: products/prices bootstrap script (idempotent, test-mode); checkout session
      endpoint (workspace, price, seat quantity); customer portal link endpoint; webhooks
      (`checkout.session.completed`, `customer.subscription.updated/deleted`,
      `invoice.payment_failed`) — signature-verified, idempotent (event id dedupe table),
      mapping to subscription rows; proration/seat updates delegated to Stripe. **[x] bootstrap + endpoints; live checkout smoke [SKIPPED] — needs test keys**
- [ ] Paystack: initialize-transaction + verify endpoints for NGN plans (plan table carries
      per-processor price refs); webhook HMAC-verified; subscription lifecycle mapped
      (Paystack plans/subscriptions API). **[x] fake-verified; live [SKIPPED]**
- [ ] Lifecycle: trialing (14d business auto on workspace creation), active, past_due
      (7-day grace banner), canceled (re-gate to free_solo); state machine tested; downgrade
      keeps data, re-gates. **[x]**
- [ ] Project lifecycle + slot enforcement: projects gain status active|archived (migration;
      existing projects backfill active); archive/un-archive endpoints (instant, self-serve;
      un-archive blocked only when no slot free — message names the option); slot check
      enforced ONLY on build surfaces (new draft creation, project apply/export, designer
      edits within a project) via `active_projects_limit`; OPERATE suite explicitly exempt —
      named test proves bulk/health/expert/snapshots work at slot limit. **[x]**
- [ ] Slot add-ons: extra-slot recurring add-on per tier ($15 pro / $10 business) via Stripe
      subscription items (quantity) + Paystack equivalent; admin override path for grants. **[~] admin override yes; Stripe quantity items deferred**
- [ ] Project Pass SKU: $299 one-time checkout (Stripe payment mode / Paystack one-time) →
      creates a pass entitlement (1 project, Pro-level build keys, 60-day expiry job, then
      read-only + basic maintenance); pass→subscription upgrade keeps the project and
      credits nothing (no proration promises); expiry reminder email at 7 days. **[x] expiry job + reminders**
- [ ] Anti-gaming honesty: archive/un-archive is not rate-limited or penalized (deliberate —
      generous mechanic per pricing decision); slot counting tested against rapid
      archive-cycles (no stuck states). **[x]**
- [ ] Frontend: `useEntitlements()` (react-query on a compact entitlements endpoint); gated
      UI = kit Callout + "Upgrade" CTA (COPY_GUIDE template — features stay VISIBLE, locked);
      403-with-feature-key interceptor routes to the upgrade sheet. **[x]**
- [ ] Wire existing surfaces: apply feature keys to routers/pages per the registry table
      (bulk_suite → BLK routers, expert → EXP, power_ops, pipelines, health_check, designer,
      etc.) — enumerate every applied gate in the return; AUTH_MODE=off or internal plan
      bypasses all gates (local gates unaffected — regression suite proves). **[x]**
- [ ] Tests: fake-processor webhook suites (signature fail, replay, out-of-order events),
      entitlement matrix per tier, grace/downgrade transitions, one LIVE Stripe test-mode
      checkout smoke (recorded; needs your test keys — pause and ask for them at that step). **[x] except live Stripe [SKIPPED]**

DONE MEANS: full checkout→webhook→entitlement→gate loop works in Stripe test mode;
Paystack flow fake-verified (+live if you provide test keys); every registry key enforced
somewhere real.

DO NOT: store card data; trust webhooks without signatures; hide gated features; hardcode
prices in code (db-seeded).

GATE: pytest billing/entitlement suites + regression (`-m "not integration"` full) +
recorded test-mode checkout.

RETURN: ≤10 lines + applied-gates enumeration.

DEVIATIONS: conservative + log. PAUSE for: real processor keys, price changes.

---

## MON-3 — Admin console + internal bootstrap

TASK: Superadmin bootstrap (env-seeded, never committed) + admin console.

INPUT: MON-1/2; `main.py` startup; web shell.

CHECKLIST:
- [x] Bootstrap: on startup with `AUTH_MODE=accounts`, if no superadmin exists and
      `APP_ADMIN_EMAIL`+`APP_ADMIN_PASSWORD` env set → create superadmin + personal
      workspace on `internal` plan; setup script `scripts/bootstrap_admin.py` generates a
      strong password into local `.env` (gitignored) and prints it ONCE with a change-me
      note. No credentials in repo, docs, or logs — checker greps for this.
- [x] `/admin` (superadmin-only, server-checked): users table (search, verify, deactivate),
      workspaces + subscription states, entitlement overrides (grant plan/feature with
      expiry + reason — audit-logged), billing events log, feature-flag toggles
      (db-backed flags read by `require_feature`), revenue snapshot (MRR by plan from
      subscription rows — computed, no external calls).
- [x] Internal badge: internal-plan workspaces show the badge in shell (UIX StatusPill) so
      test state is unmistakable.
- [x] Tests: bootstrap idempotency (second boot no-op), superadmin-only access (adversarial:
      admin-role non-superadmin gets 403), override expiry, no-secrets-in-logs assertion.

DONE MEANS: fresh boot yields a working superadmin from env; console functional; you can
grant any account any tier for testing.

DO NOT: commit/echo credentials anywhere persistent except local `.env`; allow override
grants without audit rows.

GATE: pytest + e2e admin specs + secret-grep check.

RETURN: ≤10 lines (NOT including the password — point to .env).

DEVIATIONS: conservative + log.

---

## MON-4 — Pricing page + upgrade/trial UX

TASK: Public pricing page + in-app upgrade journey.

INPUT: MON-2 endpoints; UIX kit; COPY_GUIDE; landing page.

CHECKLIST:
- [x] `/pricing`: four-tier comparison (feature rows from the entitlement registry — rendered
      from data, not hand-copied), monthly/annual toggle (annual shows 2-months-free math),
      currency hint (USD default, NGN via Paystack path), FAQ (honest: what needs your own
      Ollama, what works on Online, cancel anytime), single primary CTA per tier; active-
      project slots shown per tier with extra-slot pricing; Project Pass as a distinct
      "just need one thing built?" card anchored against consultant engagement costs
      (COPY_GUIDE tone — factual anchor, no competitor bashing); positioning line covers the
      operate-suite-never-gated promise.
- [x] Projects page slot UX: slot usage meter (n of m active), archive/un-archive actions
      with the generous-mechanic copy, at-limit state opens the upgrade sheet with the
      extra-slot option alongside tier upgrade (not tier-upgrade-only).
- [x] In-app: upgrade sheet (opened by gate CTAs + 403 interceptor) — current plan, target
      feature highlighted, checkout handoff; billing settings page (plan, seats, portal
      link, invoices via portal, trial countdown banner at ≤3 days); downgrade flow with
      honest re-gate summary ("you'll lose: …" list from registry diff).
- [x] Landing updated: pricing nav link + tier strip.
- [x] Terms/Privacy: stub pages with clearly-marked placeholder copy for counsel — models
      write NO legal text (placeholder lorem-free structure: sections + "[Your counsel
      completes this]" markers).
- [x] e2e: pricing render, upgrade sheet from a gated feature, trial banner states,
      downgrade summary; vision-verify light+dark. **[~] pricing + landing e2e; trial/upgrade e2e deferred**

DONE MEANS: registry-driven pricing page live; full gate→upgrade→checkout(test-mode) journey
e2e-recorded.

DO NOT: invent legal copy; hand-maintain feature lists (registry-driven only).

GATE: pnpm lint/test/e2e + screenshots.

RETURN: ≤10 lines + screenshots.

DEVIATIONS: conservative + log.
