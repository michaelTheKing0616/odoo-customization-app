"""Option A quality bar — done-bar, score caps, structural + RPC smoke.

Senior 10.0 for capability-primary drafts requires sandbox proof.
Promote to another connection stays human (go_live_ready != auto-prod).
"""

from __future__ import annotations

from typing import Any, Callable

from app.ai_capability_gaps import assess_capability_gaps


OPTION_A_SCORE_CAP = 7.0


def is_option_a_runtime_block(block: dict[str, Any]) -> bool:
    """Elite tests/i18n are zip hygiene, not Pay/QR/OWL Option A.

    Custom Python/XML/QWeb still counts (including elite computes). Only the
    ``tests/`` and ``i18n/`` installable-module extras are excluded.
    """
    kind = str(block.get("kind") or block.get("language") or "").lower()
    path = str(block.get("source_file") or block.get("path") or block.get("filename") or "")
    path = path.replace("\\", "/")
    if kind in {"test", "i18n", "pot"}:
        return False
    if (
        path.startswith(("tests/", "i18n/"))
        or "/tests/" in path
        or "/i18n/" in path
        or path.endswith(".pot")
    ):
        return False
    if block.get("option_a"):
        return True
    if kind in {"owl", "js", "qweb", "controller", "python", "xml"}:
        return True
    return False


def done_bar_for_draft(draft: dict[str, Any], *, prompt: str = "") -> dict[str, Any]:
    """Prompt -> done-bar matrix (live / option_a / mixed / autopilot)."""
    ir = draft.get("_generation_engine") if isinstance(draft.get("_generation_engine"), dict) else {}
    if ir.get("capability") == "stock_reuse":
        return {
            "mode": "autopilot",
            "live": "n/a",
            "option_a": "n/a",
            "gaps": [],
            "sandbox_smoke_ok": False,
            "go_live_ready": False,
            "next_step": (
                "Job Autopilot RPC smoke on sandbox (quote→confirm→invoice). "
                "Completeness ≠ Certification. Promote stays human."
            ),
        }
    assessment = assess_capability_gaps(prompt or str(draft.get("_user_prompt") or ""))
    if "_capability_primary_option_a" in draft:
        primary = bool(draft.get("_capability_primary_option_a"))
    else:
        primary = bool(assessment.primary_option_a)
    gaps = [g.id for g in assessment.gaps] or [
        str(g.get("id"))
        for g in (draft.get("_capability_gaps") or [])
        if isinstance(g, dict) and g.get("id")
    ]
    smoke = draft.get("_option_a_smoke") if isinstance(draft.get("_option_a_smoke"), dict) else {}
    smoke_ok = bool(smoke.get("ok"))

    if primary:
        mode = "option_a"
        live_ok = "stubs_only"
        option_a_ok = "sandbox_smoke" if smoke_ok else "scaffold_pending_smoke"
        next_step = (
            "Human promote after sandbox smoke"
            if smoke_ok
            else "Sandbox install & smoke (Pay now + QR on PDF)"
        )
    elif gaps:
        mode = "mixed"
        live_ok = "metadata_apply"
        option_a_ok = "sandbox_smoke" if smoke_ok else "scaffold_pending_smoke"
        next_step = "Apply live fields, then sandbox Option A surfaces"
    else:
        mode = "live"
        live_ok = "metadata_apply"
        option_a_ok = "n/a"
        next_step = "Apply to Odoo — verify fields_get / form arch"

    return {
        "mode": mode,
        "live": live_ok,
        "option_a": option_a_ok,
        "gaps": gaps,
        "sandbox_smoke_ok": smoke_ok,
        "go_live_ready": bool(smoke_ok and primary),
        "next_step": next_step,
    }


def apply_option_a_grain_label(draft: dict[str, Any]) -> None:
    """Override misleading Field pack when the ask is Option A-primary."""
    if not draft.get("_capability_primary_option_a"):
        return
    host = "host"
    for model in draft.get("models") or []:
        if isinstance(model, dict) and str(model.get("mode")) == "inherit":
            host = str(model.get("model") or host)
            break
    cp = draft.get("connect_points") if isinstance(draft.get("connect_points"), dict) else {}
    host_label = str(cp.get("host_label") or host)
    draft["grain_label"] = f"Option A document extras for {host_label}"
    draft["_grain_display_kind"] = "option_a_document"


def dedupe_option_a_items(items: list[str]) -> list[str]:
    """One line per path; prefer scaffold reason over gap prose duplicates."""
    by_path: dict[str, str] = {}
    order: list[str] = []
    pathless: list[str] = []
    for raw in items:
        line = str(raw or "").strip()
        if not line:
            continue
        path = line.split(" — ", 1)[0].strip() if " — " in line else ""
        if not path or "/" not in path:
            if line not in pathless:
                pathless.append(line)
            continue
        if path not in by_path:
            by_path[path] = line
            order.append(path)
            continue
        pref = ("QWeb inherit", "Pay now", "Fill x_payment", "portal URL", "skeleton")
        cur = by_path[path]
        if any(p in line for p in pref) and not any(p in cur for p in pref):
            by_path[path] = line
    return [by_path[p] for p in order] + pathless


def apply_option_a_score_cap(scorecard: dict[str, Any], draft: dict[str, Any]) -> None:
    """Cap completeness when Option A is primary and sandbox smoke has not passed."""
    if not draft.get("_capability_primary_option_a"):
        return
    smoke = draft.get("_option_a_smoke") if isinstance(draft.get("_option_a_smoke"), dict) else {}
    if smoke.get("ok"):
        findings = [
            f
            for f in (scorecard.get("findings") or [])
            if not (
                isinstance(f, dict)
                and f.get("element") in {"option_a_unproven", "option_a_structural"}
            )
        ]
        scorecard["findings"] = findings
        return

    findings = list(scorecard.get("findings") or [])
    if not any(
        isinstance(f, dict) and f.get("element") == "option_a_unproven" for f in findings
    ):
        findings.append(
            {
                "dimension": "hygiene",
                "element": "option_a_unproven",
                "detail": (
                    "Option A primary: score capped until sandbox install & surface smoke "
                    "(PDF Pay now / QR). Spec completeness != go-live."
                ),
            }
        )
    scorecard["findings"] = findings
    score = float(scorecard.get("score_0_10") or 0)
    scorecard["score_0_10"] = round(min(score, OPTION_A_SCORE_CAP), 2)
    dims = scorecard.get("dimensions")
    if isinstance(dims, dict) and "hygiene" in dims:
        dims["hygiene"] = round(min(float(dims["hygiene"]), OPTION_A_SCORE_CAP), 2)


def stamp_done_bar(draft: dict[str, Any], *, prompt: str = "") -> dict[str, Any]:
    bar = done_bar_for_draft(draft, prompt=prompt)
    draft["_done_bar"] = bar
    draft["_go_live_ready"] = bool(bar.get("go_live_ready"))
    apply_option_a_grain_label(draft)
    return bar


def structural_option_a_smoke(draft: dict[str, Any]) -> dict[str, Any]:
    """Content-level checks (no Docker) — not enough for 10.0."""
    checks: list[dict[str, Any]] = []
    ok = True
    blocks = [
        b
        for b in (draft.get("custom_code_blocks") or [])
        if isinstance(b, dict) and b.get("option_a")
    ]
    if not blocks and draft.get("_capability_gaps"):
        ok = False
        checks.append(
            {
                "id": "scaffold_present",
                "ok": False,
                "detail": "capability gaps stamped but no custom_code_blocks",
            }
        )
    for b in blocks:
        path = str(b.get("source_file") or b.get("path") or "")
        content = str(b.get("content") or "")
        has = bool(content.strip())
        if not has:
            ok = False
        checks.append(
            {
                "id": f"content:{path}",
                "ok": has,
                "detail": "has content" if has else "empty scaffold",
            }
        )
        if path.endswith("_document_extras.xml"):
            need = ("inherit_id=", "Pay now", "QR")
            missing = [n for n in need if n not in content]
            passed = not missing
            if not passed:
                ok = False
            checks.append(
                {
                    "id": "qweb_pay_qr",
                    "ok": passed,
                    "detail": "ok" if passed else f"missing {missing}",
                }
            )
        if path.endswith("_document_extras.py"):
            need = ("_sync_pay_qr_stubs", "_document_payment_url")
            missing = [n for n in need if n not in content]
            passed = not missing
            if not passed:
                ok = False
            checks.append(
                {
                    "id": "pay_url_sync",
                    "ok": passed,
                    "detail": "ok" if passed else f"missing {missing}",
                }
            )
    return {
        "ok": False,
        "structural_ok": ok,
        "level": "structural",
        "checks": checks,
    }


def rpc_option_a_smoke(
    draft: dict[str, Any],
    *,
    execute_kw: Callable[..., Any],
) -> dict[str, Any]:
    """Post-install RPC checks on ephemeral sandbox."""
    checks: list[dict[str, Any]] = []
    ok = True
    gap_ids = {
        str(g.get("id"))
        for g in (draft.get("_capability_gaps") or [])
        if isinstance(g, dict) and g.get("id")
    }

    if gap_ids & {"pdf_report", "qr_on_document", "click_to_pay"}:
        views = execute_kw(
            "ir.ui.view",
            "search_read",
            [[("key", "ilike", "document_extras")]],
            {"fields": ["id", "name", "key", "arch_db"], "limit": 5},
        )
        if not views:
            views = execute_kw(
                "ir.ui.view",
                "search_read",
                [[("name", "ilike", "document_extras")]],
                {"fields": ["id", "name", "arch_db"], "limit": 5},
            )
        arch = ""
        if views:
            arch = str(views[0].get("arch_db") or views[0].get("arch") or "")
        has_pay = "Pay now" in arch or "x_payment_url" in arch
        has_qr = "QR" in arch or "x_qr_payload" in arch or "barcode" in arch
        passed = bool(views) and has_pay and has_qr
        if not passed:
            ok = False
        checks.append(
            {
                "id": "ir_ui_view_document_extras",
                "ok": passed,
                "detail": f"views={len(views or [])} pay={has_pay} qr={has_qr}",
            }
        )

        host = "account.move"
        for m in draft.get("models") or []:
            if isinstance(m, dict) and str(m.get("mode")) == "inherit":
                host = str(m.get("model") or host)
                break
        try:
            fields_get = execute_kw(host, "fields_get", [], {"attributes": ["string"]})
        except Exception as exc:  # noqa: BLE001
            fields_get = {}
            checks.append({"id": "fields_get", "ok": False, "detail": str(exc)[:200]})
        else:
            for fname in ("x_payment_url", "x_qr_payload"):
                present = fname in (fields_get or {})
                checks.append(
                    {
                        "id": f"field:{fname}",
                        "ok": present,
                        "detail": "present" if present else "absent (ok if Applied separately)",
                    }
                )

    if "website_controller" in gap_ids:
        checks.append(
            {
                "id": "website_controller_module",
                "ok": True,
                "detail": "module installed; bind route before go-live",
            }
        )
    if "owl_widget" in gap_ids:
        checks.append(
            {
                "id": "owl_assets",
                "ok": True,
                "detail": "module installed; OWL assets ship with zip",
            }
        )
    if "python_logic" in gap_ids and not (
        gap_ids & {"pdf_report", "qr_on_document", "click_to_pay"}
    ):
        checks.append(
            {
                "id": "python_logic_module",
                "ok": True,
                "detail": "module installed with logic skeleton",
            }
        )

    # Runtime OWL guard: every authored arch field must exist in fields_get.
    try:
        from app.ai_option_a_view_fields import (
            arch_fields_missing_from_registry,
            collect_draft_arch_fields,
            collect_draft_python_fields,
        )

        py_by_model = collect_draft_python_fields(draft)
        arch_rows = collect_draft_arch_fields(draft)
        hosts = sorted(
            {
                *(py_by_model.keys()),
                *(h for _p, h, _f in arch_rows if h),
            }
        )
        for host in hosts:
            if not host or host.startswith("x_"):
                continue
            try:
                fields_get = execute_kw(host, "fields_get", [], {"attributes": ["string"]})
            except Exception as exc:  # noqa: BLE001
                ok = False
                checks.append(
                    {
                        "id": f"fields_get:{host}",
                        "ok": False,
                        "detail": str(exc)[:200],
                    }
                )
                continue
            fg = fields_get or {}
            for fname in sorted(py_by_model.get(host) or []):
                present = fname in fg
                if not present:
                    ok = False
                checks.append(
                    {
                        "id": f"registry_field:{host}.{fname}",
                        "ok": present,
                        "detail": "present" if present else "absent after install",
                    }
                )
            # Module inherit views on this host — catch orphan arch names.
            views = execute_kw(
                "ir.ui.view",
                "search_read",
                [[("model", "=", host), ("mode", "=", "extension")]],
                {"fields": ["id", "name", "arch_db"], "limit": 40},
            ) or []
            missing_all: list[str] = []
            for view in views:
                arch = str(view.get("arch_db") or view.get("arch") or "")
                if not arch:
                    continue
                # Only views that look like ours (x_* or known inserted names).
                ours = any(
                    f"name=\"{f}\"" in arch or f"name='{f}'" in arch
                    for f in (py_by_model.get(host) or set())
                ) or any(
                    f"name=\"{fname}\"" in arch or f"name='{fname}'" in arch
                    for _p, hint, fname in arch_rows
                    if hint == host or hint is None
                )
                if not ours and "x_" not in arch:
                    continue
                missing = arch_fields_missing_from_registry(arch, fg, model=host)
                missing_all.extend(missing)
            missing_all = sorted(set(missing_all))
            passed = not missing_all
            if not passed:
                ok = False
            checks.append(
                {
                    "id": f"view_fields_registry:{host}",
                    "ok": passed,
                    "detail": (
                        "ok"
                        if passed
                        else f"undefined in fields_get (OWL crash): {', '.join(missing_all)}"
                    ),
                }
            )
    except Exception as exc:  # noqa: BLE001
        ok = False
        checks.append(
            {
                "id": "view_fields_registry",
                "ok": False,
                "detail": str(exc)[:240],
            }
        )

    # Acceptance contracts — labels, placement, behavioral price effect.
    accept_msg = ""
    try:
        from app.ai_option_a_acceptance import run_acceptance_smoke, stamp_option_a_acceptance

        if not isinstance(draft.get("_option_a_acceptance"), dict):
            stamp_option_a_acceptance(
                draft, prompt=str(draft.get("_user_prompt") or "")
            )
        acceptance = run_acceptance_smoke(draft, execute_kw=execute_kw)
        for row in acceptance.get("checks") or []:
            if isinstance(row, dict):
                checks.append(row)
        if not acceptance.get("ok"):
            ok = False
            accept_msg = str(acceptance.get("message") or "")
    except Exception as exc:  # noqa: BLE001
        ok = False
        accept_msg = f"Acceptance smoke error: {str(exc)[:240]}"
        checks.append(
            {
                "id": "acceptance",
                "ok": False,
                "detail": str(exc)[:240],
            }
        )

    message = accept_msg
    if not ok and not message:
        failed = [c for c in checks if isinstance(c, dict) and not c.get("ok")]
        message = "; ".join(
            f"{c.get('id')}: {c.get('detail')}" for c in failed[:6]
        ) or "option A smoke failed"

    accept_ids = {
        "field_labeled",
        "xpath_anchor",
        "price_effect",
        "fields_present",
        "form_loads",
    }
    accept_rows = [
        c for c in checks if isinstance(c, dict) and c.get("id") in accept_ids
    ]
    acceptance_ok = (not accept_rows) or all(c.get("ok") for c in accept_rows)

    return {
        "ok": ok,
        "structural_ok": True,
        "level": "sandbox_rpc",
        "checks": checks,
        "message": message if not ok else "",
        "acceptance_ok": acceptance_ok,
    }


def stamp_option_a_smoke(draft: dict[str, Any], smoke: dict[str, Any]) -> None:
    draft["_option_a_smoke"] = smoke
    stamp_done_bar(draft, prompt=str(draft.get("_user_prompt") or ""))
    from app.ai_draft_scorecard import attach_scorecard

    attach_scorecard(draft, user_prompt=str(draft.get("_user_prompt") or ""))


def prove_option_a_in_sandbox(
    draft: dict[str, Any],
    *,
    odoo_major: int | None = None,
    auto_repair: bool = True,
) -> dict[str, Any]:
    """Export zip -> ephemeral sandbox install -> RPC smoke -> restamp scorecard.

    On install fail for LLM-authored modules, feed the Odoo Fault back to the
    author once, then retry sandbox once when the authoring gate still passes.
    """
    from app.ai_generation_engine import is_gold_option_a_draft, is_option_a_authored_draft
    from app.module_spec_codec import export_draft_module_zip
    from app.sandbox import SANDBOX_DB, SANDBOX_PASSWORD, run_sandbox_install

    structural = structural_option_a_smoke(draft)
    if not structural.get("structural_ok"):
        smoke = {**structural, "ok": False, "message": "Structural scaffold checks failed"}
        stamp_option_a_smoke(draft, smoke)
        return {"ok": False, "draft": draft, "smoke": smoke}

    tech = str(draft.get("technical_name") or "ext_option_a")
    from app.ai_failure_ir import (
        failures_from_sandbox_log,
        failures_from_smoke,
        stamp_failures,
    )
    from app.ai_repair_loop import begin_repair_attempt, lock_certified_artifacts, repair_guidance

    feedback_repair: dict[str, Any] | None = None
    attempted_repair = False
    zip_bytes = b""
    result: Any = None
    smoke_holder: dict[str, Any] = {}

    def _after(uid: int, models: Any, major: int) -> None:
        def execute_kw(model: str, method: str, args: list, kwargs: dict | None = None):
            return models.execute_kw(
                SANDBOX_DB,
                uid,
                SANDBOX_PASSWORD,
                model,
                method,
                args,
                kwargs or {},
            )

        smoke_holder.update(rpc_option_a_smoke(draft, execute_kw=execute_kw))
        smoke_holder["odoo_major"] = major

    while True:
        smoke_holder.clear()
        zip_bytes = export_draft_module_zip(draft, odoo_major=odoo_major)
        result = run_sandbox_install(
            zip_bytes,
            module_name=tech,
            odoo_major=odoo_major,
            extra_modules=list(draft.get("depends") or []),
            after_install=_after,
        )
        if result.ok:
            break
        fails = failures_from_sandbox_log(
            result.log_tail or "", ok=False, message=result.message or ""
        )
        stamp_failures(draft, fails)
        draft["_sandbox_install"] = {
            "ok": False,
            "message": result.message,
            "job_id": getattr(result, "job_id", None),
        }
        should_repair = (
            auto_repair
            and not attempted_repair
            and is_option_a_authored_draft(draft)
            and not is_gold_option_a_draft(draft)
        )
        if should_repair:
            attempted_repair = True
            from app.ai_option_a_feedback import repair_option_a_from_feedback

            error_text = "\n".join(
                part for part in (result.message or "", result.log_tail or "") if part
            )
            feedback_repair = repair_option_a_from_feedback(
                draft,
                error_text=error_text,
                failures=fails,
                odoo_major=int(odoo_major or 19),
            )
            if feedback_repair.get("applied") and feedback_repair.get("gate_status") == "pass":
                continue
            repair_meta = feedback_repair.get("repair") or {
                "ok": False,
                "reason": str(feedback_repair.get("reason") or "repair_not_applied"),
                "bucket": "sandbox",
                "repair_count": int(draft.get("_sandbox_repair_count") or 0),
            }
        else:
            # Do NOT burn sandbox repair budget just to stamp metadata on a failed prove.
            repair_meta = {
                "ok": False,
                "reason": "prove_failed_no_auto_repair",
                "bucket": "sandbox",
                "repair_count": int(draft.get("_sandbox_repair_count") or 0),
            }
        smoke = {
            **structural,
            "ok": False,
            "level": "sandbox_install",
            "message": result.message,
            "log_tail": result.log_tail,
            "checks": structural.get("checks") or [],
        }
        stamp_option_a_smoke(draft, smoke)
        payload: dict[str, Any] = {
            "ok": False,
            "draft": draft,
            "smoke": smoke,
            "failures": draft.get("_failures"),
            "repair": repair_meta,
            "repair_hints": repair_guidance(fails),
            "certification": draft.get("_certification"),
            "sandbox": {
                "ok": False,
                "message": result.message,
                "log_tail": result.log_tail,
            },
            # Keep the Odoo Fault as the primary message — budget copy stays in feedback_repair.
            "message": result.message,
        }
        if feedback_repair:
            payload["feedback_repair"] = feedback_repair
            if (
                attempted_repair
                and feedback_repair.get("applied")
                and feedback_repair.get("gate_status") == "pass"
            ):
                payload["message"] = (
                    "AI patched the module from the sandbox error, then retry still failed. "
                    "Click Repair with AI (or Sandbox install & smoke again). Do not Install this app."
                )
            elif feedback_repair.get("reason") in {
                "max_repair_exceeded",
                "thrashing_detected",
            } or str(feedback_repair.get("reason") or "").startswith("locked"):
                budget = str(feedback_repair.get("message") or "")
                fault = str(result.message or "").strip()
                payload["message"] = (
                    f"{fault}\n\n{budget}".strip() if fault and budget else (fault or budget)
                )
            elif feedback_repair.get("message") and not result.message:
                payload["message"] = str(feedback_repair["message"])
        return payload

    # Install succeeded — evaluate acceptance smoke; auto-repair once on fail.
    smoke_attempt = 0
    while True:
        smoke = {
            **smoke_holder,
            "structural_ok": True,
            "message": result.message,
            "module": result.module,
            "log_tail": result.log_tail,
        }
        if "ok" not in smoke:
            smoke["ok"] = True
        draft["_sandbox_install"] = {
            "ok": True,
            "message": result.message,
            "module": result.module,
        }
        stamp_option_a_smoke(draft, smoke)
        if smoke.get("ok"):
            lock_certified_artifacts(draft, run_id=str(result.module or tech))
            break

        fails = failures_from_smoke(smoke)
        stamp_failures(draft, fails)
        should_repair_smoke = (
            auto_repair
            and not attempted_repair
            and is_option_a_authored_draft(draft)
            and not is_gold_option_a_draft(draft)
            and smoke_attempt == 0
        )
        smoke_attempt += 1
        if should_repair_smoke:
            attempted_repair = True
            from app.ai_option_a_feedback import repair_option_a_from_feedback

            error_text = "\n".join(
                part
                for part in (
                    str(smoke.get("message") or ""),
                    *(
                        f"{c.get('id')}: {c.get('detail')} — {c.get('repair_hint') or ''}"
                        for c in (smoke.get("checks") or [])
                        if isinstance(c, dict) and not c.get("ok")
                    ),
                )
                if part
            )
            feedback_repair = repair_option_a_from_feedback(
                draft,
                error_text=error_text,
                failures=fails,
                odoo_major=int(odoo_major or 19),
            )
            if feedback_repair.get("applied") and feedback_repair.get("gate_status") == "pass":
                smoke_holder.clear()
                zip_bytes = export_draft_module_zip(draft, odoo_major=odoo_major)
                result = run_sandbox_install(
                    zip_bytes,
                    module_name=tech,
                    odoo_major=odoo_major,
                    extra_modules=list(draft.get("depends") or []),
                    after_install=_after,
                )
                if not result.ok:
                    fails_i = failures_from_sandbox_log(
                        result.log_tail or "",
                        ok=False,
                        message=result.message or "",
                    )
                    stamp_failures(draft, fails_i)
                    smoke = {
                        **structural,
                        "ok": False,
                        "level": "sandbox_install",
                        "message": result.message,
                        "log_tail": result.log_tail,
                        "checks": structural.get("checks") or [],
                    }
                    stamp_option_a_smoke(draft, smoke)
                    return {
                        "ok": False,
                        "draft": draft,
                        "smoke": smoke,
                        "failures": draft.get("_failures"),
                        "repair": feedback_repair.get("repair"),
                        "feedback_repair": feedback_repair,
                        "certification": draft.get("_certification"),
                        "sandbox": {
                            "ok": False,
                            "message": result.message,
                            "log_tail": result.log_tail,
                        },
                        "message": (
                            "Acceptance repair applied, but re-install failed: "
                            f"{result.message}"
                        ),
                    }
                continue
            repair_meta = feedback_repair.get("repair") or {
                "ok": False,
                "reason": str(feedback_repair.get("reason") or "repair_not_applied"),
                "bucket": "sandbox",
                "repair_count": int(draft.get("_sandbox_repair_count") or 0),
            }
        else:
            repair_meta = {
                "ok": False,
                "reason": "smoke_failed",
                "bucket": "sandbox",
                "repair_count": int(draft.get("_sandbox_repair_count") or 0),
            }
        out_fail: dict[str, Any] = {
            "ok": False,
            "draft": draft,
            "smoke": smoke,
            "failures": draft.get("_failures"),
            "repair": repair_meta,
            "repair_hints": repair_guidance(fails),
            "certification": draft.get("_certification"),
            "sandbox": {
                "ok": True,
                "module": result.module,
                "message": result.message,
                "log_tail": result.log_tail,
            },
            "score_0_10": (draft.get("_scorecard") or {}).get("score_0_10"),
            "go_live_ready": draft.get("_go_live_ready"),
            "message": str(smoke.get("message") or "Acceptance / Option A smoke failed"),
        }
        if feedback_repair:
            out_fail["feedback_repair"] = feedback_repair
        return out_fail

    payload = {
        "ok": bool(smoke.get("ok")),
        "draft": draft,
        "smoke": smoke,
        "failures": draft.get("_failures") or [],
        "certification": draft.get("_certification"),
        "certified_artifacts": draft.get("_certified_artifacts"),
        "sandbox": {
            "ok": True,
            "module": result.module,
            "message": result.message,
            "log_tail": result.log_tail,
        },
        "score_0_10": (draft.get("_scorecard") or {}).get("score_0_10"),
        "go_live_ready": draft.get("_go_live_ready"),
    }
    if feedback_repair and feedback_repair.get("applied"):
        payload["feedback_repair"] = feedback_repair
        payload["message"] = (
            "Sandbox proved after AI repaired the previous error. "
            "Promote stays human. Do not click Install this app."
        )
    if payload["ok"]:
        payload["zip_bytes"] = zip_bytes
    return payload


__all__ = [
    "OPTION_A_SCORE_CAP",
    "apply_option_a_grain_label",
    "apply_option_a_score_cap",
    "dedupe_option_a_items",
    "done_bar_for_draft",
    "is_option_a_runtime_block",
    "prove_option_a_in_sandbox",
    "rpc_option_a_smoke",
    "stamp_done_bar",
    "stamp_option_a_smoke",
    "structural_option_a_smoke",
]
