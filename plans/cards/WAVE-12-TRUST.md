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
- [ ] Connection gains `write_mode: observer|standard|production` (migration; existing
      connections backfill `standard` to avoid breaking current users; NEW connections
      default `observer`).
- [ ] Enforcement at the RPC client layer (packages/odoo-client execute_kw wrapper refuses
      non-whitelisted methods — create/write/unlink/action calls — when observer), NOT only
      at routers: one choke point, impossible to bypass from a forgotten endpoint.
- [ ] Unlock flow: workspace admin+ only; shows what write mode enables + snapshot posture;
      `production` flag additionally requires the TRUST-9 readiness checklist pass.
- [ ] Least-privilege onboarding: connect wizard step recommending a DEDICATED Odoo user +
      API key scoped to needed apps (not the admin account), with copy explaining that the
      app can never exceed that user's permissions; docs page with per-version instructions
      for creating such a user.
- [ ] UI: mode badge in top bar (Observer = neutral, Production = amber); all mutating
      buttons render disabled-with-why in observer mode (COPY_GUIDE gating template).
- [ ] Tests: client-layer refusal matrix (every mutating odoo-client method under observer),
      unlock authz, backfill migration, e2e badge + disabled states.

DONE MEANS: a fresh observer connection cannot mutate ANYTHING (proven by an exhaustive
mutating-endpoint sweep test that calls every mutating route and asserts refusal), while
browse/analyze/Expert work fully.

---

## TRUST-2 — SafetyGate: one mandatory choke point for every mutating operation (Grok 4.5)

TASK: Replace per-router safety discipline with a single enforced gate all mutations pass
through — the structural fix for the "enforcement functions existed but nothing called them"
failure class.

CHECKLIST:
- [ ] `apps/api/app/safety_gate.py`: a required dependency/context manager for mutating
      operations, evaluating in order: write-mode (TRUST-1) → entitlement → PCM tier check →
      capability matrix → risk class of the operation (declared, see below) → snapshot
      requirement → dry-run receipt requirement → confirm requirement → audit record.
      Returns a structured refusal (why + options) on any failure.
- [ ] Risk-class registry: every mutating endpoint DECLARES `risk: read|reversible|
      partially_reversible|destructive` + `snapshot: bool` + `dry_run_first: bool` +
      `confirm: none|simple|phrase`. A meta-test enumerates ALL FastAPI routes with
      mutating verbs and FAILS if any lacks a declaration — new endpoints cannot ship
      ungated (this is the card's most important line).
- [ ] Dry-run receipts: bulk execute endpoints require a receipt hash from a dry-run of the
      SAME parameters within 15 minutes; parameter drift invalidates the receipt (prevents
      dry-run-A-execute-B).
- [ ] Migrate existing routers onto the gate (builder, spec apply, automations, bulk suite,
      power ops, config ops, promote, approvals, website, overlay saves) — behavior-neutral
      where gates already existed; gaps closed where they didn't (this absorbs and verifies
      REM-2's wiring permanently).
- [ ] Kill switch: workspace-level and connection-level `writes_paused` flag (admin console +
      API) checked by the gate; pausing takes effect immediately for in-flight batch loops
      (checked per batch).
- [ ] Tests: gate-order unit suite, receipt expiry/drift, route-enumeration meta-test, kill
      switch mid-batch, refusal shapes.

DONE MEANS: the route-enumeration meta-test is green with 100% of mutating routes declared;
disabling the gate breaks the test suite loudly.

---

## TRUST-3 — Blast-radius limits: sample-first execution + abort

TASK: Bound how much any single bulk action can change before a human sees real results.

CHECKLIST:
- [ ] Sample-first mode (default ON for runs >50 records): execute on the first 10, pause,
      show per-record results, require explicit continue; abort cleanly stops between
      batches (no partial-batch kill).
- [ ] Per-run hard caps by risk class (destructive default 200/run, reversible 1000 —
      env-tunable, admin-raisable per workspace with audit); batch pacing (configurable
      sleep between chunks) to avoid hammering production instances.
- [ ] Progress + abort UI in BulkResultTable flows; aborted runs report exactly what
      completed.
- [ ] Anomaly guard: >N mutating operations per connection per hour (default 5000) →
      auto-pause writes (TRUST-2 kill switch) + surface a banner + admin notification
      record. Documented thresholds; internal plan exempt for testing.
- [ ] Tests: sample-first flow, abort between batches, cap enforcement, anomaly trip +
      auto-pause.

DONE MEANS: a 1000-record destructive run cannot proceed past 10 records without a human
reviewing real per-record outcomes.

---

## TRUST-4 — Data-loss proofing: backup artifacts before anything unrecoverable

TASK: No destructive operation without a restorable local artifact of what it destroys.

CHECKLIST:
- [ ] Field delete: default becomes DEPRECATE (rename to `x_deprecated_*`, hide from views,
      keep column/data) with a clearly-worse hard-delete option; hard delete auto-exports
      the column's data (id → value CSV, stored on the run record + downloadable) BEFORE the
      unlink; the confirm dialog links the artifact.
- [ ] Model delete: same pattern — full record-data JSON export (batched, size-capped with
      honest overflow warning) before unlink; archive offered first.
- [ ] Dedupe merge: loser records' full JSON (fields + m2m ids + chatter refs) stored on the
      BulkRunResult for manual reconstruction; UI "download merge backup".
- [ ] Power Ops destructive recipes (purge journal entries, drop attachments, etc.): same
      pre-export contract wired through SafetyGate risk class.
- [ ] Snapshot coverage audit: enumerate artifact types we mutate vs snapshot support;
      close gaps or label honestly in the UI (reversibility labels already exist — make
      them provably accurate via a restore test per artifact type).
- [ ] Restore drills as tests: for each snapshot-supported type, mutate → snapshot →
      break → restore → assert equality (live docker 19 suite).
- [ ] Tests: pre-export enforcement (destructive op REFUSED if export fails), artifact
      integrity, deprecate flow.

DONE MEANS: every destructive path either produces a verified backup artifact first or is
refused; restore drills green for all claimed-reversible types.

---

## TRUST-5 — Dirty-instance & chaos validation

TASK: Prove behavior on realistic databases, not clean demos.

CHECKLIST:
- [ ] Dirty fixture stack: docker Odoo 19 with demo data + 2–3 common OCA/community addons
      installed + seeded volume (≥50k records on a busy model, long chatter) — scripted,
      reproducible (`docker/run-dirty-gate.sh`).
- [ ] Full mutating-surface smoke against the dirty instance: builder, apply, bulk suite,
      dedupe, power ops recipe, report render, approval flow — asserting no collisions with
      pre-existing customizations (inherit-view naming, xpath anchors on modified views).
- [ ] Chaos harness at the RPC layer: injected timeouts, connection drops mid-batch, access
      errors on record N of M — assert per-record accounting stays truthful, no operation
      silently retries a WRITE it can't confirm didn't land (idempotency: batch loops
      re-verify state before re-attempting writes after a transport error).
- [ ] Apply resumability: kill apply mid-run → re-run is idempotent (existing artifacts
      detected, not duplicated) — test exists and passes.
- [ ] Concurrency: two simultaneous applies/bulk runs on one connection → second is queued
      or refused with a clear message (per-connection mutation lock), never interleaved.
- [ ] Big-volume timing recorded (dedupe scan + mass edit on the 50k model) → documented
      limits in SAFETY.md.

DONE MEANS: dirty-gate script green end-to-end; chaos suite proves truthful accounting and
no unconfirmed-write retries; concurrent mutation is impossible.

---

## TRUST-6 — Runtime coverage floor + fault-path policy (Grok 4.5)

TASK: Make the "shipped code no test ever executed" class (the `guard` NameError) structurally
hard to repeat.

CHECKLIST:
- [ ] Coverage measurement in CI for `apps/api/app/` with a per-module floor on
      mutation-relevant modules (spec_apply_ui, bulk_suite/*, power_ops*, safety_gate,
      protected_*, ai_pipeline, promote, snapshots): line coverage ≥85%, and NO module
      below 70% overall; failing floor fails CI.
- [ ] Branch-execution tests for every settings-gated path (staged mode, self-consistency
      on, thinking on/off, schema-format on/off, AUTH_MODE matrix, write-mode matrix) —
      a parametrized suite that EXECUTES each configuration end-to-end with fake providers.
- [ ] Error-path assertions: for each mutating service, at least one test where the RPC
      layer throws mid-operation and the resulting state/report is asserted (pairs with
      TRUST-5 chaos harness, unit-level).
- [ ] RULES.md/skills addition: "a config-gated code path counts as tested only if a test
      executes it under that config" (formalizing the STATE.md rule).

DONE MEANS: CI fails on coverage floor breach; the settings-matrix suite runs every gated
path; rule documented.

---

## TRUST-7 — App-side security hardening (Grok 4.5)

TASK: The app holds customer Odoo credentials — harden the app itself.

CHECKLIST:
- [ ] IDOR sweep: parametrized adversarial suite hitting EVERY workspace-scoped resource
      (connections, projects, snapshots, runs, billing, admin) cross-workspace and
      cross-role; route-enumeration ensures new resources are auto-included.
- [ ] Per-router role matrix suite (absorbs REM-10 item if not yet done).
- [ ] Credential handling audit: Fernet key rotation procedure (script + docs), credentials
      never in logs (log-scrubber test), API responses never echo secrets (schema test),
      session cookie flags verified in tests.
- [ ] Supply chain: `pip-audit` + `pnpm audit --audit-level=high` in CI (fail on high/
      critical with allowlist file); secrets scan (gitleaks or grep-based) in CI.
- [ ] App-DB backup/restore runbook: pg_dump schedule guidance in DEPLOY.md + a tested
      restore script (`scripts/restore_app_db.sh`) — the app DB holds snapshots, i.e. the
      customers' recovery data; it must itself be recoverable.
- [ ] Webhook + auth hardening from REM-10 verified present (signature-fail suites) —
      cross-check, don't duplicate.

DONE MEANS: IDOR + role suites green and auto-covering; CI security jobs active; restore
script proven on a copy.

---

## TRUST-8 — Production readiness checklist + SAFETY.md (the trust contract)

TASK: An honest, user-facing safety contract, and a gate that production-flagged connections
must pass before write mode.

CHECKLIST:
- [ ] `docs/SAFETY.md` (also rendered in-app under Settings → Trust & Safety): the
      permission model in plain words (app ≤ your Odoo user, no SQL); exactly what is
      fully / partially / not reversible (from the TRUST-4 verified table); what snapshots
      contain; blast-radius limits and how to tune; least-privilege setup guide; incident
      playbook (pause writes → assess journal → restore/rollback → contact path); honest
      statement of validation scope (tested majors, dirty-gate coverage, known limits).
- [ ] Production readiness checklist per connection (gates `write_mode=production` in
      TRUST-1): snapshot+restore drill executed on this connection (one real cycle on a
      test artifact), health check green, capability matrix probed, least-privilege
      credential confirmed (warn if the connection user is admin), backup artifact download
      verified. Stored + re-checkable; UI checklist card on Overview.
- [ ] Marketing/pricing copy alignment: claims audited against SAFETY.md (no "risk-free",
      no "fully reversible" blanket statements) — COPY_GUIDE addendum.
- [ ] In-product first-write moment: one-time interstitial on a connection's first mutating
      action summarizing the contract (snapshot taken, journal records everything, how to
      undo) — dismissible, never again.

DONE MEANS: SAFETY.md accurate against the verified reversibility table; production write
mode is unreachable without the checklist pass; copy audit clean.

---

## TRUST-9 — Design-partner beta protocol (process, not code)

TASK: Controlled exposure before general availability.

CHECKLIST:
- [ ] Beta flag: workspaces marked `beta_partner` get production write mode; others cap at
      `standard` on non-production-flagged connections (env-tunable for launch day).
- [ ] Partner runbook (`docs/BETA_PROTOCOL.md`): onboarding steps (staging instance first,
      least-privilege user, snapshot drill), weekly journal-review cadence, incident
      reporting path, exit criteria to GA (N partner-weeks with zero
      unrecoverable-data incidents and zero SafetyGate bypasses — define N=8 workspaces ×
      4 weeks, tunable).
- [ ] Telemetry (self-hosted, honest): per-workspace counts of runs, refusals, aborts,
      restores, anomaly trips — visible in admin console (no external analytics SaaS);
      this is the evidence base for the GA decision.
- [ ] GA decision entry template in MEMORY.md (what evidence, what thresholds).

DONE MEANS: beta gating enforceable in code; runbook + evidence dashboard exist; GA criteria
written down before the first partner connects.
