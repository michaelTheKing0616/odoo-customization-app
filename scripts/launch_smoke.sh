#!/usr/bin/env bash
# LAUNCH-1 — post-deploy smoke (local or staging). No secrets required.
set -euo pipefail
API="${API_URL:-http://127.0.0.1:8000}"
WEB="${WEB_URL:-http://127.0.0.1:3000}"

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

echo "LAUNCH-1 smoke passed."
