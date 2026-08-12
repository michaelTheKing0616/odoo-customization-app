#!/usr/bin/env python3
"""Wave 18 ELITE live gate — library prompt + scorecard + optional sandbox install."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("AI_ASSIST", "ollama")
os.environ.setdefault("SANDBOX_EXTRA_MODULES", "contacts,mail")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LIBRARY_PROMPT = (
    "Build a sophisticated library management system with books, loans, "
    "reservations, fines, and overdue reminders for library members"
)
_default_out = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "research"
    / f"elite_library_run_{datetime.now(UTC).strftime('%Y-%m-%d')}.json"
)
OUT = Path(os.environ["ELITE_GATE_OUT"]) if os.environ.get("ELITE_GATE_OUT") else _default_out
RUN_SANDBOX = os.environ.get("ELITE_GATE_SANDBOX", "0").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    from app.ai_elite import check_elite_scorecard_floors, elite_promote_gate
    from app.ai_ollama import draft_module_from_prompt, ollama_reachable
    from app.db import SessionLocal, init_db
    from app.db_models import OdooConnection
    from app.settings import settings

    reachable, detail = ollama_reachable(timeout_s=15.0)
    if not reachable:
        artifact = {
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "prompt": LIBRARY_PROMPT,
            "gate": "skipped",
            "reason": "Ollama unreachable",
            "ollama_detail": detail,
            "ai_assist": settings.ai_assist,
            "ai_pipeline_mode": settings.ai_pipeline_mode,
        }
        OUT.write_text(json.dumps(artifact, indent=2) + "\n")
        print(json.dumps(artifact, indent=2))
        return 1

    t0 = time.monotonic()
    error: str | None = None
    draft: dict = {}
    warnings: list[str] = []
    try:
        draft, _raw, warnings, _refusals = draft_module_from_prompt(
            LIBRARY_PROMPT,
            reuse_models=["res.partner"],
            expand=False,
        )
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
    elapsed = round(time.monotonic() - t0, 1)

    llm_status = draft.get("_llm_status") if isinstance(draft.get("_llm_status"), dict) else {}
    scorecard = draft.get("_scorecard") if isinstance(draft.get("_scorecard"), dict) else {}
    score = float(scorecard.get("score_0_10") or 0.0)
    floor_ok, floor_reasons = check_elite_scorecard_floors(scorecard) if scorecard else (False, ["missing scorecard"])
    gate_ok, gate_reasons = elite_promote_gate(draft) if draft else (False, ["empty draft"])

    sandbox_result: dict | None = None
    if RUN_SANDBOX and gate_ok and draft:
        from app.ai_elite_promote import run_elite_autopilot

        init_db()
        db = SessionLocal()
        try:
            cid = str(uuid.uuid4())
            db.add(
                OdooConnection(
                    id=cid,
                    name="Elite Live Gate",
                    url=settings.odoo_url,
                    db_name=settings.odoo_db,
                    username=settings.odoo_user,
                    secret_encrypted="dev-only-elite-gate",
                    server_version="19.0",
                )
            )
            db.commit()
            sandbox_result = run_elite_autopilot(db, connection_id=cid, spec=draft)
        finally:
            db.close()

    llm_mode = llm_status.get("mode")
    if error:
        gate = "error"
    elif llm_mode in {"llm_full", "llm_partial"} and floor_ok and gate_ok:
        gate = "pass"
    elif llm_mode in {"llm_full", "llm_partial"} and score >= float(settings.elite_scorecard_floor or 9.0):
        gate = "gate_partial"
    elif llm_mode in {"llm_full", "llm_partial"}:
        gate = "score_below_floor"
    else:
        gate = "deviation"

    artifact = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "prompt": LIBRARY_PROMPT,
        "gate": gate,
        "mode": "live_ollama_elite",
        "elapsed_s": elapsed,
        "ai_assist": settings.ai_assist,
        "ai_pipeline_mode": settings.ai_pipeline_mode,
        "ollama_model": settings.ollama_model,
        "elite_scorecard_floor": settings.elite_scorecard_floor,
        "_llm_status": llm_status,
        "score_0_10": score,
        "scorecard_floors_ok": floor_ok,
        "scorecard_floor_reasons": floor_reasons,
        "promote_gate_ok": gate_ok,
        "promote_gate_reasons": gate_reasons,
        "technical_name": draft.get("technical_name"),
        "domain_pack": draft.get("domain_pack"),
        "sandbox_enabled": RUN_SANDBOX,
        "sandbox": sandbox_result,
        "warnings_sample": warnings[:20],
    }
    if error:
        artifact["run_error"] = error
    OUT.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({k: artifact[k] for k in artifact if k != "draft"}, indent=2))
    if gate == "pass":
        return 0
    if gate == "score_below_floor":
        print(f"ELITE gate: score {score} below floor", file=sys.stderr)
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
