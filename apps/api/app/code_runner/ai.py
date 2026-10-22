"""Inline AI for the runner: explain, comment-to-code, fix error. AI proposes; code authorizes.

The proposal is returned as new code for an accepted diff. Code checks it before it is shown:
it must parse, is linted against the live schema, and any write to money records is flagged
so the money guard (dry run + approval) stays in force when it runs.
"""

from __future__ import annotations

import ast
import re
from typing import Any

ACTIONS = {"explain", "comment_to_code", "fix"}
MONEY_MODELS = re.compile(r"^(account\.|sale\.order|purchase\.order|pos\.|hr\.payslip|hr\.expense|stock\.valuation)")
WRITE_METHODS = {"create", "write", "unlink", "copy"}
SYSTEM = (
    "You help write Python scripts that run against Odoo through one function: "
    "odoo.execute_kw(model, method, args, kwargs). Other helpers: log(msg), progress(done, total). "
    "No imports, no files, no network. Use only public ORM methods. Use the version and models given. "
    "Reply as JSON: {\"code\": full new script or empty for explain, \"explanation\": plain words for a "
    "non-technical owner, at most 4 sentences}. Keep the owner's code and comments unless the request changes them."
)
SCHEMA = {"type": "object", "properties": {"code": {"type": "string"}, "explanation": {"type": "string"}},
          "required": ["code", "explanation"]}


def money_writes(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "execute_kw" and len(n.args) >= 2:
            m, meth = (a.value if isinstance(a, ast.Constant) else None for a in n.args[:2])
            if isinstance(m, str) and meth in WRITE_METHODS and MONEY_MODELS.search(m):
                out.append(f"{meth} on {m}")
    return sorted(set(out))


def authorize(code: str, original: str, lint_fn: Any) -> dict[str, Any]:
    """Code-side check of an AI proposal. Never runs it."""
    if not code.strip():
        return {"ok": True, "issues": [], "money": []}
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return {"ok": False, "reason": f"The suggestion isn't valid Python ({exc.msg}); nothing was changed.",
                "issues": [], "money": []}
    if re.search(r"^\s*(import|from)\s+\w+", code, re.M) or re.search(r"\b(__import__|eval|exec|open)\s*\(", code):
        return {"ok": False, "reason": "The suggestion tried to use imports or files, which scripts can't do; nothing was changed.",
                "issues": [], "money": []}
    new_money = sorted(set(money_writes(code)) - set(money_writes(original)))
    return {"ok": True, "issues": lint_fn(code), "money": new_money}


class ConsentRequired(Exception):
    pass


def _local_call(payload: dict[str, Any], step: str) -> dict[str, Any]:
    """Local model only: no fallback to any cloud provider, ever."""
    import json

    from app.ai_client.shared_client import wrap
    from app.llm_json import parse_llm_json_object
    from app.llm_provider import OllamaProvider
    from app.view_engine_ai import AIUnavailable

    prov = wrap(OllamaProvider())
    ok, why = prov.reachable(timeout_s=2.0)
    if not ok:
        raise AIUnavailable(f"The local assistant isn't running ({why[:80]}). Start it, or allow the cloud assistant in settings.")
    try:
        text = prov.generate_json(json.dumps({**payload, "answer_schema": SCHEMA}, ensure_ascii=False), system=SYSTEM,
                                        temperature=0.0, format_schema=SCHEMA, timeout_s=120.0)
        return parse_llm_json_object(text)
    except Exception as exc:  # noqa: BLE001
        raise AIUnavailable(f"The local assistant didn't answer ({str(exc)[:100]}).") from exc


def propose(action: str, code: str, *, request: str, error: str, major: int, models_hint: list[str],
            mode: str = "local", consent: dict[str, Any] | None = None) -> dict[str, Any]:
    """Item 29: local model by default; the cloud model only with a recorded consent."""
    from app.view_engine_ai import _call

    payload = {"action": action, "odoo_major": major, "script": code[:20000], "request": request[:2000],
               "error": error[:4000], "models_on_database": models_hint[:200]}
    if mode == "cloud":
        if not (consent or {}).get("by_at"):
            raise ConsentRequired("Sending code to the cloud assistant needs consent first.")
        out = _call(SYSTEM, payload, SCHEMA, f"code_runner_{action}")
    else:
        out = _local_call(payload, f"code_runner_{action}_local")
    return {"code": str(out.get("code") or ""), "explanation": str(out.get("explanation") or "")[:1200]}
