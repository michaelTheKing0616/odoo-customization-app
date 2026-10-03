# Cards — T5C Worker Bots L0–L3 and L4 (D10)

Self-contained. L0–L3 rules: `../T5_GUARDRAILS_CONFIG_WORKERBOTS.md` lines 144–168. GATE-L4-01–12: `../01_LOCKS_DECISIONS_CONFLICTS.md` lines 62–79 (copied below). **The L4 numbers are authored, not copied from a source. Tope must confirm them in MEMORY before any L4 card except L4-11 and L4-12 starts** (`../18_OPEN_QUESTIONS.md`).

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs; no customer database; `:8001` does not reload; never loosen a test; no live LLM in PR tests; stay inside "Change". **T5C/L4-specific:** one chassis only (`apps/api/app/worker_bot/runtime.py` plus `apps/api/app/agent_runtime/`); never a second loop; L2 is the production default; L4 is off by default in every config file and every fixture; do not stub GATE-L4-08 evidence; never enable L4 on a real tenant inside a card; do not tune the L4 thresholds inside a card.

**Levels (copied):** L0 assistant, no writes. L1 read-only tools. L2 every write pauses for approval (100%); production default. L3 REVERSIBLE unsupervised on staging; DESTRUCTIVE and BILLABLE pause. L4 allow-listed R1 and narrow R2 on production under GATE-L4.

**GATE-L4 (copied):**

| ID | Gate |
|---|---|
| GATE-L4-01 | Only op types on a tenant allow-list whose base risk is R1, or R2 that is non-DDL, non-protected, and non-outbound |
| GATE-L4-02 | Never R3, never R4, never `protected:elevate`, never `module.*`, never promote |
| GATE-L4-03 | Mode T (Bridge) on the same plan hash already applied and verified on staging |
| GATE-L4-04 | Each standing rule needs two admins, one of them the workspace owner |
| GATE-L4-05 | Standing rule expiry ≤ 30 days |
| GATE-L4-06 | Daily cap on auto-applies, default 20, tenant-configurable downward only |
| GATE-L4-07 | Blast radius ≤ 50 records per auto-apply |
| GATE-L4-08 | Eligibility: ≥ 200 L3 applies over ≥ 60 days, zero verify failures, rollback rate ≤ 1% |
| GATE-L4-09 | Any verify failure or policy violation demotes to L2 automatically and rolls back |
| GATE-L4-10 | Kill-switch drill: global and tenant switches stop an in-flight L4 apply |
| GATE-L4-11 | Never-allowed is unbypassable at L4 (master DoD 24) |
| GATE-L4-12 | An L4 bot cannot widen its own allow-list |

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_worker_bot.py tests/test_l4_policy.py tests/test_agent_runtime.py tests/test_changeset_engine.py tests/test_red_team_engine.py
```

**Audit events:** `tool_call`, `approval`, `apply`, `rollback`, `routine_run`, `error`; L4 adds `note` rows for promotion and demotion with the evidence counts.

---

## T5C

### 5C-01 — One chassis for Tracks 1, 3, 4
- **Status:** SEEDED. `worker_bot/runtime.py` (`WorkerBot`, 89 lines) drives `changeset` ops; tests cover L0, L2, L3. No representative T1 (generate), T3 (Bridge), or T4 (dashboard) task runs through it yet.
- **depends_on:** 5A-03, T8-EXEC
- **Pressure:** C3 U2 F2 K3 V2 I2 +0 = 14 → frontier
- **Read first:** `worker_bot/runtime.py`; `agent_runtime/runtime.py` (`AgentRuntime`); `changeset/executor.py`.
- **Steps:** (1) define a task adapter interface (`plan() -> ChangeSet`) with three adapters: T1 module apply, T3 Bridge contract apply, T4 dashboard save; (2) each produces a change-set and goes through the same guardrail, executor, and audit; (3) one test per adapter.
- **Acceptance:** [ ] DoD 25 and E2E step 7: one chassis, three task types, one loop, one guardrail engine, one audit chain.
- **Negative:** a test asserts there is exactly one class that calls `executor.apply` (grep test).

### 5C-02 — L2 pauses every write
- **Status:** SEEDED (`test_l2_field_create_submits_but_does_not_apply`, `test_record_text_cannot_elevate_or_bypass_on_l2`).
- **Pressure:** 6 → Grok standard
- **Acceptance:** [ ] 100% of writes pause: a property test over every catalog op type at L2 asserts zero applies.

### 5C-03 — L3 on staging
- **Status:** SEEDED (`test_l3_staging_mail_template_create_applies`, `test_l3_staging_access_create_pauses`, `test_l3_production_mail_template_pauses`).
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] REVERSIBLE (R1) unsupervised on staging only; DESTRUCTIVE and BILLABLE pause; property test over the catalog.

### 5C-04 — Multi-client lock
- **Status:** OPEN
- **depends_on:** T8-EXEC
- **Pressure:** C2 U2 F3 K2 V2 I1 +0 = 12 → Grok high effort
- **Acceptance:** [ ] one apply per database; a second apply queues and does not interleave (concurrency test with two threads and a slow fake port).
- **Negative:** release on crash: a killed holder's lock is reclaimed by the recovery job within 2 minutes (heartbeat 5 s).

### 5C-05 — Out-of-band drift aborts
- **Status:** OPEN (fingerprint mismatch abort exists in the executor; not exercised through the bot).
- **Pressure:** 9 → Grok standard
- **Acceptance:** [ ] a change made directly in the fake database between plan and apply aborts the bot's apply with STALE.

### 5C-06 — Adversarial embedded instruction
- **Status:** SEEDED (`test_record_text_cannot_elevate_or_bypass_on_l2`, `test_rt01_record_text_cannot_grant_admin`, `test_injected_instruction_does_not_add_an_op`).
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] an instruction in a product description causes no destructive action at L2 and L3.

### 5C-07 — Never-allowed at L4 (written before L4 is enabled)
- **Status:** OPEN. Write now; it does not wait for the threshold confirmation.
- **Pressure:** C2 U1 F3 K3 V1 I2 +0 = 12 → Grok high effort; reviewer (never-allowed is a 14+ family)
- **Acceptance:** [ ] a bot at L4 with an allow-list containing every op type still cannot unlink `res.users`, touch `res.users.apikeys`, or write a protected parameter.

### 5C-08 — Eval harness hook
- **Status:** OPEN
- **depends_on:** T8-EV-SEED
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] golden, adversarial, ambiguity, version drift, cost, and safety evals run against the bot with scripted doubles (no live LLM in PR).

### 5C-09 — Safety: 100% approval on billable and destructive repeats
- **Status:** OPEN
- **Pressure:** 10 → Grok high effort
- **Acceptance:** [ ] 50 repeated billable or destructive requests at L3: 50 pause.

### 5C-10 — Flow checks
- **Status:** OPEN
- **depends_on:** a flow runner (O20-11 shares it)
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] quote-to-cash 7 checks, procure-to-pay 6, manufacture 2 on a sandbox; never on production; test records prefixed.

## L4 (D10)

All L4 cards: **route frontier (pressure 16)**; reviewer on L4-01, L4-03, L4-09; depends_on 5C-03 and Tope's threshold confirmation, except L4-11 and L4-12. Code seed: `worker_bot/l4_policy.py` (`l4_eligible`, `l4_may_apply`, 30 lines) with `test_short_history_is_not_eligible`, `test_full_history_is_eligible`, `test_l4_refuses_r3_modules_and_large_blasts`. `test_invalid_level_l4_raises` proves the runtime refuses L4 today.

Shared L4 read-first: `worker_bot/l4_policy.py`, `worker_bot/runtime.py`, `changeset/policy.py`, `changeset/ops.py` (`op_base_risk`, the DDL flag), `changeset/protected_registry.py`.

| Card | Gate | Status | Change | Acceptance | Negative |
|---|---|---|---|---|---|
| L4-01 | GATE-L4-01 | SEEDED (risk check only) | `l4_policy.py`: tenant allow-list table `l4_allow_list(tenant, op_type)`; check base risk R1, or R2 with `ddl=False`, not protected, not outbound | op outside the allow-list refused; R2 DDL refused | R2 `automation.create` with email action refused (outbound) |
| L4-02 | GATE-L4-02 | SEEDED | same | R3, R4, `protected:elevate`, `module.*`, promote refused | each of the five, one test |
| L4-03 | GATE-L4-03 | OPEN | executor: L4 requires Mode T and a staging apply record with the same plan hash and `verified=True` | production L4 apply finds the staging record | Mode C at L4 refused; a hash applied on staging but verify failed refused |
| L4-04 | GATE-L4-04 | OPEN | `standing_rule` table; approve endpoint needs two distinct admins, one with role owner | rule active only after both | one admin twice; two non-owners |
| L4-05 | GATE-L4-05 | OPEN | rule `expires_at` ≤ created + 30 d, checked at create and at apply | expired rule does nothing | create with 31 days refused |
| L4-06 | GATE-L4-06 | OPEN | counter per tenant per UTC day | 21st auto-apply pauses (L2) | tenant tries to raise cap to 30: refused |
| L4-07 | GATE-L4-07 | SEEDED (blast check) | impact count from validation stage 6 | 50 records ok | 51 records refused |
| L4-08 | GATE-L4-08 | SEEDED (`l4_eligible`) | eligibility computed from audit rows (`apply` kind, env staging, level L3) not from a counter the bot can write | 200 applies / 60 days / 0 verify fail / ≤1% rollback → eligible | 199 applies; one verify failure; 1.5% rollback |
| L4-09 | GATE-L4-09 | OPEN | on verify fail or policy violation: set level L2, run rollback change-set, write `note` audit | demotion within the same apply | bot cannot re-promote itself |
| L4-10 | GATE-L4-10 | OPEN | executor checks global, tenant, and `ingenium.bridge.enabled` switches between ops | drill: flip switch mid-apply, apply stops and compensates | switch flipped before start: zero writes |
| L4-11 | GATE-L4-11 | OPEN (write now) | test only | see 5C-07 | — |
| L4-12 | GATE-L4-12 | OPEN (write now) | grant check: the allow-list is writable only by human admins | bot tool call that edits its allow-list refused and audited | template that adds an op to the allow-list is not auto-applied (EV-BOT-12) |

Per-card fields not in the table, the same for all twelve:
- **Commands:** API pytest on `tests/test_l4_policy.py` plus the new test module `tests/test_l4_gates.py`.
- **Do not:** turn L4 on in any default; claim GATE-L4-08 from fixture data; widen GATE-L4-01.
- **Log / audit:** `note` rows `l4_promoted` / `l4_demoted` with the counts; build log names the gate id.
- **Rollback:** feature flag `l4_enabled` off (default off) in `feature_flags`.
- **Evidence:** named tests green; for L4-10, a drill log in the progress log; for L4-08, a query result over real staging audit rows (not before 60 days of L3 exist).
- **Runbook:** L4 auto-demotion (`../11` runbook 12) is written by L4-09.
