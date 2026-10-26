# BOT-OPERATOR-FLOW: guided, approval-gated execution of a designed plan

Status: built (uncommitted, awaiting independent review). Package `apps/api/app/bots/operator_flow/`.

## What it does
- Input: a process_design spec `{spec_version:1, status:"designed", odoo_major, items[...]}`.
- `OperatorFlow.cards()` (read-only): one plain-language card per item: title, what will change
  (the walker's preview lines), risk (design risk + walker class and approval tier), how it is
  undone, and version availability from `versioncaps.availability` (an uninstalled module reads
  "available in Odoo N via module M; needs install").
- `OperatorFlow.run()`: executes only steps approved in `Decisions` (store-owned; the caller never
  passes an approval level), only through `Walker.plan` / `Walker.apply` (WriteGate, before_image
  RouteA, audit, kill switch, sinkhole, lockout, ledger). The bot stays the actor; the approver is
  the human. Then `configverify.verify` re-checks; an executed step that does not verify as
  "matches" is flagged needs-review and the plan reads "attention".
- Every step ends executed / already-done (approved, live state already matched, nothing
  written) / skipped-by-operator / blocked (with reason); undecided = pending. State is on disk,
  keyed by step index + ref, written under an fcntl lock with a unique temp file; a re-run never
  repeats a final step whose design item is unchanged (plus the walker ledger).
- Approval binding: each decision stores a hash of the card (kind, model, key, expected,
  relations, module, verdict, risk, the walker step with record ids and values, tier). At run
  the hash is recomputed; any mismatch blocks "design changed since approval; re-approve" and
  marks the decision stale, so it never applies again even if the design is reverted.
- Duplicate refs block the whole spec.
- Dependencies: a step waits (blocked) unless every earlier step on the same model, or whose
  ref it links to in relations, ended executed or already-done.
- `undo_plan()` returns the walker's inverse steps for this session's executed steps; they run
  through plan + apply again.

## Fail closed (blocked with reason)
- Spec not version 1, not "designed", empty, or for another Odoo major than the database.
- Item verdict `needs-custom` -> "needs module build". AS-CRAFT-MODULE and AS-PROMOTE do not exist
  yet; when they land, this flow hands such steps to them instead of blocking.
- Verdict `needs review`, risk missing/unclassified, unknown kind, more than one record per key,
  any read fault, walker refusal, approval tier above the approved level, gate refusal.
- Module installs, settings apply and linked-record relations are not executed yet (blocked).
- Model or fields not available on this database now (versioncaps reason shown).

## Tests
- `tests/test_nf_bot_operator_flow.py` (Odoo 17-20 shapes): approval gate, idempotent resume,
  skip, low approval, blocked paths, version mismatch, module wording, verify failure flag, approval-to-card binding (model, key, values,
  verdict, module, tier), duplicate refs, dependency wait, L1-on-L2, concurrency, already-done,
  undo plan, Decisions store input checks, no raw RPC write in the package.
- `tests/test_nf_bot_operator_flow_live.py` (ODOO_LIVE=1, Odoo 17 and 20 disposable sandboxes;
  `OPFLOW_PORT_<v>` / `OPFLOW_DB_<v>`): pending until approved, execute, verify "matches",
  resume, undo restores start state, uninstalled module step blocked with install wording;
  teardown archives the bot user it creates (sandbox DBs are kept).

## Known limits
- Approval level and actor are SELF-ASSERTED until BOT-SPINE-WIRE: whoever calls
  `Decisions.approve` names the actor and level. L2/L3 get no second-approver check now.
- Dependencies are coarse (same model or explicit relation ref); hidden cross-model effects
  (e.g. computed fields, automated actions) are not modelled; the walker's blast preview and
  configverify are the backstop.
- Module install, settings apply, relations between designed records: blocked, not executed.
- Undo covers steps executed in the current session object (walker `Done` kept in memory).
- `Decisions` is a local JSON store; identity of the approver is not authenticated here.

## BOT-SPINE-WIRE must connect
- `Decisions.approve/skip` to the authenticated session (actor = signed-in human) and to
  `approval.ApprovalStore` records (L1/L2/L3 tiers, plan hash), so `approval_for` reads the store.
- The gate's grant source (owner-signed grants) in place of the test stand-in.
- Sinkhole and lockout simulate on the real session; route rehearsal ids into the base RunSpec.

## Review follow-ups
1. A skipped step blocks every later step on the same model (dependencies are assumed from a shared model). Build dependencies only from explicit relations/refs, or let a skip satisfy unrelated dependents.
2. The lock covers only the state write, not the whole step: hold the lock around check, apply and save. Today the walker ledger prevents double apply; 4 concurrent runs created exactly 1 record.
3. The duplicate-ref check is exact-match only: compare after strip/casefold.
4. No direct test for the hash check inside approval_for (redundant with the run-time check).
5. The 15 test bot users archived in the nf2 sandbox DBs (9 on 17, 6 on 20) were not re-verified as test-only. The live test uses the existing nf2 sandbox DBs ingenium_nf2_r6_17/_20.
6. Connect to AS-CRAFT-MODULE and AS-PROMOTE when they exist (neither exists today).
7. BOT-SPINE-WIRE must connect Decisions.approve/skip to the signed-in session and approval.ApprovalStore (tiers, plan hash), a real owner-signed grant source, sinkhole and lockout simulate on the real session, and rehearsal ids into the RunSpec. Undo covers same-session steps only.
