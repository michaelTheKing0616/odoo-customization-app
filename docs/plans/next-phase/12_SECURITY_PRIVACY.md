# Security and privacy

This file is the threat model the cards implement. It does not replace INV-01–20.

## Threats

| Threat | Control |
|---|---|
| Instruction hidden in Odoo data, files, or uploads | Untrusted wrapper. Tools cannot widen grants. RT-01–09, RT-37, RT-47 |
| A user asks for something the policy forbids | Policy in code. R4 deny. Never-allowed |
| The model mis-plans | Validation, critic, simulation, human hash approval |
| Provider compromise or prompt leak | No secrets in the prompt. Read plane only. BYO key in KMS |
| Stolen Odoo key | Least-privilege reader and operator users. MCP key separate from RPC key. Rotation runbook |
| Cross-tenant read | RLS or equivalent workspace filter on every query. Client grant 404. RT-32. Canary rows |
| Supply chain | SAST, SBOM, lockfiles. No vendored Enterprise source |
| Approval replay | Hash plus fingerprint plus expiry. RT-17–21 |
| Audit tamper | Hash chain verify. Append-only grants |
| DoS and cost abuse | Budgets, loop guards, rate limit. RT-30, RT-31 |
| Bridge abuse | Unknown ops fail closed. Kill switch. Stolen-key test RT-36 |
| XSS via model-written HTML | Render plan cards as structured data, not as HTML from the model |
| SSRF via connection URL | https only. Block link-local `169.254.0.0/16` and cloud metadata. Re-resolve DNS. No cross-host redirects on the write plane |

## Credential planes

READ allowlist: `search_read`, `read`, `search_count`, `fields_get`, `read_group` or `formatted_read_group`, `name_search`, `default_get`, `get_views` / `get_view`, `check_access_rights` / `has_access`, `context_get`. Confirm the exact method names per version in verified-facts.

WRITE credentials decrypt only inside the executor at apply time (INV-12). The agent process cannot see them.

Groups on the Bridge database: `group_ingenium_reader`, `group_ingenium_operator`.

## Prompt injection layers

1. Structural separation of system and data.
2. Capability separation. Data cannot add tools.
3. A scanner may warn. It is not the control.
4. Taint on arguments that came from records. Tainted values cannot be approval decisions.
5. Egress allowlist.
6. Canaries RT-01–09 on every release.

## Privacy

Classes: public config, business data, personal data. Samples ≤ 5 rows and masked by default. Redaction pipeline before any provider call. No training on client data (non-goal). GDPR and Nigeria NDPA: a counsel pass is an open question in `18`, not something a card invents. Do not send a production database dump to a model.

## Secrets

Envelope encryption with the existing `fernet_key` until ADR-12 picks a KMS. Display last 4 characters only. API keys over passwords. The sandbox helper that generates an API key stays on sandboxes and is never an agent tool.

## Isolation tests that must exist before GA

- Approver A, connection B → 404.
- Forged session for another workspace → denied.
- Bot grant cannot read a second tenant's change-set.
- Audit verify fails if a row is edited.

## Compliance notes (not legal advice)

Accounting audit retention 7 years is the product default for those kinds. Segregation of duties: R3 approver is not the requester. The agent does not enrol 2FA devices, does not complete KYC, and does not register for e-invoicing.

## Pen-test

GATE-P7-03: no open critical or high. Until that report exists, GA claims in the progress log say "pen-test not done".
