# 17 — Coverage matrix

Every ID family from the ingested sources has a home in the pack, a count, and the card that builds or proves it. A checker fails this file if any count is short. Locations are pack files, not the Downloads folder. Card files are under `cards/`, and screen cards are in `13`.

## ID families

| Family | Expected count | Spec location | Card(s) |
|---|---|---|---|
| INV-01–INV-20 | 20 | `01` | Every card's do-not list; T8-POLICY, T8-S08 |
| ADR-01–ADR-14 | 14 | `T8_BOT_ENGINE.md` | ADR-01–14 rows in `cards/T8_ENGINE_CORE.md`, BL-05 |
| Decisions D1–D12 | 12 (D8 open) | `01` | ADR-02 (D8), L4-01–12 (D10), O20-* (D11), UI-F04–F11 (D12) |
| Conflict rows | 18 (15 + 3) | `01` | — (decision record) |
| Never-allowed method tuples | 5 | `01`, `T5`, `cards/T5A_GUARDRAILS.md` | 5A-01, 5A-04, 5C-07, L4-11 |
| Protected param keys | 6 | same | 5A-01, 5A-04 |
| Never-automate areas | 12 | `01` | T8-PROT, L4-02 |
| PF-1–PF-6 | 6 | `T1` | T1-PF |
| T1–T12 verdicts | 12 | `T1` | T1-GATE |
| PR-F.0, A–F | 7 steps | `T1` | T1-F0, T1-A1–A4, T1-B1–B3, T1-C1–C2, T1-D1–D3, T1-E1–E2, T1-F1–F3 |
| PR-J1–J4 | 4 | `T2` | T2-J1–J4, T2-SMOKE |
| Bridge phases 0–4 | 5 | `T3` | BR-00, BR-01–05, BR-06–10, BR-11, BR-13 |
| Verification tiers I–III | 3 | `T3` | BR-01, BR-06, BR-07 |
| Connector tiers 3a–3c | 3 | `T3` | BR-06, BR-08, BR-10 |
| Connector methods | 6 | `T3` | BR-05 |
| MCP phases 0, 1, 5 | 3 | `T4` | T4-MCP0, T4-MCP1, T4-MCP5 |
| Compiler DoD 1–20 | 20 | `T4`, `15` | T4-ISPEC (1–2), T4-SYNC (3–5), T4-BROWSER (6–7), T4-PROG (8–10), T4-GROUND (11, 13, 14), T4-WIRE (12), T4-SKT (15–18), T4-E2E (19–20) |
| Bucket B features | 5 | `T4` | T4-DASH, T4-OFF, T4-ISPEC, T4-WIRE, T4-LLM3 |
| READ_METHODS | 12 names | `T5`, `cards/T5A` | 5A-01 |
| SENSITIVE_MODELS | 23 names | same | 5A-01 |
| DESTRUCTIVE_METHODS | 24 names | same | 5A-01, 5A-06 |
| BILLABLE_METHODS | 7 patterns | same | 5A-01, 5A-06 |
| YAML sections | 47 | `T5`, `cards/T5B` | 5B-01 |
| Master DoD 1–32 | 32 | `15` | Named per card in its acceptance |
| New DoD 33–40 | 8 | `15` | Named per card |
| E2E steps | 8 | `15` | T8-P5-E2E, T4-E2E |
| R0–R4 | 5 | `02` | T8-RISK, T8-POLICY |
| Policy cells | 10 | `02` | T8-POLICY |
| Approval steps | 15 | `02` | T6-04, T6-05, T6-06, UI-S-50 |
| L0–L4 | 5 | `02` | 5C-01–03, L4-01–12 |
| GATE-L4-01–12 | 12 | `01`, `cards/T5C` | L4-01–L4-12 (one card per gate) |
| C01–C20 | 20 | `T8` | T8-GW-C, T8-S17 |
| Op types | **62** | `cards/T8_ENGINE_CORE.md` family tables | T8-OP-SCHEMA, UI, LOGIC, SEC, SET, DATA — split set verified equal to `len(OP_CATALOG)` = 62 on 2026-10-02 |
| Validation stages | 9 | `02`, `T8` | T8-VALID |
| Engine suites 1–18 | 18 | `T8`, `cards/T8_SUITES_SKILLS_EVALS.md` | T8-S01–T8-S18 |
| RT-01–RT-48 | 48 | `T8`, same | T8-RT-A (01–09), T8-RT-B (10–16), T8-RT-C (17–27), T8-RT-D (28–36), T8-RT-E (37–48) |
| GATE-P0 | 5 | `T8` | BL-06, T8-P0-FIX, T8-P0-LINT |
| GATE-P1 | 8 | `T8` | T8-GW-* |
| GATE-P2 | 9 | `T8` | T8-OD-* |
| GATE-P3 | 10 | `T8` | T8-PROT … T8-P3-COV |
| GATE-P4 | 8 | `T8` | T8-RUN … T8-P4-TIERA, T8-ROUTER |
| GATE-P5 | 6 | `T8`, `cards/T8_BOTS_PILOTS.md` | T8-P5-E2E, PAGE, SSE, RBAC, A11Y, KILL |
| GATE-P5B | 11 | same | T8-BOT-* and T8-BOT-GATES |
| GATE-P6 | 6 | `T8` | T8-P6, T8-EV-* |
| GATE-P7 | 7 | `T8` | T8-CI, CHAOS, PEN, PRIV, RUNBOOK, KILL, SBOM |
| GATE-P8 | 5 | `T8` | T8-P8-PILOTS, RUN, TRUST, GA |
| Phase gates total | 75, plus GATE-L4's 12 = 87 | `T8`, `01` | — |
| Skills by family | 31 + 34 + 22 + 11 + 12 + 52 + 11 + 8 + 7 = 188 | `T8` | T8-SK-T1-* (16 tier-1), T8-SK-FAM-A–I; 188 stubs verified (`len(all_skills())` = 188) |
| EV families | FLD 18, AUT 8, SEC 8, DATA 8, CFGBOT 15, BOT 16, APP 16, RPT 5, AMB 8, REF 8, DIAG 8, VER 8, LONG 4, RECOV 4, STUDIO 8, ACCESS 8 | `T8` | T8-EV-SEED, ASSIGN, INJ, CFG, BOT |
| J1–J12 | 12 | `T8`, `cards/T8_BOTS_PILOTS.md` | T8-P8-PILOTS |
| O20-01–O20-16 | 16 | `T9`, `cards/T9_ODOO20.md` | O20-01–16 |
| Version-table rows | **32** (V01–V32) | `cards/T9_ODOO20.md` | O20-06 (one test per row; `version_table.py` covers 19 of 32 today) |
| Capability areas 1.2.1–1.2.17 | 17 | `T5`, `T9`, `T8`, `01` | 5B-*, O20-*, T8-SK-FAM-* |
| Blueprint gotchas | 40 (20-specific subset inlined) | `T9` | O20-06, 5B-04 must not contradict |
| Oracle test names | **129** (119 unit + 10 live) | this file, §Oracle | see §Oracle |
| UX audit rows | 12 | `T7` | every UI-F and UI-S card |
| Copy dimensions | 9 | `T7` | every UI card that changes copy |
| UI routes specified | 54 blocks (UI-S-01–62, some numbers unused) | `13` | UI-S-* |
| UI foundation | 13 + 8 splits | `cards/T7_UI_FOUNDATION.md` | UI-F00–F12, UI-SP-* |
| Risks R-01–R-25 | 25 | `16` | — |
| Runbooks | 13 | `11` | T8-RUNBOOK; L4-09 writes runbook 12 |
| Test-type rows | 35 | `10` | — |
| Agent-spec open questions §16.8 | 17 | `18` | — |
| Work cards | 330 | `14` | — |

## Count checks

- Skills: 31 + 34 = 65, +22 = 87, +11 = 98, +12 = 110, +52 = 162, +11 = 173, +8 = 181, +7 = 188.
- Gates: P0 5 + P1 8 + P2 9 + P3 10 + P4 8 + P5 6 + P5B 11 + P6 6 + P7 7 + P8 5 = 75. Adding GATE-L4's 12 gives 87 gate ids. The agent spec's own gates are the 75. GATE-L4 is authored by this pack and labeled as such.
- Ops: the slash-split names in the six family cells equal `OP_CATALOG` exactly (62, script diff on 2026-10-02). After any code change, re-run that diff; it wins over any hand count.
- Oracle: 11 + 18 + 9 + 10 + 7 + 5 + 2 + 13 + 44 = 119 unit, + 10 integration = 129.

## Oracle test names (odoo-config-agent, names only, never vendored)

These are the behaviors our own tests must cover. Write our tests against our code; do not copy the oracle's code (lock: do not vendor `odoo-config-agent`). Each module maps to the card that ports it.

| Module (count) | Card | Test names |
|---|---|---|
| `test_agent.py` (11) | T8-RUN, T8-TOOLS, 5A-10 | test_tool_schemas_are_valid_json_schema, test_system_prompt_renders, test_dry_run_then_apply_flow, test_production_requires_approval_and_denial_is_respected, test_forbidden_and_unknown_tools, test_prompt_injection_is_wrapped_as_data, test_step_budget, test_context_compaction_keeps_tool_pairs, test_openai_wire_roundtrip, test_anthropic_wire_roundtrip, test_settings_and_install_tools |
| `test_client.py` (18) | T2-J2, 5B-02, 5B-06 | test_connect_detects_version, test_repr_hides_secret, test_private_methods_refused, test_ensure_create_then_unchanged_then_update, test_ensure_dry_run_writes_nothing, test_ensure_rejects_unknown_field, test_ensure_ambiguous_natural_key, test_ensure_m2m_additive_and_m2o_normalisation, test_settings_diff_and_execute, test_install_modules, test_read_retries_but_write_does_not, test_on_write_hook, test_ref_missing, test_validation_error_class, test_describe_model, test_json2_named_arguments, test_json2_http_contract, test_jsonrpc_http_contract |
| `test_errors_versions.py` (9) | O20-06, T8-OD-TRANSPORT | test_parse_traceback, test_xmlrpc_fault_traceback, test_xmlrpc_fault_access_denied, test_jsonrpc_error_mapping, test_version_parse, test_version_info_wins, test_product_types_by_version, test_model_renames_and_fields, test_xmlrpc_fault_codes |
| `test_guardrails_audit.py` (10) | 5A-01, 5A-05, 5A-10 | test_read_is_read, test_create_is_reversible, test_unlink_destructive_and_forbidden, test_security_models_destructive, test_billable_depends_on_edition, test_protected_params_forbidden, test_mass_write, test_policy_thresholds, test_audit_chain_and_tamper, test_redaction |
| `test_importers.py` (7) | 5B-06 | test_phone_normalisation, test_duplicates_in_sample, test_template_from_fields, test_validate_bad_file, test_validate_good_file_and_load, test_selection_and_numeric_validation, test_blank_values_are_not_duplicates |
| `test_knowledge_cli.py` (5) | T8-MEM, T8-CLI | test_chunks_and_search, test_build_index_offline, test_memory, test_cli_parser, test_cli_plan_with_fake |
| `test_server.py` (2) | T6-04 | test_run_with_approval_roundtrip, test_default_app_unknown_project_fails_cleanly |
| `test_spec.py` (13) | 5B-01, 5B-02, 5B-03, 5B-07, 5B-08, 5B-09 | test_example_spec_is_valid, test_adopt_example_compiles, test_schema_errors, test_duplicate_keys_rejected, test_version_aware_compilation, test_custom_field_requires_x_prefix, test_plan_apply_idempotent, test_fingerprint_drift_detected, test_destructive_changes_need_approval, test_production_requires_approval_for_everything, test_key_field_reference_and_placeholders, test_errors_block_apply, test_read_back_verification_flags_ignored_writes |
| `test_versions_profiles.py` (44) | O20-02, O20-04, O20-06, O20-07, O20-14, O20-15, 5B-04 | test_parse_versions, test_serie_and_prerelease, test_profiles_cover_15_to_20_and_20_is_latest, test_saas_uses_lower_major_profile, test_unknown_versions_are_extrapolated, test_register_future_profile_with_derive, test_version_differences_by_profile, test_notes_for_migration_from_19_to_20, test_pricelist_percentage_to_discount_on_20, test_pricelist_discount_back_to_percentage_before_20, test_pricelist_fixed_is_unchanged_everywhere, test_crud_operation, test_access_rights_compile_to_ir_access_on_20, test_access_rights_with_domain_compile_to_access_plus_rule_before_20, test_record_rules_on_20, test_record_rules_unchanged_before_20, test_fiscal_position_mapping_by_version, test_report_layout_translation_on_20, test_pricelist_and_bom_and_accounts_on_20, test_products_uom_po_only_before_19_and_cron_numbercall_only_before_18, test_users_group_field_on_20, test_choose_protocol, test_looks_like_api_key, test_auto_falls_back_from_json2_to_xmlrpc_on_404, test_explicit_protocol_does_not_fall_back, test_ui_url_style, test_capabilities_refine_profile_with_live_probes, test_capabilities_keep_profile_default_when_anchor_model_missing, test_engine_on_fake20_translates_category_alias_and_fpos, test_company_registry_becomes_additional_identifier_on_20, test_json2_named_arguments_match_19_20_orm, test_group_by_uses_formatted_read_group_on_19_plus_and_read_group_before, test_selection_probe_distinguishes_pricelist_modes, test_odoo20_security_models_are_destructive, test_version_briefing_for_20_mentions_key_changes, test_version_profile_tool_and_system_prompt_on_fake20, test_cli_profile_offline, test_uom_category_mapping_by_version, test_name_search_keyword_is_args_up_to_18_and_domain_from_19, test_profile_19_is_tested_live_and_matches_live_facts, test_auto_protocol_with_password_on_19_explains_why, test_briefing_flags_enterprise_builds_as_untested, test_snapshot_refuses_on_odoo_sh_and_online, test_briefing_trims_oldest_notes_first |
| `integration/test_live.py` (10, OPERATOR: live instance) | O20-11, T2-SMOKE, 5B-02 | test_connection_and_introspection, test_ensure_is_idempotent, test_settings_dry_run, test_example_spec_converged, test_flows, test_import_validate_and_load, test_bad_file_rejected, test_agent_tool_loop_live, test_version_profile_and_capabilities_live, test_version_sensitive_calls_live |

Not ported: `test_profiles_cover_15_to_20…` includes 15. Our port asserts that 15 is **refused** (the lock refuses majors ≤ 15), not that it is covered. `test_saas_uses_lower_major_profile` maps to OQ-VERSIONS.

## Known soft mismatches kept on purpose

- The brief said "about 55 ops"; the code and the family tables both give 62 (measured). 62 is authoritative.
- The brief said "about 120 oracle test names"; the oracle has 129 (119 unit + 10 live). All 129 are listed.
- SK-APP's overview said "~50"; 52 are listed.
- GATE-P5B-11 is specified between 08 and 09 in the source. All eleven ids exist.
- EV families that had no numbers were given ids by this pack, not copied from a source.
- Blueprint unit-test totals 79 / 123 / 124 are not gates.

## Checker rule

A reviewer counts INV, RT, C, GATE-P*, GATE-L4, skills by family, master DoD, O20 rows, version rows, ops, and oracle names in this pack. A short count fails the review. Adding a gate is allowed. Removing one is not.
