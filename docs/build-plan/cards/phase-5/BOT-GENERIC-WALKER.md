# BOT-GENERIC-WALKER

Goal (Tope): Bots can handle record tasks (create, write, button calls) on any model the walker does not refuse, on Odoo 17–20, without a hand-written handler for each task. Module code (T3) and tasks the tiers check cannot grade are out of scope (see app/bots/tiers.py CLAIM).

## Scope
- `apps/api/app/bots/walker.py`: a generic plan of `create` / `write` / `unlink` / `call` steps on any model.
  - **Validation**: every field and value is checked against live `fields_get` + `ir.model` (17-20): type, selection,
    many2one/x2many existence, required (with `default_get`), readonly / computed / related,
    translate / company-dependent notes, binary size.
  - **Side effects** come from metadata: blast (ondelete cascade/restrict), diff recompute, a dry
    `onchange` call, DB constraints, automation/server actions (classifier + sinkhole scan).
  - **Risk**: catalogue class via `classifier.classify` (unknown model/button = refused) and named
    irrecoverable states (posted entries, validated stock, sent e-invoices, locked periods) = refused.
    Reviewed refused models carry reasons. Lockout runs where the risk layer says so.
  - **Writes only via WriteGate**: `WriteGate.run` + `before_image.RouteA` for writes, `WriteGate.call` for
    create/unlink/buttons, all over `Sinkhole.quiet`. No new write path, no exemption.
  - **Idempotency**: a per-step ledger plus the gate's audit claim, so a re-run after a crash does not apply a step twice.
  - **Undo** comes from the before-state: create -> unlink, write -> restore. Unlink and button steps have none, and the plan says so.

## Results (2026-10-26, UTC+1)
- `apps/api/app/bots/walker.py`: Step / plan / apply / undo_steps; Ledger; ruff clean.
- Unit `tests/test_nf_bot_walker.py`: 38 passed (fakes for 17/18/19/20 shapes). The table covers 15 cases over 12+ models. res.partner, sale.order with lines, account.move draft, stock.picking, hr.employee, crm.lead, project.task and reviewed x_probe are applied and undone back to the exact start. These are refused with named reasons: product.template create (R4 valuation, no counter-document), res.users, ir.config_parameter, mail.mail, unreviewed x_, project.task assignees and partner email (R8, lockout cannot simulate).
- Live `tests/test_nf_bot_walker_live.py`, on 17 (18117) and 20 (18120): one walk creates res.partner.category, writes res.partner (including m2m), and writes res.partner.industry. A re-run replays from the ledger, and undo restores the start state. Refusals: res.users, an unknown field, an unknown button. Evidence is in `~/.ingenium_nf/nfwt/BOT-GENERIC-WALKER_live.txt` (final runs 12:33 and 12:37 UTC+1).
- Full run, with walker + v20_access(+live) + kill_audit + role_privileges + approval_tiers + lockout_sim(+live) + risk + risk_adversarial + risk_escalation + sinkhole*: **2328 passed, 6 skipped** (pre-existing infra/catalogue skips), in both orders. No edits after. Sandboxes stopped.
- Fixes found by the tests:
  - Each step gets its own Approval copy, so one grant is never replayed onto another step's plan hash.
  - The sinkhole proof is composed through the hooks dict. The kill_audit pin forbids `.readback` in bots.
  - many2many accepts `(6,0,ids)` only, matching the diff.
  - A nested line may not name its own parent.

## Review round 2 (2026-10-26, UTC+1): BLOCK fixes
- Nested creates: every one2many line's model passes the same model-level refusal as a step (REFUSED_MODELS, unreviewed x_). Reference values check their model part. Fields linking res.groups, and ir.ui.menu groups_id/group_ids, are refused in the walker itself (defence in depth over lockout). Each nested line model gets lockout needs_simulation + simulate and an L3 floor. The review probe (res.partner user_ids create of res.users) is now a permanent test.
- Buttons: call steps are scanned as writes on their model, always run inside an open sinkhole, and must prove the hold after the call (after_batch); an unproven hold refuses the step. Call and unlink steps are forced to L3; unlink shows the blast preview (no snapshot restore, see gaps).
- Unit 43 passed; walker + kill_audit + role_privileges + approval_tiers + lockout_sim + risk* + sinkhole* + v20_access*: 2310 passed, 10 skipped (live) in both orders; ruff clean. Live walker test not rerun this round.
- For BOT-SPINE-WIRE: `reviewed` must come from the owner's store, never from the caller.

## Honest gaps
- Unlink/button steps are L3 with blast preview but no snapshot restore (not promised; a limit).
- Unlink and button steps have no undo; that needs a snapshot restore. The plan says so.
- Onchange is a dry preview only. Odoo runs no onchange over RPC writes, so the walker does not apply its result.
- Python constraints are opaque. Only the ir.model.constraint count is shown; a violation writes nothing.
- 18 is assumed to behave like 17, and 19 is unit-tested only (no sandbox).
- E-invoice detection is a field-name heuristic (edi/l10n state fields).
- Partner email, user assignment and other R8 fields are refused until lockout can simulate them.
- Metadata is read once per Walker instance.

Tracking: BOT-GENERIC-WALKER | done 2026-10-26 | round 2: unit 43, set 2310 passed both orders; live not rerun

## Merge list
- apps/api/app/bots/walker.py
- apps/api/tests/test_nf_bot_walker.py
- apps/api/tests/test_nf_bot_walker_live.py
- docs/build-plan/cards/phase-5/BOT-GENERIC-WALKER.md

Leave out: docs/vision-verify/trial-xray/, apps/web/.next-trial-*, apps/web/src/app/e2e/bv-ui-trial/, apps/web/src/app/e2e/trial-xray-grok/
