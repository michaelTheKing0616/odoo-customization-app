#!/usr/bin/env bash
# Ensure Accounting (`account`) is installed on local Odoo 17 for Power Ops gates.
# Idempotent — skips when already installed.
# Compose: docker compose -p odoo17 -f docker/docker-compose.odoo17.yml (host :8071)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ODOO17_URL="${ODOO17_URL:-http://127.0.0.1:8071}"
export ODOO17_DB="${ODOO17_DB:-odoo17_dev}"
export ODOO17_USER="${ODOO17_USER:-admin}"
export ODOO17_PASSWORD="${ODOO17_PASSWORD:-admin}"

cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv — create the project venv first." >&2
  exit 1
fi

.venv/bin/python - <<'PY'
import os
from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

url = os.environ["ODOO17_URL"]
db = os.environ["ODOO17_DB"]
c = OdooClient(
    ConnectionConfig(
        url=url,
        db=db,
        username=os.environ["ODOO17_USER"],
        password=os.environ["ODOO17_PASSWORD"],
    )
)
try:
    c.connect()
except OdooClientError as exc:
    raise SystemExit(f"Cannot connect to Odoo 17 at {url!r}: {exc}") from exc

state = c.ensure_module_installed("account")
print(f"account module state={state!r} on db={db!r}")
PY
