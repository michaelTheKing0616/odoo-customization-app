"""Post-upgrade health sweep for tracked artifacts (TIER-4)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from odoo_client import OdooClient
from odoo_client.client import OdooClientError
from sqlalchemy.orm import Session

from app.bulk_suite.transitions import invalidate_discovery_cache
from app.db_models import CustomizationProject, HealthCheckRun, MetadataSnapshot, OdooConnection, PromotedModule
from app.jobs import create_job, enqueue
from app.spec_validate_live import validate_module_spec_live
from app.tier_matrix import invalidate_matrix_cache
from app.version_watch import clear_upgrade_flag

HealthStatus = Literal["ok", "broken", "skipped"]


@dataclass
class HealthCheckItem:
    artifact_id: str
    artifact_type: str
    label: str
    status: HealthStatus
    reason: str
    deep_link: str
    resource_type: str | None = None
    resource_key: str | None = None


@dataclass
class HealthCheckReport:
    connection_id: str
    previous_version: str | None
    current_version: str | None
    trigger: str
    ok_count: int = 0
    broken_count: int = 0
    skipped_count: int = 0
    items: list[HealthCheckItem] = field(default_factory=list)
    message: str = ""

    def add(self, item: HealthCheckItem) -> None:
        self.items.append(item)
        if item.status == "ok":
            self.ok_count += 1
        elif item.status == "broken":
            self.broken_count += 1
        else:
            self.skipped_count += 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def deep_link_for(
    connection_id: str,
    resource_type: str,
    resource_key: str,
    *,
    payload: dict[str, Any] | None = None,
) -> str:
    base = f"/connections/{connection_id}"
    payload = payload or {}

    if resource_type == "view":
        model = _payload_model(payload, "view")
        if model:
            return f"{base}/designer?model={model}"
        return f"{base}/designer"

    if resource_type in {"field", "model"}:
        model = _payload_model(payload, "field") or _payload_model(payload, "model")
        if model:
            return f"{base}?tab=fields&model={model}"
        return f"{base}?tab=fields"

    if resource_type in {"automation", "server_action", "ir_cron"}:
        return f"{base}/automations"

    if resource_type in {"menu", "action"}:
        return f"{base}/menus"

    if resource_type == "report":
        return f"{base}/reports"

    if resource_type in {"access", "rule"}:
        return f"{base}/access"

    if resource_type in {"config_parameter", "ir_default", "paperformat"}:
        return f"{base}/config"

    if resource_type in {"module_zip", "promoted_module"}:
        return base

    if resource_type == "applied_project":
        return f"{base}/projects"

    return base


def _parse_id_suffix(resource_key: str) -> int | None:
    m = re.search(r":(\d+)$", resource_key or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _payload_model(payload: dict[str, Any] | None, key: str) -> str | None:
    if not payload:
        return None
    block = payload.get(key)
    if isinstance(block, dict):
        model = block.get("model") or block.get("model_id")
        if isinstance(model, list) and len(model) >= 2:
            return str(model[1])
        if isinstance(model, str):
            return model
    return None


def _load_payload(row: MetadataSnapshot) -> dict[str, Any]:
    try:
        data = json.loads(row.payload_json)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _check_view(
    client: OdooClient,
    connection_id: str,
    row: MetadataSnapshot,
    payload: dict[str, Any],
) -> HealthCheckItem:
    vid = _parse_id_suffix(row.resource_key)
    label = row.label
    link = deep_link_for(connection_id, row.resource_type, row.resource_key, payload=payload)
    if vid is None:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=label,
            status="skipped",
            reason="Could not parse view id from snapshot key",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    try:
        views = client.execute_kw("ir.ui.view", "read", [[vid]], {"fields": ["id", "model", "type", "arch_db"]})
    except OdooClientError as exc:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=label,
            status="broken",
            reason=f"View #{vid} missing or unreadable: {exc}",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    if not views:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=label,
            status="broken",
            reason=f"View #{vid} not found in Odoo",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    view = views[0]
    model = view.get("model")
    vtype = view.get("type") or "form"
    if not model:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=label,
            status="broken",
            reason=f"View #{vid} has no model",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    try:
        client.execute_kw(model, "fields_view_get", [], {"view_type": vtype, "view_id": vid})
    except OdooClientError as exc:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=label,
            status="broken",
            reason=f"fields_view_get failed for {model}/{vtype}: {exc}",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    return HealthCheckItem(
        artifact_id=row.id,
        artifact_type="snapshot",
        label=label,
        status="ok",
        reason="View resolves and fields_view_get succeeded",
        deep_link=link,
        resource_type=row.resource_type,
        resource_key=row.resource_key,
    )


def _check_field(
    client: OdooClient,
    connection_id: str,
    row: MetadataSnapshot,
    payload: dict[str, Any],
) -> HealthCheckItem:
    fid = _parse_id_suffix(row.resource_key)
    link = deep_link_for(connection_id, row.resource_type, row.resource_key, payload=payload)
    if fid is None:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="skipped",
            reason="Could not parse field id",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    try:
        fields = client.execute_kw(
            "ir.model.fields",
            "read",
            [[fid]],
            {"fields": ["id", "name", "model", "state"]},
        )
    except OdooClientError as exc:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"Field #{fid} unreadable: {exc}",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    if not fields:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"Field #{fid} not found",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    return HealthCheckItem(
        artifact_id=row.id,
        artifact_type="snapshot",
        label=row.label,
        status="ok",
        reason=f"Field {fields[0].get('name')} on {fields[0].get('model')} exists",
        deep_link=link,
        resource_type=row.resource_type,
        resource_key=row.resource_key,
    )


def _check_automation(
    client: OdooClient,
    connection_id: str,
    row: MetadataSnapshot,
) -> HealthCheckItem:
    aid = _parse_id_suffix(row.resource_key)
    link = deep_link_for(connection_id, row.resource_type, row.resource_key)
    if aid is None:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="skipped",
            reason="Could not parse automation id",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    try:
        autos = client.execute_kw(
            "base.automation",
            "read",
            [[aid]],
            {"fields": ["id", "name", "model_id", "action_server_ids", "active"]},
        )
    except OdooClientError as exc:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"Automation #{aid} unreadable: {exc}",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    if not autos:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"Automation #{aid} not found",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    auto = autos[0]
    if not auto.get("model_id"):
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"Automation #{aid} has no model_id",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    action_ids = auto.get("action_server_ids") or []
    if action_ids:
        try:
            actions = client.execute_kw("ir.actions.server", "read", [action_ids], {"fields": ["id"]})
        except OdooClientError as exc:
            return HealthCheckItem(
                artifact_id=row.id,
                artifact_type="snapshot",
                label=row.label,
                status="broken",
                reason=f"Automation #{aid} server actions missing: {exc}",
                deep_link=link,
                resource_type=row.resource_type,
                resource_key=row.resource_key,
            )
        if len(actions) != len(action_ids):
            return HealthCheckItem(
                artifact_id=row.id,
                artifact_type="snapshot",
                label=row.label,
                status="broken",
                reason=f"Automation #{aid} references missing server actions",
                deep_link=link,
                resource_type=row.resource_type,
                resource_key=row.resource_key,
            )
    return HealthCheckItem(
        artifact_id=row.id,
        artifact_type="snapshot",
        label=row.label,
        status="ok",
        reason="Automation and action refs resolve",
        deep_link=link,
        resource_type=row.resource_type,
        resource_key=row.resource_key,
    )


def _check_record_by_id(
    client: OdooClient,
    connection_id: str,
    row: MetadataSnapshot,
    *,
    model: str,
    label_prefix: str,
) -> HealthCheckItem:
    rid = _parse_id_suffix(row.resource_key)
    link = deep_link_for(connection_id, row.resource_type, row.resource_key)
    if rid is None:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="skipped",
            reason=f"Could not parse {label_prefix} id",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    try:
        records = client.execute_kw(model, "read", [[rid]], {"fields": ["id", "name"]})
    except OdooClientError as exc:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"{label_prefix} #{rid} unreadable: {exc}",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    if not records:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"{label_prefix} #{rid} not found",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    return HealthCheckItem(
        artifact_id=row.id,
        artifact_type="snapshot",
        label=row.label,
        status="ok",
        reason=f"{label_prefix} #{rid} resolves",
        deep_link=link,
        resource_type=row.resource_type,
        resource_key=row.resource_key,
    )


def _check_model_snapshot(
    client: OdooClient,
    connection_id: str,
    row: MetadataSnapshot,
) -> HealthCheckItem:
    model = row.resource_key.split(":", 1)[-1] if ":" in row.resource_key else row.resource_key
    link = deep_link_for(connection_id, row.resource_type, row.resource_key)
    try:
        exists = client.model_exists(model)
    except OdooClientError as exc:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"Model {model} probe failed: {exc}",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    if not exists:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"Model {model} not found",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    return HealthCheckItem(
        artifact_id=row.id,
        artifact_type="snapshot",
        label=row.label,
        status="ok",
        reason=f"Model {model} exists",
        deep_link=link,
        resource_type=row.resource_type,
        resource_key=row.resource_key,
    )


def _check_report_snapshot(
    client: OdooClient,
    connection_id: str,
    row: MetadataSnapshot,
) -> HealthCheckItem:
    rid = _parse_id_suffix(row.resource_key)
    link = deep_link_for(connection_id, row.resource_type, row.resource_key)
    if rid is None:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="skipped",
            reason="Could not parse report id",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    try:
        reports = client.execute_kw(
            "ir.actions.report",
            "read",
            [[rid]],
            {"fields": ["id", "name", "model", "report_type"]},
        )
    except OdooClientError as exc:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"Report #{rid} unreadable: {exc}",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    if not reports:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="broken",
            reason=f"Report #{rid} not found",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )
    report = reports[0]
    model = report.get("model")
    if model:
        try:
            client.execute_kw(model, "fields_get", [], {"attributes": ["string"]})
        except OdooClientError as exc:
            return HealthCheckItem(
                artifact_id=row.id,
                artifact_type="snapshot",
                label=row.label,
                status="broken",
                reason=f"Report model {model} probe failed: {exc}",
                deep_link=link,
                resource_type=row.resource_type,
                resource_key=row.resource_key,
            )
    return HealthCheckItem(
        artifact_id=row.id,
        artifact_type="snapshot",
        label=row.label,
        status="ok",
        reason="Report action resolves",
        deep_link=link,
        resource_type=row.resource_type,
        resource_key=row.resource_key,
    )


def _check_snapshot(
    client: OdooClient,
    connection_id: str,
    row: MetadataSnapshot,
) -> HealthCheckItem:
    payload = _load_payload(row)
    rtype = row.resource_type

    if rtype == "view":
        return _check_view(client, connection_id, row, payload)
    if rtype == "field":
        return _check_field(client, connection_id, row, payload)
    if rtype == "automation":
        return _check_automation(client, connection_id, row)
    if rtype == "model":
        return _check_model_snapshot(client, connection_id, row)
    if rtype == "report":
        return _check_report_snapshot(client, connection_id, row)
    if rtype == "menu":
        return _check_record_by_id(client, connection_id, row, model="ir.ui.menu", label_prefix="Menu")
    if rtype == "action":
        return _check_record_by_id(
            client, connection_id, row, model="ir.actions.act_window", label_prefix="Action"
        )
    if rtype == "access":
        return _check_record_by_id(
            client, connection_id, row, model="ir.model.access", label_prefix="Access rule"
        )
    if rtype == "rule":
        return _check_record_by_id(client, connection_id, row, model="ir.rule", label_prefix="Record rule")
    if rtype == "server_action":
        return _check_record_by_id(
            client, connection_id, row, model="ir.actions.server", label_prefix="Server action"
        )
    if rtype == "ir_cron":
        return _check_record_by_id(
            client, connection_id, row, model="ir.cron", label_prefix="Scheduled action"
        )
    if rtype in {"config_parameter", "ir_default", "paperformat", "dedupe_merge"}:
        link = deep_link_for(connection_id, rtype, row.resource_key)
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="snapshot",
            label=row.label,
            status="skipped",
            reason=f"No live probe for snapshot type {rtype} (tracked only)",
            deep_link=link,
            resource_type=row.resource_type,
            resource_key=row.resource_key,
        )

    link = deep_link_for(connection_id, rtype, row.resource_key)
    return HealthCheckItem(
        artifact_id=row.id,
        artifact_type="snapshot",
        label=row.label,
        status="skipped",
        reason=f"Unknown snapshot type {rtype}",
        deep_link=link,
        resource_type=row.resource_type,
        resource_key=row.resource_key,
    )


def _check_promoted_module(
    client: OdooClient,
    connection_id: str,
    row: PromotedModule,
) -> HealthCheckItem:
    link = deep_link_for(connection_id, "promoted_module", row.module_name)
    if row.status != "installed":
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="promoted_module",
            label=row.module_name,
            status="skipped",
            reason=f"Module marked {row.status}",
            deep_link=link,
        )
    try:
        mods = client.execute_kw(
            "ir.module.module",
            "search_read",
            [[("name", "=", row.module_name)]],
            {"fields": ["name", "state"], "limit": 1},
        )
    except OdooClientError as exc:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="promoted_module",
            label=row.module_name,
            status="broken",
            reason=f"Module lookup failed: {exc}",
            deep_link=link,
        )
    if not mods or mods[0].get("state") not in {"installed", "to upgrade", "to remove"}:
        state = mods[0].get("state") if mods else "missing"
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="promoted_module",
            label=row.module_name,
            status="broken",
            reason=f"Promoted module not installed (state={state})",
            deep_link=link,
        )
    if row.models_json:
        try:
            models = json.loads(row.models_json)
        except json.JSONDecodeError:
            models = []
        for model in models if isinstance(models, list) else []:
            if not isinstance(model, str):
                continue
            try:
                if not client.model_exists(model):
                    return HealthCheckItem(
                        artifact_id=row.id,
                        artifact_type="promoted_module",
                        label=row.module_name,
                        status="broken",
                        reason=f"Model {model} from promoted module missing",
                        deep_link=link,
                    )
            except OdooClientError as exc:
                return HealthCheckItem(
                    artifact_id=row.id,
                    artifact_type="promoted_module",
                    label=row.module_name,
                    status="broken",
                    reason=f"Model {model} probe failed: {exc}",
                    deep_link=link,
                )
    return HealthCheckItem(
        artifact_id=row.id,
        artifact_type="promoted_module",
        label=row.module_name,
        status="ok",
        reason="Promoted module installed",
        deep_link=link,
    )


def _check_applied_project(
    client: OdooClient,
    connection_id: str,
    row: CustomizationProject,
) -> HealthCheckItem:
    link = deep_link_for(connection_id, "applied_project", row.id)
    try:
        spec = json.loads(row.spec_json)
    except json.JSONDecodeError:
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="applied_project",
            label=row.name,
            status="broken",
            reason="Project spec_json is invalid",
            deep_link=link,
        )
    if not isinstance(spec, dict):
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="applied_project",
            label=row.name,
            status="broken",
            reason="Project spec is not an object",
            deep_link=link,
        )
    result = validate_module_spec_live(client, spec)
    if result.fail_count > 0:
        first = next((i for i in result.items if i.status == "fail"), None)
        reason = first.message if first else f"{result.fail_count} validation failures"
        return HealthCheckItem(
            artifact_id=row.id,
            artifact_type="applied_project",
            label=row.name,
            status="broken",
            reason=reason,
            deep_link=link,
        )
    return HealthCheckItem(
        artifact_id=row.id,
        artifact_type="applied_project",
        label=row.name,
        status="ok",
        reason="Applied project spec validates on live Odoo",
        deep_link=link,
    )


def run_health_sweep(
    db: Session,
    *,
    connection_id: str,
    client: OdooClient,
    trigger: str = "manual",
    previous_version: str | None = None,
    current_version: str | None = None,
) -> HealthCheckReport:
    row = db.get(OdooConnection, connection_id)
    current_version = current_version or (row.server_version if row else None)
    report = HealthCheckReport(
        connection_id=connection_id,
        previous_version=previous_version,
        current_version=current_version,
        trigger=trigger,
    )

    invalidate_matrix_cache(connection_id)
    invalidate_discovery_cache(connection_id=connection_id)

    snapshots = (
        db.query(MetadataSnapshot)
        .filter(MetadataSnapshot.connection_id == connection_id)
        .order_by(MetadataSnapshot.created_at.desc())
        .all()
    )
    for snap in snapshots:
        report.add(_check_snapshot(client, connection_id, snap))

    promoted = (
        db.query(PromotedModule)
        .filter(PromotedModule.connection_id == connection_id)
        .order_by(PromotedModule.created_at.desc())
        .all()
    )
    for mod in promoted:
        report.add(_check_promoted_module(client, connection_id, mod))

    projects = (
        db.query(CustomizationProject)
        .filter(
            CustomizationProject.connection_id == connection_id,
            CustomizationProject.status == "applied",
        )
        .order_by(CustomizationProject.updated_at.desc())
        .all()
    )
    for project in projects:
        report.add(_check_applied_project(client, connection_id, project))

    if report.broken_count == 0:
        report.message = f"Health sweep complete — {report.ok_count} artifacts OK"
    else:
        report.message = (
            f"Health sweep found {report.broken_count} broken artifact(s) "
            f"of {report.ok_count + report.broken_count + report.skipped_count} checked"
        )
    return report


def _persist_run(
    db: Session,
    *,
    connection_id: str,
    job_id: str | None,
    trigger: str,
    report: HealthCheckReport,
    run_id: str | None = None,
) -> HealthCheckRun:
    run = HealthCheckRun(
        id=run_id or str(uuid.uuid4()),
        connection_id=connection_id,
        job_id=job_id,
        trigger=trigger,
        status="complete",
        previous_version=report.previous_version,
        current_version=report.current_version,
        ok_count=report.ok_count,
        broken_count=report.broken_count,
        report_json=json.dumps([asdict(i) for i in report.items]),
        message=report.message,
        finished_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def queue_health_check_job(
    db: Session,
    *,
    connection_id: str,
    trigger: str = "manual",
    previous_version: str | None = None,
    current_version: str | None = None,
) -> str:
    """Create background job + health_check run row; return job id."""
    run_id = str(uuid.uuid4())
    conn_row = db.get(OdooConnection, connection_id)
    pending = HealthCheckRun(
        id=run_id,
        connection_id=connection_id,
        trigger=trigger,
        status="running",
        previous_version=previous_version,
        current_version=current_version or (conn_row.server_version if conn_row else None),
        report_json="[]",
        message="Health sweep queued",
    )
    db.add(pending)
    job = create_job(db, kind="health_check", connection_id=connection_id)
    pending.job_id = job.id
    db.add(pending)
    db.commit()

    def _work() -> dict[str, Any]:
        from app.db import SessionLocal
        from app.odoo_service import client_from_connection, get_connection_or_404

        work_db = SessionLocal()
        try:
            row = get_connection_or_404(work_db, connection_id)
            client = client_from_connection(row)
            report = run_health_sweep(
                work_db,
                connection_id=connection_id,
                client=client,
                trigger=trigger,
                previous_version=previous_version,
                current_version=current_version or row.server_version,
            )
            run_row = work_db.get(HealthCheckRun, run_id)
            if run_row is not None:
                run_row.status = "complete"
                run_row.ok_count = report.ok_count
                run_row.broken_count = report.broken_count
                run_row.report_json = json.dumps([asdict(i) for i in report.items])
                run_row.message = report.message
                run_row.finished_at = datetime.now(timezone.utc)
                work_db.add(run_row)
                conn = work_db.get(OdooConnection, connection_id)
                if conn is not None:
                    clear_upgrade_flag(work_db, conn, observed_version=report.current_version)
                work_db.commit()
            return report.to_dict()
        except Exception as exc:  # noqa: BLE001
            run_row = work_db.get(HealthCheckRun, run_id)
            if run_row is not None:
                run_row.status = "failed"
                run_row.message = str(exc)[:500]
                run_row.finished_at = datetime.now(timezone.utc)
                work_db.add(run_row)
                work_db.commit()
            raise
        finally:
            work_db.close()

    enqueue(job.id, _work)
    return job.id


def run_health_check_sync(
    db: Session,
    *,
    connection_id: str,
    client: OdooClient,
    trigger: str = "manual",
    previous_version: str | None = None,
    current_version: str | None = None,
) -> HealthCheckRun:
    report = run_health_sweep(
        db,
        connection_id=connection_id,
        client=client,
        trigger=trigger,
        previous_version=previous_version,
        current_version=current_version,
    )
    run = _persist_run(
        db,
        connection_id=connection_id,
        job_id=None,
        trigger=trigger,
        report=report,
    )
    conn = db.get(OdooConnection, connection_id)
    if conn is not None:
        clear_upgrade_flag(db, conn, observed_version=report.current_version)
    return run
