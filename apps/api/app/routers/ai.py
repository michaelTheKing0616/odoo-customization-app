"""NL → ModuleSpec draft via optional Ollama + domain packs. Never auto-applies."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field

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
from app.protected_enforcement import normalize_refusal_dict
from app.protected_modules import manifest_from_json
from app.schemas import (
    AiCheckOverlapBody,
    AiCheckOverlapOut,
    AiDraftModuleBody,
    AiDraftModuleOut,
    AiProposeConnectPointsBody,
    AiProposeConnectPointsOut,
    GeneralizeComponentBody,
    ProtectedModuleRefusal,
)
from app.settings import settings

router = APIRouter(prefix="/ai", tags=["ai"])


class GeneralizePackBody(BaseModel):
    spec_json: dict[str, Any]
    consent_share_template: bool = False
    pack_slug: str | None = None
    use_llm: bool = False


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


@router.post("/check-overlap", response_model=AiCheckOverlapOut)
def check_overlap_route(body: AiCheckOverlapBody, db: Session = Depends(get_db)) -> AiCheckOverlapOut:
    from app.ai_overlap import check_overlap

    available: list[str] | None = None
    installed: list[str] | None = None
    available_odoo_modules: list[str] | None = None
    client = None
    projects: list[dict] = []
    if body.connection_id:
        available, installed, _views, _actions = _load_reuse_catalog(
            db,
            AiDraftModuleBody(prompt=body.prompt, connection_id=body.connection_id),
        )
        try:
            conn = get_connection_or_404(db, body.connection_id)
            client = client_from_connection(conn)
        except (LookupError, OdooClientError):
            client = None
        try:
            from app.db_models import CustomizationProject

            rows = (
                db.query(CustomizationProject)
                .filter(CustomizationProject.connection_id == body.connection_id)
                .order_by(CustomizationProject.updated_at.desc())
                .limit(50)
                .all()
            )
            for row in rows:
                import json

                try:
                    spec = json.loads(row.spec_json or "{}")
                except json.JSONDecodeError:
                    spec = {}
                projects.append(
                    {
                        "id": row.id,
                        "name": row.name,
                        "updated_at": row.updated_at,
                        "spec_json": spec if isinstance(spec, dict) else {},
                    }
                )
        except Exception:  # noqa: BLE001
            projects = []
        if client is not None:
            try:
                rows = client.execute_kw(
                    "ir.module.module",
                    "search_read",
                    [[("state", "in", ["uninstalled", "to install", "to upgrade"])]],
                    {"fields": ["name"], "limit": 300},
                )
                available_odoo_modules = [str(r["name"]) for r in rows if r.get("name")]
            except Exception:  # noqa: BLE001
                available_odoo_modules = None

    result = check_overlap(
        body.prompt,
        grain=body.grain,  # type: ignore[arg-type]
        host_model=body.host_model,
        connection_id=body.connection_id,
        client=client,
        available_models=available,
        installed_modules=installed,
        available_odoo_modules=available_odoo_modules,
        projects=projects,
    )
    return AiCheckOverlapOut(**result)


@router.post("/propose-connect-points", response_model=AiProposeConnectPointsOut)
def propose_connect_points_route(
    body: AiProposeConnectPointsBody, db: Session = Depends(get_db)
) -> AiProposeConnectPointsOut:
    from app.ai_component_builder import preview_connect_points
    from app.ai_grain import classify_grain

    available: list[str] | None = None
    if body.connection_id:
        available, _installed, _views, _actions = _load_reuse_catalog(
            db,
            AiDraftModuleBody(
                prompt=body.prompt,
                connection_id=body.connection_id,
            ),
        )
    grain = body.grain or classify_grain(body.prompt)
    preview = preview_connect_points(
        body.prompt,
        grain=grain,  # type: ignore[arg-type]
        available_models=available,
        gallery_id=body.gallery_id,
        host_model_override=body.host_model,
        connect_points_override=body.connect_points,
    )
    return AiProposeConnectPointsOut(
        grain=str(preview["grain"]),
        grain_label=str(preview["grain_label"]),
        connect_points=preview.get("connect_points")
        if isinstance(preview.get("connect_points"), dict)
        else None,
        host_candidates=list(preview.get("host_candidates") or []),
        requires_review=bool(preview.get("requires_review")),
        warnings=list(preview.get("warnings") or []),
        gallery_id=preview.get("gallery_id"),
    )


@router.post("/generalize-component")
def generalize_component(body: GeneralizeComponentBody) -> dict[str, object]:
    if not body.consent_share_template:
        raise HTTPException(
            status_code=403,
            detail={
                "requires_consent": True,
                "message": "Set consent_share_template=true to export a component template.",
            },
        )
    from app.ai_pack_generalizer import generalize_spec_to_component_template

    try:
        result = generalize_spec_to_component_template(
            body.spec_json,
            host_slot=body.host_slot or "any",
            pack_slug=body.pack_slug,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, **result}


@router.post("/generalize-pack")
def generalize_pack(body: GeneralizePackBody) -> dict[str, object]:
    if not body.consent_share_template:
        raise HTTPException(
            status_code=403,
            detail={
                "requires_consent": True,
                "message": "Set consent_share_template=true to export a candidate pack.",
            },
        )
    from app.ai_pack_generalizer import generalize_with_optional_llm

    try:
        result = generalize_with_optional_llm(
            body.spec_json,
            pack_slug=body.pack_slug,
            use_llm=body.use_llm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, **result}


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
            rejected_reuse_models=body.rejected_reuse_models or None,
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
        if body.overlap_choice and isinstance(draft, dict):
            from app.ai_overlap import record_overlap_choice

            draft = record_overlap_choice(
                draft,
                finding_id=body.overlap_finding_id,
                choice=body.overlap_choice,
            )
    except AiAssistUnavailable as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "AI returned malformed JSON. Click Create draft again, shorten the prompt, "
                "or use a ready-made template at the bottom of Draft Studio."
            ),
        ) from exc
    except ValueError as exc:
        detail = str(exc)
        if "malformed JSON" in detail or "Expecting" in detail:
            detail = (
                "AI returned malformed JSON. Click Create draft again, shorten the prompt, "
                "or use a ready-made template at the bottom of Draft Studio."
            )
        raise HTTPException(status_code=422, detail=detail) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI draft failed: {exc}") from exc

    domain_pack = draft.get("domain_pack") if isinstance(draft, dict) else None
    return AiDraftModuleOut(
        ok=True,
        draft=draft,
        raw_response=raw,
        warnings=warnings,
        refusals=[
            ProtectedModuleRefusal(**normalize_refusal_dict(r))
            for r in refusals
            if isinstance(r, dict)
        ],
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
