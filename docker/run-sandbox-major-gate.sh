#!/usr/bin/env bash
# Matching-major ephemeral sandbox gate (port 18069).
# Usage:
#   ./docker/run-sandbox-major-gate.sh           # defaults to 19
#   ./docker/run-sandbox-major-gate.sh 18
#   ./docker/run-sandbox-major-gate.sh 16
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAJOR="${1:-${ODOO_SANDBOX_MAJOR:-19}}"
case "$MAJOR" in
  16|17|18|19) ;;
  *)
    echo "Unsupported major: $MAJOR (allowed: 16 17 18 19)" >&2
    exit 2
    ;;
esac

ZIP_PATH="${ROOT}/docker/sandbox-addons/_smoke_m${MAJOR}.zip"
export ZIP_PATH
export ODOO_SANDBOX_MAJOR="$MAJOR"
export PYTHONPATH="${ROOT}/packages/module-generator/src:${ROOT}/packages/odoo-client/src:${PYTHONPATH:-}"

python3 <<'PY'
import os
from pathlib import Path

from module_generator import (
    FieldSpec,
    ModelSpec,
    ModuleSpec,
    ViewSpec,
    build_module_zip,
    list_view_for_major,
    manifest_version_for_major,
)

major = int(os.environ["ODOO_SANDBOX_MAJOR"])
list_type, list_root = list_view_for_major(major)
model = f"x_sandbox_smoke_m{major}"
tech = f"sandbox_smoke_m{major}"

spec = ModuleSpec(
    technical_name=tech,
    display_name=f"Sandbox Smoke {major}",
    version=manifest_version_for_major(major),
    odoo_major=major,
    models=[
        ModelSpec(
            model=model,
            description=f"Sandbox Smoke {major}",
            fields=[FieldSpec(name="x_name", ttype="char", string="Name", required=True)],
        )
    ],
    views=[
        ViewSpec(
            name=f"{model}.form",
            model=model,
            type="form",
            arch=(
                f'<form string="Smoke {major}"><sheet><group>'
                f'<field name="x_name"/></group></sheet></form>'
            ),
        ),
        ViewSpec(
            name=f"{model}.list",
            model=model,
            type=list_type,
            arch=(
                f'<{list_root} string="Smoke {major}">'
                f'<field name="x_name"/></{list_root}>'
            ),
        ),
    ],
)
out = Path(os.environ["ZIP_PATH"])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(build_module_zip(spec))
print(f"wrote {out} ({out.stat().st_size} bytes) major={major} list_root={list_root}")
PY

uv run --directory "${ROOT}/apps/api" python <<'PY'
import os
from pathlib import Path
from app.sandbox import run_sandbox_install

major = int(os.environ["ODOO_SANDBOX_MAJOR"])
tech = f"sandbox_smoke_m{major}"
zip_bytes = Path(os.environ["ZIP_PATH"]).read_bytes()
result = run_sandbox_install(
    zip_bytes,
    module_name=tech,
    keep_alive=False,
    odoo_major=major,
)
print(result)
raise SystemExit(0 if result.ok else 1)
PY
