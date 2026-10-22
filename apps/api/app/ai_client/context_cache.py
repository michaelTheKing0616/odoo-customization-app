"""Gemini / Vertex explicit context caching for large, stable system prefixes.

When a system instruction is big (catalogs, schema snapshots, long policies), it is uploaded
once as cachedContent and later requests reference it, so those tokens bill at the cached rate.
Any failure leaves the payload untouched.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from typing import Any
from urllib import request

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_names: dict[str, tuple[str, float]] = {}   # sha -> (cachedContent name, expiry); "" = negative
TTL_S = 3600


def _min_chars() -> int:
    return int(os.environ.get("INGENIUM_CTX_CACHE_MIN_CHARS", "16000"))


def apply_context_cache(provider: Any, chosen: str, payload: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("INGENIUM_CTX_CACHE", "on") == "off":
        return payload
    try:
        sys_text = payload["systemInstruction"]["parts"][0]["text"] or ""
    except (KeyError, IndexError, TypeError):
        return payload
    if len(sys_text) < _min_chars():
        return payload
    try:
        url, headers = provider._target(chosen)
    except Exception:  # noqa: BLE001
        return payload
    key = hashlib.sha256(f"{url}|{chosen}|{sys_text}".encode()).hexdigest()
    now = time.time()
    from app.ai_client import ai_cache
    with _lock:
        hit = _names.get(key)
    if hit and hit[1] > now:
        if not hit[0]:
            return payload
        ai_cache.bump("ctx_hits")
        return _use(payload, hit[0])
    if "/publishers/" in url:
        prefix, _ = url.split("/publishers/", 1)
        cc_url = prefix + "/cachedContents"
        model_ref = prefix.split("/v1/", 1)[1] + f"/publishers/google/models/{chosen}"
    else:
        cc_url = url.split("/models/", 1)[0] + "/cachedContents"
        model_ref = f"models/{chosen}"
    body = json.dumps({"model": model_ref, "systemInstruction": payload["systemInstruction"],
                       "ttl": f"{TTL_S}s"}).encode()
    try:
        req = request.Request(cc_url, data=body, headers={**headers, "Content-Type": "application/json"}, method="POST")
        with request.urlopen(req, timeout=30) as resp:  # noqa: S310 - provider endpoint
            name = json.loads(resp.read().decode()).get("name", "")
    except Exception as exc:  # noqa: BLE001
        logger.info("context cache create failed (%s); continuing uncached", exc)
        name = ""
    with _lock:
        _names[key] = (name, now + (TTL_S - 120 if name else 600))
    if not name:
        return payload
    ai_cache.bump("ctx_created")
    return _use(payload, name)


def _use(payload: dict[str, Any], name: str) -> dict[str, Any]:
    out = dict(payload)
    out.pop("systemInstruction", None)
    out["cachedContent"] = name
    return out
