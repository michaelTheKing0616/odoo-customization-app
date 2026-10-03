#!/usr/bin/env bash
# Dump Maintenance GenerateIR AI_IR_TRACE stages (Wave 4 / §4.1 operator helper).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/apps/api"
export AI_IR_TRACE=1
export AI_INTENT_LLM=off
export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///:memory:}"
OUT_DIR="${AI_IR_TRACE_DIR:-$ROOT/.cache/ai_ir_trace}"
mkdir -p "$OUT_DIR"
uv run python - <<'PY'
from app.ai_depth import apply_deterministic_depth
from app.ai_draft_jobs import studio_generate_offline_finish
from app.ai_pipeline import seed_studio_draft
from app.ai_schema_client import FakeSchemaClient

BRIEF = (
    "Build Maintenance tickets: checklist lines with done flags, parts used (product + qty), "
    "state Draft→Done; Online-honest on stock moves."
)
fake = FakeSchemaClient(
    models={"res.partner", "product.product", "hr.employee", "purchase.order"},
    fields={
        "res.partner": {"name": {"ttype": "char"}},
        "product.product": {"name": {"ttype": "char"}},
        "hr.employee": {"name": {"ttype": "char"}},
        "purchase.order": {"name": {"ttype": "char"}},
    },
)
draft = seed_studio_draft(BRIEF)
draft["_schema_client"] = fake
apply_deterministic_depth(draft, user_prompt=BRIEF)
out = studio_generate_offline_finish(BRIEF, draft, warnings=[])
print("models", [m.get("model") for m in (out.get("models") or []) if isinstance(m, dict)])
print("closure", out.get("_generate_ir_closure"))
print("trace_dir hint: set AI_IR_TRACE=1; stages under .cache/ai_ir_trace/")
PY
echo "Done. Inspect $OUT_DIR for stage dumps."
