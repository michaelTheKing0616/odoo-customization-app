#!/usr/bin/env bash
# Library template gate: build library_mgmt zip and install it in the sandbox stack.
# Requires contacts+mail preinstalled (SANDBOX_EXTRA_MODULES).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ZIP_PATH="${ROOT}/docker/sandbox-addons/_library.zip"
export ZIP_PATH
export PYTHONPATH="${ROOT}/packages/module-generator/src:${PYTHONPATH:-}"
export SANDBOX_EXTRA_MODULES="${SANDBOX_EXTRA_MODULES:-contacts,mail}"

echo "Library sandbox gate — SANDBOX_EXTRA_MODULES=${SANDBOX_EXTRA_MODULES}"

python3 <<'PY'
import os
from pathlib import Path
from module_generator import build_module_zip, library_module_spec

spec = library_module_spec(
    technical_name="library_mgmt",
    display_name="Library Management",
)
out = Path(os.environ["ZIP_PATH"])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(build_module_zip(spec))
print(f"wrote {out} ({out.stat().st_size} bytes)")
print(f"models={[m.model for m in spec.models]} depends={spec.depends}")
PY

uv run --directory "${ROOT}/apps/api" python <<'PY'
import os
from pathlib import Path
from app.sandbox import run_sandbox_install

zip_bytes = Path(os.environ["ZIP_PATH"]).read_bytes()
result = run_sandbox_install(
    zip_bytes,
    module_name="library_mgmt",
    keep_alive=False,
    extra_modules=None,
)
print(result)
raise SystemExit(0 if result.ok else 1)
PY
