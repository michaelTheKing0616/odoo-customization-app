# BOT-SINKHOLE: outbound side effects of a bot write are held, proved or refused

Phase 5 (Bots), NF stream. Sources: DECISIONS.md (risk per button, L1/L2/L3, N is the only ceiling), RESOLUTION.md, risk rules (IRRECOVERABLE, MAIL_THREAD, STATE_POSTING_ALL), clone/neutralize.py (outbound provider rules), guard.py WriteGate.

## Goal
A bot write on a production database must never send an email, SMS, webhook, payment / e-invoice / carrier call, portal invite or reset mail as an unintended consequence. Anything that can be held is held until a person decides. Anything that can't be held with proof needs an L3 approval. Anything that can't be read is refused.

## Design (app/bots/sinkhole.py, public ORM over JSON-RPC only)
1. **Scan (reads only):** active `base.automation` rules on the plan model whose trigger fires for the op (`TRIGGERS`, each with a reason), plus the `ir.actions.server` they run (`ACTION_KINDS`). Each action is one of:
   - `hold`: mail_post, followers, next_activity. Output is queued `mail.mail`.
   - `quiet`: remove_followers, log_note.
   - `recurse`: object_write, object_create, object_copy, multi. The target model's rules are scanned, depth ≤ 3. Deeper is L3.
   - `l3`: webhook, code, sms. An unknown kind or trigger is also L3.

   The scan also reports templates (flagged "with attachments"), follower counts, and `BUSINESS_OUTBOUND`: a posting or state write on account.move, account.payment, payment.transaction, stock.picking or pos.order goes to L3 when a live EDI proxy, payment provider, prod carrier or card terminal exists. Those provider models must stay in `neutralize.RULES` (tested). Any read error makes the verdict `refuse` (fail closed).
2. **open(scan, level):**
   - A refused scan is refused.
   - An L3 verdict below level 3 is refused (`RF-SINK [outbound-l3]`).
   - If the kill switch is on, open refuses.
   - Otherwise it records id baselines (mail.mail, sms.sms, mail.notification) and pauses the active `QUEUE_CRONS`: mail queue, SMS queue, time-based automation check, scheduled messages. It reads the pause back. If the pause fails, it restores the crons and refuses before any write.
3. **quiet(rpc):** wraps the rpc passed to `WriteGate`. Every write, create or unlink carries `QUIET_CTX` (each key has a reason): tracking_disable, mail_notrack, mail_create_nolog, mail_create_nosubscribe, mail_auto_subscribe_no_notify, mail_notify_force_send=False, no_reset_password. The plan's own context is kept, and reads are untouched.
4. **after_batch / readback(inner):** composed into the `WriteGate.run` readback, so a failure trips the switch and undoes the batch.
   - Every new `mail.mail` with `create_uid` = the bot user and state `outgoing` is held: state `cancel`, and `failure_reason` = `ingenium-hold:<hold_id>`. New `sms.sms` is held as `canceled`. Each hold is read back.
   - **Escaped** means a bot mail in any other state, a bot SMS that is not outgoing or canceled, or a bot `mail.notification` that is sent, bounced or in exception. It turns the switch on and returns False.
   - **Unheld** means the hold write failed, for example because the bot was demoted. It also turns the switch on and returns False.
5. **close():** runs a final proof and counts other users' queued mail. It restores the crons only if nothing is unheld. Otherwise the queue stays paused and a person must act. It returns a `Report` whose `text()` is the plain-language approval card line.
6. **decide(ledger, actor, release):** only the DB owner (`switch.owner_of`) can release or discard. Release is also refused while the kill switch is on.
   - Release sets mail back to `outgoing` and clears the marker.
   - Discard keeps the record `cancel` with `ingenium-discarded:<id> by <actor>`. Nothing is ever deleted.
   - Each message can be decided once: the ledger marks it done, and the Odoo marker check refuses a stale ledger copy.
7. **Write path:** `_qwrite` holds the file's only RPC write (AST-pinned). Its callers are exactly open, _hold, _restore and decide, and no other file references `_qwrite`. Pause, restore, hold and discard run even with the switch on, because they reduce risk. Release does not.

`Scan.facts()` gives `{sinkhole, outbound}` for the approval facts hash, and `Scan.need_tier` gives the tier floor (3 or 0).

## Exemption (said explicitly)
`test_no_raw_rpc_writes_in_bots` exemption extended by exactly one file pin: `bots / "sinkhole.py"` (tests/test_nf_bot_kill_audit.py, 2-line change). The AST pin lives in `test_single_pinned_write_path`. guard.py was not edited.

## Files
- NEW app/bots/sinkhole.py
- NEW tests/test_nf_bot_sinkhole.py (25 tests: unit suite, real WriteGate integration, AST pin, drift tests)
- NEW tests/test_nf_bot_sinkhole_live.py (Odoo 17 + 20, JSON-RPC)
- EDIT tests/test_nf_bot_kill_audit.py (exemption pin only)
- NEW docs/build-plan/cards/phase-5/BOT-SINKHOLE.md

## Permanent adversarial tests
These cases are covered:
- A hidden automation rule sends mail on write. The mail is held, including through the real WriteGate.
- A template with attachments is reported, and the held mail keeps its attachments.
- Follower auto-subscribe sends no notice under the quiet context. A raw write's mail is held.
- A scheduled action fires mid-run. The queue is paused, so nothing is sent.
- Mail queued before the run is neither held nor counted, and it sends after close.
- A portal invite on user create sends nothing under `no_reset_password`. An unflagged create is detected as escaped and trips the switch.
- A live payment provider makes the plan L3. A disabled provider is OK.
- Held mail released twice: the same ledger and a stale copy are both refused.
- Non-owner release is refused, and release with the kill switch on is refused.
- The bot is demoted mid-run. The mail is unheld, the switch turns on and the queue stays paused.
- A queue pause that fails refuses the run before any write.
- Force-send escape and sent-notification escape are both detected.
- webhook, code, sms and unknown action kinds are L3. An unknown trigger is L3.
- A recursive object_write reaching a webhook is L3.
- An unreadable scan is refused.
- `after_batch` before `open` fails closed.

Drift checks:
- Every `fields_inventory.csv` model with a stored field relating to mail.template, sms.template, mail.mail or sms.sms, or a webhook field, is in `REVIEWED_OUTBOUND_MODELS` with a reason.
- mail.mail `state` and `failure_reason` exist on 17-20.
- Every list entry has a reason.

## Round 3 (review BLOCK: recover during a live window)
- Heartbeat: the lease JSON carries `beat`. The live run refreshes it before EVERY guarded write (inside `quiet`) and after every batch (`after_batch`), using the pinned `lease_beat` purpose, which writes `value` only on the window's own lease id.
- `recover()` refuses (returns `refused: the run holding the lease is alive`, logged) unless the beat is older than `LEASE_STALE_S = 900` s. Why 900 s:
  - A batch is at most `BATCH_CAP=50` records in one write.
  - The longest silent gap is one Odoo call plus its readback.
  - Odoo's default `limit_time_real` kills a request at 120 s, and 900 s is 7 times that.
  - There is NO owner force, because forcing over a live run is the bug itself. To stop a run, the owner turns the kill switch on (the run stops at its next write and the heartbeat stops), then recovers after 15 min.
- Ownership checks: before each guarded write, at each batch, and before `close` restores anything, the run checks that the lease is still its own (same row id and hold_id). If it isn't, the run stops: the guarded write raises `SinkholeError`, the kill switch trips, and the report gets `unheld: sinkhole lease lost`. `close` then never unpauses crons or drops a lease it doesn't own.
- Stale-lease behaviour:
  - A lease whose beat is older than 900 s is treated as a crashed run.
  - The owner's `recover` holds leftover bot mail, restores the recorded crons, and drops the lease.
  - If a run is in fact still alive past the limit (a request over 15 min, e.g. `limit_time_real` raised), its next write or batch finds the lease gone and stops and trips. Mail that run created between the recovery and that check could be sent by the restored queue. This is a stated residual risk, bounded by the limit.
  - The heartbeat uses the API host's clock. Clock skew between API hosts that is larger than the limit would defeat it.
- Own keys:
  - The sinkhole refuses any plan that creates, writes or deletes an `ir.config_parameter` whose key starts with `ingenium.` (`outbound-own-key`), including the lease key.
  - Risk rules: every `param:` key, `ingenium.*`, and model writes and deletes on `ir.config_parameter` are already floored at R8 security, which means hard-floor tier 3 that a policy cannot lower. I added a test that pins this and added no new rule.
- BOT-SPINE-WIRE: `SessionActor` MUST be built only from the authenticated server session (login plus server session id), never from request bodies, plan data or chat text.

## Results round 3 (2026-10-26)
- Unit: 42 sinkhole tests pass, including the permanent probe test (`test_recover_during_live_window_refused_and_queue_stays_paused`): refused during a live window; recover works after expiry; a taken lease stops and trips the run; a lease dropped mid-run means close unpauses nothing; the heartbeat refreshes on each write and batch; own keys are refused; config_parameter is pinned at L3. Probe `test_probe_sink_lease` passes. The two round-1 probes in `test_probe_sink_race` still fail by design: the second window is refused, and `Ledger.paused` exists.
- Live Odoo 17 and 20 (18117/18120), run AFTER the final edits and ruff, with no changes since: 2 passed, `unflagged=held` on both.
- Sinkhole + live + kill_audit/approval_tiers/risk/risk_adversarial: 2183 passed, 6 skipped in BOTH orders.
- ruff format and check are clean.
- The sandboxes are stopped.

## Round 2 (review BLOCK fixes)
- Overlap (F1): a per-database lease. This is the unique `ir.config_parameter` key `ingenium.sinkhole.lease`, with JSON {hold_id, uid, paused, base}. It is created and read back BEFORE any cron is paused. A second window is refused (`outbound-lease`) and has no override. If the bot has no rights to write the lease or the crons, opening is refused (fails closed). Probe `review/test_probe_sink_race.py` now fails as intended: the 2nd open is refused, and `Ledger.paused` exists.
- Crash (F2): the paused cron ids and the hold id are stored in the lease before the pause write. `recover(SessionActor)` is owner-only and refused while the kill switch is on. It is idempotent: it holds leftover bot mail first, then restores the crons, then drops the lease. It is logged via `logging`. If messages are still unheld, the lease is kept, which blocks new runs.
- Deferred (F3): `on_time*` rules and recurse actions on them become L3, "sends later from Odoo's scheduler; never held". `DEFERRED_MODELS` (calendar.event/alarm, gamification.challenge/goal) are always L3. REVIEWED reasons are corrected, and Scan.text never promises holding for these.
- LOWs:
  - `PURPOSES` pins each `_qwrite` purpose to its model, fields, method and values, and the AST pin covers 3 literals and the callers.
  - Release and discard are both refused while the kill switch is on.
  - An SMS discard writes state `error`.
  - Business lines use provider labels, not model names.
  - `decide`/`recover` take a validated `SessionActor`; a plain string raises TypeError.
- BOT-SPINE-WIRE MUST pass the authenticated session identity and verify that `bot_uid` is the session's own Odoo user. If `bot_uid` is wrong, NOTHING is held, because the hold filters on create_uid.

## Results round 2 (2026-10-26)
- Unit: `test_nf_bot_sinkhole.py` 36 passed, plus kill_audit 129 combined.
- Live Odoo 17 + 20 (18117/18120): 2 passed. A held automation mail stays held, the queue crons restart, the lease is dropped, and a single discard works.
- Gap 7 negative, a raw write WITHOUT quiet flags: the result is `unflagged=held` on both 17 and 20. Mail created in the bot's call is caught by the create_uid/hold sweep, regardless of the context flags. Evidence: `~/.ingenium_nf/nfwt/BOT-SINKHOLE_live.txt`.
- Suites (sinkhole + kill_audit/role_privileges/approval_tiers/diff_blast/risk/risk_adversarial/clone(+live)/snapshot(+live)): 2348 passed, 13 skipped in BOTH orders.
- ruff format and check are clean.
- After the run I fixed only the order of the live test imports (ruff), and the sandboxes were stopped. That edit is cosmetic, so the live test was not run again.

## Results round 1 (2026-10-26)
- New file: 25/25 pass.
- Live: 2/2 pass on Odoo 17 (18117) and 20 (18120). Each held 1 email, restored the crons and discarded it once. The second decision was refused. Evidence is in ~/.ingenium_nf/nfwt/BOT-SINKHOLE_live.txt.
- Combined run of sinkhole, sinkhole_live, kill_audit, role_privileges, risk, risk_adversarial, clone, snapshot, diff_blast and approval_tiers: 2335 passed, 8 skipped in both orders (sinkhole first, then sinkhole last).
- ruff check and format are clean. Sandboxes 17 and 20 were stopped.
- The live probe found that Odoo 20 adds `log_note` and that mail_post there notifies followers only. Both are handled.

## Known gaps / follow-ups
1. **Not wired yet.** BOT-SPINE-WIRE must:
   - build `Sinkhole(rpc, switch, db, bot_uid)`;
   - `scan` before approval and feed `facts()` and `need_tier` into approval `Plan`/`facts_hash`;
   - `open` before `WriteGate.run`;
   - pass `quiet(rpc)` as the gate rpc and `readback(plan_readback)`;
   - `close()` in a finally block;
   - persist the `Ledger` and show `Report.text()` on the card.

   RouteA undo must also use `quiet(rpc)`, so that undo writes don't send.
2. **Silent sends are not proven.** Sends that leave no mail.mail row and no mail.notification row cannot be proven: `template.send_mail(force_send=True, auto_delete)` inside custom code. The only route to those is `code` actions, which are L3, so this is accepted. Proposed follow-up: a mail.mail id-gap heuristic.
3. **Bot attribution.** Attribution uses `create_uid` = bot uid. It needs the bots' own Odoo user (the same dependency as the DB-role lockdown).
4. **SMS holds.** SMS holds have no Odoo-side marker. A stale ledger copy could release a discarded SMS. SMS actions are L3 anyway. Proposed follow-up: mark via a `failure_type` value if one fits on 17-20.
5. **Paused queue delays everyone.** Pausing the queue delays all users' mail during the window. The report counts it, and nothing is lost.
6. **No button-path scan.** Button and method plans (`gate.call`) get the quiet context and proof, but the scan only knows CRUD triggers. Business-method outbound calls stay with the per-button risk classifier.
7. **No live negative test.** A raw write without flags on live 20 was not exercised. It is covered by unit tests only.

- R2 gaps:
  - The lease requires system rights on ir.config_parameter and ir.cron. Without them the window is refused, which fails closed.
  - While a window is open, the mail queue is paused for EVERY user of that database, so other people's mail is delayed (not lost) until close/recover.
  - Deferred/time-based sends are L3 and are never held.
  - Gap 7 was proven only for mail created inside the bot's own call. Mail that a third-party module sends synchronously, bypassing mail.mail and sms.sms, is still not held. Such a send is detected as escaped only if it leaves a record.

## Proposed tracking lines (not written to the mixed files)
- STATE_NF: BOT-SINKHOLE r3: lease heartbeat (LEASE_STALE_S=900, no force) + ownership check before writes/batches/close + own-key refusal; live 17/20 pass; 2183 passed both orders; awaiting re-review.
- STATE_NF: BOT-SINKHOLE r2 — lease + recover + deferred L3 + PURPOSES pins; live 17/20 negative held; 2348 passed both orders; awaiting re-review.
- PROGRESS.md: `2026-10-26 BOT-SINKHOLE built (NF): outbound sinkhole (scan/hold/prove/release-once, L3 for unholdable); 25 unit + live 17/20 green; 2335 combined both orders; awaiting review.`
- STATE_NF.md: `| BOT-SINKHOLE | built, in review | app/bots/sinkhole.py + tests; kill_audit exemption pin | wire in BOT-SPINE-WIRE |`
