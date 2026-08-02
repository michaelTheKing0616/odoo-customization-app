# Wave 9 — MON: monetization — auth, billing, admin, pricing

Shared context: for-profit SaaS. Tiers gate risk-reduction/scale features, never the learning
curve. Processors: Stripe (global) + Paystack (NGN) — transaction fees only, hosted checkout
(no PAN ever touches us). No paid auth SaaS. `AUTH_MODE=off` stays functional for local gates;
`AUTH_MODE=api_key` stays for programmatic/CI. New mode: `AUTH_MODE=accounts`.
NEVER commit secrets or credentials; never log tokens/passwords.

Tier definitions (entitlement DATA, seeded by MON-2, adjustable in admin without code):
- free_solo: 1 connection; metadata browser; model/field builder; menus; snapshots 7-day
  retention; community support.
- pro ($39/user/mo, annual 2-months-free): 5 connections; view designer; automations +
  approvals; reports (+designer); access builder; import + seeds; Draft Studio (local
  Ollama); module export + sandbox; full snapshots; ID generator.
- business ($149/workspace/mo + $19/extra seat): pro + bulk suite (ALL BLK tools); power ops;
  post-upgrade health check; pipelines; Odoo Expert; audit export; priority support flag.
- agency (from $399/mo): business + unlimited connections; multi-workspace client mgmt; SSO
  (placeholder flag v1); API keys surface; store packaging assist; migration assist;
  white-label report branding.
- internal: everything, unlimited — admin/testing only, badge-labeled.
Trial: business, 14 days, no card. Downgrade re-gates, never deletes.

Feature-key registry (MON-2 creates `apps/api/app/entitlements.py`; earlier waves' surfaces
map to keys): connections_limit, designer, automations, approvals, reports_designer, import,
ai_draft, module_export, sandbox, snapshots_full, id_generator, bulk_suite, power_ops,
health_check, pipelines, expert, audit_export, store_packaging, migration_assist,
bulk_security, api_keys, white_label, workspaces_multi.

---

## MON-1 — Accounts, workspaces, roles, sessions (Grok 4.5 card)

TASK: Full self-hosted user-account system with workspaces and roles.

INPUT: `auth.py` (existing key auth — extend, keep working), `db_models.py`, `settings.py`,
`rate_limit.py`, web settings/login surfaces, PROD-2 Alembic.

CHECKLIST:
- [ ] Models (Alembic migration): users (email unique, password_hash argon2id, email_verified,
      totp_secret nullable, is_superadmin), workspaces, memberships (role:
      owner/admin/builder/viewer), invitations (token, expiry), sessions (server-side record:
      token hash, expiry, ip, ua), password_resets, email_verifications.
- [ ] Password auth: argon2id (argon2-cffi); policy: min 10 chars, breach-list top-1k check
      (vendored list); login rate-limited + lockout backoff; timing-safe comparisons.
- [ ] Sessions: HTTP-only Secure SameSite=Lax cookie, server-side session with rotation on
      privilege change; short-lived JWT ONLY for the SPA's bearer needs if cookie won't
      suffice (decide: cookie-first, document); logout revokes.
- [ ] Email flows: verification + reset via SMTP settings (console/log transport in dev,
      clearly marked); tokens single-use, expiring, hashed at rest.
- [ ] TOTP 2FA: optional enroll (QR provisioning URI), verify, recovery codes (hashed);
      enforced-for-admins toggle (workspace setting).
- [ ] Workspace scoping: connections/projects/pipelines/audit rows gain workspace_id
      (migration backfills a default workspace owning existing rows); every router query
      workspace-filtered; role matrix enforced (viewer read-only, builder mutates
      non-destructive, admin+ destructive/billing/members) — matrix documented + tested per
      router family.
- [ ] `AUTH_MODE=accounts`: web login/signup/verify/reset/2FA pages (UIX kit); api-key mode
      + off mode regression-tested unchanged.
- [ ] Invitations: admin invites email → role; accept flow creates user/membership.
- [ ] OAuth (Google/GitHub) via authlib: implemented behind `OAUTH_PROVIDERS` env config
      (off default) — if time-boxed out, mark [SKIPPED] for user approval explicitly.
- [ ] Security tests: authz matrix per role, session fixation/rotation, token reuse, lockout,
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
      overrides table for admin grants).
- [ ] Stripe: products/prices bootstrap script (idempotent, test-mode); checkout session
      endpoint (workspace, price, seat quantity); customer portal link endpoint; webhooks
      (`checkout.session.completed`, `customer.subscription.updated/deleted`,
      `invoice.payment_failed`) — signature-verified, idempotent (event id dedupe table),
      mapping to subscription rows; proration/seat updates delegated to Stripe.
- [ ] Paystack: initialize-transaction + verify endpoints for NGN plans (plan table carries
      per-processor price refs); webhook HMAC-verified; subscription lifecycle mapped
      (Paystack plans/subscriptions API).
- [ ] Lifecycle: trialing (14d business auto on workspace creation), active, past_due
      (7-day grace banner), canceled (re-gate to free_solo); state machine tested; downgrade
      keeps data, re-gates.
- [ ] Frontend: `useEntitlements()` (react-query on a compact entitlements endpoint); gated
      UI = kit Callout + "Upgrade" CTA (COPY_GUIDE template — features stay VISIBLE, locked);
      403-with-feature-key interceptor routes to the upgrade sheet.
- [ ] Wire existing surfaces: apply feature keys to routers/pages per the registry table
      (bulk_suite → BLK routers, expert → EXP, power_ops, pipelines, health_check, designer,
      etc.) — enumerate every applied gate in the return; AUTH_MODE=off or internal plan
      bypasses all gates (local gates unaffected — regression suite proves).
- [ ] Tests: fake-processor webhook suites (signature fail, replay, out-of-order events),
      entitlement matrix per tier, grace/downgrade transitions, one LIVE Stripe test-mode
      checkout smoke (recorded; needs your test keys — pause and ask for them at that step).

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
- [ ] Bootstrap: on startup with `AUTH_MODE=accounts`, if no superadmin exists and
      `APP_ADMIN_EMAIL`+`APP_ADMIN_PASSWORD` env set → create superadmin + personal
      workspace on `internal` plan; setup script `scripts/bootstrap_admin.py` generates a
      strong password into local `.env` (gitignored) and prints it ONCE with a change-me
      note. No credentials in repo, docs, or logs — checker greps for this.
- [ ] `/admin` (superadmin-only, server-checked): users table (search, verify, deactivate),
      workspaces + subscription states, entitlement overrides (grant plan/feature with
      expiry + reason — audit-logged), billing events log, feature-flag toggles
      (db-backed flags read by `require_feature`), revenue snapshot (MRR by plan from
      subscription rows — computed, no external calls).
- [ ] Internal badge: internal-plan workspaces show the badge in shell (UIX StatusPill) so
      test state is unmistakable.
- [ ] Tests: bootstrap idempotency (second boot no-op), superadmin-only access (adversarial:
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
- [ ] `/pricing`: four-tier comparison (feature rows from the entitlement registry — rendered
      from data, not hand-copied), monthly/annual toggle (annual shows 2-months-free math),
      currency hint (USD default, NGN via Paystack path), FAQ (honest: what needs your own
      Ollama, what works on Online, cancel anytime), single primary CTA per tier.
- [ ] In-app: upgrade sheet (opened by gate CTAs + 403 interceptor) — current plan, target
      feature highlighted, checkout handoff; billing settings page (plan, seats, portal
      link, invoices via portal, trial countdown banner at ≤3 days); downgrade flow with
      honest re-gate summary ("you'll lose: …" list from registry diff).
- [ ] Landing updated: pricing nav link + tier strip.
- [ ] Terms/Privacy: stub pages with clearly-marked placeholder copy for counsel — models
      write NO legal text (placeholder lorem-free structure: sections + "[Your counsel
      completes this]" markers).
- [ ] e2e: pricing render, upgrade sheet from a gated feature, trial banner states,
      downgrade summary; vision-verify light+dark.

DONE MEANS: registry-driven pricing page live; full gate→upgrade→checkout(test-mode) journey
e2e-recorded.

DO NOT: invent legal copy; hand-maintain feature lists (registry-driven only).

GATE: pnpm lint/test/e2e + screenshots.

RETURN: ≤10 lines + screenshots.

DEVIATIONS: conservative + log.
