#!/usr/bin/env python3
"""Live GEN2 gate — supermarket prompt via background draft job + artifact JSON."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Ensure Ollama path is active for gate runs (settings default is off).
os.environ.setdefault("AI_ASSIST", "ollama")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROMPT = "A large mega Super Market with multiple branches"
OUT = Path(__file__).resolve().parents[3] / "docs" / "research" / "gen2_run_2026-08-05.json"


def main() -> int:
    from app.ai_draft_jobs import run_draft_job_body
    from app.ai_ollama import ollama_reachable
    from app.db import SessionLocal
    from app.job_runner import create_job
    from app.settings import settings

    reachable, detail = ollama_reachable(timeout_s=15.0)
    if not reachable:
        artifact = {
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "prompt": PROMPT,
            "gate": "skipped",
            "reason": "Ollama unreachable",
            "ollama_detail": detail,
            "ai_assist": settings.ai_assist,
            "ollama_base_url": settings.ollama_base_url,
        }
        OUT.write_text(json.dumps(artifact, indent=2) + "\n")
        print(json.dumps(artifact, indent=2))
        return 1

    db = SessionLocal()
    try:
        row = create_job(db, kind="ai_draft", connection_id=None)
        job_id = row.id
        db.commit()
    finally:
        db.close()

    t0 = time.monotonic()
    error: str | None = None
    try:
        result = run_draft_job_body(
            job_id=job_id,
            prompt=PROMPT,
            available_models=None,
            installed_modules=None,
            stock_catalog=None,
            reuse_models=["res.partner"],
            rejected_reuse_models=None,
            reuse_views=None,
            reuse_actions=None,
            expand=True,
            pipeline=None,
            protected_manifest=None,
            odoo_version=None,
            grain_override=None,
            gallery_id=None,
            host_model_override=None,
            connect_points_override=None,
            client=None,
            db_factory=SessionLocal,
            connection_id=None,
        )
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        result = {"draft": {}, "warnings": [error]}
    elapsed = round(time.monotonic() - t0, 1)
    draft = result.get("draft") or {}
    llm_status = draft.get("_llm_status") or {}
    mode = llm_status.get("mode")
    models = [
        m.get("model")
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    ]
    artifact = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "prompt": PROMPT,
        "gate": "pass" if mode in {"llm_full", "llm_partial"} else "deviation",
        "mode": "live_ollama_background_job",
        "elapsed_s": elapsed,
        "ollama_reachable": True,
        "ollama_model": settings.ollama_model,
        "ollama_base_url": settings.ollama_base_url,
        "_llm_status": llm_status,
        "technical_name": draft.get("technical_name"),
        "display_name": draft.get("display_name"),
        "domain_pack": draft.get("domain_pack"),
        "model_count": len(models),
        "model_names_sample": models[:12],
        "error_key_absent": "error" not in draft,
        "warnings_sample": (result.get("warnings") or [])[:15],
    }
    if error:
        artifact["run_error"] = error
    OUT.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact, indent=2))
    return 0 if artifact["gate"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
