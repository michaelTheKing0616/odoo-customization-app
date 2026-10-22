"""Per-call AI context: which database/snapshot a call is about and how it may be cached/guarded.

Set by routers/services with ``with ai_scope(db=..., snapshot_hash=..., surface=...)``.
Everything here is advisory input to the shared AI client; code still authorizes writes.
"""

from __future__ import annotations

import contextlib
import contextvars
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterator


@dataclass(frozen=True)
class AIScope:
    db: str = ""                       # connection id / database name
    odoo_version: str = ""
    snapshot_hash: str = ""            # changes -> cache keys change (implicit invalidation)
    surface: str = "internal"          # internal | client_chat | demo_copilot | expert
    fresh: bool = False                # "fresh answer": skip cache reads (still writes)
    semantic_ok: bool = False          # caller says near-duplicate reuse is safe
    cache_ttl_s: int | None = None
    reads: tuple[str, ...] = ()         # Odoo models whose data the prompt contains (cache deps)
    pii_names: tuple[str, ...] = ()    # known person names to mask (from Odoo partners)
    consent_cloud: bool = True         # D6: cloud AI only with client consent
    claim_verifier: Callable[[str], bool] | None = None  # checks "exists in your database" claims
    extra: dict[str, Any] = field(default_factory=dict)


_scope: contextvars.ContextVar[AIScope] = contextvars.ContextVar("ai_scope", default=AIScope())


def current_scope() -> AIScope:
    return _scope.get()


@contextlib.contextmanager
def ai_scope(**kw: Any) -> Iterator[AIScope]:
    """Nest-able: unspecified fields inherit from the enclosing scope."""
    if "reads" in kw:
        kw["reads"] = tuple(kw["reads"] or ())
    if "pii_names" in kw:
        kw["pii_names"] = tuple(kw["pii_names"] or ())
    new = replace(_scope.get(), **kw)
    tok = _scope.set(new)
    try:
        yield new
    finally:
        _scope.reset(tok)


class AIScopeMiddleware:
    """ASGI: every request about /connections/{id}/... gets ai_scope(db=id); Demo Co-Pilot
    and portal routes get their client-facing surface so the guards apply."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        kw: dict[str, Any] = {}
        parts = path.split("/")
        if "connections" in parts:
            i = parts.index("connections")
            if i + 1 < len(parts) and parts[i + 1]:
                kw["db"] = parts[i + 1]
        if "/live-demo-copilot" in path:
            kw["surface"] = "demo_copilot"
        elif "/portal" in path:
            kw["surface"] = "portal"
        for name, value in scope.get("headers") or []:
            if name == b"x-ingenium-fresh" and value in (b"1", b"true"):
                kw["fresh"] = True
        if not kw:
            await self.app(scope, receive, send)
            return
        with ai_scope(**kw):
            await self.app(scope, receive, send)
