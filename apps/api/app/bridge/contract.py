"""Ingenium Bridge integration contract. Tier I fails closed.

Secrets stay on the Connection. A contract holds connection ids only.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Direction = Literal["inbound", "outbound", "two_way"]
Conflict = Literal["odoo_wins", "remote_wins", "manual"]
MoneyPolicy = Literal["odoo_wins", "remote_wins", "manual"]

_SECRET_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "smtp_pass",
        "authorization",
        "private_key",
    }
)


class ContractError(ValueError):
    """Tier I rejected the contract."""


class EntitySpec(BaseModel):
    name: str = Field(min_length=1)
    money: bool = False
    money_policy: MoneyPolicy | None = None


class IntegrationContract(BaseModel):
    odoo_connection_id: str = Field(min_length=1)
    third_party_connection_id: str = Field(min_length=1)
    direction: Direction
    conflict_resolution: Conflict | None = None
    webhook_signature_required: bool = True
    idempotency_key_field: str = Field(default="idempotency_key", min_length=1)
    entities: list[EntitySpec] = Field(min_length=1)

    @model_validator(mode="after")
    def tier_i(self) -> IntegrationContract:
        if self.odoo_connection_id == self.third_party_connection_id:
            raise ValueError("odoo and third-party connections must differ")
        if self.direction == "two_way" and self.conflict_resolution is None:
            raise ValueError("two_way requires conflict_resolution")
        if not self.webhook_signature_required:
            raise ValueError("webhook signature verification is required when the connector supports it")
        for entity in self.entities:
            if entity.money and entity.money_policy is None:
                raise ValueError(f"entity {entity.name} requires money_policy")
        return self


def _walk_secret_keys(obj: object, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            name = str(key).lower().replace("-", "_")
            here = f"{path}.{key}" if path else str(key)
            if name in _SECRET_KEYS:
                found.append(here)
            found.extend(_walk_secret_keys(value, here))
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            found.extend(_walk_secret_keys(item, f"{path}[{index}]"))
    return found


def validate_contract(payload: dict) -> IntegrationContract:
    """Tier I. Raises ContractError when the contract is incomplete or carries a secret."""
    if not isinstance(payload, dict):
        raise ContractError("contract must be an object")
    leaked = _walk_secret_keys(payload)
    if leaked:
        raise ContractError(
            "secrets belong on the Connection, not in the contract: " + ", ".join(leaked)
        )
    for banned in ("odoo_target", "third_party"):
        block = payload.get(banned)
        if isinstance(block, dict) and any(
            str(key).lower() in _SECRET_KEYS or str(key).lower() in {"url", "username"}
            for key in block
        ):
            raise ContractError(f"{banned} credentials must be a connection_id, not an inline block")
    try:
        return IntegrationContract.model_validate(payload)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc
