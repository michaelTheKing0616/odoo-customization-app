#!/usr/bin/env bash
# Phase 6 gate: build a tiny module zip and install it in the sandbox stack.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ZIP_PATH="${ROOT}/docker/sandbox-addons/_smoke.zip"
export ZIP_PATH
export PYTHONPATH="${ROOT}/packages/module-generator/src:${PYTHONPATH:-}"

python3 <<'PY'
import os
from pathlib import Path
from module_generator import FieldSpec, ModelSpec, ModuleSpec, ViewSpec, build_module_zip

spec = ModuleSpec(
    technical_name="sandbox_smoke",
    display_name="Sandbox Smoke",
    models=[
        ModelSpec(
            model="x_sandbox_smoke",
            description="Sandbox Smoke",
            fields=[FieldSpec(name="x_name", ttype="char", string="Name", required=True)],
        )
    ],
    views=[
        ViewSpec(
            name="x_sandbox_smoke.form",
            model="x_sandbox_smoke",
            type="form",
            arch='<form string="Smoke"><sheet><group><field name="x_name"/></group></sheet></form>',
        ),
        ViewSpec(
            name="x_sandbox_smoke.list",
            model="x_sandbox_smoke",
            type="list",
            arch='<list string="Smoke"><field name="x_name"/></list>',
        ),
    ],
)
out = Path(os.environ["ZIP_PATH"])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(build_module_zip(spec))
print(f"wrote {out} ({out.stat().st_size} bytes)")
PY

uv run --directory "${ROOT}/apps/api" python <<'PY'
import os
from pathlib import Path
from app.sandbox import run_sandbox_install

zip_bytes = Path(os.environ["ZIP_PATH"]).read_bytes()
result = run_sandbox_install(zip_bytes, module_name="sandbox_smoke", keep_alive=False)
print(result)
raise SystemExit(0 if result.ok else 1)
PY
