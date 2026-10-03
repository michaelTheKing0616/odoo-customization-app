# Track 2 — JSON-2

Source: `INGENIUM_CURSOR_HANDOFF_JSON2_MIGRATION_2026-09-22.md`. D1 is closed: dual-protocol. This track does not reopen it.

## Facts

| Fact | Value |
|---|---|
| Endpoint | `POST /json/2/<model>/<method>` |
| Auth | Bearer API key. Optional `X-Odoo-Database` |
| Args | Named. Stateless. One SQL transaction per call |
| Status | 200, 400, 401, 403, 404, 500. This is a real change from legacy always-200 |
| Deprecated | XML-RPC and JSON-RPC since Odoo 19.0 |
| `db` service removed | Odoo 20 and Online 19.1 |
| `common` / `object` removal | Odoo 22 and Online 21.1 (fall 2028) |
| Online removal of legacy RPC | 21.1 winter 2027 |
| Self-host removal | Odoo 22 fall 2028 |
| Wrong earlier date | "Odoo 20 fall 2026" is obsolete. Do not repeat it |
| Online External API | Custom plan only |

`/doc` is the reference of record. Do not guess signatures.

## PRs

| ID | Gate |
|---|---|
| PR-J1 | Match `/doc` for at least `search_read`, `create`, and `fields_get` on a tip and a mirror. Unit-test 4xx and 5xx. Callers keep the frozen interface and behave identically. D1 is recorded (it is). Transport code exists; the live `/doc` check is still an operator card |
| PR-J2 | `button_immediate_install` goes through the same client. A known-good sandbox install succeeds. Record duration against the XML-RPC baseline |
| PR-J3 | Repo grep for `xmlrpc`, `execute_kw` outside the intentional legacy adapter is empty. `packages/odoo-client` may keep the legacy transport behind `rpc_protocol` |
| PR-J4 | STATE and the progress log say what is done and what is operator-only. No optimistic "JSON-2 complete" |

## Interlock

PR-A may proceed while J3–J4 are open if the client interface stays frozen. Prefer J1 before PR-A tests are treated as final. Bridge Phase 0 does not start until J1's live check is recorded.

## Stop

Do not treat this track as more urgent than Track 1. Do not change public caller signatures to match a guessed JSON-2 shape. Do not retry writes blindly when the transport returns an error.

## Caller rules

- Reads may retry when idempotent. Writes never auto-retry at the transport layer.
- TLS required. `verify=false` is forbidden. Write-plane redirects are disabled.
- Concurrency toward one database ≤ 2. Read timeout 30s. Write timeout 120s.
- Sandbox stays on XML-RPC until a card explicitly moves it, because the sandbox image is Community and API keys are optional there.
