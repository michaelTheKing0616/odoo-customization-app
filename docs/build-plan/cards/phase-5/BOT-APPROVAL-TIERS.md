# BOT-APPROVAL-TIERS — L1/L2/L3 approval tiers for bot plans

Owner: NF (Grok Bot). Depends on BOT-RISK-CLASSIFIER, BOT-KILL-AUDIT, BOT-CLONE-REHEARSAL, BOT-SNAPSHOT-PROOF.
Decisions: DECISIONS.md (tiers APPROVED; risk per button; 50/500 = pacing; the plan's exact N is the only ceiling).

## Spec
1. `app/bots/approval.py` turns a bot plan (db, task, model, exact ids, values, risk class,
   subkind, irreversible flag, rehearsal id + result, undo route, proven outside-plan fields)
   into a tier with plain reasons. Tiers only go up: max of the class tier (`base_tier`), L2
   for outside-plan side effects, L3 for irreversible work or N > the run checkpoint.
   Fails closed (refused, never a lower tier) on: no/failed rehearsal, unknown risk class,
   N < 1, no undo route (reversible work needs the before-image route; irreversible needs a
   verified snapshot), bad ids/values.
2. Persistence `bot_approval` (alembic f0a1b2c3d4e5): one row per plan hash; status
   auto (L1) | pending (L2/L3) | approved | rejected | refused. Tier, N, reasons and card are
   server-computed; no client input can set them.
3. Approve = owner-only, human approver other than the requester/bot, row locked
   (`FOR UPDATE`), grant issued through `KillSwitch.create_grant` with level = stored tier and
   n_records = stored N, bound to plan hash + rehearsal. Reject is final. Both audited
   through `AuditLog` (hash chain; decisions `approved` / `rejected` added to the check).
4. Run wiring (opt-in, guard.py untouched): `TierRehearsals` wraps the rehearsal store and
   refuses any run whose plan has no auto/approved row, a rejected/refused row, a different
   N, or a risk class lower than recorded (tier downgrade). `grant_source` hands the gate
   only the stored grant id (client grant ids ignored). `route_approval()` gives RouteA the
   stored tier (0 when not approved), so outside-plan side effects need an L2 grant.
5. API `/api/connections/{id}/bot-approvals`: GET list (pending first), GET `/{aid}` plan
   card, POST `/{aid}/approve`, POST `/{aid}/reject`. Card shows what changes, record
   count, risk, undo route, rehearsal result, and the known limits from BOT-SNAPSHOT-PROOF
   (other models, translations in other languages, company-dependent values).
6. Web: approval card (tier, reasons, count, undo, Approve/Reject, honest refusal).

## Adversarial tests (permanent)
forged grant id, replayed grant, grant for another plan, N+1 records, missing proof,
tier downgrade (client level / lower risk class), concurrent approvals (one wins),
rejected plan never runs (incl. L1), self-approval, non-owner approval.

## Results (2026-10-26)
- New tests `tests/test_nf_bot_approval_tiers.py`: 36 pass. With kill_audit, risk,
  risk_adversarial, clone and snapshot suites: 2225 passed, 6 skipped, in both orders
  (new tests first and last). Raw-RPC-write ban and migration round trip stay green.
- Web: `BotApprovalCard.test.tsx` 8/8 (vitest); eslint clean; `tsc --noEmit` clean.
- ruff check + format clean on all changed Python files.
- Behaviour added during build: resubmitting the same plan only ever makes it stricter
  (plan hash does not include the risk class; a higher tier or refusal escalates an
  undecided row; decided rows stay and runs re-check the class).

## Known gaps / follow-ups
- L1 plans are `auto` and can't be rejected from the UI (no human step by design); they
  still never run without a row, and an escalation moves them to pending.
- A grant made just before a failed audit append is left unused (never handed out: runs
  only receive the grant id stored on an approved row; it expires after 1h).
- Deciding needs `auth_mode=accounts` and an owner/admin role; auth-off installs can see
  cards but can't approve (honest 403), same as SEC-2APPROVER's open item.
- No bot yet calls `ApprovalStore.submit`; BOT-SPINE-WIRE must build `Plan` from the
  classifier + rehearsal + snapshot results and wire `TierRehearsals`, `grant_source`,
  `approval_for` and `route_approval` into WriteGate/RouteA.
- Page has no nav entry yet (route `/connections/{id}/bot-approvals`).
- Migration f0a1b2c3d4e5 is a new alembic head: any parallel migration must chain after it.
- Roles are not separated in practice: no migration adds a login role to `bot_app`. BOT-SPINE-WIRE must create a separate bot login that is a member of `bot_app`. The comment at d8e9f0a1b2c3_bot_kill_audit.py:134 ('app role (member of bot_app)') misleads: adding the API role to `bot_app` would make `bot_is_bot()` true for the API, refuse its approve/decide calls and remove its TEMP.
- The large-object revoke from PUBLIC is a no-op (warning) when the migrator is not a superuser; document that this step needs a superuser, or make it fail loudly.
- TEMP and large-object access are granted only to the migrating role: if the runtime API role differs, it loses TEMP; document this.

## Tracking lines (final, applied at merge)
- PROGRESS (final, applied): `- 2026-10-26 · BOT-APPROVAL-TIERS · pytest -q -p no:randomly tests/test_nf_bot_approval_tiers.py tests/test_nf_bot_role_privileges.py · merged (independent review round 5 APPROVE): L1/L2/L3 tiering (fail-closed), bot_approval table + role lockdown (f0a1b2c3d4e5; privilege drift test, 18-entry allowlist), owner-only audited approve/reject issuing plan-bound single-use grants, /bot-approvals API + web card; 2254 pass both orders · [Done, code]`
- STATE_NF (final, applied): `- BOT-APPROVAL-TIERS (2026-10-26): merged on premium-local-tip + nf-backend (commit subject BOT-APPROVAL-TIERS). approval.py, bot_approvals router, f0a1b2c3d4e5, BotApprovalCard; L1/L2/L3 tiers, bot role lockdown. Independent Reviewer APPROVE (round 5). Done. Next: BOT-SPINE-WIRE submits plans, creates separate bot login.`

## Round 2 results (review BLOCK fixes)
- MEDIUM: `facts_hash` (risk, irreversible, subkind, undo route, backup, outside-plan fields, n, rehearsal id/ok) is stored on each row. Approval pins `decided_facts_hash`; `reserve` and `grant_source` fail closed if they differ. Resubmitting an approved row with changed facts voids its grant and sends it back to pending (or refused). Tiers only go up (max of old and new).
- LOW a: BEFORE UPDATE trigger `bot_approval_guard` plus column-level grants. bot_app cannot decide or relax a row, decided rows are frozen, rejected rows are final.
- LOW b: the L3 label now says "workspace owner or admin" (backend `TIER_LABEL`; the UI shows the backend label).
- LOW c: a refused row is re-evaluated on resubmit; a rejected row stays rejected.
- Tests: approval file 43/43. With kill_audit/risk/risk_adversarial/clone/snapshot: 2232 passed, 6 skipped, in both orders (migration round trip and single head green). Web vitest 8/8, tsc and eslint clean, ruff clean. Reviewer probe a04 (old "stays refused" expectation) is superseded by the permanent test `test_a04_refused_plan_reevaluated_rejected_stays`: refused is re-evaluated, rejected stays rejected. All other probes pass.
- Known gaps: bot_app still has INSERT on bot_grant (pre-existing). An approved row being reopened by escalation is not written to the audit log (no decision value exists for it).

## Round 3 results (review BLOCK: bot self-approval)
- MEDIUM (b01): migration f0a1b2c3d4e5 runs `REVOKE INSERT, DELETE, TRUNCATE ON bot_grant FROM bot_app`, leaving bot_app only SELECT and UPDATE (used_at, job_id); downgrade restores INSERT. `KillSwitch.create_grant` and the KILL-AUDIT/CLONE tests use the owner engine, so no fixture relied on bot_app minting grants and none were changed. `bot_approval_guard` is now BEFORE INSERT OR UPDATE: an INSERT by bot_app needs status auto/pending/refused with grant_id, decided_by, decided_at and decided_facts_hash all NULL.
- LOW: voiding on resubmit appends an audit row (decision 'refused', reason "approval voided: plan facts changed", key `approval:<id>:void:<grant>`). 'refused' was already allowed, so the check is unchanged.
- Tests: approval file 46/46 (adds b01 exact scenario, forged approved/rejected INSERT using a real grant, and the audit row on void). With the suites: 2235 passed, 6 skipped, in both orders (migration round trip and single head green). Reviewer probes appr2: 6/6. ruff clean. Web not touched.
- Other bot_app write grants (listed only, not changed; not approval/grant minting): INSERT/UPDATE on bot_job, bot_kill_switch, bot_cap_override (from d8e9f0a1b2c3); INSERT on bot_audit (append-only, by design).
- Known gap: the trigger can't re-tier, so bot_app can still INSERT a fresh row as 'auto' for a plan that deserves L2/L3 (needs an API-only insert path or a server-side tier recompute).

## Round 4 results (bot role hardening, all in f0a1b2c3d4e5; kill-audit migration untouched)
- Approval rows: bot_app now has SELECT only on bot_approval (no INSERT/UPDATE). Submit and decide already run on the API engine (`app.db.engine`, the same owner path as `create_grant`); the bot runtime only reads rows. The trigger stays as defence in depth (shared `bot_is_bot()` helper).
- Probe finding, job forgery (real): `open_job` reuses any live job (open/done) for the same db+plan, and the run uses that job's level without checking `need`. A bot-inserted `bot_job` row therefore skipped the grant. Closed with the `bot_job_guard` trigger plus column grants:
  - Bot INSERTs must be 'open'. Level >= 2 needs the grant this transaction consumed for this exact job (job_id, used, db/plan/n match, level >= job level). Level 1 needs an owner-written auto approval row (tier 1, same db/plan/n).
  - Bot UPDATE is limited to `status`, and a job can never be revived or reopened.
- Kill switch (real: bot_app could UPDATE is_on=false): the `bot_kill_switch_guard` trigger lets the bot turn switches on, never off.
- Caps (real: bot_app could INSERT/UPDATE bot_cap_override): INSERT/UPDATE revoked.
- Downgrade restores the old grants and drops the triggers and functions.
- Tests: approval file 55/55. New tests:
  - bot INSERT on bot_approval fails for all 5 statuses
  - honest bot-role runs still work at L1 and L2
  - a bot run with no owner auto row is refused
  - forged L1/L3 live jobs, reopening a job and changing a job's level are refused
  - turning the switch off and raising caps are refused
  - Run as a real LOGIN role IN ROLE bot_app.
- Suites (kill_audit/risk/risk_adversarial/clone/snapshot): 2244 passed, 6 skipped, in both orders (migration round trip and single head green). Probes appr2 6/6. ruff clean.
- Remaining / for the kill-audit owner: open_job should also refuse a reused job whose level < need (`if live and int(live[1]) < need: return Refusal(...)`). The trigger closes the forgery path, but that guard.py check is belt-and-braces and outside this card. The level-1 job rule assumes every production bot run goes through TierRehearsals (auto row); a runtime that bypasses approvals would have its level-1 jobs refused for the bot role.

## Round 5 results (review round 3: c03/c05/c06 plus privilege drift guard; all in f0a1b2c3d4e5)
- M1 kill switch: table UPDATE revoked. bot_app keeps UPDATE only on (is_on, reason, set_by, set_at), which the trip upsert needs. `bot_kill_switch_guard` refuses any bot scope change and any bot ON->off.
- M2 grant replay:
  - The new `bot_grant_guard` trigger lets the bot set used_at/job_id only while used_at IS NULL. It must set both, and can never touch them afterwards.
  - `bot_job_guard` now makes every non-open job status final: no status change out of done/failed/stopped/killed.
- Structural drift guard: `tests/test_nf_bot_role_privileges.py` reads the live catalog via has_table/column/sequence_privilege, so direct, PUBLIC and inherited grants all count. It also checks role memberships, bot_* objects bot_app owns, callable SECURITY DEFINER functions and default ACLs. Any privilege missing from a reviewed 18-entry allowlist (each with a reason) fails the test; so does a stale allowlist entry. Present bot_* objects: bot_approval, bot_audit (+seq), bot_cap_override, bot_grant, bot_job, bot_kill_switch. The grant-rehearsal migration adds only a column, and clone/snapshot create no bot_* tables. No memberships, owned objects, SECURITY DEFINER functions or default ACLs for bot_app.
- L1 jobs need an owner-written auto approval row. `test_bot_runtime_refuses_plan_without_owner_auto_row` runs as a real LOGIN role IN ROLE bot_app (the suites run as superuser, so they don't exercise this). **BOT-SPINE-WIRE must submit every plan through ApprovalStore (API/owner engine) before the bot runtime runs it**, or L1 runs are refused.
- Tests: approval + privilege files 68/68, including permanent c03/c05 (switch move/off) and c06 (job finished->failed, grant re-point, used_at reset, second L2 job on a used grant). Probes appr3 all pass. With kill_audit/risk/risk_adversarial/clone/snapshot: 2247 passed, 6 skipped, in both orders (migration round trip and single head green). ruff clean.
- Still recommended for the kill-audit owner, outside this card: `open_job` should refuse a reused live job whose level < need.

## Round 6 results (review round 4: temp-table shadow; all in f0a1b2c3d4e5, guard.py untouched)
- MEDIUM temp shadow: dynamic SQL on current_database():
  - GRANT TEMP to the migrating/API role (current_user) explicitly, then REVOKE TEMP from PUBLIC and TEMP, CREATE from bot_app.
  - `ALTER ROLE bot_app IN DATABASE <db> SET search_path = public, pg_temp` (per-database, so the round trip doesn't leak to other DBs on the cluster).
  - Downgrade resets search_path and re-grants TEMP to PUBLIC.
  - Note: role settings are not inherited. LOGIN members of bot_app get the search_path only if set on their own role. The TEMP revoke is what actually closes the shadow for them: they can't create a temp table at all.
- LOW large objects: EXECUTE on lo_create(oid), lo_creat(integer) and lo_from_bytea(oid,bytea) revoked from PUBLIC (per-database function ACL) and granted to the migrating/API role. Server-side lo_import/lo_export are already superuser-only. No app code uses large objects. Downgrade re-grants to PUBLIC.
- LOW SET ROLE: a real LOGIN member of bot_app cannot `SET ROLE <owner>` (tested). The probe's success there is a harness artifact: its session user is superuser, and SET ROLE is checked against session_user.
- Drift test adds `test_bot_app_cannot_shadow_or_escape`:
  - bot_app has no database TEMP or CREATE and no CREATE on schema public
  - the pg_db_role_setting search_path is exactly `public, pg_temp`
  - no EXECUTE on lo_create/lo_creat/lo_from_bytea/lo_import/lo_export
  - no superuser/createrole/createdb/bypassrls/replication attributes
  - the API role still creates a temp table
  - The allowlist is still 18 entries.
- Permanent tests (real LOGIN role IN ROLE bot_app): temp shadow refused on bot_kill_switch/bot_grant/bot_approval/bot_job; d99 (the switch reads ON on the same pooled bot connection after a refused shadow attempt); SET ROLE to the owner and lo_create/lo_from_bytea refused.
- Reviewer probes appr4: all pass except two, both harness artifacts of the superuser session, not real-role behaviour: `d99_temp_shadow_hides_kill_switch` now errors because CREATE TEMP is refused, and `set_role_postgres`.
- Suites (kill_audit/risk/risk_adversarial/clone/snapshot + trust3_blast_radius; no diff_blast test file exists in this worktree): 2260 passed, 6 skipped, in both orders (migration round trip and single head green). ruff clean.
- Caveat: the PUBLIC TEMP and large-object revokes apply to every role in this database; only the migrating/API role is re-granted. Any other login role that needs temp tables must get an explicit GRANT TEMP.
