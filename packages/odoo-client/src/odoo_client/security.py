"""Access rights (ir.model.access) and simple record rules (ir.rule) for Odoo 19."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


def _coerce_m2o(value: object) -> int | None:
    if value is False or value is None:
        return None
    if isinstance(value, (list, tuple)) and value:
        return int(value[0])
    return int(value)  # type: ignore[arg-type]


def _coerce_m2o_name(value: object) -> str | None:
    if value is False or value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return str(value[1])
    return None


def _coerce_bool(value: object) -> bool:
    return bool(value)


class GroupInfo(BaseModel):
    id: int
    name: str
    full_name: str | None = None
    share: bool = False


class AccessRightInfo(BaseModel):
    id: int
    name: str
    model: str
    model_id: int
    group_id: int | None = None
    group_name: str | None = None
    perm_read: bool = True
    perm_write: bool = False
    perm_create: bool = False
    perm_unlink: bool = False
    active: bool = True


class CreateAccessRightRequest(BaseModel):
    model: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    group_id: int | None = None  # None = applies to all (no group)
    perm_read: bool = True
    perm_write: bool = True
    perm_create: bool = True
    perm_unlink: bool = True
    active: bool = True


class RecordRuleInfo(BaseModel):
    id: int
    name: str
    model: str
    model_id: int
    domain_force: str | None = None
    group_ids: list[int] = Field(default_factory=list)
    perm_read: bool = True
    perm_write: bool = True
    perm_create: bool = True
    perm_unlink: bool = True
    active: bool = True
    global_: bool = Field(False, alias="global")

    model_config = {"populate_by_name": True}


class CreateRecordRuleRequest(BaseModel):
    model: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    domain_force: str = Field(
        ...,
        min_length=1,
        description="Odoo domain as string, e.g. [('create_uid','=',user.id)]",
    )
    group_ids: list[int] = Field(
        default_factory=list,
        description="Empty = global rule (all users subject to domain)",
    )
    perm_read: bool = True
    perm_write: bool = True
    perm_create: bool = True
    perm_unlink: bool = True
    active: bool = True

    @field_validator("domain_force")
    @classmethod
    def domain_looks_like_list(cls, value: str) -> str:
        stripped = value.strip()
        if not (stripped.startswith("[") and stripped.endswith("]")):
            raise ValueError("domain_force must be an Odoo domain list string, e.g. [('id','!=',False)]")
        return stripped


class UpdateAccessRightRequest(BaseModel):
    """Safe attrs for ir.model.access write (perm_* are booleans on Odoo 19)."""

    name: str | None = None
    group_id: int | None = None
    clear_group: bool = False  # set group_id to False (all users)
    perm_read: bool | None = None
    perm_write: bool | None = None
    perm_create: bool | None = None
    perm_unlink: bool | None = None
    active: bool | None = None


class UpdateRecordRuleRequest(BaseModel):
    name: str | None = None
    domain_force: str | None = None
    group_ids: list[int] | None = None
    perm_read: bool | None = None
    perm_write: bool | None = None
    perm_create: bool | None = None
    perm_unlink: bool | None = None
    active: bool | None = None

    @field_validator("domain_force")
    @classmethod
    def domain_looks_like_list(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not (stripped.startswith("[") and stripped.endswith("]")):
            raise ValueError("domain_force must be an Odoo domain list string, e.g. [('id','!=',False)]")
        return stripped
