"""Dual-layer Expert answers: generic guidance + live connection caveats."""

from __future__ import annotations

from typing import Any

from app.expert.grounding import GroundingBundle


def _format_ref(model: str, field: str | None) -> str:
    return f"`{model}.{field}`" if field else f"`{model}`"


def format_instance_caveats(
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
) -> str | None:
    """Build the 'On your connection' section from live schema diagnostics."""
    diags = list(bundle.error_diagnostics or [])
    if not diags:
        return None

    lines: list[str] = []
    summary = bundle.instance_summary or {}
    label = summary.get("server_version") or "this connection"
    if connection_id and summary:
        lines.append(
            f"Live schema cross-check on **{label}** "
            f"(connection `{connection_id[:8]}…`):"
        )
    elif connection_id:
        lines.append("Live schema cross-check on **this connection**:")
    else:
        lines.append("Instance notes:")

    missing_models: list[str] = []
    missing_fields: list[str] = []
    ok_models: list[str] = []

    for diag in diags:
        status = str(diag.get("status") or "")
        model = str(diag.get("model") or "").strip()
        fld = diag.get("field")
        field = str(fld).strip() if fld else None
        suggestion = str(diag.get("suggestion") or "").strip()

        if status == "model_missing" and model:
            missing_models.append(model)
            if model.startswith("x_"):
                fix = (
                    f"Create **`{model}`** in **Models & Fields**, or save from **Designer** "
                    "with standard write mode enabled (missing `x_*` models are auto-created)."
                )
            else:
                fix = (
                    f"Install or enable the module that provides **`{model}`**, "
                    "or fix the technical name if it is a typo."
                )
            lines.extend(["", f"- **`{model}`** is not registered in `ir.model`. {fix}"])
            if suggestion and not model.startswith("x_"):
                lines.append(f"  {suggestion}")
        elif status == "field_missing" and model and field:
            missing_fields.append(_format_ref(model, field))
            hint = suggestion or (
                f"Add **`{field}`** on **`{model}`** in Models & Fields, "
                "or fix the typo in your view/automation."
            )
            lines.extend(["", f"- Field {_format_ref(model, field)} does not exist. {hint}"])
        elif status in {"model_ok", "ok"} and model:
            ok_models.append(model)

    if not missing_models and not missing_fields:
        return None

    if ok_models:
        ok_unique = sorted(
            {m for m in ok_models if not m.startswith("ir.")},
        )[:4]
        if ok_unique:
            lines.extend(
                [
                    "",
                    "Models confirmed present: "
                    + ", ".join(f"`{m}`" for m in ok_unique)
                    + ".",
                ]
            )

    if connection_id:
        lines.extend(
            [
                "",
                f"Designer: `/connections/{connection_id}/designer` — "
                "create missing models/fields, then retry.",
            ]
        )

    return "\n".join(lines).strip()


def compose_dual_layer_answer(
    general_markdown: str,
    bundle: GroundingBundle,
    *,
    connection_id: str | None = None,
    section_title: str = "Answer",
) -> tuple[str, list[str]]:
    """Prepend generic answer; append live caveats when diagnostics found gaps."""
    flags: list[str] = []
    general = (general_markdown or "").strip()
    caveats = format_instance_caveats(bundle, connection_id=connection_id)
    if not caveats:
        return general, flags

    flags.append("instance_caveats")
    if general.startswith("## "):
        body = f"{general}\n\n## On your connection\n\n{caveats}"
    else:
        body = f"## {section_title}\n\n{general}\n\n## On your connection\n\n{caveats}"
    return body, flags


__all__ = [
    "compose_dual_layer_answer",
    "format_instance_caveats",
]
