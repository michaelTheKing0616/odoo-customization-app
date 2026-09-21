#!/usr/bin/env bash
# Apply hint chrome + Studio Flash enrich toggle on Tope's Mac and restart :8001.
# Mac tip: machineId 4fc0d119-8958-4a46-954b-7411355d96ce
# Path: /Users/temitopeolaitanmichael/Odoo_Customization_App
# Branch: premium-local-tip
set -euo pipefail
CANDIDATES=(
  "/Users/temitopeolaitanmichael/Odoo_Customization_App"
  "${REPO:-}"
)
REPO=""
for c in "${CANDIDATES[@]}"; do
  [[ -n "$c" && -d "$c/.git" ]] && REPO="$c" && break
done
BRANCH="${BRANCH:-premium-local-tip}"
if [[ -z "$REPO" || ! -d "$REPO/.git" ]]; then
  echo "REPO not found. Set REPO=/path/to/Odoo_Customization_App" >&2
  exit 1
fi
cd "$REPO"
git fetch origin "$BRANCH" 2>/dev/null || true
git checkout "$BRANCH" 2>/dev/null || git checkout -B "$BRANCH"
if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  git stash push -u -m "pre-hint-chrome-toggle $(date +%Y%m%d-%H%M%S)" || true
fi
git pull --ff-only origin "$BRANCH" || true

cd apps/api
AI_INTENT_LLM=off uv run pytest \
  tests/test_ai_hint_chrome.py \
  tests/test_flash_ast_enrich_toggle.py \
  tests/test_ai_constraint_ast.py \
  tests/test_ai_conversation_understand.py \
  tests/test_prefer_field_pack_no_clarification_leak.py \
  tests/test_date_vs_datetime_classifier.py \
  -q

cd "$REPO"
if command -v lsof >/dev/null 2>&1 && lsof -iTCP:8001 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Restarting process on :8001…"
  PID="$(lsof -tiTCP:8001 -sTCP:LISTEN | head -1 || true)"
  if [[ -n "${PID:-}" ]]; then
    kill "$PID" || true
    sleep 1
  fi
fi
if [[ -x ./scripts/restart-api-8001.sh ]]; then
  ./scripts/restart-api-8001.sh
else
  echo "Start API on :8001 manually if needed."
fi
echo "SHA=$(git rev-parse --short HEAD)"
echo "Toggle: App Studio brief → Enrich Must-do with Flash (per connection)."
echo "Prefer Sales re-Build: status hint → canvas alert + Apply IR decoration (not Char)."
