#!/usr/bin/env bash
# Ensure Accounting (`account`) is installed on local Odoo 18 for Power Ops gates.
# Idempotent — skips when already installed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ODOO18_URL="${ODOO18_URL:-http://127.0.0.1:8070}"
export ODOO18_DB="${ODOO18_DB:-odoo18_dev}"
export ODOO18_USER="${ODOO18_USER:-admin}"
export ODOO18_PASSWORD="${ODOO18_PASSWORD:-admin}"

cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv — create the project venv first." >&2
  exit 1
fi

.venv/bin/python - <<'PY'
import os
from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

url = os.environ["ODOO18_URL"]
db = os.environ["ODOO18_DB"]
c = OdooClient(
    ConnectionConfig(
        url=url,
        db=db,
        username=os.environ["ODOO18_USER"],
        password=os.environ["ODOO18_PASSWORD"],
    )
)
try:
    c.connect()
except OdooClientError as exc:
    raise SystemExit(f"Cannot connect to Odoo 18 at {url!r}: {exc}") from exc

state = c.ensure_module_installed("account")
print(f"account module state={state!r} on db={db!r}")
PY
