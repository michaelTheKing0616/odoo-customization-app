#!/usr/bin/env bash
# P2 release-gate rubric battery (ingenium). AI_INTENT_LLM=off deterministic floor.
# Unit/no_app_db only — App Postgres not required on the box.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT/apps/api"
export AI_INTENT_LLM=off
export PYTHONPATH="${ROOT}/packages/module-generator/src:${ROOT}/packages/odoo-client/src:${PYTHONPATH:-}"
PY="${ROOT}/.venv/bin/python"
if [ ! -x "$PY" ]; then PY=python3; fi

echo "== P2 rubric battery (no_app_db) =="
"$PY" -m pytest -q --tb=line -m "no_app_db" \
  tests/test_build_spine.py \
  tests/test_class_stamp.py \
  tests/test_intent_router_class_routes.py \
  tests/test_fx_rate_class.py \
  tests/test_markup_wht_class.py \
  tests/test_report_layout_scrub_class.py \
  tests/test_prefer_field_pack_no_clarification_leak.py \
  tests/test_full_app_never_reshape_inherit.py \
  tests/test_full_app_foreign_pack_surface.py \
  tests/test_pack_adoption_policy.py \
  tests/test_pack_bleed_residual_full_app.py \
  tests/test_diagnosis_prefer_host_must_do.py \
  tests/test_ai_constraint_ast.py \
  tests/test_notes_surface_class.py \
  tests/test_brief_understanding_class.py \
  tests/test_hosting_m1.py \
  tests/test_date_vs_datetime_classifier.py \
  2>&1 | tee /tmp/ingenium-p2-rubric.txt

echo
echo "Rubric log: /tmp/ingenium-p2-rubric.txt"
