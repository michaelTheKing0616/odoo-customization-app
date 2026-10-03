"""Shopify connector. Webhook signatures use HMAC-SHA256, base64-encoded."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, Protocol


class Connector(Protocol):
    def fetch(self, entity: str, *, cursor: str | None = None) -> dict[str, Any]: ...

    def create(self, entity: str, body: dict[str, Any]) -> dict[str, Any]: ...

    def update(self, entity: str, remote_id: str, body: dict[str, Any]) -> dict[str, Any]: ...

    def declared_schema(self) -> dict[str, list[str]]: ...

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool: ...

    def parse_webhook_event(self, body: bytes) -> dict[str, Any]: ...


class ShopifyConnector:
    """Shopify Admin webhook verification. This class does not call the network."""

    def __init__(self, *, webhook_secret: str) -> None:
        if not webhook_secret:
            raise ValueError("webhook secret is required")
        self._secret = webhook_secret

    def fetch(self, entity: str, *, cursor: str | None = None) -> dict[str, Any]:
        if entity not in self.declared_schema():
            raise ValueError(f"unknown entity {entity}")
        return {"entity": entity, "items": [], "cursor": cursor}

    def create(self, entity: str, body: dict[str, Any]) -> dict[str, Any]:
        self._require_entity(entity, body)
        return {"entity": entity, "id": body.get("id"), "created": body}

    def update(self, entity: str, remote_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._require_entity(entity, body)
        return {"entity": entity, "id": remote_id, "updated": body}

    def declared_schema(self) -> dict[str, list[str]]:
        return {
            "orders": ["id", "name", "email", "total_price", "financial_status"],
            "products": ["id", "title", "status"],
        }

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        if not signature or not body:
            return False
        digest = hmac.new(self._secret.encode("utf-8"), body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(expected, signature.strip())

    def parse_webhook_event(self, body: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("malformed webhook body") from exc
        if not isinstance(payload, dict) or "id" not in payload:
            raise ValueError("malformed webhook body")
        event_id = str(payload["id"])
        return {"id": event_id, "idempotency_key": f"shopify:{event_id}", "payload": payload}

    def _require_entity(self, entity: str, body: dict[str, Any]) -> None:
        fields = self.declared_schema().get(entity)
        if fields is None:
            raise ValueError(f"unknown entity {entity}")
        missing = [name for name in fields if name not in body]
        if missing:
            raise ValueError("missing fields: " + ", ".join(missing))
