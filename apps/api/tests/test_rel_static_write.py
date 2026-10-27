"""REL-STATIC-WRITE oracle. Locked: the Worker does not edit this file.

AC1: a write, an exported-module file write, or an install is allowed only from
the baseline caller set. That set includes the write gate and the plan runner
after validation. Model output does not reach those calls without the validator.
AC2: ``guard_record_write`` returns the History row from ``save_snapshot``
(``payload.op == "write"``, ``reversible == "yes"`` when before-values exist).
A planted write outside the baseline fails the same scan.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_app_db

_APP = Path(__file__).resolve().parents[1] / "app"
_MUTATING = frozenset({"write", "create", "unlink"})
_INSTALL = frozenset({"button_immediate_install", "button_install"})
_RPC_CALLEES = frozenset({"execute_kw", "_x", "call"})
_PLANTED_REL = "_planted_bypass.py"
_PLANTED_BODY = 'client.execute_kw("res.partner", "write", [[1], {"name": "x"}])\n'
_PLANTED_KEY = f"{_PLANTED_REL}::<module>::execute_kw:write"

# Sink callers under apps/api/app. A caller outside this set is a hit.
_BASELINE_TEXT = """
ai_conversation/studio_agent.py::sandbox_check.after_install::execute_kw:create
ai_option_a_acceptance.py::_check_price_effect::execute_kw:create
ai_option_a_acceptance.py::_check_price_effect::execute_kw:write
ai_option_a_acceptance.py::_demo_partner_id::execute_kw:create
ai_walkthrough_seed.py::seed_walkthrough::execute_kw:create
app_icons.py::stamp_menu_icon_png::execute_kw:write
app_templates.py::_dedupe_library_menus::execute_kw:unlink
app_templates.py::_ensure_book_author_relation::execute_kw:unlink
approval_process_service.py::_create_activity::execute_kw:create
approval_process_service.py::approve_request::execute_kw:write
approval_process_service.py::create_request::execute_kw:create
approval_process_service.py::create_type::execute_kw:create
approval_process_service.py::refuse_request::execute_kw:write
approval_process_service.py::seed_demo_type::execute_kw:create
approval_process_service.py::submit_request::execute_kw:write
approval_service.py::_create_activity::execute_kw:create
approval_service.py::deploy_community_rule::execute_kw:create
batch_os/document_batch.py::create_draft_documents::execute_kw:create
batch_os/journal_batch.py::create_draft_moves::execute_kw:create
batch_os/master_data_batch.py::PartnersBatchRecipe.apply::execute_kw:create
batch_os/master_data_batch.py::PartnersBatchRecipe.apply::execute_kw:write
batch_os/master_data_batch.py::ProductsBatchRecipe.apply::execute_kw:create
batch_os/master_data_batch.py::ProductsBatchRecipe.apply::execute_kw:write
batch_os/order_batch.py::create_draft_orders::execute_kw:create
batch_os/payment_batch.py::_register_payment::execute_kw:create
batch_os/recipes/access_company_recipes.py::MultiCompanyLinkRecipe.apply::execute_kw:write
batch_os/recipes/access_company_recipes.py::UsersGroupsRecipe.apply::execute_kw:create
batch_os/recipes/access_company_recipes.py::UsersGroupsRecipe.apply::execute_kw:write
batch_os/recipes/accounting_fiscal_year.py::FiscalYearRecipe.apply::execute_kw:create
batch_os/recipes/accounting_lock_dates.py::LockDatesRecipe.apply::execute_kw:write
batch_os/recipes/accounting_tax_pack.py::TaxPackRecipe.apply::execute_kw:create
batch_os/recipes/automation_housekeeping_recipes.py::AttachmentsCleanupRecipe.apply::execute_kw:unlink
batch_os/recipes/automation_housekeeping_recipes.py::CronPackRecipe.apply::execute_kw:write
batch_os/recipes/automation_housekeeping_recipes.py::PartnerDedupeRecipe.apply::execute_kw:write
batch_os/recipes/settings_recipes.py::CurrencyBasicsRecipe.apply::execute_kw:write
batch_os/recipes/settings_recipes.py::PaymentTermsRecipe.apply::execute_kw:create
batch_os/recipes/settings_recipes.py::PricelistRecipe.apply::execute_kw:create
batch_os/recipes/settings_recipes.py::SequenceDefaultsRecipe.apply::execute_kw:write
bot_verify/flow_library.py::_leave_request::call:create
bots/access.py::AccessLayer._exec::call:create
bots/access.py::AccessLayer._undo_create::call:unlink
bots/module_test_gate.py::_audit.zipit::writestr
bots/owned_change.py::_zip::writestr
bots/removal.py::Removal._merge::call:create
bots/settings.py::SettingsBot.apply::call:create
bots/walker.py::Walker._exec::call:create
bridge/delivery.py::odoo_handler.handle::execute_kw:create
bridge/delivery.py::odoo_handler.handle::execute_kw:write
bridge/export.py::build_zip::writestr
bulk_suite/activities.py::run_bulk_activities::execute_kw:create
bulk_suite/attachments.py::clean_attachments::execute_kw:unlink
bulk_suite/cron_manager.py::create_cron_for_existing_method::execute_kw:create
bulk_suite/cron_manager.py::update_cron_schedule::execute_kw:write
bulk_suite/dedupe.py::_relink_chatter::execute_kw:unlink
bulk_suite/dedupe.py::_relink_chatter::execute_kw:write
bulk_suite/dedupe.py::_relink_m2m::execute_kw:write
bulk_suite/dedupe.py::_relink_m2o::execute_kw:write
bulk_suite/dedupe.py::merge_duplicates::execute_kw:unlink
bulk_suite/dedupe.py::merge_duplicates::execute_kw:write
bulk_suite/mass_edit.py::run_mass_edit::execute_kw:write
bulk_suite/portal_access.py::_grant_one::execute_kw:create
bulk_suite/portal_access.py::run_bulk_portal::execute_kw:write
bulk_suite/recompute.py::probe_recompute::execute_kw:write
bulk_suite/recompute.py::run_recompute::execute_kw:write
bulk_suite/security.py::apply_security_changes::execute_kw:write
changeset/dispatch.py::_dispatch_data::call:write
changeset/dispatch.py::_dispatch_module::call:button_immediate_install
code_runner/child.py::Engine._dispatch::execute_kw:create
code_runner/child.py::Engine._dispatch::execute_kw:unlink
code_runner/child.py::Engine._dispatch::execute_kw:write
code_runner/promote.py::publish::execute_kw:write
code_runner/promote.py::remove::execute_kw:unlink
code_runner/promote.py::test::execute_kw:create
code_studio_probe.py::probe_code_server_actions::execute_kw:create
code_studio_probe.py::probe_code_server_actions::execute_kw:unlink
code_studio_service.py::bind_code_action::execute_kw:create
code_studio_service.py::test_run_code::execute_kw:create
code_studio_service.py::test_run_code::execute_kw:unlink
config_packet/fiscal.py::_create_fiscal_positions::execute_kw:create
config_packet/fiscal.py::_create_reconcile_models::execute_kw:create
config_packet/fiscal.py::_write_cash_basis::execute_kw:write
config_packet/settings.py::apply_settings::execute_kw:create
config_packet/users.py::provision_users::execute_kw:create
data_import.py::_create_missing_m2o::execute_kw:create
data_import.py::dry_run_or_commit.flush_creates::execute_kw:create
data_import.py::dry_run_or_commit::execute_kw:write
deploy_odoo_sh.py::inject_file_into_zip::writestr
design_admission.py::tag_xmlid::execute_kw:create
design_admission.py::tag_xmlid::execute_kw:unlink
ee_drivers.py::create_approval_rule::execute_kw:create
ee_drivers.py::delete_approval_rule::execute_kw:unlink
ee_drivers.py::update_approval_rule::execute_kw:write
i18n_artifacts.py::import_spec_translations_csv::execute_kw:write
id_generator.py::create_reference_sequence::execute_kw:create
id_generator.py::create_reference_sequence::execute_kw:write
id_generator.py::run_live_id_generator::execute_kw:write
image_import.py::run_image_import::execute_kw:write
ingest/inventory.py::commit_inventory_count::execute_kw:create
ingest/inventory.py::commit_inventory_count::execute_kw:write
ingest/opening_balance.py::commit_opening_tb::execute_kw:create
invoicing_connect.py::create_draft_invoice_linked::execute_kw:create
invoicing_connect.py::create_draft_invoice_linked::execute_kw:write
job_autopilot/bootstrap.py::_probe_company_currency::execute_kw:write
job_autopilot/bootstrap.py::_probe_warehouse::execute_kw:create
job_autopilot/bootstrap.py::activate_currency::execute_kw:write
job_autopilot/connectors/rpcutil.py::create::execute_kw:create
job_autopilot/demo_seed.py::_create::execute_kw:create
job_autopilot/recipes.py::_ensure_brief_journals::execute_kw:create
job_autopilot/recipes.py::_probe_pricelist::execute_kw:create
job_autopilot/recipes.py::_probe_pricelist::execute_kw:write
job_autopilot/recipes.py::_probe_users::execute_kw:create
job_autopilot/smoke.py::_create::execute_kw:create
job_autopilot/smoke.py::_smoke_crm_won::execute_kw:write
job_autopilot/stock_kits.py::_activate_route::execute_kw:write
job_autopilot/stock_kits.py::_enable_lot_on_all_category::execute_kw:write
job_autopilot/stock_kits.py::apply_company_identity::execute_kw:write
job_autopilot/stock_kits.py::apply_document_layout::execute_kw:write
job_autopilot/stock_kits.py::apply_named_journals::execute_kw:create
job_autopilot/stock_kits.py::apply_stock_kit::execute_kw:write
power_ops_recipes.py::_exec_step::execute_kw:unlink
power_ops_recipes.py::_exec_step::execute_kw:write
promote.py::promote_module_zip::install_module_by_name
property_fields_service.py::write_properties_definition::execute_kw:write
routers/builder.py::create_model::execute_kw:write
routers/config_ops.py::create_activity_type::execute_kw:create
routers/config_ops.py::create_sequence::execute_kw:create
routers/config_ops.py::import_field_labels::execute_kw:write
routers/config_ops.py::import_translations::execute_kw:write
routers/config_ops.py::patch_ir_cron_active::execute_kw:write
routers/config_ops.py::update_company::execute_kw:write
routers/config_ops.py::update_mail_template_config::execute_kw:write
routers/config_ops.py::update_sequence::execute_kw:write
routers/config_ops.py::upsert_config_paperformat::execute_kw:create
routers/config_ops.py::upsert_config_paperformat::execute_kw:write
routers/config_ops.py::upsert_config_parameter::execute_kw:create
routers/config_ops.py::upsert_config_parameter::execute_kw:write
routers/config_ops.py::upsert_ir_default::execute_kw:create
routers/config_ops.py::upsert_ir_default::execute_kw:write
routers/config_recipes.py::run_apps_pack::execute_kw:button_immediate_install
routers/config_recipes.py::run_apps_pack::execute_kw:button_install
routers/config_recipes.py::run_day1::execute_kw:write
routers/config_recipes.py::run_master_pack::execute_kw:create
routers/config_recipes.py::run_multi_company::execute_kw:create
routers/config_recipes.py::run_multi_company::execute_kw:write
routers/config_recipes.py::run_numbering::execute_kw:create
routers/config_recipes.py::run_numbering::execute_kw:write
routers/ee_playbooks.py::attach_record_to_documents_folder::execute_kw:create
routers/ee_playbooks.py::create_sign_request::execute_kw:create
routers/export_sandbox.py::install_community_module::install_module_by_name
routers/menus_builder.py::_write_menu_groups::execute_kw:write
routers/menus_builder.py::create_window_action::execute_kw:write
routers/menus_builder.py::delete_menu::execute_kw:unlink
routers/menus_builder.py::update_menu::execute_kw:write
routers/menus_builder.py::update_window_action::execute_kw:write
routers/qweb_views.py::create_qweb_view::execute_kw:create
routers/qweb_views.py::save_qweb_view::execute_kw:create
routers/qweb_views.py::save_qweb_view::execute_kw:write
routers/reports.py::create_report::execute_kw:create
routers/reports.py::create_report::execute_kw:write
routers/reports.py::delete_report::execute_kw:unlink
routers/reports.py::report_design_preview::execute_kw:write
routers/reports.py::update_report::execute_kw:write
routers/sample_company.py::_Creator.create::execute_kw:create
routers/suite_upkeep.py::files_run::execute_kw:unlink
routers/suite_upkeep.py::files_run::writestr
routers/suite_upkeep.py::files_undo::execute_kw:create
routers/suite_upkeep.py::schedule_pause::execute_kw:write
routers/suite_upkeep.py::schedule_resume::execute_kw:write
routers/view_engine.py::_engine_publish_core::execute_kw:create
routers/view_engine.py::_engine_publish_core::execute_kw:write
routers/view_engine.py::_engine_revert_core::execute_kw:unlink
routers/view_engine.py::_engine_revert_core::execute_kw:write
routers/view_engine.py::_publish_layer_arch_core::execute_kw:create
routers/view_engine.py::_publish_layer_arch_core::execute_kw:write
routers/view_engine.py::_rollback::execute_kw:unlink
routers/view_engine.py::_rollback::execute_kw:write
routers/view_engine.py::report_engine_publish::execute_kw:create
routers/view_engine.py::report_engine_publish::execute_kw:write
routers/view_engine.py::report_engine_revert::execute_kw:unlink
routers/view_engine.py::report_engine_revert::execute_kw:write
routers/view_engine_2c.py::_abtest_stop::execute_kw:unlink
routers/view_engine_2c.py::_create_primary.undo::execute_kw:unlink
routers/view_engine_2c.py::_create_primary::execute_kw:create
routers/view_engine_2c.py::_remove_scoped::execute_kw:unlink
routers/view_engine_2c.py::_resume_role_layer::execute_kw:write
routers/view_engine_2c.py::_scoped_publish::execute_kw:create
routers/view_engine_2c.py::_scoped_publish::execute_kw:write
routers/view_engine_2c.py::_scoped_rollback::execute_kw:unlink
routers/view_engine_2c.py::_scoped_rollback::execute_kw:write
routers/view_engine_2c.py::role_layers_paused::execute_kw:write
routers/view_engine_2c.py::send_via_odoo::execute_kw:create
routers/view_engine_2d.py::_own_layer_write::execute_kw:create
routers/view_engine_2d.py::_own_layer_write::execute_kw:write
routers/view_engine_2d.py::checklist_remove::execute_kw:unlink
routers/view_engine_builder.py::_stock_screen::execute_kw:write
routers/view_engine_builder.py::guard_fix::execute_kw:write
routers/view_engine_builder.py::package_import::execute_kw:create
routers/view_engine_builder.py::package_import::execute_kw:unlink
routers/view_engine_builder.py::screen_create.undo::execute_kw:unlink
routers/view_engine_builder.py::screen_create::execute_kw:create
routers/view_engine_builder.py::screen_delete::execute_kw:unlink
routers/view_engine_logic.py::_undo_access::execute_kw:unlink
routers/view_engine_logic.py::_undo_access::execute_kw:write
routers/view_engine_logic.py::history_restore.put_back::execute_kw:write
routers/view_engine_logic.py::history_restore::execute_kw:create
routers/view_engine_logic.py::history_restore::execute_kw:write
routers/view_engine_logic.py::model_access_apply::execute_kw:create
routers/view_engine_logic.py::model_access_apply::execute_kw:write
routers/view_engine_logic.py::report_draft::execute_kw:create
routers/view_engine_logic.py::report_draft::execute_kw:unlink
routers/view_engine_reports2.py::_draft_render::execute_kw:create
routers/view_engine_reports2.py::_draft_render::execute_kw:unlink
routers/view_engine_reports2.py::_render_email::execute_kw:create
routers/view_engine_reports2.py::_render_email::execute_kw:unlink
routers/view_engine_reports2.py::_write_bodies::execute_kw:write
routers/view_engine_reports2.py::brand_apply::execute_kw:write
routers/view_engine_reports2.py::brand_preview::execute_kw:create
routers/view_engine_reports2.py::brand_preview::execute_kw:write
routers/view_engine_reports2.py::brand_undo::execute_kw:write
routers/view_engine_reports2.py::email_delete::execute_kw:unlink
routers/view_engine_reports2.py::email_preview::execute_kw:unlink
routers/view_engine_reports2.py::layout_publish::execute_kw:create
routers/view_engine_reports2.py::layout_publish::execute_kw:write
routers/view_engine_reports2.py::page_numbers_set::execute_kw:create
routers/view_engine_reports2.py::page_numbers_set::execute_kw:write
routers/view_engine_studio.py::default_set::execute_kw:unlink
routers/view_engine_studio.py::field_create::execute_kw:create
routers/view_engine_studio.py::field_delete::execute_kw:unlink
routers/view_engine_studio.py::smart_action::execute_kw:create
routers/view_engine_studio.py::smart_action::execute_kw:unlink
routers/view_engine_studio.py::smart_undo::execute_kw:unlink
routers/views.py::_ensure_act_window_view_mode::execute_kw:write
routers/website.py::publish_page::execute_kw:write
routers/website.py::save_page_blocks::execute_kw:write
routers/website.py::upload_website_image::execute_kw:create
sandbox.py::_ensure_modules_installed::execute_kw:button_immediate_install
sandbox.py::_install_module_rpc::execute_kw:button_immediate_install
snapshots.py::rollback_snapshot::execute_kw:create
snapshots.py::rollback_snapshot::execute_kw:unlink
snapshots.py::rollback_snapshot::execute_kw:write
spec_apply_ui.py::_apply_root_menu_groups::execute_kw:write
spec_apply_ui.py::_apply_safe_automations::execute_kw:write
spec_apply_ui.py::_bind_root_menu_action::execute_kw:write
spec_apply_ui.py::_emit_access_ops::execute_kw:create
spec_apply_ui.py::_ensure_apply_user_in_app_groups::execute_kw:write
spec_apply_ui.py::_ensure_root_menu::execute_kw:write
spec_apply_ui.py::_ensure_spec_groups::execute_kw:write
spec_apply_ui.py::_ensure_spec_menu_tree::execute_kw:unlink
spec_apply_ui.py::_ensure_spec_menu_tree::execute_kw:write
spec_apply_ui.py::_relax_leftover_required_fields::execute_kw:write
spec_apply_ui.py::_resolve_or_create_group_id::execute_kw:create
spec_apply_ui.py::_restrict_server_action_groups::execute_kw:write
spec_apply_ui.py::_retire_open_access_v20::execute_kw:unlink
spec_apply_ui.py::_retire_open_access_v20::execute_kw:write
spec_apply_ui.py::_scrub_live_broken_automations::execute_kw:unlink
spec_apply_ui.py::_scrub_live_broken_automations::execute_kw:write
suite_change.py::merge_group::_x:write
suite_change.py::run_record::_x:create
suite_change.py::run_record::_x:write
suite_change.py::undo_record::_x:unlink
suite_change.py::undo_record::_x:write
suite_import.py::_odoo_import::_x:create
suite_import.py::remove_imported::_x:unlink
suite_import.py::remove_imported::_x:write
suite_setup.py::apply_step::_x:button_immediate_install
suite_setup.py::apply_step::_x:create
suite_setup.py::apply_step::_x:unlink
suite_setup.py::apply_step::_x:write
write_gate.py::undo_record_values::execute_kw:unlink
write_gate.py::undo_record_values::execute_kw:write
"""

_LIVE: set[str] | None = None


def _baseline() -> frozenset[str]:
    return frozenset(
        line.strip() for line in _BASELINE_TEXT.splitlines() if line.strip()
    )


def _callee(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _direct_strings(call: ast.Call) -> list[str]:
    found: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            found.append(arg.value)
    for keyword in call.keywords:
        if keyword.arg != "method":
            continue
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            found.append(keyword.value.value)
    return found


def _sink_keys(tree: ast.AST, rel: str) -> set[str]:
    """Literal write/create/unlink, install, and zip ``writestr`` call sites."""
    keys: set[str] = set()
    stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            name = _callee(node.func)
            qual = ".".join(stack) or "<module>"
            if name == "writestr":
                keys.add(f"{rel}::{qual}::writestr")
            elif name == "install_module_by_name":
                keys.add(f"{rel}::{qual}::install_module_by_name")
            elif name in _RPC_CALLEES:
                for method in _direct_strings(node):
                    if method in _MUTATING or method in _INSTALL:
                        keys.add(f"{rel}::{qual}::{name}:{method}")
            self.generic_visit(node)

    Visitor().visit(tree)
    return keys


def _scan_source(text: str, rel: str) -> set[str]:
    return _sink_keys(ast.parse(text), rel)


def _live_keys() -> set[str]:
    global _LIVE
    if _LIVE is None:
        found: set[str] = set()
        for path in sorted(_APP.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(_APP).as_posix()
            found |= _scan_source(path.read_text(encoding="utf-8"), rel)
        _LIVE = found
    return _LIVE


def _outside(keys: set[str]) -> list[str]:
    """Baseline check. An empty body here would let the planted write pass."""
    baseline = _baseline()
    return sorted(key for key in keys if key not in baseline)


def _module_function(rel: str, name: str) -> ast.FunctionDef:
    tree = ast.parse((_APP / rel).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{rel} has no function {name}")


def _calls(fn: ast.FunctionDef) -> list[ast.Call]:
    found: list[ast.Call] = []

    def walk(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Call):
                found.append(child)
            walk(child)

    walk(fn)
    return found


def _call_lines(fn: ast.FunctionDef, name: str) -> list[int]:
    return [call.lineno for call in _calls(fn) if _callee(call.func) == name]


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _dict_constant(node: ast.Dict, key: str) -> str | None:
    for dict_key, value in zip(node.keys, node.values, strict=False):
        if isinstance(dict_key, ast.Constant) and dict_key.value == key:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
    return None


def test_ac1_positive_sinks_stay_in_baseline_after_validation() -> None:
    """Live write, export-file, and install callers are the baseline set."""
    live = _live_keys()
    extra = _outside(live)
    assert extra == [], "AC1: write outside the baseline caller set: " + ", ".join(extra[:12])
    ghosts = sorted(_baseline() - live)
    assert ghosts == [], "AC1: baseline names a caller that is gone: " + ", ".join(ghosts[:12])
    assert _PLANTED_KEY not in _baseline()
    assert not (_APP / _PLANTED_REL).exists()

    gate = _module_function("write_gate.py", "guard_record_write")
    methods = [
        method
        for call in _calls(gate)
        if _callee(call.func) == "execute_kw"
        for method in _direct_strings(call)
        if method in _MUTATING or method == "read" or method in _INSTALL
    ]
    assert methods == ["read"], "AC1: guard_record_write execute_kw method is read"
    assert _call_lines(gate, "save_snapshot"), "AC1: guard_record_write saves a snapshot"
    assert max(_call_lines(gate, "execute_kw")) < min(_call_lines(gate, "save_snapshot"))

    apply_plan = _module_function("config_as_code/apply.py", "apply_plan")
    assert _call_lines(apply_plan, "_assert_types"), "AC1: apply_plan validates the plan"
    assert _call_lines(apply_plan, "apply_changeset"), "AC1: apply_plan applies the plan"
    assert min(_call_lines(apply_plan, "_assert_types")) < min(
        _call_lines(apply_plan, "apply_changeset")
    )

    executor_apply = _module_function("changeset/executor.py", "apply")
    assert _call_lines(executor_apply, "authorize_apply"), "AC1: executor.apply authorises"
    assert _call_lines(executor_apply, "_apply_journaled"), "AC1: executor.apply writes"
    assert min(_call_lines(executor_apply, "authorize_apply")) < min(
        _call_lines(executor_apply, "_apply_journaled")
    )


def test_ac1_negative_planted_execute_kw_write_is_outside_baseline() -> None:
    """The worked-example bypass is a hit. Without the baseline check it would pass."""
    keys = _scan_source(_PLANTED_BODY, _PLANTED_REL)
    assert keys == {_PLANTED_KEY}
    blocked = _outside(keys)
    assert blocked == [_PLANTED_KEY]


def test_ac2_positive_guard_record_write_returns_reversible_write_receipt() -> None:
    """History row: op write, reversible yes when before-values exist."""
    gate = _module_function("write_gate.py", "guard_record_write")
    returns = [
        node.value
        for node in ast.walk(gate)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call)
    ]
    saves = [call for call in returns if _callee(call.func) == "save_snapshot"]
    assert len(saves) == 1, "AC2: guard_record_write returns the save_snapshot row"
    payload = _keyword(saves[0], "payload")
    assert isinstance(payload, ast.Dict)
    assert _dict_constant(payload, "op") == "write"
    reversible = _keyword(saves[0], "reversible")
    assert isinstance(reversible, ast.IfExp)
    assert isinstance(reversible.test, ast.Name) and reversible.test.id == "before"
    assert isinstance(reversible.body, ast.Constant) and reversible.body.value == "yes"
    assert isinstance(reversible.orelse, ast.Constant) and reversible.orelse.value == "no"


def test_ac2_negative_planted_write_bypass_fails_static_scan() -> None:
    """The same scan fails when the planted write sits outside the baseline."""
    keys = _scan_source(_PLANTED_BODY, _PLANTED_REL)
    assert _outside(keys) == [_PLANTED_KEY]
    assert not any(key.startswith("write_gate.py::guard_record_write::") for key in keys)
    assert not any(key.startswith("config_as_code/apply.py::apply_plan::") for key in keys)
    assert not any(key.startswith("changeset/executor.py::apply::") for key in keys)
