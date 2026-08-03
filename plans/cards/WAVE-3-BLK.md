# Wave 3 — BLK: bulk & workflow-optimization suite (Document 7, complete)

Shared context: Doc 7's principle — every operation here is ALREADY PERMITTED for the
authenticated Odoo user; Odoo's own checks fire per record inside a batch. We expose what the
UI hides. Guardrails (Doc 7 §10) apply to EVERY card: (a) never escalate privilege — all calls
run as the connection user; (b) per-record success/failure reporting, never aggregate-only;
(c) audit-log every bulk run (existing audit middleware + a bulk_runs record). Existing code:
`power_ops_recipes.py` + `routers/power_ops.py` (dry-run + confirm pattern to follow),
`packages/odoo-client` (execute_kw), `data_import.py`. New backend module family:
`apps/api/app/bulk_suite/` + `routers/bulk_suite.py`. New web page: Operate → Bulk Suite
(functional now; restyled by UIX-4c).

Shared deliverable (build once in BLK-1): `BulkRunResult` schema —
`{run_id, operation, model, total, succeeded, failed, per_record: [{id, display_name, ok,
error}], dry_run}` — stored + returned by every BLK endpoint.

---

## BLK-1 — Generic bulk state transition + discovery engine

TASK: Any-model bulk workflow transitions using per-instance discovered button methods
(Doc 7 §1 + §9).

INPUT: `packages/odoo-client` (get_views/fields_get access), `routers/power_ops.py` (confirm
pattern), capabilities cache, TIER-4 hook note (cache invalidation on version change).

CHECKLIST:
- [x] Discovery: for a model, fetch form view arch (`get_views`), parse `<button
      type="object">` names; classify state-transition candidates (button near/affecting a
      selection field named `state`/`x_status` — heuristics documented) vs wizard-openers
      (flagged not-bulk-safe); cache per (connection, model, odoo_version).
- [x] Endpoint `GET .../bulk/transitions?model=` → discovered buttons with human labels +
      bulk-safe flag. `POST .../bulk/transitions/run` — {model, ids|domain, method, dry_run,
      confirm}: dry-run lists targets; execute calls the method once with the full multi-ID
      recordset (single execute_kw), falling back to per-record calls ONLY to attribute
      per-record errors after a batch failure.
- [x] BulkRunResult schema + storage + audit hook (shared for all BLK cards).
- [x] Domain-based selection supported (DomainBuilder-compatible domain string) + explicit id
      list; hard cap configurable (default 1000/run) with clear message.
- [x] Protected-tier note: methods on tier-1 models ARE allowed (Odoo's own methods — Doc 7
      boundary), with the standard confirm gate + snapshot for reversible types.
- [x] Web: Bulk Suite page section — model picker (introspection), discovered-transitions
      list, record picker (domain or list), dry-run → results table (per-record).
- [x] Tests: arch-parse discovery unit tests (sample archs incl. wizard button), fake-RPC run
      with partial failure → per-record errors, cap test.

DONE MEANS: live smoke — bulk-confirm 3 draft records of a workflow model on docker Odoo 19
via a discovered button; partial-failure case demonstrably reported per record.

DO NOT: hardcode model/button tables; auto-execute without dry-run-first UI flow.

GATE: `uv run pytest tests/test_bulk_suite.py -q` + RPC smoke 19 + 17 (button discovery is
version-sensitive).

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## BLK-2 — Universal mass field edit

TASK: Any model, any writable field: one `write([ids], {field: value})` (Doc 7 §2).

INPUT: BLK-1 shared schema; introspection router (fields), DomainBuilder.

CHECKLIST:
- [x] `POST .../bulk/mass-edit` {model, ids|domain, values{field: value}, dry_run, confirm}:
      validates fields exist + writable (not compute/readonly, not tier-1 model per PCM-4
      unless whitelisted chatter fields), coerces types (selection key valid, m2o id exists).
- [x] Multi-field in one write supported; dry-run shows before→after sample (first 20).
- [x] Web: mass edit section on Bulk Suite (JSON values + shared domain/id picker, preview table).
- [x] Tests: validation matrix (bad field, bad selection key, readonly), fake dry-run preview,
      live smoke edit on x_blk_wf_item.

DEVIATIONS: Web uses JSON values object first — type-aware per-field inputs deferred to UIX-4c.

---

## BLK-3 — Generic duplicate detection & merge

TASK: Find + merge duplicates on ANY model with automatic FK relinking (Doc 7 §3).

INPUT: `ir.model.fields` introspection via odoo-client; snapshots service (snapshot-first);
BulkRunResult.

CHECKLIST:
- [x] Candidate search `POST .../bulk/dedupe/scan` {model, match_fields, mode: exact|fuzzy,
      limit}: exact = grouped search_read; fuzzy = normalized compare (casefold, strip
      punctuation/whitespace, optional simple ratio via difflib — no new deps) computed
      server-side on fetched candidates; returns grouped candidate sets with field previews.
- [x] Merge `POST .../bulk/dedupe/merge` {model, winner_id, loser_ids, archive_or_delete,
      confirm}: discovers ALL m2o fields across the DB referencing the model via
      `ir.model.fields` search (`relation = model`, ttype in m2o) + m2m relation tables via
      write relink (4,id / 3,id ops); relinks chatter (mail.message/mail.followers res_id)
      where present; then archive (default) or unlink losers.
- [x] Snapshot BEFORE merge (metadata + affected-record reference map stored in the run
      record for manual recovery guidance); merge is flagged partially-reversible — honest
      label per COPY_GUIDE.
- [x] res.partner path: offer Odoo's own `base_partner_merge` wizard when installed
      (detected), our generic engine otherwise/for all other models.
- [x] Web: scan → grouped candidates UI (pick winner per group) → confirm phrase → results.
- [x] Tests: relink discovery unit test (fake fields table incl. m2m), merge dry-run, live
      smoke: create 2 duplicate records of an x_ model + a referencing child, merge, assert
      child now points at winner.

DEVIATIONS: Live smoke child model created via RPC (`x_blk_wf_ref`) instead of module upgrade.

---

## BLK-4 — Cron manager

TASK: Plain-language scheduled-action management: list, explain, run-now (single/bulk),
create/edit — no developer mode (Doc 7 §4).

INPUT: `routers/config_ops.py` (existing cron list/patch — extend, don't duplicate),
odoo-client cron helpers.

CHECKLIST:
- [x] Human description per cron: model label + method + interval rendered as a sentence
      ("Every day: send overdue payment reminders (mail.template …)"); known-core crons get a
      curated description map; unknown → generated sentence from fields.
- [x] Run now: `method_direct_trigger` on ir.cron when callable via RPC (probe on the target
      major FIRST; record result); fallback = call the cron's model/method directly with its
      stored args; bulk run-now for a selection.
- [x] Create/edit: model+method picker (introspected), interval/nextcall/active; guard:
      creating code-type server actions stays under Option A rules (module path) — cron here
      only targets EXISTING methods.
- [x] Web: Operate → Cron Manager (list with plain descriptions, toggle, run-now, history of
      our triggered runs via BulkRunResult).
- [x] Tests: description renderer, probe fallback, fake run; live smoke: trigger a harmless
      core cron on docker 19.

DONE MEANS: non-developer-mode user flow complete; probe results recorded per major 17/18/19.

DO NOT: expose raw Python; delete crons (out of scope).

GATE: pytest + RPC smoke 19 (+ probe log for 17/18).

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## BLK-5 — Attachment housekeeping

TASK: Detect orphaned attachments + checksum duplicates; clean through existing confirm gates
(Doc 7 §5).

INPUT: odoo-client search_read; existing `drop_attachments` recipe (deletion path),
snapshots.

CHECKLIST:
- [x] Orphan scan: attachments with res_model/res_id where the referenced record no longer
      exists (batched existence checks per model); exclusions: res_model false/empty
      (standalone uploads — flagged separately, NOT auto-cleanable), `ir.ui.view` assets,
      anything referenced by fields of type binary with attachment=True heuristics documented.
- [x] Duplicate scan: group by checksum, rank by size × count; keep-newest default.
- [x] Report first: scan endpoints return findings + total reclaimable bytes; deletion goes
      through a confirm-phrase run reusing the power-ops confirm pattern + BulkRunResult.
- [x] Web: Operate → Housekeeping (scan cards: orphans / duplicates / large-old; findings
      tables; clean action).
- [x] Tests: orphan detection with fake data (deleted parent), checksum grouping, exclusion
      rules; live smoke on 19 with seeded attachments.

DONE MEANS: scans accurate on seeded fixtures; zero false-positive deletion of standalone or
asset attachments in tests.

DO NOT: auto-delete anything; touch attachments on tier-1 models' records without the same
confirm as everything else (no special path).

GATE: pytest + RPC smoke 19.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## BLK-6 — Bulk activities, bulk security provisioning, bulk portal access

TASK: Three batch tools with zero Studio dependency (Doc 7 §6/§7/§14).

INPUT: odoo-client (mail.activity, res.users/res.groups, portal wizard), access router.

CHECKLIST:
- [x] Bulk activities: `POST .../bulk/activities` {model, ids|domain, activity_type_id,
      summary, date_deadline, user_id?}: mail.activity create per record (res_model_id
      resolved); works on any mail.activity.mixin model (probe + honest error otherwise).
- [x] Bulk security: add/remove N users to/from M groups in one operation (m2m writes on
      res.groups.users or res.users.groups_id per major — use odoo-client compat); DIFF
      PREVIEW required before apply (who gains/loses what, incl. implied groups warning);
      offboarding preset: remove-from-all-non-base groups + deactivate option (reuses
      existing deactivate_users recipe).
- [x] Bulk portal: portal.wizard batch grant (create wizard with all partner lines in one
      wizard record where the major allows; else loop) + revoke; email-missing partners
      reported per-record, not batch-failed.
- [x] Web: three sections under Bulk Suite; security one gated to admin-ish app role later
      (MON-1 note: feature key `bulk_security`).
- [x] Tests: fake flows + per-record failures; live smoke on 19: schedule activities on 3 x_
      records; grant portal to 2 seeded partners.

DONE MEANS: three live smokes green; diff preview provably shown before security apply.

DO NOT: touch group IMPLICATIONS (no editing implied_ids); grant portal without email
silently.

GATE: pytest + RPC smoke 19.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## BLK-7 — Stored-computed recompute + threaded bulk send

TASK: The two honesty-critical tools (Doc 7 §12/§13).

INPUT: odoo-client; COPY_GUIDE honesty templates.

CHECKLIST:
- [x] Recompute: `POST .../bulk/recompute` {model, field, ids|domain}: (1) introspect the
      compute's dependency fields via fields_get/ir.model.fields; (2) VERIFY the touch
      technique on THIS instance first — probe on ≤3 records (write dependency value to
      itself, read compute before/after where determinable); (3) only then batch-touch; if
      probe can't confirm, return the honest "requires shell access — not available on this
      hosting" message (exact copy in COPY_GUIDE) with zero writes. All touch writes with
      tracking_disable context to avoid chatter spam.
- [x] Threaded send: `POST .../bulk/send-message` {model, ids, mail_template_id|body,
      subject}: per-record `message_post` with the template rendered per record —
      correct threading by construction; rate: sequential with progress; NEVER Odoo's
      mass-mail composer path (documented buggy — Doc 7 §13).
- [x] Web: recompute under Housekeeping (with the honesty state rendered when probe fails);
      send under Bulk Suite.
- [x] Tests: probe-fail path returns honesty message + no writes; threaded send fake test
      asserts message_post per record; live smoke: post templated messages to 3 records on
      19, verify message_ids attached per record.

DONE MEANS: probe honesty path demonstrably works; live threading verified.

DO NOT: claim recompute success without the probe; use mail.compose.message mass mode.

GATE: pytest + RPC smoke 19.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.

---

## BLK-8 — Cross-report-type merged PDF

TASK: Render N different QWeb reports for a record set and merge into one PDF server-side
(Doc 7 §13 narrow gap).

INPUT: `routers/reports.py`, odoo-client report rendering (probe render RPC per major —
`ir.actions.report` render via `/report/pdf` route needs session auth; RPC path:
`render_qweb_pdf` exposure varies — PROBE FIRST, document per major which path works),
new dep `pypdf` (MIT — add to apps/api pyproject).

CHECKLIST:
- [x] Render probe per major 17/18/19 recorded (which RPC/HTTP path returns PDF bytes);
      implement the working path(s) with version dispatch in odoo-client.
- [x] `POST .../reports/merge-print` {items: [{report_id, record_ids}], order}: renders each,
      merges with pypdf preserving order; returns single PDF (streamed).
- [x] Web: Reports page "Combined print" flow (pick reports + records, download).
- [x] Tests: merge unit (two small generated PDFs), live smoke on 19 (partner report +
      second report merged, page count asserted).

DONE MEANS: live merged PDF downloads with correct page count on 19; per-major probe results
documented in the card return + capability matrix (TIER-1 row).

DO NOT: shell out to wkhtmltopdf locally (server renders); guess the render RPC.

GATE: pytest + RPC smoke 19.

RETURN: ≤10 lines + probe table.

DEVIATIONS: conservative + log.

---

## BLK-9 — Inventory ID Generator port (AppleScript → product feature)

TASK: Port the Inventory ID Generator to a Python data tool: PREFIX/INITIALS/NUMBER reference
IDs with semantic initial extraction, fixing all six audit findings by construction; wire
optionally to ir.sequence.

INPUT: the AppleScript audit findings (below — verbatim, binding); `industry_seeds.py` +
`data_import.py` (CSV plumbing); `routers/config_ops.py` (sequences).

Audit findings that MUST be fixed by construction (from the AppleScript review):
1. Write-back: Numbers-style whole-column list writes corrupted data → Python port writes
   only changed cells/rows individually (CSV round-trip: only rows whose code changed are
   emitted as changed).
2. trimText only stripped ASCII spaces → trim against full whitespace incl. tabs, newlines,
   NBSP (`\s` + \u00a0 explicitly).
3. `cell idx` loop-reference bug → all indexing integer-safe by language design; add explicit
   int coercion on parsed inputs anyway.
4. `set newCodeValues to codeValues` aliasing → no shared mutable state; pure functions,
   copies explicit.
5. Log written in default encoding → all file IO explicit UTF-8.
6. Semantic initials under-specified → deterministic rules: initials from significant words
   (stopword list: the/a/an/of/and/de/la…), uppercase, configurable length (default 3),
   collision handling = numeric disambiguator on initials (ABC, AB2, AB3) with stable
   assignment; unicode-normalized (NFKD, diacritics stripped).

CHECKLIST:
- [x] `apps/api/app/id_generator.py`: pure functions — `extract_initials(name, length,
      stopwords)`, `next_number(existing_codes, prefix, initials, padding)`,
      `generate_codes(rows, config) -> [{row_id, name, existing_code, new_code, changed}]`;
      config: prefix, separator, padding (default 4), initials length, skip-if-present.
- [x] All six audit fixes covered by dedicated unit tests (one test per finding, named
      test_audit_fix_1_… etc.).
- [x] CSV mode: upload CSV (name column + optional code column) → preview changed rows only →
      download updated CSV. Reuses data_import parse plumbing.
- [x] Live mode: pick connection + model + name field + code field → dry-run preview →
      write only changed records (batched write, BulkRunResult).
- [x] ir.sequence bridge: optional "create ir.sequence for this model" (prefix pattern,
      padding) via existing config_ops sequences path, so future records number natively.
- [x] Web: Data → ID Generator page (CSV tab + Live tab, preview table showing
      old→new, changed-only toggle).
- [x] Property-based test: 500 random names → all codes unique, format-valid, idempotent
      (second run = zero changes).

DONE MEANS: unit + property tests green; live smoke assigns codes to seeded x_ records on 19;
idempotency proven.

DO NOT: renumber existing valid codes unless user opts in (skip-if-present default ON);
write unchanged rows.

GATE: `uv run pytest tests/test_id_generator.py -q` + RPC smoke 19.

RETURN: ≤10 lines.

DEVIATIONS: conservative + log.
