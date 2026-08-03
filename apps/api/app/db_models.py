"""ORM models for the app metadata store (not Odoo)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Register account models on the same metadata (MON-1).
from app import account_models as _account_models  # noqa: F401
from app import billing_models as _billing_models  # noqa: F401


class OdooConnection(Base):
    __tablename__ = "odoo_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    db_name: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[str] = mapped_column(String(200), nullable=False)
    # Fernet ciphertext of password or API key
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    server_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_seen_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    upgrade_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    upgrade_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preview_theme_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    protected_manifest_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    protected_manifest_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
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


class HealthCheckRun(Base):
    """Post-upgrade artifact sweep report (TIER-4)."""

    __tablename__ = "health_check_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")  # auto|manual
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    # running | complete | failed
    previous_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ok_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    broken_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApprovalRule(Base):
    """Button approval rule — Community engine (app DB) or Studio mirror (TIER-5)."""

    __tablename__ = "approval_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    engine: Mapped[str] = mapped_column(String(20), nullable=False, default="community")
    # community | studio
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_model: Mapped[str] = mapped_column(String(200), nullable=False)
    button_method: Mapped[str] = mapped_column(String(200), nullable=False)
    button_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    steps_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deployed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    odoo_wrapper_action_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    odoo_view_inherit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    odoo_studio_rule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ApprovalEntry(Base):
    """Per-record approval audit trail (Community engine evidence + app audit)."""

    __tablename__ = "approval_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("approval_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_model: Mapped[str] = mapped_column(String(200), nullable=False)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending | approved | rejected
    approver_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BackgroundJob(Base):
    """Async sandbox/promote job status (in-process thread pool)."""

    __tablename__ = "background_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # sandbox|promote|health_check
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
    workspace_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
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
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # active | archived — slot counting (MON-2)
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


class BulkRun(Base):
    """Stored result payload for Bulk Suite operations (BLK shared schema)."""

    __tablename__ = "bulk_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    dry_run: Mapped[str] = mapped_column(String(5), nullable=False, default="yes")  # yes|no
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
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


class ExpertChunk(Base):
    """Version-tagged knowledge chunks for the Expert RAG assistant (EXP-1)."""

    __tablename__ = "expert_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    breadcrumb: Mapped[str] = mapped_column(String(500), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

