"""Logic-family risk raises and the RT-25 safe_eval gate.

The catalog in ``ops.py`` stays the source for base risk. This module raises
that base for the logic rules and rejects the RT-25 patterns named in the
engine spec: obfuscated imports, ``__class__``, ``__globals__``, getattr
chains, and bombs. It also builds the allowlisted public ORM values the
existing change-set dispatcher sends for the logic family. It does not
execute the snippet and it does not call Odoo.
"""

from __future__ import annotations

import ast
import dis
import types
from typing import Any

OBFUSCATED_IMPORT = "safe_eval rejected an obfuscated import"
DUNDER_CLASS = "safe_eval rejected __class__"
DUNDER_GLOBALS = "safe_eval rejected __globals__"
GETATTR_CHAIN = "safe_eval rejected a getattr chain"
BOMB = "safe_eval rejected a bomb"

_REASON_ORDER = (
    OBFUSCATED_IMPORT,
    DUNDER_CLASS,
    DUNDER_GLOBALS,
    GETATTR_CHAIN,
    BOMB,
)
_CHANNELS = frozenset({"code", "email", "sms", "webhook"})
_SERVER_ACTIONS = frozenset({"server_action.create", "server_action.update"})
_AUTOMATIONS = frozenset(
    {"automation.create", "automation.update", "automation.disable"}
)
_SEQUENCES = frozenset({"sequence.create", "sequence.update"})
_SEQUENCE_WORDS = frozenset({"accounting", "journal", "legal"})
_SEQUENCE_LABELS = ("kind", "use", "purpose", "sequence_type", "category")
_OUTBOUND_LABELS = ("kind", "trigger", "action", "scope", "mode")
_CODE_KEYS = frozenset({"code", "python_code"})
_DUNDERS = frozenset({"__import__", "__class__", "__globals__"})
_DUNDER_REASON = {
    "__import__": OBFUSCATED_IMPORT,
    "__class__": DUNDER_CLASS,
    "__globals__": DUNDER_GLOBALS,
}
# A single power is a bomb at this exponent. A tower is a bomb when the inner
# power is at least this large. A string or sequence repeat is a bomb at this
# count. Smaller powers and repeats stay allowed.
_SINGLE_EXPONENT = 1024
_TOWER_INNER = 256
_REPEAT = 100_000
_FOLD_LIMIT = 80
_SNIPPET_DEPTH = 8


def logic_base_raise(op_type: str, params: dict[str, Any] | None) -> str | None:
    """Catalog raise for a logic op, before policy bumps.

    Inputs: op type and params. A missing params dict is treated as empty.
    Outputs: ``R3`` or ``R4`` when a logic rule raises the catalog base,
    otherwise ``None``. Server-action code, email, SMS, and webhook are
    ``R3``. Outbound or mass automation is ``R3``. An accounting, journal,
    or legal sequence is ``R4``. Cron stays on its catalog base.
    Side effects: none.
    """
    body = params if isinstance(params, dict) else {}
    if op_type in _SERVER_ACTIONS and _server_action_channel(body):
        return "R3"
    if op_type in _AUTOMATIONS and _outbound_or_mass(body):
        return "R3"
    if op_type in _SEQUENCES and _sensitive_sequence(body):
        return "R4"
    return None


def safe_eval_ast_issues(source: str) -> list[str]:
    """RT-25 reasons found by walking the snippet AST.

    Inputs: Python source. Empty or unparsable source has no RT-25 reason.
    Outputs: the named reasons, in a stable order, with no duplicates.
    Side effects: none. Does not compile or execute the source.
    """
    tree = _parse(source)
    if tree is None:
        return []
    return _order(_ast_reasons(tree))


def safe_eval_sandbox_issues(source: str) -> list[str]:
    """RT-25 reasons from the AST gate plus bytecode. Never executes.

    Inputs: Python source.
    Outputs: the same named reasons. A bomb is refused before ``compile``.
    Other snippets are compiled and scanned for import opcodes and the
    named dunder strings. The code object is not executed.
    Side effects: none.
    """
    tree = _parse(source)
    if tree is None:
        return []
    reasons = _ast_reasons(tree)
    if BOMB in reasons:
        return _order(reasons)
    try:
        compiled = compile(tree, "<safe_eval>", "exec")
    except (SyntaxError, ValueError, OverflowError, MemoryError):
        return _order(reasons)
    reasons.update(_bytecode_reasons(compiled))
    return _order(reasons)


def safe_eval_issues(source: str) -> list[str]:
    """Union of the AST and sandbox RT-25 reasons.

    Inputs: Python source.
    Outputs: the named reasons. Empty when both layers accept the snippet.
    Side effects: none. Does not execute the source.
    """
    return _order(set(safe_eval_ast_issues(source)) | set(safe_eval_sandbox_issues(source)))


def safe_eval_issues_in_params(params: dict[str, Any]) -> list[str]:
    """RT-25 reasons in ``code`` and ``python_code`` values.

    Inputs: op params. Nested dicts and lists are walked. Other keys are not
    treated as Python.
    Outputs: the named reasons for every snippet, with no duplicates.
    Side effects: none.
    """
    found: list[str] = []
    for snippet in _snippets(params):
        for item in safe_eval_issues(snippet):
            if item not in found:
                found.append(item)
    return found


def _server_action_channel(params: dict[str, Any]) -> bool:
    for key in ("state", "action_type"):
        value = params.get(key)
        if isinstance(value, str) and value.strip().casefold() in _CHANNELS:
            return True
    for key in _CHANNELS:
        if params.get(key):
            return True
    return False


def _outbound_or_mass(params: dict[str, Any], depth: int = 0) -> bool:
    if depth > _SNIPPET_DEPTH:
        return False
    if params.get("outbound") or params.get("mass"):
        return True
    for key in _OUTBOUND_LABELS:
        value = params.get(key)
        if isinstance(value, str) and value.strip().casefold() in {"outbound", "mass"}:
            return True
    actions = params.get("actions")
    if isinstance(actions, list):
        for item in actions:
            if isinstance(item, dict) and _outbound_or_mass(item, depth + 1):
                return True
    return False


def sensitive_sequence(params: dict[str, Any] | None) -> bool:
    """True when a sequence op is accounting, journal, or legal.

    Inputs: op params. A missing dict is empty.
    Outputs: True when an accounting, journal, or legal marker is set.
    Side effects: none.
    """
    body = params if isinstance(params, dict) else {}
    return _sensitive_sequence(body)


def _sensitive_sequence(params: dict[str, Any]) -> bool:
    for key in _SEQUENCE_WORDS:
        if params.get(key):
            return True
    for key in _SEQUENCE_LABELS:
        value = params.get(key)
        if isinstance(value, str) and value.strip().casefold() in _SEQUENCE_WORDS:
            return True
    return False


def _parse(source: str) -> ast.AST | None:
    if not isinstance(source, str) or not source.strip():
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _order(reasons: set[str]) -> list[str]:
    return [reason for reason in _REASON_ORDER if reason in reasons]


def _ast_reasons(tree: ast.AST) -> set[str]:
    reasons: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            reasons.add(OBFUSCATED_IMPORT)
        elif isinstance(node, ast.Name) and node.id in _DUNDERS:
            reasons.add(_DUNDER_REASON[node.id])
        elif isinstance(node, ast.Attribute) and node.attr in _DUNDERS:
            reasons.add(_DUNDER_REASON[node.attr])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            reason = _DUNDER_REASON.get(node.value)
            if reason is not None:
                reasons.add(reason)
        else:
            folded = _folded_str(node)
            if folded in _DUNDER_REASON:
                reasons.add(_DUNDER_REASON[folded])
        if _is_getattr_chain(node):
            reasons.add(GETATTR_CHAIN)
        if _is_bomb(node):
            reasons.add(BOMB)
    return reasons


def _is_getattr_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "getattr"
    if isinstance(func, ast.Attribute):
        return func.attr == "getattr"
    return False


def _is_getattr_chain(node: ast.AST) -> bool:
    """True when this getattr call contains another getattr call."""
    if not _is_getattr_call(node):
        return False
    for child in ast.walk(node):
        if child is not node and _is_getattr_call(child):
            return True
    return False


def _folded_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value if len(node.value) <= _FOLD_LIMIT else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _folded_str(node.left)
        right = _folded_str(node.right)
        if left is None or right is None:
            return None
        if len(left) + len(right) > _FOLD_LIMIT:
            return None
        return left + right
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return None
            parts.append(value.value)
        folded = "".join(parts)
        return folded if len(folded) <= _FOLD_LIMIT else None
    return None


def _static_int(node: ast.AST) -> int | None:
    """Small static int, or None when the node is not a safe constant."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _static_int(node.operand)
        if inner is not None:
            return -inner
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
        if _is_power_tower(node):
            return None
        base = _static_int(node.left)
        exp = _static_int(node.right)
        if (
            base is None
            or exp is None
            or exp < 0
            or exp > 12
            or abs(base) > 1000
        ):
            return None
        return base**exp
    return None


def _is_power_tower(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Pow)
        and isinstance(node.right, ast.BinOp)
        and isinstance(node.right.op, ast.Pow)
    )


def _is_bomb(node: ast.AST) -> bool:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
        exp = _static_int(node.right)
        if exp is not None and exp >= _SINGLE_EXPONENT:
            return True
        if _is_power_tower(node):
            inner = _static_int(node.right)
            if inner is None or inner >= _TOWER_INNER:
                return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _repeat_bomb(node.left, node.right) or _repeat_bomb(node.right, node.left)
    return False


def _is_sequence_literal(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
        return True
    return _folded_str(node) is not None and isinstance(node, (ast.BinOp, ast.JoinedStr))


def _repeat_bomb(seq: ast.AST, count: ast.AST) -> bool:
    if not _is_sequence_literal(seq):
        return False
    if _is_bomb(count):
        return True
    size = _static_int(count)
    return size is not None and size >= _REPEAT


def _bytecode_reasons(code: types.CodeType) -> set[str]:
    reasons: set[str] = set()
    pending = [code]
    while pending:
        current = pending.pop()
        for name in current.co_names:
            reason = _DUNDER_REASON.get(name)
            if reason is not None:
                reasons.add(reason)
        for const in current.co_consts:
            if isinstance(const, str):
                reason = _DUNDER_REASON.get(const)
                if reason is not None:
                    reasons.add(reason)
            elif isinstance(const, types.CodeType):
                pending.append(const)
        for instr in dis.get_instructions(current):
            if instr.opname in {"IMPORT_NAME", "IMPORT_FROM"}:
                reasons.add(OBFUSCATED_IMPORT)
    return reasons


LOGIC_OP_TYPES: tuple[str, ...] = (
    "server_action.create",
    "server_action.update",
    "automation.create",
    "automation.update",
    "automation.disable",
    "cron.create",
    "cron.update",
    "cron.disable",
    "sequence.create",
    "sequence.update",
    "mail_template.create",
    "mail_template.update",
    "activity_type.create",
    "activity_type.update",
    "stage.upsert",
    "stage.reorder",
    "stage.archive",
    "config_record.upsert",
)

STAGE_MODEL_REQUIRED = "stage ops need a stage model"
MODEL_REQUIRED = "model is required"
STAGE_SEQUENCE_STEP = 10

_LOGIC_TARGETS: dict[str, str] = {
    "server_action": "ir.actions.server",
    "automation": "base.automation",
    "cron": "ir.cron",
    "sequence": "ir.sequence",
    "mail_template": "mail.template",
    "activity_type": "mail.activity.type",
}
_LOGIC_WRITE_OPS = frozenset(
    {
        "server_action.update",
        "automation.update",
        "automation.disable",
        "cron.update",
        "cron.disable",
        "sequence.update",
        "mail_template.update",
        "activity_type.update",
        "stage.reorder",
        "stage.archive",
    }
)
_DISABLE_OPS = frozenset({"automation.disable", "cron.disable", "stage.archive"})
_NEEDS_MODEL = frozenset({"server_action.create", "automation.create", "cron.create"})
# Public fields copied from params. Anything else in params is not written.
_LOGIC_KEYS: dict[str, tuple[str, ...]] = {
    "server_action": ("name", "state", "code", "sequence"),
    "automation": ("name", "trigger", "filter_domain", "filter_pre_domain", "active"),
    "cron": (
        "name",
        "state",
        "code",
        "interval_number",
        "interval_type",
        "nextcall",
        "priority",
        "active",
    ),
    "sequence": (
        "name",
        "code",
        "prefix",
        "suffix",
        "padding",
        "number_increment",
        "number_next",
        "implementation",
        "active",
    ),
    "mail_template": (
        "name",
        "subject",
        "body_html",
        "email_from",
        "email_to",
        "email_cc",
        "partner_to",
        "reply_to",
        "lang",
        "auto_delete",
    ),
    "activity_type": (
        "name",
        "summary",
        "category",
        "delay_count",
        "delay_unit",
        "icon",
        "sequence",
        "active",
    ),
    "stage": ("name", "sequence", "fold", "active", "description"),
}
_STAGE_MODELS = frozenset({"project.task.type"})


def is_stage_model(model: str) -> bool:
    """True when ``model`` names a stage table the stage ops may write.

    Inputs: a technical model name.
    Outputs: True for ``*.stage``, ``*_stage``, ``project.task.type``, or a
    custom ``x_`` model whose name contains ``stage``. Anything else is False,
    so a stage op cannot become a generic write on another model.
    Side effects: none.
    """
    name = model.strip()
    if not name:
        return False
    if name in _STAGE_MODELS or name.endswith((".stage", "_stage")):
        return True
    return name.startswith("x_") and "stage" in name


def logic_target_model(op_type: str, params: dict[str, Any]) -> str:
    """Public ORM model the executor writes for one logic op.

    Inputs: catalog op type and resolved params. Stage and config_record
    ops read ``model``. Stage defaults to ``project.task.type`` when omitted
    (document choice: CRM/helpdesk stages must name their model explicitly).
    Outputs: ``ir.actions.server``, ``base.automation``, ``ir.cron``,
    ``ir.sequence``, ``mail.template``, ``mail.activity.type``, the stage
    model, or ``params["model"]`` for config_record.
    Side effects: none.
    """
    family = op_type.split(".", 1)[0]
    if family == "stage":
        return str(params.get("model") or "project.task.type").strip()
    if op_type == "config_record.upsert":
        return str(params.get("model") or "").strip()
    return _LOGIC_TARGETS[family]


def logic_write_op(op_type: str) -> bool:
    """True when the op writes existing rows instead of creating one.

    Inputs: catalog op type. ``stage.upsert`` and ``config_record.upsert``
    are neither and are handled by the dispatcher.
    Outputs: True for update, disable, reorder, and archive logic ops.
    Side effects: none.
    """
    return op_type in _LOGIC_WRITE_OPS


def logic_write_ids(params: dict[str, Any]) -> list[int]:
    """Read write ids from logic-op params.

    Inputs: op params. ``ids`` is a list of ints. ``id`` is one int. Bools
    are rejected.
    Outputs: the ids in the given order, or an empty list when none are usable.
    Side effects: none.
    """
    raw = params.get("ids")
    if isinstance(raw, list) and raw:
        ids: list[int] = []
        for item in raw:
            if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
                return []
            ids.append(item)
        return ids
    item = params.get("id")
    if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
        return []
    return [item]


def logic_payload_issues(op_type: str, params: dict[str, Any]) -> list[str]:
    """Payload preconditions the dispatcher checks before any port call.

    Inputs: catalog op type and resolved params.
    Outputs: ``model is required`` for server action, automation, and cron
    create without a model, and for ``config_record.upsert`` without a model.
    ``stage ops need a stage model`` when a stage op targets anything
    ``is_stage_model`` refuses (after the ``project.task.type`` default).
    Otherwise an empty list.
    Side effects: none.
    """
    issues: list[str] = []
    if op_type in _NEEDS_MODEL and not str(params.get("model") or "").strip():
        issues.append(MODEL_REQUIRED)
    if op_type == "config_record.upsert" and not str(params.get("model") or "").strip():
        issues.append(MODEL_REQUIRED)
    if op_type.startswith("stage.") and not is_stage_model(
        str(params.get("model") or "project.task.type")
    ):
        issues.append(STAGE_MODEL_REQUIRED)
    return issues


def logic_values(op_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Public ORM values for one logic op.

    Inputs: catalog type and resolved params. Only the allowlisted public
    fields for the target are copied. ``model`` becomes ``model_id`` (or
    ``res_model`` on activity types). Stage ops also read a ``values`` dict.
    ``config_record.upsert`` copies ``params["values"]`` as-is.
    Outputs: a values dict the existing port can create or write. Disable and
    archive ops write ``active`` false. Cron or server action code with no
    state gets ``state`` code, so the row matches the R3 risk it was gated at.
    Side effects: none. Does not call Odoo.
    """
    if op_type in _DISABLE_OPS:
        return {"active": False}
    if op_type == "config_record.upsert":
        return dict(params.get("values") or {})
    family = op_type.split(".", 1)[0]
    keys = _LOGIC_KEYS[family]
    values: dict[str, Any] = {key: params[key] for key in keys if params.get(key) is not None}
    if family == "stage":
        extra = params.get("values")
        if isinstance(extra, dict):
            for key in keys:
                if extra.get(key) is not None:
                    values[key] = extra[key]
        return values
    model = str(params.get("model") or "").strip()
    if model:
        values["res_model" if family == "activity_type" else "model_id"] = model
    if family in {"server_action", "cron"} and values.get("code") and "state" not in values:
        values["state"] = "code"
    if family == "automation":
        linked = params.get("action_server_ids")
        if isinstance(linked, list) and linked and all(
            isinstance(item, int) and not isinstance(item, bool) for item in linked
        ):
            values["action_server_ids"] = [(6, 0, list(linked))]
    if op_type == "mail_template.create" and "name" not in values:
        values["name"] = "template"
    if not values:
        values["name"] = params.get("name") or op_type
    return values


def stage_reorder_writes(params: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    """One ``sequence`` write per stage id, in the order given.

    Inputs: ``stage.reorder`` params with ``ids`` (or one ``id``).
    Outputs: ``(id, {"sequence": n})`` pairs, stepping by
    ``STAGE_SEQUENCE_STEP`` from the first id. Empty when no id is usable.
    Side effects: none.
    """
    return [
        (stage_id, {"sequence": (index + 1) * STAGE_SEQUENCE_STEP})
        for index, stage_id in enumerate(logic_write_ids(params))
    ]


def _snippets(value: Any, depth: int = 0) -> list[str]:
    if depth > _SNIPPET_DEPTH:
        return []
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _CODE_KEYS and isinstance(item, str) and item.strip():
                if item not in found:
                    found.append(item)
            elif isinstance(item, (dict, list)):
                for snippet in _snippets(item, depth + 1):
                    if snippet not in found:
                        found.append(snippet)
    elif isinstance(value, list):
        for item in value:
            for snippet in _snippets(item, depth + 1):
                if snippet not in found:
                    found.append(snippet)
    return found
