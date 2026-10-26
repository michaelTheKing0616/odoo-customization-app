# BOT-DIFF-BLAST: Diff preview and cascade-aware blast count

ID: BOT-DIFF-BLAST
Title: Exact diff preview and blast count from relations/ondelete; caps and tier selection
Status: todo
Phase: 5
Priority: P1
Type: build
Owner: NF (backend)
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: NF-EPIC-BOT;NF-BOT-DIFF-BLAST
Depends on: BOT-SNAPSHOT-PROOF (L3 path needs snapshot id) and BOT-RISK-CLASSIFIER (caps/tiers). Blocks: BOT-APPROVAL-TIERS (UI shows this payload).
Routing: Worker: L3 · Tester + Reviewer separate sessions
File allow-list (5):
- apps/api/app/bots/diff.py (new)
- apps/api/app/bots/blast.py (new)
- apps/api/app/bots/risk/rules.py (cap/tier hook)
- apps/api/tests/test_nf_bot_diff_blast.py (new)
- apps/api/tests/test_nf_bot_diff_blast_live.py (new)
Goal: Before approval, the owner sees exactly which fields/records change and how many records, companies and users are touched including cascades.
Steps: 1. Tests first. 2. STOP-AND-ASK: a needed file is outside the allow-list; a non-`ingenium_` DB; a forbidden port (3002, 8001, 8002, 8012, 5433, 5436, 8069–8073, 11434, 54329); a git write; a new dependency.
Acceptance criteria:
- AC1 Diff: per record {model, id, field, old, new}; read from live; secrets masked. Evidence: test.
- AC2 Blast: walk one2many/many2one ondelete=cascade/set null/restrict from live ir.model.fields; count per model, companies, users; restrict → refusal preview. Evidence: unit graph + live partner/move fixtures.
- AC3 Uncountable graph (cycle cap hit, access error) → RF-R6 refusal. Evidence: test.
- AC4 Caps: >50 → split into batches; >500 per run → L3 required; tier chosen per class: L1 quick tap, L2 preview + count, L3 clone rehearsal + snapshot + typed blast count. Evidence: tests.
- AC5 Payload hash stored; executing with a different diff/blast than approved → refusal (stale approval). Evidence: test.
- AC6 Readback after execution compares to diff; mismatch trips kill switch. Evidence: test.
Non-goals: approval UI; executing tasks; R5 recipient preview (BOT-SINKHOLE).
Test plan: own tests x2; combined focused set both orders (fwd/rev) x2 each; test PG 54339. Live 17 + 20 (19: ir.model.fields ondelete delta if any). Chaos: records change between preview and execute → stale refusal; batch 3 of 10 fails → stop, report done/undone counts, resume idempotent.
What can still go wrong: Python-level cascades (overridden unlink) are invisible to metadata — flag models with custom unlink as "count may be low" and require L3; computed stored fields recompute beyond the diff.
Evidence to log: PROGRESS line; live blast table.
Rollback: revert files.
Definition of Done: ACs pass; independent Reviewer APPROVE; merged; lock released.

## Results (2026-10-26, second builder, nf2-backend @ 4817d74c, uncommitted)
Files: app/bots/diff.py (new), app/bots/blast.py (new), app/bots/risk/rules.py (+TIER_CONTROLS, TierPlan, plan_tier, appended only), tests/test_nf_bot_diff_blast.py (50), tests/test_nf_bot_diff_blast_live.py (3 x Odoo 17/20).
- AC1 `diff.build_diff`: {model,id,field,old,new} from live read (active_test off); credential fields/values masked both sides; scalars, m2o id/False, x2many only `[(6,0,ids)]` (other commands, magic fields, non-stored computed, missing ids, access errors refuse). Read-only wrapper allow-lists read/search/search_read/search_count/fields_get. Also lists unchanged ids, stored computed fields whose `depends` mention a changed field, and per-record write_date (any concurrent edit = stale).
- AC2 `blast.build_blast`: graph from live ir.model.fields (stored m2o/m2m with relation = touched model); cascade walked, set null counted, restrict -> RF-R6 refusal preview naming blockers; m2m links (incoming + own) counted; companies (company_id/company_ids) and users (res.users rows + users of touched partners).
- AC3 access error, unknown on_delete on a referenced field, >20000 nodes or depth 12 -> RF-R6 cascade-graph-count.
- AC4 `rules.plan_tier`: batches = ceil(n/batch_cap); n > run_cap -> L3; "count may be low" (mail.thread or not reviewed-low-risk, from catalogue; unlink with dependents) -> L3; tier never below gate `required_tier` (drift test over all classes); every tier carries reasons. `blast.confirm` enforces L3 typed blast count + snapshot id.
- AC5 `Preview.payload_hash` over values+diff+blast+tier; `blast.StaleGuard` wraps the gate's Rehearsals and refuses `stale-approval` before the job opens (tested through WriteGate: zero writes).
- AC6 `diff.readback` is the WriteGate readback; chaos: batch 3 of 10 silently not applied -> tripped, 100 written, batch 3 undone, switch on, resume refused while on.
- Tests: own + kill-audit + risk + risk-adversarial + clone, fwd x2 and rev x2: 2186 passed, 6 skipped each. Live 17 + 20 x2: 6 passed. ruff clean.
- Live blast table (unlink company A with child B / unlink B with a bank account + draft move):
  odoo17: A -> res.partner 1, nulled parent_id 1 + commercial_partner_id 1, total 3; B -> res.partner 1 + res.partner.bank 1; move present -> refusal "restrict: account.move.commercial_partner_id".
  odoo20: identical. Delta: Odoo 20 reports on_delete False for some m2o (e.g. discuss.channel.rtc.session.partner_id) -> refused only when that field actually references a touched record. Odoo 20 renamed res.partner.bank acc_number -> account_number (test fixture only). 19 not run.

## Follow-ups / known gaps
- Payload hash is bound via StaleGuard, not persisted in the guard's grant/audit row (guard.py outside allow-list; AuditRow.diff_hash still the gate's own). BOT-APPROVAL-TIERS should store Preview.payload_hash with the grant.
- write_date has 1 s precision: an edit within the same second as preview to an unplanned field is not detected (planned-field edits always are).
- Python-level cascades (overridden unlink, res_model/res_id pointers) stay invisible: flagged "count may be low" + L3, not counted. Recompute list is name-match on `depends`, may over-report.
- Float readback uses 1e-9 relative tolerance: currency rounding by Odoo reads back different and trips (fail-closed false positive).

## Review round 1 fixes (2026-10-26, rebased onto 027cc986; rules.py block re-appended after gate_with_proofs/_ok)
- M1 `blast.confirm(p, approval, typed, snapshot, fingerprint)`: L3 needs a `snapshot.Verified`-style verifier: id must be `snap:`-form, its fingerprint must equal the target's, and `check("snapshot-proof") is True` (via `rules._ok`, exceptions = not proven). A bare/blank id never passes. NOTE: confirm is NOT yet called from the gate path; BOT-APPROVAL-TIERS / BOT-SPINE-WIRE must call it and store `Preview.payload_hash` with the approval.
- M2 `blast.visibility_reasons`: unlink searches run as the Bot's RPC user, so record rules / allowed companies can hide rows Postgres still cascades. Any active ir.rule on a graph model, more than one company, or unreadable rule/company state -> "count may be low: record rules may hide rows" (or companies) -> L3. Limit stated honestly: this flags, it does not make counts complete (no superuser path over RPC). Live: res.partner always flags (multi-company rule).
- L3 binary fields shown as {bytes, sha256}, never base64; masking adds token match (pin, otp, secret, key, cvv, iban, ... + CREDENTIAL_TOKENS) in `diff.secret`. Deviation: `rules.credential_match` NOT widened, because it feeds the committed derived floors (catalogue_rows.json); widening broke 3 drift tests (test_field_floors_no_drift, test_no_sensitive_field_writable_below_floor, test_r5_credential_sweep_drift). Widening risk floors = a separate catalogue re-derivation card.
- L4 unlink payload binds versions ([id, write_date] per deleted model). L6 set-null rows' ids + their companies/users are in the payload.
- L5, L7 remain follow-ups (above).
- Tests: own 55 + kill-audit, risk, risk-adversarial, clone, snapshot: fwd x2 / rev x2 2244 passed, 6 skipped each. Live 17 + 20: 6/6 x3. ruff clean.

Proposed PROGRESS line: `2026-10-26 BOT-DIFF-BLAST reviewed + APPROVED (2 review rounds), nf2 on 027cc986: diff preview + cascade blast + plan_tier + StaleGuard + readback + verified-snapshot confirm + record-rule L3 flag; 2245 pass fwd/rev; live 17/20 6/6; ready to merge.`
Proposed STATE_NF row: `| BOT-DIFF-BLAST | reviewed, APPROVED (2 rounds) | nf2-backend uncommitted on 027cc986 | diff.py, blast.py, risk/rules.py, 2 tests |`

## Review round 2 (2026-10-26): APPROVE, 3 lows applied
- confirm requires a real `snapshot.Verified` instance (duck types refused) and a non-empty id after `snap:`.
- Binary summary reports decoded byte count (base64 decoded; falls back to text length if not base64).
- +3 permanent cases (bare/blank `snap:`, duck verifier, constructed Verified with failed restore; decoded size). Own 56; with kill-audit/risk/risk-adversarial/clone/snapshot fwd + rev: 2245 passed, 6 skipped. ruff clean.
