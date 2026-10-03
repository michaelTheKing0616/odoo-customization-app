# Audit hash chain

**Status:** accepted (engineering spec, 2026-10-03). The append and verify path already exists in `apps/api/app/audit_chain.py`. This ADR locks the shape. It does not claim retention windows or every audit kind are wired.

**Context:** One append-only chain. Two chains fail the plan. Genesis previous hash is 64 zero characters. Each entry hash is SHA-256 of the canonical JSON without the hash field.

**Options considered:**
- A second `audit_event` table beside `audit_logs`. Two stores would become two chains.
- One chain. Prefer extending the existing store.

**Decision:** One chain. Field rules from [11_LOGGING_AUDIT_OBSERVABILITY.md](../plans/next-phase/11_LOGGING_AUDIT_OBSERVABILITY.md) section 2:

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

Redact keys matching `pass`, `password`, `secret`, `token`, `api` key (`api[_-]?key`), `smtp_pass`, `authorization`. Also redact Bearer tokens and Fernet ciphertext.

Verify walks the chain and returns the first broken index. If the append fails, the apply does not proceed.

**Consequences:** A second chain becomes harder. A tampered row fails verification. Retention (24 months, 7 years for accounting kinds, 7 days for raw LLM payloads) is still a later card, not claimed done.
