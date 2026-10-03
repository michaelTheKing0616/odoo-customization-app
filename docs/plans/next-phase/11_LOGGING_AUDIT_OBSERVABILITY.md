# Logging, audit, and observability

Two streams. Secrets never enter either. A card names which events it emits.

## 1. Build log

Append to `docs/plans/INGENIUM_NEXT_PHASE_PROGRESS.md`:

```
## YYYY-MM-DD — card id
Track:
Intent:
Model / band:
Files:
Commands and results: VERIFIED | FAILED | NOT RUN | BLOCKED | PARTIALLY VERIFIED
Gates passed: ids
Negative tests:
Not done:
Risks introduced:
```

Do not write an optimistic summary that skips a red command.

## 2. Product audit chain

One append-only store. Prefer extending `audit_logs` if the columns can be added without a second log. Otherwise a new `audit_event` table that the HTTP middleware also writes to. Two chains fail master DoD 31.

| Field | Rule |
|---|---|
| `ts` | ISO-8601 with timezone |
| `run` | run id or request id |
| `actor` | user id, bot id, or `system` |
| `tenant` | workspace id |
| `connection` | connection id or null |
| `kind` | see list |
| `plan_hash` | 16+ hex chars or null |
| `schema_fp` | or null |
| `risk` | R0–R4 or READ/REVERSIBLE/DESTRUCTIVE/BILLABLE |
| payload | JSON after redaction |
| `prev` | SHA-256 of the previous entry. Genesis is 64 `0` characters |
| `hash` | SHA-256 of the canonical JSON without the `hash` field |

Kinds: `rpc_write`, `change`, `tool_call`, `approval`, `apply`, `rollback`, `login`, `logout`, `grant`, `revoke`, `totp`, `handoff`, `routine_run`, `flow_test`, `llm_turn`, `screenshot`, `error`, `module`, `settings`, `note`.

`change` payload: `model`, `action` (`created` or `updated`), `res_id`, `key`, `xmlid`, `changes` map of `{old, new}`.

Redact keys matching `pass|password|secret|token|api[_-]?key|smtp_pass|authorization`. Also redact Bearer tokens and Fernet ciphertext.

Verify endpoint or CLI walks the chain and returns the first broken index. A tampered row fails 5A-5.

Retention: ≥ 24 months. Accounting-related kinds ≥ 7 years. Raw LLM payloads 7 days, stored separately from the chain, scrubbed.

The writer never raises into the user's request in a way that drops the entry. If the append fails, the apply does not proceed (fail closed on the audit, INV-18).

## 3. Request ids

Every API response sets `X-Request-Id`. The same id is on log lines and on the audit `run` when the call is not part of a longer bot run. Bot runs use the run id and carry the request id inside the payload.

Logs are JSON lines: `ts`, `level`, `logger`, `msg`, `request_id`, `workspace_id`. No secret fields. stdlib `logging` with a JSON formatter is enough. structlog is optional and not required.

## 4. Trace events

`phase_changed`, `tool_called`, `evidence_added`, `validation_failed`, `approval_requested`, `apply_started`, `apply_op_done`, `apply_failed`, `verification_result`, `rollback_started`, `rollback_finished`.

Metrics: quality (pass rate), safety (unapproved writes = 0), performance (latencies below), cost (tokens, usd), reliability (error rate).

## 5. SLOs

| SLO | Target |
|---|---|
| API availability | 99.5% |
| Approval to apply start | p95 < 15s |
| Stale APPLYING detected | < 2 min |
| Journal data loss | zero |
| Plan ready, ≤ 10 ops | p95 < 60s |
| Apply, ≤ 20 ops, Mode T | p95 < 30s |
| Time to first token | p50 < 2s |
| INP | ≤ 200ms |

## 6. Kill switches

Global, tenant, provider, model, op type, skill, and `ingenium.bridge.enabled`. A drill (GATE-P7-06, GATE-L4-10) shows an in-flight apply stops.

Feature flags stay in the existing `feature_flags` table.

## 7. Version stamps on a run

`engine_version`, `prompt_version`, `skill_set_version`, `model_registry_version`, `protected_registry_version`, `op_schema_version`.

## 8. Runbooks (write under `docs/runbooks/` when the card that needs them lands)

1. Provider outage.
2. Odoo dies mid-apply.
3. Stuck APPLYING.
4. Failed rollback.
5. Injection incident.
6. Leaked key.
7. Runaway cost.
8. Bad release.
9. Bridge bug.
10. Before-image restore.
11. Journal corruption.
12. L4 auto-demotion.
13. Odoo 20 spec that will not translate.

Each runbook says how to detect, how to stop the bleed, how to recover, and which audit kinds prove the recovery.
