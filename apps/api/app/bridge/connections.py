"""Bridge connection verification and Tier I gate.

Read-only probes prove a Connection can talk to its remote before any
contract that references it may leave Tier I. Secrets stay on the
Connection; probes never log credentials.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from app.bridge.contract import ContractError, IntegrationContract

DEFAULT_SHOPIFY_API_VERSION = "2024-10"
_ODOO_PROBE_MODEL = "res.partner"


class ConnectionProbeError(Exception):
    """Read-only probe failed. Safe to surface; never carries secrets."""


def probe_odoo(client: Any) -> dict[str, Any]:
    """Odoo probe: ``version`` (or ``server_version``) + one ``search_count``.

    ``client`` is any object that exposes those read-only methods, or
    ``execute_kw`` for the count. Never writes. Raises
    :class:`ConnectionProbeError` on failure.
    """
    try:
        version = _odoo_version(client)
        count = _odoo_search_count(client, _ODOO_PROBE_MODEL, [])
    except ConnectionProbeError:
        raise
    except Exception as exc:  # noqa: BLE001 — remote failures become probe failure
        raise ConnectionProbeError(f"odoo probe failed: {exc.__class__.__name__}") from exc
    if version is None or version == "" or version == {}:
        raise ConnectionProbeError("odoo probe failed: empty version")
    if not isinstance(count, int) or count < 0:
        raise ConnectionProbeError("odoo probe failed: invalid search_count")
    return {"kind": "odoo", "version": version, "search_count": count, "model": _ODOO_PROBE_MODEL}


def probe_shopify(
    *,
    shop: str,
    access_token: str,
    api_version: str = DEFAULT_SHOPIFY_API_VERSION,
    transport: httpx.BaseTransport | None = None,
    http_get: Callable[..., httpx.Response] | None = None,
) -> dict[str, Any]:
    """Shopify probe: GET ``shop.json`` with the Admin access token.

    ``http_get`` may replace the network call (tests). Raises
    :class:`ConnectionProbeError` on non-200 or malformed body. The token
    is sent as a header and is never included in the error message.
    """
    if not shop or not str(shop).strip():
        raise ConnectionProbeError("shopify probe failed: shop is required")
    if not access_token or not str(access_token).strip():
        raise ConnectionProbeError("shopify probe failed: access_token is required")
    url = shopify_shop_json_url(str(shop), api_version=api_version)
    headers = {"X-Shopify-Access-Token": str(access_token).strip(), "Accept": "application/json"}
    try:
        if http_get is not None:
            response = http_get(url, headers=headers)
        else:
            with httpx.Client(transport=transport, timeout=15.0) as client:
                response = client.get(url, headers=headers)
    except ConnectionProbeError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ConnectionProbeError(f"shopify probe failed: {exc.__class__.__name__}") from exc

    status = int(getattr(response, "status_code", 0) or 0)
    if status != 200:
        raise ConnectionProbeError(f"shopify probe failed: HTTP {status}")
    try:
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        raise ConnectionProbeError("shopify probe failed: invalid JSON") from exc
    shop_body = payload.get("shop") if isinstance(payload, dict) else None
    if not isinstance(shop_body, dict) or not shop_body.get("id"):
        raise ConnectionProbeError("shopify probe failed: shop.json missing shop.id")
    return {
        "kind": "shopify",
        "shop_id": shop_body.get("id"),
        "shop_domain": shop_body.get("myshopify_domain") or shop_body.get("domain"),
    }


def shopify_shop_json_url(shop: str, *, api_version: str = DEFAULT_SHOPIFY_API_VERSION) -> str:
    """Build the Admin REST ``shop.json`` URL for a shop domain or hostname."""
    host = str(shop).strip()
    if "://" in host:
        parsed = urlparse(host)
        host = parsed.netloc or parsed.path
    host = host.split("/", 1)[0].strip().lower()
    if not host:
        raise ConnectionProbeError("shopify probe failed: shop is required")
    if "." not in host:
        host = f"{host}.myshopify.com"
    version = (api_version or DEFAULT_SHOPIFY_API_VERSION).strip()
    return f"https://{host}/admin/api/{version}/shop.json"


def probe_for_connection(
    row: Any,
    *,
    odoo_client: Any | None = None,
    shopify_shop: str | None = None,
    shopify_token: str | None = None,
    shopify_api_version: str = DEFAULT_SHOPIFY_API_VERSION,
    shopify_transport: httpx.BaseTransport | None = None,
    shopify_http_get: Callable[..., httpx.Response] | None = None,
) -> Callable[[], dict[str, Any]]:
    """Return a zero-arg probe callable for ``row.kind`` (odoo / shopify / third_party)."""
    kind = str(getattr(row, "kind", "") or "").strip().lower()
    if kind == "odoo":
        if odoo_client is None:
            raise ConnectionProbeError("odoo probe requires odoo_client")
        return lambda: probe_odoo(odoo_client)
    if kind in {"shopify", "third_party"}:
        shop = shopify_shop if shopify_shop is not None else getattr(row, "shop", None)
        token = shopify_token if shopify_token is not None else getattr(row, "access_token", None)
        if not shop or not token:
            raise ConnectionProbeError("shopify probe requires shop and access_token")
        return lambda: probe_shopify(
            shop=str(shop),
            access_token=str(token),
            api_version=shopify_api_version,
            transport=shopify_transport,
            http_get=shopify_http_get,
        )
    raise ConnectionProbeError(f"unsupported connection kind for probe: {kind or 'missing'}")


def verify_connection(
    row: Any,
    *,
    probe_ok: bool | None = None,
    probe: Callable[[], Any] | None = None,
) -> Any:
    """Run a probe (or honor ``probe_ok``) and set ``status`` / ``verified_at``.

    Success → ``status=verified`` and ``verified_at`` (UTC).
    Failure → ``status=failed`` and ``verified_at=None``.
    Existing seeded tests pass ``probe_ok``; the live path passes ``probe``.
    """
    if probe is not None and probe_ok is not None:
        raise TypeError("verify_connection accepts probe or probe_ok, not both")
    if probe is not None:
        try:
            probe()
            ok = True
        except Exception:  # noqa: BLE001 — any probe failure marks the connection failed
            ok = False
    elif probe_ok is not None:
        ok = bool(probe_ok)
    else:
        raise TypeError("verify_connection requires probe or probe_ok")

    if ok:
        row.status = "verified"
        row.verified_at = datetime.now(UTC)
    else:
        row.status = "failed"
        row.verified_at = None
    return row


def connection_may_leave_tier_i(row: Any) -> bool:
    """A contract cannot pass Tier I until the connection is verified with a timestamp."""
    if getattr(row, "verified_at", None) is None:
        return False
    return getattr(row, "status", None) == "verified"


def require_verified_connections(
    contract: IntegrationContract,
    connections: Mapping[str, Any],
) -> None:
    """Tier I gate: every referenced connection must have ``verified_at``.

    Raises :class:`ContractError` when a connection is missing, failed, or
    unverified. Call after :func:`app.bridge.contract.validate_contract`.
    """
    refused: list[str] = []
    for label, connection_id in (
        ("odoo", contract.odoo_connection_id),
        ("third_party", contract.third_party_connection_id),
    ):
        row = connections.get(connection_id)
        if row is None or not connection_may_leave_tier_i(row):
            status = getattr(row, "status", None) if row is not None else "missing"
            refused.append(f"{label}:{connection_id} ({status})")
    if refused:
        raise ContractError(
            "Tier I requires verified connections (verified_at set): " + ", ".join(refused)
        )


def _odoo_version(client: Any) -> Any:
    if hasattr(client, "version") and callable(client.version):
        return client.version()
    if hasattr(client, "server_version") and callable(client.server_version):
        return client.server_version()
    raise ConnectionProbeError("odoo probe failed: client has no version/server_version")


def _odoo_search_count(client: Any, model: str, domain: list[Any]) -> int:
    if hasattr(client, "search_count") and callable(client.search_count):
        return int(client.search_count(model, domain))
    if hasattr(client, "execute_kw") and callable(client.execute_kw):
        return int(client.execute_kw(model, "search_count", [domain]))
    raise ConnectionProbeError("odoo probe failed: client has no search_count/execute_kw")
