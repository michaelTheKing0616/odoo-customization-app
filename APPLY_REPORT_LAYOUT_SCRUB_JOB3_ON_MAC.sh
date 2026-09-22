#!/usr/bin/env bash
# Apply P1 Job3 report/document layout address scrub CLASS onto Tope's Mac checkout.
# machineId: 4fc0d119-8958-4a46-954b-7411355d96ce
set -euo pipefail
REPO="${1:-/Users/temitopeolaitanmichael/Odoo_Customization_App}"
PATCH="${2:-/workspace/0001-feat-ingenium-report-layout-scrub-job3.patch}"
cd "$REPO"
git checkout premium-local-tip
git status -sb

STASHED=0
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "Local WIP present — stashing before apply"
  git stash push -u -m "pre-report-layout-scrub-job3-apply"
  STASHED=1
fi

git fetch origin premium-local-tip || true

if [ -f "$PATCH" ]; then
  git am --3way "$PATCH" || {
    git am --abort 2>/dev/null || true
    git apply --check "$PATCH" && git apply "$PATCH"
    git add \
      DOCKET.md MEMORY.md \
      apps/api/app/ai_report_layout_scrub.py \
      apps/api/app/ai_capability_gaps.py \
      apps/api/app/ai_capability_option_a_scaffold.py \
      apps/api/app/ai_class_stamp.py \
      apps/api/app/ai_generation_engine.py \
      apps/api/app/ai_grain.py \
      apps/api/app/ai_option_a_acceptance.py \
      apps/api/app/ai_option_a_author.py \
      apps/api/tests/test_report_layout_scrub_class.py \
      APPLY_REPORT_LAYOUT_SCRUB_JOB3_ON_MAC.sh
    git commit -m "feat(ingenium): P1 Job3 report/document layout address scrub CLASS"
  }
else
  echo "WARN: patch missing at $PATCH — pull/cherry-pick from tip instead"
  git pull --ff-only origin premium-local-tip || true
fi

git push origin premium-local-tip || echo "WARN: push failed — push manually"

if [ "$STASHED" = "1" ]; then
  git stash pop || echo "WARN: stash pop conflict — resolve manually"
fi

pkill -f "uvicorn .*8001" 2>/dev/null || true
sleep 1
cd "$REPO/apps/api"
if [ -f ../../.venv/bin/uvicorn ]; then UV=../../.venv/bin/uvicorn
elif [ -f .venv/bin/uvicorn ]; then UV=.venv/bin/uvicorn
else UV=uvicorn; fi
nohup "$UV" app.main:app --host 127.0.0.1 --port 8001 --reload \
  > /tmp/ingenium-api-8001.log 2>&1 &
echo "API restarting on :8001 — log /tmp/ingenium-api-8001.log"
echo "Done. ingenium Job3 report layout scrub CLASS. Completeness ≠ Cert ≠ Autopilot. Promote stays human."
