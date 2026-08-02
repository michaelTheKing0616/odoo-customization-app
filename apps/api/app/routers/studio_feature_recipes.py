"""Studio feature recipe honesty catalog (M2-P0c) — no Odoo RPC required."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.studio_feature_recipes import list_feature_recipes

router = APIRouter(prefix="/studio-feature-recipes", tags=["studio-feature-recipes"])


class FeatureRecipeOut(BaseModel):
    id: str
    name: str
    status: str
    how: str
    app_surfaces: list[str]


@router.get("", response_model=list[FeatureRecipeOut])
def get_feature_recipes() -> list[FeatureRecipeOut]:
    return [FeatureRecipeOut.model_validate(r) for r in list_feature_recipes()]
