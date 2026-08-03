"""NL → ModuleSpec draft via optional Ollama + domain packs. Never auto-applies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai_depth import AMBITION_TARGETS
from app.ai_ollama import (
    AiAssistUnavailable,
    ai_assist_enabled,
    draft_module_from_prompt,
    list_domain_packs,
    ollama_reachable,
)
from app.ai_rag import rag_status
from app.ai_self_consistency import self_consistency_status
from app.db import get_db
from app.llm_provider import llm_routing_status
from app.odoo_service import OdooClientError, client_from_connection, get_connection_or_404
from app.protected_modules import manifest_from_json
from app.schemas import AiDraftModuleBody, AiDraftModuleOut, ProtectedModuleRefusal
from app.settings import settings

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def ai_status() -> dict[str, object]:
    enabled = ai_assist_enabled()
    reachable = False
    detail = "disabled"
    if enabled:
        reachable, detail = ollama_reachable()
    rag = rag_status()
    routing = llm_routing_status()
    consistency = self_consistency_status()
    return {
        "ai_assist": settings.ai_assist,
        "enabled": enabled,
        "provider": settings.ai_assist,
        "pipeline_mode": settings.ai_pipeline_mode,
        "ai_critique": settings.ai_critique,
        "ai_self_consistency": consistency.get("ai_self_consistency"),
        "self_consistency": consistency,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "ai_model_bulk": routing.get("ai_model_bulk"),
        "ai_model_reasoning": routing.get("ai_model_reasoning"),
        "ai_thinking": routing.get("ai_thinking"),
        "llm_routing": routing,
        "openai_compatible_base_url": settings.openai_compatible_base_url or None,
        "openai_compatible_model": settings.openai_compatible_model,
        "ollama_reachable": reachable,
        "ollama_detail": detail,
        "domain_packs": [p["id"] for p in list_domain_packs()],
        "depth_floors": AMBITION_TARGETS,
        "rag": rag,
    }


def _load_reuse_catalog(
    db: Session,
    body: AiDraftModuleBody,
) -> tuple[list[str] | None, list[str] | None, list[dict], list[dict]]:
    available: list[str] | None = None
    installed: list[str] | None = None
    reuse_views: list[dict] = []
    reuse_actions: list[dict] = []
    if not body.connection_id:
        return available, installed, reuse_views, reuse_actions
    try:
        conn = get_connection_or_404(db, body.connection_id)
        client = client_from_connection(conn)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        models = client.list_models(limit=500)
        available = [m.model for m in models]
        for preferred in (
            "res.partner",
            "res.users",
            "product.product",
            "account.move",
            "calendar.event",
            "project.project",
            "hr.employee",
        ):
            if preferred in available:
                available.remove(preferred)
                available.insert(0, preferred)
    except Exception:  # noqa: BLE001
        available = []

    try:
        from app.capabilities import sample_installed_modules

        installed = sample_installed_modules(client, limit=300)
    except Exception:  # noqa: BLE001
        installed = []

    if body.reuse_view_ids:
        try:
            rows = client.execute_kw(
                "ir.ui.view",
                "read",
                [body.reuse_view_ids],
                {"fields": ["name", "model", "type"]},
            )
            reuse_views = [
                {
                    "id": int(r["id"]),
                    "name": r.get("name"),
                    "model": r.get("model"),
                    "type": r.get("type"),
                }
                for r in rows
            ]
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail=f"Failed to load reuse views: {exc}"
            ) from exc

    if body.reuse_action_ids:
        try:
            rows = client.execute_kw(
                "ir.actions.act_window",
                "read",
                [body.reuse_action_ids],
                {"fields": ["name", "res_model", "view_mode"]},
            )
            reuse_actions = [
                {
                    "id": int(r["id"]),
                    "name": r.get("name"),
                    "model": r.get("res_model"),
                    "view_mode": r.get("view_mode"),
                }
                for r in rows
            ]
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail=f"Failed to load reuse actions: {exc}"
            ) from exc

    return available, installed, reuse_views, reuse_actions


@router.get("/component-gallery")
def component_gallery() -> list[dict[str, str]]:
    from app.component_gallery import list_gallery

    return list_gallery()


@router.post("/draft-module", response_model=AiDraftModuleOut)
def draft_module(
    body: AiDraftModuleBody, db: Session = Depends(get_db)
) -> AiDraftModuleOut:
    available, installed, reuse_views, reuse_actions = _load_reuse_catalog(db, body)
    protected_manifest = None
    odoo_version = None
    odoo_client = None
    if body.connection_id:
        try:
            conn = get_connection_or_404(db, body.connection_id)
            protected_manifest = manifest_from_json(
                getattr(conn, "protected_manifest_json", None)
            )
            odoo_version = getattr(conn, "server_version", None) or getattr(
                conn, "protected_manifest_version", None
            )
            try:
                odoo_client = client_from_connection(conn)
            except OdooClientError:
                odoo_client = None
        except LookupError:
            protected_manifest = None
    try:
        draft, raw, warnings, refusals = draft_module_from_prompt(
            body.prompt,
            available_models=available,
            installed_modules=installed,
            reuse_models=body.reuse_models or None,
            reuse_views=reuse_views or None,
            reuse_actions=reuse_actions or None,
            expand=body.expand,
            pipeline=body.pipeline,
            protected_manifest=protected_manifest,
            odoo_version=odoo_version,
            grain_override=body.grain,
            gallery_id=body.gallery_id,
            host_model_override=body.host_model,
            connect_points_override=body.connect_points,
            client=odoo_client,
        )
    except AiAssistUnavailable as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI draft failed: {exc}") from exc

    domain_pack = draft.get("domain_pack") if isinstance(draft, dict) else None
    return AiDraftModuleOut(
        ok=True,
        draft=draft,
        raw_response=raw,
        warnings=warnings,
        refusals=[ProtectedModuleRefusal(**r) for r in refusals if isinstance(r, dict)],
        domain_pack=str(domain_pack) if domain_pack else None,
        grain=str(draft.get("grain")) if isinstance(draft, dict) and draft.get("grain") else None,
        grain_label=str(draft.get("grain_label")) if draft.get("grain_label") else None,
        connect_points=draft.get("connect_points")
        if isinstance(draft.get("connect_points"), dict)
        else None,
        host_candidates=list(draft.get("host_candidates") or [])
        if isinstance(draft, dict)
        else [],
    )
