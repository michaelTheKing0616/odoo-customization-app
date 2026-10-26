# BOT-R4-POSTING

Goal (Tope, t431u): Bots can post and validate accounting and stock documents with guardrails against mistakes that cannot be undone in production. The card was written from DECISIONS.md (risk per button; L1/L2/L3 tiers; the approved plan's exact count is the ceiling) and the R4 controls in the catalogue (period-lock check, walkthrough, no auto-rollback, a counter-document).

## Scope
- `apps/api/app/bots/posting.py`: `Poster` over `Walker`. It covers four ops: `move_post` (account.move action_post), `payment_post` (account.payment action_post), `picking_validate` (stock.picking button_validate) and `inventory_apply` (stock.quant action_apply_inventory).
  - **Always L3.** The ids must be distinct, and their count must equal the approved plan's count, both at plan and at apply.
  - **Preview:** journal lines with a balance check, payment amount/journal/partner, stock moves (product, qty, from -> to), and quant deltas. The pre-post facts, including ledger lines and moves, are bound. Any change before apply refuses ("plan again").
  - **Refused:** wrong state, sent (is_move_sent / is_sent), e-invoice state not open, matched/reconciled, inalterability hash, unbalanced entry, lot/serial tracking, partial quantity (backorder wizard), and unknown op. A lock date on or after the document date refuses, and so does one on or after today, because the counter-document could not be dated. Unreadable data refuses too.
  - **Runs as a Walker call step:** catalogue classify (the v20 stock return route is checked live), `WriteGate`, and a proven `Sinkhole` hold. Then the post-state is read back per version: payment `posted` on 17, `in_process`/`paid` on 18+. A wizard reply leaves the state unchanged and reports "mismatch".
  - **Undo uses counter-documents only, never unlink.**
    - Entry: a reversal via account.move.reversal refund_moves, then the draft reversal is posted.
    - Payment: action_draft + action_cancel.
    - Receipt: a return via stock.return.picking (create_returns on 17, action_create_returns on 18+), then validated.
    - Quant: a counter count, then apply.
    - Undo is refused if the documents changed after posting, if they are reconciled/paid, if the stock has already left, or if today is locked. Every undo write goes through `WriteGate.call` inside a proven hold.

## Results (2026-10-26, UTC+1)
- Unit `tests/test_nf_bot_posting.py`: 34 passed, 3 skipped. The skips are 20's picking validate, refused fail-closed because the return route is not on the fake target. The tests use fakes for the 17/18/19/20 shapes and cover post + undo for each op and these probes: count != plan, lock date (doc and undo date), posted / sent / e-invoice / unbalanced, tracked / partial / wizard reply, changed since preview, reconciled undo, stock already gone, and the AST check that writes go only through the gate.
- Live `tests/test_nf_bot_posting_live.py` (account + stock installed on the bv_17/_20 sandboxes):
  - 17: entry posted then reversed (reversal posted), payment posted then cancelled, receipt validated then returned (return done).
  - 20: entry and payment the same. Picking validate is refused fail-closed (return route not verified).
  - Evidence: `~/.ingenium_nf/nfwt/BOT-R4-POSTING_live.txt` (13:18 and 13:19 UTC+1).
- Set: posting(+live) + kill_audit + lockout_sim* + risk* + sinkhole* + v20_access* + walker* + fitgap*: **2492 passed, 29 skipped**, in both orders. ruff is clean, and the sandboxes were stopped.

## Honest gaps
- `inventory_apply`: the catalogue has no `b:stock.quant:action_apply_inventory` row, so the classifier refuses it ("unknown task", confirmed live on 17). It needs a catalogue.csv row and a regen, which belongs to the owner. The code and unit tests are ready (in the unit tests, every version with no row asserts the refusal).
- On 20, picking validation stays refused until `stock.picking.action_return` is seen live (classifier mitigation). The return path on 18-20 is unit-only.
- Undo writes (stock.move quantity, quant count) use `WriteGate.call`, not RouteA before-images. They are audited, idempotent and held, but the before-image is the plan's bound facts.
- Reconciliation after a reversal is left for a person. The undo of a paid or partially paid invoice is refused rather than unreconciled.
- Lock dates: company fields only. The 18+ per-user `user_*_lock_date` and lock exceptions are not read, which errs safe only when the company date is the stricter one. The lock probes are unit-only, because Odoo will not lock a period that holds drafts on the shared sandbox.
- E-invoice detection is the walker's field-name heuristic. Postings that queue EDI through crons rely on the sinkhole cron lease.
- Live on 17 and 20 only (18 and 19 are unit-only). The sandboxes bv_17/_20 now have account + stock installed.

Tracking: BOT-R4-POSTING | built 2026-10-26 | unit 34 (+3 skip), live 17/20 pass, set 2492 passed both orders | awaiting independent review

## Merge list
- apps/api/app/bots/posting.py
- apps/api/tests/test_nf_bot_posting.py
- apps/api/tests/test_nf_bot_posting_live.py
- docs/build-plan/cards/phase-5/BOT-R4-POSTING.md

Leave out: docs/vision-verify/trial-xray/, apps/web/.next-trial-*, apps/web/src/app/e2e/bv-ui-trial/, apps/web/src/app/e2e/trial-xray-grok/

## Round 2 (review BLOCK fixes)

- HIGH 1: `Poster._outbound` runs in plan and apply, with or without values. It refuses when any live provider exists (EDI proxy in prod, enabled payment provider, carrier in production mode). If the live-flag field is missing (Odoo 20 has no `payment.provider.state`), it counts all providers instead and still fails closed. It also refuses a payment that carries a token or transaction, a picking with a production carrier, and a carrier it cannot read. The reviewer's probe scenario is now a permanent test at Poster level (`test_live_provider_refuses_button_with_no_values`). sinkhole.py is unchanged.
- MEDIUM 2: lines with deferred dates and chained stock moves are refused. Apply also compares bot-created account.move/stock.picking ids before and after. Expected side records (the payment's own move, valuation moves) are listed in `PostDone.extra`. Any other new record turns the kill switch on and returns needs-human.
- Catalogue: added `b:stock.quant:action_apply_inventory` (R4, L3, reversible by counter-count, snapshot, refuse if stock moved) and regenerated catalogue_rows.json (11930 rows).
- Live: on 17, move, payment, picking and return all pass, and the inventory count is applied and counter-counted 0→4→0. On 20, move, payment and inventory count pass. The picking is refused fail-closed because the return route is not verified.
- Tests: the full set passes in both orders (2537 passed, 29 skipped). ruff is clean.
- Gaps: undo has no side-record diff. Undo writes go through gate.call, not RouteA. Validating an Odoo 20 picking is still refused.

## Round 3 (narrow BLOCK)

- E-invoicing (`Poster._einvoice`, move_post only, runs in plan and apply). Any of these refuses posting:
  - Older account_edi framework (17, and 18-20 where a localisation still ships it): `account.edi.format` exists or the journal has `edi_format_ids`, and the move's journal has any format. Also refused if the journal formats can't be read.
  - Proxy route: an `account_edi_proxy_client.user` in prod mode (round 2), on 17-20.
  - Peppol (account_peppol, 17-20): the company's `account_peppol_proxy_state` (or any `peppol_*state`) is anything other than empty, not_registered, rejected or canceled.
  - Localisation e-invoice data: any move field matching `l10n_xx*_(edi|einvoice|cfdi|sdi|sii|tbai|zatca)*` that holds a value. This covers MX CFDI, IT SDI, ES SII/TBAI, SA ZATCA, IN and similar, on 17-20.
  - Unchanged from round 1: an edi_state, `is_move_sent` or a peppol_move_state that is no longer open still refuses.
- Live quick rerun: 17 and 20 pass. None of these routes are installed on the sandboxes, so live only shows there are no false refusals.
- Catalogue L3: not done in the CSV. gen_risk_rows.py asserts that controls are identical across a risk class, and all R4 rows carry human-approve-L2. A single L3 row fails with `AssertionError: R4`. Inventory apply is still held at L3 in practice, because Poster refuses every posting and every undo below approval level 3. The CSV and json are unchanged from round 2 (backup at /tmp/r4/catalogue.csv.bak2).
- Tests: the full set passes in both orders (2541 passed, 29 skipped). ruff is clean.

## Round 4

- Module check (fail-closed, move_post only). `_einvoice` refuses posting when any installed module matches one of:
  - `l10n_<cc>_(edi|einvoice|e_invoice|cfdi|sdi|sii|tbai|zatca|nilvera|eta|dte|fe|ubl)*`
  - `l10n_tr_nilvera*`
  - `l10n_eg_edi_eta`
  - `l10n_*_edi_*`

  This covers, for example, l10n_ar_edi (AFIP CAE requested inside action_post), l10n_cl_edi DTE and l10n_in_edi. The message names the module and says a human posts it. An unreadable or empty module list also refuses. The proxy and Peppol checks are unchanged.
- Idle values: `to_send`, empty and False count as idle on l10n fields. That is safe only because the module and journal-format checks run first. `not_applicable` and `none` still refuse, because the shared walker treats them as not-open. Relaxing that needs a walker change, which is outside this card.
- Undo: `_undo_move_post` runs `_einvoice` on the draft reversal before posting it. If an e-invoice module appeared after apply, the credit note stays in draft.
- L3 floor test: move_post and inventory_apply plan at tier 3 and refuse L2 approval, even though the catalogue's R4 controls say human-approve-L2.
- Follow-up: per-row tier override in gen_risk_rows.py, so a single catalogue row can say L3 without moving the whole R4 class.
- Live: 17 and 20 pass with the module query. Neither sandbox has an l10n e-invoice module installed.
- Tests: the full set passes in both orders (2561 passed, 29 skipped). ruff is clean.

## Round 5

- Payments: payment_post and its undo now run `_einvoice` too. The undo check happens before reset-to-draft and cancel. Payments get the module check and the journal edi_format_ids check. These cover both the payment's own journal and the journals of its reconciled invoices and bills, which are read if the fields exist. Peppol and proxy-state are checked as well. Anything unreadable refuses. This catches the l10n_mx_edi CFDI payment complement and similar Colombia/Peru payment receipts. Picking and inventory ops have no e-invoice check.
- Denmark: `l10n_dk_nemhandel*` is on the module list, and the company-field pattern is widened to `\w*proxy_state$`.
- Refused fail-closed even though they are export-only: l10n_be_edi and l10n_nl_edi, which match `l10n_*_edi*`.
- Judged to need a separate send step (Send & Print, which the bot never calls): l10n_co_dian, l10n_ro_efactura, l10n_fr_pdp, l10n_de_xrechnung. They are not on the module list. The journal-format and Peppol checks still apply to them.
- Live: the 17 and 20 payment paths pass.
- Tests: the full set passes in both orders (2569 passed, 29 skipped; +8 from 2 new tests across 4 versions). ruff is clean.

## Follow-ups

- Per-row tier override in the catalogue generator (gen_risk_rows.py); the code currently forces L3 for move_post and inventory_apply.
- Tighten 3 low test assertions: picking checks should assert `isinstance(r, po.PostPlan)`; plan inventory_apply with an e-invoice module installed; replace the either-or assertion near line 532.
