"""Bridge B1: vault-backed secrets + live, read-only connect probes.

Secrets live encrypted in a Bridge-only vault namespace (separate from Code runner scripts),
so a script can never secret() a Bridge credential. Values are never returned or logged.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.bridge.gallery import BY_KEY, ProbeResult, evaluate_health
from app.code_runner import store
from app.crypto import decrypt_secret, encrypt_secret

Getter = Callable[..., httpx.Response]


def _vkey(workspace: str | None) -> str:
    return f"bridge_{workspace or 'local'}"


def put_secrets(
    workspace: str | None, key: str, values: dict[str, str], by: str | None
) -> list[str]:
    c = BY_KEY[key]
    allowed = set(c.secret_fields) | {"shop", "base_url", "realm", "access_token"}
    bad = [k for k in values if k not in allowed]
    if bad:
        raise ValueError("Unknown field(s) for " + c.name + ": " + ", ".join(bad))
    with store.lock():
        data = store.load("vault", _vkey(workspace), {})
        slot = data.setdefault(key, {})
        for k, v in values.items():
            if v:
                slot[k] = {"v": encrypt_secret(str(v)), "by": by, "at": time.time()}
        store.save("vault", _vkey(workspace), data)
    return sorted(slot)


def secret_names(workspace: str | None, key: str) -> list[dict[str, Any]]:
    slot = store.load("vault", _vkey(workspace), {}).get(key, {})
    return [{"name": k, "set_at": v.get("at")} for k, v in sorted(slot.items())]


def delete_secrets(workspace: str | None, key: str) -> bool:
    with store.lock():
        data = store.load("vault", _vkey(workspace), {})
        hit = data.pop(key, None) is not None
        store.save("vault", _vkey(workspace), data)
    return hit


def _secrets(workspace: str | None, key: str) -> dict[str, str]:
    slot = store.load("vault", _vkey(workspace), {}).get(key, {})
    return {k: decrypt_secret(v["v"]) for k, v in slot.items()}


# connector -> (base url builder, header builder). Read-only GETs only.
def _bearer(field: str) -> Callable[[dict[str, str]], dict[str, str]]:
    return lambda s: {"Authorization": "Bearer " + s.get(field, "")}


_PROBES: dict[
    str,
    tuple[
        Callable[[dict[str, str]], str], Callable[[dict[str, str]], dict[str, str]], tuple[str, ...]
    ],
] = {
    "shopify": (
        lambda s: "https://" + _shop_host(s.get("shop", "")) + "/admin/api/2024-10/shop.json",
        lambda s: {"X-Shopify-Access-Token": s.get("access_token", "")},
        ("shop", "access_token"),
    ),
    "woocommerce": (
        lambda s: s.get("base_url", "").rstrip("/") + "/wp-json/wc/v3/system_status",
        lambda s: {
            "Authorization": "Basic "
            + base64.b64encode(
                f"{s.get('consumer_key', '')}:{s.get('consumer_secret', '')}".encode()
            ).decode()
        },
        ("base_url", "consumer_key", "consumer_secret"),
    ),
    "stripe": (
        lambda s: "https://api.stripe.com/v1/balance",
        _bearer("secret_key"),
        ("secret_key",),
    ),
    "paystack": (
        lambda s: "https://api.paystack.co/balance",
        _bearer("secret_key"),
        ("secret_key",),
    ),
    "flutterwave": (
        lambda s: "https://api.flutterwave.com/v3/balances",
        _bearer("secret_key"),
        ("secret_key",),
    ),
    "hubspot": (
        lambda s: "https://api.hubapi.com/account-info/v3/details",
        _bearer("access_token"),
        ("access_token",),
    ),
    "slack": (lambda s: "https://slack.com/api/auth.test", _bearer("bot_token"), ("bot_token",)),
    "xero": (
        lambda s: "https://api.xero.com/connections",
        _bearer("access_token"),
        ("access_token",),
    ),
    "teams": (
        lambda s: "https://graph.microsoft.com/v1.0/me",
        _bearer("access_token"),
        ("access_token",),
    ),
}


def _shop_host(shop: str) -> str:
    h = shop.strip().split("://")[-1].split("/")[0].lower()
    return h if "." in h else h + ".myshopify.com"


def probe_remote(
    workspace: str | None, key: str, *, http_get: Getter | None = None
) -> list[ProbeResult]:
    if key not in _PROBES:
        return [ProbeResult("auth", False, None, "Live check not available yet for this connector")]
    url_f, hdr_f, need = _PROBES[key]
    s = _secrets(workspace, key)
    missing = [n for n in need if not s.get(n)]
    if missing:
        return [ProbeResult("auth", False, None, "Missing in vault: " + ", ".join(missing))]
    try:
        url = url_f(s)
        headers = {**hdr_f(s), "Accept": "application/json"}
        if http_get is not None:
            r = http_get(url, headers=headers)
        else:
            with httpx.Client(timeout=15.0) as cl:
                r = cl.get(url, headers=headers)
        st = int(r.status_code)
        hdrs = {
            k: v
            for k, v in r.headers.items()
            if "ratelimit" in k.lower() or "call-limit" in k.lower()
        }
        ok = st == 200
        if ok and key == "slack":
            try:
                ok = bool(r.json().get("ok"))
            except Exception:  # noqa: BLE001
                ok = False
    except Exception as exc:  # noqa: BLE001
        return [
            ProbeResult(
                "auth",
                False,
                None,
                "Could not reach " + BY_KEY[key].name + f" ({exc.__class__.__name__})",
            )
        ]
    return [ProbeResult("auth", ok, st, "", hdrs), ProbeResult("read", ok, st)]


def probe_odoo_side(client: Any) -> dict[str, Any]:
    from app.bridge.connections import ConnectionProbeError, probe_odoo

    try:
        p = probe_odoo(client)
        v = p["version"]
        ver = v.get("server_version") if isinstance(v, dict) else v
        return {"ok": True, "version": ver, "partners": p["search_count"]}
    except ConnectionProbeError as exc:
        return {"ok": False, "error": str(exc)}


def health(
    workspace: str | None,
    key: str,
    *,
    needed_entities: list[str] | None = None,
    odoo_client: Any | None = None,
    http_get: Getter | None = None,
) -> dict[str, Any]:
    probes = probe_remote(workspace, key, http_get=http_get)
    out = evaluate_health(key, probes, needed_entities=needed_entities)
    note = next(
        (
            p.detail
            for p in probes
            if p.detail
            and p.detail.startswith(("Missing in vault", "Live check", "Could not reach"))
        ),
        "",
    )
    if note:
        out["issues"] = [note] + [i for i in out["issues"] if not i.startswith("Sign-in failed")]
    if odoo_client is not None:
        out["odoo"] = probe_odoo_side(odoo_client)
        if not out["odoo"]["ok"]:
            out["issues"].append("Odoo check failed")
            out["status"] = "fail"
    return out
