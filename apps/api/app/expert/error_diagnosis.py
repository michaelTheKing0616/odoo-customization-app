"""Rule-based RPC error diagnosis when RAG retrieval is thin or absent."""

from __future__ import annotations

import re
from typing import Any

from app.expert.grounding import (
    GroundingBundle,
    extract_model_field_refs,
    looks_like_conceptual_question,
    looks_like_rpc_error,
)

_MODEL_NOT_FOUND_RE = re.compile(
    r"(?i)(?:model not found|unknown model|no model named):\s*['\"]?([a-z][a-z0-9_]*)"
)
_VALIDATING_VIEW_RE = re.compile(r"(?i)error while validating view")
_ACCESS_ERROR_RE = re.compile(
    r"(?i)(access\s*error|accesserror|not allowed to (?:access|modify|create|delete))"
)
_FAULT_RE = re.compile(r"(?i)(?:<fault\s*\d+:|fault\s+\d+:)")


def _format_ref(model: str, field: str | None) -> str:
    return f"`{model}.{field}`" if field else f"`{model}`"


def try_rule_based_error_diagnosis(
    question: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    client: Any | None = None,
) -> dict[str, Any] | None:
    """Return answer fields when the error matches a known remediation pattern."""
    del client
    if not looks_like_rpc_error(question):
        return None
    if looks_like_conceptual_question(question):
        return None

    lines: list[str] = []
    caution = ["rule_based_diagnosis"]

    for diag in bundle.error_diagnostics or []:
        status = diag.get("status")
        model = str(diag.get("model") or "").strip()
        fld = diag.get("field")
        field = str(fld).strip() if fld else None
        suggestion = str(diag.get("suggestion") or "").strip()

        if status == "model_missing" and model:
            lines.append(
                f"**Root cause:** {_format_ref(model, None)} does not exist on this connection "
                f"(`ir.model` has no record)."
            )
            if model.startswith("x_"):
                lines.extend(
                    [
                        "",
                        "**Fix:**",
                        f"1. Create the custom model `{model}` in **Models & Fields**, or save from "
                        "**Designer** with standard write mode enabled (missing `x_*` models are auto-created).",
                        "2. Re-save the view or retry the action after the model exists.",
                    ]
                )
            else:
                lines.extend(
                    [
                        "",
                        "**Fix:**",
                        f"1. Install or enable the module that provides `{model}`, or fix the model name if it is a typo.",
                        "2. Retry after the model is available on this database.",
                    ]
                )
            if suggestion:
                lines.append(f"3. {suggestion}")
        elif status == "field_missing" and model and field:
            lines.append(
                f"**Root cause:** Field {_format_ref(model, field)} does not exist on this connection."
            )
            if suggestion:
                lines.append(f"**Likely fix:** {suggestion}")
            else:
                lines.append(
                    f"**Fix:** Add `{field}` on `{model}` in Models & Fields, or fix the typo in your view/automation."
                )
        elif status == "model_ok" and model and not field:
            lines.append(
                f"**Note:** Model `{model}` exists — if you still see errors, check field names, "
                "view XML, or access rights rather than a missing model."
            )

    if not lines:
        model_match = _MODEL_NOT_FOUND_RE.search(question)
        if model_match:
            model = model_match.group(1).lower()
            if _VALIDATING_VIEW_RE.search(question) or "view" in question.lower():
                lines.append(
                    f"**Root cause:** Odoo could not validate the view because model `{model}` "
                    "is not registered in `ir.model`."
                )
                if model.startswith("x_"):
                    lines.extend(
                        [
                            "",
                            "**Fix:**",
                            f"1. Create `{model}` in **Models & Fields** before saving the view.",
                            "2. Or use **Designer → Save to Odoo** with standard write mode enabled — "
                            "missing `x_*` models are auto-created on save.",
                            "3. Re-save the view after the model exists.",
                        ]
                    )
                else:
                    lines.extend(
                        [
                            "",
                            "**Fix:**",
                            f"1. Ensure the module providing `{model}` is installed.",
                            "2. Verify the model name in the view matches an existing model on this database.",
                        ]
                    )
            else:
                lines.append(f"**Root cause:** Model `{model}` was not found on this connection.")
                if model.startswith("x_"):
                    lines.append(
                        f"**Fix:** Create the custom model `{model}` in Models & Fields, then retry."
                    )

    if not lines and _ACCESS_ERROR_RE.search(question):
        model_from_error = re.search(r"['\"]([a-z][a-z0-9_.]*)['\"]", question, re.I)
        target = model_from_error.group(1) if model_from_error else (bundle.ui_context or {}).get(
            "model"
        )
        lines.append(
            "**Root cause:** An **AccessError** means your Odoo user lacks permission for this "
            "operation (model ACL or record rules)."
        )
        fix_lines = [
            "",
            "**Fix:**",
            "1. In Odoo, check **Settings → Users & Companies → Groups** for a group with the needed access.",
            "2. In this app, use **Access Matrix** to grant the relevant group read/write on the model.",
        ]
        if target:
            fix_lines.append(f"3. The error references `{target}` — verify `ir.model.access` and record rules.")
        if connection_id:
            fix_lines.append(
                f"4. Open `/connections/{connection_id}/access-matrix` in this app to adjust ACLs."
            )
        lines.extend(fix_lines)

    if not lines and (_FAULT_RE.search(question) or _VALIDATING_VIEW_RE.search(question)):
        refs = extract_model_field_refs(question)
        if refs:
            ref_text = ", ".join(_format_ref(m, f) for m, f in refs)
            lines.append(f"**Detected references:** {ref_text}")
            lines.extend(
                [
                    "",
                    "**Next steps:**",
                    "1. Confirm each model exists in **Models & Fields** on this connection.",
                    "2. Enable standard write mode on the connection if you need live fixes.",
                    "3. Re-try the action after schema or ACL issues are corrected.",
                ]
            )

    if not lines:
        return None

    answer = "\n".join(lines)
    if connection_id and bundle.error_diagnostics:
        answer += "\n\n*Live schema cross-check ran against this connection.*"
    elif connection_id:
        answer += "\n\n*Diagnosis from the error text and connection context.*"
    else:
        answer += (
            "\n\n*Connect an Odoo instance for live schema cross-checks and version-filtered docs.*"
        )

    return {
        "answer_markdown": answer,
        "grounded": bool(
            connection_id and (bundle.error_diagnostics or bundle.instance_summary)
        ),
        "declined": False,
        "caution_flags": caution,
    }
