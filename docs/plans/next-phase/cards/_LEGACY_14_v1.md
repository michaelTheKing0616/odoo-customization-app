# Work cards

Pick one card. Load only the files it names. Paste the Grok prefix from `00_INDEX.md`. Record the build-log shape from `11`. Do not start a card whose `depends_on` is open.

Shared do-not list, on every card: do not weaken a lock in `01`; do not log secrets; do not run against a customer database; do not vendor `odoo-config-agent` or Studio source; do not assume `:8001` reloads; do not delete a test to go green; do not put a live LLM in a PR-blocking test.

Shared evidence: a progress-log entry whose commands match this card.

Pressure is the six scores plus prior failures, summed. Band maps to the route in `00`.

---

## BL — baseline

### BL-01 Re-verify the baseline
Track BL. depends_on: none. Pressure: complexity 1, uncertainty 0, consequence 1, constraints 1, verification 0, irreversibility 0, failures 0 → 3. Route: cheap.
Read: `03_BASELINE.md`. Change: `03` only if a row is wrong. Steps: re-count routers, tables, alembic head, test files. Acceptance: every exists/partial/missing row still true or corrected with a path. Negative: do not mark a partial row as exists. Command: `rg --files apps/api/app/routers | wc -l` and alembic heads. Do-not: feature code. Audit: none. Rollback: revert the doc edit.

### BL-02 Request-id middleware
depends_on BL-01. Pressure 6 (consequence 2, constraints 2, verification 1, complexity 1). Route: generalist.
Read: `apps/api/app/main.py`, `11`. Change: middleware plus a test. Steps: generate an id if `X-Request-Id` is absent, echo it, add it to the log context. Acceptance: a mutating call returns the header; the audit row can store it later. Negative: the header cannot be used to impersonate a user. Command: pytest on the new test. Audit kind: none yet. Rollback: remove the middleware.

### BL-03 JSON log formatter
depends_on BL-02. Pressure 4. Route: cheap.
Change: logging config. Acceptance: one line of JSON with `ts`, `level`, `msg`, `request_id`. Negative: a line that contains `password` or `api_key` fails the test. Command: pytest. Rollback: revert the formatter.

### BL-04 Lint slots
depends_on BL-01. Pressure 5. Route: cheap.
Change: ruff and mypy config for `apps/api` in report-only or a tiny clean subset; a `typecheck` script in `apps/web/package.json` that runs `tsc --noEmit`. Acceptance: CI invokes them without failing the whole repo on pre-existing debt; new files in later cards must be clean. Negative: do not mass-reformat. Command: the new scripts. Rollback: remove the config.

### BL-05 ADR folder
depends_on none. Pressure 2. Route: cheap.
Change: `docs/adr/ADR-01.md` through `ADR-14.md` as stubs pointing at `T8` titles. Acceptance: 14 files. Status of ADR-02 is open (D8). ADR-14 records D11. Rollback: delete the folder.

### BL-06 verified-facts and recon
depends_on BL-01. Pressure 8. Route: generalist.
Change: `docs/verified-facts.md`, `docs/recon.md`. Acceptance: GATE-P0-01 and GATE-P0-04 have a home. Each fact is marked verified or unverified. Negative: no invented Odoo signature. Rollback: revert docs.

---

## T1 — schema grounding

### T1-F0 Entrypoint trace
depends_on BL-06. Pressure 9. Route: generalist.
Read: `T1`, `_finish_seed_draft`. Acceptance: PR-F.0 written in the progress log; greens before this are labeled provisional. Negative: a node added after the entrypoint fails the trace. Command: the trace test or a documented call path.

### T1-INST AI_IR_TRACE on Maintenance
depends_on T1-F0. Pressure 6. Route: generalist.
Acceptance: PF-3 answered. Scrub-key hypothesis confirmed or refuted.

### T1-A1 schema_client positive and negative
depends_on T1-F0. Pressure 8.
Acceptance: `model_exists`, `fields_get`, `relation_ok` each have a pass and a fail test. Command: existing `test_ai_schema_client.py` plus new cases.

### T1-A2 TTL deny on stale
depends_on T1-A1. Pressure 7.
Acceptance: addendum A3. A stale catalog snapshot yields an empty or deny client. Negative: a stale snapshot must not admit a field.

### T1-A3 field_is_writable
depends_on T1-A1. Pressure 6.
Acceptance: implemented or explicitly deferred in the progress log.

### T1-A4 view_has_field stays stubbed
depends_on T1-A1. Pressure 3. Route: cheap.
Acceptance: addendum A6. A test asserts the stub. Negative: do not implement it "while here".

### T1-B1 merge admit rules
depends_on T1-A1. Pressure 11. Route: high effort.
Acceptance: admit only cue, structural allowlist, or schema-verified reuse. Allowlist readable in one sitting.

### T1-B2 Rate Line regression
depends_on T1-B1. Pressure 8.
Acceptance: addendum A4 rejects the named maintenance / Rate Line case and a generic many2one to `res.partner`.

### T1-B3 sibling golden hook
depends_on T1-B1. Pressure 7.
Acceptance: Service-cards is in the same test module as Maintenance. A brief-specific branch fails a lint or a test.

### T1-C1 approved_craft defaults off
depends_on T1-B1. Pressure 8.
Acceptance: checklist default off; toggle changes XML.

### T1-C2 copy on the checklist
depends_on T1-C1. Pressure 6.
Acceptance: copy rubric has no Accuracy or Ethics blocker. A non-technical reader can tell what a row adds.

### T1-D1 repair cap
depends_on T1-C1. Pressure 10.
Acceptance: max 3 iterations. Broken never `install_ready`. Clean is `install_ready` on the first pass. Odoo errors logged verbatim.

### T1-D2 proved requires run_tests
depends_on T1-D1. Pressure 8.
Acceptance: D2. Negative: smoke install cannot stamp `proved`.

### T1-D3 sandbox log
depends_on T1-D1. Pressure 5.
Acceptance: verbatim Odoo error stored on the job, not swallowed.

### T1-E1 CI split
depends_on T1-D2. Pressure 7.
Acceptance: tier 1 and 2 fail on schema-invalid output. Tier 3 does not block the fast suite.

### T1-E2 D2 encoded
depends_on T1-E1. Pressure 4.
Acceptance: the decision is in code and in MEMORY, not only in a comment.

### T1-F1 Maintenance golden
depends_on T1-E1. Pressure 8.
Acceptance: Maintenance passes with zero new brief-specific code.

### T1-F2 Service-cards golden
depends_on T1-F1. Pressure 8.
Acceptance: same path. Negative: a Maintenance-only branch.

### T1-F3 one Option A install_ready
depends_on T1-D1. Pressure 9.
Acceptance: at least one Option A module reaches `install_ready` on a real sandbox.

### T1-RET retire scrub
depends_on T1-F1, T1-F2. Pressure 7.
Acceptance: delete `scrub_uncued_*` only after two consecutive runs with zero scrub removals. One release keeps a no-op assert. Date, Datetime, and money go to `approved_craft`.

---

## T2 — JSON-2

### T2-J1 Live doc check
depends_on BL-06. Pressure 8.
Acceptance: PR-J1 against a real `/doc` for `search_read`, `create`, `fields_get`. Operator may run this. Record status codes 400 and 401. Negative: a guessed signature.

### T2-J2 Install port
depends_on T2-J1. Pressure 8.
Acceptance: PR-J2 sandbox install via the frozen interface. Duration compared.

### T2-J3 Grep
depends_on T2-J2. Pressure 4. Route: cheap.
Acceptance: PR-J3. Legacy transport remains only behind `rpc_protocol`.

### T2-J4 Docs honesty
depends_on T2-J3. Pressure 3. Route: cheap.
Acceptance: PR-J4 in STATE and the progress log.

### T2-SMOKE Online
depends_on T2-J1. Pressure 6.
Acceptance: Online Custom-plan smoke or an explicit "not run, no Custom plan" blocker. Do not fake a pass.

---

## T9 — Odoo 20

Each card's acceptance id is the matching O20 row in `T9_ODOO20_GA.md`. depends_on T2-J1 unless noted. Pressure 8 except O20-04 and O20-08 at 15 (frontier) and O20-05 at 12.

| Card | Title | Change |
|---|---|---|
| O20-01 | Compose file | `docker/docker-compose.odoo20.yml` port 8073 |
| O20-02 | Registry GA | `packages/odoo-client` compat registry |
| O20-03 | Adapters | `views_v20`, `automation_v20`, `security_v20` |
| O20-04 | ir.access compiler | new compiler module plus tests. Do not write `ir.rule` on 20 |
| O20-05 | Access screen | `access/page.tsx` version branch |
| O20-06 | Version-table tests | one test per row in T9 |
| O20-07 | JSON-2 default on 20 | client `auto` |
| O20-08 | Snapshots without db service | `snapshot` path. Frontier review |
| O20-09 | MCP absent on Community | detection returns absent |
| O20-10 | Major gate includes 20 | `run-sandbox-major-gate.sh` |
| O20-11 | Flows on 20 | 7 / 6 / 2 checks |
| O20-12 | Designer on 20 | list tag, not tree |
| O20-13 | Production checklist | docs plus automated translators |
| O20-14 | name_search domain | client |
| O20-15 | formatted_read_group | client |
| O20-16 | 19-to-20 spec replay | translators or a named failure, never a half-apply |

Negative for all: a test that creates `ir.rule` on a 20 fake client must fail.

---

## T5A — guardrails

Pressure 14+ on 5A-02, 5A-03, 5A-04, 5A-05: frontier plus a reviewer on 5A-03 and 5A-04.

| Card | Acceptance | Negative |
|---|---|---|
| 5A-01 classify_rpc | Verbatim lists from T5 in code. Mapping to Bucket A/B/C | A prompt cannot reclassify |
| 5A-02 dry-run hash | Every write tool in T1, T3, T4 | Live write without a seen hash |
| 5A-03 plan fingerprint | SHA-256, `res_id` excluded, 16 hex, re-plan on apply | Stale plan applies |
| 5A-04 never-allowed | No override flag exists | Approval cannot unlink `res.users` |
| 5A-05 audit chain | Fields in `11`. Verify detects a tampered row | A broken prev hash returns success |
| 5A-06 snapshot before destructive | Production DESTRUCTIVE or BILLABLE refuses without a snapshot id | Apply proceeds without one |
| 5A-07 no MCP writes | Grep gate in CI | A write through an MCP client |
| 5A-08 production policy | READ and allow-listed REVERSIBLE only without approval | A create on production auto-applies |
| 5A-09 staging policy | READ and REVERSIBLE auto; DESTRUCTIVE asks | |
| 5A-10 oracle tests | The ten names in T5 | |

depends_on: 5A-01 before the rest. 5A-05 before T6-03.

---

## T5B — config as code

depends_on 5A-03. Pressure 10 except 5B-04 at 12.

| Card | Acceptance |
|---|---|
| 5B-01 schema | 47 sections, apply order, `secret:` is a pointer |
| 5B-02 idempotent apply | second apply writes nothing |
| 5B-03 fingerprint drift | mismatch aborts |
| 5B-04 version briefing | live probe, not a static paragraph |
| 5B-05 l10n adopt | `l10n_ng` by xmlid, no duplicate tax |
| 5B-06 importers | batch 500, E.164, fuzzy 0.92, blanks are not keys |
| 5B-07 custom fields | `x_` required, `x_studio_` rejected |
| 5B-08 oracle port | `test_spec.py`, `test_importers.py`, `test_versions_profiles.py` names reimplemented |

---

## T5C and L4

depends_on 5A and one working executor from T8-EXEC.

| Card | Pressure | Acceptance |
|---|---|---|
| 5C-01 one chassis | 12 | Tracks 1, 3, 4 tasks share loop, guardrail, audit |
| 5C-02 L2 pauses all writes | 8 | 100% of writes pause |
| 5C-03 L3 staging | 10 | REVERSIBLE unsupervised on staging only; DESTRUCTIVE pauses |
| 5C-04 multi-client lock | 11 | second apply queues |
| 5C-05 out-of-band drift | 10 | abort |
| 5C-06 adversarial instruction | 12 | embedded instruction, no destructive action |
| 5C-07 never-allowed at L4 prep | 14 | the test exists before L4 is enabled |
| 5C-08 eval harness hook | 9 | golden, adversarial, ambiguity, version, cost, safety |
| 5C-09 safety 100% | 12 | billable and destructive repeats all require approval |

L4-01 through L4-12 implement GATE-L4-01 through GATE-L4-12. depends_on 5C-03 and GATE-L4-08 evidence, except L4-11 and L4-12 which can be written as negative tests earlier. Pressure 16. Route: frontier. Reviewer on L4-01, L4-03, L4-09. Do-not: do not enable L4 in production config by default.

---

## T6 — auth and inbox

| Card | depends_on | Pressure | Acceptance |
|---|---|---|---|
| T6-01 role matrix doc in code | D9 code | 6 | four roles enforced |
| T6-02 zero manual link | existing OAuth | 8 | DoD 29 path tested with mocks plus one recorded live attempt |
| T6-03 auth events on the chain | 5A-05 | 12 | login, grant, totp append. No second log |
| T6-04 inbox API | 5A-03 | 14 | approve posts the fingerprint. Mismatch 409 |
| T6-05 plan card render | T6-04 | 12 | nine sections from the engine, not the model |
| T6-06 R3 two-person | T6-04 | 15 | requester cannot be an approver. Reviewer |
| T6-07 client scope on inbox | T6-04 | 10 | 404 on the other client |
| T6-08 command center home | T6-03 | 8 | tiles for pending, failed, drift |
| T6-09 per-client page | T6-08 | 7 | one connection |
| T6-10 team grants UI | T6-01 | 8 | uses existing grant API |
| T6-11 14b five-track dashboard | tracks emitting data | 11 | DoD 32 |
| T6-12 SAML note | none | 2 | `18` records SAML as later. No code |

---

## T3 — Bridge

depends_on T2-J1 and 5A-02.

| Card | Pressure | Acceptance |
|---|---|---|
| BR-01 contract schema | 10 | Tier I rejects incomplete. `connection_id` only |
| BR-02 connections verify | 10 | no Tier I until `verified_at` |
| BR-03 secrets encrypted | 12 | no plaintext column |
| BR-04 queue tables | 6 | a test row inserts |
| BR-05 connector interface | 8 | six methods, Shopify implements them |
| BR-06 Shopify tier II | 12 | six sandbox scenarios |
| BR-07 Shopify tier III | 12 | seeded discrepancy detected |
| BR-08 tier 3b | 13 | one connector config-only |
| BR-09 genericity proof | 14 | Shopify via 3b matches hand-built above the interface |
| BR-10 dead letter | 8 | failing job visible |
| BR-11 contract studio | 9 | two-way reveals conflict_resolution |
| BR-12 catalog gate | 7 | a new connector cannot be listed before I–III |

---

## T4 — compiler and surfaces

| Card | depends_on | Pressure | Acceptance |
|---|---|---|---|
| T4-PROG | none | 8 | four surfaces, no generic spinner, opt-in detail, tool-call limit |
| T4-MCP0 | none | 7 | Phase 0 written up. YOLO observed, not used in prod |
| T4-MCP1 | T2-J1 | 10 | read-only, cap 15 fields, aggregation parity |
| T4-DASH | 5A-01 | 11 | persisted dashboard, protected model refused, citation |
| T4-OFF | 5A-02 | 12 | dropped ack is exactly-once. Promote still human |
| T4-ISPEC | T1-F2 | 13 | lossless round-trip |
| T4-SYNC | T4-ISPEC | 14 | drift blocks. Never overwrite. Reviewer |
| T4-BROWSER | T4-ISPEC | 11 | one defect class Python missed, recorded |
| T4-WIRE | T1-F2 | 10 | Stage H unavoidable. Code inspection test |
| T4-LLM3 | ADR-02 | 9 | swappable. Frontier adapter off by default. Stops if D8 still open: document only |
| T4-SKT | 5A-04 | 16 | trigger write is not pre-approval. Reviewer. Stop-ship |
| T4-E2E | the above | 12 | compiler DoD 20 |

---

## T8 — engine

ADR cards ADR-01–ADR-14: pressure 6 each except ADR-02, ADR-06, ADR-08, ADR-11 at 12. depends_on BL-05. Acceptance: the ADR file has a decision, consequences, and a status. ADR-02 may remain open.

| Card | Pressure | Acceptance |
|---|---|---|
| T8-GW-TYPES | 8 | canonical types, tool name regex |
| T8-GW-NORM | 10 | normalization rules 1–10, never eval |
| T8-GW-C | 12 | C01–C20 with cassettes |
| T8-GW-REG | 7 | no hardcoded model id outside the registry |
| T8-OD-TRANSPORT | 10 | timeouts, concurrency 2, no write retry |
| T8-OD-ENV | 9 | EnvProfile, unknown capability means no |
| T8-OD-GRAPH | 11 | SchemaGraph, row cap 200, sample 5 |
| T8-OD-BRIDGE | 14 | seven methods, DDL not dry-run in place, kill switch |
| T8-OP-SCHEMA | 12 | schema ops in T8 |
| T8-OP-UI | 10 | UI ops |
| T8-OP-LOGIC | 12 | logic ops, outbound → R3 |
| T8-OP-SEC | 15 | security ops, group-less ACL is R4. Reviewer |
| T8-OP-SET | 14 | settings and modules, uninstall is R4 |
| T8-OP-DATA | 13 | data ops, delete is R4 |
| T8-PROT | 16 | protected registry, RT-10–16. Reviewer |
| T8-RISK | 12 | escalations only go up |
| T8-POLICY | 17 | matrix in `02`. Reviewer |
| T8-VALID | 12 | stages 1–9 always run |
| T8-SIM | 12 | four simulation modes |
| T8-EXEC | 18 | Mode T/C, WAL, heartbeat, recovery. Reviewer |
| T8-VERIFY | 12 | postconditions, INV-16 |
| T8-ROLLBACK | 14 | undo is a change-set. Soft inverse keeps data |
| T8-META | 10 | MetaSnapshot equality |
| T8-CARD | 10 | plan card golden |
| T8-RUN | 11 | phase machine, no apply tool, loop guards |
| T8-PROMPT | 10 | layers, budgets, no runtime-editable prompt |
| T8-CRITIC | 9 | critic cannot waive policy |
| T8-MEM | 10 | episodic memory never auto-injected |

Engine suites T8-S01 through T8-S18: one card each, pressure 10, depends_on the executor and the ops. Acceptance is the suite row in T8. Suite 8 pressure 14. Suite 11 pressure 14. Suite 18 pressure 15.

Skills: T8-SK-T1-<NAME> for each Tier-1 skill listed in T8 (16 cards), pressure 8. T8-SK-FAM-A through T8-SK-FAM-I (9 cards) cover the remaining IDs in that family, pressure 7. T8-ROUTER pressure 11: recall@3 ≥ 0.95, precision@3 ≥ 0.6, ≥ 300 phrasings.

Eval cards:

| Card | Acceptance |
|---|---|
| T8-EV-SEED | EV-FLD, AUT, SEC, DATA numbered cases |
| T8-EV-ASSIGN | the assigned families through EV-ACCESS |
| T8-EV-CFG | EV-CFGBOT-01–15 |
| T8-EV-BOT | EV-BOT-01–16 |
| T8-RT-A | RT-01–16 |
| T8-RT-B | RT-17–36 |
| T8-RT-C | RT-37–48 |
| T8-CI | four CI stages wired |
| T8-HUMAN | 50-plan packet template |

Bot layer, depends_on T8-EXEC and T6-04:

| Card | Pressure | Acceptance |
|---|---|---|
| T8-BOT-ROSTER | 8 | limits 50 / 6 / 50 / 20 / 25 |
| T8-BOT-GRANT | 14 | effective permission intersection. Reviewer |
| T8-BOT-ROOMS | 11 | hop 4, fan-out 3, nudge once |
| T8-BOT-PRESENCE | 8 | EV-BOT-15 |
| T8-BOT-ROUTINE | 12 | Test is dry-run. Pause after 3 failures |
| T8-BOT-RECORD | 10 | staging only |
| T8-BOT-SECRETS | 14 | RT-48 |
| T8-BOT-TEAM | 12 | RT-39 requester role |
| T8-BOT-SLACK | 9 | link only for R≥2 |
| T8-BOT-CFG | 12 | EV-CFGBOT |
| T8-BOT-GATES | 12 | GATE-P5B-01–11 |
| T8-P6 | 12 | ≥ 150 scenarios, one Tier A |
| T8-P7 | 15 | full RT, chaos, pen-test slot |
| T8-P8 | 12 | pilot criteria. Tope signs GATE-P8-05 |

---

## T7 — UI

Foundation. depends_on none. Pressure 6 unless noted. Kit tests stay green: `pnpm test` in `apps/web` for the kit files, and `pnpm test:e2e` for `e2e/kit` when the family is visual.

| Card | Acceptance |
|---|---|
| UI-F01 tokens dark alerts | `.odoo-form-alert--*` uses semantic tokens in both themes |
| UI-F02 loading error not-found | three files at root and under the connection layout |
| UI-F03 empty and skeleton | every operate page that can be empty uses the kit |
| UI-F04 dialog to Base UI | Dialog family migrated. Radix dialog import gone from that family |
| UI-F05 tabs | same |
| UI-F06 tooltip | same |
| UI-F07 slot | same |
| UI-F08 sonner | toasts 3–5s, errors persist, polite live region |
| UI-F09 motion primitives | drawer and sheet interruptible, reduced-motion test |
| UI-F10 input-otp | TOTP enroll |
| UI-F11 virtuoso | tables over 50 rows |
| UI-F12 axe widen | a11y spec lists every operate route |

Splits, pressure 8, no behavior change, characterization tests first:

| Card | File |
|---|---|
| UI-SP-API | `src/lib/api.ts` |
| UI-SP-WIZARD | wizard page |
| UI-SP-STUDIO | studio page |
| UI-SP-DESIGNER | designer page |
| UI-SP-BULK | bulk-suite page |
| UI-SP-OVERVIEW | connection page |
| UI-SP-CONFIG | config page |

Screen restyles UI-S-<route> for each row in `13_UI_SCREEN_SPECS.md`. depends_on the matching UI-F family and UI-SP if the file is oversized. Pressure 7. Acceptance: states listed in `13`, UX audit table in the progress log, copy critique with no Accuracy or Ethics score of 1, desktop and narrow screenshots. There are 45 product routes plus 8 new screens in `13`. That is 53 UI-S cards. E2E harnesses are not restyled except `/e2e/kit` and `/e2e/tokens` (UI-S-KIT).

New-screen feature cards (API plus UI), pressure 11, depend on T6 or T8 as named in `13`:

UI-S-INBOX, UI-S-COMMAND, UI-S-BOTS, UI-S-ROOM, UI-S-WORKBENCH, UI-S-DASH, UI-S-CONTRACT, UI-S-BRIDGE-CONN.

---

## Count

BL 6, T1 20, T2 5, T9 16, T5A 10, T5B 8, T5C 9, L4 12, T6 12, T3 12, T4 12, ADR 14, T8 gateway and odoo and ops and engine and runtime 4+4+6+10+4 = 28, suites 18, skills 16+9+1 = 26, eval 9, bot 14, UI foundation 12, splits 7, kit 1, screen restyles 45, new screens 8.

Total: 6+20+5+16+10+8+9+12+12+12+12+14+28+18+26+9+14+12+7+1+45+8 = 304 card ids.

A builder still takes one id at a time. The extra ids are splits of the plan's "about 180", not optional scope. P6, P7, and P8 are the only cards that may be deferred past the first GA candidate, and only if `15` DoD items that depend on them are marked not yet claimed.
