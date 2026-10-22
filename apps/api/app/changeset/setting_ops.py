"""Settings and module family risk raises.

The catalog in ``ops.py`` stays the source for base risk. This module raises
that base for ``module_*`` settings, protected config keys, and company lock
dates, fiscal year, currency, and chart of accounts. It does not call Odoo.
"""

from __future__ import annotations

import re
from typing import Any

INSTALL_REVERSAL_WARNING = (
    "install is reversible only by uninstall, which is R4 and prohibited in v1"
)
BILLABLE_WARNING = (
    "this may add a paid app on Enterprise, Odoo Online, or Odoo.sh. "
    "Community does not bill for it"
)
SETTING_OP_TYPES = frozenset(
    {"setting.set", "config_param.set", "company.update", "module.install", "module.upgrade"}
)
_FIELD_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")
_MODULE_NAME = re.compile(r"^[a-z0-9_]+$")
_COMPANY_ID_KEYS = frozenset({"id", "ids", "company_id"})
_SCALAR = (str, int, float, bool)

PROTECTED_CONFIG_KEYS = frozenset(
    {
        "database.secret",
        "database.uuid",
        "database.create_date",
        "web.base.url",
        "database.enterprise_code",
        "database.expiration_date",
    }
)

_PAID_EDITIONS = frozenset({"enterprise", "online", "odoo_sh"})
_MODULE_OPS = frozenset({"module.install", "module.upgrade"})
_FISCAL_KEYS = frozenset(
    {
        "fiscalyear",
        "fiscal_year",
        "fiscalyear_last_day",
        "fiscalyear_last_month",
    }
)
_CURRENCY_KEYS = frozenset({"currency", "currency_id"})
_CHART_KEYS = frozenset(
    {
        "chart",
        "chart_template",
        "chart_template_id",
        "chart_of_accounts",
    }
)
_WALK_LIMIT = 8


def setting_base_raise(op_type: str, params: dict[str, Any] | None) -> str | None:
    """Catalog raise for a settings op, before policy bumps.

    Inputs: op type and params. A missing params dict is treated as empty.
    Outputs: ``R3`` for a ``setting.set`` whose key is ``module_*``. ``R4``
    for a protected config key or a company lock date, fiscal year, currency,
    or chart of accounts change. Otherwise ``None``. ``module.install`` and
    ``module.upgrade`` stay on the catalog base. ``module.uninstall`` is not
    lowered.
    Side effects: none.
    """
    body = params if isinstance(params, dict) else {}
    if op_type == "setting.set" and module_setting(body):
        return "R3"
    if op_type == "config_param.set" and protected_config_key(body):
        return "R4"
    if op_type == "company.update" and company_is_r4(body):
        return "R4"
    return None


def may_be_billable(
    op_type: str,
    params: dict[str, Any] | None = None,
    *,
    edition: str = "community",
) -> bool:
    """Whether this op may change what the client pays on that edition.

    Inputs: op type, optional params, and an edition name.
    Outputs: True for ``module.install``, ``module.upgrade``, and a
    ``setting.set`` of ``module_*`` when the edition is enterprise, online,
    or Odoo.sh. Community is False. ``module.uninstall`` is False because
    that op is R4 and prohibited in v1.
    Side effects: none.
    """
    if _edition(edition) not in _PAID_EDITIONS:
        return False
    if op_type in _MODULE_OPS:
        return True
    body = params if isinstance(params, dict) else {}
    return op_type == "setting.set" and module_setting(body)


def billable_warning(op_type: str, params: dict[str, Any] | None = None) -> str | None:
    """Warning for an op that may add a paid app on a paid edition.

    Inputs: op type and optional params.
    Outputs: ``BILLABLE_WARNING`` when ``may_be_billable`` is True on
    Enterprise. ``None`` otherwise. The plan card has no edition, so the
    warning names the paid editions instead of guessing one.
    Side effects: none.
    """
    if may_be_billable(op_type, params, edition="enterprise"):
        return BILLABLE_WARNING
    return None


def setting_values(params: dict[str, Any]) -> dict[str, Any]:
    """``res.config.settings`` create values for ``setting.set``.

    Inputs: op params with ``key`` (a settings field name) and ``value``.
    Outputs: ``{key: value}``.
    Side effects: none. Raises ``ValueError`` when the key is not a field
    name, the value is missing, or the value is not a scalar or ``None``.
    """
    key = params.get("key")
    if not isinstance(key, str) or not _FIELD_NAME.match(key.strip()):
        raise ValueError("setting.set key must be a res.config.settings field name")
    if "value" not in params:
        raise ValueError("setting.set requires a value")
    value = params.get("value")
    if value is not None and not isinstance(value, _SCALAR):
        raise ValueError("setting.set value must be a scalar")
    return {key.strip(): value}


def config_param_args(params: dict[str, Any]) -> list[str]:
    """``ir.config_parameter.set_param`` args for ``config_param.set``.

    Inputs: op params with ``key`` and ``value``.
    Outputs: ``[key, str(value)]``.
    Side effects: none. Raises ``ValueError`` for a missing key, a ``None``
    or ``False`` value (``set_param`` deletes the row for those), or a value
    that is not a scalar.
    """
    key = params.get("key")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("missing key")
    value = params.get("value")
    if value is None or value is False:
        raise ValueError(
            "config_param.set needs a value. An empty value would delete the parameter"
        )
    if not isinstance(value, _SCALAR):
        raise ValueError("config_param.set value must be a scalar")
    return [key.strip(), str(value)]


def company_write(params: dict[str, Any]) -> tuple[list[int], dict[str, Any]]:
    """``res.company`` write ids and values for ``company.update``.

    Inputs: op params. Ids come from ``ids``, ``id``, or ``company_id``.
    Values come from ``values`` when it is a dict, else from the other
    top-level keys.
    Outputs: ``(ids, values)``.
    Side effects: none. Raises ``ValueError`` for no id, no values, or a key
    that is not a field name. R4 fields were already refused by the handler.
    """
    ids = _company_ids(params)
    if not ids:
        raise ValueError("company.update requires a company id")
    raw = params.get("values")
    if isinstance(raw, dict):
        values = dict(raw)
    else:
        values = {key: item for key, item in params.items() if key not in _COMPANY_ID_KEYS}
    if not values:
        raise ValueError("company.update requires values")
    for key in values:
        if not isinstance(key, str) or not _FIELD_NAME.match(key):
            raise ValueError("company.update keys must be res.company field names")
    return ids, values


def module_name(params: dict[str, Any]) -> str:
    """Technical module name for ``module.install`` or ``module.upgrade``.

    Inputs: op params with ``module``.
    Outputs: the stripped technical name.
    Side effects: none. Raises ``ValueError`` when the name is missing or is
    not lowercase letters, digits, and underscores.
    """
    name = params.get("module")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("module name is required")
    name = name.strip()
    if not _MODULE_NAME.match(name):
        raise ValueError("module name must be a technical name")
    return name


def _company_ids(params: dict[str, Any]) -> list[int]:
    raw = params.get("ids")
    if isinstance(raw, list) and raw:
        if any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in raw):
            raise ValueError("company.update requires a company id")
        return list(raw)
    for key in ("id", "company_id"):
        item = params.get(key)
        if isinstance(item, int) and not isinstance(item, bool) and item > 0:
            return [item]
    return []


def install_reversal_warning(op_type: str) -> str | None:
    """Warning that install can be reversed only by uninstall.

    Inputs: op type.
    Outputs: the warning for ``module.install``. ``None`` for every other op.
    Side effects: none. The warning does not refuse the install.
    """
    if op_type == "module.install":
        return INSTALL_REVERSAL_WARNING
    return None


def module_setting(params: dict[str, Any]) -> bool:
    """True when a setting key selects an Odoo module flag.

    Inputs: op params.
    Outputs: True when ``key`` starts with ``module_`` after case folding.
    Side effects: none.
    """
    key = params.get("key")
    if not isinstance(key, str):
        return False
    return _norm(key).startswith("module_")


def protected_config_key(params: dict[str, Any]) -> bool:
    """True when a config param write names a protected key.

    Inputs: op params. The key may be ``params['key']`` or a key inside
    ``params['values']``.
    Outputs: True for a key in ``PROTECTED_CONFIG_KEYS``.
    Side effects: none.
    """
    if _key_is_protected(params.get("key")):
        return True
    values = params.get("values")
    if not isinstance(values, dict):
        return False
    if any(_key_is_protected(key) for key in values):
        return True
    return _key_is_protected(values.get("key"))


def protected_param_issues(params: dict[str, Any]) -> list[str]:
    """Issues for ``config_param.set``.

    Inputs: op params.
    Outputs: ``['protected parameter']`` for a protected key. ``['missing key']``
    when the key is absent. Otherwise an empty list.
    Side effects: none.
    """
    if protected_config_key(params):
        return ["protected parameter"]
    if not params.get("key"):
        return ["missing key"]
    return []


def company_is_r4(params: dict[str, Any]) -> bool:
    """True when a company update touches an R4 accounting control.

    Inputs: op params.
    Outputs: True for a truthy top-level ``lock_date``, any named lock-date
    field, or a fiscal year, currency, or chart of accounts field.
    Side effects: none.
    """
    return bool(
        params.get("lock_date")
        or _has_named_lock(params)
        or _has_kind(params, _FISCAL_KEYS)
        or _has_kind(params, _CURRENCY_KEYS)
        or _has_kind(params, _CHART_KEYS)
    )


def company_update_issues(params: dict[str, Any]) -> list[str]:
    """Issues for ``company.update``.

    Inputs: op params.
    Outputs: one issue per R4 category that is present. A truthy ``lock_date``
    still reports ``lock dates are refused``.
    Side effects: none.
    """
    issues: list[str] = []
    if params.get("lock_date") or _has_named_lock(params):
        issues.append("lock dates are refused")
    if _has_kind(params, _FISCAL_KEYS):
        issues.append("fiscal year changes are refused")
    if _has_kind(params, _CURRENCY_KEYS):
        issues.append("currency changes are refused")
    if _has_kind(params, _CHART_KEYS):
        issues.append("chart of accounts changes are refused")
    return issues


def company_update_refusal(
    params: dict[str, Any],
    *,
    heavy_passed: bool = False,
) -> str | None:
    """Refusal for an R4 company update, before any port call.

    Inputs: op params and whether the change-set already passed the heavy-R4
    gate. Lock dates are a hard stop and stay refused. Fiscal year, currency,
    and chart of accounts stay refused until the heavy gate has passed.
    Outputs: the lock-date refusal when a lock date is present, otherwise the
    fiscal year, currency, or chart refusal when the heavy gate has not
    passed. ``None`` when the update does not touch those controls, or when
    only heavy controls are present and ``heavy_passed`` is True.
    Side effects: none.
    """
    if params.get("lock_date") or _has_named_lock(params):
        return "lock dates are prohibited"
    if heavy_passed:
        return None
    if _has_kind(params, _FISCAL_KEYS):
        return "fiscal year changes are prohibited"
    if _has_kind(params, _CURRENCY_KEYS):
        return "currency changes are prohibited"
    if _has_kind(params, _CHART_KEYS):
        return "chart of accounts changes are prohibited"
    return None


def _key_is_protected(value: Any) -> bool:
    return isinstance(value, str) and value in PROTECTED_CONFIG_KEYS


def _edition(edition: str) -> str:
    return edition.strip().casefold().replace(".", "_").replace("-", "_")


def _norm(value: str) -> str:
    return "_".join(value.strip().casefold().split())


def _is_named_lock(token: str) -> bool:
    if token == "lock_date":
        return False
    return token.endswith("_lock_date")


def _has_named_lock(params: dict[str, Any]) -> bool:
    found = False

    def visit(value: Any, *, top: bool, depth: int) -> None:
        nonlocal found
        if found or depth > _WALK_LIMIT:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(key, str):
                    token = _norm(key)
                    if _is_named_lock(token):
                        found = True
                        return
                    if token == "lock_date" and not top and item:
                        found = True
                        return
                visit(item, top=False, depth=depth + 1)
            return
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and (_is_named_lock(_norm(item)) or _norm(item) == "lock_date"):
                    found = True
                    return
                visit(item, top=False, depth=depth + 1)

    visit(params, top=True, depth=0)
    return found


def _has_kind(params: dict[str, Any], names: frozenset[str]) -> bool:
    found = False

    def visit(value: Any, depth: int) -> None:
        nonlocal found
        if found or depth > _WALK_LIMIT:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(key, str) and _norm(key) in names:
                    found = True
                    return
                visit(item, depth + 1)
            return
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and _norm(item) in names:
                    found = True
                    return
                visit(item, depth + 1)

    visit(params, 0)
    return found
