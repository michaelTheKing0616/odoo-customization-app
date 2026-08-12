#!/usr/bin/env bash
# Copy odoo_expert_bridge into a running Odoo container, update module list, and install.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODULE_SRC="$ROOT/docker/sandbox-addons/odoo_expert_bridge"
CONTAINER="${1:-}"
DB_NAME="${ODOO_DB:-odoo_dev}"
ADMIN_USER="${ODOO_USER:-admin}"
ADMIN_PASSWORD="${ODOO_ADMIN_PASSWORD:-admin}"
ODOO_URL="${ODOO_URL:-http://127.0.0.1:8069}"
MODULE="odoo_expert_bridge"
DO_INSTALL="${INSTALL:-1}"

if [[ -z "$CONTAINER" ]]; then
  if docker ps --format '{{.Names}}' | grep -qx 'odoo-custom-odoo'; then
    CONTAINER=odoo-custom-odoo
  elif docker ps --format '{{.Names}}' | grep -qx 'odoo-custom-sandbox-odoo'; then
    CONTAINER=odoo-custom-sandbox-odoo
  else
    echo "No default Odoo container running. Usage: $0 [container_name]" >&2
    docker ps --format 'table {{.Names}}\t{{.Ports}}' >&2
    exit 1
  fi
fi

echo "==> Sync module to $CONTAINER:/mnt/extra-addons/$MODULE"
docker exec "$CONTAINER" mkdir -p "/mnt/extra-addons/$MODULE"
docker cp "$MODULE_SRC/." "$CONTAINER:/mnt/extra-addons/$MODULE/"

echo "==> Validate manifest parses as Python (Odoo ignores JSON true/false)"
docker exec "$CONTAINER" python3 -c "
import ast, pathlib
p = pathlib.Path('/mnt/extra-addons/$MODULE/__manifest__.py')
body = p.read_text()[p.read_text().find('{'):]
ast.literal_eval(body)
print('manifest OK')
"

if [[ "$DO_INSTALL" == "1" ]]; then
  echo "==> Install/upgrade via Odoo CLI (no Apps UI required)"
  INSTALL_FLAG="-u"
  if python3 - <<PY
import sys, xmlrpc.client
db = "$DB_NAME"
common = xmlrpc.client.ServerProxy("${ODOO_URL}/xmlrpc/2/common", allow_none=True)
uid = common.authenticate(db, "$ADMIN_USER", "$ADMIN_PASSWORD", {})
if not uid:
    sys.exit(0)
models = xmlrpc.client.ServerProxy("${ODOO_URL}/xmlrpc/2/object", allow_none=True)
rows = models.execute_kw(db, uid, "$ADMIN_PASSWORD", "ir.module.module", "search_read", [[("name", "=", "$MODULE")]], {"fields": ["state"], "limit": 1})
sys.exit(0 if rows and rows[0]["state"] == "installed" else 1)
PY
  then
    INSTALL_FLAG="-u"
  else
    INSTALL_FLAG="-i"
  fi
  docker exec "$CONTAINER" odoo \
    --db_host=db \
    -r odoo \
    -w odoo \
    -d "$DB_NAME" \
    "$INSTALL_FLAG" "$MODULE" \
    --stop-after-init \
    --without-demo=all
  echo "==> Restart Odoo"
  docker restart "$CONTAINER" >/dev/null
  sleep 3
fi

echo ""
echo "==> Configure Expert Bridge system parameters"
EXPERT_CONNECTION_ID="${EXPERT_CONNECTION_ID:-}"
EXPERT_WEB_BASE="${EXPERT_WEB_BASE:-}"
EXPERT_API_BASE="${EXPERT_API_BASE:-http://host.docker.internal:8001}"

# Local dev often runs Next on :3002 while Docker deploy uses :3000 — pick the stack that knows this connection.
if [[ -z "$EXPERT_WEB_BASE" && -n "$EXPERT_CONNECTION_ID" ]]; then
  for port in 3002 3000; do
    if curl -sf "http://127.0.0.1:${port}/api/connections/${EXPERT_CONNECTION_ID}" | grep -q '"id"'; then
      EXPERT_WEB_BASE="http://127.0.0.1:${port}"
      echo "    Detected web app on port ${port}"
      break
    fi
  done
fi

if [[ -z "$EXPERT_WEB_BASE" ]]; then
  for port in 3002 3000; do
    if curl -sf "http://127.0.0.1:${port}/api/connections" >/dev/null 2>&1; then
      EXPERT_WEB_BASE="http://127.0.0.1:${port}"
      echo "    Using first responsive web app on port ${port}"
      break
    fi
  done
fi

if [[ -z "$EXPERT_CONNECTION_ID" && -n "$EXPERT_API_BASE" ]]; then
  EXPERT_CONNECTION_ID="$(
    curl -sf "${EXPERT_API_BASE%/}/api/connections/resolve/by-instance?$(python3 -c "import urllib.parse; print(urllib.parse.urlencode({'url': '${ODOO_URL}', 'db_name': '${DB_NAME}'}))")" \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || true
  )"
fi

if [[ -n "$EXPERT_WEB_BASE" ]]; then
  python3 - <<PY
import xmlrpc.client
db = "$DB_NAME"
common = xmlrpc.client.ServerProxy("${ODOO_URL}/xmlrpc/2/common", allow_none=True)
uid = common.authenticate(db, "$ADMIN_USER", "$ADMIN_PASSWORD", {})
if not uid:
    raise SystemExit("Could not authenticate to Odoo — set params manually in Settings → Technical → System Parameters")
models = xmlrpc.client.ServerProxy("${ODOO_URL}/xmlrpc/2/object", allow_none=True)
params = {
    "expert_bridge.base_url": "$EXPERT_WEB_BASE",
    "expert_bridge.api_base_url": "$EXPERT_API_BASE",
}
cid = "$EXPERT_CONNECTION_ID".strip()
if cid:
    params["expert_bridge.connection_id"] = cid
for key, value in params.items():
    existing = models.execute_kw(
        db, uid, "$ADMIN_PASSWORD", "ir.config_parameter", "search", [[("key", "=", key)]]
    )
    if existing:
        models.execute_kw(db, uid, "$ADMIN_PASSWORD", "ir.config_parameter", "write", [existing, {"value": value}])
    else:
        models.execute_kw(
            db, uid, "$ADMIN_PASSWORD", "ir.config_parameter", "create", [{"key": key, "value": value}]
        )
    print(f"    {key} = {value}")
PY
else
  echo "    Could not auto-detect web app — set expert_bridge.base_url manually."
fi

echo ""
echo "Done."
echo "  Database: $DB_NAME"
echo "  Menu: Settings → Expert (Customization App)"
echo ""
echo "If Expert opens but shows 'Connection not found', your web port may differ:"
echo "  local dev (pnpm next dev -p 3002)  → expert_bridge.base_url = http://127.0.0.1:3002"
echo "  Docker deploy (compose)          → expert_bridge.base_url = http://127.0.0.1:3000"
echo "  Pass EXPERT_CONNECTION_ID=<uuid from /connections/{id}> to pin the right connection."
echo ""
echo "Odoo 19 note: there is no Settings → Technical → Modules menu."
echo "Use Apps (search '$MODULE') or this script for install."
