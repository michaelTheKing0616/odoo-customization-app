"""Enterprise-installed module RPC playbooks (mastery M5) — public models only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404

router = APIRouter(prefix="/connections/{connection_id}/ee-playbooks", tags=["ee-playbooks"])

# Technical module name → playbook metadata (never requires Studio source).
PLAYBOOKS: list[dict[str, Any]] = [
    {
        "id": "sign_templates",
        "name": "Sign templates",
        "requires_modules": ["sign"],
        "models": ["sign.template", "sign.request"],
        "description": "List Sign templates via public ORM when Sign is installed.",
    },
    {
        "id": "documents_folders",
        "name": "Documents folders",
        "requires_modules": ["documents"],
        "models": ["documents.document", "documents.folder"],
        "description": "List Documents folders/workspace roots when Documents is installed.",
    },
    {
        "id": "studio_presence",
        "name": "Studio presence warn",
        "requires_modules": ["web_studio"],
        "models": [],
        "description": (
            "Detect Studio modules — warn only; this app never uses Studio UI/source."
        ),
        "warn_only": True,
    },
    {
        "id": "spreadsheet_dashboard",
        "name": "Spreadsheet dashboards",
        "requires_modules": ["spreadsheet_dashboard"],
        "requires_any_modules": ["spreadsheet_dashboard", "spreadsheet"],
        "models": ["spreadsheet.dashboard"],
        "description": "List spreadsheet.dashboard rows when Spreadsheet Dashboard is installed.",
    },
    {
        "id": "voip",
        "name": "VoIP phonecalls",
        "requires_modules": ["voip"],
        "models": ["voip.phonecall"],
        "description": "List voip.phonecall when VoIP is installed; detect-only if model missing.",
    },
    {
        "id": "iot",
        "name": "IoT devices",
        "requires_modules": ["iot"],
        "models": ["iot.device"],
        "description": "List iot.device when IoT is installed; detect-only if model missing.",
    },
    {
        "id": "account_accountant",
        "name": "Accounting (EE) presence",
        "requires_modules": ["account_accountant"],
        "requires_any_modules": ["account_accountant", "accountant"],
        "models": [],
        "description": (
            "Detect Accounting EE / accountant module — warn/list honesty only; "
            "chart of accounts remains Community account.* when present."
        ),
        "warn_only": True,
    },
    {
        "id": "hr_payroll",
        "name": "Payroll presence",
        "requires_modules": ["hr_payroll"],
        "models": [],
        "description": "Detect hr_payroll — warn only; no payroll mutation via this playbook.",
        "warn_only": True,
    },
]


def _client(connection_id: str, db: Session):
    try:
        row = get_connection_or_404(db, connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return client_from_connection(row)
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _module_state(client: Any, name: str) -> str | None:
    rows = client.execute_kw(
        "ir.module.module",
        "search_read",
        [[("name", "=", name)]],
        {"fields": ["state"], "limit": 1},
    )
    if not rows:
        return None
    return str(rows[0].get("state") or "")


class PlaybookOut(BaseModel):
    id: str
    name: str
    description: str
    requires_modules: list[str]
    available: bool
    reason: str
    warn_only: bool = False


@router.get("", response_model=list[PlaybookOut])
def list_playbooks(connection_id: str, db: Session = Depends(get_db)) -> list[PlaybookOut]:
    client = _client(connection_id, db)
    out: list[PlaybookOut] = []
    for pb in PLAYBOOKS:
        any_mods = pb.get("requires_any_modules") or pb["requires_modules"]
        missing: list[str] = []
        installed_any = False
        for mod in any_mods:
            state = _module_state(client, mod)
            if state in {"installed", "to upgrade", "to remove"}:
                installed_any = True
            else:
                missing.append(f"{mod}={state or 'absent'}")
        # When requires_any_modules: any one installed is enough.
        if pb.get("requires_any_modules"):
            available = installed_any
            reason = (
                "RPC available"
                if available
                else f"Modules not installed: {', '.join(missing)}"
            )
        else:
            available = not missing
            reason = (
                "RPC available"
                if available
                else f"Modules not installed: {', '.join(missing)}"
            )
        if pb.get("warn_only") and available:
            if pb["id"] == "studio_presence":
                reason = (
                    "Studio-related module installed — metadata via public ORM only; "
                    "Studio source never used."
                )
            elif pb["id"] == "account_accountant":
                reason = (
                    "Accounting EE / accountant detected — chart honesty via Community "
                    "account.* models when present; no EE-only mutation here."
                )
            elif pb["id"] == "hr_payroll":
                reason = "hr_payroll installed — detect only; no payroll writes via playbook."
            else:
                reason = "Module present — warn/detect only"
        out.append(
            PlaybookOut(
                id=pb["id"],
                name=pb["name"],
                description=pb["description"],
                requires_modules=list(pb["requires_modules"]),
                available=available,
                reason=reason,
                warn_only=bool(pb.get("warn_only")),
            )
        )
    return out


class SignTemplateOut(BaseModel):
    id: int
    name: str | None = None


@router.get("/sign/templates", response_model=list[SignTemplateOut])
def list_sign_templates(
    connection_id: str, db: Session = Depends(get_db)
) -> list[SignTemplateOut]:
    client = _client(connection_id, db)
    if _module_state(client, "sign") not in {"installed", "to upgrade", "to remove"}:
        raise HTTPException(
            status_code=404,
            detail="Sign module not installed — playbook greyed out",
        )
    if not client.model_exists("sign.template"):
        raise HTTPException(status_code=404, detail="Model sign.template not found")
    try:
        rows = client.execute_kw(
            "sign.template",
            "search_read",
            [[]],
            {"fields": ["name"], "limit": 100, "order": "id desc"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [SignTemplateOut(id=int(r["id"]), name=r.get("name")) for r in rows]


class DocumentsFolderOut(BaseModel):
    id: int
    name: str | None = None


@router.get("/documents/folders", response_model=list[DocumentsFolderOut])
def list_documents_folders(
    connection_id: str, db: Session = Depends(get_db)
) -> list[DocumentsFolderOut]:
    client = _client(connection_id, db)
    if _module_state(client, "documents") not in {"installed", "to upgrade", "to remove"}:
        raise HTTPException(
            status_code=404,
            detail="Documents module not installed — playbook greyed out",
        )
    model = "documents.folder" if client.model_exists("documents.folder") else None
    if model is None and client.model_exists("documents.document"):
        # Fallback: some versions expose folders differently — refuse dishonestly mapping.
        raise HTTPException(
            status_code=404,
            detail="documents.folder model not found on this major",
        )
    if model is None:
        raise HTTPException(status_code=404, detail="Documents folder model not found")
    try:
        rows = client.execute_kw(
            model,
            "search_read",
            [[]],
            {"fields": ["name"], "limit": 100, "order": "id desc"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [DocumentsFolderOut(id=int(r["id"]), name=r.get("name")) for r in rows]


class ProbeModulesBody(BaseModel):
    modules: list[str] = Field(
        default_factory=lambda: [
            "sign",
            "documents",
            "web_studio",
            "spreadsheet_dashboard",
            "spreadsheet",
            "voip",
            "iot",
            "account_accountant",
            "accountant",
            "hr_payroll",
        ]
    )


@router.post("/probe-modules")
def probe_modules(
    connection_id: str, body: ProbeModulesBody, db: Session = Depends(get_db)
) -> dict[str, str | None]:
    client = _client(connection_id, db)
    return {m: _module_state(client, m) for m in body.modules}


class NamedRowOut(BaseModel):
    id: int
    name: str | None = None


def _require_any_module(client: Any, modules: list[str], label: str) -> str:
    for mod in modules:
        if _module_state(client, mod) in {"installed", "to upgrade", "to remove"}:
            return mod
    raise HTTPException(
        status_code=404,
        detail=f"{label} module not installed — playbook greyed out",
    )


@router.get("/spreadsheet/dashboards", response_model=list[NamedRowOut])
def list_spreadsheet_dashboards(
    connection_id: str, db: Session = Depends(get_db)
) -> list[NamedRowOut]:
    client = _client(connection_id, db)
    _require_any_module(client, ["spreadsheet_dashboard", "spreadsheet"], "Spreadsheet")
    if not client.model_exists("spreadsheet.dashboard"):
        raise HTTPException(status_code=404, detail="Model spreadsheet.dashboard not found")
    try:
        rows = client.execute_kw(
            "spreadsheet.dashboard",
            "search_read",
            [[]],
            {"fields": ["name"], "limit": 100, "order": "id desc"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [NamedRowOut(id=int(r["id"]), name=r.get("name")) for r in rows]


class SignRequestCreateBody(BaseModel):
    template_id: int
    res_model: str
    res_id: int
    reference: str | None = None


class SignRequestOut(BaseModel):
    id: int
    name: str | None = None
    state: str | None = None
    note: str | None = None


@router.post("/sign/requests", response_model=SignRequestOut, status_code=201)
def create_sign_request(
    connection_id: str, body: SignRequestCreateBody, db: Session = Depends(get_db)
) -> SignRequestOut:
    """Create a sign.request from a template + record — verified: pending-live field subset."""
    client = _client(connection_id, db)
    if _module_state(client, "sign") not in {"installed", "to upgrade", "to remove"}:
        raise HTTPException(status_code=404, detail="Sign module not installed — playbook greyed out")
    if not client.model_exists("sign.request"):
        raise HTTPException(status_code=404, detail="Model sign.request not found")
    if not client.model_exists("sign.template"):
        raise HTTPException(status_code=404, detail="Model sign.template not found")
    templates = client.execute_kw(
        "sign.template",
        "read",
        [[body.template_id]],
        {"fields": ["id", "name"]},
    )
    if not templates:
        raise HTTPException(status_code=404, detail=f"Sign template #{body.template_id} not found")
    fields = client.execute_kw("sign.request", "fields_get", [], {"attributes": ["type"]})
    vals: dict[str, Any] = {"template_id": body.template_id}
    if "reference_doc" in fields:
        vals["reference_doc"] = f"{body.res_model},{body.res_id}"
    elif "reference" in fields:
        vals["reference"] = body.reference or f"{body.res_model},{body.res_id}"
    try:
        req_id = client.execute_kw("sign.request", "create", [vals])
        rows = client.execute_kw(
            "sign.request",
            "read",
            [[int(req_id)]],
            {"fields": ["id", "name", "state"]},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = rows[0] if rows else {"id": int(req_id)}
    return SignRequestOut(
        id=int(row["id"]),
        name=row.get("name"),
        state=row.get("state"),
        note="[SKIPPED-LIVE-VERIFY] sign.request create field map not fully verified on Enterprise.",
    )


class DocumentsAttachBody(BaseModel):
    folder_id: int
    res_model: str
    res_id: int


class DocumentsAttachOut(BaseModel):
    attached: int
    document_ids: list[int] = Field(default_factory=list)
    note: str | None = None


@router.post("/documents/attach", response_model=DocumentsAttachOut)
def attach_record_to_documents_folder(
    connection_id: str, body: DocumentsAttachBody, db: Session = Depends(get_db)
) -> DocumentsAttachOut:
    """Link record attachments into a Documents folder — module-gated."""
    client = _client(connection_id, db)
    if _module_state(client, "documents") not in {"installed", "to upgrade", "to remove"}:
        raise HTTPException(
            status_code=404,
            detail="Documents module not installed — playbook greyed out",
        )
    folder_model = "documents.folder" if client.model_exists("documents.folder") else None
    if folder_model is None:
        raise HTTPException(status_code=404, detail="documents.folder model not found on this major")
    doc_model = "documents.document" if client.model_exists("documents.document") else None
    if doc_model is None:
        raise HTTPException(status_code=404, detail="documents.document model not found")
    folders = client.execute_kw(folder_model, "read", [[body.folder_id]], {"fields": ["id", "name"]})
    if not folders:
        raise HTTPException(status_code=404, detail=f"Folder #{body.folder_id} not found")
    attachments = client.execute_kw(
        "ir.attachment",
        "search_read",
        [[("res_model", "=", body.res_model), ("res_id", "=", body.res_id)]],
        {"fields": ["id", "name", "datas"], "limit": 50},
    )
    if not attachments:
        return DocumentsAttachOut(
            attached=0,
            note="No ir.attachment rows on the record to copy into Documents.",
        )
    created_ids: list[int] = []
    doc_fields = client.execute_kw(doc_model, "fields_get", [], {"attributes": ["type"]})
    for att in attachments:
        vals: dict[str, Any] = {"name": att.get("name") or "Attachment", "folder_id": body.folder_id}
        if "attachment_id" in doc_fields:
            vals["attachment_id"] = att["id"]
        elif "datas" in doc_fields and att.get("datas"):
            vals["datas"] = att["datas"]
        try:
            doc_id = client.execute_kw(doc_model, "create", [vals])
            created_ids.append(int(doc_id))
        except OdooClientError:
            continue
    return DocumentsAttachOut(
        attached=len(created_ids),
        document_ids=created_ids,
        note=(
            "[SKIPPED-LIVE-VERIFY] documents.document create field map not fully verified on Enterprise."
            if created_ids
            else "No documents created — field map may differ on this major."
        ),
    )


@router.get("/voip/phonecalls", response_model=list[NamedRowOut])
def list_voip_phonecalls(
    connection_id: str, db: Session = Depends(get_db)
) -> list[NamedRowOut]:
    client = _client(connection_id, db)
    _require_any_module(client, ["voip"], "VoIP")
    if not client.model_exists("voip.phonecall"):
        raise HTTPException(
            status_code=404,
            detail="VoIP installed but voip.phonecall model not found on this major",
        )
    try:
        rows = client.execute_kw(
            "voip.phonecall",
            "search_read",
            [[]],
            {"fields": ["name"], "limit": 100, "order": "id desc"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [NamedRowOut(id=int(r["id"]), name=r.get("name")) for r in rows]


@router.get("/iot/devices", response_model=list[NamedRowOut])
def list_iot_devices(
    connection_id: str, db: Session = Depends(get_db)
) -> list[NamedRowOut]:
    client = _client(connection_id, db)
    _require_any_module(client, ["iot"], "IoT")
    if not client.model_exists("iot.device"):
        raise HTTPException(
            status_code=404,
            detail="IoT installed but iot.device model not found on this major",
        )
    try:
        rows = client.execute_kw(
            "iot.device",
            "search_read",
            [[]],
            {"fields": ["name"], "limit": 100, "order": "id desc"},
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [NamedRowOut(id=int(r["id"]), name=r.get("name")) for r in rows]
