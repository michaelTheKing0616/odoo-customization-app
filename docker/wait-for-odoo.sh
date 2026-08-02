#!/usr/bin/env bash
# Wait until Odoo HTTP responds on localhost:8069.
set -euo pipefail

HOST="${ODOO_HOST:-127.0.0.1}"
PORT="${ODOO_PORT:-8069}"
URL="http://${HOST}:${PORT}/web/login"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-60}"

echo "Waiting for Odoo at ${URL} ..."
for ((i = 1; i <= MAX_ATTEMPTS; i++)); do
  if curl -sf -o /dev/null "$URL"; then
    echo "Odoo is up (attempt ${i})."
    exit 0
  fi
  sleep 2
done

echo "Odoo did not become ready within $((MAX_ATTEMPTS * 2))s" >&2
exit 1
