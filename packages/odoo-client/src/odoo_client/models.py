"""Pydantic request/response models for Odoo RPC operations."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FieldType(str, Enum):
    CHAR = "char"
    TEXT = "text"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    SELECTION = "selection"
    MANY2ONE = "many2one"
    ONE2MANY = "one2many"
    MANY2MANY = "many2many"
    BINARY = "binary"
    HTML = "html"
    MONETARY = "monetary"
    JSON = "json"
    PROPERTIES = "properties"
    PROPERTIES_DEFINITION = "properties_definition"
    # Deprecated API/UI alias — Odoo has no ttype=related; use concrete ttype + related=.
    RELATED = "related"


class ConnectionConfig(BaseModel):
    """Connection parameters for a target Odoo instance."""

    url: str = Field(..., description="Base URL, e.g. http://127.0.0.1:8069")
    db: str
    username: str
    password: str = Field(..., description="Password or API key")
    timeout: float = 30.0

    @field_validator("url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


class ModelInfo(BaseModel):
    id: int
    model: str
    name: str
    state: str | None = None
    transient: bool = False


class ModuleInfo(BaseModel):
    id: int
    name: str
    shortdesc: str | None = None
    state: str
    application: bool = False

    @field_validator("shortdesc", mode="before")
    @classmethod
    def coerce_false_shortdesc(cls, value: object) -> str | None:
        if value is False or value is None:
            return None
        return str(value)


class FieldInfo(BaseModel):
    id: int
    name: str
    field_description: str
    ttype: str
    model_id: int | tuple[int, str] | None = None
    required: bool = False
    readonly: bool = False
    relation: str | None = None
    state: str | None = None
    help: str | None = None
    tracking: bool = False
    selection: str | None = None
    related: str | None = None
    currency_field: str | None = None
    relation_field: str | None = None

    @field_validator(
        "relation",
        "help",
        "selection",
        "related",
        "currency_field",
        "relation_field",
        mode="before",
    )
    @classmethod
    def coerce_false_optional_str(cls, value: object) -> str | None:
        # Odoo XML-RPC returns False for empty Many2one/Char-like empties.
        if value is False or value is None:
            return None
        return str(value)

    @field_validator("tracking", mode="before")
    @classmethod
    def coerce_tracking(cls, value: object) -> bool:
        return bool(value)


class ViewInfo(BaseModel):
    id: int
    name: str
    model: str
    type: str
    arch: str | None = None

    @field_validator("arch", mode="before")
    @classmethod
    def coerce_false_arch(cls, value: object) -> str | None:
        if value is False or value is None:
            return None
        return str(value)


class CreateModelRequest(BaseModel):
    """Create a custom model via ir.model (x_* convention)."""

    name: str = Field(..., description="Human-readable model name")
    model: str = Field(..., description="Technical name, must start with x_")
    transient: bool = False

    @field_validator("model")
    @classmethod
    def require_x_prefix(cls, value: str) -> str:
        if not value.startswith("x_"):
            raise ValueError("Custom model technical name must start with 'x_'")
        if not value.replace("_", "").isalnum():
            raise ValueError("Model name must be alphanumeric/underscore only")
        return value


class CreateFieldRequest(BaseModel):
    """Create a custom field via ir.model.fields."""

    model: str = Field(..., description="Technical model name, e.g. res.partner or x_thing")
    name: str = Field(..., description="Field name; must use x_ prefix (Studio-like)")
    field_description: str
    ttype: FieldType
    required: bool = False
    readonly: bool = False
    index: bool = False
    relation: str | None = None
    relation_field: str | None = None
    selection: str | None = Field(
        default=None,
        description="Selection options as Odoo expects, e.g. [('a','A'),('b','B')]",
    )
    help: str | None = None
    related: str | None = Field(
        default=None,
        description="Related field path, e.g. partner_id.country_id",
    )
    currency_field: str | None = Field(
        default=None,
        description="Currency field name for monetary (default currency_id in Odoo)",
    )
    on_delete: str | None = Field(
        default=None,
        description="Many2one on_delete: set null | restrict | cascade. "
        "Odoo 19 requires restrict|cascade when the field is required.",
    )
    definition_record: str | None = Field(
        default=None,
        description="M2O field name on same model linking to definition holder (properties fields).",
    )
    definition_record_field: str | None = Field(
        default=None,
        description="PropertiesDefinition field name on related parent model.",
    )

    @field_validator("name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        reserved = {"id", "create_uid", "create_date", "write_uid", "write_date", "display_name"}
        if value in reserved:
            raise ValueError(f"Field name '{value}' is reserved")
        if not value.startswith("x_"):
            raise ValueError("Custom field technical name must start with 'x_'")
        if not value.replace("_", "").isalnum():
            raise ValueError("Field name must be alphanumeric/underscore only")
        return value

    def validate_type_requirements(self) -> None:
        if self.ttype in {FieldType.MANY2ONE, FieldType.MANY2MANY, FieldType.ONE2MANY}:
            if not self.relation:
                raise ValueError(f"{self.ttype.value} fields require a relation model")
        if self.ttype == FieldType.ONE2MANY and not self.relation_field:
            raise ValueError("one2many fields require relation_field")
        if self.ttype == FieldType.SELECTION and not self.selection:
            raise ValueError("selection fields require selection options")
        if self.ttype == FieldType.RELATED and not self.related:
            raise ValueError("related fields require a related path")
        if self.ttype == FieldType.PROPERTIES:
            if not self.definition_record or not self.definition_record_field:
                raise ValueError(
                    "properties fields require definition_record and definition_record_field"
                )


class CreateViewRequest(BaseModel):
    """Create or replace a view via ir.ui.view."""

    name: str
    model: str
    type: str = Field(..., description="form | list | kanban | search | qweb | ...")
    arch: str
    priority: int = 16


class ExecuteKwResult(BaseModel):
    """Generic envelope when returning raw execute_kw payloads."""

    model: str
    method: str
    result: Any
