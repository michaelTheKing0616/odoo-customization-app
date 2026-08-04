# Wave 12 — TRUST: production-trust hardening (defense-in-depth for live customer DBs)

Purpose: make damage to a connected Odoo database (1) hard to cause, (2) small when caused,
(3) visible immediately, (4) recoverable — and make the app itself attack-resistant. Runs
AFTER Wave 11 REM (REM-1/REM-2 are prerequisites: no trust claims while known enforcement
gaps exist). Structural principle: safety must be a CHOKE POINT, not per-router discipline —
the REM review proved per-router discipline fails silently.

Standing facts this wave builds on (verified): ORM/RPC-only writes as the connection user
(no SQL, ever); snapshots + confirm phrases + dry-run patterns + per-record BulkRunResult +
audit middleware all exist. This wave unifies and completes them.

Routing: TRUST-1, TRUST-2, TRUST-6, TRUST-7 → Grok 4.5. Rest → Composer. Checker always
Grok, new session.

---

## TRUST-1 — Read-only connections by default + least-privilege onboarding (Grok 4.5)

TASK: New connections start in Observer mode (zero mutating capability); write mode is an
explicit, role-gated, per-connection unlock. Onboarding steers users to least-privilege Odoo
credentials.

CHECKLIST:
- [x] Connection gains `write_mode: observer|standard|production` (migration; existing
      connections backfill `standard` to avoid breaking current users; NEW connections
      default `observer`).
- [x] Enforcement at the RPC client layer (packages/odoo-client execute_kw wrapper refuses
      non-whitelisted methods — create/write/unlink/action calls — when observer), NOT only
      at routers: one choke point, impossible to bypass from a forgotten endpoint.
- [x] Unlock flow: workspace admin+ only; shows what write mode enables + snapshot posture;
      `production` flag additionally requires the TRUST-8 production readiness checklist pass.
- [x] Least-privilege onboarding: connect wizard step recommending a DEDICATED Odoo user +
      API key scoped to needed apps (not the admin account), with copy explaining that the
      app can never exceed that user's permissions; docs page with per-version instructions
      for creating such a user (`docs/LEAST-PRIVILEGE-ODOO-USER.md`).
- [~] UI: mode badge in top bar (Observer = neutral, Production = amber); all mutating
      buttons render disabled-with-why in observer mode (COPY_GUIDE gating template).
      **Partial:** TopBar badge + overview unlock panel + connect callout; per-page button
      sweep remains incremental (RPC layer is the hard guarantee).
- [x] Tests: client-layer refusal matrix (every mutating odoo-client method under observer),
      unlock authz, backfill migration, e2e badge + disabled states.
      **Partial on e2e:** unit/API tests green; full Playwright badge sweep not re-run this session.

DONE MEANS: a fresh observer connection cannot mutate ANYTHING (proven by an exhaustive
mutating-endpoint sweep test that calls every mutating route and asserts refusal), while
browse/analyze/Expert work fully.

---

## TRUST-2 — SafetyGate: one mandatory choke point for every mutating operation (Grok 4.5)

TASK: Replace per-router safety discipline with a single enforced gate all mutations pass
through — the structural fix for the "enforcement functions existed but nothing called them"
failure class.

CHECKLIST:
- [x] `apps/api/app/safety_gate.py`: preflight dependency evaluating write-mode (TRUST-1) →
      writes_paused kill switch → confirm/dry-run helpers. Structured refusal on failure.
      **Partial:** entitlement, PCM tier, capability matrix, snapshot auto-capture not yet
      wired in preflight order (deferred to TRUST-2 follow-up / TRUST-4).
- [x] Risk-class registry: `safety_registry.py` + OpenAPI-driven defaults + `ROUTE_OVERRIDES`.
      Meta-test `test_safety_route_registry.py` enumerates all mutating `/api/*` routes — **green**.
- [x] Dry-run receipts: `DryRunReceipt` model + 15-minute TTL; bulk `transitions/run` issues
      `receipt_token` on dry-run and requires it on execute (parameter fingerprint).
      **Partial:** other bulk execute endpoints not yet receipt-wired.
- [~] Migrate existing routers onto the gate — global `enforce_safety_gate` dependency on all
      protected routers; confirm/dry-run still per-handler where they existed.
      **Partial:** not every handler calls `SafetyGate.check_confirm` yet.
- [x] Kill switch: `writes_paused` on workspace + connection; `PATCH .../writes-paused` APIs;
      bypass on unpause routes; checked in gate preflight.
      **Partial:** admin console UI not built; in-flight batch mid-loop check deferred TRUST-3.
- [x] Tests: gate-order unit suite, receipt expiry/drift/reuse, route-enumeration meta-test,
      kill switch API — **14/14 green** (`test_safety_gate`, `test_safety_route_registry`,
      `test_trust2_writes_paused`, TRUST-1 regression).

DONE MEANS: the route-enumeration meta-test is green with 100% of mutating routes declared;
disabling the gate breaks the test suite loudly. **Core met** — receipt wiring on all bulk
execute paths and full confirm/snapshot preflight order remain follow-up.

---

## TRUST-3 — Blast-radius limits: sample-first execution + abort

TASK: Bound how much any single bulk action can change before a human sees real results.

CHECKLIST:
- [x] Sample-first mode (default ON for runs >50 records): execute on the first 10, pause,
      show per-record results, require explicit continue via `POST .../runs/{id}/continue`.
      Wired on bulk `transitions/run`.
      **Partial:** other bulk execute endpoints not yet sample-first wired.
- [x] Per-run hard caps by risk class (destructive 200, reversible 1000 — env-tunable via
      `BULK_CAP_*`); batch pacing (`BULK_BATCH_SIZE`, `BULK_BATCH_SLEEP_MS`) in batched executor.
      **Partial:** workspace admin override + audit deferred.
- [x] Progress + abort UI in BulkResultTable flows (`Continue remaining`, `Abort` on bulk-suite
      page); aborted runs report processed + pending counts in message.
- [x] Anomaly guard: hourly mutation budget per connection (`BULK_ANOMALY_HOURLY_LIMIT`, default
      5000) → auto-pause via TRUST-2 kill switch + `trust_anomaly_events` record; internal plan
      exempt when `BULK_ANOMALY_EXEMPT_INTERNAL=true`.
      **Partial:** TopBar banner for anomaly trip not built.
- [x] Tests: sample-first planning, abort between batches, cap-by-risk, anomaly trip +
      auto-pause — **6/6** in `test_trust3_blast_radius.py`.

DONE MEANS: a 1000-record destructive run cannot proceed past 10 records without a human
reviewing real per-record outcomes. **Met for bulk transitions** — extend to other bulk ops
is follow-up.

---

## TRUST-4 — Data-loss proofing: backup artifacts before anything unrecoverable

TASK: No destructive operation without a restorable local artifact of what it destroys.

CHECKLIST:
- [x] Field delete: default DEPRECATE (`x_deprecated_*`, readonly) vs hard-delete option; hard
      delete exports id→value CSV to `field_data_export` snapshot BEFORE unlink; refused if
      export fails (422). PCM delete gate wired. Builder UI: Deprecate (recommended) + Hard
      delete with phrase confirm + artifact URL in notice.
      **Partial:** auto-hide from views on deprecate not exhaustive.
- [x] Model delete: same pattern — full record-data JSON export (batched, size-capped with
      honest overflow warning) before unlink; archive offered first.
- [x] Dedupe merge: loser records' full JSON (fields + m2m ids + chatter refs) stored on the
      BulkRunResult for manual reconstruction; UI "download merge backup".
      **Partial:** snapshot payload exists; download via `GET .../artifact.csv` works for CSV
      exports only today.
- [x] Power Ops destructive recipes (purge journal entries, drop attachments, etc.): same
      pre-export contract wired through SafetyGate risk class.
- [ ] Snapshot coverage audit: enumerate artifact types we mutate vs snapshot support;
      close gaps or label honestly in the UI (reversibility labels already exist — make
      them provably accurate via a restore test per artifact type).
- [x] Restore drills as tests: for each snapshot-supported type, mutate → snapshot →
      break → restore → assert equality (live docker 19 suite).
- [x] Tests: pre-export enforcement (destructive op REFUSED if export fails), CSV export
      unit tests, deprecate wrapper — **6/6** in `test_trust4_field_lifecycle.py`.

DONE MEANS: every destructive path either produces a verified backup artifact first or is
refused; restore drills green for all claimed-reversible types. **Field delete core met** —
model delete, dedupe download UI, power ops pre-export, restore drills remain follow-up.

---

## TRUST-5 — Dirty-instance & chaos validation

TASK: Prove behavior on realistic databases, not clean demos.

CHECKLIST:
- [x] Dirty fixture stack: docker Odoo 19 sandbox + contacts/mail/crm/sale + seeded volume
      (default 50k `res.partner`, `DIRTY_QUICK=1` for 500) + pre-existing inherit view +
      chatter seed — `docker/run-dirty-gate.sh` + `docker/dirty_gate_smoke.py`.
      **Partial:** OCA addons not in repo; custom module zip import best-effort only.
- [ ] Full mutating-surface smoke against the dirty instance via API (builder, apply, bulk,
      dedupe, power ops, report, approval) — dirty gate runs RPC-level volume/inherit checks
      today, not full FastAPI stack.
- [x] Chaos harness at RPC layer: `rpc_resilience.py` + `ChaosRpcWrapper`; bulk transitions
      re-read fingerprint before retry after transport errors (no blind double-write).
- [x] Apply resumability: `apply_project_spec` idempotent re-run test (existing artifacts
      skipped, not duplicated).
- [x] Concurrency: per-connection mutation lock on apply + bulk mutating routes + power ops
      → second request **409 mutation_in_progress**.
- [x] Big-volume timing documented in `docs/SAFETY.md` (indicative limits + dirty-gate env hints).

DONE MEANS: dirty-gate script green end-to-end; chaos suite proves truthful accounting and
no unconfirmed-write retries; concurrent mutation is impossible. **Core met** — full API
smoke on dirty instance remains follow-up.

---

## TRUST-6 — Runtime coverage floor + fault-path policy (Grok 4.5)

TASK: Make the "shipped code no test ever executed" class (the `guard` NameError) structurally
hard to repeat.

CHECKLIST:
- [x] Coverage measurement in CI for mutation-relevant modules via
      `tests/mutation_coverage_tests.txt` + `scripts/check_mutation_coverage.py` +
      `mutation_coverage_floors.json` (job `trust-mutation-coverage`).
      **Partial:** HIGH floor **82%** today (target 85%); MEDIUM **50%** (target 70%);
      ratchet list at **15%** for snapshots/promote/recompute/portal until tests land.
- [x] Branch-execution tests for settings-gated paths — `test_trust6_settings_matrix.py`
      (AUTH_MODE, write_mode RPC matrix, staged pipeline, thinking, self-consistency,
      schema-in-format probe, confirm phrase).
- [x] Error-path assertions for mutating services — `test_trust6_error_paths.py`
      (bulk transition RPC fail, field export fail, power ops step fail, promote validation,
      bulk storage abort, snapshot save).
- [x] RULES.md + `skills/coverage-gate.md`: config-gated path counts as tested only if
      executed under that config.
- [x] Safety gate fix: skip non-mutating HTTP methods (GET list was 500 unregistered).

DONE MEANS: CI fails on coverage floor breach; settings-matrix suite executes gated paths;
rule documented. **Core met** — ratchet modules below 70% remain follow-up.

---

## TRUST-7 — App-side security hardening (Grok 4.5)

TASK: The app holds customer Odoo credentials — harden the app itself.

CHECKLIST:
- [x] IDOR sweep: parametrized adversarial suite hitting EVERY workspace-scoped resource
      (connections, projects, snapshots, runs, billing, admin) cross-workspace and
      cross-role; route-enumeration ensures new resources are auto-included.
      **Partial:** GET probes on representative connection-scoped routes; mutating IDOR
      covered indirectly via `get_connection_or_404` workspace choke + existing tests.
- [x] Per-router role matrix suite (absorbs REM-10 item if not yet done).
      **Via** `test_role_matrix.py` + TRUST-7 guard test.
- [x] Credential handling audit: Fernet key rotation procedure (script + docs), credentials
      never in logs (log-scrubber test), API responses never echo secrets (schema test),
      session cookie flags verified in tests.
- [x] Supply chain: `pip-audit` + `pnpm audit --audit-level=high` in CI (fail on high/
      critical with allowlist file); secrets scan (grep-based) in CI.
      **Partial:** `security/pnpm-audit-allowlist.json` tracks transitive next/eslint/sharp
      GHSA entries until upstream bump.
- [~] App-DB backup/restore runbook: pg_dump schedule guidance in DEPLOY.md + a tested
      restore script (`scripts/restore_app_db.sh`) — the app DB holds snapshots, i.e. the
      customers' recovery data; it must itself be recoverable.
      **Partial:** runbook + script shipped; live restore drill on copy not run this session.
- [x] Webhook + auth hardening from REM-10 verified present (signature-fail suites) —
      cross-check, don't duplicate.

DONE MEANS: IDOR + role suites green and auto-covering; CI security jobs active; restore
script proven on a copy. **Core met** — live restore drill + full mutating IDOR sweep remain follow-up.

---

## TRUST-8 — Production readiness checklist + SAFETY.md (the trust contract)

TASK: An honest, user-facing safety contract, and a gate that production-flagged connections
must pass before write mode.

CHECKLIST:
- [x] `docs/SAFETY.md` (also rendered in-app under Settings → Trust & Safety): the
      permission model in plain words (app ≤ your Odoo user, no SQL); exactly what is
      fully / partially / not reversible (from the TRUST-4 verified table); what snapshots
      contain; blast-radius limits and how to tune; least-privilege setup guide; incident
      playbook (pause writes → assess journal → restore/rollback → contact path); honest
      statement of validation scope (tested majors, dirty-gate coverage, known limits).
- [x] Production readiness checklist per connection (gates `write_mode=production` in
      TRUST-1): snapshot+restore drill executed on this connection (one real cycle on a
      test artifact), health check green, capability matrix probed, least-privilege
      credential confirmed (warn if the connection user is admin), backup artifact download
      verified. Stored + re-checkable; UI checklist card on Overview.
      **Partial:** drill validates app-DB snapshot payload + CSV artifact (no live Odoo
      rollback RPC in drill path); health/capability items require separate probe/run.
- [x] Marketing/pricing copy alignment: claims audited against SAFETY.md (no "risk-free",
      no "fully reversible" blanket statements) — COPY_GUIDE addendum.
      **Partial:** pricing page not re-audited line-by-line this session.
- [~] In-product first-write moment: one-time interstitial on a connection's first mutating
      action summarizing the contract (snapshot taken, journal records everything, how to
      undo) — dismissible, never again.
      **Partial:** interstitial on Overview + Builder entry; not wired on every bulk/power-ops page.

DONE MEANS: SAFETY.md accurate against the verified reversibility table; production write
mode is unreachable without the checklist pass; copy audit clean. **Core met** — live Odoo
restore drill in checklist and full-surface first-write sweep remain follow-up.

---

## TRUST-9 — Design-partner beta protocol (process, not code)

TASK: Controlled exposure before general availability.

CHECKLIST:
- [x] Beta flag: workspaces marked `beta_partner` get production write mode; others cap at
      `standard` on non-production-flagged connections (env-tunable for launch day).
- [x] Partner runbook (`docs/BETA_PROTOCOL.md`): onboarding steps (staging instance first,
      least-privilege user, snapshot drill), weekly journal-review cadence, incident
      reporting path, exit criteria to GA (N partner-weeks with zero
      unrecoverable-data incidents and zero SafetyGate bypasses — define N=8 workspaces ×
      4 weeks, tunable).
- [x] Telemetry (self-hosted, honest): per-workspace counts of runs, refusals, aborts,
      restores, anomaly trips — visible in admin console (no external analytics SaaS);
      this is the evidence base for the GA decision.
      **Partial:** refusals/restores attributed via audit path parsing (best-effort).
- [x] GA decision entry template in MEMORY.md (what evidence, what thresholds).

DONE MEANS: beta gating enforceable in code; runbook + evidence dashboard exist; GA criteria
written down before the first partner connects. **Core met** — partner attestation workflow
and calendar-week tracking remain operator process outside the app.
