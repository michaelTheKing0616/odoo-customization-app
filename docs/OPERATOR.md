# Operator runbook (LAUNCH-2)

Quick path for a new operator — not a substitute for `DEPLOY.md` or `MASTER_PLAN.md`.

## Bootstrap superadmin (accounts mode)

1. Set in local `.env` only (never commit):
   - `AUTH_MODE=accounts`
   - `APP_ADMIN_EMAIL=you@example.com`
   - `APP_ADMIN_PASSWORD=<strong password>`
2. Start API — first boot creates superadmin + `internal` workspace if none exists.
3. Or run: `uv run python scripts/bootstrap_admin.py` (prints password once to `.env`).

Change the password after first login via account settings.

## Grant a test tier

1. Log in as superadmin → `/admin`.
2. Use **Grant plan** with workspace slug and plan id (`pro`, `business`, `agency`, `internal`).
3. Optional: entitlement overrides with expiry + reason (audit-logged).

## Internal plan badge

Workspaces on `internal` show an experimental StatusPill in the shell top bar — unmistakable test state.

## Feature flags

Superadmin: `GET/PUT /api/admin/feature-flags/{key}` — disables a feature platform-wide (503 with `feature_disabled`).

## Billing (optional until live)

- Stripe test keys: `STRIPE_SECRET_KEY`, webhook secret, run `python scripts/bootstrap_stripe.py` for price IDs.
- Paystack: `PAYSTACK_SECRET_KEY` for NGN path.
- Post-deploy smoke: `bash scripts/launch_smoke.sh`.

## Security

- Never commit `.env`, API keys, or Stripe/Paystack secrets.
- Rotate `FERNET_KEY` and `APP_API_KEY` before any shared host.
- `AUTH_MODE=off` is local-only — never on a public deploy.
