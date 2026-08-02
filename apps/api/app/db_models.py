"""ORM models for the app metadata store (not Odoo)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OdooConnection(Base):
    __tablename__ = "odoo_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    db_name: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[str] = mapped_column(String(200), nullable=False)
    # Fernet ciphertext of password or API key
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    server_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MetadataSnapshot(Base):
    """Point-in-time restore payload for reversible Odoo metadata mutations."""

    __tablename__ = "metadata_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # view|automation|server_action|field|module_zip
    resource_key: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g. view:123
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    reversible: Mapped[str] = mapped_column(String(20), nullable=False, default="yes")  # yes|partial|no
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SandboxValidation(Base):
    """Proof that a specific module zip passed Phase 6 sandbox install."""

    __tablename__ = "sandbox_validations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_name: Mapped[str] = mapped_column(String(120), nullable=False)
    zip_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PromotedModule(Base):
    """Modules promoted onto a connection (for uninstall / history)."""

    __tablename__ = "promoted_modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(40), nullable=False)  # filesystem|base_import_module
    zip_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    models_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of model names
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="installed")
    # installed | uninstalled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    uninstalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppApiKey(Base):
    """Hashed API keys that authorize callers of this app (not Odoo credentials)."""

    __tablename__ = "app_api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    """Append-only log of mutating API requests."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_key_prefix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BackgroundJob(Base):
    """Async sandbox/promote job status (in-process thread pool)."""

    __tablename__ = "background_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # sandbox|promote
    connection_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    # queued | running | succeeded | failed
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustomizationProject(Base):
    """Draft ModuleSpec-like project stored in app DB; Apply pushes models/fields via RPC."""

    __tablename__ = "customization_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spec_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # draft | applied
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EnvPipeline(Base):
    """Sandbox → staging → prod connection chain for module promote."""

    __tablename__ = "env_pipelines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    staging_connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prod_connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional dedicated sandbox Odoo connection; otherwise ephemeral Docker sandbox is used
    sandbox_connection_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PipelineHop(Base):
    """Record of a promote hop in an env pipeline."""

    __tablename__ = "pipeline_hops"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("env_pipelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hop: Mapped[str] = mapped_column(String(20), nullable=False)  # sandbox|staging|prod
    module_name: Mapped[str] = mapped_column(String(120), nullable=False)
    zip_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    connection_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    validation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="succeeded")
    # succeeded | failed
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

