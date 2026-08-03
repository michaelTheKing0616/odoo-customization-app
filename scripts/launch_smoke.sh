#!/usr/bin/env bash
# LAUNCH-1 / PROD-1 — post-deploy smoke (local, staging, or compose deploy profile).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="${API_URL:-http://127.0.0.1:8000}"
WEB="${WEB_URL:-http://127.0.0.1:3000}"
COMPOSE_FILE="${COMPOSE_FILE:-docker/docker-compose.deploy.yml}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-odoo-custom-deploy-smoke}"

echo "== Health =="
curl -sf "$API/health" | head -c 400
echo ""

echo "== Billing plans (public) =="
curl -sf "$API/api/billing/plans" | head -c 200
echo ""

echo "== Web pricing page =="
code=$(curl -so /dev/null -w "%{http_code}" "$WEB/pricing")
test "$code" = "200" && echo "OK pricing $code" || { echo "FAIL pricing $code"; exit 1; }

echo "== Web landing =="
code=$(curl -so /dev/null -w "%{http_code}" "$WEB/")
test "$code" = "200" && echo "OK landing $code" || { echo "FAIL landing $code"; exit 1; }

if [[ "${LAUNCH_COMPOSE_SMOKE:-0}" == "1" ]]; then
  echo "== Compose deploy boot smoke =="
  docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/$COMPOSE_FILE" up -d --build --wait
  trap 'docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/$COMPOSE_FILE" down -v' EXIT
  curl -sf "$API/health" >/dev/null
  curl -sf "$WEB/pricing" >/dev/null
  echo "OK compose deploy stack healthy"
fi

echo "LAUNCH-1 smoke passed."
