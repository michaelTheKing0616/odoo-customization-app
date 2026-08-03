#!/usr/bin/env bash
# Record 3 live /expert/ask transcripts → docs/research/expert_runs_<date>/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/api"
export EXPERT_RUNS_LIVE=1
export AI_ASSIST="${AI_ASSIST:-ollama}"
uv run pytest tests/test_expert_runs_live.py::test_record_expert_runs_live -s -m integration
echo "Expert runs written under docs/research/expert_runs_$(date +%Y-%m-%d)/"
