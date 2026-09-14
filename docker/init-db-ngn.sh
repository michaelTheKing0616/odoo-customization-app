#!/usr/bin/env bash
# Fresh local Odoo 19 DB with company currency NGN *before* Accounting.
# Leaves odoo_dev (USD CoA) untouched. Default DB: odoo_ngn.
#
# Usage (from repo root):
#   ./docker/init-db-ngn.sh
# Optional: ODOO_DB=odoo_ngn2 ./docker/init-db-ngn.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${ODOO_CONTAINER:-odoo-custom-odoo}"
DB_NAME="${ODOO_DB:-odoo_ngn}"
ODOO_URL="${ODOO_URL:-http://127.0.0.1:8069}"
ADMIN_USER="${ODOO_USER:-admin}"
ADMIN_PASSWORD="${ODOO_ADMIN_PASSWORD:-admin}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Container ${CONTAINER} is not running. Start with:" >&2
  echo "  docker compose -p odoo-custom-dev -f docker/docker-compose.yml up -d" >&2
  exit 1
fi

echo "=== 1/4 Create ${DB_NAME} without sale/account (avoids US CoA lock) ==="
SKIP_GATE_MODULES=1 ODOO_DB="$DB_NAME" "$ROOT/docker/init-db.sh"
"$ROOT/docker/wait-for-odoo.sh"

echo "=== 2/4 Write Nigeria + NGN before Accounting ==="
export PYTHONPATH="${ROOT}/packages/odoo-client/src:${PYTHONPATH:-}"
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

ODOO_URL="$ODOO_URL" ODOO_DB="$DB_NAME" ODOO_USER="$ADMIN_USER" ODOO_PASSWORD="$ADMIN_PASSWORD" \
  "$PYTHON" - <<'PY'
import os
from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

url = os.environ["ODOO_URL"]
db = os.environ["ODOO_DB"]
client = OdooClient(
    ConnectionConfig(
        url=url,
        db=db,
        username=os.environ["ODOO_USER"],
        password=os.environ["ODOO_PASSWORD"],
        write_mode="standard",
    )
)
try:
    client.connect()
except OdooClientError as exc:
    raise SystemExit(f"Cannot connect to {url!r} db={db!r}: {exc}") from exc

companies = client.execute_kw("res.company", "search", [[]], {"limit": 1})
if not companies:
    raise SystemExit("No res.company")
cid = companies[0]

ng_ids = client.execute_kw("res.country", "search", [[("code", "=", "NG")]], {"limit": 1})
if not ng_ids:
    raise SystemExit("res.country NG missing")
client.execute_kw("res.company", "write", [[cid], {"country_id": ng_ids[0]}])

ngn_id = None
for iso in ("NGN", "USD", "GBP", "EUR"):
    ids = client.execute_kw(
        "res.currency",
        "search",
        [[("name", "=", iso)]],
        {"limit": 1, "context": {"active_test": False}},
    )
    if not ids:
        raise SystemExit(f"{iso} not in res.currency")
    client.execute_kw("res.currency", "write", [[ids[0]], {"active": True}])
    if iso == "NGN":
        ngn_id = ids[0]
if ngn_id is None:
    raise SystemExit("NGN id missing")

client.execute_kw("res.company", "write", [[cid], {"currency_id": ngn_id}])
rows = client.execute_kw(
    "res.company",
    "read",
    [[cid]],
    {"fields": ["name", "currency_id", "country_id"]},
)
print(f"company={rows[0]} NGN written before Accounting")
PY

echo "=== 3/4 Install account + l10n_ng (Nigeria CoA) ==="
docker exec "$CONTAINER" odoo \
  --db_host=db \
  -r odoo \
  -w odoo \
  -d "$DB_NAME" \
  -i account,l10n_ng \
  --stop-after-init \
  --without-demo=all
"$ROOT/docker/wait-for-odoo.sh"

echo "=== 4/4 Verify company currency is still NGN ==="
ODOO_URL="$ODOO_URL" ODOO_DB="$DB_NAME" ODOO_USER="$ADMIN_USER" ODOO_PASSWORD="$ADMIN_PASSWORD" \
  "$PYTHON" - <<'PY'
import os
from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError

client = OdooClient(
    ConnectionConfig(
        url=os.environ["ODOO_URL"],
        db=os.environ["ODOO_DB"],
        username=os.environ["ODOO_USER"],
        password=os.environ["ODOO_PASSWORD"],
        write_mode="standard",
    )
)
try:
    client.connect()
except OdooClientError as exc:
    raise SystemExit(f"Verify connect failed: {exc}") from exc

companies = client.execute_kw(
    "res.company",
    "search_read",
    [[]],
    {"fields": ["name", "currency_id", "country_id"], "limit": 1},
)
row = companies[0]
cur = row.get("currency_id")
iso = cur[1] if isinstance(cur, (list, tuple)) else cur
if str(iso).upper() != "NGN":
    raise SystemExit(f"Company currency is {iso!r}, expected NGN")
account = client.get_module_state("account") or {}
l10n = client.get_module_state("l10n_ng") or {}
print(
    f"ok company={row.get('name')} currency={iso} "
    f"account={account.get('state')} l10n_ng={l10n.get('state')}"
)
print("Login: admin / admin  db=" + os.environ["ODOO_DB"] + "  url=" + os.environ["ODOO_URL"])
PY
