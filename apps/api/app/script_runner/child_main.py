"""DEV-3 / DEV-SR child process — allowlisted imports, no script filesystem or network."""

from __future__ import annotations

import ast
import builtins
import json
import os
import sys
import types
from typing import Any

ALLOWED_IMPORT_ROOTS = frozenset(
    {
        "csv",
        "io",
        "json",
        "datetime",
        "math",
        "re",
        "collections",
        "time",
    }
)

FORBIDDEN_IMPORTS = frozenset(
    {
        "subprocess",
        "socket",
        "urllib",
        "http",
        "ftplib",
        "telnetlib",
        "smtplib",
        "pickle",
        "os",
        "pathlib",
        "shutil",
        "glob",
        "tempfile",
        "requests",
        "httpx",
        "ssl",
        "ctypes",
        "multiprocessing",
        "importlib",
        "builtins",
        "sys",
        "webbrowser",
        "pty",
        "fcntl",
        "asyncio",
    }
)

_REAL_IMPORT = builtins.__import__


def _check_imports(source: str) -> None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _reject_import(alias.name)
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level:
                raise ImportError("Relative imports are not allowed in Script Runner")
            _reject_import(mod)


def _reject_import(name: str) -> None:
    root = (name or "").split(".")[0]
    if root in FORBIDDEN_IMPORTS:
        raise ImportError(f"Import {name!r} is not allowed in Script Runner")
    if root not in ALLOWED_IMPORT_ROOTS:
        raise ImportError(f"Import {name!r} is not in the allowlist")


def _guarded_import(
    name: str,
    globals: dict[str, Any] | None = None,
    locals: dict[str, Any] | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> Any:
    if level:
        raise ImportError("Relative imports are not allowed in Script Runner")
    _reject_import(name)
    module = _REAL_IMPORT(name, globals, locals, fromlist, level)
    root = name.split(".")[0]
    if root == "io":
        return _FilesystemFreeIO(module)
    return module


class _FilesystemFreeIO:
    """In-memory io only. ``io.open`` and file types stay unavailable."""

    def __init__(self, module: Any) -> None:
        self.StringIO = module.StringIO
        self.BytesIO = module.BytesIO

    def open(self, *_args: Any, **_kwargs: Any) -> Any:
        raise PermissionError("Filesystem is not available in Script Runner")

    def __getattr__(self, name: str) -> Any:
        raise PermissionError("Filesystem is not available in Script Runner")


def _blocked_open(*_args: Any, **_kwargs: Any) -> Any:
    raise PermissionError("Filesystem is not available in Script Runner")


def _script_builtins() -> dict[str, Any]:
    names = (
        "abs",
        "all",
        "any",
        "bool",
        "bytearray",
        "bytes",
        "chr",
        "dict",
        "divmod",
        "enumerate",
        "filter",
        "float",
        "format",
        "frozenset",
        "getattr",
        "hasattr",
        "hash",
        "hex",
        "id",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "map",
        "max",
        "min",
        "next",
        "object",
        "oct",
        "ord",
        "pow",
        "print",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "type",
        "zip",
        "BaseException",
        "Exception",
        "ValueError",
        "TypeError",
        "KeyError",
        "IndexError",
        "AttributeError",
        "RuntimeError",
        "StopIteration",
        "AssertionError",
        "NotImplementedError",
        "ImportError",
        "PermissionError",
        "ZeroDivisionError",
        "OverflowError",
        "OSError",
        "__build_class__",
    )
    safe: dict[str, Any] = {}
    for name in names:
        if hasattr(builtins, name):
            safe[name] = getattr(builtins, name)
    safe["__import__"] = _guarded_import
    safe["open"] = _blocked_open
    return safe


class _WriteCounter:
    def __init__(self) -> None:
        self.counts: dict[str, dict[str, int]] = {}

    def record(self, model: str, method: str, n: int = 1) -> None:
        bucket = self.counts.setdefault(model, {"create": 0, "write": 0, "unlink": 0})
        if method in bucket:
            bucket[method] += n


def _connect_client(conn: dict[str, Any], config_cls: Any, client_cls: Any) -> tuple[bool, Any]:
    """Open a client. On failure return the message only, not the client object.

    Rebound onto the execute_kw globals. ``refuse_if_forbidden`` is resolved
    there. This body must not import, or the script's allowlist blocks it.
    """
    client = client_cls(
        config_cls(
            url=conn["url"],
            db=conn["db"],
            username=conn["username"],
            password=conn["password"],
            write_mode=conn.get("write_mode", "standard"),
        )
    )
    if refuse_if_forbidden is not None:  # noqa: F821 — name lives on the clean globals
        client.rpc_guard = refuse_if_forbidden  # noqa: F821
    try:
        client.connect()
    except Exception as exc:  # noqa: BLE001 — drop the client before the script sees the error
        return False, str(exc)
    return True, client


def _open_client(conn: dict[str, Any], config_cls: Any, client_cls: Any) -> Any:
    ok, held = _connect_client(conn, config_cls, client_cls)  # noqa: F821
    if not ok:
        raise OdooClientError(held)  # noqa: F821 — name lives on the clean globals
    return held


def _invoke_execute(
    client: Any,
    model: str,
    method: str,
    args: list[Any],
    kwargs: dict[str, Any],
) -> tuple[bool, Any]:
    try:
        return True, client.execute_kw(model, method, args, kwargs)
    except Exception as exc:  # noqa: BLE001 — caller re-raises without this frame's client
        return False, str(exc)


def _execute_kw_impl(
    self: Any,
    model: str,
    method: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> Any:
    """Code template. ``_bind_execute_kw`` runs a copy whose globals are clean."""
    call_args = list(args or [])
    call_kwargs = dict(kwargs or {})
    reason = builtin_forbidden(model, method, call_args, call_kwargs)  # noqa: F821
    if reason:
        raise OdooClientError(f"forbidden {model}.{method}: {reason}")  # noqa: F821
    client = _open_client(object.__getattribute__(self, "_conn"), ConnectionConfig, OdooClient)  # noqa: F821
    counter = object.__getattribute__(self, "_counter")
    if method == "create":
        counter.record(model, "create")
    elif method == "write":
        ids = call_args[0] if call_args else []
        counter.record(model, "write", len(ids) if isinstance(ids, list) else 1)
    elif method == "unlink":
        ids = call_args[0] if call_args else []
        counter.record(model, "unlink", len(ids) if isinstance(ids, list) else 1)
    ok, outcome = _invoke_execute(client, model, method, call_args, call_kwargs)  # noqa: F821
    del client
    if not ok:
        raise OdooClientError(outcome)  # noqa: F821
    return outcome


def _bind_execute_kw(owner: Any) -> Any:
    """Callable whose globals cannot see os, sys, builtins, or this module's functions."""
    from odoo_client.client import ConnectionConfig, OdooClient, OdooClientError
    from odoo_client.rpc_policy import builtin_forbidden

    try:
        from app.rpc_guard import refuse_if_forbidden
    except ImportError:
        refuse_if_forbidden = None

    globs: dict[str, Any] = {
        "__builtins__": _script_builtins(),
        "ConnectionConfig": ConnectionConfig,
        "OdooClient": OdooClient,
        "OdooClientError": OdooClientError,
        "builtin_forbidden": builtin_forbidden,
        "refuse_if_forbidden": refuse_if_forbidden,
    }
    for name, template in (
        ("_connect_client", _connect_client),
        ("_open_client", _open_client),
        ("_invoke_execute", _invoke_execute),
    ):
        globs[name] = types.FunctionType(
            template.__code__,
            globs,
            name,
            template.__defaults__,
        )
    execute = types.FunctionType(
        _execute_kw_impl.__code__,
        globs,
        "execute_kw",
        _execute_kw_impl.__defaults__,
    )
    return types.MethodType(execute, owner)


class ScriptOdoo:
    """RPC facade. Forbidden calls raise before any socket is opened.

    The live client is not stored here. ``execute_kw`` is rebound with
    ``types.FunctionType`` onto globals that cannot see this module, so a
    script cannot walk ``__globals__`` back to ``os``. ``__getattr__`` does
    not hide an attribute that already exists, so a script that just made an
    allowed call must still be unable to reach ``_dispatch_execute``.
    """

    __slots__ = ("_conn", "_counter", "_execute_kw")

    def __init__(self, conn: dict[str, Any], counter: _WriteCounter) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_counter", counter)
        object.__setattr__(self, "_execute_kw", _bind_execute_kw(self))

    def __getattribute__(self, name: str) -> Any:
        if name == "execute_kw":
            return object.__getattribute__(self, "_execute_kw")
        if name.startswith("_"):
            raise AttributeError(name)
        raise PermissionError(f"Script Runner only allows odoo.execute_kw, not {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(name)


def _log_impl(msg: str) -> None:
    text = str(msg)
    log_lines.append(text)
    print(text, flush=True)


def _progress_impl(n: int, total: int) -> None:
    log(f"[progress] {n}/{total}")


def _bind_helpers(lines: list[str]) -> tuple[Any, Any]:
    """Helpers whose globals cannot see os, the config, or the real open()."""
    globs: dict[str, Any] = {
        "__builtins__": _script_builtins(),
        "log_lines": lines,
        "str": str,
        "print": print,
    }
    log_fn = types.FunctionType(_log_impl.__code__, globs, "log")
    globs["log"] = log_fn
    progress_fn = types.FunctionType(_progress_impl.__code__, globs, "progress")
    return log_fn, progress_fn


def main() -> int:
    config_path = os.environ.get("SCRIPT_RUNNER_CONFIG")
    script_path = os.environ.get("SCRIPT_RUNNER_SCRIPT")
    if not config_path or not script_path:
        print("Missing SCRIPT_RUNNER_CONFIG or SCRIPT_RUNNER_SCRIPT", file=sys.stderr)
        return 2
    with open(config_path, encoding="utf-8") as handle:
        cfg = json.loads(handle.read())
    with open(script_path, encoding="utf-8") as handle:
        script = handle.read()
    # The script must not be able to reopen the credential file.
    with open(config_path, "w", encoding="utf-8") as handle:
        handle.write("{}")
    os.environ.pop("SCRIPT_RUNNER_CONFIG", None)
    os.environ.pop("SCRIPT_RUNNER_SCRIPT", None)

    _check_imports(script)
    odoo = ScriptOdoo(cfg["connection"], _WriteCounter())
    log_lines: list[str] = []
    log, progress = _bind_helpers(log_lines)
    namespace: dict[str, Any] = {
        "__builtins__": _script_builtins(),
        "odoo": odoo,
        "log": log,
        "progress": progress,
    }
    exec(compile(script, script_path, "exec"), namespace)  # noqa: S102 — isolated script exec
    counts = (
        object.__getattribute__(odoo, "_counter").counts if cfg.get("count_writes", True) else {}
    )
    payload = {"write_counts": counts, "log_lines": log_lines}
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
