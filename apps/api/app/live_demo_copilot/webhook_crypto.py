"""Attendee webhook HMAC verification + payload hashing for replay protection."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any


def canonical_payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload_json(payload).encode("utf-8")).hexdigest()


def meeting_url_sha256(meeting_url: str) -> str:
    return hashlib.sha256(meeting_url.strip().encode("utf-8")).hexdigest()


def sign_payload(payload: dict[str, Any], webhook_secret_b64: str) -> str:
    """Return base64 HMAC-SHA256 of canonical JSON using Attendee's base64 webhook secret."""
    secret = base64.b64decode(webhook_secret_b64)
    digest = hmac.new(
        secret,
        canonical_payload_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_signature(payload: dict[str, Any], webhook_secret_b64: str, signature_header: str) -> bool:
    if not webhook_secret_b64 or not signature_header:
        return False
    expected = sign_payload(payload, webhook_secret_b64)
    return hmac.compare_digest(expected, signature_header.strip())
