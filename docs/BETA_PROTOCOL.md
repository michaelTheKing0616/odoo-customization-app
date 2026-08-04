# Design-partner beta protocol (Wave 12 TRUST-9)

Controlled exposure before general availability. No external analytics — evidence lives in the app DB and admin console.

## Who gets production write mode

| Workspace | Production write mode |
| --- | --- |
| `beta_partner = true` | Allowed after TRUST-8 production readiness checklist passes |
| Everyone else (pre-GA) | Capped at **standard** — production unlock returns `409 beta_partner_required` |
| Launch day | Set `PRODUCTION_WRITE_MODE_GA_UNLOCKED=1` (or `BETA_PRODUCTION_GATING_ENABLED=0`) on the API |

Superadmin marks partners: `PATCH /api/admin/workspaces/{id}/beta-partner` with `{ "enabled": true, "reason": "…" }`.

## Partner onboarding (week 0)

1. **Staging first** — connect a non-production Odoo (sandbox/staging URL), not the live ERP.
2. **Least-privilege user** — dedicated Odoo user + API key per `docs/LEAST-PRIVILEGE-ODOO-USER.md`.
3. **Observer → standard** — browse and validate; admin unlocks standard write mode on staging.
4. **Production readiness checklist** — on staging connection Overview: snapshot drill, health check, probe, least-privilege confirm, artifact download verify.
5. **Trust contract** — partner admin reads Settings → Trust & safety (`docs/SAFETY.md`).
6. **Mark beta partner** — superadmin enables `beta_partner` on the workspace.
7. **Production on staging only first** — unlock production write mode on staging; run one controlled mutating workflow end-to-end.
8. **Live connection** — repeat checklist on production connection before enabling production mode there.

## Weekly cadence (during beta)

- Review **admin trust telemetry** (`GET /api/admin/trust-telemetry`): bulk runs, refusals, aborts, restores, anomaly trips.
- Scan audit log for unexpected 403/409 refusals or writes_paused events.
- Partner confirms no unrecoverable-data incidents that week (email/support ticket).

## Incident reporting

1. Partner pauses writes (`writes_paused` on connection or workspace).
2. Capture: connection id, snapshot ids, bulk run ids, time window, what changed in Odoo.
3. File internal incident note; classify recoverable vs partial vs data loss (see SAFETY.md table).
4. If unrecoverable data loss → pause new beta partners until root-caused.

## GA exit criteria (default thresholds — env-tunable)

| Criterion | Default |
| --- | --- |
| Beta partner workspaces | **8** (`BETA_GA_MIN_WORKSPACES`) |
| Weeks active per workspace | **4** (`BETA_GA_MIN_WEEKS`) |
| Unrecoverable-data incidents | **0** (operator-attested) |
| SafetyGate bypasses | **0** (meta-test green + no audit evidence of ungated mutation) |

Evidence dashboard: admin console trust telemetry + weekly partner attestations stored offline.

## Launch day

1. Confirm exit criteria met — log decision in `MEMORY.md` using GA template.
2. Set `PRODUCTION_WRITE_MODE_GA_UNLOCKED=1` on production API.
3. Announce in release notes: production mode still requires per-connection readiness checklist.
4. Keep `beta_partner` flag for reporting; optional to retire later.

## Environment variables

```bash
BETA_PRODUCTION_GATING_ENABLED=1          # default on
PRODUCTION_WRITE_MODE_GA_UNLOCKED=0       # flip to 1 at GA
BETA_GA_MIN_WORKSPACES=8
BETA_GA_MIN_WEEKS=4
```
