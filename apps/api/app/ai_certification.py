"""Evidence-backed Certification — separate from ModuleSpec completeness 10.0
and from Job Autopilot process smoke.

Quality ≈ scorecard. Evidence ≈ checks run. Risk ≈ unknowns.
Tiers: Reject | ReviewRequired | Production | Gold.
Promote stays human even at Gold.
Autopilot job scorecard is never this artifact.
"""

from __future__ import annotations

from typing import Any, Literal

CertificationTier = Literal["Reject", "ReviewRequired", "Production", "Gold"]

_CLONE_LEAVES = frozenset(
    {
        "bill",
        "invoice",
        "payment",
        "attorney",
        "lawyer",
        "employee",
        "staff",
        "task",
        "event",
        "meeting",
        "product",
        "partner",
        "customer",
        "client",
    }
)


def _scorecard_quality(draft: dict[str, Any]) -> float:
    sc = draft.get("_scorecard") if isinstance(draft.get("_scorecard"), dict) else {}
    raw = sc.get("score_0_10")
    try:
        return max(0.0, min(100.0, float(raw or 0) * 10.0))
    except (TypeError, ValueError):
        return 0.0


def _ledger_entry(
    check_id: str,
    *,
    status: Literal["PASS", "FAIL", "SKIP", "UNKNOWN"],
    detail: str = "",
    run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "check": check_id,
        "status": status,
        "detail": detail,
        **({"run_id": run_id} if run_id else {}),
    }


def _has_forbidden_clones(draft: dict[str, Any]) -> list[str]:
    plan = draft.get("_architecture_plan") if isinstance(draft.get("_architecture_plan"), dict) else {}
    forbidden = {
        str(x).strip().lower()
        for x in (plan.get("forbidden_clones") or [])
        if str(x).strip()
    }
    hits: list[str] = []
    for model in draft.get("models") or []:
        if not isinstance(model, dict):
            continue
        mid = str(model.get("model") or "")
        if not mid.startswith("x_"):
            continue
        if str(model.get("mode") or "") == "inherit":
            continue
        leaf = mid.split(".")[-1].removeprefix("x_").lower()
        if mid.lower() in forbidden or leaf in forbidden or leaf in _CLONE_LEAVES:
            if forbidden and (
                mid.lower() in forbidden
                or f"x_{leaf}" in forbidden
                or leaf in {f.removeprefix("x_") for f in forbidden}
            ):
                hits.append(mid)
            elif not forbidden and leaf in {"bill", "invoice", "attorney", "lawyer", "payment"}:
                hits.append(mid)
    try:
        from app.ai_stock_first import list_stock_clone_models

        for mid in list_stock_clone_models(draft):
            if mid not in hits:
                hits.append(mid)
    except Exception:  # noqa: BLE001
        pass
    return hits


def _option_a_pending(draft: dict[str, Any]) -> bool:
    done = draft.get("_done_bar") if isinstance(draft.get("_done_bar"), dict) else {}
    if str(done.get("option_a") or "") == "scaffold_pending_smoke":
        return True
    smoke = draft.get("_option_a_smoke") if isinstance(draft.get("_option_a_smoke"), dict) else {}
    if draft.get("_capability_primary_option_a") and not smoke.get("ok"):
        return True
    gaps = draft.get("_capability_gaps") or []
    if gaps and not smoke.get("ok"):
        # Mixed briefs still need Option A prove for QR/pay surfaces
        gap_ids = {
            str(g.get("id") if isinstance(g, dict) else getattr(g, "id", "") or "")
            for g in gaps
        }
        if gap_ids & {
            "qr_on_document",
            "click_to_pay",
            "pdf_report",
            "payment_provider",
            "website_controller",
            "owl_widget",
            "python_logic",
        }:
            return True
    blocks = draft.get("custom_code_blocks") or []
    if blocks and not smoke.get("ok"):
        # Any Option A / compute zip without smoke is not Production
        if any(
            isinstance(b, dict)
            and (
                b.get("option_a")
                or str(b.get("source") or "").startswith("capability")
                or str(b.get("kind") or "") in {"xml", "qweb", "python"}
                or "report" in str(b.get("source_file") or "")
                or "payment" in str(b.get("source_file") or "")
                or "apply_readiness" in str(b.get("reason") or "")
            )
            for b in blocks
        ):
            return True
    return False


def build_certification(draft: dict[str, Any]) -> dict[str, Any]:
    """Compute certification from draft evidence (scorecard, smoke, plan, static)."""
    ledger: list[dict[str, Any]] = []
    hard_failures: list[str] = []

    sc = draft.get("_scorecard") if isinstance(draft.get("_scorecard"), dict) else {}
    validators = sc.get("validators") if isinstance(sc.get("validators"), dict) else {}
    validators_green = bool(validators.get("all_green"))
    ledger.append(
        _ledger_entry(
            "scorecard_validators",
            status="PASS" if validators_green else ("FAIL" if validators else "UNKNOWN"),
            detail="validators.all_green" if validators_green else "validators gaps or missing",
        )
    )

    quality = _scorecard_quality(draft)
    ledger.append(
        _ledger_entry(
            "completeness_scorecard",
            status="PASS" if quality >= 70 else "FAIL",
            detail=f"score_0_10={(sc.get('score_0_10'))} → quality={quality:.1f}",
        )
    )

    smoke = draft.get("_option_a_smoke") if isinstance(draft.get("_option_a_smoke"), dict) else {}
    option_a_primary = bool(draft.get("_capability_primary_option_a"))
    option_a_pending = _option_a_pending(draft)
    if option_a_primary or option_a_pending:
        smoke_ok = bool(smoke.get("ok"))
        ledger.append(
            _ledger_entry(
                "option_a_sandbox_smoke",
                status="PASS" if smoke_ok else "FAIL",
                detail=str(smoke.get("message") or ("ok" if smoke_ok else "unproven")),
                run_id=str(smoke.get("run_id") or "") or None,
            )
        )
        if not smoke_ok:
            hard_failures.append("option_a_smoke_failed")
    else:
        ledger.append(
            _ledger_entry(
                "option_a_sandbox_smoke",
                status="SKIP",
                detail="no Option A surfaces pending",
            )
        )

    # Explicit: Autopilot process smoke is a different scorecard — never inflate Cert
    ledger.append(
        _ledger_entry(
            "autopilot_process_smoke",
            status="SKIP",
            detail=(
                "Job Autopilot quote→invoice + custom Confirm is a separate done-bar; "
                "ModuleSpec Certification never means Autopilot passed"
            ),
        )
    )

    install = draft.get("_sandbox_install") if isinstance(draft.get("_sandbox_install"), dict) else {}
    if install:
        ok = bool(install.get("ok"))
        ledger.append(
            _ledger_entry(
                "sandbox_install",
                status="PASS" if ok else "FAIL",
                detail=str(install.get("message") or ""),
                run_id=str(install.get("job_id") or "") or None,
            )
        )
        if not ok:
            hard_failures.append("module_does_not_install")
    else:
        needs_zip = option_a_primary or option_a_pending
        if not needs_zip:
            from app.ai_option_a_quality import is_option_a_runtime_block

            needs_zip = any(
                isinstance(b, dict) and is_option_a_runtime_block(b)
                for b in (draft.get("custom_code_blocks") or [])
            )
        ledger.append(
            _ledger_entry(
                "sandbox_install",
                status="UNKNOWN" if needs_zip else "SKIP",
                detail="no sandbox install evidence yet" if needs_zip else "live metadata path",
            )
        )

    clones = _has_forbidden_clones(draft)
    if clones:
        hard_failures.append("stock_clone_models")
        ledger.append(
            _ledger_entry(
                "architecture_no_clones",
                status="FAIL",
                detail=", ".join(clones[:8]),
            )
        )
    else:
        ledger.append(
            _ledger_entry("architecture_no_clones", status="PASS", detail="no scorecard clones")
        )

    plan = draft.get("_architecture_plan") if isinstance(draft.get("_architecture_plan"), dict) else {}
    if plan:
        drift = draft.get("_architecture_drift") if isinstance(draft.get("_architecture_drift"), list) else []
        ledger.append(
            _ledger_entry(
                "architecture_plan",
                status="FAIL" if drift else "PASS",
                detail="; ".join(str(d) for d in drift[:5]) if drift else "plan present",
            )
        )
        if drift:
            hard_failures.append("architecture_plan_drift")
    else:
        ledger.append(
            _ledger_entry(
                "architecture_plan",
                status="UNKNOWN",
                detail="plan not stamped",
            )
        )

    shape = str(plan.get("document_shape") or draft.get("_document_shape") or "")
    hosts_hit: list[str] = []
    try:
        from app.ai_document_shape import forbidden_stock_hosts

        forbidden_hosts = forbidden_stock_hosts(draft)
        for model in draft.get("models") or []:
            if not isinstance(model, dict):
                continue
            mid = str(model.get("model") or "")
            if str(model.get("mode") or "") == "inherit" and mid in forbidden_hosts:
                hosts_hit.append(mid)
    except Exception:  # noqa: BLE001
        forbidden_hosts = set()
    if hosts_hit:
        hard_failures.append("out_of_scope_stock_host")
        ledger.append(
            _ledger_entry(
                "prompt_fit_hosts",
                status="FAIL",
                detail=", ".join(hosts_hit[:8]),
            )
        )
    else:
        ledger.append(
            _ledger_entry("prompt_fit_hosts", status="PASS", detail="no out-of-scope inherits")
        )

    if shape == "register":
        sats = [
            str(m.get("model"))
            for m in (draft.get("models") or [])
            if isinstance(m, dict)
            and (
                str(m.get("model") or "").endswith("_party")
                or str(m.get("model") or "").endswith("_line")
            )
        ]
        if sats:
            hard_failures.append("register_satellites")
            ledger.append(
                _ledger_entry(
                    "prompt_fit_register",
                    status="FAIL",
                    detail=", ".join(sats[:8]),
                )
            )
        else:
            ledger.append(
                _ledger_entry("prompt_fit_register", status="PASS", detail="no satellites")
            )

    static = draft.get("_static_odoo") if isinstance(draft.get("_static_odoo"), dict) else {}
    critical_static = [
        f
        for f in (static.get("findings") or [])
        if isinstance(f, dict) and str(f.get("severity") or "").lower() == "critical"
    ]
    if static:
        ledger.append(
            _ledger_entry(
                "static_odoo",
                status="FAIL" if critical_static else "PASS",
                detail=f"{len(static.get('findings') or [])} finding(s)",
            )
        )
        if critical_static:
            hard_failures.append("static_critical")
    else:
        has_code = bool(draft.get("custom_code_blocks"))
        ledger.append(
            _ledger_entry(
                "static_odoo",
                status="UNKNOWN" if has_code else "SKIP",
                detail="not analyzed" if has_code else "no custom_code_blocks",
            )
        )

    applicable = [e for e in ledger if e["status"] != "SKIP"]
    passed = [e for e in applicable if e["status"] == "PASS"]
    unknown = [e for e in applicable if e["status"] == "UNKNOWN"]
    evidence = (
        round(100.0 * len(passed) / len(applicable), 1) if applicable else 0.0
    )
    risk = min(
        100.0,
        round(
            15.0 * len(unknown)
            + 25.0 * len(hard_failures)
            + (20.0 if option_a_pending else 0.0),
            1,
        ),
    )

    if hard_failures:
        tier: CertificationTier = "Reject"
    elif evidence < 50 or quality < 70:
        tier = "ReviewRequired"
    elif evidence >= 85 and quality >= 90 and risk <= 15:
        tier = "Gold"
    elif evidence >= 70 and quality >= 80 and risk <= 35:
        tier = "Production"
    else:
        tier = "ReviewRequired"

    grain = str(draft.get("grain") or "")
    # field_pack live-only: Production without sandbox when validators green
    if (
        grain == "field_pack"
        and not option_a_primary
        and not option_a_pending
        and validators_green
        and quality >= 80
        and not hard_failures
        and tier == "ReviewRequired"
    ):
        tier = "Production"

    # Hard honesty: pending Option A / unproven zip never ships as Production/Gold
    if option_a_pending and tier in {"Production", "Gold"}:
        tier = "ReviewRequired"

    # full_app residual: unknown sandbox install caps Gold
    if (
        tier == "Gold"
        and any(e.get("check") == "sandbox_install" and e.get("status") == "UNKNOWN" for e in ledger)
    ):
        tier = "Production" if not option_a_pending else "ReviewRequired"

    engine = draft.get("_generation_engine") if isinstance(draft.get("_generation_engine"), dict) else {}
    stock_reuse = (
        engine.get("capability") == "stock_reuse"
        or str(draft.get("technical_name") or "") == "stock_reuse"
    )
    if stock_reuse:
        ledger.append(
            _ledger_entry(
                "stock_reuse_modulespec",
                status="SKIP",
                detail="Empty spec — no custom ModuleSpec to certify. Job Autopilot is the done-bar.",
            )
        )
        if tier in {"Production", "Gold"}:
            tier = "ReviewRequired"

    # Unknown / unproven sandbox must not be Production for full_app residuals
    live = draft.get("_live_apply") if isinstance(draft.get("_live_apply"), dict) else {}
    live_rpc = bool(live.get("rpc_ok") or draft.get("_live_apply_rpc_ok"))
    install_row = next(
        (e for e in ledger if e.get("check") == "sandbox_install"),
        {},
    )
    install_status = str(install_row.get("status") or "SKIP")
    if (
        not stock_reuse
        and grain != "field_pack"
        and not option_a_primary
        and install_status != "PASS"
        and not live_rpc
        and tier in {"Production", "Gold"}
    ):
        tier = "ReviewRequired"
        ledger.append(
            _ledger_entry(
                "full_app_sandbox_evidence",
                status="UNKNOWN",
                detail="ReviewRequired until sandbox install or live Apply RPC is evidenced",
            )
        )

    note = (
        "This brief has no custom residual. Completeness 10.0 is empty-spec hygiene, "
        "not a shippable ModuleSpec. Run Job Autopilot for sandbox install and "
        "quote→invoice smoke. Promote stays human."
        if stock_reuse
        else (
            "ModuleSpec completeness (_scorecard) is separate from Certification. "
            "Certification is separate from Job Autopilot process smoke. "
            "Promote stays human even at Gold."
        )
    )

    return {
        "tier": tier,
        "quality": quality,
        "evidence": evidence,
        "risk": risk,
        "hard_failures": hard_failures,
        "evidence_ledger": ledger,
        "completeness_score_0_10": sc.get("score_0_10"),
        "option_a_pending": option_a_pending,
        "note": note,
    }


def stamp_certification(draft: dict[str, Any]) -> dict[str, Any]:
    cert = build_certification(draft)
    draft["_certification"] = cert
    meta = draft.get("_meta") if isinstance(draft.get("_meta"), dict) else {}
    draft["_meta"] = {
        **meta,
        "certification_tier": cert.get("tier"),
        "certification_quality": cert.get("quality"),
        "certification_evidence": cert.get("evidence"),
        "certification_risk": cert.get("risk"),
        "option_a_pending": cert.get("option_a_pending"),
    }
    return cert


__all__ = [
    "build_certification",
    "stamp_certification",
]
