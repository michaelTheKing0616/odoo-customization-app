"""ELITE-4 — scorecard-gated export → sandbox → validation for promote autopilot."""

from __future__ import annotations

import base64
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.ai_elite import elite_promote_gate
from app.custom_code_authoring import lint_custom_code_blocks
from app.module_spec_codec import export_draft_module_zip
from app.odoo_service import get_connection_or_404
from app.promote import record_sandbox_validation, sha256_bytes
from app.sandbox import resolve_sandbox_major, run_sandbox_install

logger = logging.getLogger(__name__)


def _connection_odoo_major(server_version: str | None) -> int:
    if not server_version:
        return 19
    try:
        return int(str(server_version).split(".")[0])
    except ValueError:
        return 19


def run_elite_autopilot(
    db: Session,
    *,
    connection_id: str,
    spec: dict[str, Any],
    odoo_major: int | None = None,
    skip_gate: bool = False,
) -> dict[str, Any]:
    """Export draft zip, run sandbox install, record validation when gate passes."""
    gate_ok, gate_reasons = elite_promote_gate(spec)
    if not skip_gate and not gate_ok:
        return {
            "ok": False,
            "gate_passed": False,
            "gate_reasons": gate_reasons,
            "message": "Elite promote gate failed — improve draft scorecard or fix lint.",
        }

    lint = lint_custom_code_blocks(spec)
    if not lint.get("ok"):
        return {
            "ok": False,
            "gate_passed": gate_ok,
            "lint": lint,
            "message": "Custom code lint failed.",
        }

    conn = get_connection_or_404(db, connection_id)
    major = resolve_sandbox_major(odoo_major or _connection_odoo_major(conn.server_version))
    tech = str(spec.get("technical_name") or "custom_module")
    zip_bytes = export_draft_module_zip(spec, odoo_major=major)

    result = run_sandbox_install(
        zip_bytes=zip_bytes,
        module_name=tech,
        odoo_major=major,
        extra_modules=list(spec.get("depends") or []),
    )
    if not result.ok:
        return {
            "ok": False,
            "gate_passed": gate_ok,
            "lint": lint,
            "sandbox": {
                "ok": result.ok,
                "module": result.module,
                "message": result.message,
                "log_tail": result.log_tail,
            },
            "zip_sha256": sha256_bytes(zip_bytes),
            "message": result.message or "Sandbox install failed",
        }

    validation = record_sandbox_validation(
        db,
        connection_id=connection_id,
        module_name=tech,
        zip_bytes=zip_bytes,
    )
    scorecard = spec.get("_scorecard") if isinstance(spec.get("_scorecard"), dict) else {}
    return {
        "ok": True,
        "gate_passed": True,
        "gate_reasons": gate_reasons,
        "lint": lint,
        "validation_id": validation.id,
        "zip_sha256": validation.zip_sha256,
        "zip_base64": base64.b64encode(zip_bytes).decode("ascii"),
        "sandbox": {
            "ok": result.ok,
            "module": result.module,
            "message": result.message,
            "log_tail": result.log_tail,
        },
        "score_0_10": scorecard.get("score_0_10"),
        "technical_name": tech,
        "message": "Sandbox validation passed — ready to promote.",
    }


__all__ = ["run_elite_autopilot"]
