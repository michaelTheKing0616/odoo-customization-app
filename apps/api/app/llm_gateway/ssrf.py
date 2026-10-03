"""SSRF guard for a caller-supplied model base URL."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


class SsrfRejected(Exception):
    pass


_METADATA_HOSTS = frozenset({"metadata.google.internal", "metadata.google.com"})


_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def _blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT:
        return True
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def guard_base_url(
    url: str,
    *,
    resolve,
    allow_private_hosts: frozenset[str] = frozenset(),
) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"https", "http"} or not host or parsed.username or parsed.password:
        raise SsrfRejected("scheme or host")
    if host in _METADATA_HOSTS:
        raise SsrfRejected("metadata host")
    if parsed.scheme == "http" and host not in allow_private_hosts:
        raise SsrfRejected("http")
    try:
        addresses = list(resolve(host))
    except OSError as exc:
        raise SsrfRejected("resolve") from exc
    if not addresses:
        raise SsrfRejected("resolve")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if _blocked(ip) and host not in allow_private_hosts:
            raise SsrfRejected(f"blocked {ip}")
    return host
