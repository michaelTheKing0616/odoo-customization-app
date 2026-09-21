"""Load static feature catalog and merge Atlas intents + Batch recipes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_SEED = Path(__file__).resolve().parent / "catalog.yaml"
_JSON = _SEED.with_suffix(".json")


@dataclass
class FeatureEntry:
    id: str
    title: str
    blurb: str
    route: str  # relative path under /connections/{id}/
    source: str  # catalog | atlas | recipe | app | batch_os
    status: str = "complete"
    can_handle: bool = True
    recipe: str | None = None
    keywords: list[str] = field(default_factory=list)
    weight: float = 1.0
    atlas_class: str | None = None
    risk: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UnsupportedPattern:
    id: str
    keywords: list[str]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_yaml(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError:
        if _JSON.is_file():
            return json.loads(_JSON.read_text(encoding="utf-8"))
        raise RuntimeError("PyYAML not installed and catalog.json missing") from None
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def _raw_catalog() -> dict[str, Any]:
    if _SEED.is_file():
        return _parse_yaml(_SEED.read_text(encoding="utf-8"))
    if _JSON.is_file():
        return json.loads(_JSON.read_text(encoding="utf-8"))
    return {"features": [], "unsupported": [], "recipe_routes": {}, "honesty": ""}


def reload_catalog() -> None:
    _raw_catalog.cache_clear()
    load_features.cache_clear()


def recipe_route_map() -> dict[str, str]:
    raw = _raw_catalog()
    routes = raw.get("recipe_routes") or {}
    return {str(k): str(v) for k, v in routes.items()}


def catalog_honesty() -> str:
    return str(_raw_catalog().get("honesty") or "")


def unsupported_patterns() -> list[UnsupportedPattern]:
    raw = _raw_catalog()
    out: list[UnsupportedPattern] = []
    for row in raw.get("unsupported") or []:
        out.append(
            UnsupportedPattern(
                id=str(row.get("id") or ""),
                keywords=[str(k).lower() for k in (row.get("keywords") or [])],
                message=str(row.get("message") or ""),
            )
        )
    return out


def _static_features() -> list[FeatureEntry]:
    raw = _raw_catalog()
    features: list[FeatureEntry] = []
    for row in raw.get("features") or []:
        features.append(
            FeatureEntry(
                id=str(row.get("id") or ""),
                title=str(row.get("title") or ""),
                blurb=str(row.get("blurb") or ""),
                route=str(row.get("route") or ""),
                source=str(row.get("source") or "catalog"),
                status=str(row.get("status") or "complete"),
                can_handle=bool(row.get("can_handle", True)),
                recipe=row.get("recipe"),
                keywords=[str(k).lower() for k in (row.get("keywords") or [])],
                weight=float(row.get("weight") or 1.0),
                atlas_class=row.get("atlas_class"),
                risk=row.get("risk"),
            )
        )
    return features


def _atlas_features() -> list[FeatureEntry]:
    """Mirror every Atlas intent as a searchable feature (data-driven)."""
    try:
        from app.batch_os.atlas.loader import load_atlas
    except Exception:  # noqa: BLE001
        return []

    routes = recipe_route_map()
    features: list[FeatureEntry] = []
    for cls in load_atlas():
        for intent in cls.intents:
            recipe = intent.recipe
            route = routes.get(recipe or "", "config")
            # Prefer journal tabs when recipe maps there; else config Atlas hub.
            if not recipe:
                route = "config"
            kw = {
                intent.title.lower(),
                intent.id.lower().replace(".", " "),
                intent.id.lower().replace(".", ""),
                *(intent.blurb.lower().split()[:8] if intent.blurb else []),
            }
            if recipe:
                kw.add(recipe.lower().replace(".", " "))
                kw.add(recipe.lower())
            for model in intent.models:
                kw.add(model.lower())
            features.append(
                FeatureEntry(
                    id=f"atlas.{intent.id}",
                    title=intent.title,
                    blurb=intent.blurb or cls.blurb,
                    route=route,
                    source="atlas",
                    status=intent.status,
                    can_handle=intent.status == "complete",
                    recipe=recipe,
                    keywords=sorted(k for k in kw if k and len(k) > 2),
                    weight=1.0,
                    atlas_class=cls.id,
                    risk=intent.risk,
                )
            )
    return features


def _recipe_features() -> list[FeatureEntry]:
    """Executable Batch OS recipes as features (auto-surfaces new recipes)."""
    try:
        from app.batch_os.recipes.registry import list_recipes
    except Exception:  # noqa: BLE001
        return []

    routes = recipe_route_map()
    features: list[FeatureEntry] = []
    for card in list_recipes():
        rid = card.id
        route = routes.get(rid, "config")
        kw = {
            card.title.lower(),
            rid.lower().replace(".", " "),
            rid.lower(),
            *(card.blurb.lower().split()[:10] if card.blurb else []),
            *{m.lower() for m in (card.models or [])},
        }
        features.append(
            FeatureEntry(
                id=f"recipe.{rid}",
                title=card.title,
                blurb=card.blurb,
                route=route,
                source="recipe",
                status=card.status,
                can_handle=card.status == "complete",
                recipe=rid,
                keywords=sorted(k for k in kw if k and len(k) > 2),
                weight=1.05 if card.status == "complete" else 0.6,
                atlas_class=card.atlas_class,
                risk=str(card.risk) if card.risk else None,
            )
        )
    return features


@lru_cache(maxsize=1)
def load_features() -> tuple[FeatureEntry, ...]:
    """Merged catalog: static features first, then atlas/recipe (dedupe by id)."""
    seen: set[str] = set()
    out: list[FeatureEntry] = []
    for entry in (*_static_features(), *_atlas_features(), *_recipe_features()):
        if not entry.id or entry.id in seen:
            continue
        if not entry.route:
            continue
        seen.add(entry.id)
        out.append(entry)
    return tuple(out)


def deep_link(connection_id: str, route: str) -> str:
    route = (route or "").lstrip("/")
    return f"/connections/{connection_id}/{route}"
