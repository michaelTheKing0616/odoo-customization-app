#!/usr/bin/env bash
# TRUST-5 dirty-instance gate: Odoo 19 sandbox with demo modules, seeded volume, smoke checks.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export ODOO_SANDBOX_IMAGE="${ODOO_SANDBOX_IMAGE:-odoo:19}"
export ODOO_HOST="${ODOO_HOST:-127.0.0.1}"
export ODOO_PORT="${ODOO_PORT:-18069}"
export SANDBOX_DB="${SANDBOX_DB:-sandbox_test}"
export SANDBOX_USER="${SANDBOX_USER:-admin}"
export SANDBOX_PASSWORD="${SANDBOX_PASSWORD:-admin}"
export DIRTY_RECORD_TARGET="${DIRTY_RECORD_TARGET:-50000}"
export DIRTY_QUICK="${DIRTY_QUICK:-0}"
export KEEP_DIRTY="${KEEP_DIRTY:-0}"

if [[ "${DIRTY_QUICK}" == "1" ]]; then
  export DIRTY_RECORD_TARGET=500
fi

echo "=== TRUST-5 dirty gate (target records=${DIRTY_RECORD_TARGET}) ==="

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI not found — skip dirty gate (set up Docker to run)." >&2
  exit 0
fi

echo "Starting sandbox stack on port ${ODOO_PORT}..."
docker compose -p odoo-sandbox -f docker/docker-compose.sandbox.yml up -d

ODOO_HOST="${ODOO_HOST}" ODOO_PORT="${ODOO_PORT}" MAX_ATTEMPTS=90 ./docker/wait-for-odoo.sh

echo "Initializing database ${SANDBOX_DB}..."
docker exec odoo-custom-sandbox-odoo odoo db \
  --db_host=db \
  -r odoo \
  -w odoo \
  init \
  --username="${SANDBOX_USER}" \
  --password="${SANDBOX_PASSWORD}" \
  --force \
  "${SANDBOX_DB}" >/dev/null

export PYTHONPATH="${ROOT}/packages/module-generator/src:${PYTHONPATH:-}"
uv run --directory "${ROOT}/apps/api" python "${ROOT}/docker/dirty_gate_smoke.py"
status=$?

if [[ "${KEEP_DIRTY}" != "1" ]]; then
  echo "Tearing down sandbox..."
  docker compose -p odoo-sandbox -f docker/docker-compose.sandbox.yml down -v --remove-orphans
else
  echo "KEEP_DIRTY=1 — sandbox left running at http://${ODOO_HOST}:${ODOO_PORT}"
fi

exit "${status}"
