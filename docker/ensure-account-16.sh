#!/usr/bin/env bash
# Ensure Accounting (`account`) is installed on local Odoo 16 for Power Ops gates.
# Idempotent — skips when already installed. 16 remains experimental (not GA).
# Compose: docker compose -p odoo16 -f docker/docker-compose.odoo16.yml (host :8072)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ODOO16_URL="${ODOO16_URL:-http://127.0.0.1:8072}"
export ODOO16_DB="${ODOO16_DB:-odoo16_dev}"
export ODOO16_USER="${ODOO16_USER:-admin}"
export ODOO16_PASSWORD="${ODOO16_PASSWORD:-admin}"

cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv — create the project venv first." >&2
  exit 1
fi

.venv/bin/python - <<'PY'
import os
from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

url = os.environ["ODOO16_URL"]
db = os.environ["ODOO16_DB"]
c = OdooClient(
    ConnectionConfig(
        url=url,
        db=db,
        username=os.environ["ODOO16_USER"],
        password=os.environ["ODOO16_PASSWORD"],
    )
)
try:
    c.connect()
except OdooClientError as exc:
    raise SystemExit(f"Cannot connect to Odoo 16 at {url!r}: {exc}") from exc

state = c.ensure_module_installed("account")
print(f"account module state={state!r} on db={db!r}")
PY
