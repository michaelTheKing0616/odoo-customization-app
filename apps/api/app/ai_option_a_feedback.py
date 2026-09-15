"""Feed sandbox / operator errors back to the Option A author LLM.

Constrained patches only (implicated custom_code_blocks). Never invent account.tax.
Never live ir.actions.server state=code. Gold templates are locked.
"""

from __future__ import annotations

from typing import Any, Callable

from app.ai_failure_ir import failures_from_sandbox_log, stamp_failures
from app.ai_generation_engine import is_gold_option_a_draft, is_option_a_authored_draft
from app.ai_option_a_author import FORMAT_SCHEMA_BLOCKS, coerce_author_payload
from app.ai_option_a_gate import evaluate_authoring_gate
from app.ai_repair_loop import (
    apply_constrained_block_patch,
    begin_repair_attempt,
    budget_exhausted_message,
    implicated_files,
)
from app.ai_static_odoo import rewrite_draft_stock_xpaths

GenerateBlocks = Callable[[str, dict[str, Any]], list[dict[str, Any]]]

_REPAIR_SYSTEM = (
    "You repair an already-authored Odoo Community 17–19 module. "
    "Return ONLY JSON {blocks: [{source_file, kind, content}]}. "
    "Patch ONLY the files listed in the prompt. Do not add new files or models. "
    "Never create account.tax. Never env['account.tax'].create. "
    "Never ir.actions.server state=code. Never os/subprocess or private HTTP. "
    "Community 17–19 sale.order form inherit MUST xpath //field[@name='tax_totals'] "
    "(sale.view_order_form has no amount_tax / amount_untaxed node). "
    "sale.order.line taxes field is tax_ids (Many2many) — never tax_id. "
    "Prefer the smallest fix that matches the Odoo Fault. "
    "Escape newlines as \\n and quotes as \\\"."
)

_MAX_FILE_CHARS = 8000
_MAX_ERROR_CHARS = 3500


def _block_path(block: dict[str, Any]) -> str:
    return str(block.get("source_file") or block.get("path") or "").strip()


def _paths_match(left: str, right: str) -> bool:
    a = left.replace("\\", "/").lstrip("/")
    b = right.replace("\\", "/").lstrip("/")
    if not a or not b:
        return False
    if a == b:
        return True
    return a.endswith(b) or b.endswith(a) or a.split("/")[-1] == b.split("/")[-1]


def _existing_block_path(draft: dict[str, Any], requested: str) -> str | None:
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = _block_path(block)
        if path and _paths_match(path, requested):
            return path
    return None


def _candidate_files(draft: dict[str, Any], failures: list[dict[str, Any]]) -> list[str]:
    named = implicated_files(failures)
    matched: list[str] = []
    for name in named:
        path = _existing_block_path(draft, name)
        if path and path not in matched:
            matched.append(path)
    if matched:
        return matched[:2]
    xml_fail = any(
        isinstance(f, dict) and f.get("category") == "xml" for f in failures
    )
    kinds = {"xml", "qweb"} if xml_fail else {"python", "xml", "qweb"}
    out: list[str] = []
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        path = _block_path(block)
        kind = str(block.get("kind") or "")
        if not path:
            continue
        if xml_fail and not (path.endswith(".xml") or kind in {"xml", "qweb"}):
            continue
        if not xml_fail and kind not in kinds and not path.endswith((".py", ".xml")):
            continue
        if path not in out:
            out.append(path)
        if len(out) >= 2:
            break
    return out


def _file_excerpt(draft: dict[str, Any], path: str) -> str:
    for block in draft.get("custom_code_blocks") or []:
        if not isinstance(block, dict):
            continue
        if _block_path(block) != path:
            continue
        content = str(block.get("content") or "")
        if len(content) > _MAX_FILE_CHARS:
            return content[:_MAX_FILE_CHARS] + "\n… [truncated]"
        return content
    return ""


def _repair_user_prompt(
    draft: dict[str, Any],
    *,
    error_text: str,
    failures: list[dict[str, Any]],
    files: list[str],
    operator_notes: str,
) -> str:
    brief = str(draft.get("_user_prompt") or "")[:1200]
    lines = [
        "Operator brief:",
        brief or "(none)",
        "",
        "Odoo sandbox / install Fault (fix this — do not invent a new app):",
        (error_text or "")[:_MAX_ERROR_CHARS],
        "",
        "Failure IR:",
    ]
    for f in failures[:6]:
        if not isinstance(f, dict):
            continue
        xpath = f.get("xpath") or ""
        xmlid = f.get("xmlid") or ""
        hint = f.get("repair_hint") or ""
        lines.append(
            f"- {f.get('category')} {f.get('file') or ''}: {str(f.get('message') or '')[:400]}"
            + (f" xpath={xpath}" if xpath else "")
            + (f" xmlid={xmlid}" if xmlid else "")
            + (f" hint={hint}" if hint else "")
        )
    if operator_notes.strip():
        lines.extend(["", "Operator notes:", operator_notes.strip()[:1500]])
    lines.append("")
    lines.append("Patch only these files (return full replacement content for each):")
    for path in files:
        lines.append(f"\n===== {path} =====\n{_file_excerpt(draft, path)}")
    return "\n".join(lines)


def _default_repair_blocks(prompt: str, draft: dict[str, Any]) -> list[dict[str, Any]]:
    from app.llm_provider import generate_json_with_timeout_retry, get_llm_provider_for_tier

    provider = get_llm_provider_for_tier("fast")
    if provider is None:
        return []

    def _call(text: str) -> str:
        return generate_json_with_timeout_retry(
            provider,
            text,
            system=_REPAIR_SYSTEM,
            timeout_s=120.0,
            format_schema=FORMAT_SCHEMA_BLOCKS,
            log_step="option_a_feedback_repair",
        )

    try:
        raw = _call(prompt)
        data = coerce_author_payload(raw) if isinstance(raw, (dict, list)) else None
        if data is None:
            from app.llm_json import parse_llm_json

            data = coerce_author_payload(parse_llm_json(raw))
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(data, dict):
        return []
    blocks = data.get("blocks") if isinstance(data.get("blocks"), list) else []
    out: list[dict[str, Any]] = []
    for row in blocks:
        if not isinstance(row, dict):
            continue
        path = str(row.get("source_file") or row.get("path") or "").strip()
        content = str(row.get("content") or "")
        if path and content.strip():
            out.append({"source_file": path, "content": content, "kind": row.get("kind")})
    return out


def _stamp_feedback(
    draft: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    draft["_option_a_feedback_repair"] = payload
    return payload


def repair_option_a_from_feedback(
    draft: dict[str, Any],
    *,
    error_text: str = "",
    failures: list[dict[str, Any]] | None = None,
    operator_notes: str = "",
    generate_blocks: GenerateBlocks | None = None,
    odoo_major: int = 19,
) -> dict[str, Any]:
    """Patch authored files from a sandbox Fault or operator note. Mutates draft."""
    if is_gold_option_a_draft(draft):
        return _stamp_feedback(
            draft,
            {
                "ok": False,
                "applied": False,
                "reason": "gold_locked",
                "message": (
                    "Gold Option A templates are not LLM-patched. "
                    "Retry sandbox after restart, or re-export the zip. Do not Install this app."
                ),
            },
        )
    if not is_option_a_authored_draft(draft):
        return _stamp_feedback(
            draft,
            {
                "ok": False,
                "applied": False,
                "reason": "not_authored",
                "message": "Feedback repair applies to LLM-authored Option A modules only.",
            },
        )

    text = (error_text or "").strip()
    if not text:
        sandbox = draft.get("_sandbox_install") if isinstance(draft.get("_sandbox_install"), dict) else {}
        smoke = draft.get("_option_a_smoke") if isinstance(draft.get("_option_a_smoke"), dict) else {}
        text = str(sandbox.get("message") or smoke.get("message") or smoke.get("log_tail") or "")
    notes = (operator_notes or "").strip()
    if not text and not notes:
        return _stamp_feedback(
            draft,
            {
                "ok": False,
                "applied": False,
                "reason": "no_feedback",
                "message": "No sandbox Fault or operator notes to repair from.",
            },
        )

    fails = [f for f in (failures or []) if isinstance(f, dict)]
    if not fails and text:
        fails = failures_from_sandbox_log(text, ok=False, message=text)
    stamp_failures(draft, fails)

    # Deterministic stock xpath rewrite is free — does not consume sandbox repair budget.
    xpath_changed = rewrite_draft_stock_xpaths(draft)
    files = _candidate_files(draft, fails)
    needs_llm = bool(files) and (xpath_changed == 0 or bool(notes) or generate_blocks is not None)

    begin: dict[str, Any] = {
        "ok": True,
        "repair_count": int(draft.get("_sandbox_repair_count") or 0),
        "bucket": "sandbox",
    }
    if needs_llm:
        begin = begin_repair_attempt(draft, fails, bucket="sandbox")
        if not begin.get("ok"):
            return _stamp_feedback(
                draft,
                {
                    "ok": False,
                    "applied": bool(xpath_changed),
                    "reason": str(begin.get("reason") or "repair_blocked"),
                    "repair": begin,
                    "deterministic": bool(xpath_changed),
                    "message": budget_exhausted_message(str(begin.get("reason") or "")),
                },
            )

    llm_files: list[str] = []
    gen = generate_blocks if generate_blocks is not None else _default_repair_blocks

    if needs_llm and begin.get("ok"):
        prompt = _repair_user_prompt(
            draft,
            error_text=text or notes,
            failures=fails,
            files=files,
            operator_notes=notes,
        )
        try:
            patches = gen(prompt, draft) or []
        except Exception as exc:  # noqa: BLE001
            patches = []
            draft["_option_a_feedback_repair_error"] = str(exc)[:400]
        for row in patches[:2]:
            if not isinstance(row, dict):
                continue
            requested = str(row.get("source_file") or row.get("path") or "").strip()
            content = str(row.get("content") or "")
            path = _existing_block_path(draft, requested) if requested else None
            if not path or not content.strip():
                continue
            if path not in files and files:
                continue
            applied = apply_constrained_block_patch(draft, source_file=path, new_content=content)
            if applied.get("ok"):
                llm_files.append(path)
        if llm_files:
            rewrite_draft_stock_xpaths(draft)

    gate = evaluate_authoring_gate(draft, odoo_major=odoo_major)
    applied = bool(xpath_changed or llm_files)
    gate_status = str(gate.get("status") or "")
    if applied and gate_status == "pass":
        message = (
            "AI patched the module from the sandbox error. "
            "Retry Sandbox install & smoke. Do not click Install this app. Promote stays human."
        )
    elif applied:
        message = (
            "A patch was applied but the authoring gate failed — zip stays locked. "
            "Click Repair with AI again or Retry authoring. Do not Install this app."
        )
    elif xpath_changed == 0 and not llm_files:
        message = (
            "The model did not return a patch. Add a short note and click Repair with AI, "
            "or retry sandbox after restarting :8001. Do not Install this app."
        )
    else:
        message = "No files changed."

    return _stamp_feedback(
        draft,
        {
            "ok": applied and gate_status == "pass",
            "applied": applied,
            "files": llm_files,
            "deterministic": bool(xpath_changed),
            "llm": bool(llm_files),
            "gate_status": gate_status,
            "gate_findings": gate.get("findings") or [],
            "allowed_files": files,
            "repair": begin,
            "reason": "applied" if applied else "no_patch",
            "message": message,
            "error_excerpt": (text or notes)[:500],
        },
    )


__all__ = ["repair_option_a_from_feedback"]
