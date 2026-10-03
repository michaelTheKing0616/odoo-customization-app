# Cards — T9 Odoo 20 GA (D11)

Self-contained. Gates O20-01–O20-16 and the version table are copied from `../T9_ODOO20_GA.md` (lines 7–67). D11: Community 20 + 19 + 18 + 17 GA; 16 experimental; ≤15 refused; 20 uses `ir.access`; the `db` service is gone on 20.

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs; never point the 20 stack at a customer database; `:8001` does not reload; never loosen a test; no live LLM in PR tests; stay inside "Change". **T9-specific:** do not vendor `odoo-config-agent` (port its tests by name, D7); do not keep sending `ir.rule` creates on 20 because 19 tests passed; do not write the computed `kind` field on `ir.access`; do not claim MCP, Studio, Helpdesk, Payroll, or Quality on the Community image (Community 20 has no `ai*` modules); do not assume `demo=false` works on 17–19 (truthy-string bug; it parses on 20); `action_apply_inventory` returns None, XML-RPC must tolerate that; Playwright `networkidle` never settles on 20, wait for RPC idle (`quiet_ms` 400, timeout 20 s); do not freeze a stale image digest (blueprint used `20.0-20260926`; record the digest you actually pulled).

**Shared commands:**

```bash
uv run --directory packages/odoo-client pytest -q tests/test_registry_odoo20.py tests/test_odoo20_version_table.py
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_bridge_and_config_spec.py -k odoo
# Operator: boot the 20 stack (needs Docker and network)
docker compose -p odoo20-custom-dev -f docker/docker-compose.odoo20.yml up -d
curl -fsS http://127.0.0.1:8073/web/login >/dev/null && echo up
```

**Audit events:** security writes on 20 emit `change` rows with `model: "ir.access"` and `risk: DESTRUCTIVE` (security models stay DESTRUCTIVE).

**Version table (each row needs a fake test and a live test on 20).** Columns are 16 / 17 / 18 / 19 / 20; ≤15 is refused.

| # | Area | 16–19 | 20 |
|---|---|---|---|
| V01 | Routes | `stock.route` | `stock.route` |
| V02 | Account type | `account_type` | `account_type` |
| V03 | Account company | `company_id` (16–17), `company_ids` (18–19) | `company_ids` |
| V04 | Analytic | plans + `analytic_distribution` | same |
| V05 | Tax repartition | `repartition_line_ids` + `document_type` (17+) | same |
| V06 | Tax included | `price_include` (verify override 18–19) | override + document-level switch |
| V07 | Payment term lines | `nb_days` (17+) | `nb_days` |
| V08 | Product type | `detailed_type` (16–17), `type` + `is_storable` (18–19) | same as 18 |
| V09 | Purchase UoM | `uom_po_id` (16–18), removed 19 | removed |
| V10 | Stock done qty | `quantity` + `picked` (17+) | same |
| V11 | Automation | separate `ir.actions.server` (17+) | same |
| V12 | Cron `numbercall` | present 16–17, removed 18+ | removed |
| V13 | User groups | `groups_id` (16–18), `group_ids` (19) | `group_ids` |
| V14 | `name_search` | `args` (16–18), `domain` (19) | `domain` |
| V15 | Web URLs | `/web#action=` (17), `/odoo/...` (18+) | `/odoo/...` |
| V16 | API | JSON-2 added in 19 | JSON-2 preferred; `db` removed |
| V17 | Fiscal position tax map | separate model (16–18), on the tax (19) | on the tax |
| V18 | Access | `ir.model.access` + `ir.rule` | `ir.access` |
| V19 | Account groups | `account.group` | `parent_id`; group model gone |
| V20 | Root product category | `product.product_category_all` (16–18), Goods/Services/Expenses (19) | same as 19 |
| V21 | UoM categories / packaging | present (16–18), removed 19 | removed |
| V22 | Pricelist types | fixed/percentage/formula | fixed/discount/markup |
| V23 | Report layouts | standard/boxed/bold/striped (+ bubble/wave/folder on 19) | standard, bubble, center, compact, dual, folder, lines, wave + `report_tables_id` |
| V24 | `account.payment.state` | draft/in_process/paid (18), verify 17 and 19 | draft/paid/reconciled |
| V25 | Partner `company_type` | present | removed |
| V26 | Partner `mobile` / `title` | present (verify 19) | absent from base |
| V27 | Company registry | `company_registry` | `additional_identifiers` JSON |
| V28 | BOM consumption | present (verify 19) | removed |
| V29 | Return wizard | `stock.return.picking` (verify 19) | removed |
| V30 | Tracking values model | `mail.tracking.value` (verify 19) | removed |
| V31 | `read_group` | legacy; formatted added 19 | aggregates and tuples |
| V32 | User `role` | — (group_user / system on 19) | light / regular / system |

Code today: `packages/odoo-client/src/odoo_client/compat/version_table.py` encodes 19 keys (V01–V03, V13, V14, V18, V12, V31, V16 `db_service`, V25, V27, V22, V09, V28, V29, V26, V32, list root). The other 13 rows have no fake test yet.

---

### O20-01 — Compose file
- **Status:** SEEDED. `docker/docker-compose.odoo20.yml` exists (host 8073, Postgres `db20`, app-db on 5436). `docker/run-odoo20-smoke.sh` only prints the command. The image has not been pulled or booted.
- **depends_on:** none
- **Pressure:** C1 U1 F1 K1 V1 I0 +0 = 5 → cheap (operator boots)
- **Steps:** (1) operator runs the compose command; (2) wait for `/web/login`; (3) create a database with `demo=false` and confirm it parses on 20; (4) record `docker image inspect odoo:20 --format '{{.Id}}'`.
- **Acceptance:** [ ] O20-01: Community 20 serves on 8073 with a matching Postgres and an init script; [ ] digest recorded.
- **Do not:** reuse the 19 database volume.
- **Rollback:** `docker compose -p odoo20-custom-dev -f docker/docker-compose.odoo20.yml down -v`.

### O20-02 — Registry lists 20 as GA
- **Status:** SEEDED. `compat/registry.py` docstring "GA = 17 + 18 + 19 + 20; 16 experimental"; tests `test_ga_majors_includes_17_through_20_not_16`, `test_for_major_20_is_ga`, `test_parse_major_20_variants`, `test_for_major_15_raises`.
- **Pressure:** 4 → cheap
- **Acceptance:** [ ] O20-02: `parse_major` accepts `20.0` and `20.0+e`; [ ] the web version banner (`VersionAwarenessBanner.tsx`) says 20 is supported. Check the banner text; it is the only open part.

### O20-03 — Adapters views_v20, automation_v20, security_v20
- **Status:** PARTIAL. `compat/adapters/views_v20.py` exists (`test_odoo20_list_root_is_list_not_tree`). `automation_v20.py` and `security_v20.py` do not exist.
- **depends_on:** O20-02
- **Pressure:** C2 U2 F2 K2 V1 I1 +0 = 10 → Grok high effort
- **Read first:** `compat/adapters/automation_v19.py`, `compat/adapters/__init__.py`, `apps/api/app/odoo20/access_compiler.py`.
- **Change:** new `automation_v20.py`, new `security_v20.py`, `adapters/__init__.py`, tests.
- **Steps:**
  1. `automation_v20`: start as a copy of v19's encoder; change only what the 20 table says (V11 unchanged; V12 no `numbercall`).
  2. `security_v20`: expose `access_model() -> "ir.access"`, refuse `ir.rule` writes, delegate the compile to `apps/api/app/odoo20/access_compiler.py` (or move the compiler into the package and import it from the API; pick one, do not duplicate).
  3. Register both for major 20 only.
- **Acceptance:** [ ] O20-03: three adapters exist; [ ] 16–19 adapter tests unchanged and green (`tests/test_views_adapters_multimajor.py`, `tests/test_automation_encoders_multimajor.py`).
- **Negative:** `security_v20` asked to create `ir.rule` raises.

### O20-04 — `ir.access` compiler (frontier + reviewer)
- **Status:** SEEDED. `apps/api/app/odoo20/access_compiler.py` (75 lines); tests `test_odoo_20_access_compiles_to_ir_access`, `test_odoo_20_group_record_rule_is_refused`, `test_odoo_20_refuses_computed_kind`, `test_odoo_19_domain_right_becomes_access_plus_rule`. Not wired into any write path yet.
- **depends_on:** O20-03
- **Pressure:** C2 U2 F3 K3 V2 I3 +0 = 15 → frontier model; independent reviewer answers "what could be wrong?"
- **Read first:** `apps/api/app/odoo20/access_compiler.py`; `apps/api/app/routers/security*.py` or the access router (`rg -ln "ir.model.access" apps/api/app/routers`); `../T9_ODOO20_GA.md` lines 69–75.
- **Change:** the access write path chooses the compiler by major; tests.
- **Steps:**
  1. Find every code path that creates `ir.model.access` or `ir.rule` (`rg -n "ir\.rule|ir\.model\.access" apps/api/app`).
  2. Route each through the compiler when major = 20.
  3. `access_rights` on 20 → `ir.access` (`operation`, optional `domain`). `record_rules` that name a group on 20 → plan fails with the migration message "rewrite as access_rights with a domain". On ≤19, domain-bearing rights still compile to an access row plus an `ir.rule`.
  4. Security models `ir.access`, `ir.model.access`, `ir.rule`, `res.groups` stay DESTRUCTIVE in `rpc_classify`.
- **Acceptance:** [ ] O20-04; [ ] DoD 34: a test fails if `ir.rule` is created on a 20 fake client; [ ] the reviewer's findings are answered in the progress log.
- **Negative:** every write path above, called with major 20 and a fake client, never sends `create` on `ir.rule`.
- **Commands:** API pytest on the compiler tests and the access router tests.
- **Rollback:** revert the routing; the compiler module stays.

### O20-05 — Access screen on 20
- **Status:** OPEN
- **depends_on:** O20-04, UI-F04 (Dialog family) if the screen uses dialogs
- **Pressure:** C2 U1 F2 K2 V1 I0 +0 = 8 → Grok standard
- **Read first:** `apps/web/src/app/connections/[id]/access/page.tsx` (749 lines); `apps/web/src/components/access/`.
- **Steps:** branch on the connection major: 20 reads and writes `ir.access` (operation + domain), ≤19 keeps the current screen. Show an inline note on 20: "Odoo 20 combines access rights and record rules."
- **Acceptance:** [ ] O20-05; [ ] Vitest for both branches; [ ] the 13 route block for `…/access` passes.
- **Negative:** on 20 the "Add record rule" control is absent.

### O20-06 — Version-table tests (one per row)
- **Status:** PARTIAL (19 of 32 rows encoded; fake tests only; zero live).
- **depends_on:** O20-01 for the live half
- **Pressure:** C3 U1 F2 K2 V1 I0 +0 = 9 → Grok standard; split into cheap sub-cards O20-06-V01 … V32 if a worker prefers one row per card
- **Change:** `compat/version_table.py`, `tests/test_odoo20_version_table.py`, a live test module `tests/test_integration_odoo20.py` (skipped unless `ODOO20_URL` is set, mirroring `test_integration_odoo19.py`).
- **Steps:** for each V-row above: (1) add the key to `version_table.py`; (2) a fake test asserts the 20 value and one older value; (3) a live test reads `fields_get` or the model list on the 20 stack.
- **Acceptance:** [ ] O20-06 and DoD 35: 32 rows × (fake + live) or a written N/A per row (for example V04 "same on all majors; one live check is enough").
- **Negative:** a test that asks for `company_type` on 20 fails with a named message, not a KeyError.
- **Oracle names to port (from `test_versions_profiles.py`):** `test_profiles_cover_15_to_20_and_20_is_latest`, `test_notes_for_migration_from_19_to_20`, `test_pricelist_percentage_to_discount_on_20`, `test_pricelist_discount_back_to_percentage_before_20`, `test_pricelist_fixed_is_unchanged_everywhere`, `test_access_rights_compile_to_ir_access_on_20`, `test_access_rights_with_domain_compile_to_access_plus_rule_before_20`, `test_record_rules_on_20`, `test_record_rules_unchanged_before_20`, `test_fiscal_position_mapping_by_version`, `test_report_layout_translation_on_20`, `test_pricelist_and_bom_and_accounts_on_20`, `test_products_uom_po_only_before_19_and_cron_numbercall_only_before_18`, `test_users_group_field_on_20`, `test_company_registry_becomes_additional_identifier_on_20`, `test_group_by_uses_formatted_read_group_on_19_plus_and_read_group_before`, `test_uom_category_mapping_by_version`, `test_name_search_keyword_is_args_up_to_18_and_domain_from_19`, `test_odoo20_security_models_are_destructive`.

### O20-07 — JSON-2 default on 20
- **Status:** SEEDED (`test_major_20_auto_selects_json2_even_when_local`).
- **depends_on:** T2-J1
- **Pressure:** 5 → cheap
- **Acceptance:** [ ] O20-07: `auto` picks JSON-2 on 20; [ ] password login on 20 returns a plain message explaining that JSON-2 needs an API key (oracle `test_auto_protocol_with_password_on_19_explains_why`).

### O20-08 — Snapshots without the db service (frontier review)
- **Status:** OPEN
- **depends_on:** O20-01
- **Pressure:** C2 U3 F3 K2 V2 I2 +0 = 14 → frontier
- **Read first:** `apps/api/app/routers/snapshots.py`; `rg -n "/web/database|db\.dump|dump_db" apps/api/app`.
- **Steps:** (1) find every call to the `db` service; (2) on 20 the metadata snapshot (`metadata_snapshots`) still works because it is RPC reads; (3) a database-level backup on 20 uses the documented 20 path, or the UI asks the human to take one on Online / Odoo.sh; (4) the snapshot gate (`snapshot_gate.py`) accepts a metadata snapshot id on 20.
- **Acceptance:** [ ] O20-08 and DoD 36: no call to the removed `db` service on 20 (test with a fake that raises on `/web/database/*`); [ ] oracle `test_snapshot_refuses_on_odoo_sh_and_online`.
- **Negative:** a 20 fake that raises on the db endpoint; the snapshot flow never hits it.

### O20-09 — Native MCP absent on Community
- **Status:** SEEDED (`test_community_without_ai_modules_has_no_native_mcp`).
- **Pressure:** 3 → cheap
- **Acceptance:** [ ] O20-09; [ ] the product UI never says "MCP available" on a Community 20 connection.

### O20-10 — Major gate includes 20
- **Status:** OPEN. `docker/run-sandbox-major-gate.sh` rejects 20 (`allowed: 16 17 18 19`).
- **depends_on:** O20-01
- **Pressure:** C1 U1 F1 K1 V1 I0 +0 = 5 → cheap
- **Change:** `docker/run-sandbox-major-gate.sh`, the sandbox compose for 20 if the gate needs its own image tag.
- **Acceptance:** [ ] O20-10 and DoD 33: `./docker/run-sandbox-major-gate.sh 20` installs the smoke module and passes a read/write smoke.
- **Negative:** `./docker/run-sandbox-major-gate.sh 15` still exits 2.

### O20-11 — Flows on 20
- **Status:** OPEN
- **depends_on:** O20-10
- **Pressure:** C2 U2 F2 K1 V2 I0 +0 = 9 → Grok standard
- **Acceptance:** [ ] quote-to-cash 7 checks, procure-to-pay 6, manufacture 2 pass on a 20 sandbox; test records prefixed so they are identifiable; never on production.

### O20-12 — Designer on 20
- **Status:** OPEN
- **depends_on:** O20-03
- **Pressure:** 6 → Grok standard
- **Acceptance:** [ ] O20-12: Designer opens a form and a list view on 20; list arch root is `list`, never `tree`; [ ] `e2e/designer-*.spec.ts` gains a 20 fixture or a unit test on the arch writer.

### O20-13 — Production checklist
- **Status:** OPEN
- **depends_on:** O20-06
- **Pressure:** 5 → cheap
- **Change:** `docs/runbooks/odoo20-production-checklist.md`.
- **Checklist (copied):** bot user plus an `rpc`-scope API key with an expiry, `ODOO_PROTOCOL=auto`; read every `(verify)` note in the `profile` output; replace `company_type`, `company_registry`, percentage pricelist rules, account groups, and legacy layouts through the translators; rewrite group record rules as access rights with a domain and have a security owner review; re-run flow tests on a duplicate and check a printed invoice layout; for AI and MCP agree key ownership before an Enterprise database is connected (Community skips this).
- **Acceptance:** [ ] O20-13: the runbook exists and each automated item names its test.

### O20-14 — `name_search` uses `domain`
- **Status:** SEEDED in the version table (`name_search_kw`). Not proven at the call sites.
- **Pressure:** 4 → cheap
- **Acceptance:** [ ] every `name_search` call site in `apps/api/app` reads the keyword from the version table; [ ] test on 18 (`args`) and 20 (`domain`).

### O20-15 — `formatted_read_group`
- **Status:** SEEDED in the version table and `read_plane.py`.
- **Pressure:** 5 → cheap
- **Acceptance:** [ ] aggregate call sites on 19+ send `formatted_read_group`; the legacy `read_group` shape is not sent on 20.

### O20-16 — 19-to-20 spec replay
- **Status:** OPEN
- **depends_on:** O20-06, T5B-02
- **Pressure:** C2 U2 F3 K2 V2 I1 +0 = 12 → Grok high effort
- **Acceptance:** [ ] a 19 config spec plan replayed on 20 either applies through the translators or fails with a named migration note; it never half-applies (assert zero writes after the first refused op); [ ] runbook 13 ("Odoo 20 spec that will not translate") written.
