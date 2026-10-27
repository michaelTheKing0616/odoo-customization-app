"""SEC-AUTH-BOOT AC1. Production refuses to start with auth_mode=off.

``app.auth.assert_auth_mode_off_boot`` takes no arguments. It reads
``settings.auth_mode``, ``settings.app_environment`` (``APP_ENVIRONMENT``, the
ENV in this AC), and the argv token after a separate ``--host``. ``auth_mode=off``
may start only when that ENV is ``development`` and the host is loopback
(``127.0.0.1``, ``::1``, or ``localhost``). Every other combination raises
``RuntimeError`` whose message contains ``auth_mode=off``. ``app.main.lifespan``
calls the check before ``init_db``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_app_db

_MAIN_PATH = Path(__file__).resolve().parents[1] / "app" / "main.py"
_BOOT = "assert_auth_mode_off_boot"
_LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")
_REFUSALS = (
    ("production", "127.0.0.1"),
    ("production", "localhost"),
    ("staging", "::1"),
    ("development", "0.0.0.0"),
)


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _calls_from(node: ast.AST) -> list[ast.Call]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return []
    found: list[ast.Call] = []
    if isinstance(node, ast.Call):
        found.append(node)
    for child in ast.iter_child_nodes(node):
        found.extend(_calls_from(child))
    return found


def _lifespan_calls() -> list[ast.Call]:
    tree = ast.parse(_MAIN_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan":
            calls: list[ast.Call] = []
            for stmt in node.body:
                calls.extend(_calls_from(stmt))
            return calls
    raise AssertionError("app.main lifespan is missing")


def _require_lifespan_calls_boot_check() -> None:
    """Fail when lifespan no longer runs the boot check before init_db.

    The file is parsed. Importing ``app.main`` starts a scheduler thread that
    opens the app database.
    """
    calls = _lifespan_calls()
    names = [_call_name(call) for call in calls]
    if _BOOT not in names or "init_db" not in names:
        raise AssertionError(
            "lifespan must call app.auth.assert_auth_mode_off_boot before init_db"
        )
    if names.index(_BOOT) > names.index("init_db"):
        raise AssertionError("assert_auth_mode_off_boot must run before init_db")
    for call in calls:
        if _call_name(call) != _BOOT:
            continue
        nodes = [*call.args, *[keyword.value for keyword in call.keywords]]
        for arg in nodes:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                raise AssertionError(
                    "lifespan must not hardcode the bind address into the boot check"
                )


def _boot_check():
    import app.auth as auth

    fn = getattr(auth, _BOOT, None)
    if not callable(fn):
        raise AssertionError(
            "app.auth.assert_auth_mode_off_boot is missing; "
            "startup must refuse auth_mode=off unless ENV=development "
            "and the bind address is loopback"
        )
    return fn


def _set_boot(
    monkeypatch: pytest.MonkeyPatch,
    *,
    environment: str,
    host: str,
    auth_mode: str = "off",
) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "auth_mode", auth_mode)
    monkeypatch.setattr(settings, "app_environment", environment)
    monkeypatch.setenv("AUTH_MODE", auth_mode)
    monkeypatch.setenv("APP_ENVIRONMENT", environment)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setattr(sys, "argv", ["uvicorn", "app.main:app", "--host", host])


def test_ac1_positive_development_loopback_allows_auth_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """development plus a loopback --host may start with auth_mode=off."""
    check = _boot_check()
    for host in _LOOPBACK_HOSTS:
        _set_boot(monkeypatch, environment="development", host=host)
        assert check() is None
    _require_lifespan_calls_boot_check()


def test_ac1_negative_auth_off_refuses_unless_development_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """auth_mode=off refuses unless ENV is development and the bind is loopback."""
    check = _boot_check()
    for environment, host in _REFUSALS:
        _set_boot(monkeypatch, environment=environment, host=host)
        with pytest.raises(RuntimeError, match="auth_mode=off"):
            check()
    _require_lifespan_calls_boot_check()
