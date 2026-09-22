#!/usr/bin/env bash
# Generate spray + install grammar rubric battery (ingenium).
# Extends State/title/identity spray with production-path gates:
# uncued company/PO/Contact/Rate-line never re-inject after scrub;
# O2Ms in notebook (header 0); thin one-document menu; Date≠Datetime;
# Prefer / Vehicle / Field Work / Install grammar stay green.
# AI_INTENT_LLM=off deterministic floor. Unit/no_app_db only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT/apps/api"
export AI_INTENT_LLM=off
export PYTHONPATH="${ROOT}/packages/module-generator/src:${ROOT}/packages/odoo-client/src:${PYTHONPATH:-}"
PY="${ROOT}/.venv/bin/python"
if [ ! -x "$PY" ]; then PY=python3; fi

echo "== Generate spray / grammar rubric battery (no_app_db) =="
"$PY" -m pytest -q --tb=line -m "no_app_db" \
  tests/test_generate_spray_grammar_class.py \
  tests/test_state_title_identity_spray_class.py \
  tests/test_install_grammar_o2m_preview_class.py \
  tests/test_first_try_generate_repair_class.py \
  tests/test_prefer_host_fullapp_noun_class.py \
  tests/test_continuous_invent_class.py \
  tests/test_brief_understanding_class.py \
  tests/test_notes_surface_class.py \
  tests/test_residual_optional_satellite_primary.py \
  tests/test_residual_full_app_generate_ir.py \
  tests/test_pack_adoption_policy.py \
  tests/test_pack_bleed_residual_full_app.py \
  tests/test_full_app_foreign_pack_surface.py \
  tests/test_full_app_never_reshape_inherit.py \
  tests/test_full_app_vehicle_request_must_do.py \
  tests/test_date_vs_datetime_classifier.py \
  tests/test_build_spine.py \
  tests/test_class_stamp.py \
  tests/test_intent_router_class_routes.py \
  tests/test_fx_rate_class.py \
  tests/test_markup_wht_class.py \
  tests/test_report_layout_scrub_class.py \
  tests/test_prefer_field_pack_no_clarification_leak.py \
  tests/test_diagnosis_prefer_host_must_do.py \
  tests/test_ai_constraint_ast.py \
  tests/test_hosting_m1.py \
  tests/test_atlas_elite_p4.py \
  tests/test_batch_os_atlas_recipes.py \
  tests/test_batch_os_order_dry_run.py \
  tests/test_batch_os_document_dry_run.py \
  tests/test_batch_os_new_recipes.py \
  2>&1 | tee /tmp/ingenium-generate-spray-grammar-rubric.txt

echo
echo "Rubric log: /tmp/ingenium-generate-spray-grammar-rubric.txt"
