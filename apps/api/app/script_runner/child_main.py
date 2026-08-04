"""DEV-3 child process entry — restricted imports + Odoo client injection."""

from __future__ import annotations

import ast
import json
import os
import sys
from typing import Any

ALLOWED_IMPORT_ROOTS = frozenset(
    {
        "odoo_client",
        "csv",
        "io",
        "json",
        "datetime",
        "math",
        "re",
        "collections",
    }
)

FORBIDDEN_IMPORTS = frozenset({"subprocess", "socket", "urllib", "http", "ftplib", "telnetlib", "pickle"})


def _check_imports(source: str) -> None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_IMPORTS:
                    raise ImportError(f"Import {alias.name!r} is not allowed in Script Runner")
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            root = mod.split(".")[0]
            if root in FORBIDDEN_IMPORTS:
                raise ImportError(f"Import from {mod!r} is not allowed in Script Runner")
            if root not in ALLOWED_IMPORT_ROOTS and not mod.startswith("odoo_client"):
                raise ImportError(f"Import from {mod!r} is not in the allowlist")


class _WriteCounter:
    def __init__(self) -> None:
        self.counts: dict[str, dict[str, int]] = {}

    def record(self, model: str, method: str, n: int = 1) -> None:
        bucket = self.counts.setdefault(model, {"create": 0, "write": 0, "unlink": 0})
        if method in bucket:
            bucket[method] += n


class CountingOdooClient:
    def __init__(self, inner: Any, counter: _WriteCounter) -> None:
        self._inner = inner
        self._counter = counter

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        if method == "create":
            self._counter.record(model, "create")
        elif method == "write":
            ids = args[0] if args else []
            self._counter.record(model, "write", len(ids) if isinstance(ids, list) else 1)
        elif method == "unlink":
            ids = args[0] if args else []
            self._counter.record(model, "unlink", len(ids) if isinstance(ids, list) else 1)
        return self._inner.execute_kw(model, method, args, kwargs or {})


def main() -> int:
    config_path = os.environ.get("SCRIPT_RUNNER_CONFIG")
    script_path = os.environ.get("SCRIPT_RUNNER_SCRIPT")
    if not config_path or not script_path:
        print("Missing SCRIPT_RUNNER_CONFIG or SCRIPT_RUNNER_SCRIPT", file=sys.stderr)
        return 2
    cfg = json.loads(open(config_path, encoding="utf-8").read())
    script = open(script_path, encoding="utf-8").read()
    _check_imports(script)

    from odoo_client import ConnectionConfig, OdooClient

    conn = cfg["connection"]
    client = OdooClient(
        ConnectionConfig(
            url=conn["url"],
            db=conn["db"],
            username=conn["username"],
            password=conn["password"],
            write_mode=conn.get("write_mode", "standard"),
        )
    )
    client.connect()
    counter = _WriteCounter()
    odoo = CountingOdooClient(client, counter) if cfg.get("count_writes", True) else client
    log_lines: list[str] = []

    def log(msg: str) -> None:
        text = str(msg)
        log_lines.append(text)
        print(text, flush=True)

    def progress(n: int, total: int) -> None:
        log(f"[progress] {n}/{total}")

    namespace: dict[str, Any] = {
        "odoo": odoo,
        "log": log,
        "progress": progress,
    }
    exec(compile(script, script_path, "exec"), namespace)  # noqa: S102 — intentional isolated script exec
    payload = {"write_counts": counter.counts, "log_lines": log_lines}
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
