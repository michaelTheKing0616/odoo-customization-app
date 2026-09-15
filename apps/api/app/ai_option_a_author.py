"""LLM-authored Option A modules — gold is a shortcut, this is the general path."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from app.ai_option_a_gate import evaluate_authoring_gate
from app.ai_repair_loop import begin_repair_attempt

GenerateBlocks = Callable[[str, dict[str, Any]], list[dict[str, Any]]]

_AUTHOR_SYSTEM = (
    "You author an installable Odoo Community 17–19 module as JSON. "
    "Return ONLY JSON with key blocks: an object {blocks: [{source_file, kind, content, reason}, ...]}. "
    "Never return a bare JSON array. "
    "kind is python, xml, or qweb. Include models/__init__.py when you add models/*.py. "
    "Prefer _inherit of stock models. New x_* models are allowed for a true residual document. "
    "Never create account.tax. Never put API keys or passwords in code. "
    "Never use os, subprocess, or private/link-local HTTP URLs. "
    "urllib is allowed for public HTTPS APIs. Live ir.actions.server state=code is forbidden. "
    "QWeb report changes must inherit a stock xmlid (inherit_id). "
    "Do not invent a parallel invoice, partner, or employee model. "
    "Sales markup briefs: inherit sale.order; operator chooses markup % at sale entry "
    "(selection 10 through 25); selling price = cost + markup; withholding tax applies "
    "only to the markup amount and only on sales, never purchases. Use an existing tax "
    "xmlid — never env['account.tax'].create. "
    "sale.order form inherit MUST xpath //field[@name='tax_totals'] "
    "(Community 17–19 has no amount_tax node on sale.view_order_form). "
    "sale.order.line taxes field is tax_ids (Many2many) — never tax_id. "
    "Do not re-declare stock _compute_amount / price_subtotal with wrong @depends; "
    "add x_* markup fields and compute on those instead. "
    "JSON rules: escape every newline as \\n and every double-quote as \\\". "
    "Close every string. Prefer at most 6 short files."
)

FORMAT_SCHEMA_BLOCKS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "technical_name": {"type": "string"},
        "display_name": {"type": "string"},
        "depends": {"type": "array", "items": {"type": "string"}},
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_file": {"type": "string"},
                    "kind": {"type": "string"},
                    "content": {"type": "string"},
                    "reason": {"type": "string"},
                    "model": {"type": "string"},
                },
                "required": ["source_file", "content"],
            },
        },
    },
    "required": ["blocks"],
}


def _slug_prompt(prompt: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (prompt or "").lower()).strip("_")
    return (slug[:48] or "custom_logic").strip("_")


def _authored_display_name(prompt: str, host: str | None) -> str:
    from app.ai_grain import HOST_LABELS

    label = HOST_LABELS.get(host or "", "")
    text = prompt or ""
    if re.search(r"(?i)mark-?up", text):
        return f"{label or 'Sales'} markup"[:80]
    if re.search(r"(?i)delivery\s+(?:note|slip)|shipping\s+address", text):
        return "Delivery slip layout"
    if re.search(r"(?i)withh?olding|\bwht\b", text):
        return f"{label or 'Sales'} withholding"[:80]
    first = re.split(r"[.!\n]", text.strip())[0].strip()
    if not first or len(first) > 48 or first.lower().startswith("the client"):
        return f"{label or 'Custom'} module"[:80]
    return first[:80]


def _authored_preview_fields(prompt: str, host: str | None) -> list[dict[str, Any]]:
    text = prompt or ""
    if host == "sale.order" and re.search(r"(?i)mark-?up", text):
        return [
            {
                "name": "x_markup_percent",
                "ttype": "selection",
                "string": "Markup %",
                "required": True,
                "selection": [[str(i), f"{i}%"] for i in range(10, 26)],
                "help": (
                    "Percent for this sale. WHT applies to the markup amount only — "
                    "use an existing tax xmlid, never create account.tax."
                ),
            }
        ]
    return []


def seed_option_a_authored(prompt: str, plan: Any) -> dict[str, Any]:
    from app.ai_generation_engine import attach_generation_engine, plan_to_ir
    from app.ai_grain import module_for_model, preferred_inherit_host
    from app.ai_llm_status import attach_llm_status
    from app.ai_operator_brief import attach_operator_brief

    slug = _slug_prompt(prompt)
    host = preferred_inherit_host(prompt)
    fields = _authored_preview_fields(prompt, host)
    models: list[dict[str, Any]] = []
    depends = ["base"]
    if host:
        depends = [module_for_model(host)]
        models = [{"model": host, "mode": "inherit", "fields": fields}]
    draft: dict[str, Any] = {
        "technical_name": f"custom_{slug}"[:64],
        "display_name": _authored_display_name(prompt, host),
        "depends": depends,
        "models": models,
        "views": [],
        "menus": [],
        "custom_code_blocks": [],
        "grain": "full_app",
        "grain_label": "Option A — LLM module (gated)",
        "_user_prompt": prompt,
        "_pipeline": "option_a_authored",
        "_capability_primary_option_a": True,
        "_delivery_preference": "module_zip",
    }
    attach_operator_brief(draft, user_prompt=prompt)
    attach_llm_status(draft, mode="pack_fallback", reason="option_a_authored")
    attach_generation_engine(draft, prompt, user_phase="codegen")
    ir = draft.get("_generation_engine")
    if isinstance(ir, dict) and plan is not None:
        for key, val in plan_to_ir(plan, user_phase="codegen").items():
            ir[key] = val
        ir["capability"] = "option_a_authored"
        ir["module_delivery"] = True
        ir["gold_artifact_id"] = None
    draft["_option_a_authoring"] = {
        "status": "pending",
        "findings": [
            {
                "code": "not_evaluated",
                "message": "Authoring has not passed the gate yet.",
            }
        ],
        "disclosure": {},
        "http_hosts": [],
    }
    return draft


def _normalize_blocks(raw: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        path = str(row.get("source_file") or row.get("path") or "").strip()
        content = str(row.get("content") or row.get("source") or "")
        if not path or not content.strip():
            continue
        kind = str(row.get("kind") or "")
        if not kind:
            if path.endswith(".xml"):
                kind = "xml"
            elif path.endswith((".js", ".xml")) and "static/" in path.replace("\\", "/"):
                kind = "js" if path.endswith(".js") else "xml"
            else:
                kind = "python"
        if kind in {"xml", "qweb"} or path.endswith(".xml"):
            from app.ai_static_odoo import rewrite_stock_inherit_xpaths

            content = rewrite_stock_inherit_xpaths(content)
        block = {
            "source_file": path,
            "path": path,
            "kind": kind,
            "content": content,
            "reason": str(row.get("reason") or "option_a_authored"),
            "source": "option_a_authored",
            "option_a": True,
        }
        if row.get("model"):
            block["model"] = str(row["model"])
        out.append(block)
    return out


_TRANSIENT_AUTHOR_CODES = frozenset({"author_failed", "empty_module", "llm_unavailable"})
_JSON_FAIL_MARKERS = (
    "unterminated string",
    "malformed json",
    "expecting value",
    "invalid control character",
    "jsondecodeerror",
    "author_json",
    "not an object",
    "modulespec draft",
)


def _author_json_error(exc: BaseException) -> bool:
    if isinstance(exc, json.JSONDecodeError):
        return True
    text = str(exc).lower()
    return any(marker in text for marker in _JSON_FAIL_MARKERS)


def _author_exc_retryable(exc: BaseException) -> bool:
    from app.llm_provider import LLMError, _is_rate_limit_error, _is_unavailable_error

    if str(exc) == "llm_unavailable":
        return True
    if _author_json_error(exc):
        return True
    if isinstance(exc, LLMError):
        return _is_unavailable_error(exc) or _is_rate_limit_error(exc)
    text = str(exc).lower()
    return "503" in text or "unavailable" in text or "high demand" in text or "429" in text


def _author_fail_message(exc: BaseException) -> str:
    detail = str(exc).strip() or type(exc).__name__
    if len(detail) > 280:
        detail = detail[:277] + "…"
    if _author_json_error(exc):
        return (
            "The model returned incomplete JSON. Automatic repair could not recover a "
            "module this pass. Click Retry authoring. "
            f"Detail: {detail}"
        )
    if _author_exc_retryable(exc):
        return (
            "The language model was busy (high demand or rate limit). "
            "Click Retry authoring — we wait and try another configured model. "
            f"Detail: {detail}"
        )
    return detail


def _stamp_retryable(payload: dict[str, Any]) -> dict[str, Any]:
    findings = [row for row in (payload.get("findings") or []) if isinstance(row, dict)]
    codes = {str(row.get("code") or "") for row in findings}
    payload["retryable"] = bool(codes) and codes <= _TRANSIENT_AUTHOR_CODES
    return payload


def coerce_author_payload(data: Any) -> dict[str, Any]:
    """Accept ``{blocks:[...]}``, ``{files:[...]}``, a single block, or a bare array."""
    if isinstance(data, list):
        return {"blocks": data}
    if not isinstance(data, dict):
        raise ValueError("author_json_not_object")
    if isinstance(data.get("blocks"), list):
        return data
    for key in ("files", "custom_code_blocks"):
        rows = data.get(key)
        if isinstance(rows, list) and rows:
            out = dict(data)
            out["blocks"] = rows
            return out
    if data.get("source_file") or data.get("path"):
        meta = {
            k: v
            for k, v in data.items()
            if k not in {"source_file", "path", "content", "kind", "reason", "model"}
        }
        return {**meta, "blocks": [data]}
    return data


def _parse_author_payload(raw: str | dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(raw, (dict, list)):
        return coerce_author_payload(raw)
    from app.llm_json import parse_llm_json

    return coerce_author_payload(parse_llm_json(raw))


def _author_user_prompt(prompt: str, draft: dict[str, Any]) -> str:
    hosts = [
        str(m.get("model"))
        for m in (draft.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    ]
    return (
        f"Operator brief:\n{prompt}\n\n"
        f"Draft technical_name: {draft.get('technical_name')}\n"
        f"Inherit hosts: {hosts or ['(none yet)']}\n"
        f"Depends so far: {draft.get('depends')}\n"
        "Author the module files. Inherit the named host when present."
    )


_COMPACT_JSON_HINT = (
    "\n\nYour last JSON was truncated, a bare array, or unescaped. "
    "Return one JSON object {\"blocks\":[...]} — never a bare array. "
    "Escape newlines as \\n and quotes as \\\". Close every string. "
    "At most 4 files, each under 80 lines."
)


def _default_generate_blocks(prompt: str, draft: dict[str, Any]) -> list[dict[str, Any]]:
    from app.llm_provider import generate_json_with_timeout_retry, get_llm_provider_for_tier

    provider = get_llm_provider_for_tier("fast")
    if provider is None:
        raise RuntimeError("llm_unavailable")
    user = _author_user_prompt(prompt, draft)

    def _call(text: str) -> str:
        return generate_json_with_timeout_retry(
            provider,
            text,
            system=_AUTHOR_SYSTEM,
            timeout_s=180.0,
            format_schema=FORMAT_SCHEMA_BLOCKS,
            log_step="option_a_author",
        )

    raw = _call(user)
    data: dict[str, Any] | None = None
    try:
        parsed = _parse_author_payload(raw)
        if isinstance(parsed, dict) and _normalize_blocks(list(parsed.get("blocks") or [])):
            data = parsed
    except (json.JSONDecodeError, ValueError):
        data = None
    if data is None:
        raw = _call(user + _COMPACT_JSON_HINT)
        data = _parse_author_payload(raw)
    if not isinstance(data, dict):
        raise RuntimeError("author_json_not_object")
    if data.get("technical_name"):
        draft["technical_name"] = str(data["technical_name"])[:64]
    if data.get("display_name"):
        draft["display_name"] = str(data["display_name"])[:120]
    if isinstance(data.get("depends"), list) and data["depends"]:
        draft["depends"] = [str(x) for x in data["depends"] if str(x).strip()]
    return _normalize_blocks(list(data.get("blocks") or []))


def _repair_generate(
    prompt: str,
    draft: dict[str, Any],
    findings: list[dict[str, Any]],
    generate_blocks: GenerateBlocks,
) -> None:
    repair_prompt = (
        f"{prompt}\n\nGate findings to fix (do not ignore):\n"
        + "\n".join(
            f"- {f.get('code')}: {f.get('message')} ({f.get('file')})"
            for f in findings
            if isinstance(f, dict)
        )
    )
    blocks = generate_blocks(repair_prompt, draft)
    if blocks:
        draft["custom_code_blocks"] = blocks


def author_option_a_module(
    draft: dict[str, Any],
    *,
    prompt: str | None = None,
    generate_blocks: GenerateBlocks | None = None,
    client: Any | None = None,
    odoo_major: int = 19,
) -> dict[str, Any]:
    """Fill custom_code_blocks, evaluate gate, constrained repair up to 3."""
    text = (prompt or str(draft.get("_user_prompt") or "")).strip()
    gen = generate_blocks or _default_generate_blocks
    try:
        blocks = gen(text, draft)
    except Exception as exc:  # noqa: BLE001
        draft["custom_code_blocks"] = list(draft.get("custom_code_blocks") or [])
        payload = evaluate_authoring_gate(draft, client=client, odoo_major=odoo_major)
        leftover = [
            row
            for row in (payload.get("findings") or [])
            if isinstance(row, dict) and row.get("code") != "empty_module"
        ]
        payload["findings"] = [
            {
                "code": "author_failed",
                "message": _author_fail_message(exc),
                "file": "",
            },
            *leftover,
        ]
        payload["status"] = "fail"
        _stamp_retryable(payload)
        draft["_option_a_authoring"] = payload
        return payload

    if blocks:
        draft["custom_code_blocks"] = blocks
    payload = evaluate_authoring_gate(draft, client=client, odoo_major=odoo_major)
    attempts = 0
    while payload.get("status") != "pass" and attempts < 3:
        begin = begin_repair_attempt(draft, list(payload.get("findings") or []))
        if not begin.get("ok"):
            break
        try:
            _repair_generate(text, draft, list(payload.get("findings") or []), gen)
        except Exception:  # noqa: BLE001
            break
        payload = evaluate_authoring_gate(draft, client=client, odoo_major=odoo_major)
        attempts += 1
    return _stamp_retryable(payload)
