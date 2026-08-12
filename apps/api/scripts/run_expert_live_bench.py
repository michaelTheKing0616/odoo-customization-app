#!/usr/bin/env python3
"""Run Expert eval against live Ollama and write bench artifact."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

# Ensure app importable when run from repo root
ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.db import SessionLocal, init_db  # noqa: E402
from app.expert.ask import ask_expert, expert_assist_enabled  # noqa: E402
from tests.test_expert_eval import (  # noqa: E402
    EVAL_SET_PATH,
    EvalScore,
    load_eval_set,
    score_eval_item,
    summarize_scores,
    _chunks_from_item,
)


def summarize_scores_extended(scores: list[EvalScore]) -> dict:
    from tests.test_expert_eval import summarize_scores

    return summarize_scores(scores)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Expert live bench")
    parser.add_argument(
        "--real-retrieval",
        action="store_true",
        help="Use ingested expert_chunks from Postgres (no mock_chunks override)",
    )
    args = parser.parse_args()

    if not expert_assist_enabled():
        print("AI_ASSIST must be enabled (ollama recommended)", file=sys.stderr)
        return 2

    init_db()
    items = load_eval_set()
    db = SessionLocal()
    scores: list[EvalScore] = []
    try:
        from app.db_models import OdooConnection

        conn = db.query(OdooConnection).order_by(OdooConnection.updated_at.desc()).first()
        for item in items:
            import app.expert.ask as ask_mod

            orig = None
            if not args.real_retrieval:
                item_chunks = _chunks_from_item(item)

                def _retrieve(_db, _q, *, version=None, top_k=8, min_score=0.35, chunks=item_chunks):
                    return chunks

                orig = ask_mod.retrieve_expert_chunks
                ask_mod.retrieve_expert_chunks = _retrieve  # type: ignore[assignment]

            try:
                connection_id = item.get("connection_id")
                if connection_id and str(connection_id).startswith("eval-"):
                    connection_id = conn.id if conn else None

                provider = None
                fake = item.get("fake_response")
                if fake and not item.get("tier1_refusal") and not args.real_retrieval:
                    from tests.test_expert_eval import _EvalFakeLLM

                    provider = _EvalFakeLLM(fake)

                result = ask_expert(
                    db,
                    question=str(item["question"]),
                    connection_id=connection_id,
                    ui_context=item.get("ui_context"),
                    provider=provider,
                )
            finally:
                if orig is not None:
                    ask_mod.retrieve_expert_chunks = orig

            scores.append(score_eval_item(item, result))
    finally:
        db.close()

    summary = summarize_scores_extended(scores)
    summary["mode"] = "live_ollama_real_retrieval" if args.real_retrieval else "live_ollama_mock_chunks"
    summary["eval_set_size"] = len(items)
    summary["eval_set_path"] = str(EVAL_SET_PATH.relative_to(ROOT))

    out_dir = ROOT / "docs" / "research"
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "real" if args.real_retrieval else "mock"
    out_path = out_dir / f"expert_bench_{date.today().isoformat()}_{suffix}.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")

    target = float(os.getenv("EXPERT_BENCH_CITATION_TARGET", "0.9"))
    answered_rate = summary.get("citation_presence_answered", 0.0)
    if answered_rate < target:
        print(
            f"WARN: citation_presence_answered {answered_rate} < target {target}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
