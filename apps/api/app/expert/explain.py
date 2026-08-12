"""Grounded explain-this for models and fields in draft / builder context."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.expert.ask import ExpertAskResult, ask_expert


def _model_fields_from_draft(draft: dict[str, Any] | None, model: str) -> list[dict[str, Any]]:
    if not draft or not model:
        return []
    for row in draft.get("models") or []:
        if isinstance(row, dict) and str(row.get("model") or "") == model:
            fields = row.get("fields") or []
            return [f for f in fields if isinstance(f, dict)]
    return []


def build_explain_question(
    *,
    model: str,
    field: str | None = None,
    draft: dict[str, Any] | None = None,
    user_prompt: str = "",
) -> str:
    fields = _model_fields_from_draft(draft, model)
    field_row = next((f for f in fields if str(f.get("name") or "") == field), None) if field else None

    if field and field_row:
        ttype = field_row.get("ttype") or "?"
        string = field_row.get("string") or field
        relation = field_row.get("relation")
        rel_bit = f" relation={relation}" if relation else ""
        return (
            f"Explain the purpose of field `{field}` ({ttype}{rel_bit}, label \"{string}\") "
            f"on custom model `{model}` in this draft. Why is it included and how would it "
            f"be used in Odoo Community?"
        )

    desc = ""
    for row in draft.get("models") or [] if draft else []:
        if isinstance(row, dict) and str(row.get("model") or "") == model:
            desc = str(row.get("description") or "")
            break

    prompt_ctx = f" User goal: {user_prompt[:240]}." if user_prompt else ""
    if field:
        return (
            f"Explain field `{field}` on model `{model}` in this Odoo customization draft.{prompt_ctx} "
            f"Cover field type, business meaning, and typical form/list usage."
        )

    field_names = [str(f.get("name")) for f in fields[:12] if f.get("name")]
    field_hint = f" Key fields: {', '.join(field_names)}." if field_names else ""
    desc_hint = f" Model purpose: {desc}." if desc else ""
    return (
        f"Explain custom model `{model}` in this Odoo Community draft.{desc_hint}{field_hint}{prompt_ctx} "
        f"Cover workflow role, relationships, and how it fits the app."
    )


def explain_model_or_field(
    db: Session,
    *,
    model: str,
    field: str | None = None,
    draft: dict[str, Any] | None = None,
    user_prompt: str = "",
    connection_id: str | None = None,
    client: Any | None = None,
) -> ExpertAskResult:
    """Retrieve + answer for a specific model/field with draft context."""
    question = build_explain_question(
        model=model,
        field=field,
        draft=draft,
        user_prompt=user_prompt,
    )
    ui_context: dict[str, Any] = {
        "model": model,
        "explain_target": field or model,
        "draftSummary": f"{model}" + (f".{field}" if field else ""),
    }
    if draft:
        ui_context["draft_spec"] = {
            "models": [
                m
                for m in (draft.get("models") or [])
                if isinstance(m, dict) and str(m.get("model") or "") == model
            ][:1],
            "grain": draft.get("grain"),
            "domain_pack": draft.get("domain_pack"),
        }
    return ask_expert(
        db,
        question=question,
        connection_id=connection_id,
        ui_context=ui_context,
        client=client,
    )


__all__ = ["build_explain_question", "explain_model_or_field"]
