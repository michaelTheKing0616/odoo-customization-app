# Locks, decisions, and source conflicts

A lock fails the build if weakened. A decision in this file beats an older source sentence. Where two sources disagree and this file does not name a winner, the newer source wins and the older sentence is marked superseded, not deleted.

## Product locks (already in force)

- Promote stays human. No card may auto-promote a module to a non-sandbox connection.
- Completeness is not certification. Certification is not Job Autopilot. An empty ModuleSpec is not Cert Gold.
- Sandbox before any customer install. Refuse `write_mode=production`. Do not clone a customer production database.
- Public ORM/RPC only. Never read, copy, or reverse-engineer Odoo Enterprise Studio source.
- Option A Python: author → module → sandbox → explicit promote. Live `state=code` stays off the default path.
- Local uvicorn on `:8001` runs without `--reload`. A routing fix is not live until that process is restarted.
- Credentials encrypted at rest. Prefer Odoo API keys over passwords. Never log secrets.
- Job Autopilot stays sandbox-only. Connector recipes do not invent a vertical `x_*` and do not write partner API keys.
- The model never writes. Only the executor writes, and only after `02_APPROVAL_FLOW.md`.
- Never weaken, skip, or delete a test to make a gate pass.
- Never run a card against a real client database.
- Majors ≤15 stay refused.

## Bot invariants (INV-01–INV-20)

| ID | Rule |
|---|---|
| INV-01 | The LLM never holds write credentials. Only the Executor writes. |
| INV-02 | Every write is a typed closed-catalog op. No generic write RPC. |
| INV-03 | Every identifier is grounded against same-run introspection. |
| INV-04 | Approval binds to `plan_hash` + `schema_fingerprint`. Either change voids it. |
| INV-05 | Every op has an inverse, or it is irreversible and needs elevated approval plus a backup. |
| INV-06 | Production needs a prior successful simulation unless the policy allows R1 direct-to-prod. |
| INV-07 | Policy is independent of the model. The model cannot alter policy. |
| INV-08 | Odoo, file, web, tool, and user data are untrusted. They never alter tool permissions. |
| INV-09 | Safety never relies solely on a prompt. |
| INV-10 | A WAL entry exists before each op. A crash is recoverable. |
| INV-11 | Secrets never enter model context, logs, traces, errors, or prompts. |
| INV-12 | Read plane ≠ write plane. Write credentials decrypt only in the Executor at apply time. |
| INV-13 | Strict tenant isolation. |
| INV-14 | Apply is idempotent (upsert by xmlid). |
| INV-15 | Fail closed on uncertainty. |
| INV-16 | Never report done before verification. Report exact outcomes. |
| INV-17 | Loop, cost, time, and size limits are runtime-enforced. |
| INV-18 | The audit log is append-only and tamper-evident. |
| INV-19 | Bot artifacts are identifiable (`ingenium` xmlid), minimal, and make no callbacks. |
| INV-20 | The agent works unchanged across providers. Safety is identical. Quality and autonomy tier may vary. |

## Decisions

| ID | Decision | Status |
|---|---|---|
| D1 | JSON-2 dual-protocol: pre-19 keeps XML-RPC/JSON-RPC; 19+ can use JSON-2; `auto` falls back | Closed (MEMORY) |
| D2 | `proved` requires `run_tests=True`. `proved_smoke_only` is not a promote stamp | Closed (MEMORY) |
| D3 | Product name is Ingenium Bridge | Closed |
| D4 | Bridge Phase 1 pilot is Shopify | Closed |
| D5 | Connections are a first-class subsystem. Contracts reference `connection_id`, not inlined secrets | Closed |
| D6 | Auth is self-hosted: Authlib + TOTP. No Clerk/WorkOS/Auth0 | Closed |
| D7 | Config-as-code is reimplemented in this repo. `odoo-config-agent` is the test oracle, not a vendored runtime | Closed |
| D8 | AI gateway: thin in-house vs LiteLLM. ADR-02 still open | Open |
| D9 | Client Approver is a connection grant (`client_approver` / `client_viewer`). Out of scope returns 404 | Closed. First slice shipped |
| D10 | L4 production allow-list autonomy is built this phase. Amends agent spec §10 "No L4" | Closed 2026-10-02 |
| D11 | Odoo 20 is GA this phase, beside 17/18/19. 16 stays experimental. ≤15 refused | Closed 2026-10-02 |
| D12 | UI stack moves to Base UI, Sonner, and `motion/react`. `cmdk` stays. Migration is one component family per card | Closed 2026-10-02 |

### D10 gates (authored here; thresholds need Tope confirmation before L4-01 starts)

These numbers are not copied from a source. They are the build contract until Tope changes them in MEMORY.

| ID | Gate |
|---|---|
| GATE-L4-01 | L4 applies only to op types on a tenant allow-list whose base risk is R1, or R2 that is non-DDL, non-protected, and non-outbound |
| GATE-L4-02 | Never R3, never R4, never `protected:elevate`, never `module.*`, never promote |
| GATE-L4-03 | Execution is Mode T (Bridge) on the same plan hash already applied and verified on staging |
| GATE-L4-04 | Each standing rule needs two admins, one of them the workspace owner |
| GATE-L4-05 | Standing rule expiry ≤ 30 days |
| GATE-L4-06 | Daily cap on auto-applies, default 20, tenant-configurable downward only |
| GATE-L4-07 | Blast radius ≤ 50 records per auto-apply |
| GATE-L4-08 | Eligibility: ≥ 200 L3 applies over ≥ 60 days, zero verify failures, rollback rate ≤ 1% |
| GATE-L4-09 | Any verify failure or policy violation demotes to L2 automatically and rolls back |
| GATE-L4-10 | Kill-switch drill passes: global and tenant switches stop an in-flight L4 apply |
| GATE-L4-11 | The never-allowed list is unbypassable at L4 (master DoD 24) |
| GATE-L4-12 | A negative test proves an L4 bot cannot widen its own allow-list |

### D11 lock line (replaces the previous GA sentence)

**Odoo Community 20 + 19 + 18 + 17 = GA. 16 = experimental** (16 omits dotted `update_path` / related_write). Majors ≤15 refused. Odoo 20 uses `ir.access` instead of `ir.model.access` + `ir.rule`. The `db` service is gone on 20. No silent best-effort outside the capability registry.

### D12 library rules

- Primitives: Base UI. Migrate off Radix one family at a time (`migrate-radix-to-base`).
- Toasts: Sonner. Duration 3–5s. Errors persist. `aria-live=polite`.
- Motion: `motion/react` is the only animation library. Transform and opacity only.
- Add `input-otp` for TOTP and `react-virtuoso` for tables over 50 rows. Add `recharts` only for Dashboard Studio.
- Keep `cmdk`. Command palette open is instant (no enter animation).
- Kit tests and `/e2e/kit` stay green after each family.

## Conflict table

| # | Side A | Side B | Winner |
|---|---|---|---|
| 1 | Claude response: static cue/allowlist/craft gate | Tiered architecture: live `schema_client` | Tiered architecture (2026-09-22) |
| 2 | Start from GenerateIR redesign | "Do not start from GenerateIR in isolation" | Tiered architecture |
| 3 | PR-F letter order suggests F is late | Master order 2 places PR-F.0 before PR-A | Master + addendum: F.0 first |
| 4 | `install_ready` after clean sandbox | `proved` vs `proved_smoke_only` | D2: `proved` requires `run_tests=True` |
| 5 | Bridge plan 2026-09-23 inlines `odoo_target` / `third_party` | Addendum 2026-09-29 uses `connection_id` | Addendum |
| 6 | Pilot open (Paystack or Shopify) | D4 Shopify | D4 |
| 7 | LLM-generated connector only | Tiers 3a / 3b / 3c, try 3b before 3c | Addendum |
| 8 | Conceptual compiler order: spec, progress, wireframe, agents | Compiler build spec phases 0–6 | Compiler build spec |
| 9 | MCP research priority: Dashboard first | Master order: progress+MCP, then Dashboard, then Offline | Master |
| 10 | MCP as a write path | Track 5: MCP is read-only from Ingenium | Master Track 5 (stricter, newer) |
| 11 | PR-A need not wait for JSON-2 | Prefer J1 before PR-A tests finalize; J1 is a hard dep of Bridge | Compatible: A may start; tests finalize after J1; Bridge waits for J1 |
| 12 | Agent spec: "No L4" | Master Worker Bots L4 and blueprint L4 production allow-list | D10: build L4 with GATE-L4-01–12 |
| 13 | GA lock 17/18/19 | Blueprint: Odoo 20 GA 2026-09-24 | D11: 20 is GA this phase |
| 14 | Repo uses Radix, CSS-only motion | Prime `pick-ui-library`: Base UI, Sonner, motion | D12 |
| 15 | Agent spec phases 0–9 are a global order | Master sequence orders 1–15 | Agent phases nest inside T8 after T5A shares the core |
| 16 | Blueprint unit counts 123 / 79 / 124 and "19 not live" vs package tests named live-19 | Measured repo and a future instance | Treat blueprint numbers as claims. Verify on an instance. Do not copy the count into a gate |
| 17 | Master D1 and D2 still worded "open" | MEMORY closes both | MEMORY / this file |
| 18 | Grok Bot: shared computer, approvals in prose, no undo | Ingenium: hash-bound approvals, real undo, one audit chain | Ingenium. Grok notes are research only |

## Authority stack

```
01_LOCKS (D1–D12) and AGENTS.md product locks
  → this pack (sequencing + inlined gates)
    → ingenium-master-build-spec-next-phase.md (synthesis; "supersedes nothing")
      → leaf docs (Claude response, tiered architecture, JSON-2, Bridge plan,
         Bridge addendum, compiler conceptual, compiler build spec,
         MCP research, MCP build spec, agent spec v1.1.1, blueprint v1.1)
GROK_BOT_RESEARCH_NOTES.md is adjacent research. It is not a track.
```

The three master-spec filenames (`next-phase.md`, `_v0.md`, `_v-1.md`) are byte-identical (SHA-256 `72cd30e88cfb481affa2c9e016dde6ff46a6bf1e8403bdc5848224cd7829b881`). Ingest one.

## Never-allowed and never-automated (both lists apply)

### Method never-allowed (even with approval)

```
("res.users", "unlink")
("res.company", "unlink")
("ir.model.data", "unlink")
("ir.config_parameter", "unlink")
("res.users.apikeys", "*")
```

### Protected parameter keys (never writable)

```
database.secret, database.uuid, database.create_date, web.base.url,
database.enterprise_code, database.expiration_date
```

### Agent-spec R4 / prohibited in v1 (overlap; the stricter cell wins)

`module.uninstall`; `data.delete` default-deny; group-less ACL; granting admin/system/service accounts; company lock dates, fiscal year, currency, chart of accounts; accounting/journal/legal sequence changes; `rpc.write`; raw SQL.

### Never automate (blueprint §1.3, verbatim areas)

| Area | Agent stops | Agent does instead |
|---|---|---|
| 2FA / TOTP enrolment, SSO, captchas | They prove a human is present | Detect `HumanActionRequired`; human logs in, or a dedicated bot API key is used |
| Bank sync (Plaid/Yodlee/Ponto/Salt Edge) | Needs the account holder's consent | Creates the bank journal; human connects the feed. CSV/OFX/CAMT import can be automated |
| Payment providers | KYC and secret keys belong to the client | Installs the module if approved; human pastes keys or a vault supplies them |
| E-invoicing / tax authority registration | Legal registration and certificates | Documents requirements; human registers |
| Purchases and subscriptions | Commits the client's money | Flags BILLABLE and asks |
| Hardware / IoT pairing | Physical | Configures software records, then a checklist |
| DNS and email deliverability | Lives at the registrar | Generates the records; verifies with DNS lookups afterwards |
| Accounting, tax, and legal judgement | Not the agent's decision | Implements the accountant's spec; marks inferences "to be confirmed" |
| Custom Python modules | Must be reviewed and deployed; impossible on Odoo Online | Drafts a skeleton; does not deploy. Low-code first |
| Database manager on Odoo Online | Portal, not the instance | Asks the human for a duplicate before risky work |
| Major-version upgrades | Odoo upgrade service | Post-upgrade verification suite only |
| Irreversible production work without approval | Policy | Asks |

Odoo 20 Community has no `ai*` modules. MCP `/mcp`, Studio, Helpdesk, Payroll (`hr_payroll`), Quality, and bank-sync feeds are Enterprise or IAP. Cards must not treat them as Community-complete.

## Two drift detectors, both required

1. **Plan fingerprint drift** (Track 5): re-plan at apply; abort if the live target changed since planning. Mark the change-set STALE.
2. **ISPEC drift** (Track 4): Sync reports drift and blocks. It does not warn and continue. It never overwrites in place.

Do not conflate them. Do not share one flag.
