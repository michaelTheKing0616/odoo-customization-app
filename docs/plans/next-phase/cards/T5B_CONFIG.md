# Cards — T5B declarative config (D7: reimplement, oracle the package)

Self-contained. Source rules: `../T5_GUARDRAILS_CONFIG_WORKERBOTS.md` lines 118–142. The oracle is `odoo-config-agent` tests, ported by name. The package is never imported.

**Shared do-not:** do not weaken a lock in `../01`; no secrets in logs; no customer database; `:8001` does not reload; never loosen a test; no live LLM in PR tests; stay inside "Change". **T5B-specific:** `secret:` is a vault pointer, never a literal; `x_` prefix required and `x_studio_*` rejected; blocked items skipped unless `--include-blocked`; production apply needs an explicit acknowledgement flag **and** `write_mode=production` on the connection stays refused (the flag is for a sandbox or a confirmed staging connection); every apply goes through the change-set engine (`apps/api/app/changeset/`) so the plan hash, policy, and audit are shared; Nigeria figures (VAT 7.5%, WHT 5% and 10%) are illustrative and the accountant decides; PAYE, PenCom, and NHF come from a specialist, never from the model.

**YAML shape (copied).** Top-level keys `version`, `project`, `description`, `target`, then 47 sections applied in this order:

`modules`, `languages`, `currencies`, `companies`, `settings`, `users`, `sequences`, `mail_servers`, `tax_groups`, `accounts`, `taxes`, `journals`, `payment_terms`, `fiscal_positions`, `analytic_plans`, `analytic_accounts`, `product_categories`, `product_attributes`, `warehouses`, `locations`, `operation_types`, `routes`, `products`, `pricelists`, `reorder_rules`, `putaway_rules`, `crm_stages`, `sales_teams`, `sale_templates`, `workcenters`, `boms`, `departments`, `jobs`, `employees`, `leave_types`, `pos_payment_methods`, `pos_configs`, `projects`, `task_stages`, `custom_fields`, `views`, `server_actions`, `automations`, `crons`, `access_rights`, `record_rules`, `records`.

Entry fields: `key`, `xmlid`, `match`, `company`, `values`, `create_only`, `note`. Refs: `key:`, `ref:`, `find:`, `name:`, `secret:`, optional `?` prefix.

**Import rules (copied):** CSV `id` column always; prefer `field/id`; order categories → products → partners → pricelists → opening stock → opening GL; dates `YYYY-MM-DD`; validate against `fields_get`; prefer `load()`; batch 500; context `tracking_disable`, `mail_create_nolog`, `mail_notrack`; phone normalized to `+234…`; fuzzy name dedupe ≥ 0.92 with 3-character blocks; blank cells are never a dedupe key; partner merge is DESTRUCTIVE; opening balances need approval; posting is DESTRUCTIVE.

**Shared commands:**

```bash
cd apps/api && ../../.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_bridge_and_config_spec.py tests/test_config_apply.py tests/test_importers.py tests/test_l10n_ng_adopt.py
```

**Audit events:** `settings`, `change`, `module`, `apply`.

---

### 5B-01 — Schema: 47 sections in apply order
- **Status:** DONE for the loader (`config_as_code/loader.py`; `test_spec_section_count_and_order`, `test_literal_password_is_rejected`, `test_secret_pointer_and_x_field_compile`, `test_studio_field_prefix_is_rejected`, `test_unknown_section_is_rejected`).
- **Pressure:** 6 → Grok standard
- **Open delta:** port oracle `test_example_spec_is_valid`, `test_schema_errors`, `test_duplicate_keys_rejected`, `test_key_field_reference_and_placeholders` by name.

### 5B-02 — Idempotent apply through the change-set engine
- **Status:** SEEDED. `config_as_code/apply.py` (27 lines) applies to an in-memory `MemoryDb`; `test_second_apply_writes_nothing` passes. Not wired to Odoo or to the change-set executor.
- **depends_on:** 5B-01, T8-EXEC (Mode C at least)
- **Pressure:** C2 U2 F2 K3 V1 I1 +0 = 11 → Grok high effort
- **Read first:** `config_as_code/apply.py`, `config_as_code/loader.py` (`compile_plan`), `changeset/executor.py` (`apply`), `changeset/ops.py` (op names).
- **Steps:**
  1. Map each compiled plan entry to a closed-catalog op (`config_record.upsert`, `setting.set`, `field.create`, `access.create`, …). An entry with no op fails compile with a named error.
  2. Upsert by xmlid (INV-14). Read-before-write: no write when values equal.
  3. Submit as a change-set; apply through the executor with a fake `OdooPort`.
- **Acceptance:** [ ] second apply writes nothing against the fake port (count port calls = 0); [ ] oracle `test_plan_apply_idempotent`, `test_adopt_example_compiles`, `test_errors_block_apply`.
- **Negative:** an entry with a type mismatch blocks the whole apply before any write.

### 5B-03 — Fingerprint drift aborts
- **Status:** OPEN (compile fingerprint is stable; abort-on-drift at apply not tested).
- **depends_on:** 5B-02
- **Pressure:** 9 → Grok standard
- **Acceptance:** [ ] edit the fake database between plan and apply; apply aborts with `plan_drift`; oracle `test_fingerprint_drift_detected`.

### 5B-04 — Version briefing, probed live
- **Status:** OPEN
- **depends_on:** O20-06
- **Pressure:** C2 U2 F2 K2 V2 I0 +0 = 10 → Grok high effort
- **Acceptance:** [ ] the briefing is generated from `EnvProfile` probes (`packages/odoo-client/src/odoo_client/env_profile.py`), not a static paragraph; [ ] oracle names: `test_version_briefing_for_20_mentions_key_changes`, `test_briefing_flags_enterprise_builds_as_untested`, `test_briefing_trims_oldest_notes_first`, `test_capabilities_refine_profile_with_live_probes`, `test_capabilities_keep_profile_default_when_anchor_model_missing`.
- **Negative:** a probe that fails yields "unknown", and unknown means no.

### 5B-05 — `l10n_ng` adopt by xmlid
- **Status:** SEEDED (`config_as_code/l10n_ng.py`; `test_xmlid_shape`, `test_adopts_existing_tax`, `test_refuses_to_duplicate_a_missing_tax`).
- **Pressure:** 6 → Grok standard
- **Acceptance:** [x] adopt `account.<company_id>_l10n_ng_*`; [x] no duplicate tax; [ ] a live check on a sandbox with `l10n_ng` installed (operator).

### 5B-06 — Importers
- **Status:** SEEDED (`config_as_code/importers.py`: `normalize_ng_phone`, `is_blank`, `dedupe_key`, `fuzzy_name_match`). `load()` batching (500), the context flags, and `fields_get` validation are missing.
- **depends_on:** 5B-02
- **Pressure:** C2 U1 F2 K2 V1 I0 +0 = 8 → Grok standard
- **Acceptance:** [ ] batch of 500 through `load()`; [ ] the three context flags set; [ ] validation against `fields_get` before load; [ ] oracle `test_phone_normalisation`, `test_duplicates_in_sample`, `test_template_from_fields`, `test_validate_bad_file`, `test_validate_good_file_and_load`, `test_selection_and_numeric_validation`, `test_blank_values_are_not_duplicates`.
- **Negative:** a file with 30 bad rows reports all 30 and loads none (EV-DATA-03).

### 5B-07 — Custom fields
- **Status:** DONE for the loader rule (`test_studio_field_prefix_is_rejected`). Oracle `test_custom_field_requires_x_prefix` to port by name.
- **Pressure:** 3 → cheap

### 5B-08 — Oracle port
- **Status:** PARTIAL. Port every name in `../17_COVERAGE_MATRIX.md` §"Oracle test names" for `test_spec.py` (13), `test_importers.py` (7), and `test_versions_profiles.py` (44). Several are listed on 5B-01 to 5B-06 and O20-06 above.
- **Pressure:** C2 U1 F1 K1 V0 I0 +0 = 5 per batch → cheap; one card per oracle file is fine (5B-08a spec, 5B-08b importers, 5B-08c profiles)
- **Acceptance:** [ ] each oracle name has an Ingenium test with the same name (or the oracle name in its docstring) and the same assertion intent.
- **Do not:** copy the oracle test bodies; rewrite them against Ingenium's modules.

### 5B-09 — Approval for destructive config
- **Status:** OPEN
- **depends_on:** 5B-02
- **Pressure:** 8 → Grok standard
- **Acceptance:** [ ] oracle `test_destructive_changes_need_approval`, `test_production_requires_approval_for_everything`, `test_read_back_verification_flags_ignored_writes`, `test_version_aware_compilation`; [ ] the plan card for a config apply renders through `changeset/plan_card.py`.
