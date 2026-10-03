"""Protected registry. Core targets cannot be removed. Tenants may only add.

`protected:deny` blocks the apply at R4. `protected:elevate` raises risk by one
and requires a domain-owner approver. It never lowers risk. Composite expansion,
`$ref`, and batch domains are checked before any journal write.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml

_FLOOR_MODELS = frozenset(
    {
        "account.move",
        "account.move.line",
        "account.payment",
        "account.bank.statement",
        "account.bank.statement.line",
        "stock.quant",
        "stock.move",
        "stock.move.line",
        "hr.payslip",
        "hr.salary.rule",
        "hr.payroll.structure",
        "hr.contract",
        "res.users.apikeys",
        "ir.mail_server",
        "fetchmail.server",
        "payment.provider",
        "delivery.carrier",
    }
)
_FLOOR_ELEVATE = frozenset(
    {
        "account.fiscal.position",
        "account.reconcile.model",
        "product.category",
        "stock.warehouse",
    }
)
_FLOOR_LOCK = frozenset(
    {"lock_date", "fiscalyear_lock_date", "period_lock_date", "tax_lock_date"}
)
_FLOOR_PRIVATE = frozenset(
    {
        "hr.employee:ssnid",
        "hr.employee:passport_id",
        "hr.employee:identification_id",
        "hr.employee:private_street",
        "hr.employee:bank_account_id",
        "res.users:password",
        "res.users:new_password",
        "res.users:totp_secret",
    }
)
_FLOOR_JOURNALS = ("account.journal", "account.move")
_CODE_OPS = frozenset(
    {
        "server_action.create",
        "server_action.update",
        "automation.create",
        "automation.update",
        "cron.create",
        "cron.update",
    }
)
_BATCH_OPS = frozenset(
    {
        "data.create_batch",
        "data.update_batch",
        "data.archive_batch",
        "data.import_upsert",
        "data.merge",
        "data.delete",
    }
)
_FIELD_OPS = frozenset({"field.create", "field.update", "field.delete"})
_SETTING_OPS = frozenset({"setting.set", "company.update", "config_param.set"})
_SEQUENCE_OPS = frozenset({"sequence.create", "sequence.update"})
_SEQUENCE_KEYS = ("code", "alias", "alias_of", "same_as", "redirect", "target", "xmlid", "xml_id", "name")
_MODEL_KEYS = frozenset(
    {
        "model",
        "models",
        "relation",
        "comodel",
        "comodel_name",
        "target_model",
        "inherit",
        "_inherit",
        "inherits",
        "parent_model",
        "relation_model",
        "res_model",
        "model_id",
    }
)
_FLOOR_TRICKS = (
    "sudo(",
    "getattr(",
    "__getattr__",
    "__getitem__(",
    "env[",
    "self.env",
    "env.get(",
    "env.cr",
    ".cr.",
    "with_user(",
    "_cr.",
    "_cr(",
    "setattr(",
    "pool[",
    "eval(",
    "exec(",
    "__import__",
    "globals(",
)
_OVERFLOW = "__registry_overflow__"


class _Unresolved:
    """A $ref that does not resolve. Apply must fail closed."""
_ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)
_CONFUSABLES = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ј": "j",
    }
)
_DETECTIONS: list[dict[str, str]] = []
_YAML: dict[str, Any] | None = None


def reset_detections() -> None:
    _DETECTIONS.clear()


def detections() -> list[dict[str, str]]:
    return list(_DETECTIONS)


def _yaml() -> dict[str, Any]:
    global _YAML
    if _YAML is None:
        path = Path(__file__).with_name("protected_core.yaml")
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        _YAML = loaded if isinstance(loaded, dict) else {}
    return _YAML


def _strings(key: str) -> frozenset[str]:
    raw = _yaml().get(key) or []
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(item) for item in raw if isinstance(item, str))


def deny_models(tenant: dict[str, Any] | None = None) -> frozenset[str]:
    """Core union YAML union tenant additions. `remove_models` is ignored."""
    added: set[str] = set()
    if tenant:
        extra = tenant.get("add_models") or []
        if isinstance(extra, list):
            added.update(str(item) for item in extra)
    return _FLOOR_MODELS | _strings("deny_models") | added


def elevate_models() -> frozenset[str]:
    return _FLOOR_ELEVATE | _strings("elevate_models")


def _norm(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).translate(_ZW).casefold()
    return folded.translate(_CONFUSABLES).strip()


def _dotted(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._" else "." for ch in _norm(text))
    return f".{cleaned}."


def _hits_model(text: str, models: frozenset[str]) -> bool:
    padded = _dotted(text)
    for model in models:
        if f".{_norm(model)}." in padded:
            return True
    return False


def _params(op: dict[str, Any]) -> dict[str, Any]:
    raw = op.get("params")
    return raw if isinstance(raw, dict) else {}


def _collect_refs(value: Any, found: list[str]) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            found.append(ref)
        for item in value.values():
            _collect_refs(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_refs(item, found)


def _resolve_pointer(pointer: str, document: list[dict[str, Any]]) -> Any:
    walked = _walk_pointer(pointer, document)
    if isinstance(walked, _Unresolved):
        return pointer
    return walked


def _resolve(value: Any, document: list[dict[str, Any]], depth: int = 0) -> Any:
    if depth > 12:
        return {"__registry_overflow__": True}
    if isinstance(value, dict):
        if value.get("__registry_overflow__") is True:
            return value
        ref = value.get("$ref")
        if isinstance(ref, str):
            walked = _walk_pointer(ref, document)
            if not isinstance(walked, _Unresolved):
                return _resolve(walked, document, depth + 1)
        return {key: _resolve(item, document, depth + 1) for key, item in value.items() if key != "$ref"}
    if isinstance(value, list):
        return [_resolve(item, document, depth + 1) for item in value]
    return value


def _contains_overflow(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("__registry_overflow__") is True:
            return True
        return any(_contains_overflow(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_overflow(item) for item in value)
    return False


def _model_name(params: dict[str, Any]) -> str:
    model = params.get("model")
    return model if isinstance(model, str) else ""


def _is_model(name: str, models: frozenset[str]) -> bool:
    if not name:
        return False
    normed = _norm(name)
    for model in models:
        token = _norm(model)
        if normed == token or normed.startswith(token + "."):
            return True
    return False


def _stored_compute(params: dict[str, Any]) -> bool:
    store = params.get("store")
    if store in {True, 1, "1", "true", "True"}:
        return True
    # An omitted store flag with a compute can still be stored. Explicit store false is not.
    if params.get("compute") and store not in {False, 0, "0", "false", "False"}:
        return True
    return False


def _bad_setting_token(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    token = _norm(value).strip()
    locks = {_norm(item).strip() for item in _FLOOR_LOCK | _strings("lock_fields")}
    if token in locks or token == "lock_date" or token.endswith("_lock_date"):
        return True
    if token.startswith("module_"):
        return True
    return token in {"module.install", "module.upgrade"}


def _lock_or_module(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _bad_setting_token(key) or _bad_setting_token(item) or _lock_or_module(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_bad_setting_token(item) or _lock_or_module(item) for item in value)
    return _bad_setting_token(value)


def _private_tokens() -> frozenset[str]:
    return frozenset(_norm(item) for item in _FLOOR_PRIVATE | _strings("private_fields"))


def _private_names(model: str, tokens: frozenset[str]) -> frozenset[str]:
    prefix = f"{_norm(model)}:"
    return frozenset(token.split(":", 1)[1] for token in tokens if token.startswith(prefix))


def _private_hit(value: Any, model: str, tokens: frozenset[str] | None = None) -> bool:
    known = tokens if tokens is not None else _private_tokens()
    if isinstance(value, dict):
        row_model = model
        named = value.get("model")
        if isinstance(named, str):
            row_model = named
        names = _private_names(row_model, known)
        for key, item in value.items():
            if _norm(key) in names or _norm(f"{row_model}:{key}") in known:
                return True
            if isinstance(item, str) and _norm(item) in names:
                return True
            if _private_hit(item, row_model, known):
                return True
        return False
    if isinstance(value, list):
        return any(_private_hit(item, model, known) for item in value)
    if isinstance(value, str):
        return _norm(value) in _private_names(model, known)
    return False


def _domain_texts(value: Any, found: list[str]) -> None:
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _domain_texts(item, found)
    elif isinstance(value, list):
        for item in value:
            _domain_texts(item, found)


def _batch_hits(params: dict[str, Any], models: frozenset[str]) -> bool:
    if _is_model(_model_name(params), models):
        return True
    texts: list[str] = []
    _domain_texts(params, texts)
    return any(_hits_model(text, models) for text in texts)


def _sequence_hits(params: dict[str, Any]) -> bool:
    markers = tuple(_FLOOR_JOURNALS) + tuple(sorted(_strings("journal_markers")))
    for key in _SEQUENCE_KEYS:
        value = params.get(key)
        if not isinstance(value, str):
            continue
        padded = _dotted(value)
        for marker in markers:
            if f".{_norm(marker)}." in padded:
                return True
    return False


def _code_tricks() -> tuple[str, ...]:
    return _FLOOR_TRICKS + tuple(sorted(_strings("code_tricks")))


def _code_hits(params: dict[str, Any], models: frozenset[str]) -> bool:
    chunks: list[str] = []
    _domain_texts(params, chunks)
    if not chunks:
        return False
    tricks = tuple(re.sub(r"\s+", "", _norm(trick)) for trick in _code_tricks())
    for chunk in chunks:
        folded = re.sub(r"\s+", "", _norm(chunk))
        if any(trick in folded for trick in tricks):
            return True
        if _hits_model(chunk, models):
            return True
        for piece in re.findall(r"[a-z0-9_]+", folded):
            if _bad_setting_token(piece):
                return True
    return False


def _model_key_hits(value: Any, models: frozenset[str], parent_key: str = "") -> bool:
    if isinstance(value, dict):
        return any(_model_key_hits(item, models, key) for key, item in value.items())
    if isinstance(value, list):
        if parent_key in _MODEL_KEYS and any(isinstance(item, str) and _hits_model(item, models) for item in value):
            return True
        return any(_model_key_hits(item, models, parent_key) for item in value)
    if isinstance(value, str) and parent_key in _MODEL_KEYS:
        return _hits_model(value, models)
    return False


def _expand(op: dict[str, Any], *, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 8:
        return [{"type": _OVERFLOW, "params": {}}]
    if str(op.get("type") or "") != "model.scaffold":
        return [op]
    params = _params(op)
    children: list[dict[str, Any]] = []
    models: list[str] = []
    if isinstance(params.get("model"), str):
        models.append(str(params["model"]))
    extra = params.get("models")
    if isinstance(extra, list):
        models.extend(str(item) for item in extra if isinstance(item, str))
    for model in models:
        children.append({"type": "model.create", "params": {"model": model}})
        fields = params.get("fields")
        if isinstance(fields, list):
            for field in fields:
                if isinstance(field, dict):
                    body = dict(field)
                    body.setdefault("model", model)
                    children.append({"type": "field.create", "params": body})
    nested = params.get("ops") if isinstance(params.get("ops"), list) else params.get("children")
    if isinstance(nested, list):
        for child in nested:
            if isinstance(child, dict):
                children.extend(_expand(child, depth=depth + 1))
    return children or [op]


def _pointer_parts(pointer: str) -> list[str] | None:
    text = unquote(pointer.strip()).rstrip("/")
    if text.startswith("#/"):
        text = text[2:]
    elif text.startswith("#"):
        text = text[1:].lstrip("/")
    elif not re.match(r"^(ops[./\[])?\d+", text):
        return None
    text = text.replace("[", "/").replace("]", "")
    if "/" not in text:
        parts = text.split(".")
    else:
        parts = [part for part in text.split("/") if part]
    parts = [part.strip("'\"") for part in parts if part.strip("'\"")]
    if parts and parts[0] == "ops":
        parts = parts[1:]
    if not parts or not parts[0].isdigit():
        return None
    return parts


def _walk_pointer(pointer: str, document: list[dict[str, Any]]) -> Any:
    parts = _pointer_parts(pointer)
    if parts is None:
        return _Unresolved()
    current: Any = document
    for part in parts:
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index < 0 or index >= len(current):
                return _Unresolved()
            current = current[index]
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return _Unresolved()
    return current


def _value_hits_model(value: Any, models: frozenset[str]) -> bool:
    if isinstance(value, str):
        return _hits_model(value, models)
    texts: list[str] = []
    _domain_texts(value, texts)
    return any(_hits_model(text, models) for text in texts)


def _leaf_case(op: dict[str, Any], models: frozenset[str]) -> str | None:
    op_type = str(op.get("type") or "")
    if op_type == _OVERFLOW:
        return "RT-10"
    params = _params(op)
    model = _model_name(params)
    if op_type in _CODE_OPS and _code_hits(params, models):
        return "RT-15"
    if op_type in _SEQUENCE_OPS and (_sequence_hits(params) or params.get("accounting") or params.get("legal")):
        return "RT-16"
    if op_type in _SETTING_OPS and _lock_or_module(params):
        return "RT-13"
    if _private_hit(params, model):
        return "RT-14"
    if op_type in _FIELD_OPS and _is_model(model, models) and _stored_compute(params):
        return "RT-14"
    if op_type in {"model.create", "model.scaffold"} and _is_model(model, models):
        return "RT-10"
    if op_type in _BATCH_OPS and _batch_hits(params, models):
        return "RT-12"
    if op_type.startswith("cron.") and _is_model(model, models):
        return "RT-15"
    return None


def protected_case(
    op: dict[str, Any],
    *,
    document: list[dict[str, Any]] | None = None,
    tenant: dict[str, Any] | None = None,
) -> str | None:
    doc = document if document is not None else [op]
    models = deny_models(tenant)
    refs: list[str] = []
    _collect_refs(op, refs)
    ref_case = "RT-10" if str(op.get("type") or "") == "model.scaffold" else "RT-11"
    for ref in refs:
        if _hits_model(ref, models):
            return ref_case
        resolved_ref = _walk_pointer(ref, doc)
        if isinstance(resolved_ref, _Unresolved) or _value_hits_model(resolved_ref, models):
            return ref_case
    resolved = _resolve(op, doc)
    if _contains_overflow(resolved):
        return ref_case or "RT-11"
    if not isinstance(resolved, dict):
        return None
    if str(op.get("type") or "") == "model.scaffold":
        if _model_key_hits(_params(resolved), models):
            return "RT-10"
        for child in _expand(resolved):
            if _leaf_case(child, models):
                return "RT-10"
        return None
    return _leaf_case(resolved, models)


def resolve_op(op: dict[str, Any], document: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Replace `$ref` values with the subtree they point at. Unresolved refs stay put."""
    doc = document if document is not None else [op]
    resolved = _resolve(op, doc)
    return resolved if isinstance(resolved, dict) else op


def protected_denial(
    op: dict[str, Any],
    *,
    document: list[dict[str, Any]] | None = None,
    tenant: dict[str, Any] | None = None,
) -> str | None:
    case = protected_case(op, document=document, tenant=tenant)
    if case is None:
        return None
    _DETECTIONS.append(
        {
            "case": case,
            "op_type": str(op.get("type") or ""),
            "alert": "policy_denied",
        }
    )
    return "protected_deny"


def protection_level(
    op: dict[str, Any],
    *,
    document: list[dict[str, Any]] | None = None,
    tenant: dict[str, Any] | None = None,
) -> str | None:
    if protected_case(op, document=document, tenant=tenant):
        return "deny"
    doc = document if document is not None else [op]
    resolved = _resolve(op, doc)
    params = _params(resolved if isinstance(resolved, dict) else op)
    model = _model_name(params)
    if _is_model(model, deny_models(tenant)) or _is_model(model, elevate_models()):
        return "elevate"
    return None


def requires_domain_owner(
    op: dict[str, Any],
    *,
    document: list[dict[str, Any]] | None = None,
    tenant: dict[str, Any] | None = None,
) -> bool:
    """True when the op is `protected:elevate` and needs a domain-owner approver.

    Inputs: one op, the optional change-set it `$ref`s, and an optional tenant overlay.
    Output: whether a domain owner must approve. Deny stays a block, not an approval.
    Side effects: none. This does not record a detection.
    """
    return protection_level(op, document=document, tenant=tenant) == "elevate"
