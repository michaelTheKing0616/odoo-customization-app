#!/usr/bin/env bash
# Apply P0 any-customization class spine (+ P1 Job3 report scrub scaffold) onto Tope's Mac checkout.
# machineId: 4fc0d119-8958-4a46-954b-7411355d96ce
set -euo pipefail
REPO="${1:-/Users/temitopeolaitanmichael/Odoo_Customization_App}"
PATCH="${2:-/workspace/0001-feat-ingenium-any-customization-p0.patch}"
cd "$REPO"
git checkout premium-local-tip
git status -sb

STASHED=0
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "Local WIP present — stashing before apply"
  git stash push -u -m "pre-any-customization-p0-apply"
  STASHED=1
fi

git fetch origin premium-local-tip || true

if [ -f "$PATCH" ]; then
  git am --3way "$PATCH" || {
    git am --abort 2>/dev/null || true
    git apply --check "$PATCH" && git apply "$PATCH"
    git add \
      DOCKET.md MEMORY.md \
      apps/api/app/ai_class_stamp.py \
      apps/api/app/ai_conversation/understand.py \
      apps/api/app/ai_generation_engine.py \
      apps/api/app/ai_option_a_acceptance.py \
      apps/api/app/ai_studio_contract.py \
      apps/api/app/hosting.py \
      apps/api/app/intent_router/catalog.yaml \
      apps/api/app/intent_router/catalog.json \
      apps/api/app/promote.py \
      apps/api/app/tier_gating.py \
      apps/api/app/tier_matrix.py \
      apps/api/tests/test_class_stamp.py \
      apps/api/tests/test_hosting_m1.py \
      apps/api/tests/test_intent_router_class_routes.py \
      APPLY_ANY_CUSTOMIZATION_P0_ON_MAC.sh
    git commit -m "feat(ingenium): any-customization P0 class spine + report scrub scaffold"
  }
else
  echo "WARN: patch missing at $PATCH — pull/cherry-pick from tip instead"
  git pull --ff-only origin premium-local-tip || true
fi

git push origin premium-local-tip || echo "WARN: push failed — push manually"

if [ "$STASHED" = "1" ]; then
  git stash pop || echo "WARN: stash pop conflict — resolve manually"
fi

# Restart API :8001
pkill -f "uvicorn .*8001" 2>/dev/null || true
sleep 1
cd "$REPO/apps/api"
if [ -f ../../.venv/bin/uvicorn ]; then
  UV=../../.venv/bin/uvicorn
elif [ -f .venv/bin/uvicorn ]; then
  UV=.venv/bin/uvicorn
else
  UV=uvicorn
fi
nohup "$UV" app.main:app --host 127.0.0.1 --port 8001 --reload \
  > /tmp/ingenium-api-8001.log 2>&1 &
echo "API restarting on :8001 — log /tmp/ingenium-api-8001.log"
echo "Done. Product: ingenium. Completeness ≠ Cert ≠ Autopilot. Promote stays human."
