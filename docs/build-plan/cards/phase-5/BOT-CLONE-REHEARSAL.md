# BOT-CLONE-REHEARSAL: Rehearsal on every target type, with identity guard

ID: BOT-CLONE-REHEARSAL
Title: Route B neutralized clone (DB access) or Route A RPC rehearsal (duplicate/staging DB or proven first batch); guard against prod/copy confusion
Status: todo
Phase: 5
Priority: P1
Type: build
Owner: NF (backend)
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BOT;NF-BOT-CLONE-REHEARSAL
Depends on: BOT-KILL-AUDIT (guard + audit store holds before-images). Blocks: BOT-SNAPSHOT-PROOF, BOT-DIFF-BLAST L2/L3 execute.
Routing: Worker: L3 · Tester + Reviewer separate sessions
File allow-list (7):
- apps/api/app/bots/clone/neutralize.py (new)
- apps/api/app/bots/clone/fingerprint.py (new)
- apps/api/app/bots/clone/rehearse.py (new; route selection A/B)
- apps/api/app/bots/clone/rpc_copy.py (new; Route A duplicate/staging target)
- apps/api/app/bot_verify/targets.py (consume fingerprint only)
- apps/api/tests/test_nf_bot_clone.py (new)
- apps/api/tests/test_nf_bot_clone_live.py (new)
Goal: No prod step without a passed rehearsal. Route B (direct DB): full neutralized clone <24h old. Route A (RPC-only: Odoo Online, Odoo.sh, hosted): rehearse on a user-supplied copy (Online "Duplicate", Odoo.sh staging) when given; otherwise the proven-first-batch undo of BOT-SNAPSHOT-PROOF is the rehearsal. Hosted is never a refusal by itself.
Steps: 1. Tests first. 2. STOP-AND-ASK: a needed file is outside the allow-list; a non-`ingenium_` local DB; a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434, 54329); a git write; a new dependency; cloning a non-disposable DB without an owner approval row.
Acceptance criteria:
- AC1 Route detect: DB access probe → B, else A; recorded in rehearsal row. Evidence: test both routes.
- AC2 Route B clone ingenium_clone_*; neutralize via Odoo's own neutralize (17+) plus checks: mail servers off + SMTP trap, ir.cron inactive, payment providers disabled/test, HTTP webhooks/base_automation off, IAP off. Any item fails → refuse (never half-neutralized). Evidence: per-item assertions.
- AC3 Fingerprint = hash(database.uuid, database.create_date, db name, URL host, major). Prod step refuses when ≠ approved target; rehearsal target must differ from prod. Evidence: swapped-fingerprint test → RF-ANY.
- AC4 Route A copy guard: copy must have different db name/host AND (Online Duplicate keeps uuid) a marker param `ingenium.rehearsal_copy=<nonce>` written by the Bot to the copy and verified absent on prod before any write; then the copy is neutralized over RPC (ir.mail_server inactive, ir.cron inactive) and read back. Evidence: test where copy==prod → refusal; live 17/20 two-DB run.
- AC5 Rehearsal record: route, target fingerprint, taken_at, task id, walkthrough + readback result; prod refuses if missing/failed/stale (>24h). Evidence: tests.
- AC6 Odoo 20 uses JSON-2/JSON-RPC only (no XML-RPC). Evidence: live 20 run.
Non-goals: snapshots/undo (BOT-SNAPSHOT-PROOF), outbound sinkhole proof (BOT-SINKHOLE), lockout sim, generic walker.
Test plan: own tests x2; combined focused set both orders (fwd/rev) x2 each; test PG 54339. Live 17 + 20 (19: cron/neutralize delta) on ingenium_nf_* sources; Route A simulated with two ingenium_nf_* DBs reached by RPC only. Chaos: clone killed midway → leftover dropped, retry idempotent; stale (25h) refused; source changed after clone → mismatch refused; marker found on prod → refused.
What can still go wrong: user copy is old, so rehearsal data drifts from prod (show copy age; diff/blast always computed on prod); Online Duplicate shares uuid (hence marker); neutralize misses custom-module senders; clone disk usage.
Evidence to log: PROGRESS line; live 17/20 neutralize table; Route A guard table.
Rollback: revert files; drop ingenium_clone_* DBs; remove marker param from copies.
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.

## Worker result (2026-10-25)
Token plan: targeted reads, mechanical steps low-effort, no screenshots, focused tests.
- fingerprint.py: Identity = sha256(database.uuid, create_date, db name, normalised host:port, major), read over RPC; missing/blank/duplicate param, bad URL, major outside 17-20 -> RF-ANY. check_target refuses same fingerprint, same db name (alias/proxy) or a different major.
- rpc_copy.py (Route A): JSON-RPC client (stdlib, no XML-RPC, forbidden ports refused). prepare_copy: identities -> no marker on prod -> fresh nonce `ingenium.rehearsal_copy` written to copy -> absent on prod (alias detected, our marker removed) -> read back on copy -> RPC neutralize + read-back; verify_copy re-runs before every rehearsal write. Prod is never written.
- neutralize.py: mail servers off + one loopback SMTP trap (no odoo.conf fallback), templates unpinned, all crons off, payment disabled/test, base.automation off, fetchmail off, IAP tokens disabled, is_neutralized; read-back per item, any FAIL or unreadable item -> refuse; uninstalled model = n/a.
- rehearse.py: detect_route (Online/Odoo.sh -> A; direct-DB probe ok -> B; error -> A). Cloner (B): source must be ingenium_* or have an owner approval (else refuse); ingenium_clone_<sha12(src,plan)>; pg_dump|pg_restore (online, no session kills on prod) + filestore + new database.uuid + `odoo neutralize`; any failure drops the clone, retry idempotent. RehearsalRecord (route, prod/target fp, task, plan hash, N, diff hash, prod write_date state hash, taken_at, walkthrough + read-back, copy age, backup note from database_backup) in an append-only hash-chained fsynced JSONL (BOT_REHEARSAL_STORE). apply(): identity == approved fp == spec fp, then a matching, passed, unconsumed record <24h old with unchanged prod state, consumed under lock, then WriteGate.run; refusals are audited via the guard.
- targets.py: resolve_target(identity=, prod_fingerprint=) refuses a walk on prod or on an identity that does not match url/db; old callers unchanged.
- Tests: test_nf_bot_clone.py 46 (marker spoof/plant/alias, prod-looking URL, copy==prod, clone still sends mail x6, stale 25h/future, reuse, plan/N change, source drift, swapped fp, store tamper, kill midway x5, owner approval, SQL-ish names) with real KillSwitch/AuditLog/WriteGate on PG 54339. test_nf_bot_clone_live.py: 17, 19, 20 pass x2 (JSON-RPC, XML-RPC patched to raise).
- Live neutralize table (17/19/20 same): after `odoo neutralize` mail_server FAIL (Odoo adds its own "invalid" server), smtp_trap FAIL, cron FAIL (autovacuum left on), flag ok; after RPC layer all ok, payment n/a (not installed in seed). Route A guard table: copy==prod refused, marker on prod refused, copy neutralized ok, prod crons/marker unchanged, plan change + reuse refused, matching rehearsal applied.
- Caveats: rehearsal store is a file, not a DB table (a migration is outside the allow-list), so it needs durable storage; a local-root user can rewrite the whole chain. A copy that echoes writes without storing them would pass the marker step; custom-module senders are not neutralized. Route A copies may be old (copy_age_s recorded; diff/blast stay on prod). The clone package has no __init__.py (not on the allow-list; namespace package). Route A without a copy (proven first batch) belongs to BOT-SNAPSHOT-PROOF. Payment checks were not exercised live.
- Raw-write invariant (Tope-approved 2026-10-25): test_no_raw_rpc_writes_in_bots exempts exactly app/bots/clone/rpc_copy.py. Pin test (AST): one execute_kw, only inside JsonRpc._guarded_execute_kw, whose first statement is _require_proof (reads pass; writes need a CopyProof bound to this client's db/host with copy fp != prod fp and db != prod db; before marker verification only the marker nonce may be written); no other app/bots module except rehearse.py imports rpc_copy or uses the wrapper. Prod is never written by JsonRpc (Route B clients get a proof via rehearse.prove_clone); prod writes stay WriteGate-only (live test uses a test-side writer). Adversarial: no proof, forged proof (copy fp == prod, prod-looking URL), proof for another client, pending marker, alias via real client. Final: own 46 + live 17/19/20 x2, combined both orders x2 = 3041 passed, 0 failed; ruff clean.
- Reviewer round (2026-10-25): (1) neutralize.py is now structural: RULES cover delivery.carrier prod_environment, account_edi_proxy_client.user edi_mode, payment provider/token, mail servers + trap, crons, fetchmail, IAP, oauth, LDAP, POS terminals, calendar refresh tokens, push devices (unlinked), ir.actions.server webhook_url (-> loopback); every rule reads back every record of its field; a write error or ignored write refuses; missing model/field = n/a. Drift test: every SENSITIVE_MODELS model or model with a stored OUTBOUND_STEMS field in fields_inventory 17-20 is ruled or in NOT_OUTBOUND with a reason. (3) CopyProof carries an HMAC (process-held key, minted only by attach_proof); forged or mutated proofs refused; the AST pin now scans all of app/. (4) webhook server actions neutralized. (2) guard.py (approved): WriteGate.run on prod refuses RF-ANY without a Rehearsals provider and spec.rehearsal_id; reserve() re-picks the named rehearsal against plan hash, record set, values and recency under the store lock; any refusal before a write releases it; grants bind rehearsal_id (create_grant requires it, open_job matches it). Migration e9f0a1b2c3d4 (down d8e9f0a1b2c3, single head) adds bot_grant.rehearsal_id + NOT VALID check. c19 passes (no xfail). Flake: scans_contract ac3[victim-normal] not reproduced in 6 reversed full runs; the cause was not found and nothing was changed; comb runs now tee full logs to /tmp/combN.log. Final: live 17/19/20 3 passed; combined both orders x2 = 3059 passed each; ruff clean.

## Follow-ups (Reviewer round 2 LOW, 2026-10-26)
- attach_proof() mints proofs for any identity; protected only by the AST pin test.
- The gate does not check that its RPC client is connected to spec.db_fingerprint.
- test_nf_bot_scans_contract ac3[victim-normal] fails only in reversed order; unresolved (guess: login rate limit or leaked dependency override).
- Full suite hung near 96% with 7 failures starting at test_ai_architecture_close::test_close_repairs_music_session_fk_and_stock_clones; unverified.
