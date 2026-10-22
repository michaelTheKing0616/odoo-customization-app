# Business: Template marketplace, Client portal, Effort and billing tracker

Baseline `00_BASELINE.md` applies.

<a id="mkt"></a>
## MKT: Template marketplace
Extends FA-A28 (one templates library across features) and BR-ITEM-27 (recipe marketplace/templates). It reuses `industry_seeds`, `config_recipes`, `config_as_code` and `store_packaging`/`store_readiness`.
1. **User / job:**
   - An agency that reuses its best setups across clients, and other agencies who want proven starting points.
   - Value: faster delivery, and a network effect later.
   - Metric:
     - A template published from DB A installs as a plan on fresh test DBs of each supported version and passes Check.
     - The install success rate is shown per template from real installs only (INV-15).
2. **UX:**
   - Templates → Browse: workspace-private and Ingenium-curated sections; filter by app, industry and version.
   - Template page: what it adds (objects list), versions supported, installs and success rate (real), and the author.
   - "Use on <database>" opens a plan (Check → Approve → Run → Undo).
   - Publish: pick objects from a DB (reuses the PROMO diff picker) → describe → automated validation → curator review for public → published.
   - ⌘K: "Browse templates".
3. **UI:** area 07 App Studio gallery look (v0) for cards, and area 01 for lists. Template thumbnails are generated from metadata, never screenshots of client data.
4. **Security:**
   - Templates are untrusted input: metadata plans only, no Python (Python templates go to Option A sandbox, DEC-069).
   - Deterministic validation: allowed op types, no domains referencing `res.users` passwords or `ir.config_parameter`, no xpath `replace` on stock views, and size caps.
   - Template text is fenced before any AI touches it.
   - Publishing strips company names and emails.
5. **Robustness:**
   - Templates are versioned (semver), and installs pin a version.
   - Version adapters run on install (views_v18/v20).
6. **Data / API:**
   - Tables `templates` (id, owner_workspace, visibility: private|public, status: draft|review|published|withdrawn), `template_versions` (semver, ops JSON, versions_supported, sha256) and `template_installs` (outcome).
   - `GET /api/templates?scope=&app=&version=`.
   - `POST /api/templates {source_connection_id, ops}`.
   - `POST /api/templates/{tid}/submit`.
   - `POST /api/templates/{tid}/install {connection_id, version}` → plan id.
7. **Risks:** paid templates and revenue share are out of scope (DEC-069). Curation load.

<a id="portal"></a>
## PORTAL: Client portal (approve changes, see what was built, raise requests)
Covered in large part:
- SUITE-28: client mode and portal home.
- FA-S17: client portal items (itemise at G2): 17+.3 change requests, 17+.4 monthly report, 17+.5 tickets.
- SUITE-40: client sign-off.
- BR-ITEM-32: Bridge client mode.
- `client_access.py` and `/connections/[id]/client`.

This epic adds only: the "What was built" feed, request intake → consultant draft, and the portal security proof.
1. **User / job:**
   - The client owner: "What did my consultant change, what is waiting for me, and how do I ask for something?"
   - Value: trust and fewer status emails.
   - Metric:
     - Every History entry for the client's connection appears in the feed in plain words within 1 min.
     - A request becomes a consultant-side draft with fenced client text.
     - The client role cannot reach any Run, write or other-tenant route (tenancy and IDOR suite green).
2. **UX:**
   - Client Home (SUITE-28) has three blocks:
     - Waiting for you (approvals, sign-offs).
     - What was built (feed: "Added 'Delivery date' to Sales orders, 14 Oct, by Ada, approved by you").
     - Ask for a change (plain text plus an optional screenshot upload). The client sees status: received / planned / done.
   - The consultant sees requests in Approvals → Requests and converts one to an App Studio or suite draft.
   - ⌘K for the consultant: "Open client requests".
3. **UI:** area 04 Home (Stripe) and area 05 Approvals. Client mode is brandable (white-label WL-*).
4. **Security:**
   - Client role decisions via `client_access.client_request_decision`. New routes go in `idor_registry`.
   - Uploads use SEC-UPLOADS (type and size, malware scan if present).
   - Request text is fenced when an AI drafts the plan, and the draft needs the consultant's approval.
   - Clients never trigger Run (DEC-070).
5. **Robustness:** the feed reads History with a cursor, cached for 30 s. Requests are idempotent on a client-generated key.
6. **Data / API:**
   - Table `client_requests` (connection_id, author, text, attachment_id, status, draft_ref).
   - `GET /api/connections/{id}/client/feed?cursor=` → `{items[{when, what_plain, by, approved_by, history_id}]}`.
   - `POST …/client/requests {text, attachment_id?, idem_key}`.
   - `GET …/client/requests`.
   - `POST …/client/requests/{rid}/draft` (consultant only).
7. **Risks:** overlap with the FA-S17 itemise. When FA-S17 itemises, 17+.3 maps to PORTAL-03 and 17+.4/17+.5 stay in FA (see NEW_FEATURES_INDEX).

<a id="effort"></a>
## EFFORT: Effort and billing tracker against the SOW
New. It reads SOW lines (SOW epic), History runs and UAT. It is not SaaS billing (BILL-*), which is Ingenium charging the agency. FA Billing 4 (agency re-billing reports) is a neighbour, cross-linked.
1. **User / job:**
   - An agency owner: "Are we on budget per SOW line, and what do I invoice this month?"
   - Value: margin control on fixed-price Odoo projects.
   - Metric:
     - Burn per SOW line equals the sum of logged entries (unit test).
     - Auto-linked runs attach to the right SOW line ≥ 95% on a labelled set (by plan origin).
     - The monthly invoice CSV totals match the entries.
2. **UX:**
   - Delivery → Effort. SOW lines show budget hours, logged, % burn and a warning at 80%.
   - Log time (quick add: line, hours, note).
   - Ingenium suggests entries from its own runs ("App Studio draft for line 4.2, 1.5 h estimated"), which are accepted or edited.
   - Change requests from PORTAL become "out of scope" lines with an estimate that the client approves.
   - Month close: an invoice CSV/PDF per client.
   - ⌘K: "Log time".
3. **UI:** area 15 Billing (Stripe) with tabular figures and burn bars from the UI-CHARTS build.
4. **Security:**
   - Workspace-private. Rates are visible to owner and admin roles only.
   - No writes to any Odoo, including the agency's own, in v1 (DEC-071).
5. **Robustness:** decimal arithmetic. Entries are immutable after month close (correction entries only), with an audit-chain entry on close.
6. **Data / API:**
   - Tables `effort_entries` (sow_line_id, user, hours, note, source: manual|suggested, run_ref) and `effort_closes`.
   - `GET /api/sow/{sid}/effort` → `{lines[{id, budget_h, logged_h, burn_pct}]}`.
   - `POST /api/sow/{sid}/effort {line_id, hours, note}`.
   - `POST /api/sow/{sid}/effort/close {month}` → CSV/PDF.
7. **Risks:** timesheet adoption. Suggestions from runs reduce typing.
