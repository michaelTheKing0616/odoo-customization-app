"""Apply a draft CustomizationProject ModuleSpec-like JSON to a live Odoo connection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from odoo_client import CreateFieldRequest, CreateModelRequest, FieldType, OdooClient
from odoo_client.client import OdooClientError

from app.field_helpers import ensure_currency_field_for_monetary


@dataclass
class ApplyResult:
    models_created: list[str] = field(default_factory=list)
    fields_created: int = 0
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""


_TTYPE_MAP = {
    "char": FieldType.CHAR,
    "text": FieldType.TEXT,
    "html": FieldType.HTML,
    "integer": FieldType.INTEGER,
    "float": FieldType.FLOAT,
    "boolean": FieldType.BOOLEAN,
    "date": FieldType.DATE,
    "datetime": FieldType.DATETIME,
    "binary": FieldType.BINARY,
    "selection": FieldType.SELECTION,
    "many2one": FieldType.MANY2ONE,
    "one2many": FieldType.ONE2MANY,
    "many2many": FieldType.MANY2MANY,
    "monetary": FieldType.MONETARY,
    "json": FieldType.JSON,
}


def _is_currency_companion(field_entry: dict[str, Any]) -> bool:
    if field_entry.get("related"):
        return False
    name = str(field_entry.get("name") or "")
    relation = str(field_entry.get("relation") or "")
    ttype = str(field_entry.get("ttype") or "").lower()
    return ttype == "many2one" and (
        relation == "res.currency" or name.endswith("currency_id")
    )


def _is_monetary_field(field_entry: dict[str, Any]) -> bool:
    ttype = str(field_entry.get("ttype") or "").lower()
    return ttype == "monetary" or bool(field_entry.get("currency_field"))


def _field_create_rank(field_entry: dict[str, Any]) -> int:
    """Currency M2O before scalars, related, then monetary. O2M is a later pass.

    Related fields (including related x_currency_id) must not rank as currency
    companions — Odoo rejects a related path whose hop is not yet on the model.
    """
    if field_entry.get("related"):
        return 2
    if _is_currency_companion(field_entry):
        return 0
    if _is_monetary_field(field_entry):
        return 3
    return 1


def _spec_models_index(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for model in spec.get("models") or []:
        if isinstance(model, dict) and model.get("model"):
            out[str(model["model"])] = model
    return out


def _create_one_field(
    client: OdooClient,
    model_name: str,
    field_entry: dict[str, Any],
    result: ApplyResult,
) -> None:
    fname = field_entry.get("name")
    if not fname or not isinstance(fname, str):
        return
    if fname == "x_name" and client.field_exists(model_name, "x_name"):
        return
    if client.field_exists(model_name, fname):
        result.skipped.append(f"field:{model_name}.{fname}")
        return
    related = str(field_entry.get("related") or "").strip()
    if related:
        hop = related.split(".")[0]
        if hop and not client.field_exists(model_name, hop):
            result.warnings.append(
                f"Skipped {model_name}.{fname}: related hop {hop!r} missing"
            )
            return
    ttype_raw = str(field_entry.get("ttype") or "char").lower()
    ttype = _TTYPE_MAP.get(ttype_raw)
    if ttype is None:
        result.warnings.append(
            f"Unsupported ttype {ttype_raw!r} for {model_name}.{fname}"
        )
        return
    try:
        req = CreateFieldRequest(
            model=model_name,
            name=fname,
            field_description=str(
                field_entry.get("string")
                or field_entry.get("field_description")
                or fname
            ),
            ttype=ttype,
            required=bool(field_entry.get("required")),
            readonly=bool(field_entry.get("readonly")),
            relation=field_entry.get("relation"),
            relation_field=field_entry.get("relation_field"),
            selection=field_entry.get("selection"),
            help=field_entry.get("help"),
            related=field_entry.get("related"),
            currency_field=field_entry.get("currency_field"),
            on_delete=field_entry.get("on_delete"),
        )
        client.create_field(req)
        result.fields_created += 1
    except (OdooClientError, ValueError, Exception) as exc:  # noqa: BLE001
        result.warnings.append(f"Failed {model_name}.{fname}: {exc}")


def _ensure_live_currency_for_monetary(
    client: OdooClient,
    model_name: str,
    field_entry: dict[str, Any],
    result: ApplyResult,
) -> None:
    currency_name = str(field_entry.get("currency_field") or "x_currency_id").strip()
    if not currency_name:
        return
    try:
        name, created = ensure_currency_field_for_monetary(
            client, model_name, currency_field=currency_name
        )
        if created:
            result.fields_created += 1
            result.warnings.append(f"Created {model_name}.{name} for monetary apply")
    except (OdooClientError, ValueError, Exception) as exc:  # noqa: BLE001
        result.warnings.append(
            f"Currency field {model_name}.{currency_name} before monetary failed: {exc}"
        )


def _ensure_o2m_inverse_on_live(
    client: OdooClient,
    spec: dict[str, Any],
    parent_model: str,
    field_entry: dict[str, Any],
    result: ApplyResult,
) -> bool:
    """Odoo rejects O2M unless the inverse M2O already exists on the target."""
    relation = str(field_entry.get("relation") or "")
    inverse = str(field_entry.get("relation_field") or "")
    fname = str(field_entry.get("name") or "")
    if not relation or not inverse:
        result.warnings.append(
            f"Skipped {parent_model}.{fname}: O2M missing relation/relation_field"
        )
        return False
    if not relation.startswith("x_"):
        if client.field_exists(relation, inverse):
            return True
        result.warnings.append(
            f"Skipped {parent_model}.{fname}: stock {relation} has no inverse {inverse}"
        )
        return False
    if client.field_exists(relation, inverse):
        return True
    child = _spec_models_index(spec).get(relation)
    inv_spec = None
    if child:
        inv_spec = next(
            (
                f
                for f in (child.get("fields") or [])
                if isinstance(f, dict) and str(f.get("name") or "") == inverse
            ),
            None,
        )
    if not isinstance(inv_spec, dict):
        inv_spec = {
            "name": inverse,
            "ttype": "many2one",
            "string": parent_model,
            "relation": parent_model,
        }
    _create_one_field(client, relation, inv_spec, result)
    if client.field_exists(relation, inverse):
        return True
    result.warnings.append(
        f"Skipped {parent_model}.{fname}: inverse {relation}.{inverse} missing"
    )
    return False


def apply_project_spec(client: OdooClient, spec: dict[str, Any]) -> ApplyResult:
    """Create missing models + fields (currency, then scalars/M2O, then O2M)."""
    result = ApplyResult()
    models = spec.get("models") or []
    if not isinstance(models, list):
        result.warnings.append("spec.models must be a list")
        result.message = "Nothing applied"
        return result

    ready_models: list[tuple[str, dict[str, Any]]] = []

    for model_entry in models:
        if not isinstance(model_entry, dict):
            result.warnings.append(f"Skip non-object model entry: {model_entry!r}")
            continue
        model_name = model_entry.get("model")
        if not model_name or not isinstance(model_name, str):
            result.warnings.append("Skip model without technical name")
            continue
        description = model_entry.get("description") or model_entry.get("name") or model_name
        if not client.model_exists(model_name):
            if not model_name.startswith("x_"):
                result.warnings.append(
                    f"Skip non-custom model {model_name} (does not exist / cannot create)"
                )
                continue
            try:
                client.create_model(
                    CreateModelRequest(name=str(description), model=model_name),
                    with_defaults=True,
                )
                result.models_created.append(model_name)
            except OdooClientError as exc:
                result.warnings.append(f"Failed to create model {model_name}: {exc}")
                continue
        else:
            result.skipped.append(f"model:{model_name}")
        ready_models.append((model_name, model_entry))

    # Pass 1: everything except one2many, currency companions first
    for model_name, model_entry in ready_models:
        fields = model_entry.get("fields") or []
        if not isinstance(fields, list):
            continue
        ordered = [
            f
            for f in fields
            if isinstance(f, dict) and str(f.get("ttype") or "").lower() != "one2many"
        ]
        ordered.sort(key=_field_create_rank)
        for field_entry in ordered:
            if _is_monetary_field(field_entry):
                _ensure_live_currency_for_monetary(
                    client, model_name, field_entry, result
                )
            _create_one_field(client, model_name, field_entry, result)

    # Pass 2: one2many after inverses exist (create missing custom inverses)
    for model_name, model_entry in ready_models:
        fields = model_entry.get("fields") or []
        if not isinstance(fields, list):
            continue
        for field_entry in fields:
            if not isinstance(field_entry, dict):
                continue
            if str(field_entry.get("ttype") or "").lower() != "one2many":
                continue
            if not _ensure_o2m_inverse_on_live(
                client, spec, model_name, field_entry, result
            ):
                continue
            _create_one_field(client, model_name, field_entry, result)

    result.message = (
        f"Applied: {len(result.models_created)} model(s), "
        f"{result.fields_created} field(s); skipped {len(result.skipped)}"
    )
    return result


def diff_project_spec(client: OdooClient, spec: dict[str, Any]) -> dict[str, Any]:
    """Compare draft project spec against live Odoo (pre-apply conflict report)."""
    to_create_models: list[str] = []
    existing_models: list[str] = []
    to_create_fields: list[str] = []
    existing_fields: list[str] = []
    conflicts: list[str] = []
    models = spec.get("models") or []
    if not isinstance(models, list):
        return {
            "ok": False,
            "message": "spec.models must be a list",
            "to_create_models": [],
            "existing_models": [],
            "to_create_fields": [],
            "existing_fields": [],
            "conflicts": ["spec.models must be a list"],
        }

    for model_entry in models:
        if not isinstance(model_entry, dict):
            continue
        model_name = model_entry.get("model")
        if not model_name or not isinstance(model_name, str):
            continue
        exists = client.model_exists(model_name)
        if exists:
            existing_models.append(model_name)
            conflicts.append(
                f"model already exists: {model_name} (fields may still apply)"
            )
        else:
            to_create_models.append(model_name)

        fields = model_entry.get("fields") or []
        if not isinstance(fields, list):
            continue
        for field_entry in fields:
            if not isinstance(field_entry, dict):
                continue
            fname = field_entry.get("name")
            if not fname or not isinstance(fname, str):
                continue
            key = f"{model_name}.{fname}"
            if exists and client.field_exists(model_name, fname):
                existing_fields.append(key)
                conflicts.append(f"field already exists: {key}")
            else:
                to_create_fields.append(key)

    return {
        "ok": True,
        "message": (
            f"{len(to_create_models)} model(s) to create, "
            f"{len(existing_models)} model(s) exist, "
            f"{len(to_create_fields)} field(s) to create, "
            f"{len(existing_fields)} field(s) already live"
        ),
        "to_create_models": to_create_models,
        "existing_models": existing_models,
        "to_create_fields": to_create_fields,
        "existing_fields": existing_fields,
        "conflicts": conflicts,
    }
