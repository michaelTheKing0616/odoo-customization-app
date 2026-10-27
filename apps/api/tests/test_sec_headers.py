"""SEC-HEADERS AC1 (handover §6.8 L785): security response headers and SSRF guard targets.

Product lines whose deletion would fail the hard asserts (SSRF):
- ``apps/api/app/llm_gateway/ssrf.py:19-28`` (``_blocked``)
- ``apps/api/app/llm_gateway/ssrf.py:52-55`` (resolve-then-block loop in ``guard_base_url``)

Product lines the header checks expect once shipped (currently missing → xfail):
- ``apps/api/app/main.py`` response hardening middleware (HSTS, CSP + nonce,
  ``frame-ancestors``, Referrer-Policy, Permissions-Policy, nosniff)
- ``apps/web/next.config.ts`` ``headers()`` export for the Next.js surface

SSRF cases use ``guard_base_url`` with a stub ``resolve`` only. No packet is sent
to 169.254.169.254 or other metadata hosts. Does not bind port 8001.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENVIRONMENT", "development")
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

from app.llm_gateway.ssrf import SsrfRejected, guard_base_url  # noqa: E402
from app.main import app  # noqa: E402

_NEXT_CONFIG = Path(__file__).resolve().parents[2] / "web" / "next.config.ts"
_HEALTH = "/health"
_NONCE_IN_CSP = re.compile(r"nonce-[A-Za-z0-9+/=_-]+")


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _header_map(response) -> dict[str, str]:
    return {name.lower(): value for name, value in response.headers.items()}


# --- SSRF (hard asserts; guard_base_url + stub resolve only) ---


def test_ssrf_blocks_link_local_metadata_169_254_169_254() -> None:
    """Deleting ``ssrf.py:_blocked`` lets link-local metadata through."""
    with pytest.raises(SsrfRejected):
        guard_base_url(
            "https://169.254.169.254/latest/meta-data",
            resolve=lambda _host: ["169.254.169.254"],
        )


def test_ssrf_blocks_loopback_127_0_0_1_literal_host() -> None:
    """Deleting ``ssrf.py:_blocked`` lets IPv4 loopback through."""
    with pytest.raises(SsrfRejected):
        guard_base_url("https://127.0.0.1/internal", resolve=lambda _host: ["127.0.0.1"])


def test_ssrf_blocks_loopback_ipv6_bracket_host() -> None:
    """Deleting ``ssrf.py:_blocked`` lets ``[::1]`` through."""
    with pytest.raises(SsrfRejected):
        guard_base_url("https://[::1]/internal", resolve=lambda _host: ["::1"])


@pytest.mark.parametrize(
    "resolved",
    [
        ["127.0.0.1"],
        ["169.254.169.254"],
        ["::1"],
    ],
    ids=["rebind-to-127.0.0.1", "rebind-to-169.254.169.254", "rebind-to-::1"],
)
def test_ssrf_blocks_dns_rebinding_to_refused_addresses(resolved: list[str]) -> None:
    """Deleting ``ssrf.py:52-55`` lets a public hostname reach a refused IP."""
    with pytest.raises(SsrfRejected):
        guard_base_url(
            "https://model-gateway.example/v1/chat",
            resolve=lambda _host: resolved,
        )


# --- API response headers (xfail until main.py ships hardening middleware) ---


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.8-HEADERS-HSTS: GET /health responses omit Strict-Transport-Security "
        "(no security headers middleware in app.main yet)"
    ),
)
def test_api_health_includes_strict_transport_security(client: TestClient) -> None:
    response = client.get(_HEALTH)
    assert response.status_code == 200
    headers = _header_map(response)
    assert "strict-transport-security" in headers
    assert headers["strict-transport-security"].strip()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.8-HEADERS-CSP-NONCE: GET /health responses omit Content-Security-Policy "
        "with a script/style nonce"
    ),
)
def test_api_health_csp_includes_nonce(client: TestClient) -> None:
    response = client.get(_HEALTH)
    assert response.status_code == 200
    csp = _header_map(response).get("content-security-policy", "")
    assert csp
    assert _NONCE_IN_CSP.search(csp), csp


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.8-HEADERS-FRAME-ANCESTORS: GET /health CSP omits frame-ancestors "
        "(default deny except embedding features)"
    ),
)
def test_api_health_csp_includes_frame_ancestors(client: TestClient) -> None:
    response = client.get(_HEALTH)
    assert response.status_code == 200
    csp = _header_map(response).get("content-security-policy", "")
    assert "frame-ancestors" in csp.lower()


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6.8-HEADERS-REFERRER: GET /health responses omit Referrer-Policy",
)
def test_api_health_includes_referrer_policy(client: TestClient) -> None:
    response = client.get(_HEALTH)
    assert response.status_code == 200
    assert "referrer-policy" in _header_map(response)


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6.8-HEADERS-PERMISSIONS: GET /health responses omit Permissions-Policy",
)
def test_api_health_includes_permissions_policy(client: TestClient) -> None:
    response = client.get(_HEALTH)
    assert response.status_code == 200
    assert "permissions-policy" in _header_map(response)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.8-HEADERS-NOSNIFF: GET /health responses omit "
        "X-Content-Type-Options: nosniff"
    ),
)
def test_api_health_includes_nosniff(client: TestClient) -> None:
    response = client.get(_HEALTH)
    assert response.status_code == 200
    nosniff = _header_map(response).get("x-content-type-options", "")
    assert nosniff.lower() == "nosniff"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.8-HEADERS-WEB: apps/web/next.config.ts does not declare security "
        "headers for Next.js responses"
    ),
)
def test_next_config_declares_security_headers() -> None:
    text = _NEXT_CONFIG.read_text(encoding="utf-8")
    assert "headers" in text, "next.config.ts has no headers() hook"
    lowered = text.lower()
    for needle in (
        "strict-transport-security",
        "content-security-policy",
        "referrer-policy",
        "permissions-policy",
        "x-content-type-options",
    ):
        assert needle in lowered, f"missing {needle} in next.config.ts"
