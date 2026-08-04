# SAFETY.md — Trust & safety contract (Wave 12 TRUST-8)

> User-facing honesty contract for live Odoo mutation. Rendered in-app under **Settings → Trust & safety**.
> The app never exceeds your Odoo user's permissions. It uses public ORM/RPC only — **no direct SQL**.

## Permission model

- Every mutation runs as the **Odoo user on the connection** (password or API key you provided).
- The platform cannot grant rights your Odoo user does not have.
- **Observer** mode blocks all mutating RPC at the client layer (browse/analyze/Expert still work).
- **Standard** mode enables mutating routes with SafetyGate, snapshots, and confirm gates where configured.
- **Production** mode requires the **production readiness checklist** on that connection (see below).

Use a **dedicated Odoo user** scoped to the apps you customize — not your main admin account. See `docs/LEAST-PRIVILEGE-ODOO-USER.md`.

## What snapshots contain

Snapshots store JSON payloads captured **before** risky metadata changes: view arch, automations, ACL rows, menus, reports, and CSV exports for field hard-delete. They live in the **app database**, separate from Odoo.

Snapshots are taken automatically before many mutating operations when configured. You can list and rollback from the Journal / snapshot endpoints.

## Reversibility (verified TRUST-4 table)

| Change type | Reversibility | Notes |
| --- | --- | --- |
| View arch edits | **Fully reversible** | Rollback restores prior arch via RPC |
| Automations + linked server actions | **Fully reversible** | Best-effort scalar + action restore |
| ACL / access rules | **Fully reversible** | Created rules can be unlinked on rollback |
| Menus, reports (metadata) | **Fully reversible** | Snapshot payload drives restore |
| Field **deprecate** (`x_deprecated_*`) | **Fully reversible** | Readonly rename path; data kept |
| Field **hard delete** | **Partially reversible** | CSV exported first; column drop not recoverable from CSV alone |
| Model delete | **Partially reversible** | JSON export when implemented; DB tables may remain |
| Bulk record delete / unlink | **Not reversible** | Snapshots do not restore business data |
| Dropped DB columns / data loss | **Not reversible** | Warn before destructive ops |

Labels in the UI: **Fully reversible**, **Partially reversible — …**, **Not reversible**.

## Blast radius (TRUST-3)

| Control | Default |
| --- | --- |
| Sample-first threshold | 50 records (pause after sample batch) |
| Reversible cap | 1,000 records / request |
| Destructive cap | 200 records / request |
| Batch size | 25 records |
| Batch sleep | 200 ms |
| Hourly auto-pause | 500 mutations / connection / hour |

Tune via `BULK_CAP_*`, `BULK_BATCH_*`, and `BULK_ANOMALY_*` env vars on the API.

## Concurrency & kill switch (TRUST-2 / TRUST-5)

- **One mutating apply or bulk run per connection** at a time (`409 mutation_in_progress`).
- **writes_paused** on workspace or connection blocks all Odoo mutations until cleared.
- Bulk transitions: on transport errors, **fingerprint re-read** before retry (`write_date`, `display_name`).

## Validation scope (honest)

| Surface | Validated on |
| --- | --- |
| Clean sandbox Odoo 19 | `docker/run-sandbox-gate.sh`, RPC integration tests |
| Dirty instance (19 + contacts/mail/crm/sale) | `docker/run-dirty-gate.sh` |
| Odoo Community **19, 18, 17** | GA capability registry |
| Odoo 16 | Experimental — some features omitted |
| OCA addon matrix | **Not** covered by dirty gate today |

Re-run gates on your hardware; numbers in older sections are indicative only.

## Incident playbook

1. **Pause writes** — toggle writes_paused on the connection or workspace.
2. **Assess** — Audit log (`/api/audit/logs`) and connection Journal / bulk run results.
3. **Restore** — Rollback snapshots where reversible; import CSV exports for field deletes if needed.
4. **Escalate** — If data loss occurred, treat as partial recovery only; contact your operator with snapshot IDs and run IDs.

## Production readiness checklist

Before **Production** write mode unlocks, each connection must pass:

1. **Snapshot + restore drill** — creates a drill snapshot; validates restore payload (app DB).
2. **Health check green** — latest run `complete` with zero broken artifacts.
3. **Capability matrix probed** — connection probed (server version recorded).
4. **Least-privilege confirmed** — admin acknowledges dedicated-user guidance (warns if user looks like admin).
5. **Backup artifact download verified** — drill CSV artifact downloaded and marked verified.

Complete the checklist on the connection **Overview** card. Production mode stays blocked until all items pass.

**Pre-GA (TRUST-9):** production write mode is also limited to **beta partner** workspaces unless the API has `PRODUCTION_WRITE_MODE_GA_UNLOCKED=1`. See `docs/BETA_PROTOCOL.md`.

## Not claimed

- Zero-downtime on customer production during bulk runs.
- Perfect undo for dropped columns, unlinked records, or mass deletes.
- Risk-free customization — ERP changes always carry operator responsibility.
- Fully reversible **everything** — see table above.

## App database

The app Postgres holds snapshots and encrypted credentials. Back up regularly — see `docs/DEPLOY.md` and `scripts/restore_app_db.sh`.
