# BOT-KILL-AUDIT: Kill switch and append-only Bot audit

ID: BOT-KILL-AUDIT
Title: Per-DB and global kill switch checked before every write; append-only Bot audit
Status: todo
Phase: 5
Priority: P1
Type: build
Owner: NF (backend)
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BOT;NF-BOT-KILL-AUDIT
Depends on: BOT-RISK-CLASSIFIER (audit rows carry class/rule ids); BV-AUDIT-WIRE startup hook. Blocks: BOT-CLONE-REHEARSAL.
Routing: Worker: L2 · schema change · Tester + Reviewer separate sessions
File allow-list (4):
- apps/api/app/bots/guard.py (new; kill switch + write gate)
- apps/api/app/bots/audit.py (new; append-only writer)
- apps/api/alembic/versions/<new>_bot_kill_audit.py (new)
- apps/api/tests/test_nf_bot_kill_audit.py (new)
Goal: No Bot write reaches Odoo when a kill switch is on, and every Bot decision leaves an immutable record.
Steps: 1. Tests first. 2. STOP-AND-ASK: a needed file is outside the allow-list; a non-`ingenium_` DB; a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434, 54329); a git write; a new dependency.
Acceptance criteria:
- AC1 guard.check(db_fingerprint) runs before every write RPC; global or per-DB flag on → refusal RF-ANY "kill switch". Evidence: test with a recording stand-in RPC: zero write calls.
- AC2 Readback mismatch trips the per-DB switch automatically and audits the trip. Evidence: test.
- AC3 Audit row: who, approver, task id, class, diff hash, blast count, snapshot id, idempotency key, decision; no secrets (password/api key/token fields rejected). Evidence: test.
- AC4 Append-only: app role has no UPDATE/DELETE on bot_audit (DB-level revoke or trigger); attempted update fails. Evidence: test on PG 54339.
- AC5 Idempotency: same key twice → second is a no-op with a "duplicate" row. Evidence: test.
- AC6 Guard state read failure → treat as ON (fail closed). Evidence: test.
- AC7 Migration up/down clean on ingenium_* DB.
Non-goals: UI toggle (later card), clone/snapshot, executing tasks.
Test plan: own tests x2; combined focused set both orders (fwd/rev) x2 each; test PG 54339. Chaos: switch flipped mid-batch → remaining calls refused, batch reports partial with counts; DB connection drop during audit write → write refused; concurrent writers do not interleave rows for one key.
What can still go wrong: writes issued outside the Bot path (direct connector calls) bypass the guard — Reviewer greps for raw execute_kw writes in bots/; switch is checked per call, so a single in-flight call can still land.
Evidence to log: PROGRESS line; migration up/down output.
Rollback: alembic downgrade; revert files.
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.

## Worker result (2026-10-25, after reviewer round 1 + pacing correction)
Token plan: targeted reads only, mechanical steps low-effort, no screenshots, focused tests.
- guard.py: KillSwitch (global + per-DB; unreadable/missing global row = ON; anyone may turn ON; only owner_of(scope), NFKC/casefold-normalised, may clear or tighten overrides; lookup failure denies). A job = one plan: sha256(db, task, model, values, exact ids), hard total N counted from intent rows (CapError past N). 50/batch and 500/checkpoint are pacing: each checkpoint re-reads the segment and re-checks the switch; clean = continue with no new approval; failure = trip per-DB switch + undo the segment. Same plan again (any new key) reuses the live job → "duplicate", never extra records; a new plan needs a new grant. Grants: owner-only create_grant, single-use (atomic UPDATE … used_at IS NULL), bound to db, plan hash, N, level ≥ need, approver (normalised, never the bot), expiry. L2/L3 classes and N > 500 need a grant (N > 500 → L3). Kill checked before the job, each batch and each record call; in-flight kill undoes the batch.
- audit.py: intent row before write (no row = no write); sha256 chain under an advisory lock; external append-only anchor file (id, count, head hash, fsync, written before commit) → verify_chain detects edits and tail truncation; secrets rejected by key name (with/without separators) and value shape (bearer, JWT, sk_/ghp_/AKIA, ≥40-char base64/hex); redact() for gate text; idempotency unique per (db, key, batch) and (job, batch); follow-up rows carry real blast_count.
- Migration d8e9f0a1b2c3: bot_kill_switch, bot_cap_override (CHECK tighten-only), bot_grant, bot_job, bot_audit; append-only triggers; bot_audit + trigger fn owned by NOLOGIN bot_audit_owner, app role bot_app gets INSERT/SELECT only (tested: cannot ALTER/DISABLE TRIGGER/UPDATE/DELETE/TRUNCATE). Up/down tested.
- BV tests (approved): head assertions now "rev is ancestor of the single head"; ORM drift ignores raw-SQL bot_* tables/indexes.
- Caveats: migration needs CREATEROLE/superuser; deploy must log in as a member of bot_app, not the migration owner; a superuser can still tamper (detected by chain + anchor, not prevented); anchor path BOT_AUDIT_ANCHOR (default ~/.ingenium/bot_audit/<db>.anchor) must be on durable storage; a commit failure after the anchor write leaves a false-positive anchor; one in-flight RPC can land before undo; grant_source hook is the owner-UI seam (tests use a fake owner).

## Follow-ups (reviewer round 2, LOW)
- bot_app role can write bot_grant / bot_kill_switch via raw SQL; owner checks live only in Python. Move to DB-level (SECURITY DEFINER fns / RLS).
- redaction: apply NFKC normalisation and strip Unicode format chars (Cf) before secret matching.
- anchor file lives on the app host; needs an external append-only sink.
- downgrade leaves bot_app / bot_audit_owner roles behind.
- migration needs CREATEROLE/superuser; document in deploy runbook.
