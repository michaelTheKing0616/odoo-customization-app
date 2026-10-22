# New-feature baseline (applies to every NF epic; epics list only their deltas)

Status: proposal (INV-06) until DEC-050. Source: Tope's new-features brief, 22 Oct. Clean-room: public Odoo ORM over XML-RPC / JSON-RPC (JSON-2 on 20 where the compat registry says so). No Odoo Enterprise or Studio code is read or copied (INV-12).

## B1 UX baseline (every screen)

| State | What the owner sees (copy pattern) | Component |
|---|---|---|
| Empty (never run) | One sentence on what the scan finds, one primary button "Run the check (read-only, about N min)". | F1-STATES empty |
| Loading / running | Skeleton rows plus a progress line "Reading 3 of 9 areas · 1 min left". Cancel is always there. Never a bare spinner. | `LoaderCallout`, skeleton from F1-STATES |
| Partial | Results so far, with a `Callout` "Stopped early at the time limit. 6 of 9 areas checked. Run the rest". Partial results are never shown as complete. | `Callout` |
| Error | `ErrorNotice` with the plain cause and one fix ("Odoo said the key has expired. Open Connect to add a new key"). | `ErrorNotice` |
| Permission denied (Ingenium role) | "Your role can view results but not run checks. Ask a workspace admin." No button that fails later. | `Callout` |
| Permission denied (Odoo user) | Names the missing Odoo group and why the check needs it. Links to the least-privilege guide (EL-CONN-LEASTPRIV). | `Callout` |
| Offline / Odoo unreachable | The last saved results stay visible, stamped "From 14:02, Odoo is not answering now". Retry has backoff. Write buttons are off. | `StatusPill` + `Callout` |
| Huge data | Counts come from `read_group` / `search_count`. Samples are capped (B4). The banner says "Sampled 5,000 of 1.2M records". Tables use `DataTable` virtualisation (F1-PAGINATE). | `DataTable` |

- **Keyboard:** every screen registers its actions with `useCommand` (⌘K): "Run …", "Open …", "Export …". Lists support j/k and Enter. Esc closes sheets. Focus is always visible.
- **Undo / History:** any fix runs as a change plan through Check → Approve → Run (the existing write gate and receipt). It lands in History with one-click Undo where Odoo allows (views, automations, server actions, menus, access rules). Where undo is partial (data, dropped fields), the confirm dialog says so before the run.

## B2 UI baseline
- Map area and reference product come from `UI_REFERENCE_MAP.md`. The per-screen protocol is `07_UI_EXCELLENCE_PROTOCOL.md` §4: a ui-spec card comes first, then build, then the contact sheet and GATE-B.
- **Existing components only:**
  - `components/ui/`: `DataTable`, `StatusPill`, `Badge`, `Callout`, `ErrorNotice`, `LoaderCallout`, `ConfirmDialogV2`, `DiffView`, `Sheet`, `Dialog`, `Tabs`, `Disclosure`, `Term`, `TechName`, `CodeBlock`, `Combobox`, `Select`, `Input`, `Textarea`, `Tooltip`, `layout-primitives`, `success`, `AppToaster` (Sonner).
  - Also the F1-STATES state set and charts from area 16 (recharts in Dashboard Studio only, D12; other charts use the UI-CHARTS-* build).
  - A new component needs two uses and goes through F1 review.
- **Tokens only:** no raw hex or `rgb(`. Light-ish backgrounds always get dark ink, enforced by `apps/web/src/lib/a11y/contrast.test.ts`. Dark mode has parity. There is no new visual language. The brand follows `docs/brand/README.md`; `docs/brand/ingenium-v2/` does not exist in this repo.
- **Motion:** `motion/react` with transform/opacity only, 100–250 ms with ease-out on enter. It is interruptible and turns off under reduced motion.
- **Responsive and accessibility:**
  - Layouts are checked at 390 / 768 / 1024 / 1440 / 1920. There is no horizontal scroll at 390 outside tables.
  - WCAG 2.2 AA: focus visible (2.4.11), target size ≥ 24 px (2.5.8), no drag-only actions (2.5.7), and zero serious/critical axe issues.
- **Plain words:** owner-visible copy passes the jargon guard (F1-JARGON). Odoo technical names appear only inside `TechName`.

## B3 Security and fidelity baseline

| STRIDE | Default control |
|---|---|
| Spoofing | Ingenium auth (`AUTH_MODE`, DEC-034). The Odoo connection uses the stored API key. Each call is scoped to the workspace that owns the connection (SEC-TENANCY test covers every new route). |
| Tampering | Engines only read. Writes exist only as change plans through the write gate (receipt, 428/403, `mutation_lock`, anomaly cap, blast radius). Every write and every run lands in `audit_chain.append_entry`. |
| Repudiation | The audit chain records the actor, connection, plan hash and receipt. Second approver per SEC-2APPROVER where the epic says so. |
| Information disclosure | Findings store counts, record ids and masked samples only. Field values are not stored unless the epic says so. Nothing leaves the client DB except into the App DB of the same workspace. AI calls get schema and counts, never record values, unless the epic lists a field and fences it. |
| Denial of service | Per-connection RPC budget (B4). A scan never runs two copies on one connection. The anomaly cap applies to writes. |
| Elevation of privilege | Client-mode users go through `client_access.client_request_decision`. New routes are added to `security/idor_registry.py`. No route lets a client trigger Run. |

- **Least privilege:**
  - Read-only epics need only read groups on the models they scan.
  - Each epic lists its Odoo groups. A missing group is a finding, not a crash.
- **Hosting (`hosting.py`):**
  - Read scans run on Online, Odoo.sh and on-prem.
  - Anything that installs a module is refused on Online (no custom modules) and runs sandbox → human promote on Odoo.sh and on-prem (Option A).
  - [Inferred: RPC on Odoo Online needs a plan with external API access; verify in each epic's live card via L2-PROVE-HOSTING.]
- **Prompt injection:** any client text (record names, notes, uploaded BRDs, statements, templates) reaches a model only through `app/ai_client` with `fence_fields(payload, source=…)`. Model output goes through a deterministic validator before it reaches a plan (INV-13). The model never chooses models, fields or methods outside the live schema packet (GND-GATE).
- **Refusals (always):**
  - Never write posted journal entries, payments or invoices.
  - Never write tier-1 accounting fields.
  - Never delete a company, user or posted document.
  - Never run on a DB that the connection does not own.
  - Never clone a customer production DB (AGENTS).
  - Promote to another connection stays human.
- **Secrets:** no secret or client PII in logs, packets, findings or screenshots (INV-17). Exports are masked by default.

## B4 Robustness baseline
- **Idempotency:** a scan run key is `(connection_id, scan_id, params_hash, schema_fingerprint, day)`. A repeated POST returns the same run. Plan writes reuse the write-gate receipt (one receipt, one run).
- **Retries:** reads only, 3 tries with backoff of 0.5 / 1 / 2 s plus jitter, and only on transport errors and 5xx. Writes are never retried without the write gate's idempotency.
- **Timeouts:**
  - Per RPC call: 20 s.
  - Per scan area: its own budget.
  - Whole scan: 10 min by default; at the limit the result is partial.
- **Cancel:** checked between calls.
- **Rate limit:** each connection gets a token bucket, default 4 calls/s and 1 running scan [Inferred: tune in the SCAN live card]. Odoo 429 or 503 backs off and is surfaced as "Odoo asked us to slow down".
- **Large DBs:** `search_count` / `read_group` first. Samples are capped at 5,000 rows per area. Pages are 500 ids.
- **p95 budgets per size class:**

  | Size class | Largest model | Full scan p95 |
  |---|---|---|
  | S | ≤ 10k rows | 30 s |
  | M | ≤ 1M rows | 3 min |
  | L | ≤ 10M rows | 10 min, partial allowed |

- **Partial failure:** results are saved per area, and an area failure never loses the other areas. Plan runs are atomic per step, with snapshot before and Undo after (`odoo_snapshot`, `changeset/rollback.py`).
- **Versions:**
  - All version facts come from `app/compat/odoo_versions.py`.
  - Views: `<tree>` on 17, `<list>` on 18+.
  - Odoo 20 uses `ir.access` (no `ir.rule`), `group_ids` and no `db` service.
  - 16 is experimental and gets a plain "not checked on 16" note.

## B5 API and data baseline
- **Routes:** routes go under `/api/connections/{id}/…` and are registered in `app/main.py`. Each epic has one router file.
- **Error envelope for new routes:** `{"error": {"code": str, "message": str (plain), "detail": dict | null, "retry_after_s": int | null}}`. Codes:

  | Code | HTTP |
  |---|---|
  | `ODOO_UNREACHABLE` | 503 |
  | `ODOO_ACCESS_MISSING` | 403 |
  | `ROLE_DENIED` | 403 |
  | `HOSTING_NOT_SUPPORTED` | 409 |
  | `MONEY_GUARD_REFUSED` | 403 |
  | `RECEIPT_REQUIRED` | 428 |
  | `RATE_LIMITED` | 429 |
  | `VALIDATION` | 422 |
  | `NOT_FOUND` | 404 |
  | `CONFLICT` | 409 |

- **Scan types** are defined once in SCAN-01 (`app/scans/contract.py`):
  - `ScanRun {id, connection_id, scan_id, status: queued|running|partial|done|failed|cancelled, started_at, finished_at, areas: [AreaResult], budget_ms, odoo_version, schema_fingerprint}`
  - `AreaResult {area, status: done|partial|skipped|failed, rows_read, sampled: bool, duration_ms, findings_count, error_code | null}` (`error_code` is one of the B5 error codes; `skipped` means the Odoo user cannot read that area)
  - `Finding {id, scan_id, area, severity: info|low|medium|high|critical, title, plain_why, count, sample_ids: [int] (≤20), model, evidence: dict, fix: FixRef | null, docs_url | null}`
  - `FixRef {kind: plan|link|manual, plan_template, params}`
- **Migrations:** App DB tables are created only with Alembic (B0-ALEMBIC). Every new table carries `workspace_id`, `connection_id` and `created_at`. Retention is 90 days by default (DEC-052).
