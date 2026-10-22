"""Code runner v2 child process: dry run (intercepted writes) or real run (journaled), with events.

Safety layers, outermost first:
1. Dry run connects with write_mode="observer": the client itself refuses every write.
2. The facade intercepts writes and records what *would* change (before/after), never sending them.
3. Scripts may not touch dunder attributes or names (no reaching closures, globals, classes).
4. The existing runner's import allowlist, builtins and forbidden-RPC policy apply unchanged.
Events go to stdout as lines starting with EV_PREFIX (JSON).
"""

from __future__ import annotations

import ast
import json
import os
import sys
import time
import traceback
from typing import Any

EV_PREFIX = "@@CR "
WRITE_METHODS = {"create", "write", "unlink"}
READ_METHODS = {"search", "search_read", "search_count", "read", "fields_get", "name_search", "read_group",
                "formatted_read_group", "default_get", "web_search_read", "web_read", "check_access_rights",
                "check_access", "get_views"}
SAMPLE_CAP = 20
MAX_RESULT_ROWS = 5000


class ScriptError(Exception):
    pass


def check_source(source: str) -> None:
    """Reject dunder access (the escape route out of any Python sandbox)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ScriptError(f"Line {node.lineno}: '{node.attr}' isn't allowed in scripts.")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ScriptError(f"Line {node.lineno}: '{node.id}' isn't allowed in scripts.")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("__") and node.value.endswith("__"):
            raise ScriptError(f"Line {node.lineno}: names like '{node.value}' aren't allowed in scripts.")


_SECRET_VALUES: list[str] = []


def emit(ev: dict[str, Any]) -> None:
    line = json.dumps(ev, default=str)
    for v in sorted(_SECRET_VALUES, key=len, reverse=True):
        if len(v) >= 3:
            line = line.replace(json.dumps(v)[1:-1], "***")
    sys.stdout.write(EV_PREFIX + line + "\n")
    sys.stdout.flush()


def script_line() -> int:
    for fr in reversed(traceback.extract_stack()):
        if fr.filename == "<script>":
            return fr.lineno or 0
    return 0


def _ids(v: Any) -> list[int]:
    if isinstance(v, int):
        return [v]
    return [i for i in v if isinstance(i, int)] if isinstance(v, (list, tuple)) else []


class Engine:
    """Holds the client; never reachable from the script (dunder ban + slots facade)."""

    def __init__(self, client: Any, mode: str, control: str, sample: bool) -> None:
        self.client, self.mode, self.control, self.sample = client, mode, control, sample
        self.fake = 0
        self.domains: list[tuple[str, Any]] = []

    def _control(self) -> None:
        while True:
            try:
                with open(self.control, encoding="utf-8") as fh:
                    state = fh.read().strip()
            except OSError:
                return
            if state == "stop":
                raise ScriptError("Stopped by you. Changes made so far are kept and can be undone.")
            if state != "pause":
                return
            time.sleep(0.5)

    def call(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
        from odoo_client.rpc_policy import builtin_forbidden

        reason = builtin_forbidden(model, method, args, kwargs)
        if reason:
            raise ScriptError(f"{model}.{method} isn't allowed: {reason}")
        line, t0 = script_line(), time.perf_counter()
        try:
            out = self._dispatch(model, method, list(args), dict(kwargs))
        finally:
            emit({"t": "call", "model": model, "method": method, "line": line, "ms": round((time.perf_counter() - t0) * 1000, 2)})
        return out

    def _read_before(self, model: str, ids: list[int], fields: list[str]) -> dict[int, dict[str, Any]]:
        if not ids:
            return {}
        rows = self.client.execute_kw(model, "read", [ids, sorted(set(fields) | {"display_name"})], {})
        return {r["id"]: r for r in rows}

    def _dispatch(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
        if method in WRITE_METHODS or method not in READ_METHODS:
            self._control()
        if method in {"search", "search_read"} and self.sample:
            self.domains.append((model, args[0] if args else kwargs.get("domain", [])))
            kwargs["limit"] = min(int(kwargs.get("limit") or SAMPLE_CAP), SAMPLE_CAP)
        if method in READ_METHODS:
            return self.client.execute_kw(model, method, args, kwargs)
        dry = self.mode == "dry"
        if method == "create":
            vals = args[0] if args else kwargs.get("vals_list", {})
            many = isinstance(vals, list)
            rows = vals if many else [vals]
            if dry:
                ids = []
                for v in rows:
                    self.fake -= 1
                    ids.append(self.fake)
                    emit({"t": "change", "op": "create", "model": model, "id": self.fake, "before": None, "after": v})
                return ids if many else ids[0]
            got = self.client.execute_kw(model, "create", [rows], kwargs)
            new = _ids(got)
            for i, v in zip(new, rows):
                emit({"t": "change", "op": "create", "model": model, "id": i, "before": None, "after": v})
            return new if many else (new[0] if new else got)
        if method == "write":
            ids, vals = _ids(args[0] if args else []), (args[1] if len(args) > 1 else kwargs.get("vals", {}))
            real = [i for i in ids if i > 0]
            before = self._read_before(model, real, list(vals))
            for i in ids:
                b = before.get(i, {})
                emit({"t": "change", "op": "write", "model": model, "id": i, "label": b.get("display_name"),
                      "before": {k: b.get(k) for k in vals}, "after": vals})
            return True if dry else self.client.execute_kw(model, "write", [real, vals], kwargs)
        if method == "unlink":
            ids = [i for i in _ids(args[0] if args else []) if i > 0]
            before = self._read_before(model, ids, [])
            for i in ids:
                emit({"t": "change", "op": "unlink", "model": model, "id": i, "label": before.get(i, {}).get("display_name"),
                      "before": before.get(i), "after": None})
            return True if dry else self.client.execute_kw(model, "unlink", [ids], kwargs)
        # Any other public method (action_*, button_*, custom): on a dry run it is only listed.
        ids = _ids(args[0] if args else [])
        emit({"t": "change", "op": "method", "model": model, "method": method, "ids": ids, "before": None, "after": None})
        if dry:
            return True
        return self.client.execute_kw(model, method, args, kwargs)


def _bind(engine: Engine) -> tuple[Any, Any, Any, Any]:
    class RunnerOdoo:
        __slots__ = ()

        def execute_kw(self, model: str, method: str, args: Any = None, kwargs: Any = None) -> Any:
            return engine.call(str(model), str(method), list(args or []), dict(kwargs or {}))

    rows_out: list[Any] = []

    def log(msg: Any, group: str = "") -> None:
        emit({"t": "log", "msg": str(msg)[:4000], "group": str(group)[:80], "line": script_line()})

    def progress(done: int, total: int) -> None:
        emit({"t": "progress", "done": int(done), "total": int(total)})

    def result(rows: Any) -> None:
        if isinstance(rows, dict):
            rows = [rows]
        for r in list(rows)[: MAX_RESULT_ROWS - len(rows_out)]:
            rows_out.append(r if isinstance(r, dict) else {"value": r})
        emit({"t": "result", "rows": rows_out[-len(list(rows)):] if rows else []})

    return RunnerOdoo(), log, progress, result


def _secret_getter(secrets: dict[str, str]) -> Any:
    def secret(name: str) -> str:
        if name not in secrets:
            raise KeyError(f"No secret named {name!r} for this connection. Add it in the vault.")
        return secrets[name]
    return secret


def plain_traceback(exc: BaseException) -> dict[str, Any]:
    line = 0
    for fr in traceback.extract_tb(exc.__traceback__):
        if fr.filename == "<script>":
            line = fr.lineno or 0
    msg = str(exc).strip().splitlines()[-1] if str(exc).strip() else type(exc).__name__
    if "Invalid field" in msg or "has no field" in msg:
        hint = "A field name is wrong for this Odoo version; check the Problems list."
    elif "Access" in msg and "denied" in msg.lower():
        hint = "This user isn't allowed to do that in Odoo."
    elif isinstance(exc, KeyError):
        hint = f"The record has no value named {msg}; read that field first."
    else:
        hint = ""
    return {"line": line, "message": msg[:1000], "hint": hint, "kind": type(exc).__name__}


def main() -> int:
    from app.script_runner.child_main import _check_imports, _script_builtins
    from odoo_client import ConnectionConfig, OdooClient

    with open(os.environ["CR_CONFIG"], encoding="utf-8") as fh:
        cfg = json.loads(fh.read())
    with open(os.environ["CR_CONFIG"], "w", encoding="utf-8") as fh:
        fh.write("{}")  # credentials are gone before the script starts
    os.environ.pop("CR_CONFIG", None)
    conn, mode = cfg["connection"], cfg["mode"]
    secrets = dict(cfg.get("secrets") or {})
    _SECRET_VALUES.extend(secrets.values())
    script = cfg["script"]
    try:
        check_source(script)
        _check_imports(script)
    except (ScriptError, ImportError, SyntaxError) as exc:
        emit({"t": "error", **plain_traceback(exc), "line": getattr(exc, "lineno", 0) or 0})
        return 1
    client = OdooClient(ConnectionConfig(url=conn["url"], db=conn["db"], username=conn["username"], password=conn["password"],
                                         write_mode="observer" if mode == "dry" else conn.get("write_mode", "standard")))
    try:
        from app.rpc_guard import refuse_if_forbidden

        client.rpc_guard = refuse_if_forbidden
    except ImportError:
        pass
    client.connect()
    engine = Engine(client, mode, cfg.get("control", ""), bool(cfg.get("sample")))
    odoo, log, progress, result = _bind(engine)
    safe = _script_builtins()
    real_getattr, real_hasattr = safe["getattr"], safe["hasattr"]

    def guarded_getattr(obj: Any, name: str, *default: Any) -> Any:
        if str(name).startswith("_"):
            raise AttributeError(f"'{name}' isn't allowed in scripts.")
        return real_getattr(obj, name, *default)

    def guarded_hasattr(obj: Any, name: str) -> bool:
        return not str(name).startswith("_") and real_hasattr(obj, name)

    safe.update(getattr=guarded_getattr, hasattr=guarded_hasattr)
    for name in ("vars", "dir", "globals", "locals", "eval", "exec", "compile", "breakpoint", "input"):
        safe.pop(name, None)
    ns: dict[str, Any] = {"__builtins__": safe, "odoo": odoo, "log": log, "progress": progress,
                          "result": result, "params": dict(cfg.get("params") or {}),
                          "secret": _secret_getter(secrets),
                          "resume_from": int(cfg.get("resume_from") or 0), "done_ids": dict(cfg.get("done_ids") or {})}
    del conn, cfg
    t0 = time.perf_counter()
    try:
        exec(compile(script, "<script>", "exec"), ns)  # noqa: S102 - isolated child process
    except BaseException as exc:  # noqa: BLE001
        emit({"t": "error", **plain_traceback(exc)})
        return 1
    finally:
        emit({"t": "timing", "ms": round((time.perf_counter() - t0) * 1000, 1)})
        if engine.sample:
            counts = []
            for model, dom in engine.domains[:20]:
                try:
                    counts.append({"model": model, "count": client.execute_kw(model, "search_count", [dom], {})})
                except Exception:  # noqa: BLE001
                    pass
            emit({"t": "sample_counts", "counts": counts})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        emit({"t": "error", "line": 0, "message": str(exc)[:500], "hint": "", "kind": type(exc).__name__})
        raise SystemExit(1) from exc
