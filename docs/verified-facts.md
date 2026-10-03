# Verified facts (repo-local)

Each bullet is tagged **`[verified]`** (supported by files in this repo at read time) or **`[unverified]`** (not confirmed here, external, or future work). Odoo RPC method names below are only those seen in this codebase—not a general Odoo API reference.

---

## 1. Request ids (`X-Request-Id`)

- **`[verified]`** Middleware lives in `apps/api/app/request_id.py` (`RequestIdMiddleware`, header name `X-Request-Id`).
- **`[verified]`** Incoming values are accepted only when they fully match `^[A-Za-z0-9_-]{1,128}$` (`_SAFE_REQUEST_ID.fullmatch`).
- **`[verified]`** Values containing a space fail that pattern and are replaced with a new id (`uuid.uuid4().hex`).
- **`[verified]`** Values containing the substring `Bearer` are also rejected (same replacement), even if they match the regex.
- **`[verified]`** Safe incoming ids are echoed on the response header; unsafe/missing ids get a 32-char lowercase hex id on the response.
- **`[verified]`** Tests in `apps/api/tests/test_request_id.py` cover missing header, safe echo (`trace_abc123-XYZ_99`), and rejection of `"has space inside"` and `"prefix-Bearer-suffix"`.
- **`[unverified]`** Behavior in a production deploy (TLS terminators stripping or rewriting headers, multi-instance consistency) was not exercised in this pass.

**Section status:** **`[verified]`** by code and unit tests in-repo; **`[unverified]`** for production deployment.

---

## 2. `view_has_field` (AI schema clients)

- **`[verified]`** Implementations are in `apps/api/app/ai_schema_client.py`.
- **`[verified]`** `LiveSchemaClient.view_has_field` tries `execute_kw` with model method `get_views` (form view), then falls back to `fields_view_get` when needed, and parses arch XML for the field name (see docstring and method body in that file).
- **`[verified]`** `FakeSchemaClient.view_has_field` returns true only when the field appears in the test-supplied `view_fields` map for the model; missing model entry → false.
- **`[verified]`** `DenySchemaClient.view_has_field` always returns false.
- **`[verified]`** `CatalogSchemaClient.view_has_field` always returns false.

**Section status:** **`[verified]`** by code reading (not by live Odoo RPC in this document).

---

## 3. JSON-2 transport

- **`[verified]`** HTTP JSON-2 transport module exists at `packages/odoo-client/src/odoo_client/transport/json2.py` (`Json2Transport`, docstring references `POST /json/2/<model>/<method>`).
- **`[verified]`** `STATE.md` (2026-10-02) records local tip: `/doc` returned **404**; password login → XML-RPC ok; Bearer without API key → **401 Invalid apikey**.
- **`[verified]`** 2026-10-03 live calls on `https://aonb.odoo.com` (database `aonb`) and `https://aonb-mirror.odoo.com` (database `aonb-mirror`, described as a duplicate of the tip). No API key is stored in this file. A 500 traceback referenced `/home/odoo/src/odoo/20.0/`, so this build is 20.0, not a 19 tip.
- **`[verified]`** `GET /json/2` returns **404** with message `Did you mean POST /json/2/<model>/<method>?`.
- **`[verified]`** `POST /json/2/res.partner/search_read` with `domain`, `limit`, and `fields` returns **200** on both hosts. `POST /json/2/res.partner/fields_get` with `attributes` returns **200** on both hosts. `POST /json/2/res.partner/create` with an empty body returns **422** `missing a required argument: 'vals_list'` on both hosts. One `create` with `vals_list` on the tip returned **200**; that probe contact was then removed with `unlink`.
- **`[verified]`** A Bearer token that is not an API key returns **401** `Invalid apikey` on both hosts. A `search_read` whose `domain` is a string returns **500** `Domain() invalid argument type`, not 400, on both hosts.
- **`[unverified]`** `GET /doc` and `GET /doc/res.partner` return **200** HTML for the public website. Those pages do not name `search_read`, `fields_get`, or `json/2`. The parameter names above were taken from live calls and server errors, not from `/doc`.

**Section status:** transport and these two hosts **`[verified]`** for the call shapes above. `/doc` as the API reference on this website is **`[unverified]`**.

---

## 4. Odoo 20 stack

- **`[verified]`** Decision D11 in `MEMORY.md` (2026-10-02): Odoo Community **20** is GA alongside 17–19; 16 remains experimental; majors ≤15 refused; 20 uses `ir.access` (not `ir.model.access` + `ir.rule`) per that decision text.
- **`[verified]`** No `docker-compose.odoo20.yml` (or similarly named odoo20 compose file) is present in this repo; existing compose files under `docker/` include 16–18 and sandbox/deploy variants only.
- **`[unverified]`** A runnable Odoo 20 Docker gate stack (images, adapters, CI) is not built or validated in this repository yet.

**Section status:** policy **`[verified]`** in MEMORY; stack **`[unverified]`** / not built.

---

## 5. Audit hash chain

- **`[verified]`** Product audit hash chain (append-only store, `prev` / `hash` SHA-256 linkage, kinds, redaction rules) is **specified** in `docs/plans/next-phase/11_LOGGING_AUDIT_OBSERVABILITY.md` §2.
- **`[verified]`** Current app audit persistence is a simpler `audit_logs` table (`apps/api/app/db_models.py` `AuditLog`: method, path, status, IP, api key prefix, duration, detail_json, timestamp) with **`[verified]`** no `prev` / `hash` / `plan_hash` columns in that model.
- **`[verified]`** `apps/api/app/audit.py` middleware writes those HTTP audit rows; it does not implement the spec’s chained hash writer or verify CLI.
- **`[unverified]`** End-to-end tamper-evident audit chain as in the next-phase spec (including fail-closed append on apply).

**Section status:** spec **`[verified]`**; implementation **`[unverified]`** (not present in product code read here).
