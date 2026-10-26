# BOT-SNAPSHOT-PROOF: Proven undo before risky steps, on every target type

ID: BOT-SNAPSHOT-PROOF
Title: Route A before-image + reverse-write undo proven on batch 1; Route B pg_dump + filestore restore-verified
Status: todo
Phase: 5
Priority: P1
Type: build
Owner: NF (backend)
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BOT;NF-BOT-SNAPSHOT-PROOF
Depends on: BOT-CLONE-REHEARSAL (route + fingerprint). Blocks: BOT-DIFF-BLAST L3 path.
Routing: Worker: L3 · Tester + Reviewer separate sessions
Context: Route B reuses apps/api/app/database_backup.py, do not duplicate.
File allow-list (6):
- apps/api/app/bots/snapshot.py (new; Route B)
- apps/api/app/bots/before_image.py (new; Route A capture + undo plan)
- apps/api/app/database_backup.py (only if reuse needs a hook)
- apps/api/app/bots/risk/rules.py (wire RF undo/snapshot checks)
- apps/api/tests/test_nf_bot_snapshot.py (new)
- apps/api/tests/test_nf_bot_snapshot_live.py (new)
Goal: R2W/R3/R6/R8/R8C/R9 prod steps run only with a proven undo. Reversibility table (Route A, reverse writes): field values → restore old values; created records → unlink if no dependents, else archive; archive↔unarchive; settings/ir.config_parameter; metadata (views, fields, rules, actions, ir.access on 20) → restore/unlink. NOT reversible by RPC: posted moves, validated stock, sent mail/EDI/payments, delete/merge with dependents, company/tax/sequence change with transactions, module uninstall data, lockout (bot loses access). Those stay L3 (see BOT-RISK-CLASSIFIER).
Steps: 1. Tests first. 2. STOP-AND-ASK: a needed file is outside the allow-list; a non-`ingenium_` local DB; a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434, 54329); a git write; a new dependency.
Acceptance criteria:
- AC1 Route A before-image: RPC read of every record id + every field in the diff (+ write_date) stored in bot_audit, size-capped 50/batch, 500/run; payload hash. Evidence: test, row.
- AC2 Undo plan generated per row from the table above; a row with no reverse op → task reclassified irreversible → L3 path. Evidence: test.
- AC3 Proof on batch 1 (≤50): apply → read back == diff → undo → read back == before-image → re-apply → read back. Any mismatch → stop, auto-undo, kill switch trips, rest of run refused. Evidence: live 17/20 + injected mismatch test.
- AC4 Every later batch: readback vs diff; mismatch → stop + auto-undo of that batch + report done/undone counts. Evidence: chaos test.
- AC5 Concurrency: write_date changed since before-image → refuse undo of that record, flag for human. Evidence: test.
- AC6 Route B snapshot = pg_dump + filestore tar, sha256 each, fingerprint, taken_at; restore to ingenium_scratch_*, touched-table row counts + ir_attachment count match, drop scratch; corrupt/hash mismatch/stale/other fingerprint → refusal "snapshot-proof". Evidence: byte-flip test, live.
- AC7 Snapshot or before-image id written to bot_audit. Evidence: row.
Non-goals: automatic full-DB restore on prod (runbook only); retention policy.
Test plan: own tests x2; combined focused set both orders (fwd/rev) x2 each; test PG 54339. Live 17 + 20, Route A over RPC only. Chaos: dump killed → no id; disk full → refusal; scratch name collision → new name; RPC drop mid-undo → resume idempotent from audit.
What can still go wrong: computed/onchange side effects not captured by field diff (readback catches, undo may not restore — reclassify); undo on records edited by users meanwhile (AC5); mail.tracking/chatter noise from undo writes is permanent; huge DBs exceed time → refuse, never skip.
Evidence to log: PROGRESS line; live proof timings per route.
Rollback: revert files; delete snapshot files; before-images retained in audit.
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.

## Worker result (2026-10-26)
- Route A, `app/bots/before_image.py`, is a `RouteA` object that plugs into `WriteGate.run` through its before_image/readback/undo hooks. All calls are JSON-RPC; there is no XML-RPC import, and an AST test checks that.
  - Before-image: every id × every diff field + write_date, 1..50 ids per batch, only plan ids, no id twice. It is stored content-addressed as `bi:<sha256 split by ':'>`. The ref goes in the bot_audit intent row; values stay out of the audit table, because the audit refuses values and 40+ character blobs.
  - Batch 1 runs the proof: apply → read back == diff → undo → read back == before-image → re-apply → read back. On a mismatch, the gate trips the kill switch and auto-undoes.
  - Batches after the first are refused unless an HMAC proof bound to this plan hash exists.
  - Undo re-hashes the stored file. Tampered, missing, stale (>24h) or other-plan images are refused. Records already restored are skipped, so a resume is idempotent. A record whose write_date or values changed since our apply is flagged for a human and not overwritten.
  - Fields that cannot be restored make the plan `Irreversible` (L3 path): one2many, related, computed (depends), non-stored, readonly. m2m is restored with (6,0,ids); binary is read with bin_size=False.
  - `REVERSE_OPS` table: posted, stock, send, unlink, merge, uninstall, lockout and company-change-with-transactions have no reverse op.
- Route B, `app/bots/snapshot.py`: pg_dump -Fc (built by the new `database_backup.pg_dump_argv` hook) + filestore tar, each with sha256, plus fingerprint, taken_at and source counts of the touched tables and ir_attachment. The id is `snap:<manifest sha>`.
  - `verify` refuses with "snapshot-proof" on: a byte-flipped or missing file, an altered manifest, another fingerprint, a stale snapshot, a lossy or failed restore.
  - It restores into a fresh `ingenium_scratch_*` (a name collision gets a new name) and always drops it.
  - A killed dump or a full disk leaves no id and no files.
- `rules.py`: `gate_with_proofs` gives before-image, batch1-undo-proof and snapshot-proof credit only when a verifier bound to the plan confirms them. `gate()` is unchanged, so the legacy tests that pass these controls as plain names still pass.
- Live 17/20 (JSON-RPC, XML-RPC patched to raise):
  - Route A, 60 records, proof + 2 batches: 2.0s on 17, 2.1s on 20.
  - Injected mismatch + concurrent edit: trip, auto-undo, the edited record flagged, batch 2 never written.
  - Route B take + verify: 3.4s on each; the byte-flip was refused; 0 scratch DBs left.
- Round 2 (approved 08:14/08:22): kill-audit check is now AST-based (execute_kw, or write/create/unlink as the RPC method arg); Path.unlink not flagged; a regression probe proves a new raw RPC unlink is flagged. Exempt only guard.py, rpc_copy.py, before_image.py. before_image pin: the single write is in `_write_one`, which first checks `_halted` (kill switch: forward writes need it clear; reverse writes stop only if the state is unreadable). It is called per record only from `_prove`/`_undo_result`, which are reachable only via the readback/undo hooks.
- Clone writes (neutralize, fingerprint.set_param, rehearse) now go through `rpc_copy.rpc_write`, which runs JsonRpc's proof-checked wrapper. The single execute_kw pin is unchanged.
- Legacy `rules.gate` deleted (now private `_evaluate`); classifier and risk tests migrated to `gate_with_proofs`; test proves name-only proofs are refused.
- Full suites, both orders ×2: 3099 passed each time. Live 17+20 clone + snapshot: 4 passed (19 skipped, stack down); containers stopped. Ruff clean.
- Round 3 (review BLOCK 08:38): full-image before-image. `full_fields` (fields_get, all fields) captures every stored field: writable ones are restored; readonly/computed/related/one2many ones are compare-only. Excluded: magic fields and chatter log o2m (mail.*, rating). Binary is stored as `sha:` + a 0600 blob, capped at 25M chars. Readback and undo compare the full image (write_date/write_uid recorded only). Undo restores every changed writable field (2 passes). Anything left differing marks it unrestorable and fails closed. Outside-plan fields are counted in `side_effects`/`outside_plan`; batches after the proof trip on any new side effect. Rule OPR: `GateCtx.outside_plan_fields` needs L2+. The copy-rehearsal skip now also needs `full-image-proof` (no side effects, nothing unrestorable). `RouteA.check` returns False before a proof exists. Images are 0600 in a 0700 dir. The snapshot manifest is HMAC-signed with a process key and verified on restore.
- Live 17/20 side effects of a parent_id write: v17 street, city, commercial_*, complete_name; v20 commercial_*, complete_name, type. All restored. A name write's complete_name is restored. Full suites, both orders x2: 3106 passed. Live: 6 passed. Ruff clean.
- Reviewer probe s03 can't pass as written: its Fake `fields_get` only returns the fields asked for, so `street` can't be discovered. Real Odoo `fields_get([])` returns all fields. The same case is covered by `test_side_effect_parent_sync_captured_restored_and_flagged` and the live test.
- Round 4 (review MEDIUM): undo restores only plan fields plus side effects proven ours (re-applied on the same record by the batch-1 proof round-trip). A changed outside-plan field the re-apply does not reproduce is a person's edit: its value is put back, the record is flagged "not ours: human review", and the proof fails closed (no further batches). Later undos never restore unproven outside-plan fields; they flag them. LOWs: snapshot dump/filestore/manifest are 0600 in a 0700 dir; rule OPR is re-checked at runtime on every batch 2..N (`RouteA(approval=...)`, side effects need L2). Probes t16/t18/t20 pass.
- Known limits (follow-up, not built; must be shown to the user as limits): the before-image covers only the target model's records, so (1) changes our write causes on other models, (2) translated field values in languages other than the context language, and (3) company-dependent values for other companies are not captured or restored. Residual: during the proof, a person's edit is briefly overwritten before it is put back; an edit landing in that window could be lost.
- Wiring note: no app code constructs `RouteA` yet; the caller must pass the plan's approval tier, or OPR blocks every batch after the first that has outside-plan side effects (default 0, fail closed).

- Follow-up (probe t21): `proven_side` is tracked per field for the whole plan, not per record (before_image.py ~371, ~493). Within a batch, treat a proven side effect as ours only when the new value matches what the proof showed; otherwise flag it 'not ours'.
- Accepted LOW: the proof briefly overwrites a person's value before restoring it (millisecond-scale last-writer-wins risk). Odoo has no compare-and-set, and a clone cannot show production write overrides.
- Review round 3: APPROVED.
