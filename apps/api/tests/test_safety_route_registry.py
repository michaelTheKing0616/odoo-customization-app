"""TRUST-2 route registry meta-test — every mutating /api route must be declared."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.main import app  # noqa: E402
from app.safety_registry import (  # noqa: E402
    MUTATING_METHODS,
    build_route_registry,
    is_exempt,
    route_key,
)


def _mutating_api_routes() -> list[str]:
    paths = app.openapi()["paths"]
    keys: list[str] = []
    for path, ops in paths.items():
        if not path.startswith("/api/"):
            continue
        for method, _meta in ops.items():
            if method.upper() in MUTATING_METHODS:
                keys.append(route_key(method, path))
    return sorted(keys)


def test_every_mutating_api_route_has_safety_spec() -> None:
    registry = build_route_registry(app.openapi()["paths"])
    missing: list[str] = []
    for key in _mutating_api_routes():
        if key not in registry:
            missing.append(key)
    assert not missing, "Missing SafetySpec for routes:\n" + "\n".join(missing)


def test_non_exempt_routes_are_gated_at_runtime() -> None:
    """Document count — meta-test fails if new routes lack registry entries."""
    keys = _mutating_api_routes()
    gated = [k for k in keys if not is_exempt(k)]
    assert len(gated) >= 150
    assert len(keys) == len(set(keys))
