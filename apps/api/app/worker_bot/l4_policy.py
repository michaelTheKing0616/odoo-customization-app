"""L4 is a checked policy, not an enabled default. Thresholds match the locks file.

GATE-L4-12 lives here too. It does not enable L4 and it does not read eligibility history.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.audit_chain import append_entry
from app.changeset.ops import OP_CATALOG, get_op, op_base_risk
from app.changeset.protected_registry import protection_level
from app.changeset.setting_ops import protected_config_key
from app.rpc_classify import classify_rpc

L4_MIN_APPLIES = 200
L4_MIN_DAYS = 60
L4_MAX_ROLLBACK = 0.01
L4_MAX_BLAST = 50
L4_ALLOWED_RISKS = frozenset({"R0", "R1"})

# GATE-L4-01. Reasons are fixed tokens. They are not a runtime level and they
# do not carry op params, so a secret in a payload cannot land in a log line.
GATE_L4_01 = "GATE-L4-01"
GATE_L4_03 = "GATE-L4-03"
L4_NOT_ON_ALLOW_LIST = "not_on_allow_list"
L4_BASE_RISK = "base_risk"
L4_R2_DDL = "r2_ddl"
L4_PROTECTED = "protected"
L4_OUTBOUND = "outbound"

_OUTBOUND_WALK_LIMIT = 8
_OUTBOUND_ACTION_TOKENS = frozenset({"email", "sms", "webhook", "mail_post", "outbound", "mass"})
_OUTBOUND_LABELS = (
    "state",
    "action",
    "action_type",
    "action_kind",
    "kind",
    "trigger",
    "scope",
    "mode",
)
_OUTBOUND_BOOL_KEYS = frozenset({"email", "sms", "webhook", "outbound", "mass"})
_OUTBOUND_NESTED_KEYS = ("actions", "action", "safe_actions", "action_server_ids")


def l4_eligible(*, applies: int, days: int, rollback_rate: float, verify_failures: int) -> bool:
    return (
        applies >= L4_MIN_APPLIES
        and days >= L4_MIN_DAYS
        and rollback_rate <= L4_MAX_ROLLBACK
        and verify_failures == 0
    )


def _rpc_shape(
    *,
    op_type: str,
    model: str,
    method: str,
    params: dict[str, Any] | None,
) -> tuple[str, str, dict[str, Any] | None]:
    body = params if isinstance(params, dict) else {}
    rpc_model = model or (body.get("model") if isinstance(body.get("model"), str) else "")
    rpc_method = method
    values: dict[str, Any] | None = None
    if op_type == "user.unlink":
        rpc_model = rpc_model or "res.users"
        rpc_method = rpc_method or "unlink"
    elif op_type == "data.unlink" or op_type.endswith(".unlink"):
        rpc_method = rpc_method or "unlink"
    elif op_type == "config_param.set":
        rpc_model = rpc_model or "ir.config_parameter"
        rpc_method = rpc_method or "write"
        inferred: dict[str, Any] = {}
        key = body.get("key")
        if isinstance(key, str):
            inferred["key"] = key
        if "value" in body:
            inferred["value"] = body.get("value")
        extra = body.get("values")
        if isinstance(extra, dict):
            inferred.update(extra)
        values = inferred or None
    if rpc_model == "res.users.apikeys" and not rpc_method:
        rpc_method = "write"
    return rpc_model, rpc_method, values


def _never_allowed_rpc(
    *,
    op_type: str,
    model: str,
    method: str,
    values: dict[str, Any] | None,
    args: tuple[Any, ...] | list[Any] | None,
    params: dict[str, Any] | None,
) -> bool:
    """Same never-allowed check as classify_rpc. Approval and allow-lists cannot clear it."""
    rpc_model, rpc_method, inferred_values = _rpc_shape(
        op_type=op_type,
        model=model,
        method=method,
        params=params,
    )
    use_values = values if values is not None else inferred_values
    if rpc_model and rpc_method:
        return classify_rpc(
            rpc_model,
            rpc_method,
            values=use_values,
            args=args,
        ).forbidden
    if use_values or args is not None:
        return classify_rpc(
            "ir.config_parameter",
            "set_param" if args is not None else "write",
            values=use_values,
            args=args,
        ).forbidden
    return False


def _action_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip().casefold()
    if not token:
        return None
    return token


def _params_are_outbound(params: Mapping[str, Any], depth: int = 0) -> bool:
    """True when the params name an email, SMS, webhook, outbound, or mass action.

    Inputs: one params mapping and the current walk depth.
    Outputs: whether this mapping, or an action nested under ``actions``,
    ``action``, ``safe_actions``, or ``action_server_ids``, is an outbound
    action. ``action_server_ids`` may be action dicts or Odoo command triples
    ``(0, 0, vals)``. A string stored on another key, such as a partner email
    address, is not an action.
    Side effects: none.
    """
    if depth > _OUTBOUND_WALK_LIMIT:
        return False
    for key in _OUTBOUND_BOOL_KEYS:
        if params.get(key) is True:
            return True
    for key in _OUTBOUND_LABELS:
        token = _action_token(params.get(key))
        if token in _OUTBOUND_ACTION_TOKENS:
            return True
    for key in _OUTBOUND_NESTED_KEYS:
        if _nested_is_outbound(params.get(key), depth):
            return True
    return False


def _nested_is_outbound(value: Any, depth: int) -> bool:
    """True when a nested action value names an outbound action.

    Inputs: one nested value and the depth of the mapping that held it.
    Outputs: whether a mapping, a token string, a list or tuple of those, or
    an Odoo command whose vals mapping is outbound. Integers and other
    scalars are not actions.
    Side effects: none.
    """
    if isinstance(value, Mapping):
        return _params_are_outbound(value, depth + 1)
    token = _action_token(value)
    if token in _OUTBOUND_ACTION_TOKENS:
        return True
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if depth + 1 > _OUTBOUND_WALK_LIMIT:
            return False
        for item in value:
            if _nested_is_outbound(item, depth + 1):
                return True
    return False


def _op_is_protected(op_type: str, params: dict[str, Any]) -> bool:
    """True when the op is protected:deny, protected:elevate, or a protected config key.

    Inputs: catalog op type and its params.
    Outputs: whether GATE-L4-01 must treat the op as protected.
    Side effects: none. This reads the protected registry and does not record a detection.
    """
    if op_type == "config_param.set" and protected_config_key(params):
        return True
    level = protection_level({"type": op_type, "params": params})
    return level in {"deny", "elevate"}


_MODULE_APPLY_OPS = frozenset({"module.install", "module.upgrade", "module.uninstall"})


def _is_promote_op(op_type: str) -> bool:
    """True when the op type is a module promote.

    Inputs: the op type string.
    Outputs: whether it is ``promote`` or ends with ``.promote``.
    Side effects: none.
    """
    token = op_type.strip()
    return token == "promote" or token.endswith(".promote")


def _l4_gate_02_refuses(
    *,
    risk: str,
    op_type: str,
    params: dict[str, Any] | None,
) -> bool:
    """GATE-L4-02. An allow-list does not clear these five.

    Inputs: caller risk, op type, and optional params.
    Outputs: True when the caller risk or the catalog base risk is R3 or R4,
    the target is ``protected:elevate``, the op is ``module.install``,
    ``module.upgrade``, or ``module.uninstall``, or the op is a promote.
    Side effects: none. Does not enable L4 and does not record a detection.
    """
    if risk in {"R3", "R4"}:
        return True
    token = op_type.strip()
    if token.startswith("module.") or token in _MODULE_APPLY_OPS:
        return True
    if _is_promote_op(token):
        return True
    body = params if isinstance(params, dict) else {}
    if op_base_risk(token, body) in {"R3", "R4"}:
        return True
    return protection_level({"type": token, "params": body}) == "elevate"


def l4_gate_01_refusal(
    *,
    op_type: str,
    params: dict[str, Any] | None = None,
    allow_list: Collection[str] | None = None,
) -> str | None:
    """GATE-L4-01 allow-list content check.

    Inputs: an op type, optional params, and the tenant allow-list when one is in play.
    ``AllowListRegistry`` is the in-memory ``l4_allow_list(tenant, op_type)`` table.
    Outputs: None when the op may pass this gate. Otherwise ``not_on_allow_list``,
    ``base_risk``, ``r2_ddl``, ``protected``, or ``outbound``. Base risk must be R1,
    or R2 whose catalog ``ddl`` flag is false, that is not protected, and that is
    not an outbound action. An email action on ``automation.create`` is outbound.
    A missing allow-list skips the membership check. A provided list refuses an
    op type that is absent from it.
    Side effects: none. Does not enable L4, does not read eligibility history,
    and does not write an audit row or a customer database.
    """
    if allow_list is not None and op_type not in allow_list:
        return L4_NOT_ON_ALLOW_LIST
    body = params if isinstance(params, dict) else {}
    entry = get_op(op_type)
    base = op_base_risk(op_type, body)
    if base in L4_ALLOWED_RISKS:
        return None
    if entry is None or base != "R2":
        return L4_BASE_RISK
    if entry.ddl:
        return L4_R2_DDL
    if _op_is_protected(op_type, body):
        return L4_PROTECTED
    if _params_are_outbound(body):
        return L4_OUTBOUND
    return None


# Executor plan hashes are sha256 hex, 16 characters, lowercase.
_PLAN_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


@dataclass(frozen=True, slots=True)
class StagingApplyRecord:
    """One staging apply of a plan hash.

    ``verified`` is true only when that apply's verification passed.
    Holding a record does not enable L4.
    """

    plan_hash: str
    verified: bool
    environment: str = "staging"


def _plan_hash_token(value: Any) -> str | None:
    """Lowercase 16-hex plan hash, or None when the value is not one.

    Inputs: a candidate hash.
    Outputs: the stripped hash when it matches the executor fingerprint shape.
    Side effects: none.
    """
    if not isinstance(value, str):
        return None
    token = value.strip()
    if _PLAN_HASH_RE.fullmatch(token):
        return token
    return None


def _resolved_plan_mode(*, plan_mode: str, mode_t: bool) -> str:
    """Executor mode for GATE-L4-03.

    Inputs: an explicit plan mode and the Mode T boolean.
    Outputs: ``T`` or ``C``. An explicit ``T`` or ``C`` wins. Otherwise the
    boolean maps true to ``T`` and false to ``C``.
    Side effects: none.
    """
    token = plan_mode.strip().upper()
    if token in {"T", "C"}:
        return token
    return "T" if mode_t else "C"


def _staging_apply_view(record: Any) -> tuple[str, bool, str] | None:
    """Plan hash, verified flag, and environment from one staging apply record.

    Inputs: a ``StagingApplyRecord`` or a mapping with ``plan_hash`` and ``verified``.
    Outputs: the three fields when the hash is a plan hash and the environment
    is a string. ``verified`` is true only for the boolean ``True``. A mapping
    that omits ``environment`` is staging.
    Side effects: none.
    """
    if isinstance(record, StagingApplyRecord):
        plan_hash = _plan_hash_token(record.plan_hash)
        if plan_hash is None:
            return None
        return plan_hash, record.verified is True, record.environment.strip().casefold()
    if not isinstance(record, Mapping):
        return None
    plan_hash = _plan_hash_token(record.get("plan_hash"))
    if plan_hash is None:
        return None
    environment = record.get("environment", "staging")
    if not isinstance(environment, str):
        return None
    return plan_hash, record.get("verified") is True, environment.strip().casefold()


def l4_gate_03_allows(
    *,
    mode: str,
    plan_hash: str,
    staging_applies: Sequence[StagingApplyRecord | Mapping[str, Any]],
) -> bool:
    """GATE-L4-03. Mode T, and the same plan hash verified on staging.

    Inputs: the plan's executor mode (``T`` or ``C``), the production plan hash,
    and staging apply records.
    Outputs: True only when the mode is T and one staging record has that hash
    with ``verified`` true. Mode C is False. A matching hash whose verification
    failed is False. A verified record for a different hash is False. A record
    whose environment is not staging does not count.
    Side effects: none. Does not enable L4, does not read eligibility history,
    and does not write an audit row.
    """
    if mode.strip().upper() != "T":
        return False
    token = _plan_hash_token(plan_hash)
    if token is None:
        return False
    if isinstance(staging_applies, (str, bytes)) or not isinstance(staging_applies, Sequence):
        return False
    for record in staging_applies:
        view = _staging_apply_view(record)
        if view is None:
            continue
        stored_hash, verified, environment = view
        if environment != "staging":
            continue
        if stored_hash != token or not verified:
            continue
        return True
    return False


def l4_may_apply(
    *,
    risk: str,
    op_type: str,
    rows: int,
    mode_t: bool,
    staging_verified: bool,
    model: str = "",
    method: str = "",
    values: dict[str, Any] | None = None,
    args: tuple[Any, ...] | list[Any] | None = None,
    params: dict[str, Any] | None = None,
    allow_list: Collection[str] | None = None,
    plan_mode: str = "",
    plan_hash: str = "",
    staging_applies: Sequence[StagingApplyRecord | Mapping[str, Any]] | None = None,
    environment: str = "",
) -> bool:
    """Whether this op would pass the L4 policy checks that exist today.

    Inputs: caller risk, op type, blast count, Mode T, staging verification,
    optional RPC shape, an optional tenant allow-list, the plan mode, the plan
    hash, staging apply records, and the target environment. The environment
    does not waive the staging-record check.
    Outputs: False when never-allowed, Mode T, staging, caller risk above R2,
    GATE-L4-01, GATE-L4-02, GATE-L4-03, module ops, or the blast cap refuse the
    op. True only when every check passes, including GATE-L4-03: the plan mode
    is T and a staging apply record has the same plan hash with ``verified``
    true. ``mode_t`` and ``staging_verified`` do not admit a call that has no
    such record. R2 passes GATE-L4-01 only when the catalog op is non-DDL, not
    protected, and not outbound.
    GATE-L4-02 still refuses R3, R4, ``protected:elevate``, module install,
    upgrade, and uninstall, and promote when an earlier check would have
    allowed them. An allow-list does not clear that refusal.
    Side effects: none. Does not enable L4 and does not apply the op.
    """
    if _never_allowed_rpc(
        op_type=op_type,
        model=model,
        method=method,
        values=values,
        args=args,
        params=params,
    ):
        return False
    if not mode_t or not staging_verified:
        return False
    if risk not in L4_ALLOWED_RISKS and risk != "R2":
        return False
    if op_type.startswith("module.") or op_type in {"data.delete", "module.uninstall"}:
        return False
    if rows > L4_MAX_BLAST:
        return False
    if allow_list is not None and op_type not in allow_list:
        return False
    if l4_gate_01_refusal(op_type=op_type, params=params, allow_list=allow_list) is not None:
        return False
    # GATE-L4-02. Runs after the allow-list membership check so a listed op
    # still cannot be R3, R4, protected:elevate, a module install/upgrade/
    # uninstall, or a promote.
    if _l4_gate_02_refuses(risk=risk, op_type=op_type, params=params):
        return False
    # GATE-L4-03. The only allow path needs Mode T and a staging apply of this
    # plan hash with verified true. Caller flags do not stand in for that record.
    if not l4_gate_03_allows(
        mode=_resolved_plan_mode(plan_mode=plan_mode, mode_t=mode_t),
        plan_hash=plan_hash,
        staging_applies=() if staging_applies is None else staging_applies,
    ):
        return False
    return True


# GATE-L4-12. Human admins may record. Bots and templates cannot widen the list.
HUMAN_ADMIN_ROLES = frozenset({"admin", "owner"})
BOT_AUDIT_ACTOR = "worker_bot"
GATE_L4_12 = "GATE-L4-12"
L4_ALLOW_LIST_REFUSED = "l4_allow_list_refused"

_ALLOW_LIST_EDIT_TOOLS = frozenset(
    {
        "l4.allow_list.add",
        "l4.allow_list.grant",
        "allow_list.add",
        "allow_list.grant",
    }
)
_ALLOW_LIST_MUTATION_TYPES = frozenset(
    {
        "l4_allow_list.add",
        "l4_allow_list.grant",
        "allow_list.add",
        "allow_list.grant",
    }
)
_GRANT_ARG_KEYS = frozenset(
    {
        "allow_list_add",
        "grant_op",
        "add_to_allow_list",
        "allow_list_op",
    }
)
_TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
# Same API-key shape the log scrubber drops. It also matches the tenant id pattern.
_SECRET_SHAPED_RE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
# A short slug such as "acme" stays on the note. Hex-only and token-character
# values of this length are opaque and must be stored as unlisted.
_OPAQUE_TENANT_MIN_LENGTH = 32
_HEX_ONLY_RE = re.compile(rf"^[0-9a-f]{{{_OPAQUE_TENANT_MIN_LENGTH},}}$")
_TOKEN_CHARS_RE = re.compile(rf"^[a-z0-9_-]{{{_OPAQUE_TENANT_MIN_LENGTH},}}$")
_RUN_ID_RE = re.compile(r"^bot-run-[a-z0-9]{1,32}$")


@dataclass(frozen=True, slots=True)
class AllowListGrantResult:
    """Outcome of one allow-list write attempt.

    ``recorded`` is true only after a human admin write.
    ``auto_applied`` stays false. A bot or template attempt does not change the list.
    """

    recorded: bool
    auto_applied: bool
    refused: bool
    reason: str


class AllowListRegistry:
    """In-process tenant allow-list. Not a customer database and not an L4 enablement."""

    def __init__(self) -> None:
        self._by_tenant: dict[str, set[str]] = {}

    def ops(self, tenant: str) -> frozenset[str]:
        """Ops recorded for one tenant. Empty when the tenant has no human grant."""
        return frozenset(self._by_tenant.get(tenant, ()))

    def _remember(self, tenant: str, op_type: str) -> None:
        current = self._by_tenant.get(tenant)
        if current is None:
            self._by_tenant[tenant] = {op_type}
            return
        current.add(op_type)


def _refused(reason: str) -> AllowListGrantResult:
    return AllowListGrantResult(
        recorded=False,
        auto_applied=False,
        refused=True,
        reason=reason,
    )


def _audit_tenant(tenant: str) -> str:
    """Tenant label safe to store on the refusal note.

    Inputs: the raw tenant string from the refused tool call.
    Outputs: the slug when it is a short human id, otherwise ``unlisted``.
    Side effects: none. A secret-shaped value, a hex-only value of 32 or more
    characters, or a token-character value of 32 or more characters is not returned.
    """
    token = tenant.strip()
    if _SECRET_SHAPED_RE.search(token):
        return "unlisted"
    if _HEX_ONLY_RE.fullmatch(token) or _TOKEN_CHARS_RE.fullmatch(token):
        return "unlisted"
    if _TENANT_RE.fullmatch(token):
        return token
    return "unlisted"


def _audit_op_type(op_type: str) -> str:
    token = op_type.strip()
    if token in OP_CATALOG:
        return token
    return "unlisted"


def _audit_tool(tool_name: str) -> str:
    if tool_name in _ALLOW_LIST_EDIT_TOOLS:
        return tool_name
    return "unlisted"


def _audit_run_id(run_id: str | None) -> str | None:
    if run_id is None:
        return None
    token = run_id.strip()
    if _RUN_ID_RE.fullmatch(token):
        return token
    return None


def is_allow_list_edit_tool(
    tool_name: str,
    tool_args: Mapping[str, Any] | None = None,
) -> bool:
    """True when a tool call is an allow-list write.

    Inputs: the tool name and its argument mapping.
    Outputs: whether GATE-L4-12 must refuse the call.
    Side effects: none. Argument values are not read.
    """
    if tool_name in _ALLOW_LIST_EDIT_TOOLS:
        return True
    if isinstance(tool_args, Mapping) and _GRANT_ARG_KEYS.intersection(tool_args):
        return True
    return False


def record_allow_list_change(
    registry: AllowListRegistry,
    *,
    role: str,
    tenant: str,
    op_type: str,
    admin_id: str,
) -> AllowListGrantResult:
    """Record one op on a tenant allow-list for a human admin.

    Inputs: registry, workspace role, tenant, catalog op type, and the admin id.
    Outputs: ``recorded`` when the role is admin or owner and the op is in the catalog.
    Side effects: adds the op to ``registry`` only on success. Does not write an audit
    row, does not call Odoo, and does not enable L4.
    """
    if role not in HUMAN_ADMIN_ROLES:
        return _refused("human_admin_required")
    if not isinstance(admin_id, str) or not admin_id.strip():
        return _refused("human_admin_required")
    tenant_token = tenant.strip()
    if not _TENANT_RE.fullmatch(tenant_token):
        return _refused("invalid_tenant")
    op_token = op_type.strip()
    if op_token not in OP_CATALOG:
        return _refused("op_not_in_catalog")
    registry._remember(tenant_token, op_token)
    return AllowListGrantResult(
        recorded=True,
        auto_applied=False,
        refused=False,
        reason="recorded",
    )


def refuse_bot_allow_list_tool_call(
    db: Session,
    registry: AllowListRegistry,
    *,
    actor: str,
    tenant: str,
    op_type: str,
    tool_name: str,
    run_id: str | None = None,
    tool_args: Mapping[str, Any] | None = None,
) -> AllowListGrantResult:
    """Refuse a bot tool call that would edit the allow-list, and audit the refusal.

    Inputs: an audit session, the allow-list registry, bot actor, tenant, requested
    op, tool name, optional run id, and the raw tool arguments.
    Outputs: a refused result. ``recorded`` and ``auto_applied`` are false.
    Side effects: appends one ``note`` row on the audit chain. The payload is a fixed
    set of fields. ``tool_args`` and ``actor`` are not copied into that payload.
    A tenant that looks like a secret, or an opaque hex or token value of 32
    characters or more, is stored as ``unlisted``. A short slug is kept.
    Does not change ``registry`` and does not enable L4.
    """
    if not isinstance(registry, AllowListRegistry):
        raise TypeError("registry must be an AllowListRegistry")
    if not isinstance(actor, str):
        raise TypeError("actor must be a string")
    if tool_args is not None and not isinstance(tool_args, Mapping):
        raise TypeError("tool_args must be a mapping when provided")
    payload = {
        "gate": GATE_L4_12,
        "event": L4_ALLOW_LIST_REFUSED,
        "actor_kind": "bot",
        "tenant": _audit_tenant(tenant),
        "op_type": _audit_op_type(op_type),
        "tool": _audit_tool(tool_name),
    }
    append_entry(
        db,
        actor=BOT_AUDIT_ACTOR,
        kind="note",
        payload=payload,
        run_id=_audit_run_id(run_id),
    )
    return _refused("bot_cannot_widen_allow_list")


def _template_adds_allow_list_op(op: Mapping[str, Any]) -> bool:
    op_type = op.get("type")
    if isinstance(op_type, str) and op_type.strip() in _ALLOW_LIST_MUTATION_TYPES:
        return True
    params = op.get("params")
    if isinstance(params, Mapping) and _GRANT_ARG_KEYS.intersection(params):
        return True
    return False


def template_allow_list_change(
    registry: AllowListRegistry,
    changeset: Sequence[Mapping[str, Any]],
    *,
    tenant: str,
) -> AllowListGrantResult:
    """A template that adds an op to the allow-list is not auto-applied.

    Inputs: the registry, the template changeset, and the tenant the template names.
    Outputs: refused when any op would widen the allow-list. Otherwise no edit.
    Side effects: none. ``registry`` is not modified. ``tenant`` is unused on purpose
    so a template cannot select a list to write. Does not write an audit row and
    does not enable L4.
    """
    if not isinstance(registry, AllowListRegistry):
        raise TypeError("registry must be an AllowListRegistry")
    if not isinstance(tenant, str):
        raise TypeError("tenant must be a string")
    if not isinstance(changeset, Sequence) or isinstance(changeset, (str, bytes)):
        return _refused("invalid_template")
    for op in changeset:
        if isinstance(op, Mapping) and _template_adds_allow_list_op(op):
            return _refused("template_not_auto_applied")
    return AllowListGrantResult(
        recorded=False,
        auto_applied=False,
        refused=False,
        reason="no_allow_list_edit",
    )
