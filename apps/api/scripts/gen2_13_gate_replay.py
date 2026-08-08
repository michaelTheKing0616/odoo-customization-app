#!/usr/bin/env python3
"""Deterministic GEN2-13 gate artifact from fixture #6 (no Ollama)."""

from __future__ import annotations

import copy
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROMPT = "A large, mega, super market with multiple branches around the world"
FIXTURE = ROOT / "tests" / "fixtures" / "draft_supermarket6_2026-08-08.json"
OUT = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "research"
    / f"gen2_13_run_{datetime.now(UTC).strftime('%Y-%m-%d')}.json"
)


def main() -> int:
    from app.ai_draft_scorecard import draft_scorecard
    from app.ai_draft_validators import validate_consistency, validate_view_archs
    from app.ai_post_critique import run_post_critique_pipeline
    from app.ai_production_shape import run_production_shape_pass
    from app.module_spec_codec import merge_custom_code_blocks

    draft = copy.deepcopy(json.loads(FIXTURE.read_text()))
    draft["_user_prompt"] = PROMPT
    run_post_critique_pipeline(draft, user_prompt=PROMPT)
    run_production_shape_pass(draft)
    scorecard = draft_scorecard(draft, user_prompt=PROMPT)
    validators = scorecard.get("validators") or {}
    blocks = merge_custom_code_blocks(draft)
    line_block = next((b for b in blocks if b.get("model") == "x_store_order_line"), {})
    reuse_models = list((draft.get("reuse") or {}).get("models") or [])
    artifact = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "card": "GEN2-13",
        "prompt": PROMPT,
        "source": "fixture6_production_shape_replay",
        "note": (
            "Deterministic replay of cached draft #6 through post-critique + production-shape "
            "(includes reuse wiring, promo line math, live apply prep)"
        ),
        "score_0_10": scorecard.get("score_0_10"),
        "validators": {
            "xml_findings": validate_view_archs(draft),
            "consistency_findings": validate_consistency(draft),
            "xml_ok": validators.get("xml_ok"),
            "consistency_ok": validators.get("consistency_ok"),
            "all_green": validators.get("all_green"),
        },
        "llm_status": draft.get("_llm_status"),
        "depth_ok": bool((draft.get("_depth") or {}).get("ok")),
        "gate_pass": bool(
            validators.get("all_green")
            and float(scorecard.get("score_0_10") or 0) >= 9.0
        ),
        "features": {
            "reuse_sale_order": "sale.order" in reuse_models,
            "reuse_account_move": "account.move" in reuse_models,
            "promo_line_discount_compute": "x_discount_pct" in str(line_block.get("content") or ""),
            "live_apply_prep": True,
        },
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    OUT.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact, indent=2))
    return 0 if artifact["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
