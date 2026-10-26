# BOT-R6-DELETE-MERGE: guarded archive, delete and record merge (R6)

No earlier card existed (DECISIONS.md: risk per button, start with delete buttons); written here.

## Scope
Irrecoverable removals through the gate only: archive-vs-delete, unlink with full cascade
preview, partner/contact dedupe merge via Odoo's stock wizard, undo where possible. L3 with the
exact count bound to the plan, verified snapshot, Sinkhole for outbound effects, Odoo 17-20,
fail closed, no raw RPC writes (kill_audit ban).

## Built (status: awaiting independent review, no git writes)
`apps/api/app/bots/removal.py` (`Removal` on top of `walker.Walker`),
`apps/api/tests/test_nf_bot_removal.py` (20 tests, real audit DB, walker fake Odoo extended).

- Archive first: a model with `active` gets an archive plan (walker write, before-image,
  proof, undo). Delete only with `allow_delete=True`; models without `active` are never
  silently deleted.
- Delete: `blast.preview` over live ir.model.fields (cascade walked, set-null counted,
  restrict refused, uncountable refused); every deleted and set-null row checked for final
  states (walker.IRRECOVERABLE: posted moves/payments, done stock, locked orders, paid POS, plus
  reconciled journal items, posted-entry lines, reconcile rows). Then a walker unlink step
  (its own irrecoverable check + Sinkhole hold).
- Merge: res.partner only through `base.partner.merge.automatic.wizard` (create, then
  `action_merge`, each a gate job). Products/other models refused (no stock wizard). 2-3
  partners, kept one included; partners with users refused; wizard missing refused. Before-image
  in the ImageStore: all stored fields of every partner, and every relinked row (all m2o/m2m to
  res.partner, and res_model/res_id pointers) with its old value. Final-state rows among
  relinked rows refuse. Readback: merged-away gone, kept exists, every imaged row now points
  to the kept partner; otherwise kill switch on.
- L3 for delete and merge: `blast.confirm` (typed exact count, `snapshot.Verified` of this
  DB) and `spec.snapshot_id` must equal the verified snapshot id. `blast.StaleGuard` wraps the
  gate's rehearsals for the run: the preview/image is recomputed when each job opens and any
  change refuses (count bound to the plan).
- Undo merge: recreate the merged-away partners from the image (restorable stored fields) and
  relink each imaged row group as its own walker plan; rows the walker refuses (e.g.
  mail.message history) are reported and stay on the kept partner (status `partial`).
- Version: walker version check (17-20, server shape) for all paths, incl. merge.

## Results
- removal 20 passed (archive x4 versions, delete x4, merge x4, refusals, stale, kill, mismatch,
  relink shape, AST raw-write pin). kill_audit raw-write ban passes with removal.py.
- Suites fitgap/kill_audit/lockout_sim/risk*/sinkhole/v20_access/walker/settings/removal:
  forward 2494 passed / 6 skipped / 1 failed; reverse file order identical; test-level reverse
  (removal+walker+kill_audit) 156 passed. diff_blast 2 skip + pass.
- The 1 failure is `test_nf_bot_risk.py::test_catalogue_rows_complete_and_traceable`: it
  hashes `~/.ingenium_nf/taxonomy/catalogue.csv`, which was modified outside nf2 at 13:28 (UTC+1)
  and no longer matches `catalogue_rows.json` (BOT-R4-POSTING added
  `b:stock.quant:action_apply_inventory`, 11930 rows; clears when that merges). Not touched by this card; fails without these
  files too (diff_blast+risk alone).
- Ruff clean.
- Live sandbox test: not run. The brief named ports 18117/18120 and ingenium_nf_bv_*, which are
  NF's and banned for nf2 (nf2 sandboxes are 18217-18220); left for a cheap follow-up.

## Gaps
- Undo merge gives new partner ids (Odoo cannot reuse an id over RPC); history (mail.message,
  followers) and anything the walker refuses stays on the kept partner; reported.
- Pointers other than res_model/res_id (reference fields, ir.property / company-dependent
  values, many2one_reference) are not imaged; the wizard may move them.
- Delete has no automatic undo: restore = snapshot.
- StaleGuard compares the full image incl. write_date; a concurrent harmless edit refuses (by
  design, noisy).
- Delete on a model with `active` needs explicit `allow_delete`; no policy yet for when delete
  is preferred (e.g. GDPR).
- Not live-verified on Odoo 17/20 (wizard field names, Python-level cascades).
- Catalogue rows suggested (not added; csv not edited): `b:base.partner.merge.automatic.wizard:action_merge`
  (R6 merge, 17|18|19|20). Today the merge tier comes from `rules.plan_tier("R6","merge")`
  directly, not a catalogue lookup.

## Review fixes (BLOCK 13:44, re-review pending)
- MEDIUM 1: merge refuses when a source partner is any company's `partner_id` (read with active_test off, no company restriction) or has an `ir.model.data` xmlid. Either read failing means refuse. Tested.
- LOW 2: the delete preview counts res_model/res_id rows (mail.message, mail.followers, ir.attachment and the like found through `ir.model.fields name=res_id`), lists them and adds them to the typed exact count. If they can't be read, it refuses. Tested.
- LOW 3: merging into an archived partner is refused. Tested.
- LOW 4: **undoing a merge is partial.** It recreates the removed partners with NEW ids and relinks what it can. Read-only/computed fields (e.g. commercial_partner_id) and rows Odoo deleted during the merge (e.g. duplicate followers) are not restored, and the result says `partial`. **Only restoring the snapshot gives a complete undo.**
- Live fixes: (a) transient models, including the merge wizard itself, are left out of the relink image, because the wizard row made the stale-approval guard trip live. (b) Odoo 20 commits the merge but then fails building the RPC reply ("Cursor already closed"). If no source partner is gone, the result is needs-human. Otherwise the full readback decides: done, or the kill switch on a mismatch.

## Recommended catalogue row (csv NOT edited; to add on merge)
`b:base.partner.merge.automatic.wizard:action_merge`: class R6, subkind merge, tier L3. Controls: audit, idempotency key, typed exact count, snapshot proof, readback, kill switch on mismatch. Allowed only through `app.bots.removal`. The generic button runner/walker refuses it (`test_generic_runner_refuses_merge_button`).

## Live check (2026-10-26, nf2 sandboxes 18217/18220, evidence `~/.ingenium_nf/nfwt/BOT-R6_live.txt`)
- v17: archive done. Delete done (count 2, includes 1 mail.followers pointer). Merge done (count 4, kid relinked, source gone). Undo partial, as expected. Kill switch off.
- v20: archive done. Delete done (count 1; ir.rule is unreadable for the bot, so the count is flagged "may be low"). Merge done after the post-commit RPC error, verified by readback. Undo partial. Kill switch off.
- `tests/test_nf_bot_removal_live.py` is skipped without ODOO_LIVE.
- Suites (removal, kill_audit, lockout_sim, risk*, sinkhole, v20_access, walker, fitgap, settings, live): 2497 passed, 8 skipped, 1 failed in both orders. The failure is the known catalogue row count from the BOT-R4-POSTING row. ruff is clean.
- Gap: no fake-level test yet for the "server commits then errors" path. It is proven live on 20 only.

## Round-2 fixes (BLOCK 14:03, re-review pending)
- MEDIUM 1, company contacts. RPC has no read that record rules can't hide, so the merge fails closed (`Removal._companies`):
  - It reads all visible companies and their contacts, the bot's `company_ids`, and whether anyone has `base.group_multi_company` (works for both the `groups_id` and `group_ids` field names).
  - It probes company ids 1..max+5 that it can't see. An AccessError or any error other than MissingError means a hidden company, so the merge is refused. A row that shows up only when read by id is also refused.
  - Multi-company (more than 1 visible company, or the group in use): the bot must belong to every visible company or the merge is refused.
  - Any read error means refused.
  - The post-merge readback now checks that every company contact still exists and that no company points at a merged-away partner.
  - Unit test: a fake hides a branch company whose contact is the merge source.
  - Live on 17 (second company, bot not in it): refused with "the bot must belong to every company". On 17 a plain internal user still sees every company, so the hidden-company case could only be tested with the fake.
  - Residual risk: a hidden company with id > max visible + 5 is not detected.
- LOW 2: if reads fail after a possible commit (the post-error check or the readback), the kill switch turns on and the result is `mismatch`. Tested.
- LOW 3: when the count may be low, the first plan line now starts with "COUNT MAY BE LOW (n reasons below)" next to the number to type. After the delete, a readback re-counts surviving target, cascade and res_model/res_id rows. If gone ≠ typed, the kill switch turns on. Tested.
- LOW 4: mail.tracking.value and mail.notification rows are not counted separately; they go with their mail.message rows.
- Live re-run (17 and 20): archive, delete with the readback, merge and partial undo all passed. The kill switch stayed off. Evidence is in `~/.ingenium_nf/nfwt/BOT-R6_live.txt`.
- Suites, both orders: 2501 passed, 8 skipped, 1 failed. The failure is the known catalogue row count. ruff is clean.

## Review follow-ups

- Recommended catalogue row `b:base.partner.merge.automatic.wizard:action_merge` (R6, merge, L3, allowed only via `app.bots.removal`). Not added yet: the generator needs a per-row tier override first.
- Optional: an extra company probe up to the `res_company_id_seq` max.
- Accepted low: a hidden company whose id is more than 5 above the highest visible id is not detected.
- The multi-company live refusal is tested on Odoo 17 only.
