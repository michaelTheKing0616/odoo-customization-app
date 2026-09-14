"""Blocking Option A authoring gate — zip and sandbox stay locked until pass."""

from __future__ import annotations

from typing import Any

from app.ai_generation_engine import is_gold_option_a_draft
from app.ai_host_install import host_install_offers
from app.ai_option_a_policy import (
    extract_disclosure_ir,
    policy_findings,
    rpc_verify_findings,
)
from app.custom_code_authoring import lint_custom_code_blocks
from app.module_spec_codec import export_draft_module_zip


def is_option_a_authored_draft(draft: dict[str, Any] | None) -> bool:
    if not isinstance(draft, dict):
        return False
    ir = draft.get("_generation_engine")
    return isinstance(ir, dict) and ir.get("capability") == "option_a_authored"


def requires_authoring_gate(draft: dict[str, Any] | None) -> bool:
    """Gold zips are pre-validated. LLM-authored modules must pass this gate."""
    if not isinstance(draft, dict):
        return False
    if is_gold_option_a_draft(draft):
        return False
    return is_option_a_authored_draft(draft)


def authoring_status(draft: dict[str, Any] | None) -> str:
    rec = draft.get("_option_a_authoring") if isinstance(draft, dict) else None
    if isinstance(rec, dict) and rec.get("status"):
        return str(rec.get("status"))
    return ""


def authoring_gate_passed(draft: dict[str, Any] | None) -> bool:
    if not requires_authoring_gate(draft):
        return True
    return authoring_status(draft) == "pass"


def evaluate_authoring_gate(
    draft: dict[str, Any],
    *,
    client: Any | None = None,
    odoo_major: int = 19,
) -> dict[str, Any]:
    """Lint + policy + dry structural zip. Stamps ``_option_a_authoring``."""
    try:
        from app.ai_static_odoo import rewrite_draft_stock_xpaths

        rewrite_draft_stock_xpaths(draft)
    except Exception:  # noqa: BLE001
        pass
    findings: list[dict[str, Any]] = []
    lint = lint_custom_code_blocks(draft)
    if not lint.get("ok"):
        for row in lint.get("blocks") or []:
            if not isinstance(row, dict):
                continue
            for issue in row.get("issues") or []:
                if not isinstance(issue, dict):
                    continue
                findings.append(
                    {
                        "code": str(issue.get("code") or "lint"),
                        "message": str(issue.get("message") or "lint failed"),
                        "file": str(row.get("source_file") or ""),
                    }
                )
        if not findings:
            findings.append(
                {"code": "lint_failed", "message": "custom_code_blocks lint failed", "file": ""}
            )

    for row in policy_findings(draft):
        findings.append(row)
    for row in rpc_verify_findings(draft, client):
        findings.append(row)

    if not (draft.get("custom_code_blocks") or []):
        findings.append(
            {
                "code": "empty_module",
                "message": "No custom_code_blocks yet — zip and sandbox stay locked.",
                "file": "",
            }
        )

    if not findings:
        try:
            zip_bytes = export_draft_module_zip(draft, odoo_major=odoo_major)
            from app.ai_structural_zip_gate import structural_zip_gate

            gate = structural_zip_gate(zip_bytes)
            if not gate.get("ok"):
                for msg in gate.get("findings") or []:
                    findings.append(
                        {
                            "code": "structural_zip",
                            "message": str(msg),
                            "file": "__manifest__.py",
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            findings.append(
                {
                    "code": "zip_build_failed",
                    "message": str(exc),
                    "file": "__manifest__.py",
                }
            )

    status = "pass" if not findings else "fail"
    offers = host_install_offers(findings)
    payload = {
        "status": status,
        "findings": findings,
        "disclosure": extract_disclosure_ir(draft),
        "http_hosts": extract_disclosure_ir(draft).get("http_hosts") or [],
        "host_install": offers,
    }
    draft["_option_a_authoring"] = payload
    ir = draft.get("_generation_engine")
    if isinstance(ir, dict):
        ir["option_a_authoring"] = {
            "status": status,
            "finding_count": len(findings),
            "host_install_count": len(offers),
        }
        if status != "pass":
            ir["user_phase"] = "failed"
    return payload


def authoring_block_detail(draft: dict[str, Any]) -> dict[str, Any]:
    rec = draft.get("_option_a_authoring") if isinstance(draft.get("_option_a_authoring"), dict) else {}
    return {
        "option_a_authoring_blocked": True,
        "status": rec.get("status") or "fail",
        "findings": rec.get("findings") or [
            {
                "code": "not_evaluated",
                "message": "Option A authoring gate has not passed. Zip and sandbox stay locked.",
            }
        ],
        "http_hosts": rec.get("http_hosts") or [],
        "host_install": rec.get("host_install") or [],
        "message": "LLM-authored module is not ready — fix gate findings before zip or sandbox.",
    }


def raise_if_authoring_blocked(draft: dict[str, Any]) -> None:
    from fastapi import HTTPException

    if authoring_gate_passed(draft):
        return
    if requires_authoring_gate(draft) and authoring_status(draft) != "pass":
        evaluate_authoring_gate(draft)
    if authoring_gate_passed(draft):
        return
    raise HTTPException(status_code=422, detail=authoring_block_detail(draft))
