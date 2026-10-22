# Operate: Drift watch, Staging→prod promotion, Access/SoD audit, Performance doctor

Baseline `00_BASELINE.md` applies.

<a id="drift"></a>
## DRIFT: Drift watch (out-of-band production changes, diff, undo)
Extends FA Pipelines item 4 (drift alarm between live and test), HOME-AGENCY (drift column), 5B-03 (fingerprint drift), BR-DRIFT (Bridge schema drift; separate scope) and `odoo_snapshot.py`.
1. **User / job:**
   - An agency whose client admin edits production directly: "Tell me what changed outside Ingenium, show the diff, let me put it back."
   - Value: prevents silent breakage and blame games.
   - Metric:
     - Every out-of-band change to a watched object type made on the live test DB between two scans is detected (recall 100% on the seeded live test).
     - The same object changed via Ingenium is never flagged (precision on Ingenium journal entries is 100%).
2. **UX:**
   - Operate → Drift. The timeline of detected changes shows: object, kind (added / changed / removed), when (Odoo `write_date`), by whom (`write_uid` name), and whether Ingenium made it.
   - Click → `DiffView` of the before (last snapshot) and now.
   - Actions: "Accept as new baseline" (records the acceptance) or "Put it back" (a restore plan through Check → Approve → Run with Undo).
   - Watch frequency: daily by default, hourly as an option.
   - Notifications go to Home "Needs you".
   - ⌘K: "Check for drift now".
3. **UI:** area 01 History (Linear) for the timeline and area 14 for the restore confirm.
4. **Security:**
   - Watched types: `ir.ui.view`, `ir.ui.menu`, `ir.actions.*`, `base.automation`, `ir.model.fields` (manual), `res.groups`, `ir.model.access`, `ir.rule` (17–19) or `ir.access` (20), and `ir.cron`.
   - Restore is limited to types the snapshot can restore (DEC-059). Fields and data are report-only.
   - The restore runs as a plan with a receipt, under the anomaly cap.
5. **Robustness:**
   - The fingerprint per object is `sha256(normalised record JSON)`. The baseline is the latest snapshot plus Ingenium journal entries.
   - Scans use `write_date > last_scan` filters, and a full sweep runs weekly.
6. **Data / API:**
   - Table `drift_events` (object_model, res_id, kind, before_hash, after_hash, write_uid, write_date, by_ingenium, status: open|accepted|restored).
   - Scan id `drift`.
   - `GET /api/connections/{id}/drift?status=open` → `{events[]}`.
   - `GET …/drift/{eid}/diff` → `{before, after}`.
   - `POST …/drift/{eid}/accept`.
   - `POST …/drift/{eid}/restore` → plan id.
7. **Risks:** `write_date` is updated by Odoo itself on module upgrade, which is a false positive. Mitigation: suppress events whose `write_uid` is `__system__` (OdooBot / uid 1) during a module upgrade window detected by `version_watch`; label the rest.

<a id="promo"></a>
## PROMO: Staging→prod promotion as one reviewed change set
Extends FA-PIPELINES (Test → Staging → Live lanes, the same package each time), FA Pipelines item 5 (release notes), `promote.py`, the `environments` router and the `changeset/` executor. Promotion to another connection stays human (AGENTS); this epic makes it reviewable and safe, not automatic.
1. **User / job:**
   - An agency that built and tested changes on staging: "Ship exactly those changes to production as one reviewed change set, and undo it if needed."
   - Value: no hand re-keying, and no forgotten piece.
   - Metric:
     - A change set built from staging applies to a fresh test target with an object-level diff of zero against staging for the included objects (live).
     - Every promotion has reviewer and approver audit entries.
2. **UX:**
   - Pipelines → "New release". Pick the source (staging) and target (prod).
   - Ingenium lists the differences (from the journals and a metadata diff), and the user picks objects.
   - Release notes are auto-drafted in plain words and editable.
   - Review: the second approver sees the diff plus notes.
   - Promote: Check (dry run on target) → Approve → Run → History with one-click Undo of the whole set (where Odoo allows).
   - Conflicts: when a target object changed since the base, the screen shows a 3-way view and the user chooses which version to keep.
   - ⌘K: "New release".
3. **UI:** area 05 Approvals (Superhuman, Linear Inbox) for review, and area 01 for the release list.
4. **Security:**
   - Two-person rule by default for Live targets (SEC-2APPROVER).
   - The money guard and protected registry (`changeset/protected_registry.py`) apply on the target.
   - The source and target must belong to the same workspace (tenancy test).
5. **Robustness:**
   - The change set is content-addressed (`sha256` of ordered ops).
   - Apply is ordered: models → fields → views → actions → menus → access → automations, the same order as the wave engine.
   - The whole set has a snapshot before it. A step failure rolls back applied steps via `changeset/rollback.py` and reports.
6. **Data / API:**
   - Table `releases` (source_id, target_id, ops JSON, sha256, notes, reviewer, approver, status, snapshot_id).
   - `POST /api/releases {source_connection_id, target_connection_id}` → candidate diff.
   - `POST /api/releases/{rid}/ops {include[]}`.
   - `POST /api/releases/{rid}/review {decision}`.
   - `POST /api/releases/{rid}/promote` → 428 without a receipt.
   - `POST /api/releases/{rid}/undo`.
7. **Risks:** this touches write-path orchestration, so the promote/undo card is routed L3 with oracle tests. Conflict UX is complex; v1 offers "keep target" or "take source" per object only.

<a id="sod"></a>
## SOD: Access and segregation-of-duties audit with auditor report
Extends SUITE-12/13 (role x-ray, access hygiene; built look-only in REG-SUITE-LOOK), FA-S03 (access: test as user), SEC-LEASTPRIV / EL-CONN-LEASTPRIV (Ingenium's own user) and HIST-EXPORT (tamper-proof export).
1. **User / job:**
   - A finance lead or external auditor: "Who can both create a vendor and pay a vendor bill? Who has admin? Give me a signed report."
   - Value: SME audits and bank or investor due diligence.
   - Metric:
     - On the seeded live DBs, each default conflict rule returns exactly the users who hold both capabilities (computed from groups plus implied groups plus model access), matching a hand-built expected list on 17–20.
     - The report signature verifies.
2. **UX:**
   - Operate → Access audit. Three tabs:
     - Conflicts: rule, users, path ("Alice → Accounting / Billing → can create `account.payment`").
     - Privileged users: Settings, Administrator, technical features.
     - Dormant accounts: no login for 90 days, from access hygiene.
   - Each conflict offers "Remove from group" as a plan (with Undo) or "Accept with reason".
   - "Auditor report" produces a PDF with the rules, results, accepted exceptions with names, and a hash anchored in the audit chain.
   - ⌘K: "Run access audit".
3. **UI:** area 09 Records tables, plus area 14 for the report and confirm.
4. **Security:**
   - The default rule set lives in `app/scans/sod_rules.yaml` (DEC-060). Each rule names model and operation pairs, for example `res.partner:create` + `account.payment:create`.
   - Capabilities are computed from `res.groups` (`implied_ids` closure), `ir.model.access` (17–19) or `ir.access` (20), and record rules flagged as "may narrow" without being evaluated.
   - Group removal is a plan and is refused for the connection's own integration user.
5. **Robustness:** the closure is computed once per run. Users are paged at 500. Odoo 20 group field names come from compat.
6. **Data / API:**
   - Scan id `sod`.
   - `GET /api/connections/{id}/sod/latest` → `{rules[{id, title, pairs[]}], conflicts[{rule_id, user_id, paths[]}], privileged[], dormant[], accepted[]}`.
   - `POST …/sod/accept {rule_id, user_id, reason}`.
   - `GET …/sod/{run}/report.pdf`.
7. **Risks:** record rules can narrow access, so the model-level result over-reports. The report labels results "may be narrowed by record rules: N users". DEC-060.

<a id="perf"></a>
## PERF: Performance doctor
New. Partly in BOLD-B3 (doctor). Public ORM only: no `pg_stat`, no SQL (INV-12).
1. **User / job:**
   - An admin whose Odoo "feels slow": "What is slow and what can we change without a developer?"
   - Value: finds the usual configuration causes, such as overdue crons, huge attachment tables in the DB, mail queue backlog, unindexed custom fields used in filters, and too many active automations on hot models.
   - Metric:
     - Every finding names its measured evidence (timed probe ms, counts).
     - Probes stay within the RPC budget (≤ 60 calls per run by default).
     - Findings are identical in kind on 17–20.
2. **UX:**
   - Operate → Performance. "Run doctor (read-only, about 1 min)".
   - Results:
     - timed probes (list view load for the top 10 models by count, p50 and p95 over 5 tries);
     - cron backlog (`nextcall` overdue, `failure_count` where the version has it);
     - `mail.mail` queue size;
     - attachment storage split (db vs file, where `ir.attachment` exposes it);
     - custom fields used in search views or filters without `index`;
     - automations per model.
   - Fixes:
     - add an index flag on a custom `x_` field (plan, sandbox-first);
     - deactivate an unused automation (plan, Undo);
     - plain advice for host-level items (workers, memory), labelled "ask your host".
   - ⌘K: "Run performance doctor".
3. **UI:** area 16 Charts (probe timings, bar per model), area 09 for findings.
4. **Security:**
   - Probes are read-only and capped.
   - The index flag applies to `x_` manual fields only. It is refused on stock fields.
   - On Online, fixes are limited to automations.
5. **Robustness:**
   - Probes are spaced at 250 ms or more and stop on any 429/503.
   - Timing noise: the median of 5 tries, and a finding only when p50 is above 1.5 s [Inferred threshold; tune live].
6. **Data / API:**
   - Scan id `perf`.
   - `GET /api/connections/{id}/perf/latest` → `{probes[{model, view, p50_ms, p95_ms, n}], crons[], mail_queue, attachments, unindexed[], automations_per_model[]}`.
   - Fixes use `POST …/findings/{fid}/plan`.
7. **Risks:** whether `ir.model.fields.index` can be written through RPC on manual fields is [Inferred], and the PERF-LIVE card proves it per version, otherwise the fix becomes advice only. DEC-073 covers the probe budget.
