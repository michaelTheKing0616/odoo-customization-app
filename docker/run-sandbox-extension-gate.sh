#!/usr/bin/env bash
# Extension gate: install a module that depends on sale+account in the sandbox.
# Slower than run-sandbox-gate.sh (smoke) because sale/account must be installed first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ZIP_PATH="${ROOT}/docker/sandbox-addons/_extension.zip"
export ZIP_PATH
export PYTHONPATH="${ROOT}/packages/module-generator/src:${PYTHONPATH:-}"
# Preload stock apps the candidate depends on (clean sandbox only has base by default)
export SANDBOX_EXTRA_MODULES="${SANDBOX_EXTRA_MODULES:-sale,account}"

echo "Extension sandbox gate — SANDBOX_EXTRA_MODULES=${SANDBOX_EXTRA_MODULES}"
echo "(This is slower than docker/run-sandbox-gate.sh smoke.)"

python3 <<'PY'
import os
from pathlib import Path
from module_generator import FieldSpec, ModelSpec, ModuleSpec, build_module_zip

spec = ModuleSpec(
    technical_name="sandbox_extension",
    display_name="Sandbox Extension",
    depends=["base", "sale", "account"],
    models=[
        ModelSpec(
            model="res.partner",
            description="Partner Extension",
            mode="inherit",
            inherit="res.partner",
            fields=[
                FieldSpec(
                    name="x_sandbox_ext_note",
                    ttype="char",
                    string="Sandbox Ext Note",
                )
            ],
        )
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
# None → read SANDBOX_EXTRA_MODULES from settings/env
result = run_sandbox_install(
    zip_bytes,
    module_name="sandbox_extension",
    keep_alive=False,
    extra_modules=None,
)
print(result)
raise SystemExit(0 if result.ok else 1)
PY
