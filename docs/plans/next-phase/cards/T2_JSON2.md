# Cards — T2 JSON-2

Self-contained. Gates copied from `../T2_JSON2.md`. D1 is closed (dual-protocol); no card reopens it.

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs or the progress log (an API key is a secret); no customer database; `:8001` does not reload; never loosen a test; no live LLM in PR tests; stay inside "Change". **T2-specific:** do not change a public caller signature to match a guessed JSON-2 shape; `/doc` is the reference of record, do not guess; never auto-retry a write at the transport layer; TLS required, `verify=false` forbidden, no write-plane redirects; ≤ 2 concurrent calls per database, read timeout 30 s, write timeout 120 s; the sandbox stays on XML-RPC until a card moves it; do not repeat the obsolete "Odoo 20 removes legacy RPC in fall 2026" date.

**Facts (copied):** endpoint `POST /json/2/<model>/<method>`; Bearer API key, optional `X-Odoo-Database`; named args, stateless, one SQL transaction per call; status codes 200, 400, 401, 403, 404, 500; XML-RPC and JSON-RPC deprecated since 19.0; `db` service removed in Odoo 20 and Online 19.1; `common` / `object` removal in Odoo 22 and Online 21.1 (fall 2028); Online legacy-RPC removal 21.1 (winter 2027); Online External API is Custom plan only.

**Shared commands:**

```bash
uv run --directory packages/odoo-client pytest -q tests/test_json2_transport.py tests/test_registry_odoo20.py
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/<file>.py
```

**Audit events:** none new. Transport calls that write already flow through `rpc_guard` and the HTTP audit middleware.

---

### T2-J1 — PR-J1 live `/doc` check
- **Status:** OPERATOR. Transport and 20 unit tests exist (`packages/odoo-client/src/odoo_client/transport/json2.py`, `execute_kw_map.py`, `tests/test_json2_transport.py`). Local tip `/doc` returned 404 on 2026-10-02; password login gives 401 Invalid apikey on Bearer (expected).
- **depends_on:** BL-06
- **Pressure:** C1 U2 F2 K2 V2 I1 +0 = 10 → Grok high effort for the write-up; the live call is a human with an API key
- **Read first:** `transport/json2.py`, `transport/execute_kw_map.py`, `tests/test_json2_transport.py`.
- **Change:** `docs/verified-facts.md`; tests only if `/doc` contradicts the mapper.
- **Steps:**
  1. Operator creates an API key (Preferences → Account Security → New API key, scope `rpc`, with an expiry) on a 19 tip and on a mirror.
  2. Open `/doc` (or `/doc/<model>`) and record the parameter names for `search_read`, `create`, and `fields_get`.
  3. Compare to `execute_kw_map.py`: `search_read` uses `domain` plus kwargs; `create` takes `vals_list`; `fields_get` takes `attributes`.
  4. Call each once and record status codes. Trigger a 400 (bad domain) and a 401 (bad key).
  5. Write each fact in `verified-facts.md` as verified, with date and Odoo build.
- **Acceptance:** [ ] PR-J1: `/doc` matches for the three methods on a tip and a mirror; [ ] 4xx and 5xx unit-tested (`test_json2_http_errors_raise_with_full_body` exists); [ ] callers keep the frozen interface (`test_execute_kw_json2_path_does_not_touch_xmlrpc_object`).
- **Negative:** a guessed signature (one not seen in `/doc`) fails review; record "not verified" rather than guess.
- **Do not:** paste the key into the progress log.
- **Rollback:** revert the facts file.
- **Evidence:** facts rows with build id and date.

### T2-J2 — PR-J2 install port
- **Status:** SEEDED (`test_map_button_immediate_install_ids`). Live install via JSON-2 not recorded.
- **depends_on:** T2-J1
- **Pressure:** C2 U1 F2 K1 V2 I0 +0 = 8 → Grok standard
- **Steps:** (1) run `button_immediate_install` for a known-good module through the same client with `rpc_protocol=json2` on a 19 instance that has an API key; (2) time it; (3) run the XML-RPC baseline on the same module and record both durations.
- **Acceptance:** [ ] install succeeds through the frozen interface; [ ] both durations recorded.
- **Do not:** switch the sandbox default to JSON-2 in this card.

### T2-J3 — PR-J3 grep
- **Status:** OPEN. `rg -l "xmlrpc|execute_kw" apps/api/app` returns 101 files today; most are callers of the client's `execute_kw` method, which is the frozen interface and is allowed.
- **depends_on:** T2-J2
- **Pressure:** C2 U1 F1 K1 V0 I0 +0 = 5 → cheap
- **Steps:**
  1. `rg -n "import xmlrpc|xmlrpc\.client|ServerProxy" apps packages --glob '!**/tests/**'`.
  2. Every hit outside `packages/odoo-client` (legacy adapter) and the sandbox is a finding. List it.
  3. Calls to `client.execute_kw(...)` are the frozen interface and are not findings.
- **Acceptance:** [ ] the direct-transport grep is empty outside the allowed adapter and sandbox, or each remaining hit has a card.
- **Negative:** a new `ServerProxy(` in `apps/api/app` fails the grep test (add `tests/test_no_direct_xmlrpc.py` mirroring `test_no_mcp_write.py`, including the cache skip from BL-07).

### T2-J4 — PR-J4 honest docs
- **Status:** OPEN
- **depends_on:** T2-J3
- **Pressure:** 3 → cheap
- **Acceptance:** [ ] STATE.md and the progress log list what is done and what is operator-only; [ ] no sentence says "JSON-2 complete" while T2-J1 or T2-SMOKE is open.

### T2-SMOKE — Odoo Online smoke
- **Status:** OPERATOR / BLOCKED until a Custom-plan Online database is available.
- **depends_on:** T2-J1
- **Pressure:** 6 → operator plus Grok standard for the write-up
- **Acceptance:** [ ] Online Custom-plan `search_read`, `create`, `fields_get` recorded; or [ ] an explicit "not run: no Custom plan" line in STATE.md.
- **Do not:** fake a pass.
