# B0-RANDOM-ORDER: suite passes twice in random order (or reverse file order once)

ID: B0-RANDOM-ORDER
Title: suite passes twice in random order (or reverse file order once)
Status: todo
Phase: 0
Priority: P0
Type: test
TOKEN CHARTER: docs/build-plan/01_TOKEN_CHARTER.md applies. Budget: M (caps in budget.json). Stop at 80%.
Ledger IDs: P0-2-AC2;REL-7.6;P0-2-H001;P0-2-H002;P0-2-H003;P0-2-H004;P0-2-H005;P0-2-H006;P0-2-H007;P0-2-H008;P0-2-H009;P0-2-H010;P0-2-H011;P0-2-H012;P0-2-H013;P0-2-H014;P0-2-H015;P0-2-H016;P0-2-H017;P0-2-H018;P0-2-H019;P0-2-H020;P0-2-H021;P0-2-H022;P0-2-H023;P0-2-H024;P0-2-H025;P0-2-H026;P0-2-H027;P0-2-H028;P0-2-H029;P0-2-H030;P0-2-H031;P0-2-H032;P0-2-H033;P0-2-H034;P0-2-H035;P0-2-H036;P0-2-H037;P0-2-H038;P0-2-H039;P0-2-H040;P0-2-H041;P0-2-H042;P0-2-H043;P0-2-H044;P0-2-H045;P0-2-H046;P0-2-H047;P0-2-H048;P0-2-H049;P0-2-H050;P0-2-H051;P0-2-H052;P0-2-H053;P0-2-H054;P0-2-H055;P0-2-H056;P0-2-H057;P0-2-H058;P0-2-H059;P0-2-H060;P0-2-H061;P0-2-H062;P0-2-H063;P0-2-H064;P0-2-H065;P0-2-H066;P0-2-H067;P0-2-H068;P0-2-H069;P0-2-H070;P0-2-H071;P0-2-H072
Depends on: B0-INV, B0-GREEN
Routing: Worker: L2 (grok-4.7-xhigh) · Tester: T0 + L2 separate session · Reviewer: L2 separate session · Score: 3 (C0 U1 F1 K1 V0 I0)
Context pack:
- `sed -n '467p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- `sed -n '843p' docs/specs/INGENIUM_MASTER_HANDOVER.md`
- apps/api/tests/conftest.py
- apps/api/pytest.ini
- apps/web/vitest.config.ts
- docs/build-plan/FACTS.md
File allow-list:
- apps/api/tests/conftest.py
- apps/api/pytest.ini
- apps/web/vitest.config.ts
- apps/api/tests/test_b0_random_order.py (new)
- apps/api/tests/test_apply_readiness.py (xfail mark only)
- apps/api/tests/test_preview_proxy_reality.py (xfail mark only)
- apps/api/tests/test_admin.py (xfail mark only)
Goal: Make every AC below true for `B0-RANDOM-ORDER` and prove it with the Test plan; change nothing outside the allow-list.
Steps:
1. Read the context pack only. List the behaviours under test, one per AC, with concrete input → expected output.
2. Write the tests in the allow-list files. Each test must fail if the behaviour were removed: name in the Worker packet the product line whose deletion would make it fail.
3. Run the Test plan command twice (second time `-p randomly` for API once DEC-047 lands) → identical green results.
4. If a test exposes a real defect, do not fix product code: mark it `xfail(strict=True, reason=<new ledger row>)` and report it in the Worker packet.
5. Write the Worker packet.
6. STOP-AND-ASK: a needed file is outside the allow-list; an AC is ambiguous or contradicts another; a live check would need a non-`ingenium_` DB, a forbidden port, a git write or a new dependency; an oracle test looks wrong.
Acceptance criteria:
- AC1: the suite passes twice in a row with `pytest -p randomly` (or the repo's own random-order option), proving no order dependence. If no random-order plugin is installed, run the suite in reverse file order once. (source: INGENIUM_MASTER_HANDOVER.md L467)
- AC2: Rules: tests never touch the dev App DB or any non-`ingenium_` Odoo DB (P0-3, 6.7); no test depends on order; no test calls a real cloud AI unless marked and skipped by default. (source: INGENIUM_MASTER_HANDOVER.md L843)
Symbols:
- `pytest-randomly` is installed (commit `7fda3ab6`, DEC-047). Use the "yes" row below. Do not edit `pyproject.toml`.
- Existing order-leak fixture: `_isolate_ai_process_state` in `apps/api/tests/conftest.py`.
Worked example:
- When `pytest-randomly` is installed: `cd apps/api && uv run pytest -q -p randomly` twice. Both finish green.
- When it is not installed: `cd apps/api && uv run pytest -q $(find tests -name 'test_*.py' | sort -r)` finishes green.
Decision:
| `pytest-randomly` installed | proof |
| yes | the `-p randomly` command twice, both green |
| no | reverse file order, once, green |
2026-10-23 loop 1: narrow pin passed. Full `-p randomly` stopped at maxfail (4 failed, 2 errors, 206 passed). `test_apply_readiness.py` failed alone, so it is not an order leak and stays outside this allow-list. Loop 2 classifies the other five nodes. An isolation failure is named and not edited. A pass-alone failure may be fixed only in the allow-list. No xfail in a file this card cannot edit. No tester until both full runs are green.
2026-10-23 loop 2 STOP. Order leaks, fixed in `conftest.py` only: `test_persisted_card_is_scoped_to_the_connection`, `test_history_unknown_connection_404`, `test_history_merges_and_filters` (session engine restored). Isolation, outside the allow-list, not edited: `test_ensure_header_line_models_scaffolds_transfer_and_count_lines` (`x_branch_transfer_line` absent), `test_resolve_field_endpoint` (404), `test_admin_feature_flags_and_deactivate` (`plan_id` `internal` not in `billing_plans`). Full suite not re-run. Loops used: 2/2. Asking Tope before any allow-list add or xfail.
2026-10-23 Tope yes: those three files are on this allow-list for one `pytest.mark.xfail(strict=True)` each, on the test that fails alone. No skip, no file-level mark, no product code, no fixture edit. Ledger rows, assigned to the card that fixes the product: `P0-2-XFAIL-LINE` → `AS-CRAFT-APPLY` (scaffold in `ensure_header_line_models`; [Inferred] no card allow-lists `ai_apply_readiness.py`, and this apply card is the open apply owner). `P0-2-XFAIL-RESOLVE` → `EL-X-EDGE-RECORDS` (only card that may edit `routers/views.py`). `P0-2-XFAIL-PLAN` → `BILL-PLANS` (DEC-011, billing plan ids; bootstrap uses `internal`). Tester runs the narrow pin, `-p randomly` twice, and reverse file order twice. A new failure in any other file stops the card.
2026-10-23 tester FAIL. Pin 1 passed. First `-p randomly` exit 2: 81 failed, 1203 passed, 28 skipped, 1 xfailed, 2 errors. Runs 3–5 not started. Named files outside the three xfails: `test_ai_pack_project_tracker.py`, `test_bl_08.py`, `test_ai_conversation_intent_gate.py`, `test_tier_matrix.py`, `test_ai_pack_helpdesk.py`, `test_full_app_vehicle_request_must_do.py`, `test_pdf04_report_grounding.py`, `test_website_unsafe_gate.py`. Card stopped. No reviewer.
2026-10-23 Tope: split, do not patch the 81 on this card. Classify each of the 83 nodes in its own pytest process before any further code edit. The original `-q` log did not print a `randomly-seed` line, so "the same seed" could not be replayed. Each node ran as `uv run pytest -q -p no:randomly --tb=no <node>` with a 180s cap. 83 finished, 0 timeouts, 0 NF (`test_nf_*`, `app/bot_verify`, scans, assist, `migration_studio`). Result: 20 fail alone (list a, real failure), 63 pass alone (list b, order leak). The two original ERRORs (`test_website_unsafe_gate.py`) pass alone, so they are leaks.

List (a) fails alone:
- `tests/test_ai_pack_project_tracker.py::test_merge_deepens_thin_project_task`
- `tests/test_bl_08.py::test_ac2_negative_squashed_tracks_do_not_pass_on_their_own`
- `tests/test_bl_08.py::test_ac2_positive_each_commits_tests_pass_on_their_own`
- `tests/test_ai_conversation_intent_gate.py::test_stock_chip_after_simple_document_does_not_wipe_residual`
- `tests/test_ai_conversation_intent_gate.py::test_clarify_merge_sets_residual_app`
- `tests/test_ai_pack_helpdesk.py::test_helpdesk_finish_does_not_reattach_project`
- `tests/test_pdf04_report_grounding.py::test_default_qweb_uses_external_layout`
- `tests/test_ai_form_slots.py::test_sla_due_lands_in_dates_column_without_nested_group`
- `tests/test_ai_form_slots.py::test_notes_go_to_other_info_tab`
- `tests/test_ai_domain_agnostic_quality.py::test_pack_seed_scorecard_is_not_capped_by_stock_fk_or_reset_to_draft`
- `tests/test_ai_domain_agnostic_quality.py::test_collapse_omits_related_stock_documents_from_header_form`
- `tests/test_ai_domain_agnostic_quality.py::test_quality_closer_does_not_invent_stock_reverse_o2m_or_ops_status`
- `tests/test_ai_ollama.py::test_draft_module_with_monkeypatched_ollama`
- `tests/test_ai_model_quality.py::test_normalize_client_id_to_partner_and_rebuild_view`
- `tests/test_ai_model_quality.py::test_ghost_hearing_auto_remap_and_parent_o2ms`
- `tests/test_job_autopilot.py::test_run_endpoint_refuses_production`
- `tests/test_job_autopilot.py::test_run_endpoint_attaches_in_flight_job`
- `tests/test_job_autopilot.py::test_run_endpoint_queues_sandbox`
- `tests/test_job_autopilot.py::test_promote_to_endpoint_requires_confirm`
- `tests/test_job_autopilot.py::test_packet_endpoint_json`

List (b) passes alone (order leak). Owned by `B0-RANDOM-ORDER-b`. No xfail and no skip:
- `tests/test_tier_matrix.py::test_capability_matrix_endpoint`
- `tests/test_tier_matrix.py::test_capability_matrix_endpoint_requires_version`
- `tests/test_full_app_vehicle_request_must_do.py::test_vehicle_request_must_do_structured[Make]`
- `tests/test_full_app_vehicle_request_must_do.py::test_visitor_log_regression_untouched`
- `tests/test_full_app_vehicle_request_must_do.py::test_vehicle_request_must_do_structured[Build]`
- `tests/test_full_app_vehicle_request_must_do.py::test_vehicle_request_must_do_structured[Create]`
- `tests/test_prefer_field_pack_no_clarification_leak.py::test_prefer_siblings_no_json_leak[Extend Contacts: add Loyalty tier and membership window (start and end dates). Show a status hint when tier is set. Do not create a new app — inherit res.partner.-res.partner-Loyalty]`
- `tests/test_prefer_field_pack_no_clarification_leak.py::test_tope_sales_generate_ir_clean_after_confirm`
- `tests/test_role_matrix.py::test_superadmin_console_role_matrix[admin-403]`
- `tests/test_role_matrix.py::test_billing_checkout_role_matrix[admin-200]`
- `tests/test_role_matrix.py::test_superadmin_console_role_matrix[viewer-403]`
- `tests/test_role_matrix.py::test_projects_slot_limit_role_matrix[owner-403]`
- `tests/test_role_matrix.py::test_expert_ask_role_matrix[viewer-200]`
- `tests/test_role_matrix.py::test_connections_create_role_matrix[admin-201]`
- `tests/test_role_matrix.py::test_all_roles_read_connections`
- `tests/test_role_matrix.py::test_connections_delete_role_matrix[admin-204]`
- `tests/test_role_matrix.py::test_connections_delete_role_matrix[viewer-403]`
- `tests/test_role_matrix.py::test_invitations_create_role_matrix[owner-201]`
- `tests/test_role_matrix.py::test_expert_ask_role_matrix[admin-200]`
- `tests/test_role_matrix.py::test_bulk_read_role_matrix[owner-200]`
- `tests/test_role_matrix.py::test_projects_slot_limit_role_matrix[builder-403]`
- `tests/test_role_matrix.py::test_expert_ask_role_matrix[builder-200]`
- `tests/test_role_matrix.py::test_bulk_read_role_matrix[viewer-200]`
- `tests/test_role_matrix.py::test_automations_pcm_role_matrix[owner-422]`
- `tests/test_role_matrix.py::test_automations_pcm_role_matrix[builder-422]`
- `tests/test_role_matrix.py::test_invitations_create_role_matrix[admin-201]`
- `tests/test_role_matrix.py::test_connections_delete_role_matrix[owner-204]`
- `tests/test_role_matrix.py::test_expert_ask_role_matrix[owner-200]`
- `tests/test_role_matrix.py::test_superadmin_console_role_matrix[builder-403]`
- `tests/test_role_matrix.py::test_connections_create_role_matrix[owner-201]`
- `tests/test_role_matrix.py::test_connections_create_role_matrix[viewer-403]`
- `tests/test_role_matrix.py::test_projects_slot_limit_role_matrix[viewer-403]`
- `tests/test_role_matrix.py::test_invitations_create_role_matrix[builder-403]`
- `tests/test_role_matrix.py::test_superadmin_console_role_matrix[owner-403]`
- `tests/test_role_matrix.py::test_projects_slot_limit_role_matrix[admin-403]`
- `tests/test_role_matrix.py::test_billing_checkout_role_matrix[owner-200]`
- `tests/test_role_matrix.py::test_invitations_create_role_matrix[viewer-403]`
- `tests/test_role_matrix.py::test_connections_create_role_matrix[builder-201]`
- `tests/test_role_matrix.py::test_automations_pcm_role_matrix[admin-422]`
- `tests/test_role_matrix.py::test_bulk_read_role_matrix[builder-200]`
- `tests/test_role_matrix.py::test_billing_checkout_role_matrix[builder-403]`
- `tests/test_role_matrix.py::test_billing_checkout_role_matrix[viewer-403]`
- `tests/test_role_matrix.py::test_automations_pcm_role_matrix[viewer-422]`
- `tests/test_role_matrix.py::test_bulk_read_role_matrix[admin-200]`
- `tests/test_role_matrix.py::test_connections_delete_role_matrix[builder-403]`
- `tests/test_role_matrix.py::test_viewer_cannot_invite`
- `tests/test_trust8_production_readiness.py::test_production_mode_blocked_until_checklist`
- `tests/test_trust8_production_readiness.py::test_incomplete_checklist_uses_todo_not_fail`
- `tests/test_trust8_production_readiness.py::test_drill_prefers_tracked_snapshot`
- `tests/test_trust8_production_readiness.py::test_first_write_ack_persisted`
- `tests/test_trust8_production_readiness.py::test_broken_health_is_fail_not_todo`
- `tests/test_trust8_production_readiness.py::test_admin_user_requires_acknowledge`
- `tests/test_trust8_production_readiness.py::test_snapshot_drill_and_full_checklist_pass`
- `tests/test_trust8_production_readiness.py::test_evaluate_todos_without_probe`
- `tests/test_state_title_identity_spray_class.py::test_maintenance_title_not_build_maintenance`
- `tests/test_t6_04_inbox_binding.py::test_rt20_freeze_window_blocks_approve`
- `tests/test_t6_04_inbox_binding.py::test_decide_fingerprint_mismatch_returns_409_plan_stale`
- `tests/test_t6_04_inbox_binding.py::test_rt17_replay_on_modified_plan_is_refused`
- `tests/test_t6_04_inbox_binding.py::test_deny_and_stop_is_a_decide_choice`
- `tests/test_t6_04_inbox_binding.py::test_rt19_expired_approval_is_refused_at_apply`
- `tests/test_residual_optional_satellite_primary.py::test_generate_primary_is_brief_noun[Build Vehicle request: employees request a fleet vehicle for a date range; manager approve/refuse; on approve, optionally link/create a Fleet vehicle assignment note. List/kanban by state (Draft → Submitted → Approved/Refused → Done). Menu under Fleet or HR — pick the more natural parent.-x_vehicle_request-Vehicle Request]`
- `tests/test_website_unsafe_gate.py::test_refuse_script_on_save_api`
- `tests/test_website_unsafe_gate.py::test_allow_plain_save`

2026-10-23 second full `-p randomly` (seed `1766196243`, ~51 min) exit 1. The summary counts were dropped when the log was truncated. The captured tracebacks are `sqlite3.OperationalError: no such table: users`. That run is not a new classification. Default pin after `addopts = -p no:randomly`: `tests/test_b0_random_order.py` 1 passed.
2026-10-23 default1 (shuffle off, alone) `201 failed, 5587 passed, 48 skipped, 3 xfailed, 540 errors` in `/tmp/B0-RANDOM-ORDER_default1.txt`. default2 was stopped so it would not share the database. HEAD conftest outside the repo: `test_sec_gate_scope.py` 464 passed; the two alembic nodes fail with `database=postgres` (pre-existing guard); `test_reg_np_t6.py` 6 failed, 16 passed. The 540 errors were the leak-fix restoring the URL but leaving `SessionLocal` on SQLite. conftest now restores the engine before the next import, reapplies a swap module's engine only for its tests, and rebinds copied `SessionLocal` names. Combo gnd+t6+sec_gate+role_matrix: 536 passed. Rooted HEAD baseline (old conftest, repo-depth copy, shuffle off): 470 failed, 4985 passed, 52 skipped, 4 xfailed, 364 errors in 12:21. Log `/tmp/B0-RANDOM-ORDER_baseline.txt`. Node ids: baseline `/tmp/B0-RANDOM-ORDER_baseline_nodes.txt` (834), default_a `/tmp/B0-RANDOM-ORDER_default_a_nodes.txt` (74), both 72 (`P0-2-H001`–`P0-2-H072`), fixed-by-card 762. New before the last conftest edit: admin strict xfail (session DB kept billing plan `internal`; fixture now deletes that plan) and `test_b0_green_web_tsc_no_emit_exits_zero` (uncommitted `Tooltip.tsx`, ledger `P0-2-TSC-UIB`; the copy's root has no `apps/web`, so the baseline did not run that check). Post-fix green-bar pair is `/tmp/B0-RANDOM-ORDER_default_c.txt` then `default_d.txt`.

Suite-run assertion lines for list (a), taken from the first `-p randomly` log. A fresh alone traceback was not captured: the first node hung past 180s, the script did not kill the child, and a 45s retry also hung while another full `-p randomly` process is on Postgres `54329`. The orphan was reaped. These lines are the suite traceback, not a second alone run:
- `test_merge_deepens_thin_project_task`: `x_project_id` is not in `{x_name, x_status}`
- `test_ac2_negative_squashed_tracks_do_not_pass_on_their_own` and `test_ac2_positive_each_commits_tests_pass_on_their_own`: git status still shows uncommitted `apps/api/app/changeset`, so AC2 refuses
- `test_stock_chip_after_simple_document_does_not_wipe_residual`: assessment text has no `Custom residual: named in brief`
- `test_clarify_merge_sets_residual_app`: `ir_confidence` is `low`, not `high` or `medium`
- `test_helpdesk_finish_does_not_reattach_project`: no model `x_ticket_time_line` (`StopIteration`)
- `test_default_qweb_uses_external_layout`: `DEFAULT_QWEB` still contains `web.html_container`
- `test_sla_due_lands_in_dates_column_without_nested_group`: `x_sla_due` is not in `{x_sla_due_date_on_invoices}`
- `test_notes_go_to_other_info_tab`: `x_notes` is not in `{x_notes_field_on_vendor_bills}`
- `test_pack_seed_scorecard_is_not_capped_by_stock_fk_or_reset_to_draft`: `assert not True`
- `test_collapse_omits_related_stock_documents_from_header_form`: the form still contains `name="x_lead_id"`
- `test_quality_closer_does_not_invent_stock_reverse_o2m_or_ops_status`: `('pending', 'blocked')` is not an allowed pair
- `test_draft_module_with_monkeypatched_ollama`: technical name is `artisan_commission_studio`, not `demo_books`
- `test_normalize_client_id_to_partner_and_rebuild_view`: `action_x_event` is not in `{None, action_x_matter}`
- `test_ghost_hearing_auto_remap_and_parent_o2ms`: `x_task` is not in `{x_event}`
- five `test_job_autopilot.py` endpoint nodes: response is 404 `Connection not found`
Test plan:
- `cd apps/api && uv run pytest -q tests/test_b0_random_order.py` → plugin installed, shuffle off
- `cd apps/api && uv run pytest -q` twice → both green. Random order is not on in this default.
- Opt-in, not this card's green bar: `-p randomly`, or `PYTEST_ADDOPTS='-p randomly'`
- The two `test_bl_08.py` AC2 nodes stay unmarked. They fail because `apps/api/app/changeset` is uncommitted. A strict xfail would go red on the commit that clears that.
- List (a) other than those two gets strict xfails. List (b) is `B0-RANDOM-ORDER-b`.
Common mistakes: direct `execute_kw` outside the write gate; LLM calls outside `app/ai_client`; positional xpath; `attrs`; `<tree>` vs `<list>` by major; tests touching a non-`ingenium_` DB; restarting `:8001` (it runs without --reload).
Gate: none (no Tope gate). Narrowest named test green → Tester PASS (separate session; runs the oracle tests unmodified) → Reviewer PASS (separate session; checks INV-01..18, the allow-list and the ACs line by line).
Evidence to log: One line in `apps/api/evals/v2/PROGRESS.md`: date · card ID · command · result counts · label ([Done, code] or [Done, live]). Tester packet and Reviewer verdict summary in `STATE.md` token ledger.
Rollback: Revert this card's diff (allow-list files only). Odoo changes made during checks exist only in dropped `ingenium_*` DBs; any product write path keeps its snapshot + Undo (History).
Definition of Done: Every AC has evidence; oracle tests unmodified and green; no file outside the allow-list changed; Orchestrator updates the ledger rows; Status set to done.
