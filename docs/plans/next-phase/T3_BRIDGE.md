# Track 3 — Ingenium Bridge

Sources: Bridge plan 2026-09-23, amended by the 2026-09-29 addendum. The addendum wins on contract shape, Connections, and connector tiers. D3, D4, and D5 are closed.

## Departures from a generic integration tutorial

- Middleware is the default. Ingenium does not become the third-party system.
- Webhook signature verification is required when the connector supports it.
- One Integration Contract is the IR. Missing required fields fail closed.
- Verification is mandatory. A contract does not become available on a green form.
- Money entities require `money_policy`.
- Two-way sync is refused unless `conflict_resolution` is set.
- Secrets are not inlined in the contract. They live on the Connection, encrypted at rest.

## Contract

A contract references `connection_id` values. It does not embed `odoo_target` or `third_party` credential blocks (addendum supersedes the 23 Sep sketch).

Required on every event: `idempotency_key`.

Connection record fields: `kind`, `verified_at`, `status`, plus the odoo or third-party non-secret fields. A connection must pass a live verify before any contract using it passes Tier I.

## Connector interface

The engine above a connector does not grow a per-vendor branch. Queue, idempotency, contract rules, verification tiers, and the catalog gate stay as they are. A new platform is a new connector plus a field mapping onto Odoo models. The connector never holds Odoo write credentials and never writes Odoo itself. A sync job takes the connector's records and writes Odoo through the public ORM.

The Shopify class currently implements six methods: `fetch`, `create`, `update`, `declared_schema`, `verify_webhook_signature`, `parse_webhook_event`. That is the REST-plus-webhook shape, not the ceiling.

A connector declares which of these it supports. Unsupported ones are absent, not faked:

| Capability | Used for |
|---|---|
| `declared_schema` | Entities and fields the platform actually has |
| `fetch` / `search` | Pull, including a filter, not only a cursor |
| `create` / `update` / `cancel` | Push and void |
| `parse_webhook_event` | Inbound HTTP when the platform sends webhooks |
| `verify_webhook_signature` | Required only when webhooks are declared |
| `poll` | Platforms with no webhooks |

Auth (API key, OAuth2, HMAC, basic) lives on the Connection, not as a new engine. Transport (REST, GraphQL, webhook, poll, file drop) is connector config. Webhook signatures stay mandatory for webhook transports. A poll-only platform is not rejected for lacking a signature. Tier 3b is "config only, no new Python," and it is not limited to REST plus webhook. Tier 3c remains the path when config cannot express the platform.

## Tiers

| Tier | Meaning | Rule |
|---|---|---|
| 3a | Known catalog connector | Hand-built. Shopify is the first |
| 3b | Generic transport, config only (REST, GraphQL, webhook, poll, file) | Try this before 3c |
| 3c | LLM-generated connector | Allowed only after 3b cannot express it |

Genericity proof: a Tier 3b or 3c expression of Shopify matches the hand-built connector's contract behavior, with zero changes above the connector interface.

## Verification tiers

| Tier | Proves |
|---|---|
| I | Static contract validation. Incomplete contracts fail |
| II | Sandbox dry-run: happy path, duplicate webhook, partial failure, auth failure, rate limit, malformed payload |
| III | Reconciliation dry-run with a seeded discrepancy. The run must detect it |

## Phases

| Phase | Exit |
|---|---|
| 0 | PR-J1 recorded. Contract schema rejects an incomplete fixture. Queue tables accept a test row |
| 1 | Shopify passes Tiers I–III against real sandboxes. Tier III detects the seeded discrepancy. This is the architecture proof |
| 2 | At least one connector is expressed as Tier 3b config only. Genericity proof passes. Phase 2 then covers 3c |
| 3 | A deliberately failing job lands in the dead-letter queue and is visible to an operator |
| 4 | Each catalog addition passes I–III before it is offered |

## Queue

Postgres tables (`integration_events`, jobs, mappings). Not a managed queue SaaS. Jobs are resumable from a fresh plan, never a stale one.

## Contract Studio

Built after the Phase 1 schema is stable. Form plus connection pickers. Choosing two-way reveals `conflict_resolution` and blocks save until it is set.

## Not in this track

Paystack is not the pilot (D4). It may be a later catalog card under Phase 4. Autopilot payment connectors are not this contract.
