# Commit plan

Card BL-08. This file only proposes commits. Nothing in it has been committed.

Each commit waits for Tope's yes. Do not force-push. Do not push. Do not reset. Do not put unrelated folders in one commit.

Left out on purpose: `.cache/`, `.pnpm-store/`, folders named `__pycache__`, and files whose names start with `0001-` and end with `.patch`.

Today's check used `git status --short` on `apps/api/app` and `packages`, the same trees the locked test reads. A new uncommitted folder or file under `apps/api/app/` keeps the first check open. A new uncommitted source file under `packages/` keeps it open when that file sits in a `src` folder. Tests do not. The old pack named these folders on 2026-10-02 as new and uncommitted. This plan uses today's `ls` and `git status`, not that older label.

There are 63 new product folders and files. Until they are committed, the first check stays open. The second check stays open for the same reason: a commit that does not exist yet cannot have its tests run on their own.

Each new or changed test file is added in one commit. The pytest command on a row still runs every test that imports that folder, including a test file added in another commit.

Suggested order is the row order below, with one chain of database change files that point at each other. Commit that chain in the order in the next section. The screen-store row and the bridge row sit inside that chain. Every other row can land in the order written.

## Database change files that point at each other

These files live in `apps/api/alembic/versions/`. Each one names the file before it. Commit them in this order. A row that says it is part of a later commit stays in that commit. Every other row in this section is its own commit.

### `apps/api/alembic/versions/t0u1v2w3x4y5_dry_run_seen.py`

Own commit. It creates the `dry_run_seen` table. The code that uses that table is `apps/api/app/dry_run_ledger.py`, which is already tracked and changed. That file is not a new product module, so it stays out of this commit. `apps/api/app/db_models.py` is also already tracked and holds unrelated changes, so it stays out too.

Test command, from the repo root:

```
cd apps/api && python3 -m pytest tests/test_dry_run_ledger.py -q --tb=line
```

This commit waits for Tope's yes.

### `apps/api/alembic/versions/u1v2w3x4y5z6_view_designer_history_comments.py`

Part of the `view_engine_store` commit below. It creates `view_layer_versions` and `view_comments`. That store file reads those tables. It is not a separate commit.

That commit waits for Tope's yes.

### `apps/api/alembic/versions/v2w3x4y5z6a7_view_builder_items.py`

Part of the same `view_engine_store` commit. It creates `view_builder_items`. The store file reads that table too. It is not a separate commit.

That commit waits for Tope's yes.

### `apps/api/alembic/versions/w3x4y5z6a7b8_connection_hosting.py`

Own commit, after the screen-store commit. It adds `hosting` on `odoo_connections`. The field is declared in `apps/api/app/db_models.py`, which is already tracked and holds unrelated changes, so that file stays out of this commit.

No test file is tied to this database change alone, so this row has no pytest command.

This commit waits for Tope's yes.

### `apps/api/alembic/versions/x4y5z6a7b8c9_connection_group_label.py`

Own commit. It adds `group_label` on `odoo_connections`. Leave `apps/api/app/db_models.py` out of this commit. It is already tracked and holds other changes.

No test file is tied to this database change alone, so this row has no pytest command.

This commit waits for Tope's yes.

### `apps/api/alembic/versions/y5z6a7b8c9d0_connection_is_test_copy.py`

Own commit. It adds `is_test_copy` on `odoo_connections`. Leave `apps/api/app/db_models.py` out of this commit. It is already tracked and holds other changes.

No test file is tied to this database change alone, so this row has no pytest command.

This commit waits for Tope's yes.

### `apps/api/alembic/versions/z6a7b8c9d0e1_user_display_name.py`

Own commit. It adds `display_name` on `users`. The field is declared in `apps/api/app/account_models.py`, which is already tracked and changed, and is not a new product module, so that file stays out of this commit.

No test file is tied to this database change alone, so this row has no pytest command.

This commit waits for Tope's yes.

### `apps/api/alembic/versions/ze1f2a3b4c5d_integration_event_delivery.py`

Part of the `bridge` commit below, and only after `z6a7b8c9d0e1_user_display_name.py` is committed. `apps/api/app/bridge/delivery.py` is the new file that uses `integration_events`. It is not a separate commit.

That commit waits for Tope's yes.

## Folders named in the old pack

Each short name was checked with `ls`. All eleven are in the tree.

### changeset

Path: `apps/api/app/changeset/` (in tree).

Files in this commit:

- `apps/api/app/changeset/cli.py` — already tracked, but changed.
- `apps/api/app/changeset/data_ops.py` — already tracked, but changed.
- `apps/api/app/changeset/dispatch.py` — already tracked, but changed.
- `apps/api/app/changeset/executor.py` — already tracked, but changed.
- `apps/api/app/changeset/handlers.py` — already tracked, but changed.
- `apps/api/app/changeset/inbox.py` — already tracked, but changed.
- `apps/api/app/changeset/logic_ops.py` — already tracked, but changed.
- `apps/api/app/changeset/meta_snapshot.py` — already tracked, but changed.
- `apps/api/app/changeset/plan_card.py` — already tracked, but changed.
- `apps/api/app/changeset/policy.py` — already tracked, but changed.
- `apps/api/app/changeset/recovery.py` — already tracked, but changed.
- `apps/api/app/changeset/rollback.py` — already tracked, but changed.
- `apps/api/app/changeset/schema_ops.py` — already tracked, but changed.
- `apps/api/app/changeset/setting_ops.py` — already tracked, but changed.
- `apps/api/app/changeset/simulate.py` — already tracked, but changed.
- `apps/api/app/changeset/store.py` — already tracked, but changed.
- `apps/api/app/changeset/ui_ops.py` — already tracked, but changed.

- `apps/api/tests/engine/test_suite_01_op_conformance.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/engine/test_suite_02_round_trip.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/engine/test_suite_03_idempotency.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/engine/test_suite_08_policy.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/engine/test_suite_13_lock.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_changeset_cli.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_changeset_engine.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_changeset_inbox.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_critic.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_data_ops.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_executor_wal.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_l4_gate_02.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_l4_gates.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_l4_never_allowed.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_logic_ops.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_meta_snapshot.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_multi_client_lock.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_plan_card_goldens.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_plan_card_store.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_policy_matrix.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_production_budgets.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_protected_registry.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_red_team_engine.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_reg_np_5a.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_reg_np_l4.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_rollback.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_rollback_tiers.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_schema_ops.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_setting_ops.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_simulation_modes.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_suite_changeset_gate.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_suite_store_move.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_t6_04_inbox_binding.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_t6_05_plan_card_sections.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_ui_ops.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/engine/test_suite_01_op_conformance.py tests/engine/test_suite_02_round_trip.py tests/engine/test_suite_03_idempotency.py tests/engine/test_suite_04_atomicity.py tests/engine/test_suite_06_approval_binding.py tests/engine/test_suite_07_drift.py tests/engine/test_suite_08_policy.py tests/engine/test_suite_09_protected.py tests/engine/test_suite_10_validator.py tests/engine/test_suite_11_crash.py tests/engine/test_suite_12_unknown.py tests/engine/test_suite_13_lock.py tests/engine/test_suite_15_data.py tests/engine/test_suite_18_boundaries.py tests/test_agent_runtime.py tests/test_agent_tools.py tests/test_bridge_protocol.py tests/test_changeset_cli.py tests/test_changeset_engine.py tests/test_changeset_inbox.py tests/test_config_apply.py tests/test_critic.py tests/test_data_ops.py tests/test_dispatch_and_shopify.py tests/test_executor_bridge.py tests/test_executor_gates.py tests/test_executor_wal.py tests/test_fixture_catalog.py tests/test_handlers_grants_skills.py tests/test_l4_gate_02.py tests/test_l4_gates.py tests/test_l4_never_allowed.py tests/test_logic_ops.py tests/test_meta_snapshot.py tests/test_multi_client_lock.py tests/test_odoo20_access_write_path.py tests/test_odoo20_spec_replay.py tests/test_plan_card_goldens.py tests/test_plan_card_recovery.py tests/test_plan_card_store.py tests/test_policy_matrix.py tests/test_production_budgets.py tests/test_protected_registry.py tests/test_red_team_engine.py tests/test_reg_np_5a.py tests/test_reg_np_l4.py tests/test_risk_escalation.py tests/test_rollback.py tests/test_rollback_tiers.py tests/test_schema_ops.py tests/test_security_ops.py tests/test_setting_ops.py tests/test_simulation.py tests/test_simulation_modes.py tests/test_suite_changeset_gate.py tests/test_suite_store_move.py tests/test_t4_skt_triggers.py tests/test_t6_04_inbox_binding.py tests/test_t6_05_plan_card_sections.py tests/test_ui_ops.py tests/test_verify.py tests/test_worker_bot.py tests/test_worker_bot_adversarial_embedded_5c06.py tests/test_worker_bot_drift.py tests/test_worker_bot_l2_catalog.py tests/test_worker_bot_l3_catalog.py tests/test_worker_bot_l3_repeat_pause_5c09.py -q --tb=line
```

Database change files already in history (do not add them again):

- `apps/api/alembic/versions/s9t0u1v2w3x4_journal_wal.py`
- `apps/api/alembic/versions/q7r8s9t0u1v2_plan_cards.py`

`s9t0u1v2w3x4_journal_wal.py` is the one `apps/api/app/changeset/executor.py` names for `journal_entry`. `q7r8s9t0u1v2_plan_cards.py` creates `plan_cards`, which `apps/api/app/changeset/store.py` writes.

Worked example for this card: this folder, the test files that import it, and the database change files that create its tables, as one commit. There is no `?? apps/api/app/changeset/` line today. The files below are already tracked and changed, so this folder alone is not what keeps the first check open.

This commit waits for Tope's yes.

### llm_gateway

Path: `apps/api/app/llm_gateway/` (in tree).

Files in this commit:

- `apps/api/app/llm_gateway/providers.py` — new and not committed.

- `apps/api/tests/test_llm_gateway_providers.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_llm_gateway_vision_provider.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/engine/test_suite_16_redaction.py tests/engine/test_suite_18_boundaries.py tests/test_clarify_rules.py tests/test_llm_gateway.py tests/test_llm_gateway_adapters.py tests/test_llm_gateway_conformance_replay.py tests/test_llm_gateway_phase1.py tests/test_llm_gateway_providers.py tests/test_llm_gateway_vision_provider.py tests/test_wireframe_live_vision.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### agent_runtime

Path: `apps/api/app/agent_runtime/` (in tree).

Files in this commit:

- `apps/api/app/agent_runtime/runtime.py` — already tracked, but changed.
- `apps/api/app/agent_runtime/schema_tools.py` — new and not committed.

- `apps/api/tests/test_agent_runtime.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_gnd_agent_live_schema.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/engine/test_suite_05_state_machine.py tests/test_agent_memory.py tests/test_agent_prompt.py tests/test_agent_runtime.py tests/test_agent_tools.py tests/test_clarify_rules.py tests/test_critic.py tests/test_gnd_agent_live_schema.py tests/test_handlers_grants_skills.py tests/test_production_budgets.py tests/test_reg_np_5a.py tests/test_simulation.py tests/test_skill_router.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### bots

Path: `apps/api/app/bots/` (in tree).

Git shows no change in this folder. No commit is proposed.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_handlers_grants_skills.py tests/test_skill_router.py -q --tb=line
```

No database change file belongs to this folder.

No commit is proposed. A later commit of this folder would still wait for Tope's yes.

### worker_bot

Path: `apps/api/app/worker_bot/` (in tree).

Files in this commit:

- `apps/api/app/worker_bot/l3_policy.py` — new and not committed.
- `apps/api/app/worker_bot/l4_policy.py` — already tracked, but changed.
- `apps/api/app/worker_bot/runtime.py` — already tracked, but changed.
- `apps/api/app/worker_bot/standing_rule.py` — new and not committed.

- `apps/api/tests/test_l4_allow_list_grant.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_l4_gate_03.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_l4_gate_04.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_l4_policy.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_worker_bot_adversarial_embedded_5c06.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_worker_bot_drift.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_worker_bot_l2_catalog.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_worker_bot_l3_catalog.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_worker_bot_l3_repeat_pause_5c09.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/engine/test_suite_10_validator.py tests/test_l4_allow_list_grant.py tests/test_l4_gate_02.py tests/test_l4_gate_03.py tests/test_l4_gate_04.py tests/test_l4_gates.py tests/test_l4_never_allowed.py tests/test_l4_policy.py tests/test_production_budgets.py tests/test_red_team_engine.py tests/test_reg_np_5a.py tests/test_reg_np_l4.py tests/test_worker_bot.py tests/test_worker_bot_adversarial_embedded_5c06.py tests/test_worker_bot_drift.py tests/test_worker_bot_l2_catalog.py tests/test_worker_bot_l3_catalog.py tests/test_worker_bot_l3_repeat_pause_5c09.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### bridge

Path: `apps/api/app/bridge/` (in tree).

Files in this commit:

- `apps/api/app/bridge/__init__.py` — already tracked, but changed.
- `apps/api/app/bridge/canvas.py` — new and not committed.
- `apps/api/app/bridge/connections.py` — already tracked, but changed.
- `apps/api/app/bridge/delivery.py` — new and not committed.
- `apps/api/app/bridge/drafting.py` — new and not committed.
- `apps/api/app/bridge/export.py` — new and not committed.
- `apps/api/app/bridge/flows.py` — new and not committed.
- `apps/api/app/bridge/gallery.py` — new and not committed.
- `apps/api/app/bridge/live_probe.py` — new and not committed.
- `apps/api/app/bridge/mapping.py` — new and not committed.
- `apps/api/app/bridge/ops.py` — new and not committed.
- `apps/api/app/bridge/reliability.py` — new and not committed.
- `apps/api/app/bridge/spec_import.py` — new and not committed.
- `apps/api/app/bridge/sync_rules.py` — new and not committed.
- `apps/api/app/bridge/tokens.py` — new and not committed.
- `apps/api/alembic/versions/ze1f2a3b4c5d_integration_event_delivery.py` — new and not committed. Database change file for this folder.

- `apps/api/tests/test_bridge_canvas.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_delivery.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_drafting.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_export.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_flow_volume.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_flows.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_gallery.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_mapping.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_ops.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_queue.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_reliability.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_spec_import.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_bridge_sync_rules.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_prepared_footer.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_reg_np_br.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/engine/test_suite_14_bridge.py tests/test_bridge_and_config_spec.py tests/test_bridge_canvas.py tests/test_bridge_delivery.py tests/test_bridge_drafting.py tests/test_bridge_export.py tests/test_bridge_flow_volume.py tests/test_bridge_flows.py tests/test_bridge_gallery.py tests/test_bridge_mapping.py tests/test_bridge_memory.py tests/test_bridge_ops.py tests/test_bridge_queue.py tests/test_bridge_reliability.py tests/test_bridge_spec_import.py tests/test_bridge_sync_rules.py tests/test_dispatch_and_shopify.py tests/test_prepared_footer.py tests/test_reg_np_br.py -q --tb=line
```

Database change files already in history (do not add them again):

- `apps/api/alembic/versions/p6q7r8s9t0u1_bridge_connections_queue.py`

`p6q7r8s9t0u1_bridge_connections_queue.py` creates `bridge_connections`. It is already in history. The new file `ze1f2a3b4c5d_integration_event_delivery.py` goes in this commit with `apps/api/app/bridge/delivery.py`.

Land this commit only after `apps/api/alembic/versions/z6a7b8c9d0e1_user_display_name.py` is committed. The bridge database change file points at that file.

This commit waits for Tope's yes.

### config_as_code

Path: `apps/api/app/config_as_code/` (in tree).

Files in this commit:

- `apps/api/app/config_as_code/__init__.py` — already tracked, but changed.
- `apps/api/app/config_as_code/apply.py` — already tracked, but changed.

- `apps/api/tests/test_reg_np_5b.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_bridge_and_config_spec.py tests/test_config_apply.py tests/test_importers.py tests/test_l10n_ng_adopt.py tests/test_odoo20_spec_replay.py tests/test_reg_np_5b.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### odoo20

Path: `apps/api/app/odoo20/` (in tree).

Files in this commit:

- `apps/api/app/odoo20/__init__.py` — already tracked, but changed.

- `apps/api/tests/test_odoo20_access_write_path.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_odoo20_spec_replay.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_bridge_and_config_spec.py tests/test_config_apply.py tests/test_odoo20_spec_replay.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### offline

Path: `apps/api/app/offline/` (in tree).

Files in this commit:

- `apps/api/app/offline/__init__.py` — already tracked, but changed.
- `apps/api/app/offline/flush.py` — new and not committed.
- `apps/api/app/offline/idempotency.py` — already tracked, but changed.

- `apps/api/tests/test_offline_flush.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_idempotency_store.py tests/test_offline_flush.py -q --tb=line
```

Database change files already in history (do not add them again):

- `apps/api/alembic/versions/r8s9t0u1v2w3_idempotency_keys.py`

`r8s9t0u1v2w3_idempotency_keys.py` creates `idempotency_keys`. `apps/api/app/offline/idempotency.py` reads that table. The file is already in history.

This commit waits for Tope's yes.

### skills

Path: `apps/api/app/skills/` (in tree).

Git shows no change in this folder. No commit is proposed.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_handlers_grants_skills.py tests/test_skill_router.py -q --tb=line
```

No database change file belongs to this folder.

No commit is proposed. A later commit of this folder would still wait for Tope's yes.

### progress

Path: `apps/api/app/progress/` (in tree).

Files in this commit:

- `apps/api/app/progress/__init__.py` — already tracked, but changed.
- `apps/api/app/progress/emit.py` — new and not committed.
- `apps/api/app/progress/stage_bus.py` — already tracked, but changed.
- `apps/api/app/progress/stage_registry.py` — new and not committed.
- `apps/api/app/progress/store.py` — new and not committed.

- `apps/api/tests/test_progress_router.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_stage_bus.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_progress_router.py tests/test_stage_bus.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

## Other new product folders and files

The locked test treats each of these as its own module. Each one is still new and not committed, so the first check stays open. Loose files under `apps/api/app/` each get their own commit. A folder gets one commit for every new or changed file inside it.

### ai_browser_agent

Path: `apps/api/app/ai_browser_agent.py` (in tree, one file).

Files in this commit:

- `apps/api/app/ai_browser_agent.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### ai_client

Path: `apps/api/app/ai_client/` (in tree).

Files in this commit:

- `apps/api/app/ai_client/` — new and not committed. Contains: __init__.py, ai_cache.py, ai_scope.py, context_cache.py, guards.py, shared_client.py.

- `apps/api/tests/test_ai_guards_unfenced.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_ai_shared_client.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_ask_timing.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_ai_guards_unfenced.py tests/test_ai_shared_client.py tests/test_ask_timing.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### ai_conversation

Path: `apps/api/app/ai_conversation/` (in tree).

Files in this commit:

- `apps/api/app/ai_conversation/app_design.py` — new and not committed.
- `apps/api/app/ai_conversation/automation_records.py` — new and not committed.
- `apps/api/app/ai_conversation/brief_checklist.py` — new and not committed.
- `apps/api/app/ai_conversation/brief_expand.py` — new and not committed.
- `apps/api/app/ai_conversation/capability.py` — new and not committed.
- `apps/api/app/ai_conversation/clarify.py` — already tracked, but changed.
- `apps/api/app/ai_conversation/clause_grounding.py` — new and not committed.
- `apps/api/app/ai_conversation/conflict_look.py` — new and not committed.
- `apps/api/app/ai_conversation/design_quality.py` — new and not committed.
- `apps/api/app/ai_conversation/design_refresh.py` — new and not committed.
- `apps/api/app/ai_conversation/design_scope.py` — new and not committed.
- `apps/api/app/ai_conversation/diagnosis_decision.py` — new and not committed.
- `apps/api/app/ai_conversation/grounding.py` — new and not committed.
- `apps/api/app/ai_conversation/install_step.py` — new and not committed.
- `apps/api/app/ai_conversation/intent_contract.py` — new and not committed.
- `apps/api/app/ai_conversation/intent_gate.py` — already tracked, but changed.
- `apps/api/app/ai_conversation/intent_lexicon.py` — already tracked, but changed.
- `apps/api/app/ai_conversation/intent_llm.py` — already tracked, but changed.
- `apps/api/app/ai_conversation/model_authorizer.py` — new and not committed.
- `apps/api/app/ai_conversation/orphan_repair.py` — new and not committed.
- `apps/api/app/ai_conversation/refine.py` — already tracked, but changed.
- `apps/api/app/ai_conversation/stock_routing.py` — new and not committed.
- `apps/api/app/ai_conversation/studio_agent.py` — new and not committed.
- `apps/api/app/ai_conversation/understand.py` — already tracked, but changed.

- `apps/api/tests/test_ai_conversation_session.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_ai_conversation_understand.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_brief_checklist.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_clause_grounding.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_continuous_invent_class.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_fix_plan_step3_4.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_gemini_vertex.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_gnd_gen_live_schema.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_gnd_studio_live_schema.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_intent_contract.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_intent_contract_platform.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_intent_ladder.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_live_regressions_oct12.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_messy_briefs_policy.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_model_authorizer.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_orphan_repair.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_s11_install_step.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_s12_followup.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_s7_phases.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_stock_routing.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_stock_wiring.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_studio_agent.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_studio_design_quality.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_studio_step1_grounding.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_studio_step2a_app_design.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_studio_step3_design_build.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_studio_stock_first_corpus.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_studio_suggested_models.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_ai_approval_flow.py tests/test_ai_constraint_ast.py tests/test_ai_conversation_intent_gate.py tests/test_ai_conversation_session.py tests/test_ai_conversation_understand.py tests/test_ai_form_slots.py tests/test_ai_intent_llm.py tests/test_approved_craft_default_off.py tests/test_brief_checklist.py tests/test_brief_understanding_class.py tests/test_class_stamp.py tests/test_clause_grounding.py tests/test_continuous_invent_class.py tests/test_contract_draft_identity.py tests/test_craft_smart_buttons_diagnosis.py tests/test_date_vs_datetime_classifier.py tests/test_diagnosis_prefer_host_must_do.py tests/test_diagnosis_visitor_log.py tests/test_first_try_generate_repair_class.py tests/test_fix_plan_step3_4.py tests/test_flash_ast_enrich_toggle.py tests/test_full_app_foreign_pack_surface.py tests/test_full_app_never_reshape_inherit.py tests/test_full_app_vehicle_request_must_do.py tests/test_gemini_vertex.py tests/test_generate_roots_delivery_canvas_status.py tests/test_gnd_gen_live_schema.py tests/test_gnd_studio_live_schema.py tests/test_intent_contract.py tests/test_intent_contract_platform.py tests/test_intent_ladder.py tests/test_live_regressions_oct12.py tests/test_messy_briefs_policy.py tests/test_model_authorizer.py tests/test_notes_surface_class.py tests/test_orphan_repair.py tests/test_pack_adoption_policy.py tests/test_prefer_field_pack_no_clarification_leak.py tests/test_prefer_host_fullapp_noun_class.py tests/test_residual_optional_satellite_primary.py tests/test_residual_session_identity.py tests/test_s11_install_step.py tests/test_s12_followup.py tests/test_s1_field_ir.py tests/test_s7_phases.py tests/test_state_title_identity_spray_class.py tests/test_stock_routing.py tests/test_stock_wiring.py tests/test_structural_repair_and_inherit_ops.py tests/test_studio_agent.py tests/test_studio_design_quality.py tests/test_studio_step1_grounding.py tests/test_studio_step2a_app_design.py tests/test_studio_step3_design_build.py tests/test_studio_stock_first_corpus.py tests/test_studio_suggested_models.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### ai_design_compile

Path: `apps/api/app/ai_design_compile.py` (in tree, one file).

Files in this commit:

- `apps/api/app/ai_design_compile.py` — new and not committed.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_messy_briefs_policy.py tests/test_studio_stock_first_corpus.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### ai_edit_blocks

Path: `apps/api/app/ai_edit_blocks.py` (in tree, one file).

Files in this commit:

- `apps/api/app/ai_edit_blocks.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### ai_option_a_packet_ground

Path: `apps/api/app/ai_option_a_packet_ground.py` (in tree, one file).

Files in this commit:

- `apps/api/app/ai_option_a_packet_ground.py` — new and not committed.

- `apps/api/tests/test_gnd_opta_live_schema.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_gnd_opta_live_schema.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### ai_pack_stock_first

Path: `apps/api/app/ai_pack_stock_first.py` (in tree, one file).

Files in this commit:

- `apps/api/app/ai_pack_stock_first.py` — new and not committed.

- `apps/api/tests/test_pack_stock_first.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_pack_stock_first.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### auth_audit

Path: `apps/api/app/auth_audit.py` (in tree, one file).

Files in this commit:

- `apps/api/app/auth_audit.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### brief_integrations

Path: `apps/api/app/brief_integrations.py` (in tree, one file).

Files in this commit:

- `apps/api/app/brief_integrations.py` — new and not committed.

- `apps/api/tests/test_brief_integrations.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_brief_integrations.py tests/test_intent_contract.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### builders_ticker

Path: `apps/api/app/builders_ticker.py` (in tree, one file).

Files in this commit:

- `apps/api/app/builders_ticker.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### code_runner

Path: `apps/api/app/code_runner/` (in tree).

Files in this commit:

- `apps/api/app/code_runner/` — new and not committed. Contains: __init__.py, ai.py, child.py, library.py, lint.py, promote.py, runs.py, schema.py, snippets.py, store.py, testing.py, vault.py, versions.py.

- `apps/api/tests/test_code_runner_editor.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_code_runner_r3.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_code_runner_runs.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_bridge_delivery.py tests/test_bridge_flows.py tests/test_code_runner_editor.py tests/test_code_runner_r3.py tests/test_code_runner_runs.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### compat

Path: `apps/api/app/compat/` (in tree).

Files in this commit:

- `apps/api/app/compat/` — new and not committed. Contains: __init__.py, odoo_versions.py.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### data

Path: `apps/api/app/data/` (in tree).

Files in this commit:

- `apps/api/app/data/view_catalog/` — new and not committed. Contains: v17.json.gz, v18.json.gz, v19.json.gz, v20.json.gz.
- `apps/api/app/data/widget_catalog/` — new and not committed. Contains: v17.json, v18.json, v19.json, v20.json.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### design_admission

Path: `apps/api/app/design_admission.py` (in tree, one file).

Files in this commit:

- `apps/api/app/design_admission.py` — new and not committed.

- `apps/api/tests/test_design_admission.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_design_admission_xmlid.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_design_admission.py tests/test_design_admission_xmlid.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### email_receipt

Path: `apps/api/app/email_receipt.py` (in tree, one file).

Files in this commit:

- `apps/api/app/email_receipt.py` — new and not committed.

- `apps/api/tests/test_email_receipt.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_email_receipt.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### expert

Path: `apps/api/app/expert/` (in tree).

Files in this commit:

- `apps/api/app/expert/access_guidance.py` — already tracked, but changed.
- `apps/api/app/expert/ask.py` — already tracked, but changed.
- `apps/api/app/expert/chatter_bridge.py` — already tracked, but changed.
- `apps/api/app/expert/draft_review.py` — already tracked, but changed.
- `apps/api/app/expert/error_diagnosis.py` — already tracked, but changed.
- `apps/api/app/expert/field_constraint_guidance.py` — already tracked, but changed.
- `apps/api/app/expert/grounding.py` — already tracked, but changed.
- `apps/api/app/expert/ingest.py` — already tracked, but changed.
- `apps/api/app/expert/instance_caveats.py` — already tracked, but changed.
- `apps/api/app/expert/knowledge_fallback.py` — already tracked, but changed.
- `apps/api/app/expert/l10n_chunks.py` — already tracked, but changed.
- `apps/api/app/expert/l10n_guidance.py` — already tracked, but changed.
- `apps/api/app/expert/live_schema_ask.py` — new and not committed.
- `apps/api/app/expert/narrative.py` — already tracked, but changed.
- `apps/api/app/expert/nl_search.py` — already tracked, but changed.
- `apps/api/app/expert/platform_guidance.py` — already tracked, but changed.
- `apps/api/app/expert/product_guidance.py` — already tracked, but changed.
- `apps/api/app/expert/stack_inference.py` — already tracked, but changed.
- `apps/api/app/expert/suggested_prompts.py` — already tracked, but changed.
- `apps/api/app/expert/vertical_catalog.py` — already tracked, but changed.
- `apps/api/app/expert/vertical_playbooks.py` — already tracked, but changed.
- `apps/api/app/expert/view_guidance.py` — already tracked, but changed.
- `apps/api/app/expert/view_mode_guidance.py` — already tracked, but changed.

- `apps/api/tests/test_ai_architecture_close.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_ai_honesty_ir_independent.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_edition_detection.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_expert_generic_prompt_ids.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_find_anything_records.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_gnd_expert_live_schema.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_gnd_g_text_live_schema.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_ai_architecture_close.py tests/test_ai_honesty_ir_independent.py tests/test_edition_detection.py tests/test_expert_access_guidance.py tests/test_expert_ask.py tests/test_expert_conceptual.py tests/test_expert_draft_review.py tests/test_expert_error_diagnosis.py tests/test_expert_eval.py tests/test_expert_generic_prompt_ids.py tests/test_expert_grounding.py tests/test_expert_ingest.py tests/test_expert_knowledge_fallback.py tests/test_expert_l10n.py tests/test_expert_product_guidance.py tests/test_expert_stack_inference.py tests/test_expert_upgrade.py tests/test_expert_verticals.py tests/test_expert_view_guidance.py tests/test_find_anything_records.py tests/test_gnd_expert_live_schema.py tests/test_gnd_g_text_live_schema.py tests/test_master_reference_ingest.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### grounding

Path: `apps/api/app/grounding/` (in tree).

Files in this commit:

- `apps/api/app/grounding/` — new and not committed. Contains: __init__.py, rag.py, tools.py.

- `apps/api/tests/test_t4_ground.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_t4_ground.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### live_demo_copilot

Path: `apps/api/app/live_demo_copilot/` (in tree).

Files in this commit:

- `apps/api/app/live_demo_copilot/after_meeting.py` — new and not committed.
- `apps/api/app/live_demo_copilot/bot_backend.py` — new and not committed.
- `apps/api/app/live_demo_copilot/bot_status.py` — already tracked, but changed.
- `apps/api/app/live_demo_copilot/db_grounding.py` — new and not committed.
- `apps/api/app/live_demo_copilot/leave_purge.py` — already tracked, but changed.
- `apps/api/app/live_demo_copilot/pipeline.py` — already tracked, but changed.
- `apps/api/app/live_demo_copilot/stage2_answer.py` — already tracked, but changed.
- `apps/api/app/live_demo_copilot/vexa_client.py` — new and not committed.

- `apps/api/tests/test_copilot_after_meeting.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_gnd_demo.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_meeting_bot_vexa.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_copilot_after_meeting.py tests/test_gnd_demo.py tests/test_live_demo_copilot.py tests/test_meeting_bot_vexa.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### live_schema_context

Path: `apps/api/app/live_schema_context.py` (in tree, one file).

Files in this commit:

- `apps/api/app/live_schema_context.py` — new and not committed.

- `apps/api/tests/test_gnd_auto_live_schema.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_gnd_g_map_live_schema.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_gnd_g_pipe_live_schema.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_gnd_mod_stock_app.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_live_schema_context.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_brief_integrations.py tests/test_gnd_agent_live_schema.py tests/test_gnd_auto_live_schema.py tests/test_gnd_expert_live_schema.py tests/test_gnd_g_map_live_schema.py tests/test_gnd_g_pipe_live_schema.py tests/test_gnd_g_text_live_schema.py tests/test_gnd_gen_live_schema.py tests/test_gnd_mod_stock_app.py tests/test_gnd_opta_live_schema.py tests/test_live_schema_context.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### odoo_snapshot

Path: `apps/api/app/odoo_snapshot.py` (in tree, one file).

Files in this commit:

- `apps/api/app/odoo_snapshot.py` — new and not committed.

- `apps/api/tests/test_connection_snapshot_overview.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_odoo_snapshot.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_overview_attention.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_connection_snapshot_overview.py tests/test_odoo_snapshot.py tests/test_overview_attention.py tests/test_s12_followup.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### qweb_unsafe_gate

Path: `apps/api/app/qweb_unsafe_gate.py` (in tree, one file).

Files in this commit:

- `apps/api/app/qweb_unsafe_gate.py` — new and not committed.

- `apps/api/tests/test_pdf05_unsafe_template_gate.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_pdf05_unsafe_template_gate.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### qweb_view_blocks

Path: `apps/api/app/qweb_view_blocks.py` (in tree, one file).

Files in this commit:

- `apps/api/app/qweb_view_blocks.py` — new and not committed.

- `apps/api/tests/test_qweb_views_unsafe_gate.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_qweb_views_unsafe_gate.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### routers

Path: `apps/api/app/routers/` (in tree).

Files in this commit:

- `apps/api/app/routers/access.py` — already tracked, but changed.
- `apps/api/app/routers/accounts.py` — already tracked, but changed.
- `apps/api/app/routers/actions.py` — already tracked, but changed.
- `apps/api/app/routers/ai.py` — already tracked, but changed.
- `apps/api/app/routers/ai_cache.py` — new and not committed.
- `apps/api/app/routers/ai_studio.py` — already tracked, but changed.
- `apps/api/app/routers/approvals.py` — already tracked, but changed.
- `apps/api/app/routers/apps.py` — already tracked, but changed.
- `apps/api/app/routers/auth.py` — already tracked, but changed.
- `apps/api/app/routers/automations.py` — already tracked, but changed.
- `apps/api/app/routers/batch_os.py` — already tracked, but changed.
- `apps/api/app/routers/bridge.py` — already tracked, but changed.
- `apps/api/app/routers/builder.py` — already tracked, but changed.
- `apps/api/app/routers/bulk_suite.py` — already tracked, but changed.
- `apps/api/app/routers/code_runner.py` — new and not committed.
- `apps/api/app/routers/code_studio.py` — already tracked, but changed.
- `apps/api/app/routers/command_center.py` — new and not committed.
- `apps/api/app/routers/config_ops.py` — already tracked, but changed.
- `apps/api/app/routers/config_recipes.py` — already tracked, but changed.
- `apps/api/app/routers/connections.py` — already tracked, but changed.
- `apps/api/app/routers/dashboard_studio.py` — new and not committed.
- `apps/api/app/routers/data_import.py` — already tracked, but changed.
- `apps/api/app/routers/ee_playbooks.py` — already tracked, but changed.
- `apps/api/app/routers/environments.py` — already tracked, but changed.
- `apps/api/app/routers/expert.py` — already tracked, but changed.
- `apps/api/app/routers/export_sandbox.py` — already tracked, but changed.
- `apps/api/app/routers/health_check.py` — already tracked, but changed.
- `apps/api/app/routers/history.py` — new and not committed.
- `apps/api/app/routers/id_generator.py` — already tracked, but changed.
- `apps/api/app/routers/inbox.py` — already tracked, but changed.
- `apps/api/app/routers/ingest.py` — already tracked, but changed.
- `apps/api/app/routers/intent_route.py` — already tracked, but changed.
- `apps/api/app/routers/introspection.py` — already tracked, but changed.
- `apps/api/app/routers/job_autopilot.py` — already tracked, but changed.
- `apps/api/app/routers/live_demo_copilot.py` — already tracked, but changed.
- `apps/api/app/routers/module_spec.py` — already tracked, but changed.
- `apps/api/app/routers/offline.py` — new and not committed.
- `apps/api/app/routers/power_ops.py` — already tracked, but changed.
- `apps/api/app/routers/progress.py` — new and not committed.
- `apps/api/app/routers/projects.py` — already tracked, but changed.
- `apps/api/app/routers/qweb_views.py` — new and not committed.
- `apps/api/app/routers/reports.py` — already tracked, but changed.
- `apps/api/app/routers/sample_company.py` — new and not committed.
- `apps/api/app/routers/script_runner.py` — already tracked, but changed.
- `apps/api/app/routers/studio_agent.py` — new and not committed.
- `apps/api/app/routers/suite.py` — new and not committed.
- `apps/api/app/routers/suite_change.py` — new and not committed.
- `apps/api/app/routers/suite_insights.py` — new and not committed.
- `apps/api/app/routers/suite_records.py` — new and not committed.
- `apps/api/app/routers/suite_upkeep.py` — new and not committed.
- `apps/api/app/routers/view_engine.py` — new and not committed.
- `apps/api/app/routers/view_engine_2c.py` — new and not committed.
- `apps/api/app/routers/view_engine_2d.py` — new and not committed.
- `apps/api/app/routers/view_engine_builder.py` — new and not committed.
- `apps/api/app/routers/view_engine_logic.py` — new and not committed.
- `apps/api/app/routers/view_engine_reports2.py` — new and not committed.
- `apps/api/app/routers/view_engine_studio.py` — new and not committed.
- `apps/api/app/routers/views.py` — already tracked, but changed.
- `apps/api/app/routers/website.py` — already tracked, but changed.
- `apps/api/app/routers/wireframe.py` — new and not committed.

- `apps/api/tests/test_ask_events.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_copilot_delivery.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_edit_with_ai.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_email_test_send.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_field_fill_rates.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_mastery_regression_battery.py` — already tracked, but changed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_pdf04_report_grounding.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_reg_dryinstall.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_suite_send_later.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_suite_stage1.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_suite_stage2.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_suite_stage4_versions.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_view_engine_2b_fixes.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_view_engine_2c.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_view_engine_2d.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_view_engine_2e.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_view_engine_studio.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_whoami_greeting.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_access_live_pack_confirm.py tests/test_ask_events.py tests/test_ask_timing.py tests/test_connection_snapshot_overview.py tests/test_connection_wip_persist.py tests/test_copilot_delivery.py tests/test_domain_playbooks_m3.py tests/test_edit_with_ai.py tests/test_ee_playbooks_m5.py tests/test_email_test_send.py tests/test_field_fill_rates.py tests/test_gnd_g_text_live_schema.py tests/test_gnd_gen_live_schema.py tests/test_mastery_regression_battery.py tests/test_odoo20_access_write_path.py tests/test_offline_flush.py tests/test_overlay_structure.py tests/test_pdf04_report_grounding.py tests/test_pdf05_unsafe_template_gate.py tests/test_pipeline_major_m4.py tests/test_reg_dryinstall.py tests/test_suite_send_later.py tests/test_suite_stage1.py tests/test_suite_stage2.py tests/test_suite_stage4_versions.py tests/test_view_engine_2b_fixes.py tests/test_view_engine_2c.py tests/test_view_engine_2d.py tests/test_view_engine_2e.py tests/test_view_engine_studio.py tests/test_whoami_greeting.py tests/test_xpath_preview_validation.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### sample_company

Path: `apps/api/app/sample_company/` (in tree).

Files in this commit:

- `apps/api/app/sample_company/` — new and not committed. Contains: __init__.py.

- `apps/api/tests/test_sample_company.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_sample_company.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### schema_freshness

Path: `apps/api/app/schema_freshness.py` (in tree, one file).

Files in this commit:

- `apps/api/app/schema_freshness.py` — new and not committed.

- `apps/api/tests/test_schema_freshness.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_schema_freshness.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### stock_app_install

Path: `apps/api/app/stock_app_install.py` (in tree, one file).

Files in this commit:

- `apps/api/app/stock_app_install.py` — new and not committed.

- `apps/api/tests/test_gnd_mod_autopilot_map.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_brief_integrations.py tests/test_edition_detection.py tests/test_gnd_mod_autopilot_map.py tests/test_gnd_mod_stock_app.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_ask

Path: `apps/api/app/suite_ask.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_ask.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_catalog

Path: `apps/api/app/suite_catalog.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_catalog.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_change

Path: `apps/api/app/suite_change.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_change.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_changeset

Path: `apps/api/app/suite_changeset.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_changeset.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_data

Path: `apps/api/app/suite_data/` (in tree).

Files in this commit:

- `apps/api/app/suite_data/` — new and not committed. Contains: odoo_config_catalog.md.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_import

Path: `apps/api/app/suite_import.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_import.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_insights

Path: `apps/api/app/suite_insights.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_insights.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_playbooks

Path: `apps/api/app/suite_playbooks.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_playbooks.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_records

Path: `apps/api/app/suite_records.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_records.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_setup

Path: `apps/api/app/suite_setup.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_setup.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_store

Path: `apps/api/app/suite_store.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_store.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_upkeep

Path: `apps/api/app/suite_upkeep.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_upkeep.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### suite_workbook

Path: `apps/api/app/suite_workbook.py` (in tree, one file).

Files in this commit:

- `apps/api/app/suite_workbook.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### triggers

Path: `apps/api/app/triggers/` (in tree).

Files in this commit:

- `apps/api/app/triggers/` — new and not committed. Contains: __init__.py, runner.py.

- `apps/api/tests/test_t4_skt_triggers.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_t4_skt_triggers.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine

Path: `apps/api/app/view_engine.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine.py` — new and not committed.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_edit_with_ai.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_2c

Path: `apps/api/app/view_engine_2c.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_2c.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_2d

Path: `apps/api/app/view_engine_2d.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_2d.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_access

Path: `apps/api/app/view_engine_access.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_access.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_ai

Path: `apps/api/app/view_engine_ai.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_ai.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_library

Path: `apps/api/app/view_engine_library.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_library.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_logic

Path: `apps/api/app/view_engine_logic.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_logic.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_pdf

Path: `apps/api/app/view_engine_pdf.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_pdf.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_portable

Path: `apps/api/app/view_engine_portable.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_portable.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_report

Path: `apps/api/app/view_engine_report.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_report.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_report_blocks

Path: `apps/api/app/view_engine_report_blocks.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_report_blocks.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

### view_engine_store

Path: `apps/api/app/view_engine_store.py` (in tree, one file).

Files in this commit:

- `apps/api/app/view_engine_store.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

Database change files in this commit, after `apps/api/alembic/versions/t0u1v2w3x4y5_dry_run_seen.py` is committed: `apps/api/alembic/versions/u1v2w3x4y5z6_view_designer_history_comments.py` and `apps/api/alembic/versions/v2w3x4y5z6a7_view_builder_items.py`. The store file creates and reads `view_layer_versions`, `view_comments`, and `view_builder_items`. `apps/api/app/routers/view_engine_2c.py` also reads those tables and stays in the routers commit.

This commit waits for Tope's yes.

### wireframe

Path: `apps/api/app/wireframe/` (in tree).

Files in this commit:

- `apps/api/app/wireframe/` — new and not committed. Contains: __init__.py, compile.py, reader.py, review.py, stock_map.py.

- `apps/api/tests/test_wireframe.py` — new and not committed. Test file that imports this code. It is added in this commit only.
- `apps/api/tests/test_wireframe_stock_map.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_wireframe.py tests/test_wireframe_live_vision.py tests/test_wireframe_stock_map.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### wireframe_live

Path: `apps/api/app/wireframe_live.py` (in tree, one file).

Files in this commit:

- `apps/api/app/wireframe_live.py` — new and not committed.

- `apps/api/tests/test_wireframe_live_vision.py` — new and not committed. Test file that imports this code. It is added in this commit only.

Test command, from the repo root. It runs every test file that imports this code, including files already in history:

```
cd apps/api && python3 -m pytest tests/test_wireframe_live_vision.py -q --tb=line
```

No database change file belongs to this folder.

This commit waits for Tope's yes.

### write_gate

Path: `apps/api/app/write_gate.py` (in tree, one file).

Files in this commit:

- `apps/api/app/write_gate.py` — new and not committed.

No test file imports this code, so this row has no pytest command.

No database change file belongs to this folder.

This commit waits for Tope's yes.

## Package source

### module-generator

Path: `packages/module-generator/` (in tree). The locked test keeps the first check open because these source files are new and sit under `src`.

Files in this commit:

- `packages/module-generator/src/module_generator/ispec.py` — new and not committed.
- `packages/module-generator/src/module_generator/sync.py` — new and not committed.
- `packages/module-generator/tests/test_ispec_roundtrip.py` — new and not committed.
- `packages/module-generator/tests/test_recompile_sync.py` — new and not committed.

`tests/test_ispec_roundtrip.py` imports `module_generator.ispec`. `tests/test_recompile_sync.py` imports `module_generator.sync`.

Test command, from the repo root:

```
cd packages/module-generator && python3 -m pytest tests/test_ispec_roundtrip.py tests/test_recompile_sync.py -q --tb=line
```

No database change file belongs to this package.

This commit waits for Tope's yes.

### odoo-client

Path: `packages/odoo-client/` (in tree). The locked test keeps the first check open because the source file below is new and sits under `src`.

Files in this commit:

- `packages/odoo-client/src/odoo_client/compat/ir_access_shim.py` — new and not committed.
- `packages/odoo-client/tests/test_odoo20_drift_cells.py` — new and not committed.

`packages/odoo-client/src/odoo_client/client.py` imports `odoo_client.compat.ir_access_shim`. `tests/test_odoo20_drift_cells.py` imports `odoo_client.OdooClient` from that client.

Test command, from the repo root:

```
cd packages/odoo-client && python3 -m pytest tests/test_odoo20_drift_cells.py -q --tb=line
```

No database change file belongs to this package.

This commit waits for Tope's yes.

## New test files that do not belong in the product commits

These are tests, so the locked test does not treat them as product modules. They stay out of the product commits so those commits do not pick up unrelated work. Each one is still its own proposed commit.

### `packages/module-generator/tests/test_named_odoo_widget.py`

Path is in tree. New and not committed. It imports `module_generator` view helpers. It does not import `module_generator.ispec` or `module_generator.sync`.

Test command, from the repo root:

```
cd packages/module-generator && python3 -m pytest tests/test_named_odoo_widget.py -q --tb=line
```

This commit waits for Tope's yes.

### `packages/odoo-client/tests/conftest.py`

Path is in tree. New and not committed. It is the host guard for this package's tests. It does not import `ir_access_shim`.

### `packages/odoo-client/tests/test_host_guard.py`

Path is in tree. New and not committed. It checks the same host guard. It does not import `ir_access_shim`. Commit it with `packages/odoo-client/tests/conftest.py`, as one commit, separate from the source file above.

Test command, from the repo root:

```
cd packages/odoo-client && python3 -m pytest tests/test_host_guard.py -q --tb=line
```

This commit waits for Tope's yes.

## Still open

The first check stays open: `git status --short` still shows 63 new product folders and files, listed above.
The second check stays open: those commits have not been made, so their tests have not passed on their own.
Both stay open until Tope says yes and the commits land.

